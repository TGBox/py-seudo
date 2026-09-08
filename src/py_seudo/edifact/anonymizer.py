"""EDIFACT ESOL Anonymizer for German Healthcare Billing (§ 302 SGB V)."""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Set, Tuple

from py_seudo.edifact.tokenizer import EdifactParser, EdifactSegment, serialize_segments
from py_seudo.models import MappingEntry, ReplacementCategory


class EsolAnonymizer:
    """Anonymizes ESOL / EDIFACT billing files while maintaining syntactic validity

    and technical error-diagnostic data (Kassen-IK, diagnoses, position numbers).
    """

    def __init__(self, raw_edifact: str, specified_practice_ik: Optional[str] = None):
        self.raw_edifact = raw_edifact
        self.specified_practice_ik = specified_practice_ik
        self.parser = EdifactParser(raw_edifact)
        self.segments = self.parser.parse_segments()

        # State tracking
        self.practice_iks: Set[str] = set()
        self.kassen_iks: Set[str] = set()
        self.detected_entities: Dict[str, MappingEntry] = {}

        # Counters for generating consistent pseudonyms
        self._patient_counter = 0
        self._doctor_counter = 0
        self._practice_counter = 0
        self._invoice_counter = 0
        self._recipe_counter = 0

        # Pre-pass to discover practice and kassen IKs
        self._discover_institutions()

    def _discover_institutions(self) -> None:
        """Scan segments to reliably distinguish Practice-IK from Krankenkassen-IK."""
        if self.specified_practice_ik:
            self.practice_iks.add(self.specified_practice_ik.strip())

        for seg in self.segments:
            tag = seg.tag

            # UNB segment: UNB+UNOC:3+SenderIK:Qual+ReceiverIK:Qual+...
            if tag == "UNB":
                sender_ik = seg.get_element(1, 0).strip()
                receiver_ik = seg.get_element(2, 0).strip()
                if sender_ik and re.match(r"^\d{9}$", sender_ik):
                    if not self.specified_practice_ik:
                        self.practice_iks.add(sender_ik)
                if receiver_ik and re.match(r"^\d{9}$", receiver_ik):
                    self.kassen_iks.add(receiver_ik)

            # NAD segment
            elif tag == "NAD":
                qual = seg.get_element(0, 0).strip()
                ik_or_id = seg.get_element(1, 0).strip()

                if qual in ("FPR", "LE", "LBO"):
                    if ik_or_id and re.match(r"^\d{9}$", ik_or_id):
                        self.practice_iks.add(ik_or_id)

                elif qual in ("KTR", "KK"):
                    if ik_or_id and re.match(r"^\d{9}$", ik_or_id):
                        self.kassen_iks.add(ik_or_id)

            # FKT segment
            elif tag == "FKT":
                ik_le = seg.get_element(1, 0).strip()
                ik_ktr = seg.get_element(2, 0).strip()
                if ik_le and re.match(r"^\d{9}$", ik_le):
                    self.practice_iks.add(ik_le)
                if ik_ktr and re.match(r"^\d{9}$", ik_ktr):
                    self.kassen_iks.add(ik_ktr)

        for p_ik in self.practice_iks:
            if p_ik in self.kassen_iks:
                self.kassen_iks.remove(p_ik)

    def _get_or_create_mapping(
        self, original: str, category: ReplacementCategory, description: str = ""
    ) -> str:
        """Retrieve existing pseudonym or generate a new syntactically valid one."""
        if not original:
            return ""

        orig_clean = original.strip()
        if orig_clean in self.detected_entities:
            entry = self.detected_entities[orig_clean]
            entry.count += 1
            return entry.pseudonym

        pseudonym = self._generate_pseudonym(orig_clean, category)
        self.detected_entities[orig_clean] = MappingEntry(
            original=orig_clean,
            pseudonym=pseudonym,
            category=category,
            count=1,
            description=description,
        )
        return pseudonym

    def _generate_pseudonym(self, orig: str, category: ReplacementCategory) -> str:
        """Generate syntactically compliant dummy values."""
        if category == ReplacementCategory.PRACTICE_IK:
            self._practice_counter += 1
            return f"999{self._practice_counter:06d}"

        elif category == ReplacementCategory.KVNR:
            self._patient_counter += 1
            return f"X{self._patient_counter:09d}"

        elif category == ReplacementCategory.PATIENT_NAME:
            self._patient_counter = max(self._patient_counter, 1)
            num = self._patient_counter
            if " " in orig or "," in orig:
                return f"Mustermann_{num}, Max_{num}"
            return f"Patient_{num}"

        elif category == ReplacementCategory.BIRTHDATE:
            if re.match(r"^\d{8}$", orig):
                year = orig[:4]
                return f"{year}0615"
            elif re.match(r"^\d{2}\.\d{2}\.\d{4}$", orig):
                year = orig[-4:]
                return f"15.06.{year}"
            return orig

        elif category == ReplacementCategory.DOCTOR_NAME:
            self._doctor_counter += 1
            return f"Dr. med. Musterarzt_{self._doctor_counter}"

        elif category == ReplacementCategory.DOCTOR_LANR:
            self._doctor_counter = max(self._doctor_counter, 1)
            return f"888{self._doctor_counter:06d}"

        elif category == ReplacementCategory.DOCTOR_BSNR:
            self._doctor_counter = max(self._doctor_counter, 1)
            return f"777{self._doctor_counter:06d}"

        elif category == ReplacementCategory.INVOICE_NUMBER:
            self._invoice_counter += 1
            prefix_match = re.match(r"^([A-Za-z_-]+)", orig)
            prefix = prefix_match.group(1) if prefix_match else "RE"
            return f"{prefix}999{self._invoice_counter:04d}"

        elif category == ReplacementCategory.ADDRESS:
            return "Musterstrasse 42"

        return f"ANON_{orig}"

    def anonymize(self) -> Tuple[str, List[MappingEntry]]:
        """Run anonymization over all parsed segments."""
        last_patient_context = False

        for seg in self.segments:
            tag = seg.tag

            # 1. UNB Segment
            if tag == "UNB":
                sender_ik = seg.get_element(1, 0)
                if sender_ik in self.practice_iks:
                    pseudo_ik = self._get_or_create_mapping(
                        sender_ik, ReplacementCategory.PRACTICE_IK, "Praxis-IK (UNB Absender)"
                    )
                    seg.set_element(1, pseudo_ik, 0)

            # 2. FKT Segment
            elif tag == "FKT":
                ik_le = seg.get_element(1, 0)
                if ik_le:
                    pseudo_ik = self._get_or_create_mapping(
                        ik_le, ReplacementCategory.PRACTICE_IK, "Praxis-IK (FKT Leistungserbringer)"
                    )
                    seg.set_element(1, pseudo_ik, 0)
                ik_rs = seg.get_element(3, 0)
                if ik_rs and (ik_rs in self.practice_iks or ik_rs == ik_le):
                    pseudo_rs = self._get_or_create_mapping(
                        ik_rs, ReplacementCategory.PRACTICE_IK, "Praxis-IK (FKT Rechnungssteller)"
                    )
                    seg.set_element(3, pseudo_rs, 0)

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
                inv_nr = seg.get_element(0, 0)
                if inv_nr:
                    pseudo_inv = self._get_or_create_mapping(
                        inv_nr, ReplacementCategory.INVOICE_NUMBER, "Rechnungsnummer (INV)"
                    )
                    seg.set_element(0, pseudo_inv, 0)

            # 5. NAD Segment: Name and Address
            elif tag == "NAD":
                qual = seg.get_element(0, 0).strip()

                # Find all non-empty elements after qualifier and ID
                non_empty_indices = [
                    i for i in range(2, len(seg.elements)) if seg.get_element(i, 0).strip()
                ]

                # Practice: NAD+FPR
                if qual in ("FPR", "LE", "LBO"):
                    ik = seg.get_element(1, 0)
                    if ik:
                        pseudo_ik = self._get_or_create_mapping(
                            ik, ReplacementCategory.PRACTICE_IK, "Praxis-IK (NAD)"
                        )
                        seg.set_element(1, pseudo_ik, 0)

                    if non_empty_indices:
                        name_idx = non_empty_indices[0]
                        p_name = seg.get_element(name_idx, 0)
                        if p_name:
                            pseudo_name = "Musterpraxis Sonnenschein"
                            self.detected_entities[p_name] = MappingEntry(
                                original=p_name,
                                pseudonym=pseudo_name,
                                category=ReplacementCategory.PRACTICE_IK,
                                count=1,
                                description="Praxisname",
                            )
                            seg.set_element(name_idx, pseudo_name, 0)

                        if len(non_empty_indices) > 1:
                            street_idx = non_empty_indices[1]
                            p_street = seg.get_element(street_idx, 0)
                            seg.set_element(street_idx, "Musterpraxisweg 1", 0)
                            self.detected_entities[p_street] = MappingEntry(
                                original=p_street,
                                pseudonym="Musterpraxisweg 1",
                                category=ReplacementCategory.ADDRESS,
                                count=1,
                                description="Praxis Strasse",
                            )

                        if len(non_empty_indices) > 2:
                            city_idx = non_empty_indices[2]
                            p_city = seg.get_element(city_idx, 0)
                            seg.set_element(city_idx, "Musterstadt", 0)
                            self.detected_entities[p_city] = MappingEntry(
                                original=p_city,
                                pseudonym="Musterstadt",
                                category=ReplacementCategory.ADDRESS,
                                count=1,
                                description="Praxis Ort",
                            )

                        for idx in non_empty_indices[3:]:
                            val = seg.get_element(idx, 0)
                            if re.match(r"^\d{5}$", val):
                                seg.set_element(idx, "99999", 0)
                                self.detected_entities[val] = MappingEntry(
                                    original=val,
                                    pseudonym="99999",
                                    category=ReplacementCategory.ADDRESS,
                                    count=1,
                                    description="Praxis PLZ",
                                )

                # Patient: NAD+VP / NAD+IM / NAD+VN / NAD+PE
                elif qual in ("VP", "IM", "VN", "PE"):
                    last_patient_context = True
                    kvnr = seg.get_element(1, 0)
                    if kvnr:
                        pseudo_kvnr = self._get_or_create_mapping(
                            kvnr, ReplacementCategory.KVNR, "Versichertennummer (KVNR)"
                        )
                        seg.set_element(1, pseudo_kvnr, 0)

                    if non_empty_indices:
                        self._patient_counter += 1
                        p_idx = self._patient_counter

                        # Surname
                        surname_idx = non_empty_indices[0]
                        nachname = seg.get_element(surname_idx, 0)
                        p_surname = f"Mustermann_{p_idx}"
                        self.detected_entities[nachname] = MappingEntry(
                            original=nachname,
                            pseudonym=p_surname,
                            category=ReplacementCategory.PATIENT_NAME,
                            count=1,
                            description="Patient Nachname",
                        )
                        seg.set_element(surname_idx, p_surname, 0)

                        # Forename (if present)
                        p_forename = f"Max_{p_idx}"
                        if len(non_empty_indices) > 1:
                            forename_idx = non_empty_indices[1]
                            vorname = seg.get_element(forename_idx, 0)
                            self.detected_entities[vorname] = MappingEntry(
                                original=vorname,
                                pseudonym=p_forename,
                                category=ReplacementCategory.PATIENT_NAME,
                                count=1,
                                description="Patient Vorname",
                            )
                            seg.set_element(forename_idx, p_forename, 0)

                            # Combined full names
                            full_1 = f"{vorname} {nachname}"
                            full_2 = f"{nachname}, {vorname}"
                            self.detected_entities[full_1] = MappingEntry(
                                original=full_1,
                                pseudonym=f"{p_forename} {p_surname}",
                                category=ReplacementCategory.PATIENT_NAME,
                                count=1,
                                description="Patient Vollname",
                            )
                            self.detected_entities[full_2] = MappingEntry(
                                original=full_2,
                                pseudonym=f"{p_surname}, {p_forename}",
                                category=ReplacementCategory.PATIENT_NAME,
                                count=1,
                                description="Patient Vollname (Nachname, Vorname)",
                            )

                        # Street
                        if len(non_empty_indices) > 2:
                            street_idx = non_empty_indices[2]
                            street = seg.get_element(street_idx, 0)
                            p_street = "Musterweg 12"
                            seg.set_element(street_idx, p_street, 0)
                            self.detected_entities[street] = MappingEntry(
                                original=street,
                                pseudonym=p_street,
                                category=ReplacementCategory.ADDRESS,
                                count=1,
                                description="Patient Strasse",
                            )

                        # City
                        if len(non_empty_indices) > 3:
                            city_idx = non_empty_indices[3]
                            city = seg.get_element(city_idx, 0)
                            p_city = "Musterort"
                            seg.set_element(city_idx, p_city, 0)
                            self.detected_entities[city] = MappingEntry(
                                original=city,
                                pseudonym=p_city,
                                category=ReplacementCategory.ADDRESS,
                                count=1,
                                description="Patient Ort",
                            )

                        # Postal code
                        for idx in non_empty_indices[4:]:
                            val = seg.get_element(idx, 0)
                            if re.match(r"^\d{5}$", val):
                                seg.set_element(idx, "12345", 0)
                                self.detected_entities[val] = MappingEntry(
                                    original=val,
                                    pseudonym="12345",
                                    category=ReplacementCategory.ADDRESS,
                                    count=1,
                                    description="Patient PLZ",
                                )

                # Doctor: NAD+ARZ / NAD+BY
                elif qual in ("ARZ", "BY"):
                    lanr = seg.get_element(1, 0)
                    if lanr and re.match(r"^\d{9}$", lanr):
                        pseudo_lanr = self._get_or_create_mapping(
                            lanr, ReplacementCategory.DOCTOR_LANR, "Arztnummer (LANR in NAD)"
                        )
                        seg.set_element(1, pseudo_lanr, 0)

                    if non_empty_indices:
                        name_idx = non_empty_indices[0]
                        doc_name = seg.get_element(name_idx, 0)
                        self._doctor_counter += 1
                        pseudo_doc = f"Dr. med. Musterarzt_{self._doctor_counter}"
                        self.detected_entities[doc_name] = MappingEntry(
                            original=doc_name,
                            pseudonym=pseudo_doc,
                            category=ReplacementCategory.DOCTOR_NAME,
                            count=1,
                            description="Arztname",
                        )
                        seg.set_element(name_idx, pseudo_doc, 0)

                # Kostenträger: NAD+KTR -> KEEP UNCHANGED!
                elif qual in ("KTR", "KK"):
                    last_patient_context = False

            # 6. DTM Segment (Date)
            elif tag == "DTM":
                qual = seg.get_element(0, 0)
                date_val = seg.get_element(0, 1)
                if not date_val and len(seg.elements) > 1:
                    qual = seg.get_element(0, 0)
                    date_val = seg.get_element(1, 0)

                if qual in ("102", "329", "032") or last_patient_context:
                    if date_val and re.match(r"^\d{8}$", date_val):
                        pseudo_date = self._get_or_create_mapping(
                            date_val, ReplacementCategory.BIRTHDATE, "Geburtsdatum (CCYYMMDD)"
                        )
                        if seg.get_element(0, 1):
                            seg.set_element(0, pseudo_date, 1)
                        else:
                            seg.set_element(1, pseudo_date, 0)

                        year = date_val[:4]
                        month = date_val[4:6]
                        day = date_val[6:8]
                        de_date = f"{day}.{month}.{year}"
                        de_pseudo = f"15.06.{year}"
                        self.detected_entities[de_date] = MappingEntry(
                            original=de_date,
                            pseudonym=de_pseudo,
                            category=ReplacementCategory.BIRTHDATE,
                            count=1,
                            description="Geburtsdatum (DD.MM.YYYY)",
                        )
                last_patient_context = False

            # 7. BES Segment (Betriebsstätte / Arzt)
            elif tag == "BES":
                bsnr = seg.get_element(0, 0)
                if bsnr and re.match(r"^\d{9}$", bsnr):
                    pseudo_bsnr = self._get_or_create_mapping(
                        bsnr, ReplacementCategory.DOCTOR_BSNR, "Betriebsstättennummer (BSNR in BES)"
                    )
                    seg.set_element(0, pseudo_bsnr, 0)
                lanr = seg.get_element(1, 0)
                if lanr and re.match(r"^\d{9}$", lanr):
                    pseudo_lanr = self._get_or_create_mapping(
                        lanr, ReplacementCategory.DOCTOR_LANR, "Arztnummer (LANR in BES)"
                    )
                    seg.set_element(1, pseudo_lanr, 0)

            # 8. EHE Segment (Rezept / Verordnungsnummer)
            elif tag == "EHE":
                belegnr = seg.get_element(0, 0)
                if belegnr and len(belegnr) >= 4:
                    self._recipe_counter += 1
                    pseudo_ehe = f"BELEG999{self._recipe_counter:04d}"
                    self.detected_entities[belegnr] = MappingEntry(
                        original=belegnr,
                        pseudonym=pseudo_ehe,
                        category=ReplacementCategory.INVOICE_NUMBER,
                        count=1,
                        description="Verordnungs-/Belegnummer (EHE)",
                    )
                    seg.set_element(0, pseudo_ehe, 0)

        anonymized_text = serialize_segments(self.segments)
        return anonymized_text, list(self.detected_entities.values())
