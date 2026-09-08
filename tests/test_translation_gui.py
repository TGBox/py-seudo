"""GUI integration tests for EnglishTabWidget and ApiSettingsDialog."""
from pathlib import Path
from unittest.mock import patch

import pytest
from PySide6.QtWidgets import QMessageBox

from py_seudo.engine import PseudoEngine
from py_seudo.gui.api_settings_dialog import ApiSettingsDialog
from py_seudo.gui.app import MainWindow
from py_seudo.gui.english_tab import EnglishTabWidget
from py_seudo.samples import SAMPLE_EMAIL_REJECTION, SAMPLE_ESOL_WITH_ERRORS
from py_seudo.translation.models import TranslationProvider, TranslationSettings
from py_seudo.translation.settings_manager import SettingsManager


def test_english_tab_widget_init(qtbot):
    s = SettingsManager.load_settings()
    s.provider = TranslationProvider.LOCAL
    SettingsManager.save_settings(s)

    tab = EnglishTabWidget()
    qtbot.addWidget(tab)

    assert tab.provider_combo.count() == 4
    assert tab.provider_combo.currentData() == TranslationProvider.LOCAL
    assert "Lokaler Generator" in tab.status_badge.text()
    assert tab.editor.toPlainText() == ""


def test_english_tab_widget_set_result(qtbot):
    tab = EnglishTabWidget()
    qtbot.addWidget(tab)

    engine = PseudoEngine()
    result = engine.process(esol_text=SAMPLE_ESOL_WITH_ERRORS, email_text=SAMPLE_EMAIL_REJECTION)

    tab.set_result(result)
    text = tab.get_report_text()
    assert "SECTION 1: SUMMARY OF PROBLEMS & REJECTION REASONS" in text
    assert "SECTION 2: ENGLISH TRANSLATION OF ANONYMIZED EMAIL" in text
    assert "SECTION 2: TECHNICAL CONTEXT" not in text
    assert "Zeichen" in tab.stats_label.text()

    # Manual edit signal test
    edited_text = []
    tab.report_edited.connect(lambda t: edited_text.append(t))
    tab.editor.setPlainText("Manually modified report")
    assert edited_text == ["Manually modified report"]
    assert tab.get_report_text() == "Manually modified report"


def test_english_tab_provider_change_and_regenerate(qtbot):
    tab = EnglishTabWidget()
    qtbot.addWidget(tab)

    # Change to Claude
    idx = tab.provider_combo.findData(TranslationProvider.CLAUDE)
    tab.provider_combo.setCurrentIndex(idx)
    assert "Claude" in tab.status_badge.text()

    # Change to OpenAI
    idx_oa = tab.provider_combo.findData(TranslationProvider.OPENAI)
    tab.provider_combo.setCurrentIndex(idx_oa)
    assert "OpenAI" in tab.status_badge.text()

    # Reset
    s = SettingsManager.load_settings()
    s.provider = TranslationProvider.LOCAL
    SettingsManager.save_settings(s)


def test_api_settings_dialog(qtbot):
    dlg = ApiSettingsDialog()
    qtbot.addWidget(dlg)

    dlg.openai_key_edit.setText("sk-test-12345")
    dlg.openai_model_edit.setText("gpt-4o")
    dlg.gemini_key_edit.setText("aiza-test-67890")
    dlg.claude_key_edit.setText("sk-ant-test-999")

    dlg._save()

    loaded = SettingsManager.load_settings()
    assert loaded.openai_api_key == "sk-test-12345"
    assert loaded.openai_model == "gpt-4o"
    assert loaded.gemini_api_key == "aiza-test-67890"
    assert loaded.claude_api_key == "sk-ant-test-999"


def test_mainwindow_english_integration(qtbot, tmp_path):
    win = MainWindow()
    qtbot.addWidget(win)

    # Verify tab 4 exists
    tab_titles = [win.tabs.tabText(i) for i in range(win.tabs.count())]
    assert any("Englisch" in t for t in tab_titles)

    # Load demo errors
    win._load_demo_errors()
    assert win.esol_box.file_content
    assert win.email_box.file_content

    # Run anonymization
    win._run_anonymization()
    assert win.current_result is not None
    assert win.english_tab.get_report_text() != ""
    assert "SECTION 1:" in win.english_tab.get_report_text()

    # Test save flow writes english report file
    with patch("PySide6.QtWidgets.QFileDialog.getExistingDirectory", return_value=str(tmp_path)), \
         patch.object(QMessageBox, "information") as mock_info, \
         patch.object(QMessageBox, "warning", return_value=QMessageBox.StandardButton.Yes):

        win._save_anonymized_files()

        # Check saved files
        files = list(tmp_path.glob("*_summary_and_email_en.txt"))
        assert len(files) == 1, f"Expected 1 english report file, got: {files}"
        en_content = files[0].read_text(encoding="utf-8")
        assert "SECTION 1: SUMMARY OF PROBLEMS & REJECTION REASONS" in en_content
        assert "SECTION 2: ENGLISH TRANSLATION OF ANONYMIZED EMAIL" in en_content
        assert "SECTION 2: TECHNICAL CONTEXT" not in en_content

    # Test reset
    win._reset_all()
    assert win.english_tab.get_report_text() == ""


def test_english_tab_copy_and_save_single(qtbot, tmp_path):
    tab = EnglishTabWidget()
    qtbot.addWidget(tab)

    # Empty copy does nothing
    tab._copy_to_clipboard()

    # With content
    tab.editor.setPlainText("Test Report Content")
    with patch.object(QMessageBox, "information"):
        tab._copy_to_clipboard()

    # Save single report
    target_file = str(tmp_path / "custom_report.txt")
    with patch("PySide6.QtWidgets.QFileDialog.getSaveFileName", return_value=(target_file, "Text (*.txt)")), \
         patch.object(QMessageBox, "information"):
        tab._save_single_report()

    assert Path(target_file).exists()
    assert Path(target_file).read_text(encoding="utf-8") == "Test Report Content"


def test_api_settings_dialog_test_actions(qtbot):
    dlg = ApiSettingsDialog()
    qtbot.addWidget(dlg)

    with patch("py_seudo.gui.api_settings_dialog.check_api_connection", return_value=(True, "All good")), \
         patch.object(QMessageBox, "information") as mock_info:
        dlg._test_openai()
        dlg._test_gemini()
        dlg._test_claude()
        assert mock_info.call_count == 3

    with patch("py_seudo.gui.api_settings_dialog.check_api_connection", return_value=(False, "Failed connection")), \
         patch.object(QMessageBox, "critical") as mock_crit:
        dlg._test_openai()
        dlg._test_gemini()
        dlg._test_claude()
        assert mock_crit.call_count == 3


def test_english_tab_regenerate_flow(qtbot):
    tab = EnglishTabWidget()
    qtbot.addWidget(tab)

    engine = PseudoEngine()
    result = engine.process(esol_text=SAMPLE_ESOL_WITH_ERRORS, email_text=SAMPLE_EMAIL_REJECTION)
    tab.current_result = result

    # Regenerate local
    tab.regenerate()
    assert "SECTION 1:" in tab.get_report_text()

    # Regenerate with mocked exception
    with patch("py_seudo.gui.english_tab.generate_developer_report", side_effect=RuntimeError("API down")), \
         patch.object(QMessageBox, "critical") as mock_crit:
        tab.regenerate()
        assert mock_crit.call_count == 1

