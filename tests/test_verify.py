"""Abschlusspruefung (py_seudo.verify): Lecks muessen gemeldet werden.

Jeder Fall hier stammt aus der Sicherheitspruefung vom 25.11.2026: Eingaben,
bei denen echte Daten im Output stehen blieben, ohne dass das Programm etwas
gemeldet hat. Die Anonymisierer selbst muessen diese Faelle (noch) nicht
loesen -- aber die Pruefung muss sie finden, damit Export und KI-Versand
gesperrt werden.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from py_seudo.engine import PseudoEngine
from py_seudo.models import AnonymizationResult, MappingEntry, ReplacementCategory
from py_seudo.translation.api_client import generate_developer_report
from py_seudo.translation.local_generator import LocalReportGenerator
from py_seudo.translation.models import TranslationProvider, TranslationSettings
from py_seudo.verify import UnresolvedSuspicions, recheck, verify_text

UNB = "UNA:+.? '\nUNB+UNOC:3+123456789:2+101575519:2+20240101:1200+1'\n"


def _texts(result: AnonymizationResult) -> set[str]:
    return {s.text for s in result.suspicions}


# --- Lecks werden gefunden ---------------------------------------------------

def test_email_only_leaks_are_flagged():
    mail = (
        "Patient Anna Meier, geb. 01.02.1980, KVNR A111111111,\n"
        "Anschrift Ringweg 3, 50667 Koeln. IK 123456789.\n"
    )
    r = PseudoEngine().process(email_text=mail)
    found = _texts(r)
    assert "A111111111" in found
    assert "01.02.1980" in found
    assert "123456789" in found
    assert "50667 Koeln" in found


def test_leaking_headers_and_attachment_names_are_flagged():
    mail = (
        "Return-Path: <andrea.becker@tk.de>\n"
        "From: Andrea Becker <a.becker@tk.de>\n"
        "To: praxis@sonnenschein.de\n"
        "Subject: Test\n"
        "MIME-Version: 1.0\n"
        'Content-Type: multipart/mixed; boundary="BB"\n\n'
        "--BB\nContent-Type: text/plain\n\nHallo\n"
        '--BB\nContent-Type: application/pdf\n'
        'Content-Disposition: attachment; filename="Protokoll_A123456789.pdf"\n\nAAAA\n--BB--\n'
    )
    r = PseudoEngine().process(email_text=mail)
    found = _texts(r)
    assert "andrea.becker@tk.de" in found
    assert "A123456789" in found


def test_unhandled_esol_segments_are_flagged():
    esol = UNB + (
        "NAD+PV+A111111111+++Meier+Anna+Ringweg 3+Koeln++50667+DE'\n"
        "COM+0221 123456:TE'\n"
        "COM+praxis@meier.de:EM'\n"
        "NAD+ARZ+1234567890+++Dr. Meier'\n"
        "BES+12345678+123456789'\n"
        "UNZ+1+1'\n"
    )
    r = PseudoEngine().process(esol_text=esol)
    found = _texts(r)
    assert "A111111111" in found
    assert "praxis@meier.de" in found
    assert "1234567890" in found
    assert "12345678" in found


def test_surviving_original_is_flagged():
    r = AnonymizationResult(
        anonymized_email="Hallo Meierhofer",
        mappings=[MappingEntry("Meierhofer", "Mustermann_1", ReplacementCategory.PATIENT_NAME)],
    )
    recheck(r)
    assert "Meierhofer" in _texts(r)


# --- Keine Fehlalarme bei dem, was stehen bleiben darf ------------------------

def test_pseudonyms_kassen_iks_and_dates_are_not_flagged():
    r = AnonymizationResult(
        anonymized_esol=(
            "NAD+VP+X000000001+++Mustermann_1+Max_1'\n"
            "NAD+KTR+101575519+++TK'\n"
            "DTM+472:20240315:102'\n"
            "ENF+21201+10+45.50'\n"
        ),
        anonymized_email=(
            "Kontakt: kontakt@beispiel.invalid, Tel +49 000 0000000\n"
            "Rechnungsdatum 12.03.2024\n"
        ),
        kassen_iks=["101575519"],
        mappings=[
            MappingEntry("A123456789", "X000000001", ReplacementCategory.KVNR),
            MappingEntry("Meier", "Mustermann_1", ReplacementCategory.PATIENT_NAME),
        ],
    )
    assert recheck(r) == []


def test_original_inside_pseudonym_is_not_a_leak():
    """'Mustermann' als Original darf in 'Mustermann_2' nicht anschlagen."""
    found = verify_text(
        "NAD+VP+X000000001+++Mustermann_2'",
        AnonymizationResult(
            mappings=[
                MappingEntry("Mustermann", "Mustermann_2", ReplacementCategory.PATIENT_NAME),
                MappingEntry("A123456789", "X000000001", ReplacementCategory.KVNR),
            ]
        ),
        "ESOL",
    )
    assert found == []


def test_synthetic_fixture_reports_known_gaps():
    """Die Fixture enthaelt eine Praxisadresse im NAM-Segment, die der
    Anonymisierer nicht ersetzt -- die Pruefung muss sie melden."""
    esol = Path("tests/data/slla21_synthetic.txt").read_text(encoding="utf-8")
    r = PseudoEngine().process(esol_text=esol)
    assert "55555 Testhausen" in _texts(r)


# --- Freigabe ----------------------------------------------------------------

def test_acknowledged_items_are_released_individually():
    r = PseudoEngine().process(email_text="KVNR A111111111, IK 123456789\n")
    assert {"A111111111", "123456789"} <= _texts(r)

    r.acknowledged.add("123456789")
    recheck(r)
    assert "123456789" not in _texts(r)
    assert "A111111111" in _texts(r)


def test_detector_suspicion_disappears_once_fixed():
    r = PseudoEngine().process(email_text="Patient Anna Meier, KVNR A111111111\n")
    r.anonymized_email = r.anonymized_email.replace("A111111111", "X000000099")
    r.english_report = LocalReportGenerator.generate_report(r)
    recheck(r)
    assert "A111111111" not in _texts(r)


# --- Englischer Report -------------------------------------------------------

def test_report_never_falls_back_to_original_email():
    r = PseudoEngine().process(email_text="Sehr geehrte Damen und Herren,\nPatientin Anna Meier\n")
    r.anonymized_email = ""  # Anwender hat den E-Mail-Editor geleert
    report = LocalReportGenerator.generate_report(r)
    assert "Anna Meier" not in report
    assert "No email text" in report


def test_report_is_checked_too():
    r = AnonymizationResult(english_report="Patient insurance no. A111111111")
    recheck(r)
    assert any("Englischer Report" in s.reason for s in r.suspicions)


# --- KI-Versand ----------------------------------------------------------------

def test_cloud_call_blocked_while_suspicions_open():
    r = PseudoEngine().process(email_text="Sehr geehrte Damen und Herren,\nKVNR A111111111\n")
    settings = TranslationSettings(provider=TranslationProvider.OPENAI, openai_api_key="x")
    with patch("py_seudo.translation.api_client.call_openai_api") as call:
        with pytest.raises(UnresolvedSuspicions):
            generate_developer_report(r, settings)
        call.assert_not_called()


def test_cloud_call_allowed_once_clean():
    r = PseudoEngine().process(email_text="Sehr geehrte Damen und Herren,\nKVNR A111111111\n")
    r.acknowledged.update(s.text for s in r.suspicions)
    recheck(r)
    settings = TranslationSettings(provider=TranslationProvider.OPENAI, openai_api_key="x")
    with patch("py_seudo.translation.api_client.call_openai_api", return_value="OK") as call:
        assert generate_developer_report(r, settings) == "OK"
        call.assert_called_once()


def test_local_provider_never_blocked():
    r = PseudoEngine().process(email_text="KVNR A111111111\n")
    assert r.suspicions
    settings = TranslationSettings(provider=TranslationProvider.LOCAL)
    assert "SECTION 1:" in generate_developer_report(r, settings)
