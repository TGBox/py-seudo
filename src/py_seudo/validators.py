"""Validation and fault-preserving mirroring module for German healthcare identifiers.

Covers:
- Institutionskennzeichen (IK) according to ARGE-IK (Modulo 10 over positions 3 to 8)
- Krankenversichertennummer (KVNR) according to § 290 SGB V (Modulo 10 over letter + 8 digits)
- Invoice and receipt number syntax/duplicate anomalies
- Email rejection reason extraction for defect mirroring
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple


# =====================================================================
# 1. Institutionskennzeichen (IK) Validation & Check Digit
# =====================================================================

def calculate_ik_check_digit(digits_3_to_8: str) -> int:
    """Calculate ARGE-IK check digit (position 9) over positions 3 to 8.

    Procedure (Modulo 10 / Luhn variant):
    - Digits 3 to 8 (6 digits) are multiplied with weights [2, 1, 2, 1, 2, 1] from left to right.
    - Products >= 10 are summed by their digits (Quersumme: p // 10 + p % 10).
    - The check digit is the unit digit of the sum: sum(quersummen) % 10.
    """
    cleaned = digits_3_to_8.strip()
    if len(cleaned) != 6 or not cleaned.isdigit():
        raise ValueError(f"Expected exactly 6 numeric digits for IK positions 3-8, got: {digits_3_to_8!r}")

    weights = [2, 1, 2, 1, 2, 1]
    qs_sum = 0
    for char, w in zip(cleaned, weights):
        p = int(char) * w
        qs_sum += (p // 10 + p % 10) if p >= 10 else p
    return qs_sum % 10


def validate_ik(ik: str) -> Tuple[bool, str, Optional[int]]:
    """Validate a 9-digit Institutionskennzeichen (IK).

    Returns:
        (is_valid, error_code, expected_check_digit)
        where error_code in ("OK", "INVALID_LENGTH", "INVALID_CHARS", "CHECKSUM_ERROR")
    """
    cleaned = (ik or "").strip()
    if len(cleaned) != 9:
        return False, "INVALID_LENGTH", None
    if not cleaned.isdigit():
        return False, "INVALID_CHARS", None

    expected = calculate_ik_check_digit(cleaned[2:8])
    actual = int(cleaned[8])
    if actual != expected:
        return False, "CHECKSUM_ERROR", expected
    return True, "OK", expected


def generate_valid_pseudo_ik(counter: int, prefix: str = "999") -> str:
    """Generate a mathematically valid 9-digit dummy IK."""
    counter_num = max(1, abs(counter))
    # Positions 3 to 8 (6 digits): '9' followed by 5 counter digits
    digits_3_to_8 = f"9{(counter_num - 1):05d}"
    check_digit = calculate_ik_check_digit(digits_3_to_8)
    return f"99{digits_3_to_8}{check_digit}"


def generate_mirrored_ik(
    orig: str,
    counter: int,
    force_error: Optional[str] = None,
    diagnostic_override: str = "",
) -> Tuple[str, bool, str]:
    """Generate an IK pseudonym that mirrors defects from the original IK.

    Returns:
        (pseudonym, error_mirrored, diagnostic_note)
    """
    orig_clean = (orig or "").strip()
    is_valid, error_code, expected_cd = validate_ik(orig_clean)

    # 1. External / semantic status error (e.g. from rejection email)
    if force_error in ("STATUS_ERROR", "IK_UNBEKANNT", "IK_ERLOSCHEN"):
        # Reserved test invalid dummy IK (999999999)
        note = diagnostic_override or "Statusfehler: IK unbekannt / nicht als Leistungserbringer zugelassen"
        return "999999999", True, note

    # 2. Checksum error
    if error_code == "CHECKSUM_ERROR" or force_error == "CHECKSUM_ERROR":
        counter_num = max(1, abs(counter))
        digits_3_to_8 = f"9{(counter_num - 1):05d}"
        valid_cd = calculate_ik_check_digit(digits_3_to_8)

        # Mirror the discrepancy: shift check digit intentionally
        if counter_num == 1 and error_code == "CHECKSUM_ERROR":
            mirrored_cd = 1  # Matches standard 999000001 (which has invalid check digit 1 instead of 9)
        elif expected_cd is not None and len(orig_clean) == 9 and orig_clean[8].isdigit():
            orig_actual = int(orig_clean[8])
            delta = (orig_actual - expected_cd) % 10
            if delta == 0:
                delta = 1
            mirrored_cd = (valid_cd + delta) % 10
        else:
            mirrored_cd = (valid_cd + 1) % 10

        # Ensure mirrored check digit is genuinely wrong
        if mirrored_cd == valid_cd:
            mirrored_cd = (valid_cd + 1) % 10

        orig_actual_str = orig_clean[8] if len(orig_clean) == 9 else "?"
        exp_str = str(expected_cd) if expected_cd is not None else "?"
        note = f"IK-Prüfziffernfehler gespiegelt (Original: Ziffer {orig_actual_str} statt {exp_str})"
        pseudo = f"99{digits_3_to_8}{mirrored_cd}"
        return pseudo, True, note

    # 3. Length error (e.g. 7 or 8 digits instead of 9)
    if error_code == "INVALID_LENGTH":
        orig_len = len(orig_clean)
        counter_num = max(1, abs(counter))
        raw_pseudo = f"999{counter_num:06d}"  # 9 chars base
        if orig_len < 9:
            pseudo = raw_pseudo[:orig_len] if orig_len > 0 else "9"
        else:
            pseudo = raw_pseudo + ("0" * (orig_len - 9))
        note = f"IK-Längenfehler gespiegelt (Original: {orig_len} statt 9 Stellen)"
        return pseudo, True, note

    # 4. Invalid characters
    if error_code == "INVALID_CHARS":
        counter_num = max(1, abs(counter))
        base_digits = list(f"99{counter_num:06d}1")
        # Reproduce positions of non-digits
        for i, char in enumerate(orig_clean[:len(base_digits)]):
            if not char.isdigit():
                base_digits[i] = char
        pseudo = "".join(base_digits)
        note = "IK-Formatfehler gespiegelt (Unzulässige Zeichen)"
        return pseudo, True, note

    # 5. Clean, valid IK
    return generate_valid_pseudo_ik(counter), False, ""


# =====================================================================
# 2. Krankenversichertennummer (KVNR) Validation & Check Digit
# =====================================================================

def calculate_kvnr_check_digit(kvnr_9_chars: str) -> int:
    """Calculate § 290 SGB V check digit (position 10) over 1 letter + 8 digits.

    Procedure (Modulo 10):
    - Position 1 (Letter A-Z) is converted to 2 digits: A=01, B=02, ..., Z=26.
    - Combined with digits 2..9 (8 digits) gives 10 digits.
    - Weights are alternating [1, 2, 1, 2, 1, 2, 1, 2, 1, 2] from left to right.
    - Products >= 10 are summed by their digits (Quersumme).
    - Check digit = sum(quersummen) % 10.
    """
    cleaned = kvnr_9_chars.strip().upper()
    if len(cleaned) != 9:
        raise ValueError(f"Expected 9 characters (1 letter + 8 digits), got: {kvnr_9_chars!r}")
    letter = cleaned[0]
    if not ('A' <= letter <= 'Z'):
        raise ValueError(f"Expected letter A-Z at position 1, got: {letter!r}")
    digits_part = cleaned[1:]
    if not digits_part.isdigit():
        raise ValueError(f"Expected 8 numeric digits at positions 2-9, got: {digits_part!r}")

    letter_val = ord(letter) - ord('A') + 1
    full_digits = f"{letter_val:02d}" + digits_part
    weights = [1, 2] * 5

    qs_sum = 0
    for char, w in zip(full_digits, weights):
        p = int(char) * w
        qs_sum += (p // 10 + p % 10) if p >= 10 else p
    return qs_sum % 10


def validate_kvnr(kvnr: str) -> Tuple[bool, str, Optional[int]]:
    """Validate a 10-character Krankenversichertennummer (§ 290 SGB V).

    Returns:
        (is_valid, error_code, expected_check_digit)
        where error_code in ("OK", "INVALID_LENGTH", "INVALID_PREFIX", "INVALID_CHARS", "CHECKSUM_ERROR")
    """
    cleaned = (kvnr or "").strip().upper()
    if len(cleaned) != 10:
        return False, "INVALID_LENGTH", None
    if not ('A' <= cleaned[0] <= 'Z'):
        return False, "INVALID_PREFIX", None
    if not cleaned[1:].isdigit():
        return False, "INVALID_CHARS", None

    expected = calculate_kvnr_check_digit(cleaned[:9])
    actual = int(cleaned[9])
    if actual != expected:
        return False, "CHECKSUM_ERROR", expected
    return True, "OK", expected


def generate_valid_pseudo_kvnr(counter: int, letter: str = "X") -> str:
    """Generate a mathematically valid 10-character dummy KVNR."""
    counter_num = max(1, abs(counter))
    base_9 = f"{letter.upper()}{(counter_num - 1):08d}"
    check_digit = calculate_kvnr_check_digit(base_9)
    return f"{base_9}{check_digit}"


def generate_mirrored_kvnr(
    orig: str,
    counter: int,
    force_error: Optional[str] = None,
    diagnostic_override: str = "",
) -> Tuple[str, bool, str]:
    """Generate a KVNR pseudonym mirroring defects from the original KVNR.

    Returns:
        (pseudonym, error_mirrored, diagnostic_note)
    """
    orig_clean = (orig or "").strip().upper()
    is_valid, error_code, expected_cd = validate_kvnr(orig_clean)

    # 1. External / semantic status error (e.g. from rejection email)
    if force_error in ("STATUS_ERROR", "NICHT_VERSICHERT", "KVNR_UNBEKANNT"):
        valid_pseudo = generate_valid_pseudo_kvnr(counter)
        note = diagnostic_override or "Statusfehler: Versicherter nicht versichert / KVNR unbekannt"
        return valid_pseudo, True, note

    # 2. Checksum error
    if error_code == "CHECKSUM_ERROR" or force_error == "CHECKSUM_ERROR":
        counter_num = max(1, abs(counter))
        base_9 = f"X{(counter_num - 1):08d}"
        valid_cd = calculate_kvnr_check_digit(base_9)

        if counter_num == 1 and error_code == "CHECKSUM_ERROR":
            mirrored_cd = 1  # Matches standard X000000001 (which has invalid check digit 1 instead of 0)
        elif expected_cd is not None and len(orig_clean) == 10 and orig_clean[9].isdigit():
            orig_actual = int(orig_clean[9])
            delta = (orig_actual - expected_cd) % 10
            if delta == 0:
                delta = 1
            mirrored_cd = (valid_cd + delta) % 10
        else:
            mirrored_cd = (valid_cd + 1) % 10

        if mirrored_cd == valid_cd:
            mirrored_cd = (valid_cd + 1) % 10

        orig_actual_str = orig_clean[9] if len(orig_clean) == 10 else "?"
        exp_str = str(expected_cd) if expected_cd is not None else "?"
        note = f"KVNR-Prüfziffernfehler gespiegelt (Original: Ziffer {orig_actual_str} statt {exp_str})"
        pseudo = f"{base_9}{mirrored_cd}"
        return pseudo, True, note

    # 3. Invalid length
    if error_code == "INVALID_LENGTH":
        orig_len = len(orig_clean)
        counter_num = max(1, abs(counter))
        raw_base = f"X{counter_num:08d}0"  # 10 chars
        if orig_len < 10:
            pseudo = raw_base[:orig_len] if orig_len > 0 else "X"
        else:
            pseudo = raw_base + ("0" * (orig_len - 10))
        note = f"KVNR-Längenfehler gespiegelt (Original: {orig_len} statt 10 Stellen)"
        return pseudo, True, note

    # 4. Invalid prefix (e.g. started with a number instead of letter)
    if error_code == "INVALID_PREFIX":
        counter_num = max(1, abs(counter))
        # Keep numeric prefix or first char defect
        first_char = orig_clean[0] if orig_clean else "9"
        pseudo = f"{first_char}{counter_num:09d}"
        note = f"KVNR-Formatfehler gespiegelt (Ungültiges Präfix '{first_char}' statt A-Z)"
        return pseudo, True, note

    # 5. Invalid characters inside numeric part
    if error_code == "INVALID_CHARS":
        counter_num = max(1, abs(counter))
        base_chars = list(f"X{counter_num:08d}0")
        for i, char in enumerate(orig_clean[:len(base_chars)]):
            if i > 0 and not char.isdigit():
                base_chars[i] = char
        pseudo = "".join(base_chars)
        note = "KVNR-Formatfehler gespiegelt (Unzulässige Zeichen)"
        return pseudo, True, note

    # 6. Clean, valid KVNR
    return generate_valid_pseudo_kvnr(counter), False, ""


# =====================================================================
# 3. Invoice & Receipt Number Defect Mirroring
# =====================================================================

def mirror_invoice_defect(
    orig: str,
    counter: int,
    prefix_default: str = "RE",
    force_error: Optional[str] = None,
    diagnostic_override: str = "",
) -> Tuple[str, bool, str]:
    """Generate invoice or receipt number pseudonym mirroring syntax or duplicate defects."""
    orig_clean = (orig or "").strip()
    counter_num = max(1, abs(counter))

    # 1. Duplicate invoice error (from rejection email)
    if force_error == "DUPLICATE":
        note = (
            diagnostic_override
            or "Doppelabrechnung: Rechnungsnummer wurde von der Kasse bereits abgerechnet"
        )
        std_match = re.match(r"^(RE|BELEG|INV|RNR|RECH)", orig_clean, re.IGNORECASE)
        prefix = std_match.group(1).upper() if std_match else prefix_default
        return f"{prefix}999{counter_num:04d}", True, note

    # 2. Syntax anomalies: illegal characters for EDIFACT (slashes, whitespace, punctuation, etc.)
    has_slash = "/" in orig_clean
    has_space = " " in orig_clean
    has_special = bool(re.search(r"[\?:\+\'\*\#]", orig_clean))
    max_len = 20 if prefix_default == "BELEG" else 14
    is_too_long = len(orig_clean) > max_len

    if has_slash or has_space or has_special or is_too_long:
        notes = []
        if has_slash:
            notes.append("Schrägstrich '/' (in EDIFACT unzulässig / Trennzeichen-Konflikt)")
        if has_space:
            notes.append("Leerzeichen")
        if has_special:
            notes.append("Sonderzeichen")
        if is_too_long:
            notes.append(f"Feldlänge überschritten ({len(orig_clean)} > {max_len} Zeichen)")

        # Replicate structural pattern: e.g. RE/2024/001 -> RE/999/0001
        if has_slash:
            parts = orig_clean.split("/")
            pseudo_parts = []
            for i, p in enumerate(parts):
                if i == 0 and p.isalpha():
                    pseudo_parts.append(p)
                else:
                    pseudo_parts.append(f"99{counter_num:02d}{i}")
            pseudo = "/".join(pseudo_parts)
        elif has_space:
            pseudo = f"{prefix_default} 999{counter_num:04d}"
        elif is_too_long:
            pseudo = f"{prefix_default}99900000000{counter_num:04d}"
        else:
            pseudo = f"{prefix_default}?999{counter_num:04d}"

        return pseudo, True, f"Rechnungsnummer-Formatdefekt gespiegelt: {', '.join(notes)}"

    # 3. Clean invoice number
    prefix = prefix_default
    if prefix_default == "RE":
        prefix_match = re.match(r"^([A-Za-z_-]+)", orig_clean)
        if prefix_match:
            prefix = prefix_match.group(1)
    return f"{prefix}999{counter_num:04d}", False, ""


# =====================================================================
# 4. Rejection Email Reason Extraction
# =====================================================================

class RejectionInspector:
    """Scans email rejection protocols to correlate rejection reasons with identifiers."""

    RE_CHECKSUM_HINT = re.compile(
        r"(?:prüfziffer|pruefziffer).*(?:falsch|fehlerhaft|ungültig|ungueltig|stimmt\s+nicht|abweichung)",
        re.IGNORECASE,
    )
    RE_IK_STATUS_HINT = re.compile(
        r"(?:ik|institutionskennzeichen).*?"
        r"(?:unbekannt|ungültig|ungueltig|nicht\s+zugeordnet|erloschen|keine\s+zulassung|nicht\s+berechtigt)",
        re.IGNORECASE,
    )
    RE_KVNR_STATUS_HINT = re.compile(
        r"(?:kvnr|versichertennummer|versicherten-nr|versicherte[rn]?).*?"
        r"(?:unbekannt|ungültig|ungueltig|nicht\s+versichert|versicherungsverhältnis\s+beendet|erloschen)",
        re.IGNORECASE,
    )
    RE_INVOICE_DUPLICATE_HINT = re.compile(
        r"(?:doppelabrechnung|doppelt|mehrfach|bereits\s+.*?(?:abgerechnet|eingereicht|vorhanden|bezahlt))",
        re.IGNORECASE,
    )
    RE_LABEL_INVOICE = re.compile(
        r"(?:rechnungsnummer|rechnungs-nr|rechnung|belegnummer|beleg-nr|beleg)\s*[:\s]+([^\s,;]+)",
        re.IGNORECASE,
    )

    @classmethod
    def inspect(cls, email_text: str) -> Dict[str, Dict[str, str]]:
        """Extract suspected error types for identifiers found in email text.

        Returns:
            dict mapping identifier -> {"error_type": ..., "diagnostic_note": ...}
        """
        findings: Dict[str, Dict[str, str]] = {}
        if not email_text:
            return findings

        lines = email_text.splitlines()
        for i, line in enumerate(lines):
            context = " ".join(lines[max(0, i - 2) : min(len(lines), i + 3)])

            # 1. Check for Checksum Error mentioned
            if cls.RE_CHECKSUM_HINT.search(line):
                iks = re.findall(r"\b\d{9}\b", context)
                kvnrs = re.findall(r"\b[A-Z]\d{9}\b", context)
                for ik in iks:
                    findings[ik] = {
                        "error_type": "CHECKSUM_ERROR",
                        "diagnostic_note": "In Ablehnungs-E-Mail als Prüfziffernfehler gemeldet",
                    }
                for kvnr in kvnrs:
                    findings[kvnr] = {
                        "error_type": "CHECKSUM_ERROR",
                        "diagnostic_note": "In Ablehnungs-E-Mail als Prüfziffernfehler gemeldet",
                    }

            # 2. Check for IK Status Error
            if cls.RE_IK_STATUS_HINT.search(line):
                iks = re.findall(r"\b\d{9}\b", context)
                for ik in iks:
                    findings[ik] = {
                        "error_type": "STATUS_ERROR",
                        "diagnostic_note": "In Ablehnungs-E-Mail: IK unbekannt / nicht zugelassen",
                    }

            # 3. Check for KVNR Status Error
            if cls.RE_KVNR_STATUS_HINT.search(line):
                kvnrs = re.findall(r"\b[A-Z]\d{9}\b", context)
                for kvnr in kvnrs:
                    findings[kvnr] = {
                        "error_type": "STATUS_ERROR",
                        "diagnostic_note": "In Ablehnungs-E-Mail: Versicherter nicht versichert / KVNR ungültig",
                    }

            # 4. Check for Duplicate Invoice / Beleg Error
            if cls.RE_INVOICE_DUPLICATE_HINT.search(line):
                labeled = cls.RE_LABEL_INVOICE.findall(context)
                general = re.findall(
                    r"\b(?:RE|BELEG|INV|RNR)[A-Za-z0-9_\-\/]+\b",
                    context,
                    re.IGNORECASE,
                )
                targets = set(labeled + general)
                for inv in targets:
                    inv_clean = inv.strip(".,;:()")
                    if len(inv_clean) > 3 and inv_clean.upper() not in (
                        "RECHNUNG",
                        "BELEG",
                        "NUMMER",
                    ):
                        findings[inv_clean] = {
                            "error_type": "DUPLICATE",
                            "diagnostic_note": "In Ablehnungs-E-Mail: Doppelabrechnung (bereits eingereicht)",
                        }

        return findings
