"""Tests for ESOL EDIFACT anonymization logic."""
import pytest
from py_seudo.edifact.anonymizer import EsolAnonymizer
from py_seudo.models import ReplacementCategory


def test_kassen_ik_and_diagnoses_preserved():
    raw = (
        "UNA:+.? '\n"
        "UNB+UNOC:3+123456789:2+101575519:2+20240410:1430+REF01++DTA'\n"
        "UNH+1+SLLA:15:0:0'\n"
        "FKT+01+123456789+101575519'\n"
        "NAD+FPR+123456789+++Praxis Dr. Real+Bahnhofstr. 1+Muenchen++80331+DE'\n"
        "NAD+KTR+101575519+++Barmer Ersatzkasse'\n"
        "DIA+M54.5'\n"
        "ENF+21201+10+45.50'\n"
        "UNT+7+1'\n"
        "UNZ+1+REF01'\n"
    )
    anon = EsolAnonymizer(raw)
    out_text, mappings = anon.anonymize()

    # Kassen-IK 101575519 MUST remain untouched in UNB, FKT, and NAD+KTR
    assert "101575519" in out_text
    assert "Barmer Ersatzkasse" in out_text
    assert "DIA+M54.5" in out_text
    assert "ENF+21201+10+45.50" in out_text

    # Practice IK 123456789 MUST be replaced
    assert "123456789" not in out_text
    assert "999000001" in out_text

    # Real practice name and address MUST be replaced
    assert "Praxis Dr. Real" not in out_text
    assert "Bahnhofstr. 1" not in out_text
    assert "Muenchen" not in out_text


def test_patient_pseudonymization():
    raw = (
        "UNH+1+SLLA:15:0:0'\n"
        "NAD+VP+A123456789+++Schmidt+Erika+Blumenweg 5+Hamburg++20095+DE'\n"
        "DTM+102:19750824:102'\n"
        "UNT+3+1'\n"
    )
    anon = EsolAnonymizer(raw)
    out_text, mappings = anon.anonymize()

    # Real names and addresses removed
    assert "Schmidt" not in out_text
    assert "Erika" not in out_text
    assert "Blumenweg 5" not in out_text
    assert "Hamburg" not in out_text
    assert "20095" not in out_text
    assert "A123456789" not in out_text

    # Syntactically valid dummy KVNR (10 chars, letter + 9 digits)
    assert "X000000001" in out_text

    # Birth year preserved (1975), month/day standardized to 0615
    assert "19750615" in out_text
    assert "19750824" not in out_text

    # Verify registered mapping categories
    categories = {m.category for m in mappings}
    assert ReplacementCategory.KVNR in categories
    assert ReplacementCategory.PATIENT_NAME in categories
    assert ReplacementCategory.BIRTHDATE in categories
    assert ReplacementCategory.ADDRESS in categories


def test_doctor_pseudonymization():
    raw = (
        "UNH+1+SLLA:15:0:0'\n"
        "NAD+ARZ+123456789+++Dr. med. Martin Mueller'\n"
        "BES+876543210+123456789+20240215'\n"
        "EHE+VERORD998877'\n"
        "UNT+4+1'\n"
    )
    anon = EsolAnonymizer(raw)
    out_text, mappings = anon.anonymize()

    assert "Dr. med. Martin Mueller" not in out_text
    assert "Martin Mueller" not in out_text
    assert "876543210" not in out_text
    assert "VERORD998877" not in out_text

    # Valid dummy LANR and BSNR
    assert "888000001" in out_text
    assert "777000002" in out_text
    assert "BELEG9990001" in out_text


def test_specified_practice_ik_override():
    raw = (
        "UNH+1+SLGA:15:0:0'\n"
        "REC+555666777+RE123+20240101'\n"
        "UNT+2+1'\n"
    )
    anon = EsolAnonymizer(raw, specified_practice_ik="555666777")
    out_text, mappings = anon.anonymize()

    assert "555666777" not in out_text
    assert "999000001" in out_text


def test_slla21_heilmittel_file():
    from pathlib import Path
    esol_file = Path("testdata/in/ESOL0001")
    if not esol_file.exists():
        pytest.skip("testdata/in/ESOL0001 not present")

    text = esol_file.read_text(encoding="latin-1")
    anon = EsolAnonymizer(text)
    out_text, mappings = anon.anonymize()

    # Practice IK pseudonymized
    assert "480512931" not in out_text
    # Patient name pseudonymized
    assert "Appenzeller" not in out_text
    assert "Abel" not in out_text
    # Birthdate year preserved (2019), month/day standardized to 0615
    assert "20190615" in out_text
    assert "20190118" not in out_text
    # Doctor LANR and BSNR in ZHE pseudonymized
    assert "242325300" not in out_text
    assert "963752734" not in out_text
    # Kassen-IKs preserved
    assert "660510336" in out_text
    assert "104080005" in out_text
    # Position numbers and diagnosis preserved
    assert "54103" in out_text
    assert "R29.2" in out_text

