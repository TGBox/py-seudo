"""Tests for local, offline English developer report generation and translation."""
import tempfile
from pathlib import Path

from py_seudo.engine import PseudoEngine
from py_seudo.samples import (
    SAMPLE_EMAIL,
    SAMPLE_EMAIL_REJECTION,
    SAMPLE_ESOL,
    SAMPLE_ESOL_WITH_ERRORS,
)
from py_seudo.translation.local_generator import LocalReportGenerator


def test_local_report_with_clean_sample():
    engine = PseudoEngine()
    result = engine.process(esol_text=SAMPLE_ESOL, email_text=SAMPLE_EMAIL)

    assert result.english_report, "English report should be automatically populated"
    report = result.english_report

    # Verify 2 sections (Problem summary and Email translation)
    assert "SECTION 1: SUMMARY OF PROBLEMS & REJECTION REASONS" in report
    assert "SECTION 2: ENGLISH TRANSLATION OF ANONYMIZED EMAIL" in report

    # Verify that Section 2 with raw EDIFACT segments was removed
    assert "SECTION 2: TECHNICAL CONTEXT" not in report
    assert "Identifier Cross-Reference" not in report
    assert "NAD+FPR" not in report
    assert "NAD+VP" not in report

    # Verify diagnosis and tariff rejection detected
    assert "TARIFF REJECTION DETECTED" in report or "REJECTION" in report
    assert "Heilmittelkatalog" in report or "Remedy Catalog" in report

    # Verify translated email content
    assert "Dear" in report or "Hello" in report
    assert "rejection" in report.lower()
    assert "physical therapy" in report.lower() or "21201" in report


def test_local_report_with_mirrored_errors():
    engine = PseudoEngine()
    result = engine.process(esol_text=SAMPLE_ESOL_WITH_ERRORS, email_text=SAMPLE_EMAIL_REJECTION)

    report = result.english_report
    assert report

    # Verify status
    assert "REJECTION DETECTED" in report
    assert "FAULT(S) REPLICATED FOR DEBUGGING" in report

    # Verify specific mirrored defects are summarized
    assert "ARGE-IK Modulo-10 checksum error" in report or "check digit" in report.lower()
    assert "§ 290 SGB V" in report
    assert "Prohibited delimiter (slash '/') syntax defect" in report or "slash" in report.lower()
    assert "Duplicate billing receipt defect" in report or "duplicate" in report.lower()

    # Verify translated rejection email retains pseudonyms and translates headers
    assert "Subject:" in report
    assert "From:" in report
    assert "Check digit" in report or "check digit" in report.lower()


def test_translate_email_text_standalone():
    sample_de = """Hallo Herr Becker,

anbei sende ich Ihnen das Abweisungsprotokoll der Techniker Krankenkasse zur Abrechnungsdatei ESOL0099.
Die Kasse meldet formale Fehler in den Identifikatoren:

Sehr geehrte Damen und Herren,

Ihre Datensendung ESOL0099 konnte nicht verarbeitet werden und wurde maschinell abgewiesen.
Folgende Abweisungsgründe wurden festgestellt:

1. Institutionskennzeichen (IK): 999000001
   Fehler: Prüfziffer fehlerhaft (Prüfziffer stimmt nicht mit Modulo-10-Berechnung überein).

Bitte korrigieren Sie die Daten in Ihrem Praxisverwaltungssystem und reichen Sie eine korrigierte Neulieferung ein.

Mit freundlichen Grüßen
Alexander Testperson
TK Fachzentrum Abrechnung
"""
    translated = LocalReportGenerator.translate_email_text(sample_de)

    assert "Hello Mr. Becker," in translated
    assert "Dear Sir or Madam," in translated
    assert "Your data transmission ESOL0099 could not be processed and was automatically rejected." in translated
    assert "The following rejection reasons were identified:" in translated
    assert "Check digit invalid (check digit does not match Modulo-10 calculation)." in translated
    assert "Please correct the data in your practice management system and submit a corrected re-delivery." in translated
    assert "Sincerely / Kind regards," in translated
    assert "TK Billing Competence Center" in translated


def test_empty_inputs_report():
    engine = PseudoEngine()
    result = engine.process(esol_text="", email_text="")

    report = result.english_report
    assert "SECTION 1: SUMMARY OF PROBLEMS & REJECTION REASONS" in report
    assert "SECTION 2: ENGLISH TRANSLATION OF ANONYMIZED EMAIL" in report
    assert "(No email text was provided in this processing run.)" in report


def test_export_english_report():
    engine = PseudoEngine()
    result = engine.process(esol_text=SAMPLE_ESOL, email_text=SAMPLE_EMAIL)

    with tempfile.TemporaryDirectory() as tmpdir:
        target = Path(tmpdir) / "test_report_en.txt"
        PseudoEngine.export_english_report(result, target)

        assert target.exists()
        content = target.read_text(encoding="utf-8")
        assert "PY-SEUDO DEVELOPER HANDOVER REPORT (ENGLISH)" in content
        assert "SECTION 1:" in content
