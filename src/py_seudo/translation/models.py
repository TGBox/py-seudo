"""Data models for translation and English developer report generation."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class TranslationProvider(str, Enum):
    LOCAL = "local"
    OPENAI = "openai"
    GEMINI = "gemini"
    CLAUDE = "claude"

    @property
    def display_name(self) -> str:
        names = {
            TranslationProvider.LOCAL: "Lokaler Generator (Offline, DSGVO-konform)",
            TranslationProvider.OPENAI: "OpenAI / Kompatibel (z. B. GPT-4o, Ollama)",
            TranslationProvider.GEMINI: "Google Gemini",
            TranslationProvider.CLAUDE: "Anthropic Claude",
        }
        return names.get(self, self.value)


@dataclass
class TranslationSettings:
    provider: TranslationProvider = TranslationProvider.LOCAL
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_base_url: str = ""
    gemini_api_key: str = ""
    gemini_model: str = "gemini-1.5-flash"
    claude_api_key: str = ""
    claude_model: str = "claude-3-5-haiku-20241022"
