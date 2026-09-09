"""Local, 100% offline generator for English issue summaries, EDIFACT analysis,

and email translations. Fully GDPR-compliant with zero external network requests.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from py_seudo.models import AnonymizationResult, MappingEntry
from py_seudo.validators import validate_ik, validate_kvnr


class LocalReportGenerator:
    """Generates a comprehensive 3-part English developer handover document."""

    # Common phrase mappings for German healthcare rejection emails
    GERMAN_TO_ENGLISH_PATTERNS: List[Tuple[re.Pattern, str]] = [
        # Salutations & Greetings
        (re.compile(r"^Sehr geehrte Damen und Herren,?", re.IGNORECASE), "Dear Sir or Madam,"),
        (re.compile(r"^Sehr geehrte Frau\s+([A-Za-z\-]+),?", re.IGNORECASE), r"Dear Ms. \1,"),
        (re.compile(r"^Sehr geehrter Herr\s+([A-Za-z\-]+),?", re.IGNORECASE), r"Dear Mr. \1,"),
        (re.compile(r"^Hallo Frau\s+([A-Za-z\-]+),?", re.IGNORECASE), r"Hello Ms. \1,"),
        (re.compile(r"^Hallo Herr\s+([A-Za-z\-]+),?", re.IGNORECASE), r"Hello Mr. \1,"),
        (re.compile(r"^Guten Tag Frau\s+([A-Za-z\-]+),?", re.IGNORECASE), r"Good day Ms. \1,"),
        (re.compile(r"^Guten Tag Herr\s+([A-Za-z\-]+),?", re.IGNORECASE), r"Good day Mr. \1,"),
        (re.compile(r"^Mit freundlichen Gr[uü][sß]en,?", re.IGNORECASE), "Sincerely / Kind regards,"),
        (re.compile(r"^Liebe Gr[uü][sß]e,?", re.IGNORECASE), "Best regards,"),

        # Standard Intro & Outro sentences
        (
            re.compile(
                r"bei der maschinellen Pr[uü]fung Ihrer Abrechnungsdatei\s+([^\s]+)\s+zu IK\s+(\d+)\s+wurden formale und inhaltliche Abweisungs-Fehler festgestellt:?",
                re.IGNORECASE,
            ),
            r"During automated verification of your billing data file \1 for Practice IK \2, formal and content-related rejection errors were detected:",
        ),
        (
            re.compile(
                r"Ihre Datensendung\s+([^\s]+)\s+konnte nicht verarbeitet werden und wurde maschinell abgewiesen\.?",
                re.IGNORECASE,
            ),
            r"Your data transmission \1 could not be processed and was automatically rejected.",
        ),
        (
            re.compile(
                r"Folgende Abweisungsgr[uü]nde wurden festgestellt:?",
                re.IGNORECASE,
            ),
            "The following rejection reasons were identified:",
        ),
        (
            re.compile(
                r"ich habe wieder eine Ablehnung von der Kasse bekommen\.\s*K[oö]nnen Sie mir hier weiterhelfen\??",
                re.IGNORECASE,
            ),
            "I received another rejection from the health insurance fund. Could you please help me with this?",
        ),
        (
            re.compile(
                r"anbei sende ich Ihnen das Abweisungsprotokoll der\s+(.+?)\s+zur Abrechnungsdatei\s+([^\s]+)\.?",
                re.IGNORECASE,
            ),
            r"Attached please find the rejection protocol from \1 regarding billing file \2.",
        ),
        (
            re.compile(
                r"Die Kasse meldet formale Fehler in den Identifikatoren:?",
                re.IGNORECASE,
            ),
            "The health insurance fund reports formal errors in the identifiers:",
        ),
        (
            re.compile(
                r"Bitte korrigieren Sie den Datensatz in Ihrer Praxissoftware und [uü]bermitteln Sie eine Neulieferung\.?",
                re.IGNORECASE,
            ),
            "Please correct the data record in your practice management software and submit a re-delivery.",
        ),
        (
            re.compile(
                r"Bitte korrigieren Sie die Daten in Ihrem Praxisverwaltungssystem und reichen Sie eine korrigierte Neulieferung ein\.?",
                re.IGNORECASE,
            ),
            "Please correct the data in your practice management system and submit a corrected re-delivery.",
        ),

        # Detail Labels & Error lines
        (
            re.compile(
                r"Fehlerdetails zu Belegnummer\s+([^\s]+)\s+\(Rechnung\s+([^\s\)]+)\):?",
                re.IGNORECASE,
            ),
            r"Error details for Receipt No. \1 (Invoice \2):",
        ),
        (re.compile(r"^\s*-\s*Patient:\s*", re.IGNORECASE), "- Patient: "),
        (re.compile(r"^\s*-\s*Anschrift:\s*", re.IGNORECASE), "- Address: "),
        (re.compile(r"^\s*-\s*Verordnender Arzt:\s*", re.IGNORECASE), "- Referring Physician: "),
        (re.compile(r"^\s*-\s*Diagnose:\s*", re.IGNORECASE), "- Diagnosis: "),
        (re.compile(r"^\s*-\s*Fehlermeldung:\s*", re.IGNORECASE), "- Error Message: "),
        (re.compile(r"^\s*-\s*Segment:\s*", re.IGNORECASE), "- Segment: "),
        (re.compile(r"\bZeile\s+(\d+)\b", re.IGNORECASE), r"Line \1"),
        (re.compile(r"\bGeb\.\s*(\d{2}\.\d{2}\.\d{4})\b", re.IGNORECASE), r"DOB: \1"),
        (re.compile(r"\bKVNR:\s*([A-Z0-9]+)\b", re.IGNORECASE), r"KVNR (Insurance No.): \1"),
        (re.compile(r"\bLANR:\s*(\d+)\b", re.IGNORECASE), r"LANR (Physician ID): \1"),
        (re.compile(r"\bBSNR:\s*(\d+)\b", re.IGNORECASE), r"BSNR (Practice ID): \1"),

        # Specific Error Explanations
        (
            re.compile(
                r"Pr[uü]fziffer fehlerhaft\s*\(Pr[uü]fziffer stimmt nicht mit Modulo-10-Berechnung [uü]berein\)\.?",
                re.IGNORECASE,
            ),
            "Check digit invalid (check digit does not match Modulo-10 calculation).",
        ),
        (
            re.compile(
                r"Pr[uü]fziffer ung[uü]ltig gem[aä][sß]\s*§?\s*290\s*SGB\s*V\.?",
                re.IGNORECASE,
            ),
            "Check digit invalid according to § 290 SGB V (German Social Code).",
        ),
        (
            re.compile(
                r"Unzul[aä]ssige Zeichen\s*\(Schr[aä]gstrich\s*'/'\s*im REC-Segment verletzt Felddefinition\)\.?",
                re.IGNORECASE,
            ),
            "Impermissible characters (forward slash '/' in REC segment violates field specification).",
        ),
        (
            re.compile(
                r"Doppelabrechnung\s*-\s*Belegnummer wurde bereits mit Rechnung\s+([^\s]+)\s+abgerechnet\.?",
                re.IGNORECASE,
            ),
            r"Duplicate billing - receipt number was already billed with invoice \1.",
        ),
        (
            re.compile(
                r"Die Positionsnummer\s+(\d+)\s*\(([^\)]+)\)\s+ist zur angegebenen Diagnose\s+([^\s]+)\s+nicht abrechnungsf[aä]hig gem[aä][sß]\s+Heilmittelkatalog\s*\(Paragraph 302 SGB V\)\.?",
                re.IGNORECASE,
            ),
            r"Billing position code \1 (\2) is not eligible for reimbursement with diagnosis \3 according to the German Remedy Catalog (§ 302 SGB V).",
        ),

        # Common headers and departments
        (re.compile(r"^Betreff:\s*", re.IGNORECASE), "Subject: "),
        (re.compile(r"^Von:\s*", re.IGNORECASE), "From: "),
        (re.compile(r"^An:\s*", re.IGNORECASE), "To: "),
        (re.compile(r"^Datum:\s*", re.IGNORECASE), "Date: "),
        (re.compile(r"Abrechnungsteam\s+([A-Z]+)", re.IGNORECASE), r"\1 Billing Team"),
        (re.compile(r"Fachzentrum Abrechnung", re.IGNORECASE), "Billing Competence Center"),
        (re.compile(r"Abrechnungszentrum", re.IGNORECASE), "Billing Clearinghouse"),
        (re.compile(r"Abrechnungspr[uü]fung", re.IGNORECASE), "Billing Audit Department"),
    ]

    @classmethod
    def generate_report(cls, result: AnonymizationResult) -> str:
        """Generate the developer handover text with problem summary and email translation."""
        sections = [
            cls._build_header(result),
            cls._build_section_1_executive_summary(result),
            cls._build_section_2_translated_email(result),
            cls._build_footer(),
        ]
        return "\n\n".join(sections).strip()

    @staticmethod
    def _build_header(result: AnonymizationResult) -> str:
        sep = "=" * 80
        return (
            f"{sep}\n"
            f"PY-SEUDO DEVELOPER HANDOVER REPORT (ENGLISH)\n"
            f"GDPR-Compliant Rejection Analysis & English Translation\n"
            f"{sep}\n"
            f"CONFIDENTIALITY NOTICE: All personal identifiable data (names, birthdates,\n"
            f"addresses, doctor IDs, private practice IKs) in this document and the\n"
            f"associated files have been pseudonymized in strict compliance with the EU GDPR\n"
            f"and German § 302 SGB V regulations. Insurer routing IKs, ICD-10 diagnostic\n"
            f"codes, and technical tariffs have been preserved for bug-fixing purposes."
        )

    @classmethod
    def _build_section_1_executive_summary(cls, result: AnonymizationResult) -> str:
        sep = "-" * 80
        lines = [
            f"{sep}",
            "SECTION 1: SUMMARY OF PROBLEMS & REJECTION REASONS",
            f"{sep}",
        ]

        mirrored_errors = [m for m in result.mappings if m.error_mirrored]
        suspicions = result.suspicions

        if mirrored_errors:
            lines.append(f"STATUS: REJECTION DETECTED - {len(mirrored_errors)} FAULT(S) REPLICATED FOR DEBUGGING")
            lines.append("")
            lines.append("Key Issues Identified:")
            for idx, m in enumerate(mirrored_errors, 1):
                cat_val = m.category.value if hasattr(m.category, "value") else str(m.category)
                note_en = cls._translate_diagnostic_note(m.diagnostic_note, cat_val)
                lines.append(f"  {idx}. [{cat_val.upper()}]")
                lines.append(f"     • Replicated Defect:   {note_en}")
                if m.description:
                    lines.append(f"     • Technical Impact:    {m.description}")
        else:
            # Check if email contains diagnosis or tariff rejection without identifier errors
            email_text = result.original_email or result.anonymized_email
            if "nicht abrechnungsf" in email_text.lower() or "abweis" in email_text.lower() or "ablehn" in email_text.lower():
                lines.append("STATUS: CONTENT / TARIFF REJECTION DETECTED")
                lines.append("")
                lines.append("Key Issues Identified:")
                lines.append("  • The health insurer rejected one or more billing positions due to")
                lines.append("    a medical diagnosis mismatch under the German Remedy Catalog (§ 302 SGB V).")
                lines.append("  • All identifiers (IK, KVNR, invoice numbers) passed mathematical validation,")
                lines.append("    indicating the error lies in the billed position code vs. ICD-10 diagnosis.")
            else:
                lines.append("STATUS: CLEAN BILLING TRANSMISSION (NO FORMAL REJECTIONS DETECTED)")
                lines.append("")
                lines.append("All structural identifiers conform to official specifications.")

        if suspicions:
            lines.append("")
            lines.append(f"WARNING - {len(suspicions)} Potential Sensitive Item(s) Flagged:")
            for s in suspicions:
                lines.append(f"  • Line {s.line}: Flagged for verification ({s.reason})")

        lines.append("")
        lines.append("Summary Statistics:")
        lines.append(f"  • Unique Pseudonymized Entities: {len(result.mappings)}")
        lines.append(f"  • Total Replacements across Files: {result.total_replacements}")

        return "\n".join(lines)

    @classmethod
    def _build_section_2_translated_email(cls, result: AnonymizationResult) -> str:
        sep = "-" * 80
        lines = [
            f"{sep}",
            "SECTION 2: ENGLISH TRANSLATION OF ANONYMIZED EMAIL",
            f"{sep}",
        ]

        email_to_translate = result.anonymized_email or result.original_email
        if not email_to_translate.strip():
            lines.append("(No email text was provided in this processing run.)")
            return "\n".join(lines)

        translated_email = cls.translate_email_text(email_to_translate)
        lines.append(translated_email)
        return "\n".join(lines)

    @classmethod
    def translate_email_text(cls, email_text: str) -> str:
        """Translate German healthcare rejection email to English."""
        if not email_text:
            return ""

        output_lines: List[str] = []
        for line in email_text.splitlines():
            translated = line
            for pattern, replacement in cls.GERMAN_TO_ENGLISH_PATTERNS:
                if pattern.search(translated):
                    translated = pattern.sub(replacement, translated)
            output_lines.append(translated)

        return "\n".join(output_lines)

    @staticmethod
    def _translate_diagnostic_note(note_de: str, category_de: str) -> str:
        """Translate German diagnostic notes into concise English developer descriptions."""
        if not note_de:
            return "Defect intentionally replicated for developer analysis."

        n_lower = note_de.lower()
        if "prüfziffer" in n_lower or "pruefziffer" in n_lower:
            if "ik" in n_lower or "institutionskennzeichen" in category_de.lower():
                return "ARGE-IK Modulo-10 checksum error intentionally replicated."
            if "kvnr" in n_lower or "krankenversichertennummer" in category_de.lower():
                return "§ 290 SGB V check digit discrepancy intentionally replicated."
            return "Check digit calculation failure replicated."
        if "schr" in n_lower and "strich" in n_lower:
            return "Prohibited delimiter (slash '/') syntax defect replicated."
        if "doppelabrechnung" in n_lower or "doppelt" in n_lower:
            return "Duplicate billing receipt defect replicated."
        if "unbekannt" in n_lower or "status" in n_lower:
            return "Status error: Unknown / invalid identifier in insurer registry."
        if "zeichen" in n_lower or "format" in n_lower:
            return "Syntax / format anomaly replicated."

        return note_de

    @staticmethod
    def _build_footer() -> str:
        sep = "=" * 80
        return (
            f"{sep}\n"
            f"END OF REPORT - Generated automatically by py-seudo.\n"
            f"{sep}"
        )
