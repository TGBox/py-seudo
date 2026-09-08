# Code-Review py-seudo

**Datum:** 08.09.2026 · **Umfang:** kompletter Quellcode (`src/`, `tests/`, Build, CI, README)
**Methodik:** statische Durchsicht + ausgeführte Gegenproben gegen die Kernlogik (`edifact`, `email`, `engine`).
Die GUI konnte in der Prüfumgebung nicht gestartet werden (kein PySide6), sie wurde nur gelesen.

Alle mit **[verifiziert]** markierten Befunde sind durch einen tatsächlich ausgeführten Lauf belegt; die Ein-/Ausgaben stehen jeweils dabei.

---

## Gesamteinschätzung

Die Grundarchitektur ist gut gewählt: eigener EDIFACT-Tokenizer statt Regex über den Rohtext, saubere Trennung in `edifact` / `email` / `engine` / `gui`, typisierte Dataclasses, src-Layout, CI-Matrix über zwei Betriebssysteme, DSGVO-Warnungen an den richtigen Stellen. Der Escape-/Delimiter-Roundtrip des Tokenizers ist korrekt — das ist der Teil, der erfahrungsgemäß am häufigsten schiefgeht, und er stimmt.

Das Problem liegt eine Ebene darüber. Die Anonymisierung arbeitet **positions- und qualifierbasiert nach dem Denylist-Prinzip**: Es wird ersetzt, was erkannt wurde. Alles, was nicht erkannt wird, läuft unverändert durch — ohne Fehler, ohne Warnung, ohne Spur in der Mapping-Tabelle. Für ein Werkzeug, dessen Zweck es ist, Dateien *nach außen an Dritte* zu geben, ist das die falsche Fehlerrichtung. Ein Anonymisierer muss fail-closed sein: im Zweifel ersetzen oder wenigstens melden.

Konkret: Ich habe sieben Wege gefunden, auf denen echte Patienten- oder Praxisdaten unbemerkt im Output landen, und vier Wege, auf denen umgekehrt genau die Diagnosedaten zerstört werden, die erhalten bleiben sollen. Die Kernzusage „gleiches Pseudonym für dieselbe Entität" hält der Code außerdem nicht ein.

Empfehlung: vor dem produktiven Einsatz die Punkte A1–A4, B1, B2 und C1 beheben und einen Verifikationslauf (A8) einziehen.

---

## A. Datenschutz — Klardaten im Output

### A1 · E-Mail ohne ESOL-Datei wird praktisch nicht anonymisiert **[verifiziert]**

`EmailAnonymizer` ersetzt im Body ausschließlich das, was vorher aus der ESOL-Datei gelernt wurde, plus Telefon und E-Mail-Adresse. Ohne ESOL-Datei bleibt der Rest stehen.

```
Eingabe (nur E-Mail, kein ESOL):
  Patient Anna Meier, geb. 01.02.1980, KVNR A111111111,
  Anschrift Ringweg 3, 50667 Koeln. IK 123456789.

Ausgabe:
  Patient Anna Meier, geb. 01.02.1980, KVNR A111111111,
  Anschrift Ringweg 3, 50667 Koeln. IK 123456789.
```

Die GUI erlaubt diesen Modus ausdrücklich („mindestens eine ESOL-Datei **oder** eine Rückmeldungsemail"), meldet aber Erfolg. Verschärfend: `KVNR_REGEX` und `IK_REGEX` sind in `email/anonymizer.py` Zeile 22–23 **definiert, werden aber nirgends verwendet** — die Absicht war offenbar da, die Umsetzung fehlt.

*Fix:* generische Erkenner im E-Mail-Pfad aktivieren (KVNR, IK, Geburtsdaten in beiden Schreibweisen, PLZ+Ort) und die GUI warnen lassen, dass der Nur-E-Mail-Modus schwächer ist.

### A2 · Zusatz-Header und Anhänge bleiben unangetastet **[verifiziert]**

Bereinigt werden `From`, `To`, `Cc`, `Subject` und eine feste Löschliste. Alles andere bleibt:

```
Return-Path: <andrea.becker@tk.de>              ← bleibt
Delivered-To: praxis.mueller@sonnenschein.de     ← bleibt
Reply-To: Andrea Becker <a.becker@tk.de>         ← bleibt
References: <abc123@sonnenschein-therapie.de>    ← bleibt
Content-Disposition: attachment;
  filename="Fehlerprotokoll_Mustermann_Max_A123456789.pdf"   ← bleibt
[PDF-Payload]                                    ← bleibt vollständig
```

Bei echten `.eml`-Dateien aus Outlook ist das der wahrscheinlichste Leak-Pfad überhaupt: Anhänge heißen in der Praxis fast immer nach Patient oder Belegnummer, und Rückweisungsprotokolle kommen häufig als Anhang statt im Body.

*Fix:* Header-**Allowlist** statt Denylist (nur `Date`, `Subject`, `Content-Type`, `MIME-Version` durchlassen, Rest verwerfen). Anhänge entweder entfernen und durch einen Platzhalter-Part ersetzen oder — bei Textformaten — durch denselben Ersetzungslauf schicken; Dateinamen in jedem Fall pseudonymisieren.

### A3 · Unbekannte NAD-Qualifier laufen still durch **[verifiziert]**

```
Eingabe:  NAD+PV+A111111111+++Meier+Anna+Ringweg 3+Koeln++50667+DE'
Ausgabe:  NAD+PV+A111111111+++Meier+Anna+Ringweg 3+Koeln++50667+DE'
```

Behandelt werden `FPR/LE/LBO`, `VP/IM/VN/PE`, `ARZ/BY`, `KTR/KK`. Jeder andere Qualifier fällt in den `else`-Zweig (anonymizer.py:439), der das SLLA:21-Layout `NAD+Nachname+Vorname+Geburtsdatum` erwartet. Passt das Muster nicht exakt — Vorname fehlt, Geburtsdatum steht woanders, Qualifier ist `PV`/`GB`/`ZA` —, passiert gar nichts.

Dasselbe Muster beim SLLA:21-Layout selbst:

```
Eingabe:  NAD+Meier+Anna+Ringweg 3'      (kein 8-stelliges Geburtsdatum)
Ausgabe:  NAD+Meier+Anna+Ringweg 3'
```

*Fix:* Der `else`-Zweig muss ein `raise` oder mindestens eine Warnung im Ergebnis erzeugen, nicht ein stilles `pass`. Ein NAD-Segment, das nicht zugeordnet werden konnte, ist ein Befund, kein Normalfall.

### A4 · Kein FTX / COM / FRE-Handling **[verifiziert]**

```
FTX+Rueckfrage zu Patientin Anna Meier, Tel 0221 123456'   ← unverändert
COM+0221 123456:TE'                                        ← unverändert
COM+praxis@meier.de:EM'                                    ← unverändert
```

Freitextsegmente sind in Fehlerdateien genau die Stelle, an der Klarnamen auftauchen. `COM` transportiert Telefon und E-Mail der Praxis — der `NAM`-Handler deckt nur ein Feld in SLGA ab.

### A5 · Formatabweichungen umgehen die Regexe **[verifiziert]**

Alle Nummernprüfungen sind auf exakt neun Ziffern verdrahtet (`^\d{9}$`):

```
NAD+ARZ+1234567890+++Dr. Meier'   → LANR (10-stellig) bleibt, nur der Name wird ersetzt
BES+12345678+123456789+...'       → BSNR (8-stellig) bleibt stehen
```

Reale Dateien enthalten führende Nullen, Leerzeichen, gelegentlich falsch gefüllte Felder. Genau diese Fälle sind es, die man mit Fremdentwicklern teilen will — und genau sie rutschen durch.

### A6 · Vergleich ohne `strip()` im UNB-Segment **[verifiziert]**

`_discover_institutions` normalisiert mit `.strip()` (Zeile 50), `anonymize()` vergleicht in Zeile 171 ohne:

```
Eingabe:  UNB+UNOC:3+ 123456789 :2+101575519:2+...'
          REC+123456789+RE1+20240101'
Ausgabe:  UNB+UNOC:3+ 123456789 :2+101575519:2+...'   ← Praxis-IK im Klartext
          REC+999000001+RE9990001+20240101'           ← hier ersetzt
```

Dieselbe IK erscheint im Output einmal echt und einmal pseudonymisiert. Das ist der schlechtest mögliche Zustand: das Pseudonym ist über die Datei selbst auflösbar.

### A7 · Substring-Prüfung bei E-Mail-Adressen **[verifiziert]**

`if "invalid" not in email_str and "example.com" not in email_str` (email/anonymizer.py:182) prüft auf Teilstrings statt auf die Domain:

```
Eingabe:  Kontakt: info@invalid-praxis-mueller.de
Ausgabe:  Kontakt: info@invalid-praxis-mueller.de
```

*Fix:* Domain-Teil extrahieren und gegen `{"beispiel.invalid", "kasse.invalid", …}` prüfen — oder, sauberer, prüfen, ob die Adresse eines der selbst erzeugten Pseudonyme *ist*.

### A8 · Kein Verifikationslauf — das strukturelle Kernproblem

Nirgends wird geprüft, ob die Anonymisierung tatsächlich vollständig war. Das Programm meldet „✓ Anonymisierung erfolgreich: 20 Entitäten pseudonymisiert" und sagt damit nichts darüber aus, was es *nicht* gefunden hat.

Das ist der Punkt, an dem ich am meisten Hebel sehe. Ein Nachlauf über den erzeugten Output kostet wenig und fängt alle Befunde aus A1–A7 auf einmal ab:

```python
def verify(anonymized: str, mappings: list[MappingEntry]) -> list[Finding]:
    findings = []
    # 1. Kein Original darf im Output überlebt haben
    for m in mappings:
        if m.original != m.pseudonym and m.original in anonymized:
            findings.append(Finding("REST_ORIGINAL", m.original, m.category))
    # 2. Generische Muster, die niemals überleben dürfen
    for pat, label in ((KVNR_RE, "KVNR"), (IBAN_RE, "IBAN"), (DATE_DE_RE, "Datum"),
                       (EMAIL_RE, "E-Mail"), (PHONE_RE, "Telefon")):
        for hit in pat.finditer(anonymized):
            if hit.group(0) not in KNOWN_PSEUDONYMS:
                findings.append(Finding("VERDACHT", hit.group(0), label))
    # 3. 9-stellige Zahlen, die weder bekanntes Kassen-IK noch Pseudonym sind
    ...
    return findings
```

In der GUI als eigener Reiter „Restrisiko" mit Ampel, und der Export-Button bleibt bei Funden gesperrt bzw. erzwingt eine explizite Bestätigung. Das dreht die Fehlerrichtung von fail-open auf fail-closed, ohne die bestehende Logik anzufassen.

### A9 · `testdata/` ist nicht in `.gitignore`

`tests/test_esol_anonymizer.py:109` liest `testdata/in/ESOL0001` — einen echten Abrechnungsdatensatz. Dieser Pfad steht **nicht** in `.gitignore`. Ein `git add -A` committet echte Patientendaten. Der Ordner existiert aktuell nicht im Projekt, aber der Testcode lädt aktiv dazu ein, ihn anzulegen.

Zusätzlich stehen in den Assertions dieses Tests echte Nachnamen (`Appenzeller`, `Abel`) und echte IKs (`480512931`, `242325300`, `963752734`). Die sind bereits im Repository — und wenn das Repo je öffentlich wird, sind sie öffentlich.

*Fix:* `testdata/`, `*.esol`, `ESOL*` in `.gitignore`; Assertions gegen synthetische Werte einer selbst gebauten Testdatei tauschen, die committet werden darf.

### A10 · Hardcodierte Dummy-Werte können echten Werten gleichen **[verifiziert]**

Patient-PLZ wird pauschal durch `"12345"` ersetzt. Wohnt der Patient tatsächlich in 12345, ist die Ersetzung ein No-Op — und die Mapping-Tabelle protokolliert stolz `12345 → 12345`. Dasselbe gilt für `"Musterweg 12"`, `"99999"`, `"Musterort"`.

*Fix:* Dummy-Werte aus einem Bereich wählen, der nicht vergeben ist (PLZ `00000`, Straßen mit erkennbarem Präfix), oder beim Erzeugen prüfen, ob der Dummy dem Original gleicht, und dann eine Variante nehmen.

---

## B. Korrektheit — zerstörte Diagnosedaten

Das Versprechen des README lautet, dass Kassen-IKs, Diagnosen, Positionsnummern und Beträge exakt erhalten bleiben. An vier Stellen hält der Code das nicht.

### B1 · FKT-Positionsheuristik kann Praxis- und Kassen-IK vertauschen **[verifiziert]**

`_discover_institutions` nimmt an, dass in `FKT` das erste 9-stellige Feld die Praxis ist:

```
Eingabe:  FKT+01+101575519+123456789'      (Kasse an Position 1)
          NAD+KTR+101575519+++TK'
Ausgabe:  FKT+01+999000001+123456789'      ← Kassen-IK zerstört, Praxis-IK im Klartext
          NAD+KTR+101575519+++TK'          ← dieselbe Kasse hier unverändert
```

Beide Fehler in einem Lauf: die Kassen-IK — der wichtigste Diagnosewert — ist weg, die Praxis-IK steht offen da, und die Kassen-IK erscheint in derselben Datei einmal als `999000001` und einmal als `101575519`. Ausgelöst wird das durch die Deduplizierungsschleife in Zeile 86–88, die im Konfliktfall immer zugunsten „Praxis" entscheidet.

*Fix:* IK-Klassifikation nicht aus der Position ableiten, sondern aus einer gepflegten Liste bekannter Kostenträger-IKs (die ersten Stellen sind vergeben: `10x`, `66x` usw.) plus Kreuzvalidierung über `NAD+KTR`. Bei Widerspruch zwischen zwei Quellen einen Konflikt melden statt still zu entscheiden — und `NAD+KTR` sollte in der Klassifikation stärker wiegen als eine Positionsvermutung in `FKT`.

### B2 · `last_patient_context` zerstört Leistungsdaten **[verifiziert]**

```
Eingabe:  NAD+VP+A111111111+++Meier+Anna'
          DTM+472:20240315:102'    ← Leistungsdatum
          DTM+102:19800101:102'    ← Geburtsdatum
Ausgabe:  DTM+472:20240615:102'    ← auf den 15.06. gesetzt, Datum vernichtet
          DTM+102:19800615:102'    ← korrekt
```

Jedes `DTM` unmittelbar nach einem Patienten-`NAD` gilt als Geburtsdatum. Da ein großer Teil der § 302-Rückweisungen genau am Leistungsdatum hängt („Leistungsdatum außerhalb des Verordnungszeitraums", „Behandlung vor Verordnungsdatum"), zerstört das systematisch den Fehler, den man untersuchen wollte — und zwar unsichtbar, weil das Ergebnis syntaktisch plausibel bleibt.

Nebenbefund: Die Qualifier-Prüfung `qual in ("102", "329", "032")` liest DE 2005 (Funktionscode), vergleicht aber gegen Werte, die wie DE 2379 (Formatqualifier) aussehen. In den Testdaten steht `DTM+102:19820314:102`, wo beides zufällig 102 ist — deshalb fällt es nicht auf. Das gehört gegen die echte § 302-Spezifikation und ein reales File geprüft.

*Fix:* Geburtsdatum ausschließlich über den korrekten Qualifier erkennen, `last_patient_context` ersatzlos streichen. Wenn ein Fallback nötig ist, dann über Plausibilität (Jahr < aktuelles Jahr − 1), nicht über Segmentnachbarschaft.

### B3 · Telefon-Regex frisst IKs und Zahlenketten **[verifiziert]**

```
Eingabe:  Kassen-IK 0101575519 im Text.
          Belegnummer 0987654 3210.
          Tel 030 1234567
Ausgabe:  Kassen-IK +49 000 0000000 im Text.
          Belegnummer +49 000 0000000.
          Tel +49 000 0000000
```

`\b0[1-9][\d\s\/\(\)-]{6,}\b` greift auf jede längere Ziffernkette mit führender Null. Der Schutz `re.match(r"^\d{9}$", …)` deckt nur exakt neun Ziffern ohne Trennzeichen ab. In Fehler-E-Mails stehen IKs und Belegnummern regelmäßig mit Leerzeichen gruppiert.

*Fix:* Telefonnummern nur mit Kontextanker erkennen (`Tel`, `Telefon`, `Fax`, `Mobil`, `+49`, Zeilenanfang einer Signatur) statt rein über die Ziffernform; bekannte Kassen-IKs und Pseudonyme vorab als geschützte Bereiche markieren.

### B4 · Kettenersetzung: ESOL und E-Mail widersprechen sich **[verifiziert]**

`_apply_replacements` läuft die Mappings nacheinander mit `re.sub` über denselben String. Ein bereits eingesetztes Pseudonym kann von einer späteren Regel erneut getroffen werden:

```
Mappings:  10115 → 12345 (Patient-PLZ),  12345 → 99999 (Praxis-PLZ)
ESOL-Output:  ... Musterort++12345+DE'      ← Patient hat PLZ 12345
E-Mail-Output: "Patient wohnt in 99999, Praxis in 99999."
```

Der Patient hat in der ESOL-Datei die PLZ 12345 und in der E-Mail 99999. Die beiden Dateien, die gemeinsam weitergegeben werden, widersprechen sich — und das Ergebnis hängt von der Reihenfolge ab, in der die Segmente in der Datei standen.

*Fix:* Ein einziger Durchlauf mit einem kombinierten Alternations-Regex und `re.sub(pattern, callback, text)`. Der Callback schlägt das Pseudonym nach; bereits ersetzte Bereiche werden nie erneut betrachtet. Das ist gleichzeitig deutlich schneller als die aktuelle Schleife mit einem `finditer` + `sub` pro Mapping.

---

## C. Konsistenz der Pseudonyme

### C1 · Direktzuweisungen umgehen die Mapping-Logik **[verifiziert]**

An über zwölf Stellen wird `self.detected_entities[key] = MappingEntry(...)` direkt geschrieben, statt `_get_or_create_mapping` zu verwenden. Folge: Bei jedem Vorkommen wird ein *neues* Pseudonym erzeugt und der alte Eintrag überschrieben.

```
Eingabe:  NAD+VP+A111111111+++Meier+Anna+Ringweg 3+Koeln++50667+DE'
          NAD+VP+A111111111+++Meier+Anna+Ringweg 3+Koeln++50667+DE'   (identisch)
Ausgabe:  NAD+VP+X000000001+++Mustermann_2+Max_2+...'
          NAD+VP+X000000001+++Mustermann_3+Max_3+...'   ← anderer "Patient"

Mapping-Tabelle:  Meier → Mustermann_3   (Mustermann_2 taucht nirgends auf)
```

Derselbe Patient wird zu zwei verschiedenen Personen; die Mapping-Tabelle kennt nur die letzte Variante und ist damit für die Rückauflösung unbrauchbar. `count` bleibt konstant 1, wodurch auch die Statistik in der Statusleiste falsch ist. Betroffen sind Patientennamen, Adressen, Praxisnamen, Arztnamen und `EHE`-Belegnummern.

*Fix:* Ausnahmslos alle Ersetzungen über `_get_or_create_mapping` führen. Als Schlüssel nicht den Rohstring, sondern `(category, normalisierter_wert)` — das behebt gleichzeitig C3.

### C2 · Zählerversatz zwischen KVNR und Name **[verifiziert]**

`_patient_counter` wird sowohl beim Erzeugen der KVNR (`_generate_pseudonym`) als auch im NAD-Handler hochgezählt:

```
KVNR:  X000000001   ↔   Name: Mustermann_2 / Max_2
Arzt:  LANR 888000001, BSNR 777000002, Name Musterarzt_2
```

Fachlich harmlos, praktisch ärgerlich: Wer die anonymisierte Datei liest, kann Nummern und Namen nicht mehr zueinander in Beziehung setzen.

*Fix:* Ein Zähler pro Entität (nicht pro Feld). Erst die Patienten-ID vergeben, dann alle Felder dieses Patienten aus derselben ID ableiten.

### C3 · Ein globaler Namensraum für alle Kategorien

`detected_entities` ist über alle Kategorien hinweg nach dem Originalstring indiziert. Eine Ziffernfolge, die einmal als Rechnungsnummer und einmal als Belegnummer auftaucht, teilt sich einen Eintrag; welches Pseudonym gewinnt, entscheidet die Reihenfolge.

### C4 · Toter Code und falsche Kategorien

- `_generate_pseudonym`, Zweig `PATIENT_NAME` (Zeile 123–128): wird nie erreicht, da Patientennamen ausschließlich per Direktzuweisung gesetzt werden.
- Praxisnamen werden unter `ReplacementCategory.PRACTICE_IK` abgelegt (Zeile 196, 270) — die Mapping-Tabelle zeigt „Praxis-IK (Institutionskennzeichen)" für einen Klartextnamen. Es fehlt eine Kategorie `PRACTICE_NAME`.
- `EHE`-Belegnummern laufen unter `INVOICE_NUMBER`, obwohl es Verordnungsnummern sind.

---

## D. Architektur und Wartbarkeit

### D1 · `EsolAnonymizer.anonymize()` ist zu groß

Eine Methode, 420 Zeilen, eine `if/elif`-Kette über Segment-Tags, darin verschachtelte Qualifier-Verzweigungen mit Index-Arithmetik über `non_empty_indices`. Jede neue Layout-Variante (SLLA:21, SLGA:21, künftige Versionen) vergrößert dieselbe Methode. Testbar ist sie nur end-to-end.

Vorschlag: Handler-Registry plus deklarative Feldregeln.

```python
SEGMENT_HANDLERS: dict[str, Handler] = {}

def handles(tag): ...          # Decorator, registriert den Handler

@handles("NAD")
def _nad(seg, ctx):
    rule = NAD_RULES.get(seg.get_element(0, 0).strip())
    if rule is None:
        ctx.warn(UnknownLayout(seg))   # ← statt stillem Durchlauf (A3)
        return
    rule.apply(seg, ctx)

NAD_RULES = {
    "VP": FieldRule(id_field=1, id_cat=KVNR,
                    text_fields=[(0, SURNAME), (1, FORENAME), (2, STREET), (3, CITY)],
                    postal_scan_from=4),
    ...
}
```

Damit werden Layouts zu Daten statt zu Code, neue Qualifier sind eine Zeile, und jede Regel ist einzeln testbar. Der Umbau ist gut inkrementell machbar — Tag für Tag, mit den bestehenden Tests als Netz.

### D2 · Keine Konfiguration von außen

Qualifier-Listen, Dummy-Werte, Kassen-IK-Präfixe und Regexe stehen fest im Code. Wenn beim Abrechnungszentrum eine Layout-Variante auftaucht, muss neu gebaut und die .exe verteilt werden. Eine YAML/JSON-Regeldatei neben der Anwendung (mit eingebautem Default) würde das entkoppeln.

### D3 · Erkennen und Ersetzen sind nicht getrennt

Beides passiert in einem Durchlauf, deshalb gibt es keinen Trockenlauf („was würde erkannt?") und keinen Zwischenpunkt für die Verifikation aus A8. Eine Trennung in *detect → plan → apply → verify* macht alle vier Schritte einzeln prüfbar.

### D4 · GUI

- **Kein Threading:** `_run_anonymization` läuft im UI-Thread. Bei mehreren MB großen Sammelabrechnungen friert das Fenster ein. `QThreadPool` + `QRunnable` genügt.
- **`.msg` im Dateifilter** (`app.py:180`): Outlook-`.msg` ist ein binäres OLE-Format. `read_text` mit latin-1-Fallback liefert Zeichensalat, die Anonymisierung greift nicht, und der Anwender bekommt trotzdem „✓ erfolgreich". Entweder `extract-msg` einbinden oder `.msg` aus dem Filter nehmen und beim Erkennen ablehnen.
- **Zeilenenden:** `write_text` ohne `newline=""` übersetzt `\n` unter Windows zu `\r\n`. Der Tokenizer normalisiert eingelesene `\r\n` bereits zu `\n`. Eine LF-Datei kommt also als CRLF-Datei zurück — für strenge Validatoren relevant.
- **Überschreiben ohne Rückfrage** im Zielordner.
- **Inline-Styles überschreiben das Theme:** feste Farben wie `color: #94a3b8` (app.py:50) und der Security-Banner mit `background-color: #1e3a8a` (mapping_widget.py:67) folgen dem Light Mode nicht. Gehört in die Stylesheets als benannte Objektnamen.
- **`Qt.ItemFlag.ItemIsEditable` mit `^`** statt `& ~` (mapping_widget.py:108 ff.): XOR *setzt* das Flag, wenn es nicht gesetzt war. Funktioniert hier zufällig, ist aber falsch.
- **Falsche Zusicherung im Export-Dialog:** „Die Datei ist durch die .gitignore dieses Projekts gegen versehentliches Committen geschützt" — der Anwender wählt den Zielordner frei; außerhalb des Projekts gilt das nicht. Diese Aussage sollte weg oder an eine Prüfung des Zielpfads gebunden werden.

### D5 · Kleinigkeiten

- Ungenutzte Imports: `QMimeData`, `QIcon`, `QApplication` in `app.py`; `difflib` in `diff_widget.py`; `Optional`/`Tuple` teilweise in `models.py` und `tokenizer.py`.
- `max_lines` in `diff_widget._highlight_diffs:127` wird berechnet und nicht verwendet.
- Das Highlighting positioniert den Cursor pro geänderter Zeile von vorn (`Start` + n × `NextBlock`) → O(n²). Bei großen Dateien spürbar.
- Version steht doppelt in `pyproject.toml` und `__init__.py`.
- CSV-Export ohne BOM: Excel unter Windows/DE zeigt Umlaute falsch → `encoding="utf-8-sig"`.
- Kein Logging — bei einem Fehler in der Anonymisierung gibt es nur die QMessageBox.
- Tokenizer: ein nicht terminiertes letztes Segment bekommt beim Serialisieren ein `'` angehängt; Whitespace zwischen Segmenten geht verloren. Beides harmlos, führt aber zu Diff-Zeilen, die keine echte Änderung sind.

---

## E. Tests

Die Suite ist ordentlich aufgebaut und deckt die glücklichen Pfade ab. Drei strukturelle Schwächen:

### E1 · Der einzige Test mit einer echten Datei läuft nie

```python
esol_file = Path("testdata/in/ESOL0001")
if not esol_file.exists():
    pytest.skip("testdata/in/ESOL0001 not present")
```

Der Ordner ist nicht im Repo, also skippt der Test — lokal wie in CI, ohne dass jemand es merkt. Genau dieser Test hätte die Befunde A5, B1 und C1 aufgedeckt. Ersatz: eine synthetische, aber realistisch aufgebaute SLLA:21-Datei ins Repo legen (erfundene Namen, erfundene IKs, echte Struktur) und ohne Skip testen.

### E2 · Fast nur Abwesenheitsprüfungen

Die Assertions haben durchweg die Form `assert "Meier" not in out_text`. Solche Tests bestehen auch dann, wenn der Anonymisierer das halbe Segment zerlegt. Es fehlt die Gegenrichtung:

- Segmentanzahl und Tag-Reihenfolge unverändert?
- Beträge, Positionsnummern, Mengen, Leistungsdaten bitidentisch?
- Output erneut parsebar (Round-Trip durch den Tokenizer)?
- Idempotenz: zweiter Lauf über den Output ändert nichts mehr?

Ein Golden-File-Test (Input → erwarteter Output, komplett) fängt all das auf einmal ab und macht Regressionen im Diff sichtbar.

### E3 · Fehlende Fälle

Nicht abgedeckt: E-Mail ohne ESOL (A1), derselbe Patient mehrfach (C1), FKT-Varianten (B1), unbekannte Qualifier (A3), Anhänge (A2), latin-1-Dateien, CRLF-Dateien, `DTM` mit anderem Qualifier (B2), Nummern abweichender Länge (A5).

Für den Anonymisierer bietet sich zusätzlich ein Property-Test an: *Für jede erzeugte Eingabe gilt — kein Original aus der Mapping-Tabelle steht im Output.* Mit `hypothesis` und einem kleinen EDIFACT-Generator ist das überschaubar und findet genau die Klasse von Fehlern, die hier auftritt.

### E4 · Sonstiges

- `test_coverage_boost.py`: Tests nach Verhalten benennen, nicht nach Coverage-Absicht. Der Inhalt gehört auf die thematischen Dateien verteilt.
- Dort wird `QApplication` ohne die `offscreen`-Fixture erzeugt — auf dem Windows-Runner können echte Fenster aufgehen.
- CI: kein `--cov-fail-under`, kein `ruff`, kein `mypy`. Alle drei sind zwei Zeilen im Workflow und halten die Qualität über die Zeit.
- `.gitignore` enthält `*.spec` und ignoriert damit die projekteigene `py-seudo.spec`.

---

## Priorisierter Vorschlag

**Zuerst — Datenschutz (blockierend für den produktiven Einsatz)**

1. `testdata/` in `.gitignore`, echte Namen/IKs aus den Test-Assertions entfernen *(A9)*
2. Verifikationslauf mit „Restrisiko"-Anzeige und gesperrtem Export bei Funden *(A8)*
3. Unbekannte NAD-Layouts melden statt still durchlassen *(A3)*
4. Generische Erkenner im E-Mail-Pfad aktivieren, Header-Allowlist, Anhänge behandeln *(A1, A2)*

**Danach — Korrektheit**

5. Alle Ersetzungen über `_get_or_create_mapping`, ein Zähler pro Entität *(C1, C2)*
6. `last_patient_context` entfernen, Geburtsdatum nur über den korrekten DTM-Qualifier *(B2)*
7. IK-Klassifikation über Kostenträgerliste statt Position, Konflikte melden *(B1)*
8. E-Mail-Ersetzung als ein Durchlauf mit Alternations-Regex und Callback *(B4)*
9. Telefonerkennung an Kontextanker binden *(B3)*

**Danach — Struktur**

10. Handler-Registry und deklarative Feldregeln für `anonymize()` *(D1)*
11. Golden-File-Test, Round-Trip-Test, Property-Test; `ruff` und `mypy` in CI *(E1–E4)*
12. Threading, `.msg`-Behandlung, Theme-Bereinigung in der GUI *(D4)*

Die Punkte 1–4 sind alle klein und unabhängig voneinander; 5–9 fasst man sinnvoll in einem Durchgang durch `edifact/anonymizer.py` zusammen.
