"""Headless tests for PySide6 GUI components."""
import os
import pytest
from PySide6.QtWidgets import QApplication

from py_seudo.gui.app import MainWindow
from py_seudo.gui.diff_widget import DiffWidget
from py_seudo.gui.mapping_widget import MappingWidget
from py_seudo.engine import PseudoEngine
from py_seudo.samples import SAMPLE_EMAIL, SAMPLE_ESOL


@pytest.fixture(scope="session")
def qapp():
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_main_window_creation(qapp):
    window = MainWindow()
    assert window.windowTitle().startswith("py-seudo")
    assert window.is_dark_mode is True
    assert window.esol_box is not None
    assert window.email_box is not None


def test_theme_toggle(qapp):
    window = MainWindow()
    assert window.is_dark_mode is True
    assert "Light Mode" in window.theme_btn.text()

    window._toggle_theme()
    assert window.is_dark_mode is False
    assert "Dark Mode" in window.theme_btn.text()

    window._toggle_theme()
    assert window.is_dark_mode is True


def test_load_demo_data_and_anonymize(qapp):
    window = MainWindow()
    window._load_demo_data()

    assert "demo_ESOL0001.txt" in window.esol_box.path_label.text()
    assert "demo_rueckmeldung.eml" in window.email_box.path_label.text()

    # Trigger anonymization
    window._run_anonymization()

    assert window.current_result is not None
    assert window.current_result.total_replacements > 0
    assert window.save_files_btn.isEnabled() is True

    # Check that diff widgets received content
    assert len(window.esol_diff.left_edit.toPlainText()) > 0
    assert len(window.esol_diff.right_edit.toPlainText()) > 0
    assert len(window.email_diff.left_edit.toPlainText()) > 0
    assert len(window.email_diff.right_edit.toPlainText()) > 0

    # Check that mapping table is populated
    assert window.mapping_widget.table.rowCount() > 0


def test_mapping_search_filter(qapp):
    window = MainWindow()
    window._load_demo_data()
    window._run_anonymization()

    total_rows = window.mapping_widget.table.rowCount()
    assert total_rows > 0

    # Filter for non-existent text
    window.mapping_widget._filter_mappings("NON_EXISTENT_QUERY_12345")
    assert window.mapping_widget.table.rowCount() == 0

    # Clear filter
    window.mapping_widget._filter_mappings("")
    assert window.mapping_widget.table.rowCount() == total_rows


def test_reset_all(qapp):
    window = MainWindow()
    window._load_demo_data()
    window._run_anonymization()

    assert window.current_result is not None
    window._reset_all()

    assert window.current_result is None
    assert window.esol_box.file_content == ""
    assert window.email_box.file_content == ""
    assert window.save_files_btn.isEnabled() is False
    assert window.mapping_widget.table.rowCount() == 0


def test_diff_widget_copy(qapp):
    diff = DiffWidget("Test")
    diff.set_content("Line 1\nLine 2", "Line 1\nLine 2 Modified")
    assert "1 geänderte" in diff.stats_label.text()
    diff._copy_anonymized()
    clipboard = QApplication.clipboard()
    if clipboard:
        assert clipboard.text() == "Line 1\nLine 2 Modified"
