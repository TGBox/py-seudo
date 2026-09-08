"""Email parser and sanitizer for clearing sensitive headers, contacts, and text references."""
from __future__ import annotations

import email
from email import policy
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from py_seudo.email.names import NameDetector, NameHit, NameRole
from py_seudo.models import MappingEntry, ReplacementCategory, Suspicion


@dataclass(frozen=True)
class _Span:
    """Eine geplante Ersetzung an einer konkreten Textstelle."""

    start: int
    end: int
    original: str
    replacement: str
    category: ReplacementCategory
    description: str
    #: Hoehere Prioritaet gewinnt bei Ueberschneidung.
    priority: int


# Prioritaeten: was aus der ESOL-Datei bekannt ist, schlaegt jede Heuristik.
_PRIO_MAPPING = 40
_PRIO_NAME = 30
_PRIO_EMAIL = 20
_PRIO_IK = 15
_PRIO_PHONE = 10

_ROLE_CATEGORY = {
    NameRole.PATIENT: ReplacementCategory.PATIENT_NAME,
    NameRole.DOCTOR: ReplacementCategory.DOCTOR_NAME,
    NameRole.CONTACT: ReplacementCategory.CONTACT_PERSON,
}

_FEMALE_FIRST_NAMES_SET = frozenset({
    "anna", "andrea", "anja", "angelika", "barbara", "birgit", "brigitte",
    "christa", "christina", "christine", "claudia", "daniela", "elke", "emma",
    "erika", "hannah", "heike", "helga", "ingrid", "julia", "karin",
    "katharina", "kerstin", "laura", "lea", "lena", "lisa", "maria", "marion",
    "martina", "melanie", "mia", "monika", "nicole", "petra", "renate",
    "sabine", "sarah", "silke", "simone", "sophie", "stefanie", "steffi",
    "susanne", "tanja", "ulla", "ursula", "ute"
})

_MALE_FIRST_NAMES_SET = frozenset({
    "alexander", "andreas", "bernd", "carsten", "christian", "daniel", "david",
    "dieter", "dirk", "felix", "florian", "frank", "hans", "holger", "jan",
    "jens", "joerg", "johannes", "jonas", "juergen", "jürgen", "karsten",
    "klaus", "leon", "lukas", "manfred", "markus", "martin", "matthias",
    "maximilian", "michael", "oliver", "paul", "peter", "philipp", "ralf",
    "ralph", "sebastian", "stefan", "stephan", "sven", "thomas", "thorsten",
    "tim", "tobias", "torsten", "ulrich", "uwe", "wolfgang"
})

_PREFERRED_SURNAMES: Dict[str, str] = {
    "müller": "Schmidt",
    "mueller": "Schmidt",
    "sonnenschein": "Winkler",
    "ulrichs": "Schuhmann",
    "meier": "Schmidt",
}

_PREFERRED_FIRST_NAMES: Dict[str, str] = {
    "simone": "Ulla",
}

_FEMALE_FIRST_NAMES_POOL: Sequence[str] = (
    "Ulla", "Sabine", "Claudia", "Susanne", "Petra", "Andrea", "Monika",
    "Birgit", "Renate", "Erika", "Brigitte", "Christa", "Elke", "Julia",
    "Maria", "Stefanie", "Melanie", "Christina", "Katharina", "Nicole"
)

_MALE_FIRST_NAMES_POOL: Sequence[str] = (
    "Michael", "Thomas", "Stefan", "Andreas", "Christian", "Peter",
    "Klaus", "Wolfgang", "Hans", "Jürgen", "Dieter", "Manfred",
    "Uwe", "Frank", "Bernd", "Markus", "Martin", "Jan", "Daniel"
)

_SURNAMES_POOL: Sequence[str] = (
    "Schmidt", "Winkler", "Schuhmann", "Weber", "Fischer", "Schneider",
    "Bauer", "Hoffmann", "Wagner", "Becker", "Schulz", "Koch", "Richter",
    "Klein", "Wolf", "Schröder", "Neumann", "Schwarz", "Zimmermann", "Braun",
    "Krüger", "Hartmann", "Lange", "Schmitt", "Werner", "Krause", "Lehmann",
    "Huber", "Herrmann", "Köhler"
)


class EmailAnonymizer:
    """Sanitizes email headers, contact signatures, and harmonizes body text

    with the pseudonyms established during ESOL anonymization.

    Namen, die nur in der E-Mail vorkommen und daher aus der ESOL-Datei nicht
    bekannt sind, werden ueber ihren Kontext erkannt (siehe
    :mod:`py_seudo.email.names`). Was dabei unklar bleibt, landet in
    :attr:`suspicions` und wird dem Anwender gemeldet.
    """

    PHONE_REGEX = re.compile(
        r"(?:(?:(?:\+|00)49\s*[\d\s\/\(\)-]{7,})|(?:\b0[1-9][\d\s\/\(\)-]{6,}\b))"
    )
    EMAIL_REGEX = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
    KVNR_REGEX = re.compile(r"\b[A-Z]\d{9}\b")
    IK_REGEX = re.compile(r"\b\d{9}\b")

    # Domains, die von py-seudo selbst erzeugt werden und daher nicht erneut
    # ersetzt werden duerfen. RFC 2606 / RFC 6761 reservieren .invalid und .example
    # ausdruecklich fuer solche Zwecke.
    PLACEHOLDER_DOMAINS = frozenset({"beispiel.invalid", "kasse.invalid", "example.com"})
    PLACEHOLDER_TLDS = (".invalid", ".example", ".test", ".localhost")

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
        self.suspicions: List[Suspicion] = []

        # Personen, die erst in der E-Mail auftauchen.
        self._person_index: Dict[Tuple[NameRole, str], int] = {}
        self._person_gender: Dict[Tuple[NameRole, str], str] = {}
        self._person_data: Dict[Tuple[NameRole, str], Dict[str, Any]] = {}
        self._used_surnames: Set[str] = set()
        self._used_female_first: Set[str] = set()
        self._used_male_first: Set[str] = set()
        self._surname_pool_idx = 0
        self._female_first_pool_idx = 0
        self._male_first_pool_idx = 0
        self._person_counter = self._highest_used_index()

    # ------------------------------------------------------------------
    # Einstieg
    # ------------------------------------------------------------------

    def anonymize(self) -> Tuple[str, List[MappingEntry]]:
        """Anonymize the email (either RFC 822 .eml format or plain text)."""
        if not self.raw_email.strip():
            return "", []

        if self._is_rfc822_email(self.raw_email):
            return self._anonymize_rfc822()
        return self._anonymize_plain_text()

    def _is_rfc822_email(self, text: str) -> bool:
        """Determines whether input is an RFC 822 email file with leading headers."""
        if not text.strip():
            return False
        lines = text.splitlines()
        header_lines: List[str] = []
        for line in lines:
            if not line.strip():
                break
            header_lines.append(line)

        if not header_lines:
            return False

        header_field_pattern = re.compile(r"^[A-Za-z0-9_-]+:\s*")
        header_keys = {"from:", "to:", "subject:", "date:", "message-id:", "content-type:", "received:", "cc:", "bcc:"}
        found_headers = 0

        for line in header_lines:
            if line.startswith(" ") or line.startswith("\t"):
                # Continuation line
                continue
            if not header_field_pattern.match(line):
                return False
            line_lower = line.lower().strip()
            for h in header_keys:
                if line_lower.startswith(h):
                    found_headers += 1
                    break

        return found_headers >= 2

    def _anonymize_rfc822(self) -> Tuple[str, List[MappingEntry]]:
        """Parse, sanitize headers, and replace text in RFC 822 email."""
        msg = email.message_from_string(self.raw_email, policy=policy.compat32)

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
            sanitized_subj = self._apply_replacements(orig_subj, section="Betreff")
            msg.replace_header("subject", sanitized_subj)

        # Process payload
        if msg.is_multipart():
            for idx, part in enumerate(msg.walk(), start=1):
                content_type = part.get_content_type()
                if content_type in ("text/plain", "text/html"):
                    try:
                        text = self._extract_message_text(part)
                        sanitized = self._apply_replacements(text, section=f"Textteil {idx}")
                        part.set_payload(sanitized)
                        if "content-transfer-encoding" in part:
                            del part["content-transfer-encoding"]
                        part["Content-Transfer-Encoding"] = "8bit"
                    except Exception:
                        pass
        else:
            try:
                text = self._extract_message_text(msg)
                sanitized = self._apply_replacements(text, section="Nachrichtentext")
                msg.set_payload(sanitized)
                if "content-transfer-encoding" in msg:
                    del msg["content-transfer-encoding"]
                msg["Content-Transfer-Encoding"] = "8bit"
            except Exception:
                pass

        return msg.as_string(), self.email_mappings

    @staticmethod
    def _extract_message_text(part: email.message.Message) -> str:
        """Safely extract decoded text without corrupting German special characters."""
        cte = str(part.get("content-transfer-encoding", "")).strip().lower()
        charset = part.get_content_charset() or "utf-8"

        if cte in ("quoted-printable", "base64"):
            try:
                payload_bytes = part.get_payload(decode=True)
                if isinstance(payload_bytes, bytes):
                    for enc in (charset, "utf-8", "latin-1", "cp1252"):
                        try:
                            return payload_bytes.decode(enc)
                        except (UnicodeDecodeError, LookupError):
                            continue
                    return payload_bytes.decode("utf-8", errors="replace")
            except Exception:
                pass

        raw_payload = part.get_payload()
        if isinstance(raw_payload, str):
            return raw_payload
        if isinstance(raw_payload, bytes):
            for enc in (charset, "utf-8", "latin-1", "cp1252"):
                try:
                    return raw_payload.decode(enc)
                except (UnicodeDecodeError, LookupError):
                    continue
            return raw_payload.decode("utf-8", errors="replace")
        return ""

    def _anonymize_plain_text(self) -> Tuple[str, List[MappingEntry]]:
        """Sanitize plain text email content."""
        sanitized = self._apply_replacements(self.raw_email, section="Text")
        return sanitized, self.email_mappings

    # ------------------------------------------------------------------
    # Ersetzung: ein Durchlauf ueber ueberschneidungsfreie Bereiche
    # ------------------------------------------------------------------

    def _apply_replacements(self, text: str, section: str = "") -> str:
        """Alle Ersetzungen in EINEM Durchlauf.

        Frueher lief pro Mapping ein eigenes ``re.sub`` ueber den bereits
        veraenderten Text. Dabei konnte ein eingesetztes Pseudonym von einer
        spaeteren Regel erneut getroffen werden -- ESOL-Datei und E-Mail
        widersprachen sich dann. Hier werden erst alle Fundstellen auf dem
        Originaltext gesammelt, Ueberschneidungen aufgeloest und dann genau
        einmal ersetzt.
        """
        if not text:
            return text

        mapping_spans = self._mapping_spans(text)
        email_spans = self._email_spans(text)

        protected = [(s.start, s.end) for s in mapping_spans + email_spans]
        for entry in self.shared_mappings.values():
            if entry.pseudonym and len(entry.pseudonym) >= 2:
                for m in re.finditer(rf"\b{re.escape(entry.pseudonym)}\b", text):
                    protected.append((m.start(), m.end()))

        detector = NameDetector(protected)
        name_spans = self._name_spans(text, detector)

        spans = mapping_spans + email_spans + name_spans
        spans += self._ik_spans(text)
        spans += self._phone_spans(text)

        accepted = self._resolve_overlaps(spans)
        result = self._rebuild(text, accepted)

        for span in accepted:
            self._record_mapping(
                span.original, span.replacement, span.category, span.description
            )

        for suspicion in detector.suspicions(text, [(s.start, s.end) for s in accepted]):
            self._add_suspicion(suspicion, section)

        return result

    @staticmethod
    def _resolve_overlaps(spans: Sequence[_Span]) -> List[_Span]:
        """Hoechste Prioritaet gewinnt, bei Gleichstand der laengere Bereich."""
        ordered = sorted(spans, key=lambda s: (-s.priority, -(s.end - s.start), s.start))
        kept: List[_Span] = []
        for span in ordered:
            if span.start >= span.end:
                continue
            if any(span.start < k.end and span.end > k.start for k in kept):
                continue
            kept.append(span)
        return sorted(kept, key=lambda s: s.start)

    @staticmethod
    def _rebuild(text: str, spans: Sequence[_Span]) -> str:
        out: List[str] = []
        cursor = 0
        for span in spans:
            out.append(text[cursor : span.start])
            out.append(span.replacement)
            cursor = span.end
        out.append(text[cursor:])
        return "".join(out)

    # ------------------------------------------------------------------
    # Quellen fuer Ersetzungen
    # ------------------------------------------------------------------

    def _mapping_spans(self, text: str) -> List[_Span]:
        """Fundstellen der aus der ESOL-Datei bekannten Werte."""
        spans: List[_Span] = []
        # Laengste zuerst, damit "Max Mustermann" vor "Mustermann" greift
        for orig_key, entry in sorted(
            self.shared_mappings.items(), key=lambda item: len(item[0]), reverse=True
        ):
            if not orig_key or len(orig_key) < 2:
                continue
            if orig_key == entry.pseudonym:
                # Pseudonym gleicht dem Original -- eine Ersetzung waere ein No-Op
                continue

            pattern = rf"\b{re.escape(orig_key)}\b" if re.match(r"^\w+$", orig_key) else re.escape(orig_key)
            for m in re.finditer(pattern, text):
                spans.append(
                    _Span(
                        start=m.start(),
                        end=m.end(),
                        original=orig_key,
                        replacement=entry.pseudonym,
                        category=entry.category,
                        description=f"E-Mail Ersetzung: {entry.description or orig_key}",
                        priority=_PRIO_MAPPING,
                    )
                )
        return spans

    def _name_spans(self, text: str, detector: NameDetector) -> List[_Span]:
        """Personennamen, die nur in der E-Mail vorkommen."""
        hits = detector.find(text)
        if not hits:
            return []

        # Erst Personen registrieren und Pseudonyme zuweisen -- damit dieselbe Person
        # in Anrede und Signatur denselben Nachnamen und konsistente Daten erhaelt.
        for hit in hits:
            self._ensure_person_registered(hit)

        spans = []
        for hit in hits:
            spans.append(
                _Span(
                    start=hit.start,
                    end=hit.end,
                    original=hit.text,
                    replacement=self._pseudonym_for(hit),
                    category=_ROLE_CATEGORY[hit.role],
                    description=f"Name aus der E-Mail ({hit.trigger})",
                    priority=_PRIO_NAME,
                )
            )
        return spans

    def _email_spans(self, text: str) -> List[_Span]:
        spans = []
        for m in self.EMAIL_REGEX.finditer(text):
            address = m.group(0)
            if self._is_placeholder_address(address):
                continue
            spans.append(
                _Span(
                    start=m.start(),
                    end=m.end(),
                    original=address,
                    replacement="kontakt@beispiel.invalid",
                    category=ReplacementCategory.CONTACT_INFO,
                    description="E-Mail-Adresse",
                    priority=_PRIO_EMAIL,
                )
            )
        return spans

    def _phone_spans(self, text: str) -> List[_Span]:
        spans = []
        for m in self.PHONE_REGEX.finditer(text):
            raw = m.group(0)
            stripped = raw.strip()
            if re.fullmatch(r"\d{9}", stripped) or re.fullmatch(r"\d{2}\.\d{2}\.\d{4}", stripped):
                continue
            # Nur den getrimmten Teil ersetzen, damit umgebender Whitespace bleibt
            offset = m.start() + (len(raw) - len(raw.lstrip()))
            spans.append(
                _Span(
                    start=offset,
                    end=offset + len(stripped),
                    original=stripped,
                    replacement="+49 000 0000000",
                    category=ReplacementCategory.CONTACT_INFO,
                    description="Telefon-/Faxnummer",
                    priority=_PRIO_PHONE,
                )
            )
        return spans

    def _ik_spans(self, text: str) -> List[_Span]:
        """Praxis-IKs, die im Text stehen, aber kein eigenes Mapping haben."""
        spans = []
        for p_ik in self.practice_iks:
            entry = self.shared_mappings.get(p_ik)
            pseudo = entry.pseudonym if entry else "999000001"
            for m in re.finditer(rf"\b{re.escape(p_ik)}\b", text):
                spans.append(
                    _Span(
                        start=m.start(),
                        end=m.end(),
                        original=p_ik,
                        replacement=pseudo,
                        category=ReplacementCategory.PRACTICE_IK,
                        description="Praxis-IK im Text",
                        priority=_PRIO_IK,
                    )
                )
        return spans

    # ------------------------------------------------------------------
    # Pseudonyme fuer Namen aus der E-Mail
    # ------------------------------------------------------------------

    @staticmethod
    def _surname_key(name: str) -> str:
        tokens = [t for t in re.split(r"\s+", name.strip()) if t]
        return tokens[-1].rstrip(".").casefold() if tokens else name.casefold()

    def _highest_used_index(self) -> int:
        """Hoechste bereits von der ESOL-Seite vergebene Nummer.

        Die E-Mail-Seite zaehlt darueber weiter, damit ``Mustermann_2`` aus der
        ESOL-Datei und ein neuer Name in der E-Mail nicht dieselbe Nummer
        bekommen und so zwei Personen zu einer verschmelzen.
        """
        highest = 0
        for entry in self.shared_mappings.values():
            for match in re.finditer(r"_(\d+)\b", entry.pseudonym):
                highest = max(highest, int(match.group(1)))
        return highest

    def _claim_index(self, hit: NameHit) -> int:
        """Nummer aus einem bestehenden ESOL-Mapping uebernehmen, sonst neue vergeben."""
        surname = self._surname_key(hit.text)
        for orig, entry in self.shared_mappings.items():
            if self._surname_key(orig) == surname:
                match = re.search(r"_(\d+)\b", entry.pseudonym)
                if match:
                    return int(match.group(1))
        self._person_counter += 1
        return self._person_counter

    def _ensure_person_registered(self, hit: NameHit) -> None:
        tokens = [t for t in re.split(r"\s+", hit.text.strip()) if t]
        raw_surname = self._surname_key(hit.text)
        key = (hit.role, raw_surname)

        if key in self._person_data:
            if hit.salutation and not self._person_data[key].get("salutation_known"):
                self._person_data[key]["gender"] = hit.salutation
                self._person_data[key]["salutation_known"] = True
                self._person_gender[key] = hit.salutation
            return

        gender = hit.salutation
        salutation_known = bool(gender)
        if not gender and len(tokens) >= 2:
            first_lower = tokens[0].lower()
            if first_lower in _FEMALE_FIRST_NAMES_SET:
                gender = "f"
            elif first_lower in _MALE_FIRST_NAMES_SET:
                gender = "m"
        if not gender:
            gender = "m"

        idx = self._claim_index(hit)
        self._person_index[key] = idx
        self._person_gender[key] = gender

        # Preferred or pool surname
        if raw_surname in _PREFERRED_SURNAMES and _PREFERRED_SURNAMES[raw_surname] not in self._used_surnames:
            surname = _PREFERRED_SURNAMES[raw_surname]
        else:
            surname = ""
            while self._surname_pool_idx < len(_SURNAMES_POOL):
                cand = _SURNAMES_POOL[self._surname_pool_idx]
                self._surname_pool_idx += 1
                if cand not in self._used_surnames and cand.casefold() != raw_surname:
                    surname = cand
                    break
            if not surname:
                surname = f"Muster_{idx}"

        self._used_surnames.add(surname)

        # Preferred or pool first name
        first_lower = tokens[0].lower() if len(tokens) >= 2 else ""
        if first_lower in _PREFERRED_FIRST_NAMES:
            first_name = _PREFERRED_FIRST_NAMES[first_lower]
        elif gender == "f":
            first_name = ""
            while self._female_first_pool_idx < len(_FEMALE_FIRST_NAMES_POOL):
                cand = _FEMALE_FIRST_NAMES_POOL[self._female_first_pool_idx]
                self._female_first_pool_idx += 1
                if cand not in self._used_female_first:
                    first_name = cand
                    break
            if not first_name:
                first_name = _FEMALE_FIRST_NAMES_POOL[idx % len(_FEMALE_FIRST_NAMES_POOL)]
            self._used_female_first.add(first_name)
        else:
            first_name = ""
            while self._male_first_pool_idx < len(_MALE_FIRST_NAMES_POOL):
                cand = _MALE_FIRST_NAMES_POOL[self._male_first_pool_idx]
                self._male_first_pool_idx += 1
                if cand not in self._used_male_first:
                    first_name = cand
                    break
            if not first_name:
                first_name = _MALE_FIRST_NAMES_POOL[idx % len(_MALE_FIRST_NAMES_POOL)]
            self._used_male_first.add(first_name)

        self._person_data[key] = {
            "gender": gender,
            "salutation_known": salutation_known,
            "first_name": first_name,
            "surname": surname,
            "idx": idx,
        }

    def _pseudonym_for(self, hit: NameHit) -> str:
        self._ensure_person_registered(hit)
        key = (hit.role, self._surname_key(hit.text))
        person = self._person_data[key]
        idx = person["idx"]
        tokens = [t for t in re.split(r"\s+", hit.text.strip()) if t]

        if hit.role is NameRole.PATIENT:
            if len(tokens) >= 2:
                return f"Max_{idx} Mustermann_{idx}"
            return f"Mustermann_{idx}"

        if hit.role is NameRole.DOCTOR:
            return f"Musterarzt_{idx}"

        # Contact person: generate natural name in the exact same style as original
        fake_surname = person["surname"]
        fake_first = person["first_name"]

        # Check for particle (e.g. "von Kettenburg")
        if len(tokens) >= 2 and tokens[0].lower() in ("von", "vom", "van", "zu", "zur", "de", "del", "di"):
            particle = tokens[0]
            return f"{particle} {fake_surname}"

        # Check for hyphenated surname without first name (e.g. "Meier-Schulz")
        if "-" in self._surname_key(hit.text) and len(tokens) == 1:
            second_cand = "Bauer" if fake_surname != "Bauer" else "Weber"
            return f"{fake_surname}-{second_cand}"

        if len(tokens) == 1:
            # Just surname: "Müller" -> "Schmidt", "Ulrichs" -> "Schuhmann", "Meier" -> "Schmidt"
            return fake_surname

        # Full name: "Simone Sonnenschein" -> "Ulla Winkler", "Alexander Testperson" -> "Michael Schuhmann"
        return f"{fake_first} {fake_surname}"

    # ------------------------------------------------------------------
    # Hilfsfunktionen
    # ------------------------------------------------------------------

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

    def _add_suspicion(self, suspicion: Suspicion, section: str) -> None:
        if section:
            suspicion = Suspicion(
                text=suspicion.text,
                line=suspicion.line,
                reason=f"{suspicion.reason} ({section})",
            )
        if not any(s.text == suspicion.text and s.reason == suspicion.reason for s in self.suspicions):
            self.suspicions.append(suspicion)

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
