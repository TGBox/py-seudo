"""EDIFACT ESOL Anonymizer for German Healthcare Billing (§ 302 SGB V)."""
from __future__ import annotations

import re
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
                    if ik_pos3 and re.match(r"^[A-Za-z0-9]{6,14}$", ik_pos3):
                        self.kassen_iks.add(ik_pos3)

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
            self._patient_counter += 1
            return generate_mirrored_kvnr(
                orig,
                self._patient_counter,
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
            self._doctor_counter = max(self._doctor_counter, 1)
            return f"888{self._doctor_counter:06d}", False, ""

        elif category == ReplacementCategory.DOCTOR_BSNR:
            self._doctor_counter = max(self._doctor_counter, 1)
            return f"777{self._doctor_counter:06d}", False, ""

        elif category == ReplacementCategory.ADDRESS:
            return "Musterstrasse 42", False, ""

        return f"ANON_{orig}", False, ""

    def anonymize(self) -> Tuple[str, List[MappingEntry]]:
        """Run anonymization over all parsed segments."""
        last_patient_context = False

        for seg in self.segments:
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

            # 2b. NAM Segment (Praxisname / Kontaktdaten in SLGA)
            elif tag == "NAM":
                p_name = seg.get_element(0, 0).strip()
                if p_name:
                    pseudo_name = "Praxis fuer Therapie Musterpraxis"
                    self.detected_entities[p_name] = MappingEntry(
                        original=p_name,
                        pseudonym=pseudo_name,
                        category=ReplacementCategory.PRACTICE_IK,
                        count=1,
                        description="Praxisname (NAM)",
                    )
                    seg.set_element(0, pseudo_name, 0)
                # Element 3: Practice contact / email
                p_contact = seg.get_element(3, 0).strip()
                if p_contact:
                    pseudo_contact = "kontakt@beispiel.invalid"
                    self.detected_entities[p_contact] = MappingEntry(
                        original=p_contact,
                        pseudonym=pseudo_contact,
                        category=ReplacementCategory.CONTACT_INFO,
                        count=1,
                        description="Praxis E-Mail / Kontakt (NAM)",
                    )
                    seg.set_element(3, pseudo_contact, 0)

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
                        pseudo_kvnr = self._get_or_create_mapping(
                            inv_val, ReplacementCategory.KVNR, "Versichertennummer (INV)"
                        )
                        seg.set_element(0, pseudo_kvnr, 0)
                    else:
                        pseudo_inv = self._get_or_create_mapping(
                            inv_val, ReplacementCategory.INVOICE_NUMBER, "Rechnungsnummer (INV)"
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

                else:
                    # SLLA:21 / § 302 Heilmittel without qualifier: NAD+Nachname+Vorname+Geburtsdatum
                    nachname = seg.get_element(0, 0).strip()
                    vorname = seg.get_element(1, 0).strip()
                    geburtsdatum = seg.get_element(2, 0).strip()

                    if nachname and vorname and re.match(r"^\d{8}$", geburtsdatum):
                        self._patient_counter += 1
                        p_idx = self._patient_counter
                        p_surname = f"Mustermann_{p_idx}"
                        p_forename = f"Max_{p_idx}"
                        pseudo_dob = f"{geburtsdatum[:4]}0615"

                        self.detected_entities[nachname] = MappingEntry(
                            original=nachname,
                            pseudonym=p_surname,
                            category=ReplacementCategory.PATIENT_NAME,
                            count=1,
                            description="Patient Nachname (NAD)",
                        )
                        self.detected_entities[vorname] = MappingEntry(
                            original=vorname,
                            pseudonym=p_forename,
                            category=ReplacementCategory.PATIENT_NAME,
                            count=1,
                            description="Patient Vorname (NAD)",
                        )
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

                        self.detected_entities[geburtsdatum] = MappingEntry(
                            original=geburtsdatum,
                            pseudonym=pseudo_dob,
                            category=ReplacementCategory.BIRTHDATE,
                            count=1,
                            description="Geburtsdatum (CCYYMMDD)",
                        )
                        de_date = f"{geburtsdatum[6:8]}.{geburtsdatum[4:6]}.{geburtsdatum[:4]}"
                        de_pseudo = f"15.06.{geburtsdatum[:4]}"
                        self.detected_entities[de_date] = MappingEntry(
                            original=de_date,
                            pseudonym=de_pseudo,
                            category=ReplacementCategory.BIRTHDATE,
                            count=1,
                            description="Geburtsdatum (DD.MM.YYYY)",
                        )

                        seg.set_element(0, p_surname, 0)
                        seg.set_element(1, p_forename, 0)
                        seg.set_element(2, pseudo_dob, 0)

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

            # 7b. ZHE Segment (LANR und BSNR in SLLA:21)
            elif tag == "ZHE":
                lanr = seg.get_element(0, 0).strip()
                if lanr and re.match(r"^\d{9}$", lanr):
                    pseudo_lanr = self._get_or_create_mapping(
                        lanr, ReplacementCategory.DOCTOR_LANR, "Arztnummer (LANR in ZHE)"
                    )
                    seg.set_element(0, pseudo_lanr, 0)
                bsnr = seg.get_element(1, 0).strip()
                if bsnr and re.match(r"^\d{9}$", bsnr):
                    pseudo_bsnr = self._get_or_create_mapping(
                        bsnr, ReplacementCategory.DOCTOR_BSNR, "Betriebsstaettennummer (BSNR in ZHE)"
                    )
                    seg.set_element(1, pseudo_bsnr, 0)

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

        anonymized_text = serialize_segments(self.segments)
        return anonymized_text, list(self.detected_entities.values())
