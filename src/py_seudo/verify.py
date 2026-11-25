"""Abschlusspruefung: Hat die Anonymisierung etwas uebersehen?

Die Erkenner in ``edifact`` und ``email`` ersetzen, was sie kennen. Was sie
nicht kennen, laeuft unveraendert durch. Dieses Modul dreht die Fehlerrichtung
um: Es laeuft *nach* der Anonymisierung ueber alle Texte, die das Programm
verlassen koennen (ESOL, E-Mail, englischer Report), und meldet alles, was
nach Personenbezug aussieht und weder ein selbst erzeugtes Pseudonym noch ein
bekanntes Kassen-IK ist.

Die Funde landen als :class:`~py_seudo.models.Suspicion` in
``result.suspicions``. Solange dort etwas steht, sperrt die GUI den Export und
den Versand an externe KI-Anbieter. Der Anwender loest einen Fund auf, indem er
ihn ersetzt (neue Ersetzung im Mapping-Reiter) oder ausdruecklich als
unkritisch freigibt (``result.acknowledged``).
"""
from __future__ import annotations

import re
from datetime import date
from typing import Iterable, List, Set

from py_seudo.models import AnonymizationResult, MappingEntry, Suspicion

# Kuerzere Originale (z. B. "Max", "DE") wuerden ueberall Treffer erzeugen.
_MIN_ORIGINAL_LEN = 4

_KVNR_RE = re.compile(r"(?<![A-Za-z0-9])[A-Z]\d{9}(?![A-Za-z0-9])")
_LONG_NUMBER_RE = re.compile(r"(?<![A-Za-z0-9_.,])\d{8,10}(?![A-Za-z0-9_]|[.,]\d)")
_BIRTHDATE_RE = re.compile(
    r"(?:\bgeb\.?|\bgeboren(?:\s+am)?|\bGeburtsdatum|\bGeb\.-?Dat(?:um|\.)?|\bDOB|\bdate of birth)"
    r"\s*:?\s*(\d{1,2}\.\s?\d{1,2}\.\s?\d{2,4}|\d{8})",
    re.IGNORECASE,
)
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(
    r"\b(?:Tel(?:efon)?|Fax|Mobil|Handy|Phone)\.?\s*(?:Nr\.?)?\s*:?\s*"
    r"((?:\+|00)?\d[\d\s/()-]{5,}\d)",
    re.IGNORECASE,
)
_PLZ_ORT_RE = re.compile(r"(?<!\d)(\d{5})\s+([A-ZÄÖÜ][a-zäöüß]+(?:[\s-][A-ZÄÖÜ][a-zäöüß]+)?)")

_PLACEHOLDER_TLDS = (".invalid", ".example", ".test", ".localhost")
_PLACEHOLDER_DOMAINS = {"example.com", "example.org", "example.net"}


def _is_yyyymmdd(digits: str) -> bool:
    """8-stellige Ziffernfolge, die ein plausibles Datum CCYYMMDD ist.

    EDIFACT-Datumsfelder (DTM, REC, INV, UNB) sind keine Kennnummern und
    wuerden sonst in jeder Datei Fehlalarme ausloesen.
    """
    if len(digits) != 8:
        return False
    try:
        date(int(digits[:4]), int(digits[4:6]), int(digits[6:]))
    except ValueError:
        return False
    return 1900 <= int(digits[:4]) <= 2100


def _line_of(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def _allowed_tokens(result: AnonymizationResult) -> Set[str]:
    """Alles, was im Output stehen darf: Pseudonyme, Kassen-IKs, Freigaben."""
    allowed: Set[str] = set(result.kassen_iks) | set(result.acknowledged)
    for m in result.mappings:
        if not m.pseudonym:
            continue
        allowed.add(m.pseudonym)
        allowed.update(re.findall(r"[A-Za-z0-9._%+@-]+", m.pseudonym))
    return allowed


def _surviving_originals(
    text: str, mappings: Iterable[MappingEntry], section: str
) -> List[Suspicion]:
    found: List[Suspicion] = []
    pseudonyms = {m.pseudonym for m in mappings}
    for m in mappings:
        original = (m.original or "").strip()
        if len(original) < _MIN_ORIGINAL_LEN or original == m.pseudonym:
            continue
        # Ist das Original zugleich Pseudonym einer anderen Entitaet, laesst
        # sich im Output nicht unterscheiden, was gemeint ist. Das ist ein
        # Konflikt, aber kein Beleg fuer ein Leck -- er wird gesondert gemeldet.
        rx = re.compile(r"(?<![A-Za-z0-9_])" + re.escape(original) + r"(?![A-Za-z0-9_])")
        hit = rx.search(text)
        if not hit:
            continue
        if original in pseudonyms:
            reason = "Original ist zugleich Pseudonym einer anderen Angabe – nicht eindeutig"
        else:
            reason = "Original wurde nicht vollständig ersetzt"
        found.append(Suspicion(original, _line_of(text, hit.start()), f"{reason} ({section})"))
    return found


def verify_text(
    text: str, result: AnonymizationResult, section: str, allowed: Set[str] | None = None
) -> List[Suspicion]:
    """Alle Verdachtsstellen in *text*."""
    if not text or not text.strip():
        return []
    if allowed is None:
        allowed = _allowed_tokens(result)

    found = _surviving_originals(text, result.mappings, section)

    def add(value: str, pos: int, label: str) -> None:
        value = value.strip()
        if value and value not in allowed:
            found.append(Suspicion(value, _line_of(text, pos), f"{label} ({section})"))

    for hit in _KVNR_RE.finditer(text):
        add(hit.group(0), hit.start(), "Mögliche Versichertennummer")

    for hit in _LONG_NUMBER_RE.finditer(text):
        digits = hit.group(0)
        if not _is_yyyymmdd(digits):
            add(digits, hit.start(), "Mögliche IK/LANR/BSNR oder Belegnummer")

    for hit in _BIRTHDATE_RE.finditer(text):
        add(hit.group(1), hit.start(1), "Mögliches Geburtsdatum")

    for hit in _EMAIL_RE.finditer(text):
        address = hit.group(0)
        if section == "ESOL":
            address = address.rsplit("+", 1)[-1].rsplit(":", 1)[-1]
        domain = address.rsplit("@", 1)[-1].lower()
        if domain.endswith(_PLACEHOLDER_TLDS) or domain in _PLACEHOLDER_DOMAINS:
            continue
        add(address, hit.start() + hit.group(0).find(address), "E-Mail-Adresse")

    for hit in _PHONE_RE.finditer(text):
        number = hit.group(1)
        if set(re.sub(r"\D", "", number)[2:]) <= {"0"}:
            continue  # selbst erzeugter Platzhalter wie +49 000 0000000
        add(number, hit.start(1), "Telefonnummer")

    for hit in _PLZ_ORT_RE.finditer(text):
        plz = hit.group(1)
        if plz in allowed:
            continue
        add(hit.group(0), hit.start(), "Postleitzahl mit Ort")

    return found


def _dedupe(items: Iterable[Suspicion]) -> List[Suspicion]:
    seen: Set[str] = set()
    out: List[Suspicion] = []
    for s in items:
        if s.text in seen:
            continue
        seen.add(s.text)
        out.append(s)
    return out


def verify_result(result: AnonymizationResult) -> List[Suspicion]:
    """Prueft alles, was exportiert oder versendet werden kann."""
    allowed = _allowed_tokens(result)
    found: List[Suspicion] = []
    found += verify_text(result.anonymized_esol, result, "ESOL", allowed)
    found += verify_text(result.anonymized_email, result, "E-Mail", allowed)
    found += verify_text(result.english_report, result, "Englischer Report", allowed)
    return _dedupe(found)


def _present_in_output(text: str, result: AnonymizationResult) -> bool:
    return any(
        text in part
        for part in (result.anonymized_esol, result.anonymized_email, result.english_report)
        if part
    )


def recheck(result: AnonymizationResult) -> List[Suspicion]:
    """Verdachtsliste neu aufbauen -- nach jeder Aenderung an den Texten aufrufen.

    * Funde der Erkenner bleiben, solange ihr Text noch im Output steht.
    * Die Abschlusspruefung laeuft komplett neu.
    * Ausdruecklich freigegebene Stellen fallen heraus.
    """
    detector = [s for s in result.detector_suspicions if _present_in_output(s.text, result)]
    merged = _dedupe(detector + verify_result(result))
    result.suspicions = [s for s in merged if s.text not in result.acknowledged]
    return result.suspicions


class UnresolvedSuspicions(RuntimeError):
    """Versand oder Export abgelehnt, weil noch Verdachtsfaelle offen sind."""

    def __init__(self, findings: List[Suspicion]):
        self.findings = findings
        preview = ", ".join(s.text for s in findings[:5])
        more = f" (+{len(findings) - 5} weitere)" if len(findings) > 5 else ""
        super().__init__(
            f"{len(findings)} ungeklärte Stelle(n) mit möglichem Personenbezug: {preview}{more}"
        )


def prompt_findings(prompt: str, result: AnonymizationResult) -> List[Suspicion]:
    """Pruefung eines Textes, der an einen externen Dienst gehen soll."""
    findings = verify_text(prompt, result, "KI-Anfrage")
    return [s for s in _dedupe(findings) if s.text not in result.acknowledged]
