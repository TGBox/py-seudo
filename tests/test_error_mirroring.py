"""Comprehensive unit tests for healthcare identifier validation and fault-preserving mirroring (Fehler-Spiegelung)."""
import json
import csv
from pathlib import Path

import pytest

from py_seudo.engine import PseudoEngine
from py_seudo.gui.app import MainWindow
from py_seudo.models import ReplacementCategory
from py_seudo.samples import SAMPLE_EMAIL_REJECTION, SAMPLE_ESOL_WITH_ERRORS
from py_seudo.validators import (
    RejectionInspector,
    calculate_ik_check_digit,
    calculate_kvnr_check_digit,
    generate_mirrored_ik,
    generate_mirrored_kvnr,
    generate_valid_pseudo_ik,
    generate_valid_pseudo_kvnr,
    mirror_invoice_defect,
    validate_ik,
    validate_kvnr,
)


# =====================================================================
# 1. Tests for IK (Institutionskennzeichen) Check Digit & Validation
# =====================================================================

def test_ik_validation_official_real_iks():
    """Verify ARGE-IK Modulo 10 check digit over digits 3 to 8 on real institutions."""
    real_iks = [
        "101575519",  # Techniker Krankenkasse (TK)
        "104926702",  # Barmer
        "105830016",  # DAK Gesundheit
        "108018132",  # AOK Baden-Württemberg
        "108310400",  # AOK Bayern
        "109519005",  # AOK PLUS
        "101570638",  # Hanseatische Krankenkasse (HEK)
        "661430035",  # IQVIA Datenannahmestelle
    ]
    for ik in real_iks:
        is_val, err, expected_cd = validate_ik(ik)
        assert is_val is True, f"Expected {ik} to be valid, got {err} (expected {expected_cd})"
        assert err == "OK"
        assert expected_cd == int(ik[8])


def test_ik_validation_checksum_error():
    """Altered check digit must fail with CHECKSUM_ERROR."""
    # 101575519 is valid with check digit 9; altering to 8 or 0 must fail
    is_val, err, expected_cd = validate_ik("101575518")
    assert is_val is False
    assert err == "CHECKSUM_ERROR"
    assert expected_cd == 9

    is_val2, err2, exp2 = validate_ik("441234568")
    assert is_val2 is False
    assert err2 == "CHECKSUM_ERROR"
    assert exp2 == 1


def test_ik_validation_length_and_charset():
    """Invalid lengths and characters must be detected."""
    assert validate_ik("1234567")[1] == "INVALID_LENGTH"
    assert validate_ik("1234567890")[1] == "INVALID_LENGTH"
    assert validate_ik("")[1] == "INVALID_LENGTH"
    assert validate_ik("12345678A")[1] == "INVALID_CHARS"
    assert validate_ik("4400123-5")[1] == "INVALID_CHARS"


def test_ik_generate_valid_pseudo():
    """Valid pseudo IK generator must produce strictly valid IKs."""
    for i in range(1, 15):
        pseudo = generate_valid_pseudo_ik(i)
        is_val, err, _ = validate_ik(pseudo)
        assert is_val is True, f"Generated pseudo {pseudo} must be valid, got {err}"


def test_ik_defect_mirroring():
    """Defects in the original IK must be faithfully mirrored in the pseudonym."""
    # 1. Checksum error mirrored
    p_err, m_err, note_err = generate_mirrored_ik("441234568", counter=2)
    assert m_err is True
    assert "Prüfziffernfehler" in note_err
    assert validate_ik(p_err)[0] is False, f"Pseudonym {p_err} must also fail IK validation"
    assert validate_ik(p_err)[1] == "CHECKSUM_ERROR"

    # 2. Length error mirrored
    p_len, m_len, note_len = generate_mirrored_ik("4412345", counter=1)
    assert m_len is True
    assert len(p_len) == 7
    assert "Längenfehler" in note_len
    assert validate_ik(p_len)[1] == "INVALID_LENGTH"

    # 3. Invalid characters mirrored
    p_chr, m_chr, note_chr = generate_mirrored_ik("4412345A9", counter=1)
    assert m_chr is True
    assert "A" in p_chr
    assert "Formatfehler" in note_chr
    assert validate_ik(p_chr)[1] == "INVALID_CHARS"

    # 4. Semantic / status error
    p_stat, m_stat, note_stat = generate_mirrored_ik(
        "101575519", counter=1, force_error="STATUS_ERROR", diagnostic_override="IK unbekannt"
    )
    assert m_stat is True
    assert p_stat == "999999999"
    assert "IK unbekannt" in note_stat


# =====================================================================
# 2. Tests for KVNR (Krankenversichertennummer § 290 SGB V)
# =====================================================================

def test_kvnr_validation_official_examples():
    """Verify official § 290 SGB V KVNR calculation examples from GKV-Datenaustausch."""
    # Official examples from Richtlinie § 290 SGB V:
    assert validate_kvnr("A000500015") == (True, "OK", 5)
    assert validate_kvnr("C000500021") == (True, "OK", 1)


def test_kvnr_validation_checksum_error():
    """Altered check digit must fail with CHECKSUM_ERROR."""
    # A000500015 has check digit 5; 4 or 0 must fail
    is_val, err, expected_cd = validate_kvnr("A000500014")
    assert is_val is False
    assert err == "CHECKSUM_ERROR"
    assert expected_cd == 5


def test_kvnr_validation_length_and_prefix():
    """Invalid length and prefix must be detected."""
    assert validate_kvnr("A00050001")[1] == "INVALID_LENGTH"
    assert validate_kvnr("A0005000155")[1] == "INVALID_LENGTH"
    assert validate_kvnr("1000500015")[1] == "INVALID_PREFIX"
    assert validate_kvnr("A0005000X5")[1] == "INVALID_CHARS"


def test_kvnr_generate_valid_pseudo():
    """Valid pseudo KVNR generator must produce strictly valid KVNRs."""
    for i in range(1, 15):
        pseudo = generate_valid_pseudo_kvnr(i)
        is_val, err, _ = validate_kvnr(pseudo)
        assert is_val is True, f"Generated pseudo {pseudo} must be valid, got {err}"


def test_kvnr_defect_mirroring():
    """Defects in the original KVNR must be faithfully mirrored in the pseudonym."""
    # 1. Checksum error mirrored
    p_err, m_err, note_err = generate_mirrored_kvnr("Z987654329", counter=2)
    assert m_err is True
    assert "Prüfziffernfehler" in note_err
    assert validate_kvnr(p_err)[0] is False
    assert validate_kvnr(p_err)[1] == "CHECKSUM_ERROR"

    # 2. Length error mirrored
    p_len, m_len, note_len = generate_mirrored_kvnr("A123456", counter=1)
    assert m_len is True
    assert len(p_len) == 7
    assert "Längenfehler" in note_len

    # 3. Invalid prefix mirrored
    p_pre, m_pre, note_pre = generate_mirrored_kvnr("9123456789", counter=1)
    assert m_pre is True
    assert p_pre.startswith("9")
    assert "Formatfehler" in note_pre

    # 4. Status error
    p_stat, m_stat, note_stat = generate_mirrored_kvnr(
        "A000500015", counter=1, force_error="STATUS_ERROR", diagnostic_override="Versicherter nicht versichert"
    )
    assert m_stat is True
    assert "nicht versichert" in note_stat


# =====================================================================
# 3. Tests for Invoice and Receipt Number Defect Mirroring
# =====================================================================

def test_invoice_defect_mirroring():
    """Invoices with slashes, duplicates, or format defects must be mirrored."""
    # 1. Slash defect (EDIFACT illegal character)
    p_slash, m_slash, note_slash = mirror_invoice_defect("RE/2024/099", counter=1)
    assert m_slash is True
    assert "/" in p_slash
    assert "Schrägstrich" in note_slash

    # 2. Duplicate invoice error
    p_dup, m_dup, note_dup = mirror_invoice_defect(
        "RE202400123", counter=1, force_error="DUPLICATE", diagnostic_override="Doppelabrechnung gemeldet"
    )
    assert m_dup is True
    assert "Doppelabrechnung" in note_dup

    # 3. Clean invoice number
    p_clean, m_clean, _ = mirror_invoice_defect("RE202400123", counter=1)
    assert m_clean is False
    assert p_clean == "RE9990001"


# =====================================================================
# 4. Tests for Rejection Email Inspector
# =====================================================================

def test_rejection_inspector():
    """Rejection inspector extracts reported errors and associates them with IDs."""
    findings = RejectionInspector.inspect(SAMPLE_EMAIL_REJECTION)
    assert "441234568" in findings
    assert findings["441234568"]["error_type"] == "CHECKSUM_ERROR"

    assert "Z987654329" in findings
    assert findings["Z987654329"]["error_type"] == "CHECKSUM_ERROR"

    assert "BELEG_DOPPELT_77" in findings
    assert findings["BELEG_DOPPELT_77"]["error_type"] == "DUPLICATE"


# =====================================================================
# 5. End-to-End Tests with Billing Errors (ESOL + Email)
# =====================================================================

def test_end_to_end_error_mirroring(tmp_path: Path):
    """End-to-end anonymization with billing errors mirrors all defects faithfully."""
    engine = PseudoEngine()
    result = engine.process(
        esol_text=SAMPLE_ESOL_WITH_ERRORS,
        email_text=SAMPLE_EMAIL_REJECTION,
    )

    # 1. Verify that defective IK was replaced with a mirrored defective IK
    ik_mapping = next(m for m in result.mappings if m.category == ReplacementCategory.PRACTICE_IK)
    assert ik_mapping.original == "441234568"
    assert ik_mapping.error_mirrored is True
    assert "Prüfziffernfehler" in ik_mapping.diagnostic_note
    # The generated pseudonym must also fail IK check digit validation!
    assert validate_ik(ik_mapping.pseudonym)[0] is False
    assert ik_mapping.pseudonym in result.anonymized_esol
    assert ik_mapping.pseudonym in result.anonymized_email

    # 2. Verify that defective KVNR was replaced with a mirrored defective KVNR
    kvnr_mapping = next(m for m in result.mappings if m.category == ReplacementCategory.KVNR)
    assert kvnr_mapping.original == "Z987654329"
    assert kvnr_mapping.error_mirrored is True
    assert "Prüfziffernfehler" in kvnr_mapping.diagnostic_note
    # The generated pseudonym must also fail KVNR validation!
    assert validate_kvnr(kvnr_mapping.pseudonym)[0] is False
    assert kvnr_mapping.pseudonym in result.anonymized_esol
    assert kvnr_mapping.pseudonym in result.anonymized_email

    # 3. Verify that slash defect in invoice number was preserved in pseudonym
    inv_mapping = next(
        m for m in result.mappings if m.category == ReplacementCategory.INVOICE_NUMBER and "/" in m.original
    )
    assert "/" in inv_mapping.pseudonym
    assert inv_mapping.error_mirrored is True

    # 4. Verify duplicate beleg mapping
    beleg_mapping = next(
        m for m in result.mappings if m.original == "BELEG_DOPPELT_77"
    )
    assert beleg_mapping.error_mirrored is True
    assert "Doppelabrechnung" in beleg_mapping.diagnostic_note

    # 5. Audit JSON export test
    json_path = tmp_path / "audit_with_errors.json"
    PseudoEngine.export_audit_mapping_json(result, json_path)
    audit_json = json.loads(json_path.read_text(encoding="utf-8"))
    assert audit_json["total_errors_mirrored"] >= 3
    for entry in audit_json["mappings"]:
        if entry["original"] in ("441234568", "Z987654329", "RE/2024/099", "BELEG_DOPPELT_77"):
            assert entry["error_mirrored"] is True
            assert len(entry["diagnostic_note"]) > 0

    # 6. Audit CSV export test
    csv_path = tmp_path / "audit_with_errors.csv"
    PseudoEngine.export_audit_mapping_csv(result, csv_path)
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f, delimiter=";")
        rows = list(reader)
        header = rows[0]
        assert "FehlerGespiegelt" in header
        assert "DiagnoseHinweis" in header
        ik_row = next(r for r in rows[1:] if r[0] == "441234568")
        assert ik_row[4] == "Ja"  # FehlerGespiegelt column
        assert "Prüfziffer" in ik_row[5]  # DiagnoseHinweis column


# =====================================================================
# 6. GUI Integration Test for Error Demo Loading & Badges
# =====================================================================

def test_gui_load_demo_errors_and_badges(qapp):
    """GUI button for demo errors loads sample and displays ⚠️ Gespiegelt badges."""
    window = MainWindow()
    window._load_demo_errors()
    assert "demo_ESOL0099_fehler.txt" in window.esol_box.path_label.text()
    assert "demo_rueckweisung_email.eml" in window.email_box.path_label.text()

    window._run_anonymization()
    assert window.current_result is not None
    assert len(window.current_result.mappings) > 0

    table = window.mapping_widget.table
    assert table.columnCount() == 6
    assert table.horizontalHeaderItem(4).text() == "Fehler-Spiegelung"

    # Find at least one row with the mirrored error badge
    found_badge = False
    for r in range(table.rowCount()):
        status_item = table.item(r, 4)
        if status_item and "Gespiegelt" in status_item.text():
            found_badge = True
            break
    assert found_badge is True, "Expected to find at least one '⚠️ Gespiegelt' status badge in table"
