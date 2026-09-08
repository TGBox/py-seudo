"""Tests for PseudoEngine orchestration and audit file exports."""
import json
import csv
from pathlib import Path
import pytest
from py_seudo.engine import PseudoEngine
from py_seudo.models import ReplacementCategory
from py_seudo.samples import SAMPLE_EMAIL, SAMPLE_ESOL


def test_pseudo_engine_end_to_end():
    engine = PseudoEngine()
    result = engine.process(esol_text=SAMPLE_ESOL, email_text=SAMPLE_EMAIL)

    assert result.total_replacements > 0
    assert len(result.mappings) >= 10
    assert len(result.practice_iks) == 1
    assert "123456789" in result.practice_iks
    assert "101575519" in result.kassen_iks

    # Ensure cross-file consistency:
    # Check that patient KVNR in anonymized ESOL is the same as in anonymized Email
    kvnr_entry = next(m for m in result.mappings if m.category == ReplacementCategory.KVNR)
    assert kvnr_entry.pseudonym in result.anonymized_esol
    assert kvnr_entry.pseudonym in result.anonymized_email

    # Check practice IK
    ik_entry = next(m for m in result.mappings if m.category == ReplacementCategory.PRACTICE_IK)
    assert ik_entry.pseudonym in result.anonymized_esol
    assert ik_entry.pseudonym in result.anonymized_email

    # Check Doctor
    doc_entry = next(m for m in result.mappings if m.category == ReplacementCategory.DOCTOR_NAME)
    assert doc_entry.pseudonym in result.anonymized_esol
    assert doc_entry.pseudonym in result.anonymized_email


def test_export_audit_json(tmp_path: Path):
    engine = PseudoEngine()
    result = engine.process(esol_text=SAMPLE_ESOL, email_text=SAMPLE_EMAIL)

    json_path = tmp_path / "mapping_audit.json"
    PseudoEngine.export_audit_mapping_json(result, json_path)

    assert json_path.exists()
    content = json.loads(json_path.read_text(encoding="utf-8"))
    assert "GDPR_NOTICE" in content
    assert "NIEMALS" in content["GDPR_NOTICE"]
    assert len(content["mappings"]) == len(result.mappings)


def test_export_audit_csv(tmp_path: Path):
    engine = PseudoEngine()
    result = engine.process(esol_text=SAMPLE_ESOL, email_text=SAMPLE_EMAIL)

    csv_path = tmp_path / "mapping_audit.csv"
    PseudoEngine.export_audit_mapping_csv(result, csv_path)

    assert csv_path.exists()
    # utf-8-sig: die Datei traegt eine BOM, damit Excel unter Windows UTF-8 erkennt
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f, delimiter=";")
        rows = list(reader)
        # Header + rows
        assert len(rows) == len(result.mappings) + 1
        assert rows[0] == [
            "Original",
            "Pseudonym",
            "Kategorie",
            "Anzahl",
            "FehlerGespiegelt",
            "DiagnoseHinweis",
            "ManuellGeaendert",
            "Beschreibung",
        ]

    # Die BOM muss tatsaechlich vorhanden sein, sonst zeigt Excel Umlaute falsch
    assert csv_path.read_bytes().startswith(b"\xef\xbb\xbf")


def test_empty_inputs():
    engine = PseudoEngine()
    result = engine.process("", "")
    assert result.original_esol == ""
    assert result.anonymized_esol == ""
    assert result.mappings == []
    assert result.total_replacements == 0
