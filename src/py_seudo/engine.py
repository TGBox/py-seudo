"""Unified PseudoEngine orchestrating cross-file ESOL and Email pseudonymization."""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Dict, List, Optional

from py_seudo.edifact.anonymizer import EsolAnonymizer
from py_seudo.email.anonymizer import EmailAnonymizer
from py_seudo.models import AnonymizationResult, MappingEntry, Suspicion
from py_seudo.validators import RejectionInspector


class PseudoEngine:
    """Coordinates ESOL and Email anonymization ensuring bidirectional

    consistency and safe audit logging.
    """

    def __init__(self, specified_practice_ik: Optional[str] = None):
        self.specified_practice_ik = specified_practice_ik

    def process(self, esol_text: str = "", email_text: str = "") -> AnonymizationResult:
        """Run complete anonymization pipeline across ESOL file and Email."""
        result = AnonymizationResult(
            original_esol=esol_text,
            original_email=email_text,
        )

        shared_mappings: Dict[str, MappingEntry] = {}
        practice_iks: List[str] = []
        kassen_iks: List[str] = []

        # 0. Pre-inspect rejection email to discover reported errors (checksum, status, duplicates)
        known_defects: Dict[str, Dict[str, str]] = {}
        if email_text.strip():
            known_defects = RejectionInspector.inspect(email_text)

        # 1. Process ESOL file first if provided
        if esol_text.strip():
            esol_anon = EsolAnonymizer(
                esol_text,
                specified_practice_ik=self.specified_practice_ik,
                known_defects=known_defects,
            )
            anon_esol_text, esol_mappings = esol_anon.anonymize()
            result.anonymized_esol = anon_esol_text
            result.practice_iks = list(esol_anon.practice_iks)
            result.kassen_iks = list(esol_anon.kassen_iks)
            result.suspicions.extend(esol_anon.suspicions)

            practice_iks = result.practice_iks
            kassen_iks = result.kassen_iks

            for m in esol_mappings:
                shared_mappings[m.original] = m

        # 2. Process Email with shared mappings
        if email_text.strip():
            email_anon = EmailAnonymizer(
                raw_email=email_text,
                shared_mappings=shared_mappings,
                practice_iks=practice_iks,
                kassen_iks=kassen_iks,
            )
            anon_email_text, email_mappings = email_anon.anonymize()
            result.anonymized_email = anon_email_text
            result.suspicions.extend(email_anon.suspicions)

            for m in email_mappings:
                if m.original in shared_mappings:
                    shared_mappings[m.original].count += m.count
                    # Preserve error mirroring info if found in email
                    if m.error_mirrored and not shared_mappings[m.original].error_mirrored:
                        shared_mappings[m.original].error_mirrored = True
                        shared_mappings[m.original].diagnostic_note = m.diagnostic_note
                else:
                    shared_mappings[m.original] = m

        # Aggregate unique mappings
        result.mappings = list(shared_mappings.values())
        return result

    @staticmethod
    def export_audit_mapping_json(result: AnonymizationResult, target_path: Path) -> None:
        """Export mapping table to JSON file with security header."""
        target_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "GDPR_NOTICE": (
                "STRENG VERTRAULICH: Diese Zuordnungstabelle enthaelt Klardaten und darf "
                "NIEMALS veroeffentlicht oder in ein Versionskontrollsystem (Git) hochgeladen werden!"
            ),
            "practice_iks": result.practice_iks,
            "kassen_iks": result.kassen_iks,
            "total_replacements": result.total_replacements,
            "total_errors_mirrored": sum(1 for m in result.mappings if m.error_mirrored),
            "mappings": [m.to_dict() for m in result.mappings],
        }
        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    @staticmethod
    def export_audit_mapping_csv(result: AnonymizationResult, target_path: Path) -> None:
        """Export mapping table to CSV file.

        Kodierung ist utf-8-sig: Excel unter Windows erkennt UTF-8 nur an der BOM,
        sonst werden Umlaute in Namen und Kategorien falsch dargestellt.
        """
        target_path.parent.mkdir(parents=True, exist_ok=True)
        with open(target_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f, delimiter=";")
            writer.writerow([
                "Original",
                "Pseudonym",
                "Kategorie",
                "Anzahl",
                "FehlerGespiegelt",
                "DiagnoseHinweis",
                "Beschreibung",
            ])
            for m in result.mappings:
                writer.writerow([
                    m.original,
                    m.pseudonym,
                    m.category.value,
                    m.count,
                    "Ja" if m.error_mirrored else "Nein",
                    m.diagnostic_note,
                    m.description,
                ])
