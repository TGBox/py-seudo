"""Absicherung der KI-Anbindung: Transport, Schluessel, Richtlinie."""
from __future__ import annotations

import io
import json
from unittest.mock import patch

import pytest

from py_seudo.models import AnonymizationResult
from py_seudo.translation import secret_store
from py_seudo.translation.api_client import (
    call_claude_api,
    call_gemini_api,
    call_openai_api,
    describe_target,
    generate_developer_report,
    validate_base_url,
    validate_model,
)
from py_seudo.translation.models import TranslationProvider, TranslationSettings


def _resp(payload: dict) -> io.BytesIO:
    return io.BytesIO(json.dumps(payload).encode("utf-8"))


def test_gemini_key_is_sent_in_header_not_url():
    settings = TranslationSettings(gemini_api_key="geheim-123", gemini_model="gemini-1.5-flash")
    captured = {}

    def fake_urlopen(req, timeout=0):
        captured["url"] = req.full_url
        captured["headers"] = {k.lower(): v for k, v in req.header_items()}
        return _resp({"candidates": [{"content": {"parts": [{"text": "ok"}]}}]})

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        assert call_gemini_api(settings, "x") == "ok"
    assert "geheim-123" not in captured["url"]
    assert captured["headers"]["x-goog-api-key"] == "geheim-123"


@pytest.mark.parametrize(
    "url",
    ["https://api.openai.com/v1", "http://localhost:11434/v1", "http://127.0.0.1:8080/v1", ""],
)
def test_allowed_base_urls(url):
    assert validate_base_url(url)


@pytest.mark.parametrize(
    "url", ["http://llm.firma.de/v1", "ftp://example.com", "http://192.168.1.10/v1", "nonsense"]
)
def test_rejected_base_urls(url):
    with pytest.raises(ValueError):
        validate_base_url(url)


def test_openai_refuses_plain_http_to_remote_host():
    settings = TranslationSettings(openai_api_key="k", openai_base_url="http://llm.firma.de/v1")
    with patch("urllib.request.urlopen") as urlopen:
        with pytest.raises(ValueError, match="https"):
            call_openai_api(settings, "x")
        urlopen.assert_not_called()


@pytest.mark.parametrize("model", ["gpt-4o-mini", "llama3:8b", "claude-3-5-haiku-20241022"])
def test_valid_model_names(model):
    assert validate_model(model) == model


@pytest.mark.parametrize("model", ["../../evil", "a b", "x?key=1", ""])
def test_invalid_model_names(model):
    with pytest.raises(ValueError):
        validate_model(model)


def test_gemini_rejects_model_with_path_characters():
    settings = TranslationSettings(gemini_api_key="k", gemini_model="../v1/other")
    with patch("urllib.request.urlopen") as urlopen:
        with pytest.raises(ValueError):
            call_gemini_api(settings, "x")
        urlopen.assert_not_called()


def test_policy_disables_cloud(monkeypatch):
    monkeypatch.setenv("PY_SEUDO_DISABLE_CLOUD", "1")
    with patch("urllib.request.urlopen") as urlopen:
        for fn, settings in (
            (call_openai_api, TranslationSettings(openai_api_key="k")),
            (call_gemini_api, TranslationSettings(gemini_api_key="k")),
            (call_claude_api, TranslationSettings(claude_api_key="k")),
        ):
            with pytest.raises(RuntimeError, match="Richtlinie"):
                fn(settings, "x")
        urlopen.assert_not_called()

    r = AnonymizationResult(anonymized_email="Hallo")
    with pytest.raises(RuntimeError, match="Richtlinie"):
        generate_developer_report(r, TranslationSettings(provider=TranslationProvider.OPENAI))
    # Lokal geht weiterhin
    assert "SECTION 1:" in generate_developer_report(r, TranslationSettings())


def test_describe_target_names_the_host():
    s = TranslationSettings(provider=TranslationProvider.OPENAI, openai_base_url="http://localhost:11434/v1")
    assert describe_target(s).startswith("localhost")
    s = TranslationSettings(provider=TranslationProvider.CLAUDE)
    assert "api.anthropic.com" in describe_target(s)


# --- Schluesselablage -----------------------------------------------------------

def test_plain_fallback_roundtrip_off_windows(monkeypatch):
    monkeypatch.setattr(secret_store, "is_secure", lambda: False)
    stored = secret_store.protect("sk-123")
    assert stored == "plain:sk-123"
    assert secret_store.unprotect(stored) == ("sk-123", False)


def test_dpapi_path_encrypts_and_migrates(monkeypatch):
    monkeypatch.setattr(secret_store, "is_secure", lambda: True)
    # DPAPI simulieren: "verschluesseln" = umdrehen
    monkeypatch.setattr(secret_store, "_dpapi", lambda data, protect: data[::-1])
    stored = secret_store.protect("sk-123")
    assert stored.startswith("dpapi:")
    assert "sk-123" not in stored
    assert secret_store.unprotect(stored) == ("sk-123", False)
    # Altbestand im Klartext -> lesbar, aber zur Migration markiert
    assert secret_store.unprotect("sk-legacy") == ("sk-legacy", True)


def test_unreadable_dpapi_value_is_dropped(monkeypatch):
    monkeypatch.setattr(secret_store, "is_secure", lambda: True)

    def broken(data, protect):
        raise OSError("anderer Benutzer")

    monkeypatch.setattr(secret_store, "_dpapi", broken)
    assert secret_store.unprotect("dpapi:AAAA") == ("", False)


def test_settings_manager_migrates_legacy_plaintext(monkeypatch):
    from PySide6.QtCore import QSettings

    from py_seudo.translation.settings_manager import SettingsManager

    monkeypatch.setattr(secret_store, "is_secure", lambda: True)
    monkeypatch.setattr(secret_store, "_dpapi", lambda data, protect: data[::-1])
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    q = QSettings("py-seudo", "py-seudo")
    q.clear()
    q.setValue("translation/openai_api_key", "sk-legacy")

    loaded = SettingsManager.load_settings()
    assert loaded.openai_api_key == "sk-legacy"
    raw = str(QSettings("py-seudo", "py-seudo").value("translation/openai_api_key"))
    assert raw.startswith("dpapi:")
    assert "sk-legacy" not in raw
    q.clear()
