"""Tests for manual editing capabilities in preview panes, mapping table, and audit trail."""
from __future__ import annotations

import csv
import json
from pathlib import Path
from unittest.mock import patch

import pytest
from PySide6.QtCore import Qt

from py_seudo.engine import PseudoEngine
from py_seudo.gui.app import MainWindow
from py_seudo.gui.mapping_widget import AddMappingDialog
from py_seudo.models import AnonymizationResult, MappingEntry, ReplacementCategory
from py_seudo.samples import SAMPLE_EMAIL, SAMPLE_ESOL


def test_inplace_mapping_table_edit(qapp):
    """Editing pseudonym cell in table updates entry, badge, and propagates to preview widgets."""
    window = MainWindow()
    window._load_demo_data()
    window._run_anonymization()

    assert window.current_result is not None
    table = window.mapping_widget.table
    assert table.rowCount() > 0

    # Locate first mapping row
    first_entry = window.current_result.mappings[0]
    old_pseudo = first_entry.pseudonym
    new_pseudo = "MEIN_WUNSCH_PSEUDONYM_99"

    # Find row with this pseudonym
    target_row = -1
    for r in range(table.rowCount()):
        item = table.item(r, 2)
        if item and item.text() == old_pseudo:
            target_row = r
            break
    assert target_row >= 0

    # Ensure pseudonym item is editable
    pseudo_item = table.item(target_row, 2)
    assert bool(pseudo_item.flags() & Qt.ItemFlag.ItemIsEditable) is True

    # Simulate user in-place edit
    pseudo_item.setText(new_pseudo)

    # 1. Verify MappingEntry updated
    assert first_entry.pseudonym == new_pseudo
    assert first_entry.is_manual is True

    # 2. Verify status badge updated to ✏️ Manuell
    status_item = table.item(target_row, 4)
    assert status_item is not None
    assert "Manuell" in status_item.text()

    # 3. Verify propagation to DiffWidgets
    if old_pseudo in window.current_result.original_esol or old_pseudo in window.esol_diff.get_anonymized_text():
        assert new_pseudo in window.esol_diff.get_anonymized_text()
    if old_pseudo in window.email_diff.get_anonymized_text():
        assert new_pseudo in window.email_diff.get_anonymized_text()


def test_add_custom_replacement_dialog_and_propagation(qapp):
    """Adding a custom replacement rule propagates replacement into ESOL and E-Mail."""
    window = MainWindow()
    window._load_demo_data()
    window._run_anonymization()

    initial_count = len(window.current_result.mappings)

    orig_str = "Praxis Physiotherapie Schulz"
    custom_pseudo = "Physio-Zentrum Sonnenschein"

    new_entry = MappingEntry(
        original=orig_str,
        pseudonym=custom_pseudo,
        category=ReplacementCategory.PRACTICE_IK,
        is_manual=True,
    )

    # Emit signal as if AddMappingDialog was accepted
    window.mapping_widget.mapping_added.emit(new_entry)

    # Verify entry added to result
    assert len(window.current_result.mappings) == initial_count + 1
    added = window.current_result.mappings[-1]
    assert added.original == orig_str
    assert added.pseudonym == custom_pseudo
    assert added.is_manual is True

    # Verify text was replaced in DiffWidgets
    if orig_str in window.current_result.original_esol:
        assert custom_pseudo in window.esol_diff.get_anonymized_text()
    if orig_str in window.current_result.original_email:
        assert custom_pseudo in window.email_diff.get_anonymized_text()


def test_add_mapping_dialog_validation(qapp):
    """AddMappingDialog validates input and constructs valid MappingEntry."""
    dlg = AddMappingDialog()
    assert dlg.windowTitle() != ""

    # Empty inputs fail validation
    with patch("py_seudo.gui.mapping_widget.QMessageBox.warning") as mock_warn:
        dlg._on_accept()
        mock_warn.assert_called()

    # Valid inputs
    dlg.orig_edit.setText("Sensible Angabe")
    dlg.pseudo_edit.setText("Anonyme Angabe")
    entry = dlg.get_entry()
    assert entry.original == "Sensible Angabe"
    assert entry.pseudonym == "Anonyme Angabe"
    assert entry.is_manual is True


def test_direct_preview_pane_editing_and_save(qapp, tmp_path: Path):
    """Direct edits in the right text edit are preserved upon saving."""
    window = MainWindow()
    window._load_demo_data()
    window._run_anonymization()

    # The right edit should NOT be read-only
    assert window.esol_diff.right_edit.isReadOnly() is False
    assert window.email_diff.right_edit.isReadOnly() is False

    # Perform direct manual edits in the preview panes
    esol_addition = "\nMANUELLE_ESOL_AENDERUNG_ZEILE"
    email_addition = "\nMANUELLE_EMAIL_AENDERUNG_ZEILE"

    window.esol_diff.right_edit.setPlainText(window.esol_diff.get_anonymized_text() + esol_addition)
    window.email_diff.right_edit.setPlainText(window.email_diff.get_anonymized_text() + email_addition)

    assert "MANUELLE_ESOL_AENDERUNG_ZEILE" in window.esol_diff.get_anonymized_text()
    assert "MANUELLE_EMAIL_AENDERUNG_ZEILE" in window.email_diff.get_anonymized_text()

    # Save to disk using mocked directory picker
    with patch("PySide6.QtWidgets.QFileDialog.getExistingDirectory", return_value=str(tmp_path)), \
         patch("PySide6.QtWidgets.QMessageBox.information"):
        window._save_anonymized_files()

    # Check files on disk
    saved_files = list(tmp_path.glob("*"))
    assert len(saved_files) >= 1

    all_content = "\n".join(f.read_text(encoding="utf-8", errors="ignore") for f in saved_files)
    assert "MANUELLE_ESOL_AENDERUNG_ZEILE" in all_content or "MANUELLE_EMAIL_AENDERUNG_ZEILE" in all_content


def test_audit_export_reflects_manual_edits(tmp_path: Path):
    """Audit JSON and CSV exports correctly record manual edits."""
    result = AnonymizationResult()
    result.mappings = [
        MappingEntry(
            original="123456789",
            pseudonym="999000001",
            category=ReplacementCategory.PRACTICE_IK,
            is_manual=False,
            error_mirrored=True,
            diagnostic_note="Prüfziffernfehler",
        ),
        MappingEntry(
            original="Dr. med. Schulz",
            pseudonym="Dr. med. Musterarzt_1",
            category=ReplacementCategory.DOCTOR_NAME,
            is_manual=True,
        ),
    ]

    # Test JSON export
    json_path = tmp_path / "audit.json"
    PseudoEngine.export_audit_mapping_json(result, json_path)
    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data["total_manual_edits"] == 1
    assert data["total_errors_mirrored"] == 1
    assert data["mappings"][0]["is_manual"] is False
    assert data["mappings"][1]["is_manual"] is True

    # Test CSV export
    csv_path = tmp_path / "audit.csv"
    PseudoEngine.export_audit_mapping_csv(result, csv_path)
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f, delimiter=";")
        rows = list(reader)
        header = rows[0]
        assert "ManuellGeaendert" in header
        idx = header.index("ManuellGeaendert")
        assert rows[1][idx] == "Nein"
        assert rows[2][idx] == "Ja"
