"""Tests for email sanitization and cross-file replacement logic."""
import pytest
from py_seudo.email.anonymizer import EmailAnonymizer
from py_seudo.models import MappingEntry, ReplacementCategory


def test_rfc822_header_sanitization():
    raw_email = (
        "From: Andrea Becker <a.becker@barmer.de>\n"
        "To: Dr. Real <praxis@dr-real.de>\n"
        "Cc: chefarzt@dr-real.de\n"
        "Subject: Rueckweisung Abrechnung 123456789 - Patient Max Schmidt\n"
        "Message-ID: <12345@barmer.de>\n"
        "Received: from mail.barmer.de by mx.dr-real.de\n"
        "Content-Type: text/plain; charset=\"utf-8\"\n"
        "\n"
        "Hallo Herr Doktor,\n"
        "bitte pruefen Sie die Abrechnung fuer Max Schmidt (KVNR: A987654321)."
    )

    shared_mappings = {
        "123456789": MappingEntry("123456789", "999000001", ReplacementCategory.PRACTICE_IK),
        "Max Schmidt": MappingEntry("Max Schmidt", "Max_1 Mustermann_1", ReplacementCategory.PATIENT_NAME),
        "A987654321": MappingEntry("A987654321", "X000000001", ReplacementCategory.KVNR),
    }

    anon = EmailAnonymizer(raw_email, shared_mappings=shared_mappings)
    out_text, mappings = anon.anonymize()

    # Headers sanitized
    assert "a.becker@barmer.de" not in out_text
    assert "praxis@dr-real.de" not in out_text
    assert "chefarzt@dr-real.de" not in out_text
    assert "Message-ID" not in out_text
    assert "Received" not in out_text
    assert "Abrechnungsstelle <abrechnung@kasse.invalid>" in out_text
    assert "Praxisleitung <praxis@beispiel.invalid>" in out_text

    # Subject sanitized
    assert "123456789" not in out_text
    assert "999000001" in out_text
    assert "Max Schmidt" not in out_text
    assert "Max_1 Mustermann_1" in out_text

    # Body sanitized
    assert "A987654321" not in out_text
    assert "X000000001" in out_text


def test_plain_text_phone_and_email_masking():
    plain_text = (
        "Fehlerbericht Abrechnung:\n"
        "Patientin Anna Meier wurde abgewiesen.\n"
        "Bei Rueckfragen wenden Sie sich an support@abrechnungszentrum.de oder telefonisch:\n"
        "Zentrale: 030 / 12345678\n"
        "Mobil: +49 171 9988776\n"
        "Fax: 089 555-12345"
    )

    shared_mappings = {
        "Anna Meier": MappingEntry("Anna Meier", "Erika_1 Musterfrau_1", ReplacementCategory.PATIENT_NAME),
    }

    anon = EmailAnonymizer(plain_text, shared_mappings=shared_mappings)
    out_text, mappings = anon.anonymize()

    assert "Anna Meier" not in out_text
    assert "Erika_1 Musterfrau_1" in out_text
    assert "support@abrechnungszentrum.de" not in out_text
    assert "kontakt@beispiel.invalid" in out_text

    assert "030 / 12345678" not in out_text
    assert "+49 171 9988776" not in out_text
    assert "089 555-12345" not in out_text
    assert "+49 000 0000000" in out_text


def test_empty_email_handling():
    anon = EmailAnonymizer("")
    out_text, mappings = anon.anonymize()
    assert out_text == ""
    assert mappings == []
