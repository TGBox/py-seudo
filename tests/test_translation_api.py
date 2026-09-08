"""Unit tests for translation API clients and settings manager."""
import io
import json
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from py_seudo.models import AnonymizationResult, MappingEntry, ReplacementCategory
from py_seudo.translation.api_client import (
    call_claude_api,
    call_gemini_api,
    call_openai_api,
    check_api_connection,
    generate_developer_report,
)
from py_seudo.translation.models import TranslationProvider, TranslationSettings
from py_seudo.translation.settings_manager import SettingsManager


def test_call_openai_api_success():
    settings = TranslationSettings(
        provider=TranslationProvider.OPENAI,
        openai_api_key="test-sk-123",
        openai_model="gpt-4o-mini",
        openai_base_url="https://api.openai.com/v1",
    )

    mock_resp = io.BytesIO(
        json.dumps({
            "choices": [
                {"message": {"content": "Sample OpenAI Developer Report"}}
            ]
        }).encode("utf-8")
    )

    with patch("urllib.request.urlopen", return_value=mock_resp):
        res = call_openai_api(settings, "Test prompt")
        assert res == "Sample OpenAI Developer Report"


def test_call_openai_api_http_error():
    settings = TranslationSettings(
        provider=TranslationProvider.OPENAI,
        openai_api_key="invalid-key",
    )

    err = urllib.error.HTTPError(
        url="https://api.openai.com/v1/chat/completions",
        code=401,
        msg="Unauthorized",
        hdrs={},
        fp=io.BytesIO(b'{"error": {"message": "Incorrect API key"}}'),
    )

    with patch("urllib.request.urlopen", side_effect=err):
        with pytest.raises(RuntimeError, match="OpenAI API error \\(401\\)"):
            call_openai_api(settings, "Test prompt")


def test_call_gemini_api_success():
    settings = TranslationSettings(
        provider=TranslationProvider.GEMINI,
        gemini_api_key="test-gemini-key",
        gemini_model="gemini-1.5-flash",
    )

    mock_resp = io.BytesIO(
        json.dumps({
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": "Sample Gemini Developer Report"}]
                    }
                }
            ]
        }).encode("utf-8")
    )

    with patch("urllib.request.urlopen", return_value=mock_resp):
        res = call_gemini_api(settings, "Test prompt")
        assert res == "Sample Gemini Developer Report"


def test_call_gemini_api_missing_key():
    settings = TranslationSettings(
        provider=TranslationProvider.GEMINI,
        gemini_api_key="",
    )
    with pytest.raises(ValueError, match="Google Gemini API-Key is missing"):
        call_gemini_api(settings, "Test")


def test_call_claude_api_success():
    settings = TranslationSettings(
        provider=TranslationProvider.CLAUDE,
        claude_api_key="sk-ant-test",
        claude_model="claude-3-5-haiku-20241022",
    )

    mock_resp = io.BytesIO(
        json.dumps({
            "content": [
                {"text": "Sample Claude Developer Report"}
            ]
        }).encode("utf-8")
    )

    with patch("urllib.request.urlopen", return_value=mock_resp):
        res = call_claude_api(settings, "Test prompt")
        assert res == "Sample Claude Developer Report"


def test_call_claude_api_missing_key():
    settings = TranslationSettings(
        provider=TranslationProvider.CLAUDE,
        claude_api_key="",
    )
    with pytest.raises(ValueError, match="Anthropic Claude API-Key is missing"):
        call_claude_api(settings, "Test")


def test_check_api_connection():
    # Local
    ok, msg = check_api_connection(TranslationProvider.LOCAL, TranslationSettings())
    assert ok is True
    assert "offline" in msg

    # OpenAI mock success
    settings = TranslationSettings(openai_api_key="valid")
    mock_resp = io.BytesIO(json.dumps({"choices": [{"message": {"content": "OK"}}]}).encode("utf-8"))
    with patch("urllib.request.urlopen", return_value=mock_resp):
        ok, msg = check_api_connection(TranslationProvider.OPENAI, settings)
        assert ok is True
        assert "OK" in msg

    # Gemini mock failure
    err = urllib.error.URLError(reason="Connection refused")
    with patch("urllib.request.urlopen", side_effect=err):
        ok, msg = check_api_connection(TranslationProvider.GEMINI, TranslationSettings(gemini_api_key="key"))
        assert ok is False
        assert "Connection refused" in msg


def test_generate_developer_report_dispatcher():
    result = AnonymizationResult(
        anonymized_esol="UNA:+.? '",
        anonymized_email="Hallo Herr Becker",
        mappings=[
            MappingEntry(
                original="123456789",
                pseudonym="999000001",
                category=ReplacementCategory.PRACTICE_IK,
                error_mirrored=True,
                diagnostic_note="Prüfzifferfehler",
            )
        ]
    )

    # Dispatcher with Local provider
    settings_local = TranslationSettings(provider=TranslationProvider.LOCAL)
    res_local = generate_developer_report(result, settings_local)
    assert "SECTION 1:" in res_local

    # Dispatcher with OpenAI provider mocked
    settings_openai = TranslationSettings(provider=TranslationProvider.OPENAI, openai_api_key="test")
    with patch("py_seudo.translation.api_client.call_openai_api", return_value="Mocked AI Report"):
        res_ai = generate_developer_report(result, settings_openai)
        assert res_ai == "Mocked AI Report"


def test_settings_manager_save_and_load(tmp_path, monkeypatch):
    from PySide6.QtCore import QSettings
    q = QSettings("py-seudo", "py-seudo")
    q.clear()

    monkeypatch.setenv("OPENAI_API_KEY", "env-openai-key")
    monkeypatch.setenv("GEMINI_API_KEY", "env-gemini-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "env-claude-key")

    s = SettingsManager.load_settings()
    assert s.openai_api_key == "env-openai-key"
    assert s.gemini_api_key == "env-gemini-key"
    assert s.claude_api_key == "env-claude-key"

    # Now explicit save
    s.openai_api_key = "custom-openai-key"
    s.provider = TranslationProvider.OPENAI
    SettingsManager.save_settings(s)

    reloaded = SettingsManager.load_settings()
    assert reloaded.openai_api_key == "custom-openai-key"
    assert reloaded.provider == TranslationProvider.OPENAI

    # Reset back to local so other tests are unaffected
    reloaded.provider = TranslationProvider.LOCAL
    SettingsManager.save_settings(reloaded)
