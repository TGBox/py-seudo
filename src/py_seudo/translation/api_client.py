"""HTTP client for optional LLM APIs (OpenAI, Gemini, Claude) using urllib.request."""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Dict, Tuple

from py_seudo.models import AnonymizationResult
from py_seudo.translation.local_generator import LocalReportGenerator
from py_seudo.translation.models import TranslationProvider, TranslationSettings

SYSTEM_PROMPT = """You are an expert technical writer and German healthcare billing (§ 302 SGB V) specialist.
Your task is to generate a clean, professional English developer handover report in text format for foreign software developers.
The input consists of an already-anonymized rejection email and a list of detected billing rejection errors.

Strictly format your response in two clearly labeled sections:
================================================================================
PY-SEUDO DEVELOPER HANDOVER REPORT (ENGLISH)
================================================================================

--------------------------------------------------------------------------------
SECTION 1: SUMMARY OF PROBLEMS & REJECTION REASONS
--------------------------------------------------------------------------------
(Summarize why the billing was rejected, list the specific technical errors like checksum mismatch, prohibited characters, or duplicate billing, and state necessary software fixes. Do NOT include raw personal data or EDIFACT segment dumps.)

--------------------------------------------------------------------------------
SECTION 2: ENGLISH TRANSLATION OF ANONYMIZED EMAIL
--------------------------------------------------------------------------------
(Provide a complete, fluent English translation of the anonymized rejection email, preserving all pseudonymized identifiers and technical codes intact.)
================================================================================
"""


def build_user_prompt(result: AnonymizationResult) -> str:
    parts = []
    if result.anonymized_email:
        parts.append(f"--- ANONYMIZED REJECTION EMAIL (GERMAN) ---\n{result.anonymized_email}")

    mirrored = [m for m in result.mappings if m.error_mirrored]
    if mirrored:
        err_lines = [f"• {m.category.value}: {m.diagnostic_note}" for m in mirrored]
        parts.append(f"--- DETECTED / MIRRORED DEFECTS ---\n" + "\n".join(err_lines))

    return "\n\n".join(parts)


def call_openai_api(settings: TranslationSettings, prompt: str, system_prompt: str = SYSTEM_PROMPT) -> str:
    """Call OpenAI or OpenAI-compatible endpoint (e.g. Ollama, LocalAI)."""
    api_key = settings.openai_api_key.strip()
    model = settings.openai_model.strip() or "gpt-4o-mini"
    base_url = settings.openai_base_url.strip() or "https://api.openai.com/v1"
    base_url = base_url.rstrip("/")
    endpoint = f"{base_url}/chat/completions"

    headers = {
        "Content-Type": "application/json",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
    }

    req = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"].strip()
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI API error ({e.code}): {body}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Network error connecting to OpenAI endpoint: {e.reason}") from e


def call_gemini_api(settings: TranslationSettings, prompt: str, system_prompt: str = SYSTEM_PROMPT) -> str:
    """Call Google Gemini generateContent REST API."""
    api_key = settings.gemini_api_key.strip()
    if not api_key:
        raise ValueError("Google Gemini API-Key is missing.")

    model = settings.gemini_model.strip() or "gemini-1.5-flash"
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

    headers = {"Content-Type": "application/json"}
    full_text = f"{system_prompt}\n\nTask:\n{prompt}"
    payload = {
        "contents": [
            {
                "parts": [{"text": full_text}]
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
        },
    }

    req = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            candidate = data["candidates"][0]
            part = candidate["content"]["parts"][0]
            return part["text"].strip()
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Gemini API error ({e.code}): {body}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Network error connecting to Gemini API: {e.reason}") from e


def call_claude_api(settings: TranslationSettings, prompt: str, system_prompt: str = SYSTEM_PROMPT) -> str:
    """Call Anthropic Claude messages REST API."""
    api_key = settings.claude_api_key.strip()
    if not api_key:
        raise ValueError("Anthropic Claude API-Key is missing.")

    model = settings.claude_model.strip() or "claude-3-5-haiku-20241022"
    endpoint = "https://api.anthropic.com/v1/messages"

    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
    }

    payload = {
        "model": model,
        "max_tokens": 4096,
        "system": system_prompt,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.2,
    }

    req = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["content"][0]["text"].strip()
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Anthropic Claude API error ({e.code}): {body}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Network error connecting to Claude API: {e.reason}") from e


def check_api_connection(provider: TranslationProvider, settings: TranslationSettings) -> Tuple[bool, str]:
    """Test connectivity for the given provider."""
    try:
        if provider == TranslationProvider.LOCAL:
            return True, "Lokaler Generator ist sofort einsatzbereit (offline)."
        elif provider == TranslationProvider.OPENAI:
            res = call_openai_api(settings, "Say 'OK' in one word.", system_prompt="Answer briefly.")
            return True, f"Verbindung erfolgreich: {res}"
        elif provider == TranslationProvider.GEMINI:
            res = call_gemini_api(settings, "Say 'OK' in one word.", system_prompt="Answer briefly.")
            return True, f"Verbindung erfolgreich: {res}"
        elif provider == TranslationProvider.CLAUDE:
            res = call_claude_api(settings, "Say 'OK' in one word.", system_prompt="Answer briefly.")
            return True, f"Verbindung erfolgreich: {res}"
        else:
            return False, f"Unbekannter Anbieter: {provider}"
    except Exception as e:
        return False, str(e)


def generate_developer_report(result: AnonymizationResult, settings: TranslationSettings) -> str:
    """Generate the developer handover report using the configured provider."""
    if settings.provider == TranslationProvider.LOCAL:
        return LocalReportGenerator.generate_report(result)

    user_prompt = build_user_prompt(result)
    if not user_prompt.strip():
        return LocalReportGenerator.generate_report(result)

    if settings.provider == TranslationProvider.OPENAI:
        return call_openai_api(settings, user_prompt)
    elif settings.provider == TranslationProvider.GEMINI:
        return call_gemini_api(settings, user_prompt)
    elif settings.provider == TranslationProvider.CLAUDE:
        return call_claude_api(settings, user_prompt)

    return LocalReportGenerator.generate_report(result)
