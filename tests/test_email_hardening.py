"""E-Mail-Pfad: Header, Anhaenge, Fehlerfaelle, Binaerdateien, Telefonerkennung."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from py_seudo.email.anonymizer import EmailAnonymizer
from py_seudo.engine import PseudoEngine


def _mail(body_parts: str, extra_headers: str = "") -> str:
    return (
        "From: Andrea Becker <a.becker@tk.de>\n"
        "To: praxis@sonnenschein.de\n"
        "Subject: Rueckweisung\n"
        f"{extra_headers}"
        "MIME-Version: 1.0\n"
        'Content-Type: multipart/mixed; boundary="BB"\n\n'
        f"{body_parts}--BB--\n"
    )


def test_unknown_headers_are_dropped():
    raw = _mail(
        "--BB\nContent-Type: text/plain\n\nHallo\n",
        extra_headers=(
            "Return-Path: <andrea.becker@tk.de>\n"
            "Reply-To: Andrea Becker <a.becker@tk.de>\n"
            "Delivered-To: praxis.mueller@sonnenschein.de\n"
            "X-Sender-Name: Andrea Becker\n"
            "References: <abc@sonnenschein-therapie.de>\n"
        ),
    )
    out, _ = EmailAnonymizer(raw).anonymize()
    for leak in ("Return-Path", "Reply-To", "Delivered-To", "X-Sender-Name", "References",
                 "Andrea Becker", "sonnenschein"):
        assert leak not in out
    assert "Subject: Rueckweisung" in out


def test_binary_attachment_is_replaced_by_placeholder():
    raw = _mail(
        "--BB\nContent-Type: text/plain\n\nHallo\n"
        '--BB\nContent-Type: application/pdf; name="Meier_Anna.pdf"\n'
        'Content-Disposition: attachment; filename="Meier_Anna.pdf"\n'
        "Content-Transfer-Encoding: base64\n\nSGVsbG8=\n"
    )
    out, _ = EmailAnonymizer(raw).anonymize()
    assert "Meier_Anna" not in out
    assert "SGVsbG8=" not in out
    assert "Anhang entfernt (application/pdf" in out


def test_text_attachment_is_anonymized_and_renamed():
    raw = _mail(
        "--BB\nContent-Type: text/plain\n\nHallo\n"
        '--BB\nContent-Type: text/plain; name="Protokoll_Meier.txt"\n'
        'Content-Disposition: attachment; filename="Protokoll_Meier.txt"\n\n'
        "Patientin Anna Meier, KVNR A123456789\n"
    )
    out, _ = EmailAnonymizer(raw).anonymize()
    assert "Protokoll_Meier" not in out
    assert "Anna Meier" not in out
    assert "A123456789" not in out
    assert 'filename="anhang_' in out


def test_attached_email_is_removed():
    raw = _mail(
        "--BB\nContent-Type: text/plain\n\nHallo\n"
        "--BB\nContent-Type: message/rfc822\n\n"
        "From: Patientin Anna Meier <anna@meier.de>\nSubject: x\n\nText\n"
    )
    out, _ = EmailAnonymizer(raw).anonymize()
    assert "anna@meier.de" not in out
    assert "Anhang entfernt (message/rfc822" in out


def test_failing_text_part_is_removed_and_reported():
    raw = _mail("--BB\nContent-Type: text/plain\n\nPatientin Anna Meier\n")
    anon = EmailAnonymizer(raw)
    with patch.object(EmailAnonymizer, "_extract_message_text", side_effect=RuntimeError("kaputt")):
        out, _ = anon.anonymize()
    assert "Anna Meier" not in out
    assert "entfernt, konnte nicht sicher verarbeitet werden" in out
    assert anon.suspicions


def test_failing_part_blocks_export_until_acknowledged():
    raw = _mail("--BB\nContent-Type: text/plain\n\nHallo\n")
    with patch.object(EmailAnonymizer, "_extract_message_text", side_effect=RuntimeError("kaputt")):
        result = PseudoEngine().process(email_text=raw)
    assert result.suspicions


@pytest.mark.parametrize("label", ["ESOL-Datei", "E-Mail"])
def test_binary_input_is_rejected(label):
    msg_like = "\xd0\xcf\x11\xe0" + "\x00".join("Patientin Anna Meier")
    kwargs = {"esol_text": msg_like} if label == "ESOL-Datei" else {"email_text": msg_like}
    with pytest.raises(ValueError, match="Binärdatei"):
        PseudoEngine().process(**kwargs)


@pytest.mark.parametrize(
    "text, bleibt",
    [
        ("Kassen-IK 0101575519 im Text.\n", "0101575519"),
        ("Belegnummer 0987654 3210.\n", "0987654 3210"),
        ("Rechnungsnummer: 0123 456789\n", "0123 456789"),
    ],
)
def test_identifiers_are_not_mistaken_for_phone_numbers(text, bleibt):
    out, _ = EmailAnonymizer(text).anonymize()
    assert bleibt in out


@pytest.mark.parametrize(
    "text, weg",
    [
        ("Tel 030 1234567\n", "030 1234567"),
        ("Telefon: 0221/123456\n", "0221/123456"),
        ("Fax: 089 555-12345\n", "089 555-12345"),
        ("erreichbar unter 030 98765432\n", "030 98765432"),
        ("+49 30 1234567\n", "30 1234567"),
    ],
)
def test_phone_numbers_are_still_replaced(text, weg):
    out, _ = EmailAnonymizer(text).anonymize()
    assert weg not in out


def test_kvnr_and_birthdate_replaced_without_esol():
    out, mappings = EmailAnonymizer("KVNR A123456789, geb. 24.08.1975\n").anonymize()
    assert "A123456789" not in out
    assert "24.08.1975" not in out
    assert "15.06.1975" in out
    # gleiche KVNR -> gleiches Pseudonym
    out2, _ = EmailAnonymizer("A123456789 und A123456789\n").anonymize()
    first, second = out2.split(" und ")
    assert first.strip() == second.strip()
