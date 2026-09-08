"""Kontextbasierte Erkennung von Personennamen in Kassen-Rueckmeldungen.

Der Detektor rankt nicht, wie ein Wort aussieht, sondern **wo** es steht: hinter
einer Anrede, hinter einem Arzttitel, hinter einer Feldbeschriftung, in einem
Signaturblock. Das vermeidet die Fehltreffer, die eine reine Namensliste
produziert (Weiss, Reich, Sommer, Ortsnamen) und kommt ohne Modell und ohne
zusaetzliche Abhaengigkeit aus.

Der Preis dafuer: Namen ohne verwertbaren Kontext werden nicht erkannt. Damit
das nicht still passiert, meldet der Detektor solche Stellen als Verdachtsfall
(:class:`py_seudo.models.Suspicion`), statt sie zu ignorieren.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Sequence, Tuple

from py_seudo.models import Suspicion


class NameRole(str, Enum):
    """Rolle, in der ein Name im Text auftaucht -- bestimmt das Pseudonym."""

    PATIENT = "patient"
    DOCTOR = "doctor"
    CONTACT = "contact"


@dataclass(frozen=True)
class NameHit:
    start: int
    end: int
    text: str
    role: NameRole
    trigger: str
    #: "f" = weibliche Anrede, "m" = maennliche Anrede, "" = unbekannt
    salutation: str = ""


# --------------------------------------------------------------------------
# Bausteine fuer Namensmuster
# --------------------------------------------------------------------------

# Namenspartikel ("von", "van der", ...) -- klein geschrieben mitten im Namen
_PARTICLE = r"(?:von|vom|van|zu|zur|zum|de|del|della|di|da|den|der|ten|ter|le|la|dos|el|al)"
# Ein Namenswort: Grossbuchstabe am Anfang, Bindestrich- und Apostrophnamen erlaubt
_WORD = r"[A-ZÄÖÜ][a-zäöüß]+(?:[-'’][A-ZÄÖÜ]?[a-zäöüß]+)*"
# Initiale, z. B. das "J." in "Dr. med. J. Schmidt"
_INITIAL = r"[A-ZÄÖÜ]\."
_TOKEN = rf"(?:{_WORD}|{_INITIAL})"
# Ein bis drei Token, optional durch ein Partikel verbunden.
# Der Lookahead verhindert, dass mitten in einem bereits gesetzten Pseudonym
# gematcht wird: "Mustermann_1" -> nach "Mustermann" folgt "_", also \w -> kein Treffer.
# Trennung nur mit horizontalem Whitespace: ein Name laeuft nie ueber das Zeilenende.
# Ein fuehrendes Partikel gehoert zum Namen: "Frau von Kettenburg".
_NAME = rf"(?:{_PARTICLE}[ \t]+)?{_TOKEN}(?:[ \t]+(?:{_PARTICLE}[ \t]+)?{_TOKEN}){{0,2}}(?!\w)"

_FRAU = r"(?:Frau|Fr\.)"
_HERR = r"(?:Herrn|Herr|Hr\.)"


def _c(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern, re.UNICODE)


# --------------------------------------------------------------------------
# Muster je Rolle. Gruppe "name" ist immer der zu ersetzende Teil.
# --------------------------------------------------------------------------

_PATIENT_PATTERNS: Sequence[Tuple[re.Pattern[str], str]] = [
    (_c(rf"(?:Name\s+de[sr]\s+Versicherten|Versichertenname|Patientenname|Name\s+des\s+Patienten)"
        rf"[ \t]*:[ \t]*(?P<name>{_NAME})"), "Feldbeschriftung Versichertenname"),
    (_c(rf"\b(?:Patient(?:in)?|Versicherte(?:r|n)?|Pat\.|Mitglied)[ \t]*:[ \t]*(?P<name>{_NAME})"),
     "Feldbeschriftung Patient"),
    (_c(rf"\b(?:Patient(?:in)?|Versicherte(?:r|n)?)[ \t]+(?P<name>{_NAME})"),
     "Fliesstext 'Patient <Name>'"),
]

_DOCTOR_PATTERNS: Sequence[Tuple[re.Pattern[str], str]] = [
    (_c(rf"\b(?:Verordnende[rn]?\s+Arzt|Verordner(?:in)?|Arzt|Ärztin|Aerztin|"
        rf"Therapeut(?:in)?|Behandler(?:in)?|Leistungserbringer)\s*:\s*"
        rf"(?:Dr\.\s*)?(?:med\.\s*)?(?:dent\.\s*)?(?P<name>{_NAME})"),
     "Feldbeschriftung Arzt"),
    (_c(rf"\b(?:Dr|Dres|Prof)\.[ \t]*(?:med\.[ \t]*)?(?:dent\.[ \t]*)?(?:vet\.[ \t]*)?(?P<name>{_NAME})"),
     "Arzttitel"),
]

_CONTACT_PATTERNS: Sequence[Tuple[re.Pattern[str], str]] = [
    (_c(rf"\bSehr\s+geehrte[rs]?\s+(?:{_FRAU}|{_HERR})[ \t]+(?P<name>{_NAME})"), "Anrede"),
    (_c(rf"\b(?:Guten\s+Tag|Hallo|Liebe[rs]?)\s+(?:{_FRAU}|{_HERR})[ \t]+(?P<name>{_NAME})"), "Anrede"),
    (_c(rf"\b(?:Ansprechpartner(?:in)?|Sachbearbeiter(?:in)?|Bearbeiter(?:in)?|"
        rf"Ihr\s+Kontakt|Rückfragen\s+an|Rueckfragen\s+an)[ \t]*:?[ \t]*(?P<name>{_NAME})"),
     "Feldbeschriftung Ansprechpartner"),
    (_c(rf"\bi\.[ \t]*[AVav]\.[ \t]*(?P<name>{_NAME})"), "Unterschriftszusatz i. A. / i. V."),
    # Muss zuletzt stehen: allgemeinstes Muster, greift nur, wenn kein spezielleres passte
    (_c(rf"\b(?:{_FRAU}|{_HERR})[ \t]+(?P<name>{_NAME})"), "Anrede Frau/Herr"),
]

_SALUTATION_F = _c(rf"(?:{_FRAU})\s*$")
_SALUTATION_M = _c(rf"(?:{_HERR})\s*$")

# Grussformel -- leitet den Signaturblock ein
_GREETING = re.compile(
    r"^\s*(?:mit\s+freundlichen\s+gr(?:ü|ue)(?:ß|ss)en"
    r"|(?:freundliche|viele|beste|herzliche|liebe)\s+gr(?:ü|ue)(?:ß|ss)e"
    r"|mfg|vg|lg)\s*[,.]?\s*$",
    re.IGNORECASE,
)


# --------------------------------------------------------------------------
# Begriffe, die nie als Personenname gelten
# --------------------------------------------------------------------------

# Enthaelt ein Kandidat eines dieser Woerter, ist er kein Personenname.
_STOPWORDS = frozenset(
    w.lower()
    for w in (
        # Kostentraeger und Rechtsformen -- bleiben laut Vorgabe im Klartext
        "Krankenkasse", "Krankenversicherung", "Ersatzkasse", "Betriebskrankenkasse",
        "Pflegekasse", "Kasse", "Kostenträger", "Kostentraeger",
        "TK", "AOK", "DAK", "IKK", "BKK", "KKH", "HEK", "HKK", "Barmer",
        "Knappschaft", "SVLFG", "Debeka", "Techniker",
        # Organisationen und Rechtsformen
        "Team", "Abrechnungsteam", "Serviceteam", "Abteilung", "Fachbereich",
        "Sachgebiet", "Referat", "Service", "Servicecenter", "Kundenservice",
        "Zentrum", "Abrechnungszentrum", "Rechenzentrum", "Praxis", "Klinik",
        "GmbH", "AG", "KG", "OHG", "mbH", "eG", "Syntela", "DMRZ",
        # Fachbegriffe aus Fehlerprotokollen
        "Abrechnung", "Abrechnungsdatei", "Fehlermeldung", "Fehlerprotokoll",
        "Positionsnummer", "Heilmittelkatalog", "Krankengymnastik", "Diagnose",
        "Verordnung", "Rechnung", "Belegnummer", "Segment", "Zeile", "Datei",
        "Neulieferung", "Praxissoftware", "Anschrift", "Datum", "Geburtsdatum",
        "Betreff", "Anlage", "Anhang", "Seite", "Hinweis", "Fehler",
        # Rollenbezeichner -- stehen oft direkt vor dem Namen und gehoeren nicht dazu
        "Patient", "Patientin", "Versicherter", "Versicherte", "Versicherten",
        "Arzt", "Ärztin", "Aerztin", "Therapeut", "Therapeutin",
        "Sachbearbeiter", "Sachbearbeiterin", "Ansprechpartner", "Ansprechpartnerin",
        "Bearbeiter", "Bearbeiterin", "Leistungserbringer", "Verordner",
        # Sonstiges, das in Anreden/Signaturen auftaucht
        "Damen", "Herren", "Doktor", "Sehr", "Mit", "Bitte", "Ihre", "Ihr",
        "Postfach", "Telefon", "Telefax", "Mobil", "Internet",
    )
)

# Zeilen im Signaturblock, die offensichtlich kein Name sind
_NON_NAME_LINE = _c(r"[0-9@/]|^\s*(?:tel|fax|mobil|e-?mail|www|http)", )

_TOKEN_SPLIT = _c(r"[^\s]+")


def trim_candidate(candidate: str) -> Tuple[int, int]:
    """Stoppwoerter am Rand abschneiden und den verbleibenden Bereich zurueckgeben.

    Liefert ``(offset, laenge)`` relativ zu ``candidate``; ``(0, 0)``, wenn nichts
    Verwertbares uebrig bleibt. Abschneiden statt Verwerfen ist wichtig: aus
    "Sachbearbeiter Thomas Wagner" soll "Thomas Wagner" werden, nicht gar nichts --
    und ein angrenzendes Wort wie "Bitte" am Satzanfang darf nicht dazu fuehren,
    dass der ganze Name unersetzt stehen bleibt.
    """
    tokens = [(m.start(), m.end(), m.group(0)) for m in _TOKEN_SPLIT.finditer(candidate)]
    if not tokens:
        return (0, 0)

    def is_stop(tok: str) -> bool:
        return tok.strip(".,;:").lower() in _STOPWORDS

    first, last = 0, len(tokens) - 1
    while first <= last and is_stop(tokens[first][2]):
        first += 1
    while last >= first and is_stop(tokens[last][2]):
        last -= 1
    if first > last:
        return (0, 0)

    kept = tokens[first : last + 1]
    # Reine Initialen ("J. S.") sind zu unspezifisch, um sie blind zu ersetzen
    if not any(len(tok.strip(".")) > 2 for _s, _e, tok in kept):
        return (0, 0)
    # Ein Stoppwort mitten im Kandidaten heisst: hier stossen zwei Dinge aneinander
    if any(is_stop(tok) for _s, _e, tok in kept):
        return (0, 0)

    return (kept[0][0], kept[-1][1] - kept[0][0])


class NameDetector:
    """Findet Personennamen ueber ihren Kontext und meldet unklare Stellen."""

    def __init__(self, protected_spans: Sequence[Tuple[int, int]] = ()):
        #: Bereiche, die bereits durch ein anderes Verfahren ersetzt werden
        #: (ESOL-Mappings, E-Mail-Adressen) -- dort wird nicht nochmal gesucht.
        self.protected_spans = list(protected_spans)

    # -- oeffentliche API ---------------------------------------------------

    def find(self, text: str) -> List[NameHit]:
        """Alle Namenstreffer, ueberschneidungsfrei, in Textreihenfolge."""
        hits: List[NameHit] = []
        for role, patterns in (
            (NameRole.PATIENT, _PATIENT_PATTERNS),
            (NameRole.DOCTOR, _DOCTOR_PATTERNS),
            (NameRole.CONTACT, _CONTACT_PATTERNS),
        ):
            for pattern, trigger in patterns:
                for m in pattern.finditer(text):
                    hits.append(self._make_hit(text, m, role, trigger))
        hits.extend(self._find_in_signature(text))

        hits = [h for h in hits if h is not None]
        hits = [h for h in hits if not self._overlaps_protected(h)]
        return self._drop_overlaps(hits)

    def suspicions(self, text: str, resolved: Sequence[Tuple[int, int]]) -> List[Suspicion]:
        """Stellen, die nach Personenname aussehen, aber nicht ersetzt wurden."""
        found: List[Suspicion] = []
        taken = list(resolved)

        def is_free(start: int, end: int) -> bool:
            return not any(start < e and end > s for s, e in taken)

        # 1. Anrede ohne verwertbaren Namen dahinter
        for m in _c(rf"\b(?:{_FRAU}|{_HERR}|Dr\.|Prof\.)\s+(?P<rest>\S+)").finditer(text):
            start, end = m.span("rest")
            if is_free(start, end) and m.group("rest")[:1].isupper():
                found.append(
                    Suspicion(
                        text=m.group(0).strip(),
                        line=text.count("\n", 0, start) + 1,
                        reason="Anrede oder Titel, aber der Name dahinter wurde nicht erkannt",
                    )
                )

        # 2. Zeilen im Signaturblock, die nicht ersetzt wurden
        for start, end, line in self._signature_lines(text):
            stripped = line.strip()
            if not stripped or not is_free(start, end):
                continue
            if _NON_NAME_LINE.search(stripped):
                continue
            if len(stripped.split()) > 4 or not stripped[:1].isupper():
                continue
            # Firmen- und Abteilungszeilen ("Abrechnungsteam TK") sind kein Verdachtsfall
            if trim_candidate(stripped)[1] == 0:
                continue
            found.append(
                Suspicion(
                    text=stripped,
                    line=text.count("\n", 0, start) + 1,
                    reason="Zeile im Signaturblock -- moeglicherweise ein Name",
                )
            )

        # Duplikate zusammenfassen, Reihenfolge erhalten
        seen: Dict[Tuple[str, int], None] = {}
        unique = []
        for s in found:
            key = (s.text, s.line)
            if key not in seen:
                seen[key] = None
                unique.append(s)
        return unique

    # -- intern -------------------------------------------------------------

    def _make_hit(self, text: str, m: re.Match[str], role: NameRole, trigger: str):
        start, end = m.span("name")
        offset, length = trim_candidate(m.group("name"))
        if length == 0:
            return None
        start, end = start + offset, start + offset + length

        before = text[max(0, start - 12) : start]
        if _SALUTATION_F.search(before):
            salutation = "f"
        elif _SALUTATION_M.search(before):
            salutation = "m"
        else:
            salutation = ""
        return NameHit(start, end, text[start:end], role, trigger, salutation)

    def _signature_lines(self, text: str):
        """Bis zu vier nicht-leere Zeilen nach einer Grussformel."""
        offset = 0
        after_greeting = 0
        for raw_line in text.splitlines(keepends=True):
            line = raw_line.rstrip("\r\n")
            if _GREETING.match(line):
                after_greeting = 4
            elif after_greeting and line.strip():
                yield offset, offset + len(line), line
                after_greeting -= 1
            offset += len(raw_line)

    def _find_in_signature(self, text: str) -> List[NameHit]:
        hits = []
        whole_line = _c(rf"^\s*(?P<name>{_NAME})\s*$")
        for start, _end, line in self._signature_lines(text):
            m = whole_line.match(line)
            if not m:
                continue
            s, _e = m.span("name")
            offset, length = trim_candidate(m.group("name"))
            if length == 0:
                continue
            abs_start = start + s + offset
            hits.append(
                NameHit(abs_start, abs_start + length, text[abs_start : abs_start + length],
                        NameRole.CONTACT, "Signaturblock")
            )
        return hits

    def _overlaps_protected(self, hit: NameHit) -> bool:
        return any(hit.start < e and hit.end > s for s, e in self.protected_spans)

    @staticmethod
    def _drop_overlaps(hits: List[NameHit]) -> List[NameHit]:
        """Bei Ueberschneidung gewinnt der laengere, bei Gleichstand der spezifischere."""
        role_rank = {NameRole.PATIENT: 0, NameRole.DOCTOR: 1, NameRole.CONTACT: 2}
        ordered = sorted(hits, key=lambda h: (-(h.end - h.start), role_rank[h.role], h.start))
        kept: List[NameHit] = []
        for hit in ordered:
            if any(hit.start < k.end and hit.end > k.start for k in kept):
                continue
            kept.append(hit)
        return sorted(kept, key=lambda h: h.start)
