"""Email parser and sanitizer for clearing sensitive headers, contacts, and text references."""
from __future__ import annotations

import email
from email import policy
import re
from typing import Dict, List, Optional, Tuple

from py_seudo.models import MappingEntry, ReplacementCategory


class EmailAnonymizer:
    """Sanitizes email headers, contact signatures, and harmonizes body text

    with the pseudonyms established during ESOL anonymization.
    """

    PHONE_REGEX = re.compile(
        r"(?:(?:(?:\+|00)49\s*[\d\s\/\(\)-]{7,})|(?:\b0[1-9][\d\s\/\(\)-]{6,}\b))"
    )
    EMAIL_REGEX = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
    KVNR_REGEX = re.compile(r"\b[A-Z]\d{9}\b")
    IK_REGEX = re.compile(r"\b\d{9}\b")

    def __init__(
        self,
        raw_email: str,
        shared_mappings: Optional[Dict[str, MappingEntry]] = None,
        practice_iks: Optional[List[str]] = None,
        kassen_iks: Optional[List[str]] = None,
    ):
        self.raw_email = raw_email
        self.shared_mappings = dict(shared_mappings) if shared_mappings else {}
        self.practice_iks = set(practice_iks or [])
        self.kassen_iks = set(kassen_iks or [])
        self.email_mappings: List[MappingEntry] = []

    def anonymize(self) -> Tuple[str, List[MappingEntry]]:
        """Anonymize the email (either RFC 822 .eml format or plain text)."""
        if not self.raw_email.strip():
            return "", []

        if self._is_rfc822_email(self.raw_email):
            return self._anonymize_rfc822()
        else:
            return self._anonymize_plain_text()

    def _is_rfc822_email(self, text: str) -> bool:
        """Heuristic to determine whether input is an RFC 822 email file."""
        lines = text.splitlines()[:20]
        header_keys = {"from:", "to:", "subject:", "date:", "message-id:", "content-type:"}
        found_headers = 0
        for line in lines:
            line_lower = line.lower().strip()
            for h in header_keys:
                if line_lower.startswith(h):
                    found_headers += 1
                    break
        return found_headers >= 2

    def _anonymize_rfc822(self) -> Tuple[str, List[MappingEntry]]:
        """Parse, sanitize headers, and replace text in RFC 822 email."""
        msg = email.message_from_string(self.raw_email, policy=policy.default)

        # Sanitize headers
        if "from" in msg:
            orig_from = msg["from"]
            msg.replace_header("from", "Abrechnungsstelle <abrechnung@kasse.invalid>")
            self._record_mapping(
                orig_from,
                "Abrechnungsstelle <abrechnung@kasse.invalid>",
                ReplacementCategory.CONTACT_INFO,
                "E-Mail Header: Von",
            )

        if "to" in msg:
            orig_to = msg["to"]
            msg.replace_header("to", "Praxisleitung <praxis@beispiel.invalid>")
            self._record_mapping(
                orig_to,
                "Praxisleitung <praxis@beispiel.invalid>",
                ReplacementCategory.CONTACT_INFO,
                "E-Mail Header: An",
            )

        if "cc" in msg:
            msg.replace_header("cc", "anonymisiert@beispiel.invalid")

        for h in ["message-id", "received", "dkim-signature", "x-sender-ip", "user-agent", "x-mailer"]:
            if h in msg:
                del msg[h]

        if "subject" in msg:
            orig_subj = msg["subject"]
            sanitized_subj = self._apply_replacements(orig_subj)
            msg.replace_header("subject", sanitized_subj)

        # Ensure Content-Transfer-Encoding is 8bit so output remains clean human-readable text
        if "content-transfer-encoding" in msg:
            del msg["content-transfer-encoding"]
        msg["Content-Transfer-Encoding"] = "8bit"

        # Process payload
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                if content_type in ("text/plain", "text/html"):
                    try:
                        payload = part.get_payload(decode=True)
                        charset = part.get_content_charset() or "utf-8"
                        text = payload.decode(charset, errors="replace")
                        sanitized = self._apply_replacements(text)
                        part.set_payload(sanitized)
                        if "content-transfer-encoding" in part:
                            del part["content-transfer-encoding"]
                        part["Content-Transfer-Encoding"] = "8bit"
                    except Exception:
                        pass
        else:
            try:
                payload = msg.get_payload(decode=True)
                charset = msg.get_content_charset() or "utf-8"
                if payload:
                    text = payload.decode(charset, errors="replace")
                else:
                    text = msg.get_payload() or ""
                sanitized = self._apply_replacements(text)
                msg.set_payload(sanitized)
            except Exception:
                pass

        return msg.as_string(), self.email_mappings

    def _anonymize_plain_text(self) -> Tuple[str, List[MappingEntry]]:
        """Sanitize plain text email content."""
        sanitized = self._apply_replacements(self.raw_email)
        return sanitized, self.email_mappings

    def _apply_replacements(self, text: str) -> str:
        """Apply all shared ESOL mappings first, then apply general regex sanitizers."""
        result = text

        # 1. Apply known mappings from ESOL (longest strings first)
        sorted_mappings = sorted(
            self.shared_mappings.items(), key=lambda item: len(item[0]), reverse=True
        )

        for orig_key, entry in sorted_mappings:
            if not orig_key or len(orig_key) < 2:
                continue

            if re.match(r"^\w+$", orig_key):
                pattern = rf"\b{re.escape(orig_key)}\b"
            else:
                pattern = re.escape(orig_key)

            matches = list(re.finditer(pattern, result))
            if matches:
                result = re.sub(pattern, entry.pseudonym, result)
                self._record_mapping(
                    orig_key,
                    entry.pseudonym,
                    entry.category,
                    f"E-Mail Ersetzung: {entry.description or orig_key}",
                    count=len(matches),
                )

        # 2. General regex for Phone numbers
        for match in self.PHONE_REGEX.finditer(result):
            phone_str = match.group(0).strip()
            if re.match(r"^\d{2}\.\d{2}\.\d{4}$", phone_str) or re.match(r"^\d{9}$", phone_str):
                continue
            dummy_phone = "+49 000 0000000"
            result = result.replace(phone_str, dummy_phone)
            self._record_mapping(
                phone_str, dummy_phone, ReplacementCategory.CONTACT_INFO, "Telefon-/Faxnummer"
            )

        # 3. General regex for E-Mail addresses
        for match in self.EMAIL_REGEX.finditer(result):
            email_str = match.group(0).strip()
            if not self._is_placeholder_address(email_str):
                dummy_email = "kontakt@beispiel.invalid"
                result = result.replace(email_str, dummy_email)
                self._record_mapping(
                    email_str, dummy_email, ReplacementCategory.CONTACT_INFO, "E-Mail-Adresse"
                )

        # 4. Check for any remaining 9-digit practice IKs
        for p_ik in self.practice_iks:
            if p_ik in result:
                pseudo_ik = self.shared_mappings.get(
                    p_ik, MappingEntry(p_ik, "999000001", ReplacementCategory.PRACTICE_IK)
                ).pseudonym
                result = result.replace(p_ik, pseudo_ik)
                self._record_mapping(
                    p_ik, pseudo_ik, ReplacementCategory.PRACTICE_IK, "Praxis-IK im Text"
                )

        return result

    # Domains, die von py-seudo selbst erzeugt werden und daher nicht erneut
    # ersetzt werden duerfen. RFC 2606 / RFC 6761 reservieren .invalid und .example
    # ausdruecklich fuer solche Zwecke.
    PLACEHOLDER_DOMAINS = frozenset({"beispiel.invalid", "kasse.invalid", "example.com"})
    PLACEHOLDER_TLDS = (".invalid", ".example", ".test", ".localhost")

    @classmethod
    def _is_placeholder_address(cls, address: str) -> bool:
        """True, wenn die Adresse bereits ein Platzhalter ist.

        Prueft den Domain-Teil, nicht die ganze Zeichenkette: eine echte Adresse wie
        ``info@invalid-praxis-mueller.de`` enthaelt zwar das Wort "invalid", ist aber
        kein Platzhalter und muss ersetzt werden.
        """
        _, _, domain = address.rpartition("@")
        domain = domain.lower().rstrip(".")
        if not domain:
            return False
        if domain in cls.PLACEHOLDER_DOMAINS:
            return True
        return any(domain == tld.lstrip(".") or domain.endswith(tld) for tld in cls.PLACEHOLDER_TLDS)

    def _record_mapping(
        self,
        original: str,
        pseudonym: str,
        category: ReplacementCategory,
        description: str = "",
        count: int = 1,
    ) -> None:
        """Add to list of mappings detected/applied in this email."""
        for existing in self.email_mappings:
            if existing.original == original:
                existing.count += count
                return

        self.email_mappings.append(
            MappingEntry(
                original=original,
                pseudonym=pseudonym,
                category=category,
                count=count,
                description=description,
            )
        )
