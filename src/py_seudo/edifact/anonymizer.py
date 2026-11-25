"""EDIFACT ESOL Anonymizer for German Healthcare Billing (§ 302 SGB V)."""
from __future__ import annotations

import re
from datetime import date
from typing import Dict, List, Optional, Set, Tuple

from py_seudo.edifact.tokenizer import EdifactParser, EdifactSegment, serialize_segments
from py_seudo.models import MappingEntry, ReplacementCategory, Suspicion
from py_seudo.validators import (
    generate_mirrored_ik,
    generate_mirrored_kvnr,
    mirror_invoice_defect,
    validate_ik,
    validate_kvnr,
)


class EsolAnonymizer:
    """Anonymizes ESOL / EDIFACT billing files while maintaining syntactic validity

    and technical error-diagnostic data (Kassen-IK, diagnoses, position numbers).
    """

    def __init__(
        self,
        raw_edifact: str,
        specified_practice_ik: Optional[str] = None,
        known_defects: Optional[Dict[str, Dict[str, str]]] = None,
    ):
        self.raw_edifact = raw_edifact
        self.specified_practice_ik = specified_practice_ik
        self.known_defects = dict(known_defects or {})
        self.parser = EdifactParser(raw_edifact)
        self.segments = self.parser.parse_segments()

        # State tracking
        self.practice_iks: Set[str] = set()
        self.kassen_iks: Set[str] = set()
        self.detected_entities: Dict[str, MappingEntry] = {}
        self.suspicions: List[Suspicion] = []

        # Counters for generating consistent pseudonyms
        self._patient_counter = 0
        self._doctor_counter = 0
        self._practice_counter = 0
        self._invoice_counter = 0
        self._recipe_counter = 0
        self._lanr_counter = 0
        self._bsnr_counter = 0
        self._other_counter = 0

        # Eine Nummer pro Patient: KVNR, Name, Adresse leiten sich daraus ab,
        # damit derselbe Patient ueberall dieselben Pseudonyme bekommt.
        self._patient_ids: Dict[str, int] = {}
        self._patient_seq = 0
        self._pending_kvnr: Optional[str] = None  # INV-KVNR fuer das folgende NAD (SLLA)

        # Bezugsdatum der Datei (UNB) -- trennt Geburts- von Leistungsdaten.
        self._reference_date: Optional[date] = None

        # Pre-pass to discover practice and kassen IKs
        self._discover_institutions()

    def _discover_institutions(self) -> None:
        """Scan segments to reliably distinguish Practice-IK from Krankenkassen-IK."""
        if self.specified_practice_ik:
            self.practice_iks.add(self.specified_practice_ik.strip())

        for idx, seg in enumerate(self.segments):
            tag = seg.tag

            # UNB segment: UNB+UNOC:3+SenderIK:Qual+ReceiverIK:Qual+...
            if tag == "UNB":
                sender_ik = seg.get_element(1, 0).strip()
                receiver_ik = seg.get_element(2, 0).strip()
                self._reference_date = self._parse_date(seg.get_element(3, 0).strip())
                if sender_ik and re.match(r"^[A-Za-z0-9]{6,14}$", sender_ik):
                    if not self.specified_practice_ik:
                        self.practice_iks.add(sender_ik)
                if receiver_ik and re.match(r"^[A-Za-z0-9]{6,14}$", receiver_ik):
                    self.kassen_iks.add(receiver_ik)
                    is_val, err_code, exp_cd = validate_ik(receiver_ik)
                    if not is_val:
                        self.suspicions.append(
                            Suspicion(
                                text=receiver_ik,
                                line=idx + 1,
                                reason=f"Kostenträger-IK (Empfänger UNB) hat Prüfziffern-/Formatfehler: {err_code}",
                            )
                        )

            # NAD segment
            elif tag == "NAD":
                qual = seg.get_element(0, 0).strip()
                ik_or_id = seg.get_element(1, 0).strip()

                if qual in ("FPR", "LE", "LBO"):
                    if ik_or_id and re.match(r"^[A-Za-z0-9]{6,14}$", ik_or_id):
                        self.practice_iks.add(ik_or_id)

                elif qual in ("KTR", "KK"):
                    if ik_or_id and re.match(r"^[A-Za-z0-9]{6,14}$", ik_or_id):
                        self.kassen_iks.add(ik_or_id)
                        is_val, err_code, exp_cd = validate_ik(ik_or_id)
                        if not is_val:
                            self.suspicions.append(
                                Suspicion(
                                    text=ik_or_id,
                                    line=idx + 1,
                                    reason=f"Kostenträger-IK (NAD+KTR) hat Prüfziffern-/Formatfehler: {err_code}",
                                )
                            )

            # FKT segment
            elif tag == "FKT":
                # Layout 1: FKT+01+IK_LE+IK_KTR...
                # Layout 2: FKT+01++IK_LE+IK_KTR+IK_KTR+IK_LE (SLLA/SLGA:21)
                ik_pos1 = seg.get_element(1, 0).strip()
                ik_pos2 = seg.get_element(2, 0).strip()
                ik_pos3 = seg.get_element(3, 0).strip()

                if ik_pos1 and re.match(r"^[A-Za-z0-9]{6,14}$", ik_pos1):
                    self.practice_iks.add(ik_pos1)
                    if ik_pos2 and re.match(r"^[A-Za-z0-9]{6,14}$", ik_pos2):
                        self.kassen_iks.add(ik_pos2)
                elif not ik_pos1 and ik_pos2 and re.match(r"^[A-Za-z0-9]{6,14}$", ik_pos2):
                    self.practice_iks.add(ik_pos2)
                    # Layout 2: FKT+01++IK_LE+IK_KTR+IK_KTR+IK_LE -- beide
                    # Kostentraeger-Positionen auswerten.
                    for ik_ktr in (ik_pos3, seg.get_element(4, 0).strip()):
                        if ik_ktr and re.match(r"^[A-Za-z0-9]{6,14}$", ik_ktr):
                            self.kassen_iks.add(ik_ktr)

        for p_ik in self.practice_iks:
            if p_ik in self.kassen_iks:
                self.kassen_iks.remove(p_ik)

    def _get_or_create_mapping(
        self,
        original: str,
        category: ReplacementCategory,
        description: str = "",
        force_error: Optional[str] = None,
        diagnostic_override: str = "",
        prefix_default: str = "RE",
        counter: Optional[int] = None,
    ) -> str:
        """Retrieve existing pseudonym or generate a new (possibly defect-mirrored) one."""
        if not original:
            return ""

        orig_clean = original.strip()
        if orig_clean in self.detected_entities:
            entry = self.detected_entities[orig_clean]
            entry.count += 1
            return entry.pseudonym

        pseudonym, is_mirrored, note = self._generate_pseudonym(
            orig_clean,
            category,
            force_error=force_error,
            diagnostic_override=diagnostic_override,
            prefix_default=prefix_default,
            counter=counter,
        )
        desc = description
        if is_mirrored and note:
            desc = f"{description} [{note}]" if description else note

        self.detected_entities[orig_clean] = MappingEntry(
            original=orig_clean,
            pseudonym=pseudonym,
            category=category,
            count=1,
            description=desc,
            error_mirrored=is_mirrored,
            diagnostic_note=note,
        )
        return pseudonym

    def _generate_pseudonym(
        self,
        orig: str,
        category: ReplacementCategory,
        force_error: Optional[str] = None,
        diagnostic_override: str = "",
        prefix_default: str = "RE",
        counter: Optional[int] = None,
    ) -> Tuple[str, bool, str]:
        """Generate syntactically compliant or defect-mirrored dummy values."""
        defect_info = self.known_defects.get(orig, {})
        f_err = force_error or defect_info.get("error_type")
        diag_ovr = diagnostic_override or defect_info.get("diagnostic_note", "")

        if category == ReplacementCategory.PRACTICE_IK:
            self._practice_counter += 1
            return generate_mirrored_ik(
                orig,
                self._practice_counter,
                force_error=f_err,
                diagnostic_override=diag_ovr,
            )

        elif category == ReplacementCategory.KVNR:
            if counter is None:
                counter = self._new_patient_index()
            return generate_mirrored_kvnr(
                orig,
                counter,
                force_error=f_err,
                diagnostic_override=diag_ovr,
            )

        elif category == ReplacementCategory.INVOICE_NUMBER:
            if prefix_default == "BELEG" or orig.startswith("BELEG"):
                self._recipe_counter += 1
                ctr = self._recipe_counter
            else:
                self._invoice_counter += 1
                ctr = self._invoice_counter

            return mirror_invoice_defect(
                orig,
                ctr,
                prefix_default=prefix_default,
                force_error=f_err,
                diagnostic_override=diag_ovr,
            )

        elif category == ReplacementCategory.PATIENT_NAME:
            self._patient_counter = max(self._patient_counter, 1)
            num = self._patient_counter
            if " " in orig or "," in orig:
                return f"Mustermann_{num}, Max_{num}", False, ""
            return f"Patient_{num}", False, ""

        elif category == ReplacementCategory.BIRTHDATE:
            if re.match(r"^\d{8}$", orig):
                year = orig[:4]
                return f"{year}0615", False, ""
            elif re.match(r"^\d{2}\.\d{2}\.\d{4}$", orig):
                year = orig[-4:]
                return f"15.06.{year}", False, ""
            return orig, False, ""

        elif category == ReplacementCategory.DOCTOR_NAME:
            self._doctor_counter += 1
            return f"Dr. med. Musterarzt_{self._doctor_counter}", False, ""

        elif category == ReplacementCategory.DOCTOR_LANR:
            self._lanr_counter += 1
            return self._shaped_id(orig, "888", self._lanr_counter, "LANR")

        elif category == ReplacementCategory.DOCTOR_BSNR:
            self._bsnr_counter += 1
            return self._shaped_id(orig, "777", self._bsnr_counter, "BSNR")

        elif category == ReplacementCategory.ADDRESS:
            return "Musterstrasse 42", False, ""

        return f"ANON_{orig}", False, ""

    # ------------------------------------------------------------------
    # Hilfen
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_date(value: str) -> Optional[date]:
        """CCYYMMDD oder YYMMDD (UNB) -> date; sonst None."""
        try:
            if re.fullmatch(r"\d{8}", value):
                return date(int(value[:4]), int(value[4:6]), int(value[6:]))
            if re.fullmatch(r"\d{6}", value):
                return date(2000 + int(value[:2]), int(value[2:4]), int(value[4:]))
        except ValueError:
            return None
        return None

    def _looks_like_birthdate(self, value: str) -> bool:
        """Liegt das Datum deutlich vor dem Dateidatum?

        Leistungs- und Verordnungsdaten liegen hoechstens wenige Monate vor der
        Abrechnung, Geburtsdaten (fast immer) Jahre. Zwei Jahre Abstand trennen
        beides zuverlaessig, ohne Leistungsdaten zu zerstoeren.
        """
        d = self._parse_date(value)
        if d is None:
            return False
        ref = self._reference_date or date.today()
        try:
            cutoff = ref.replace(year=ref.year - 2)
        except ValueError:  # 29.02.
            cutoff = ref.replace(year=ref.year - 2, day=28)
        return d < cutoff

    @staticmethod
    def _shaped_id(orig: str, prefix: str, counter: int, label: str) -> Tuple[str, bool, str]:
        """Pseudonym fuer LANR/BSNR, das Laenge und Zeichenart des Originals spiegelt.

        Abweichende Laengen oder Zeichen sind genau die Fehler, die man an
        Entwickler weitergeben will -- sie sollen im Pseudonym sichtbar bleiben.
        """
        expected = 9
        source = f"{prefix}{counter:06d}"
        if orig.isdigit() and len(orig) == expected:
            return source, False, ""
        if orig.isdigit():
            body = f"{prefix}{counter:0{max(len(orig) - len(prefix), 1)}d}"
            pseudo = body[-len(orig):] if len(body) > len(orig) else body
            return pseudo, True, f"{label} mit {len(orig)} statt {expected} Stellen – Formatfehler gespiegelt"
        digits = iter(source * (len(orig) // len(source) + 1))
        pseudo = "".join(
            "X" if ch.isalpha() else next(digits) if ch.isdigit() else ch for ch in orig
        )
        return pseudo, True, f"{label} mit unzulässigen Zeichen – Format gespiegelt"

    def _new_patient_index(self) -> int:
        self._patient_seq += 1
        return self._patient_seq

    def _patient_index(self, *keys: Optional[str]) -> int:
        """Stabile Nummer pro Patient (ueber KVNR oder Name)."""
        idx = next((self._patient_ids[k] for k in keys if k and k in self._patient_ids), None)
        if idx is None:
            idx = self._new_patient_index()
        for k in keys:
            if k:
                self._patient_ids.setdefault(k, idx)
        return idx

    def _set_mapping(
        self, original: str, pseudonym: str, category: ReplacementCategory, description: str
    ) -> str:
        """Festes Pseudonym registrieren -- oder das bereits vergebene wiederverwenden.

        Frueher wurde an vielen Stellen ``detected_entities[...] = ...`` direkt
        geschrieben. Derselbe Patient bekam dadurch bei jedem Vorkommen ein neues
        Pseudonym, und die Mapping-Tabelle kannte nur das letzte.
        """
        orig = (original or "").strip()
        if not orig:
            return original
        entry = self.detected_entities.get(orig)
        if entry is not None:
            entry.count += 1
            return entry.pseudonym
        # pseudonym == orig kommt nur noch vor, wenn der Wert bereits ein
        # Platzhalter von py-seudo ist (zweiter Lauf). Dynamische Werte wie PLZ
        # nutzen 00xxx und koennen keiner echten Angabe mehr gleichen.
        self.detected_entities[orig] = MappingEntry(
            original=orig, pseudonym=pseudonym, category=category, count=1, description=description
        )
        return pseudonym

    def _register_alias(
        self, original: str, pseudonym: str, category: ReplacementCategory, description: str
    ) -> None:
        """Schreibweise fuer die E-Mail-Seite merken (z. B. 'Vorname Nachname')."""
        orig = original.strip()
        if orig and orig not in self.detected_entities:
            self.detected_entities[orig] = MappingEntry(
                original=orig, pseudonym=pseudonym, category=category, count=0, description=description
            )

    def _id(self, value: str, category: ReplacementCategory, description: str, **kw) -> str:
        return self._get_or_create_mapping(value.strip(), category, description, **kw) if value.strip() else value

    def _patient_fields(
        self, seg: EdifactSegment, indices: List[int], idx: int, source: str
    ) -> None:
        """Name, Strasse, Ort, PLZ eines Patienten aus der Patientennummer ableiten."""
        if not indices:
            return
        surname_ps, forename_ps = f"Mustermann_{idx}", f"Max_{idx}"
        nachname = seg.get_element(indices[0], 0)
        surname_ps = self._set_mapping(nachname, surname_ps, ReplacementCategory.PATIENT_NAME, f"Patient Nachname ({source})")
        seg.set_element(indices[0], surname_ps, 0)

        if len(indices) > 1:
            vorname = seg.get_element(indices[1], 0)
            forename_ps = self._set_mapping(vorname, forename_ps, ReplacementCategory.PATIENT_NAME, f"Patient Vorname ({source})")
            seg.set_element(indices[1], forename_ps, 0)
            self._register_alias(f"{vorname.strip()} {nachname.strip()}", f"{forename_ps} {surname_ps}",
                                 ReplacementCategory.PATIENT_NAME, "Patient Vollname")
            self._register_alias(f"{nachname.strip()}, {vorname.strip()}", f"{surname_ps}, {forename_ps}",
                                 ReplacementCategory.PATIENT_NAME, "Patient Vollname (Nachname, Vorname)")

        if len(indices) > 2:
            street = seg.get_element(indices[2], 0)
            seg.set_element(indices[2], self._set_mapping(street, f"Musterweg {10 + idx}", ReplacementCategory.ADDRESS, "Patient Strasse"), 0)
        if len(indices) > 3:
            city = seg.get_element(indices[3], 0)
            seg.set_element(indices[3], self._set_mapping(city, "Musterort", ReplacementCategory.ADDRESS, "Patient Ort"), 0)
        for i in indices[4:]:
            val = seg.get_element(i, 0)
            if re.fullmatch(r"\d{5}", val.strip()):
                # 00xxx ist in Deutschland nicht vergeben -> kann nie einer echten PLZ gleichen.
                seg.set_element(i, self._set_mapping(val, f"{idx:05d}", ReplacementCategory.ADDRESS, "Patient PLZ"), 0)

    def _register_birthdate(self, value: str, description: str) -> str:
        pseudo = self._get_or_create_mapping(value, ReplacementCategory.BIRTHDATE, description)
        de_date = f"{value[6:8]}.{value[4:6]}.{value[:4]}"
        self._register_alias(de_date, f"15.06.{value[:4]}", ReplacementCategory.BIRTHDATE, "Geburtsdatum (DD.MM.YYYY)")
        return pseudo

    def _generic_pseudonym(self, value: str) -> str:
        """Ersatzwert fuer ein Feld, dessen Bedeutung unbekannt ist."""
        v = value.strip()
        if v in self.detected_entities:
            entry = self.detected_entities[v]
            entry.count += 1
            return entry.pseudonym
        if re.fullmatch(r"[A-Z]\d{9}", v):
            return self._get_or_create_mapping(v, ReplacementCategory.KVNR, "Versichertennummer (unbekanntes Layout)")
        if re.fullmatch(r"\d{8}", v) and self._parse_date(v):
            return self._register_birthdate(v, "Datum (unbekanntes Layout)")
        if re.fullmatch(r"\d{5}", v):
            return self._set_mapping(v, "00999", ReplacementCategory.ADDRESS, "PLZ (unbekanntes Layout)")
        if "@" in v:
            return self._set_mapping(v, "kontakt@beispiel.invalid", ReplacementCategory.CONTACT_INFO, "E-Mail (unbekanntes Layout)")
        if v.isdigit():
            self._other_counter += 1
            return self._set_mapping(v, self._shaped_id(v, "555", self._other_counter, "Nummer")[0],
                                     ReplacementCategory.OTHER, "Kennnummer (unbekanntes Layout)")
        self._other_counter += 1
        return self._set_mapping(v, f"Angabe_{self._other_counter}", ReplacementCategory.OTHER, "Feld (unbekanntes Layout)")

    def _anonymize_unknown_nad(self, seg: EdifactSegment, line: int) -> None:
        """NAD, dessen Layout nicht erkannt wurde: alles ersetzen und melden.

        Frueher lief ein solches Segment unveraendert durch. Jetzt wird jedes
        Feld ausser Qualifier, Kassen-IK und Laenderkennzeichen ersetzt -- im
        Zweifel geht damit ein Diagnosewert verloren, aber kein Personenbezug raus.
        """
        first = seg.get_element(0, 0).strip()
        start = 1 if re.fullmatch(r"[A-Z0-9]{1,3}", first) else 0
        for i in range(start, len(seg.elements)):
            for c in range(len(seg.elements[i])):
                val = seg.get_element(i, c)
                if not val.strip() or val.strip() in self.kassen_iks:
                    continue
                if i == len(seg.elements) - 1 and re.fullmatch(r"[A-Z]{2}", val.strip()):
                    continue  # Laenderkennzeichen
                seg.set_element(i, self._generic_pseudonym(val), c)
        marker = f"NAD+{seg.get_element(0, 0)}"
        self.suspicions.append(
            Suspicion(
                text=marker,
                line=line,
                reason="Unbekanntes NAD-Layout – alle Felder vorsorglich ersetzt, bitte prüfen",
            )
        )

    _PHONE_QUALIFIERS = {"TE", "FX", "MO", "AL", "AH", "AJ", "TL"}

    def _anonymize_com(self, seg: EdifactSegment) -> None:
        """COM: Telefon, Fax, E-Mail der Praxis -- immer ersetzen."""
        for i in range(len(seg.elements)):
            value = seg.get_element(i, 0)
            if not value.strip():
                continue
            qual = seg.get_element(i, 1).strip().upper()
            if qual == "EM" or "@" in value:
                pseudo = self._set_mapping(value, "kontakt@beispiel.invalid", ReplacementCategory.CONTACT_INFO, "E-Mail (COM)")
            elif qual in self._PHONE_QUALIFIERS or re.search(r"\d", value):
                pseudo = self._set_mapping(value, "+49 000 0000000", ReplacementCategory.CONTACT_INFO, "Telefon/Fax (COM)")
            else:
                pseudo = self._generic_pseudonym(value)
            seg.set_element(i, pseudo, 0)

    def _anonymize_nam(self, seg: EdifactSegment) -> None:
        """NAM (Praxisangaben in SLGA): Name, Anschrift, Kontakt -- alle Felder."""
        for i in range(len(seg.elements)):
            value = seg.get_element(i, 0)
            v = value.strip()
            if not v:
                continue
            if i == 0:
                pseudo = self._set_mapping(v, "Praxis fuer Therapie Musterpraxis", ReplacementCategory.PRACTICE_NAME, "Praxisname (NAM)")
            elif "@" in v:
                pseudo = self._set_mapping(v, "kontakt@beispiel.invalid", ReplacementCategory.CONTACT_INFO, "Praxis E-Mail / Kontakt (NAM)")
            elif re.fullmatch(r"\d{5}\s+\S.*", v):
                pseudo = self._set_mapping(v, "00999 Musterstadt", ReplacementCategory.ADDRESS, "Praxis PLZ und Ort (NAM)")
            elif re.search(r"\d", v) and re.search(r"[A-Za-zÄÖÜäöüß]", v):
                pseudo = self._set_mapping(v, "Musterpraxisweg 1", ReplacementCategory.ADDRESS, "Praxis Strasse (NAM)")
            elif re.fullmatch(r"[\d\s/()+-]{6,}", v):
                pseudo = self._set_mapping(v, "+49 000 0000000", ReplacementCategory.CONTACT_INFO, "Praxis Telefon (NAM)")
            else:
                pseudo = self._generic_pseudonym(v)
            seg.set_element(i, pseudo, 0)

    def _anonymize_free_text(self, seg: EdifactSegment, line: int) -> None:
        """FTX: Freitext durch die Namens-/Kontakterkennung der E-Mail schicken.

        Freitext ist die Stelle, an der in Fehlerdateien Klarnamen auftauchen.
        Bekannte Werte aus der Datei, Namen mit Kontext ("Patientin ..."),
        Telefonnummern, E-Mail-Adressen und KVNR werden ersetzt. Weil Namen
        ohne Kontext nicht sicher erkennbar sind, wird jedes FTX zusaetzlich
        zur Pruefung gemeldet.
        """
        from py_seudo.email.anonymizer import EmailAnonymizer  # lokal: vermeidet Zyklus

        for i in range(len(seg.elements)):
            for c in range(len(seg.elements[i])):
                text = seg.get_element(i, c)
                if not re.search(r"[A-Za-zÄÖÜäöüß]{3,}", text) or re.fullmatch(r"[A-Z0-9]{1,3}", text.strip()):
                    continue  # Qualifier / Code
                anon = EmailAnonymizer(
                    raw_email=text,
                    shared_mappings=self.detected_entities,
                    practice_iks=list(self.practice_iks),
                    kassen_iks=list(self.kassen_iks),
                )
                cleaned = anon._apply_replacements(text, section=f"FTX Zeile {line}")
                for m in anon.email_mappings:
                    if m.original not in self.detected_entities:
                        self.detected_entities[m.original] = m
                for sus in anon.suspicions:
                    self.suspicions.append(Suspicion(text=sus.text, line=line, reason=sus.reason))
                seg.set_element(i, cleaned, c)
                plain = re.split(r"[+:'?*]", cleaned, maxsplit=1)[0].strip()
                marker = plain[:60] if len(plain) >= 3 else seg.tag
                self.suspicions.append(
                    Suspicion(text=marker, line=line, reason="Freitext (FTX) – bitte auf Namen prüfen")
                )

    # ------------------------------------------------------------------
    # Hauptlauf
    # ------------------------------------------------------------------

    _BIRTH_QUALIFIERS = ("102", "329", "032")

    def anonymize(self) -> Tuple[str, List[MappingEntry]]:
        """Run anonymization over all parsed segments."""
        last_patient_context = False
        free_text: List[Tuple[EdifactSegment, int]] = []

        for line, seg in enumerate(self.segments, start=1):
            tag = seg.tag

            # 1. UNB Segment
            if tag == "UNB":
                # Achtung: _discover_institutions() normalisiert mit strip(), hier muss
                # genauso normalisiert werden -- sonst bleibt " 123456789 " im Klartext
                # stehen, waehrend dieselbe IK in REC/FKT ersetzt wird.
                sender_ik = seg.get_element(1, 0).strip()
                if sender_ik in self.practice_iks:
                    pseudo_ik = self._get_or_create_mapping(
                        sender_ik, ReplacementCategory.PRACTICE_IK, "Praxis-IK (UNB Absender)"
                    )
                    seg.set_element(1, pseudo_ik, 0)

            # 2. FKT Segment
            elif tag == "FKT":
                for elem_idx in range(len(seg.elements)):
                    val = seg.get_element(elem_idx, 0).strip()
                    if val in self.practice_iks:
                        pseudo_ik = self._get_or_create_mapping(
                            val, ReplacementCategory.PRACTICE_IK, "Praxis-IK (FKT)"
                        )
                        seg.set_element(elem_idx, pseudo_ik, 0)

            # 2b. NAM Segment (Praxisname / Anschrift / Kontakt in SLGA)
            elif tag == "NAM":
                self._anonymize_nam(seg)

            # 2c. COM Segment (Telefon / Fax / E-Mail)
            elif tag == "COM":
                self._anonymize_com(seg)

            # 2d. FTX Segment -- erst am Ende, wenn alle Namen der Datei bekannt sind
            elif tag == "FTX":
                free_text.append((seg, line))

            # 3. REC Segment
            elif tag == "REC":
                ik_le = seg.get_element(0, 0)
                if ik_le:
                    pseudo_ik = self._get_or_create_mapping(
                        ik_le, ReplacementCategory.PRACTICE_IK, "Praxis-IK (REC)"
                    )
                    seg.set_element(0, pseudo_ik, 0)
                rechnr = seg.get_element(1, 0)
                if rechnr:
                    pseudo_rec = self._get_or_create_mapping(
                        rechnr, ReplacementCategory.INVOICE_NUMBER, "Rechnungsnummer (REC)"
                    )
                    seg.set_element(1, pseudo_rec, 0)

            # 4. INV Segment
            elif tag == "INV":
                inv_val = seg.get_element(0, 0).strip()
                if inv_val:
                    if re.match(r"^[A-Za-z]\d{7,10}$", inv_val):
                        idx = self._patient_index(inv_val)
                        pseudo_kvnr = self._get_or_create_mapping(
                            inv_val, ReplacementCategory.KVNR, "Versichertennummer (INV)", counter=idx
                        )
                        seg.set_element(0, pseudo_kvnr, 0)
                        self._pending_kvnr = inv_val
                    else:
                        pseudo_inv = self._get_or_create_mapping(
                            inv_val, ReplacementCategory.INVOICE_NUMBER, "Rechnungsnummer (INV)"
                        )
                        seg.set_element(0, pseudo_inv, 0)

            # 5. NAD Segment: Name and Address
            elif tag == "NAD":
                qual = seg.get_element(0, 0).strip()
                non_empty_indices = [
                    i for i in range(2, len(seg.elements)) if seg.get_element(i, 0).strip()
                ]

                # Practice: NAD+FPR
                if qual in ("FPR", "LE", "LBO"):
                    last_patient_context = False
                    ik = seg.get_element(1, 0)
                    if ik:
                        pseudo_ik = self._get_or_create_mapping(
                            ik, ReplacementCategory.PRACTICE_IK, "Praxis-IK (NAD)"
                        )
                        seg.set_element(1, pseudo_ik, 0)
                    fixed = [
                        ("Musterpraxis Sonnenschein", ReplacementCategory.PRACTICE_NAME, "Praxisname"),
                        ("Musterpraxisweg 1", ReplacementCategory.ADDRESS, "Praxis Strasse"),
                        ("Musterstadt", ReplacementCategory.ADDRESS, "Praxis Ort"),
                    ]
                    for idx_pos, (pseudo, cat, desc) in zip(non_empty_indices, fixed):
                        val = seg.get_element(idx_pos, 0)
                        seg.set_element(idx_pos, self._set_mapping(val, pseudo, cat, desc), 0)
                    for idx_pos in non_empty_indices[3:]:
                        val = seg.get_element(idx_pos, 0)
                        if re.fullmatch(r"\d{5}", val.strip()):
                            seg.set_element(idx_pos, self._set_mapping(val, "00999", ReplacementCategory.ADDRESS, "Praxis PLZ"), 0)

                # Patient: NAD+VP / NAD+IM / NAD+VN / NAD+PE
                elif qual in ("VP", "IM", "VN", "PE"):
                    last_patient_context = True
                    kvnr = seg.get_element(1, 0).strip()
                    name_key = None
                    if non_empty_indices:
                        nach = seg.get_element(non_empty_indices[0], 0).strip()
                        vor = seg.get_element(non_empty_indices[1], 0).strip() if len(non_empty_indices) > 1 else ""
                        name_key = f"name:{nach}|{vor}"
                    idx = self._patient_index(kvnr or None, name_key)
                    if kvnr:
                        seg.set_element(1, self._get_or_create_mapping(
                            kvnr, ReplacementCategory.KVNR, "Versichertennummer (KVNR)", counter=idx
                        ), 0)
                    self._patient_fields(seg, non_empty_indices, idx, "NAD")

                # Doctor: NAD+ARZ / NAD+BY
                elif qual in ("ARZ", "BY"):
                    last_patient_context = False
                    lanr = seg.get_element(1, 0)
                    if lanr.strip():
                        seg.set_element(1, self._id(lanr, ReplacementCategory.DOCTOR_LANR, "Arztnummer (LANR in NAD)"), 0)
                    if non_empty_indices:
                        name_idx = non_empty_indices[0]
                        doc_name = seg.get_element(name_idx, 0)
                        if doc_name.strip() not in self.detected_entities:
                            self._doctor_counter += 1
                        pseudo_doc = self._set_mapping(
                            doc_name, f"Dr. med. Musterarzt_{self._doctor_counter}",
                            ReplacementCategory.DOCTOR_NAME, "Arztname",
                        )
                        seg.set_element(name_idx, pseudo_doc, 0)
                        for extra in non_empty_indices[1:]:
                            seg.set_element(extra, self._generic_pseudonym(seg.get_element(extra, 0)), 0)

                # Kostenträger: NAD+KTR -> KEEP UNCHANGED!
                elif qual in ("KTR", "KK"):
                    last_patient_context = False

                else:
                    # SLLA:21 / § 302 Heilmittel without qualifier: NAD+Nachname+Vorname+Geburtsdatum
                    nachname = seg.get_element(0, 0).strip()
                    vorname = seg.get_element(1, 0).strip()
                    geburtsdatum = seg.get_element(2, 0).strip()

                    if nachname and vorname and re.match(r"^\d{8}$", geburtsdatum):
                        idx = self._patient_index(self._pending_kvnr, f"name:{nachname}|{vorname}")
                        self._pending_kvnr = None
                        self._patient_fields(seg, [0, 1], idx, "NAD")
                        seg.set_element(2, self._register_birthdate(geburtsdatum, "Geburtsdatum (CCYYMMDD)"), 0)
                        last_patient_context = True
                    else:
                        last_patient_context = False
                        self._anonymize_unknown_nad(seg, line)

            # 6. DTM Segment (Date)
            elif tag == "DTM":
                qual = seg.get_element(0, 0)
                date_val = seg.get_element(0, 1)
                if not date_val and len(seg.elements) > 1:
                    qual = seg.get_element(0, 0)
                    date_val = seg.get_element(1, 0)

                # Geburtsdatum nur ueber den Qualifier -- oder direkt nach einem
                # Patienten-NAD, wenn das Datum deutlich vor dem Dateidatum liegt.
                # Leistungsdaten (DTM+472 o. ae.) bleiben so erhalten.
                is_birth = qual in self._BIRTH_QUALIFIERS or (
                    last_patient_context and self._looks_like_birthdate(date_val)
                )
                if is_birth and date_val and re.match(r"^\d{8}$", date_val):
                    pseudo_date = self._register_birthdate(date_val, "Geburtsdatum (CCYYMMDD)")
                    if seg.get_element(0, 1):
                        seg.set_element(0, pseudo_date, 1)
                    else:
                        seg.set_element(1, pseudo_date, 0)
                last_patient_context = False

            # 7. BES Segment (Betriebsstätte / Arzt)
            elif tag == "BES":
                bsnr = seg.get_element(0, 0)
                if bsnr.strip():
                    seg.set_element(0, self._id(bsnr, ReplacementCategory.DOCTOR_BSNR, "Betriebsstättennummer (BSNR in BES)"), 0)
                lanr = seg.get_element(1, 0)
                if lanr.strip():
                    seg.set_element(1, self._id(lanr, ReplacementCategory.DOCTOR_LANR, "Arztnummer (LANR in BES)"), 0)

            # 7b. ZHE Segment (LANR und BSNR in SLLA:21)
            elif tag == "ZHE":
                lanr = seg.get_element(0, 0)
                if lanr.strip():
                    seg.set_element(0, self._id(lanr, ReplacementCategory.DOCTOR_LANR, "Arztnummer (LANR in ZHE)"), 0)
                bsnr = seg.get_element(1, 0)
                if bsnr.strip():
                    seg.set_element(1, self._id(bsnr, ReplacementCategory.DOCTOR_BSNR, "Betriebsstaettennummer (BSNR in ZHE)"), 0)

            # 8. EHE Segment (Rezept / Verordnungsnummer)
            elif tag == "EHE":
                belegnr = seg.get_element(0, 0)
                if belegnr and len(belegnr) >= 4:
                    pseudo_ehe = self._get_or_create_mapping(
                        belegnr,
                        ReplacementCategory.INVOICE_NUMBER,
                        "Verordnungs-/Belegnummer (EHE)",
                        prefix_default="BELEG",
                    )
                    seg.set_element(0, pseudo_ehe, 0)

        for seg, line in free_text:
            self._anonymize_free_text(seg, line)

        anonymized_text = serialize_segments(self.segments)
        return anonymized_text, [e for e in self.detected_entities.values()]
