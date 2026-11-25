"""ESOL-Pfad: Segmente, die frueher unveraendert durchliefen, und Konsistenz."""
from __future__ import annotations

from py_seudo.edifact.anonymizer import EsolAnonymizer

UNB = "UNA:+.? '\nUNB+UNOC:3+123456789:2+101575519:2+20240401:1200+1'\n"


def run(body: str):
    anon = EsolAnonymizer(UNB + body)
    out, mappings = anon.anonymize()
    return out, mappings, anon.suspicions


def test_same_patient_gets_same_pseudonyms():
    line = "NAD+VP+A111111111+++Meier+Anna+Ringweg 3+Koeln++50667+DE'\n"
    out, mappings, _ = run(line + line)
    first, second = [l for l in out.splitlines() if l.startswith("NAD+VP")]
    assert first == second
    by_orig = {m.original: m for m in mappings}
    assert by_orig["Meier"].pseudonym in first
    assert by_orig["Meier"].count == 2


def test_kvnr_and_name_share_one_number():
    out, _, _ = run("NAD+VP+A111111111+++Meier+Anna'\n")
    assert "X000000001" in out
    assert "Mustermann_1+Max_1" in out


def test_patient_postal_code_cannot_match_real_one():
    """Dummy-PLZ 00xxx ist nicht vergeben -- frueher ersetzte 12345 durch 12345."""
    out, mappings, _ = run("NAD+VP+A111111111+++Meier+Anna+Ringweg 3+Koeln++12345+DE'\n")
    assert "++12345+" not in out
    plz = next(m for m in mappings if m.original == "12345")
    assert plz.pseudonym.startswith("00")


def test_service_date_after_patient_is_kept():
    out, _, _ = run(
        "NAD+VP+A111111111+++Meier+Anna'\n"
        "DTM+472:20240315:102'\n"
    )
    assert "DTM+472:20240315:102'" in out


def test_old_date_after_patient_is_treated_as_birthdate():
    out, _, _ = run(
        "NAD+VP+A111111111+++Meier+Anna'\n"
        "DTM+999:19800101:102'\n"
    )
    assert "19800101" not in out
    assert "19800615" in out


def test_unknown_nad_qualifier_is_fully_replaced_and_reported():
    out, _, suspicions = run("NAD+PV+A111111111+++Meier+Anna+Ringweg 3+Koeln++50667+DE'\n")
    for leak in ("A111111111", "Meier", "Anna", "Ringweg", "Koeln", "50667"):
        assert leak not in out
    assert "+DE'" in out  # Laenderkennzeichen bleibt
    assert any(s.text == "NAD+PV" for s in suspicions)


def test_slla_nad_without_birthdate_is_not_passed_through():
    out, _, suspicions = run("NAD+Meier+Anna+Ringweg 3'\n")
    assert "Meier" not in out and "Ringweg" not in out
    assert suspicions


def test_kassen_ik_in_unknown_nad_is_kept():
    out, _, _ = run("NAD+XY+101575519+++Meier'\n")
    assert "101575519" in out
    assert "Meier" not in out


def test_com_segments_are_replaced():
    out, _, _ = run("COM+0221 123456:TE'\nCOM+praxis@meier.de:EM'\n")
    assert "0221 123456" not in out
    assert "praxis@meier.de" not in out


def test_free_text_is_anonymized_and_flagged():
    out, _, suspicions = run(
        "NAD+VP+A111111111+++Meier+Anna'\n"
        "FTX+AAI+++Rueckfrage zu Patientin Anna Meier, Tel 0221 123456'\n"
    )
    assert "Anna Meier" not in out
    assert "0221 123456" not in out
    assert any("Freitext" in s.reason for s in suspicions)


def test_nam_address_is_replaced():
    out, _, _ = run("NAM+Praxis Nord+Nordstr 1+24103 Kiel+info@praxis-nord.de'\n")
    for leak in ("Praxis Nord", "Nordstr 1", "24103 Kiel", "praxis-nord"):
        assert leak not in out


def test_odd_length_lanr_and_bsnr_are_replaced_and_mirrored():
    out, mappings, _ = run("NAD+ARZ+1234567890+++Dr. Meier'\nBES+12345678+1234567890'\n")
    assert "1234567890" not in out
    assert "12345678" not in out
    lanr = next(m for m in mappings if m.original == "1234567890")
    bsnr = next(m for m in mappings if m.original == "12345678")
    assert len(lanr.pseudonym) == 10 and lanr.error_mirrored
    assert len(bsnr.pseudonym) == 8 and bsnr.error_mirrored


def test_distinct_lanrs_get_distinct_pseudonyms():
    out, mappings, _ = run("BES+111111111+222222222'\nBES+333333333+444444444'\n")
    pseudos = {m.pseudonym for m in mappings if m.original in ("222222222", "444444444")}
    assert len(pseudos) == 2


def test_second_payer_ik_in_fkt_layout_2_is_kept():
    out, _, _ = run("FKT+01++123456789+101575519+104080005+123456789'\n")
    assert "104080005" in out
    assert "101575519" in out
