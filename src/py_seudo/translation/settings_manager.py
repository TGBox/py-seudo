"""Settings manager for translation configuration with QSettings and environment variable fallback."""
from __future__ import annotations

import os
from PySide6.QtCore import QSettings

from py_seudo.translation.models import TranslationProvider, TranslationSettings

ORGANIZATION = "py-seudo"
APPLICATION = "py-seudo"


class SettingsManager:
    """Manages persistent translation configuration."""

    @classmethod
    def load_settings(cls) -> TranslationSettings:
        q = QSettings(ORGANIZATION, APPLICATION)

        provider_str = q.value("translation/provider", TranslationProvider.LOCAL.value)
        try:
            provider = TranslationProvider(str(provider_str))
        except ValueError:
            provider = TranslationProvider.LOCAL

        openai_key = str(q.value("translation/openai_api_key", "")).strip()
        if not openai_key:
            openai_key = os.environ.get("OPENAI_API_KEY", "").strip()

        openai_model = str(q.value("translation/openai_model", "gpt-4o-mini")).strip() or "gpt-4o-mini"
        openai_base = str(q.value("translation/openai_base_url", "")).strip()

        gemini_key = str(q.value("translation/gemini_api_key", "")).strip()
        if not gemini_key:
            gemini_key = os.environ.get("GEMINI_API_KEY", "") or os.environ.get("GOOGLE_API_KEY", "")
            gemini_key = gemini_key.strip()

        gemini_model = str(q.value("translation/gemini_model", "gemini-1.5-flash")).strip() or "gemini-1.5-flash"

        claude_key = str(q.value("translation/claude_api_key", "")).strip()
        if not claude_key:
            claude_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()

        claude_model = str(q.value("translation/claude_model", "claude-3-5-haiku-20241022")).strip() or "claude-3-5-haiku-20241022"

        return TranslationSettings(
            provider=provider,
            openai_api_key=openai_key,
            openai_model=openai_model,
            openai_base_url=openai_base,
            gemini_api_key=gemini_key,
            gemini_model=gemini_model,
            claude_api_key=claude_key,
            claude_model=claude_model,
        )

    @classmethod
    def save_settings(cls, settings: TranslationSettings) -> None:
        q = QSettings(ORGANIZATION, APPLICATION)
        q.setValue("translation/provider", settings.provider.value)
        q.setValue("translation/openai_api_key", settings.openai_api_key)
        q.setValue("translation/openai_model", settings.openai_model)
        q.setValue("translation/openai_base_url", settings.openai_base_url)
        q.setValue("translation/gemini_api_key", settings.gemini_api_key)
        q.setValue("translation/gemini_model", settings.gemini_model)
        q.setValue("translation/claude_api_key", settings.claude_api_key)
        q.setValue("translation/claude_model", settings.claude_model)
        q.sync()
