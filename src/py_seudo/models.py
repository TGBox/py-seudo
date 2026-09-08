"""Data models for py-seudo anonymization."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List


class ReplacementCategory(str, Enum):
    PATIENT_NAME = "Patientenname"
    KVNR = "Krankenversichertennummer (KVNR)"
    BIRTHDATE = "Geburtsdatum"
    ADDRESS = "Adresse / Wohnort"
    PRACTICE_IK = "Praxis-IK (Institutionskennzeichen)"
    DOCTOR_NAME = "Arztname"
    DOCTOR_LANR = "Arztnummer (LANR)"
    DOCTOR_BSNR = "Betriebsstättennummer (BSNR)"
    INVOICE_NUMBER = "Rechnungs-/Belegnummer"
    CONTACT_INFO = "Kontaktdaten / Signatur"
    CONTACT_PERSON = "Kontaktperson (Anrede / Signatur)"
    OTHER = "Sonstiges"


@dataclass
class MappingEntry:
    original: str
    pseudonym: str
    category: ReplacementCategory
    count: int = 1
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "original": self.original,
            "pseudonym": self.pseudonym,
            "category": self.category.value,
            "count": self.count,
            "description": self.description,
        }


@dataclass
class Suspicion:
    """Eine Stelle, die nach Personenbezug aussieht, aber nicht ersetzt wurde.

    Verdachtsfaelle werden gemeldet statt still uebergangen: der Anwender soll
    sehen, was das Programm nicht sicher zuordnen konnte, bevor er die Datei
    aus der Hand gibt.
    """

    text: str
    line: int
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return {"text": self.text, "line": self.line, "reason": self.reason}


@dataclass
class AnonymizationResult:
    original_esol: str = ""
    anonymized_esol: str = ""
    original_email: str = ""
    anonymized_email: str = ""
    mappings: List[MappingEntry] = field(default_factory=list)
    practice_iks: List[str] = field(default_factory=list)
    kassen_iks: List[str] = field(default_factory=list)
    suspicions: List[Suspicion] = field(default_factory=list)

    @property
    def total_replacements(self) -> int:
        return sum(m.count for m in self.mappings)

    @property
    def is_clean(self) -> bool:
        """True, wenn kein Verdachtsfall offen ist."""
        return not self.suspicions

    def get_mappings_by_category(self) -> Dict[str, List[MappingEntry]]:
        result: Dict[str, List[MappingEntry]] = {}
        for m in self.mappings:
            cat = m.category.value
            if cat not in result:
                result[cat] = []
            result[cat].append(m)
        return result
