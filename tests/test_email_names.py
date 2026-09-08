"""Tests fuer die kontextbasierte Namenserkennung in E-Mails."""
import pytest

from py_seudo.email.anonymizer import EmailAnonymizer
from py_seudo.email.names import NameDetector, NameRole
from py_seudo.engine import PseudoEngine
from py_seudo.models import MappingEntry, ReplacementCategory


def anonymize(text: str, shared=None):
    anon = EmailAnonymizer(text, shared_mappings=shared)
    out, mappings = anon.anonymize()
    return out, mappings, anon.suspicions


# ---------------------------------------------------------------------------
# Der Kernfall: Namen, die nur in der E-Mail stehen
# ---------------------------------------------------------------------------


def test_namen_ohne_esol_datei_werden_ersetzt():
    """Ohne ESOL-Datei blieb frueher jeder Name im Klartext stehen."""
    text = (
        "From: kasse@tk.de\n"
        "To: praxis@x.de\n"
        "Subject: Rueckweisung\n"
        "\n"
        "Sehr geehrte Frau Hoffmann,\n"
        "\n"
        "der Vorgang zu Patient Anna Meier wurde abgewiesen.\n"
        "Verordnender Arzt: Dr. med. Johannes Schmidt\n"
        "Bei Rueckfragen wenden Sie sich an Herrn Wagner.\n"
        "\n"
        "Mit freundlichen Gruessen\n"
        "Andrea Becker\n"
    )
    out, _mappings, _susp = anonymize(text)

    for name in ("Hoffmann", "Anna Meier", "Johannes Schmidt", "Wagner", "Andrea Becker"):
        assert name not in out, f"{name!r} steht noch im Klartext"


@pytest.mark.parametrize(
    "text, name",
    [
        ("Sehr geehrte Frau Hoffmann,\n", "Hoffmann"),
        ("Sehr geehrter Herr Hoffmann,\n", "Hoffmann"),
        ("Guten Tag Frau Hoffmann\n", "Hoffmann"),
        ("Patient: Anna Meier\n", "Anna Meier"),
        ("Patientin Anna Meier wurde abgewiesen\n", "Anna Meier"),
        ("Versicherter: Hans Peter Meier\n", "Hans Peter Meier"),
        ("Verordnender Arzt: Dr. med. Johannes Schmidt\n", "Johannes Schmidt"),
        ("Zweitmeinung durch Dr. med. K. Lehmann\n", "K. Lehmann"),
        ("Ansprechpartnerin: Petra Klein\n", "Petra Klein"),
        ("i. A. Andrea Becker\n", "Andrea Becker"),
        ("Rueckfragen an: Thomas Wagner\n", "Thomas Wagner"),
        ("Sehr geehrte Frau von Kettenburg,\n", "von Kettenburg"),
        ("Patient: Anna-Lena Meier-Schulz\n", "Anna-Lena Meier-Schulz"),
    ],
)
def test_kontextmuster(text, name):
    out, _m, _s = anonymize(text)
    assert name not in out, f"{name!r} wurde nicht erkannt in {text!r}"


def test_arzt_und_patient_bekommen_unterschiedliche_pseudonymarten():
    out, mappings, _s = anonymize(
        "Patient: Anna Meier\nVerordnender Arzt: Dr. med. Johannes Schmidt\n"
    )
    assert "Mustermann_" in out
    assert "Musterarzt_" in out

    kategorien = {m.category for m in mappings}
    assert ReplacementCategory.PATIENT_NAME in kategorien
    assert ReplacementCategory.DOCTOR_NAME in kategorien


def test_kontaktperson_bekommt_eigene_kategorie():
    _out, mappings, _s = anonymize("Sehr geehrte Frau Hoffmann,\n")
    assert any(m.category is ReplacementCategory.CONTACT_PERSON for m in mappings)


def test_anrede_bestimmt_die_form_des_pseudonyms():
    out_f, _m, _s = anonymize("Sehr geehrte Frau Hoffmann,\n")
    out_m, _m2, _s2 = anonymize("Sehr geehrter Herr Hoffmann,\n")
    assert "Sachbearbeiterin_" in out_f
    assert "Sachbearbeiter_" in out_m and "Sachbearbeiterin_" not in out_m


# ---------------------------------------------------------------------------
# Konsistenz
# ---------------------------------------------------------------------------


def test_nachname_allein_teilt_das_pseudonym_mit_dem_vollnamen():
    """"Frau Becker" und die Signatur "Andrea Becker" sind dieselbe Person."""
    out, _m, _s = anonymize(
        "Sehr geehrte Frau Becker,\n"
        "wie mit Frau Becker besprochen.\n"
        "\n"
        "Mit freundlichen Gruessen\n"
        "Andrea Becker\n"
    )
    pseudonyme = {w.strip(".,;:") for w in out.split() if w.startswith("Sachbearbeiter")}
    assert len(pseudonyme) == 1, f"erwartet ein Pseudonym, gefunden: {pseudonyme}"


def test_nummern_kollidieren_nicht_mit_denen_aus_der_esol_datei():
    """Die E-Mail-Seite zaehlt ueber die hoechste ESOL-Nummer hinaus weiter."""
    shared = {
        "Schmidt": MappingEntry("Schmidt", "Mustermann_7", ReplacementCategory.PATIENT_NAME),
    }
    out, _m, _s = anonymize("Sehr geehrte Frau Hoffmann,\n", shared=shared)
    assert "Sachbearbeiterin_8" in out


def test_bekannter_name_behaelt_die_nummer_aus_der_esol_datei():
    shared = {
        "Anna Meier": MappingEntry(
            "Anna Meier", "Max_3 Mustermann_3", ReplacementCategory.PATIENT_NAME
        ),
    }
    out, _m, _s = anonymize("Patient: Anna Meier, siehe auch Frau Meier.\n", shared=shared)
    assert "Max_3 Mustermann_3" in out
    assert "Meier" not in out


def test_zweiter_lauf_aendert_nichts_mehr():
    """Pseudonyme duerfen nicht selbst wieder als Namen erkannt werden."""
    text = (
        "Sehr geehrte Frau Hoffmann,\n"
        "Patient: Anna Meier\n"
        "Arzt: Dr. med. Johannes Schmidt\n"
        "\nMit freundlichen Gruessen\nAndrea Becker\n"
    )
    once, _m, _s = anonymize(text)
    twice, _m2, _s2 = anonymize(once)
    assert once == twice


def test_esol_und_email_widersprechen_sich_nicht():
    """Regression: eingesetzte Pseudonyme wurden frueher erneut ersetzt."""
    esol = (
        "UNH+1+SLLA:15:0:0'\n"
        "NAD+VP+A111111111+++Meier+Anna+Ringweg 3+Koeln++10115+DE'\n"
        "NAD+FPR+123456789+++Praxis Nord+Nordstr 1+Kiel++12345+DE'\n"
    )
    mail = "Patient wohnt in 10115, Praxis in 12345.\n"
    result = PseudoEngine().process(esol, mail)

    patient_plz = result.anonymized_esol.split("Musterort++")[1][:5]
    assert f"Patient wohnt in {patient_plz}" in result.anonymized_email


# ---------------------------------------------------------------------------
# Was NICHT ersetzt werden darf
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text, bleibt",
    [
        ("Kostentraeger: Techniker Krankenkasse\n", "Techniker Krankenkasse"),
        ("Abrechnungsteam TK\n", "Abrechnungsteam TK"),
        ("Sehr geehrte Damen und Herren,\n", "Damen und Herren"),
        ("Diagnose: M54.5 nicht abrechnungsfaehig\n", "M54.5"),
        ("Die Positionsnummer 21201 (Krankengymnastik)\n", "Krankengymnastik"),
        ("gemaess Heilmittelkatalog\n", "Heilmittelkatalog"),
    ],
)
def test_keine_fehltreffer(text, bleibt):
    out, _m, _s = anonymize(text)
    assert bleibt in out


def test_kassenname_in_der_signatur_bleibt_stehen():
    out, _m, _s = anonymize(
        "Mit freundlichen Gruessen\nAbrechnungsteam TK\nTechniker Krankenkasse\n"
    )
    assert "Abrechnungsteam TK" in out
    assert "Techniker Krankenkasse" in out


def test_rollenbezeichner_wird_nicht_mitersetzt():
    out, _m, _s = anonymize("Rueckfragen an: Sachbearbeiter Thomas Wagner\n")
    assert "Thomas Wagner" not in out
    assert "Sachbearbeiter" in out  # das Label selbst bleibt


# ---------------------------------------------------------------------------
# Verdachtsfaelle statt stillem Durchlauf
# ---------------------------------------------------------------------------


def test_unklare_anrede_wird_gemeldet():
    # Versalien-Nachnamen kommen in echter Korrespondenz vor und passen auf kein
    # Namensmuster -- sie muessen gemeldet statt still uebergangen werden.
    _out, _m, suspicions = anonymize("Sehr geehrte Frau MUELLER-LUEDENSCHEIDT,\n")
    assert suspicions, "unklare Anrede haette gemeldet werden muessen"
    assert any("Anrede" in s.reason or "Titel" in s.reason for s in suspicions)


def test_saubere_email_meldet_keinen_verdacht():
    _out, _m, suspicions = anonymize(
        "Sehr geehrte Frau Hoffmann,\n\nDie Datei wurde abgewiesen.\n"
        "\nMit freundlichen Gruessen\nAndrea Becker\n"
    )
    assert suspicions == []


def test_verdacht_landet_im_ergebnis():
    result = PseudoEngine().process("", "Sehr geehrte Frau Xyz123abc,\n")
    assert result.suspicions
    assert result.is_clean is False


def test_is_clean_bei_sauberem_ergebnis():
    result = PseudoEngine().process("", "Die Datei wurde abgewiesen.\n")
    assert result.is_clean is True


# ---------------------------------------------------------------------------
# Detektor direkt
# ---------------------------------------------------------------------------


def test_detektor_liefert_rollen():
    hits = NameDetector().find(
        "Patient: Anna Meier\nArzt: Dr. med. Johannes Schmidt\nSehr geehrte Frau Hoffmann,\n"
    )
    rollen = {h.role for h in hits}
    assert rollen == {NameRole.PATIENT, NameRole.DOCTOR, NameRole.CONTACT}


def test_detektor_respektiert_geschuetzte_bereiche():
    text = "Patient: Anna Meier\n"
    ganz = (text.index("Anna Meier"), text.index("Anna Meier") + len("Anna Meier"))
    assert NameDetector([ganz]).find(text) == []


def test_name_laeuft_nicht_ueber_das_zeilenende():
    """Regression: '\\s+' im Muster verband Name und naechstes Wort ueber die Zeile."""
    hits = NameDetector().find("Zweitmeinung durch Dr. med. K. Lehmann\n\nBitte pruefen Sie.\n")
    assert len(hits) == 1
    assert hits[0].text == "K. Lehmann"
