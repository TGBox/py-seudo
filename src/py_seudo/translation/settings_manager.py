"""Settings manager for translation configuration with QSettings and environment variable fallback."""
from __future__ import annotations

import os
from PySide6.QtCore import QSettings

from py_seudo.translation import secret_store
from py_seudo.translation.models import TranslationProvider, TranslationSettings

_KEY_NAMES = ("openai_api_key", "gemini_api_key", "claude_api_key")

ORGANIZATION = "py-seudo"
APPLICATION = "py-seudo"


class SettingsManager:
    """Manages persistent translation configuration."""

    @staticmethod
    def _read_secret(q: QSettings, name: str) -> tuple[str, bool]:
        return secret_store.unprotect(str(q.value(f"translation/{name}", "") or "").strip())

    @classmethod
    def load_settings(cls) -> TranslationSettings:
        q = QSettings(ORGANIZATION, APPLICATION)
        legacy: dict[str, str] = {}

        provider_str = q.value("translation/provider", TranslationProvider.LOCAL.value)
        try:
            provider = TranslationProvider(str(provider_str))
        except ValueError:
            provider = TranslationProvider.LOCAL

        openai_key, migrate = cls._read_secret(q, "openai_api_key")
        if migrate:
            legacy["openai_api_key"] = openai_key
        if not openai_key:
            openai_key = os.environ.get("OPENAI_API_KEY", "").strip()

        openai_model = str(q.value("translation/openai_model", "gpt-4o-mini")).strip() or "gpt-4o-mini"
        openai_base = str(q.value("translation/openai_base_url", "")).strip()

        gemini_key, migrate = cls._read_secret(q, "gemini_api_key")
        if migrate:
            legacy["gemini_api_key"] = gemini_key
        if not gemini_key:
            gemini_key = os.environ.get("GEMINI_API_KEY", "") or os.environ.get("GOOGLE_API_KEY", "")
            gemini_key = gemini_key.strip()

        gemini_model = str(q.value("translation/gemini_model", "gemini-1.5-flash")).strip() or "gemini-1.5-flash"

        claude_key, migrate = cls._read_secret(q, "claude_api_key")
        if migrate:
            legacy["claude_api_key"] = claude_key
        if not claude_key:
            claude_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()

        claude_model = str(q.value("translation/claude_model", "claude-3-5-haiku-20241022")).strip() or "claude-3-5-haiku-20241022"

        settings = TranslationSettings(
            provider=provider,
            openai_api_key=openai_key,
            openai_model=openai_model,
            openai_base_url=openai_base,
            gemini_api_key=gemini_key,
            gemini_model=gemini_model,
            claude_api_key=claude_key,
            claude_model=claude_model,
        )
        if legacy:
            # Unverschluesselte Altbestaende sofort verschluesselt neu ablegen
            # (nur diese -- Schluessel aus Umgebungsvariablen nie persistieren).
            for name, value in legacy.items():
                q.setValue(f"translation/{name}", secret_store.protect(value))
            q.sync()
        return settings

    @staticmethod
    def _write_secrets(q: QSettings, settings: TranslationSettings) -> None:
        for name in _KEY_NAMES:
            q.setValue(f"translation/{name}", secret_store.protect(getattr(settings, name)))

    @classmethod
    def save_settings(cls, settings: TranslationSettings) -> None:
        q = QSettings(ORGANIZATION, APPLICATION)
        q.setValue("translation/provider", settings.provider.value)
        q.setValue("translation/openai_model", settings.openai_model)
        q.setValue("translation/openai_base_url", settings.openai_base_url)
        q.setValue("translation/gemini_model", settings.gemini_model)
        q.setValue("translation/claude_model", settings.claude_model)
        cls._write_secrets(q, settings)
        q.sync()
