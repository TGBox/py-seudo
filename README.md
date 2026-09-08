# py-seudo 🛡️ (v1.0.0)

> **DSGVO-konforme Pseudonymisierung von ESOL-Abrechnungsdateien (§ 302 SGB V) und Kassen-Rückmeldungs-E-Mails für Heil- und Hilfsmittelerbringer mit intelligenter Fehler-Spiegelung und manuellen Korrekturmöglichkeiten.**

`py-seudo` ist eine moderne Windows-Desktop-Applikation (PySide6 mit Dark/Light-Mode), mit der Sie fehlerhafte Abrechnungsdateien (ESOL/EDIFACT) und die zugehörigen Rückweisungsemails von Krankenkassen und Abrechnungszentren (z. B. Syntela, TK, Barmer, AOK, Emmendingen, DMRZ) sicher und vollständig anonymisieren können – **ohne dass der technische Kontext für die Fehleranalyse und Fehlerbehebung verloren geht**.

---

## ✨ Hauptfunktionen

### 1. 🔒 DSGVO-konforme Pseudonymisierung
- **Patientendaten:** Namen, Vornamen, Anschriften und KVNRs werden durch syntaktisch valide Dummy-Werte ersetzt.
- **Geburtsdaten:** Das Geburtsjahr bleibt zur Prüfung von Volljährigkeit und Zuzahlungsbefreiung (§ 32 SGB V) erhalten, Tag und Monat werden standardisiert (`15.06.JJJJ` bzw. `JJJJ0615`).
- **Praxisdaten:** Eigene Praxis-IKs (9 Ziffern), Rechnungsnummern, Praxisadressen und Verordnungs-/Belegnummern werden neutralisiert.
- **Arztdaten:** Arzt-Namen, LANR (Lebenslange Arztnummer) und BSNR (Betriebsstättennummer) werden pseudonymisiert.

### 2. ⚠️ Neu in v1.0: Fehler-Spiegelung (Fault-Preserving Anonymization)
Wenn eine Abrechnung von der Krankenkasse abgewiesen wurde (z. B. wegen Tippfehlern in der IK, ungültiger KVNR-Prüfziffer oder doppelter Rechnungsnummer), durften diese Werte bisher nicht einfach durch fehlerfreie Standard-Dummies ersetzt werden, da Entwickler den Ablehnungsgrund sonst nicht mehr nachvollziehen konnten. `py-seudo` spiegelt Fehler mathematisch und syntaktisch:
- **Amtliche Prüfziffernverfahren:**
  - **Institutionskennzeichen (IK):** Vollständige Implementierung des **ARGE-IK Modulo-10-Verfahrens** über die Stellen 3 bis 8 (Gewichtung `[2, 1, 2, 1, 2, 1]`, Einerstelle der Quersumme).
  - **Krankenversichertennummer (KVNR):** Vollständige Implementierung der Richtlinie nach **§ 290 SGB V** (Buchstabencode A=01..Z=26 + 8 Ziffern mit Modulo-10-Prüfziffer).
- **Prüfzifferndefekt-Spiegelung:** War die Prüfziffer im Original fehlerhaft, erzeugt `py-seudo` ein Pseudonym, das **denselben Prüfzifferndefekt** aufweist (Prüfziffer weicht bewusst von der Modulo-10-Berechnung ab).
- **Syntax- & Formatfehler-Spiegelung:** Unzulässige Trennzeichen (z. B. Schrägstriche im REC-Segment `RE/2024/099`), Leerzeichen, Sonderzeichen oder Längenüberschreitungen werden strukturell im Pseudonym repliziert (`RE/99010/99011`).
- **Intelligenter `RejectionInspector`:** Scannt Abweisungs-E-Mails automatisch nach Gründen wie *Prüfziffernfehler*, *IK erloschen / unbekannt*, *nicht versichert* oder *Doppelabrechnung* und korreliert diese direkt mit den Segmenten der Abrechnungsdatei.
- **Status-Badges:** Im Ersetzungsprotokoll sofort erkennbar an `⚠️ Gespiegelt` (Orange) mit Diagnose-Tooltip vs. `✓ Valide` (Grün).

### 3. ✏️ Neu in v1.0: Manuelle Nachbearbeitung & Korrekturen
Falls die Erkennung eine Stelle übersehen hat oder man gezielt eigene Dummy-Werte verwenden möchte:
- **In-Place-Editing im Ersetzungsprotokoll:** Doppelklick auf die Spalte *Pseudonym (Ersetzt)* erlaubt die direkte Anpassung. Die Änderung wird **sofort global** in beiden Dokumenten (ESOL & E-Mail) synchronisiert.
- **Button `➕ Neue Ersetzung...`:** Erlaubt das freie Hinzufügen neuer Ersetzungsregeln (Originalwert $\rightarrow$ Pseudonym + Kategorie). Alle Vorkommen in Abrechnung und E-Mail werden auf Knopfdruck ersetzt.
- **Direkt editierbare Textvorschau:** Die rechte Seite der Diff-Ansicht ist nicht schreibgeschützt, sondern frei editierbar (`✏️ Manuell bearbeitbar`). Änderungen fließen direkt in das Speichern und Kopieren ein.
- **Optische Kennzeichnung:** Manuell bearbeitete Einträge werden mit dem Badge `✏️ Manuell` hervorgehoben.

### 4. 🩺 Erhalt der technischen Analysedaten
- **Kostenträger-IKs (Krankenkassen):** Bleiben vollständig unverändert erhalten.
- **Diagnosen (ICD-10):** Codes wie `M54.5` bleiben erhalten.
- **Abrechnungspositionen:** Heilmittel-Positionsnummern (z. B. `21201`), Tarife, Mengen und Beträge bleiben für die Fehlersuche exakt erhalten.
- **Syntaktische Validität:** EDIFACT-Trennzeichen (`+`, `:`, `'`, `?`) und Segmentstrukturen (`UNA`, `UNB`, `UNH`, `FKT`, `REC`, `INV`, `NAD`, `DTM`, `BES`, `ZHE`, `EHE`, `UNT`, `UNZ`) werden strikt gewahrt.

### 5. ✉️ Konsistente E-Mail-Bereinigung & Namenserkennung
- Gleiche Pseudonyme wie in der ESOL-Datei (derselbe Dummy-Name, dieselbe Dummy-KVNR).
- Bereinigung von Kopfzeilen (`From`, `To`, `Cc`, `Subject`, `Message-ID`).
- Automatische Maskierung von E-Mail-Adressen, Telefon- und Faxnummern.
- **Kontextbasierte Namenserkennung:** Namen aus Anreden (`Sehr geehrte Frau …`), Titeln (`Dr. med. …`), Feldbeschriftungen (`Patient:`, `Verordnender Arzt:`) und Signaturen werden mit realistischen deutschen Namen ersetzt (z. B. `Frau Schmidt`, `Ulla Winkler`).
- **Umlaut-Erhalt:** Verlustfreies UTF-8-Encoding schützt deutsche Sonderzeichen (ä, ö, ü, ß).

### 6. ⚠️ Restrisiko-Meldung & lückenloser Audit-Trail
- **Restrisiko-Banner:** Stellen, die nach Personenbezug aussehen, aber nicht eindeutig zugeordnet werden konnten, werden nicht heimlich übergangen, sondern im Reiter *Ersetzungs-Protokoll* aufgelistet. Vor dem Export wird darauf hingewiesen.
- **Audit-Export:**
  - **JSON-Export:** Enthält alle Ersetzungen, `total_errors_mirrored`, `total_manual_edits` sowie Diagnosehinweise.
  - **CSV-Export (Excel-optimiert):** Mit UTF-8-BOM und den Spalten `Original`, `Pseudonym`, `Kategorie`, `Anzahl`, `FehlerGespiegelt`, `DiagnoseHinweis`, `ManuellGeaendert`, `Beschreibung`.
- **Sicherheit:** Zuordnungen verbleiben standardmäßig ausschließlich im RAM. Lokale Audit-Exporte sind via `.gitignore` gegen versehentliche Git-Commits geschützt.

---

## 🎨 Benutzeroberfläche

- **Theme-Toggle:** Schneller Wechsel zwischen Dark Mode und Light Mode.
- **Drag & Drop:** Einfaches Ziehen von ESOL-Dateien und E-Mails direkt ins Fenster.
- **Side-by-Side Diff-Ansicht:** Synchronisiertes Scrollen mit Hervorhebung modifizierter Zeilen.
- **1-Klick-Demos:**
  - `📋 Beispieldaten laden`: Lädt fehlerfreie Standard-Abrechnungsdaten.
  - `⚠️ Demo mit Fehlern`: Lädt eine abgewiesene Abrechnung zur Demonstration der Fehler-Spiegelung (Prüfziffernfehler in IK & KVNR, Schrägstrich in Rechnungsnummer, Doppelabrechnung).

---

## 🚀 Schnellstart

### Option 1: Standalone `.exe` (Empfohlen für Endanwender)
Laden Sie einfach die portable Datei `dist/py-seudo.exe` herunter und starten Sie diese per Doppelklick (Windows 10 / 11, keine Installation oder Python erforderlich).

### Option 2: Ausführen aus dem Quellcode (mit `uv`)
Voraussetzung: Python >= 3.11 und [uv](https://docs.astral.sh/uv/)

```bash
# Repository klonen
git clone https://github.com/TGBox/py-seudo.git
cd py-seudo

# Abhängigkeiten installieren
uv sync

# Anwendung starten
uv run py-seudo
# oder direkt:
uv run main.py
```

---

## 🔨 Standalone-EXE kompilieren

Das Projekt verfügt über ein optimiertes Build-Skript ([build_exe.py](file:///c:/Users/DaniBani/Documents/VisualStudioCodeProjects/py-seudo/build_exe.py)), welches ungenutzte Qt6-Bibliotheken (Quick, Qml, 3D, WebEngine etc.) ausschließt und die Dateigröße von rund 250 MB auf schlanke **~42 MB** reduziert:

```bash
uv run python build_exe.py
```

Die fertige `.exe` befindet sich anschließend im Ordner `dist/py-seudo.exe`.

---

## 🧪 Tests & Qualitätssicherung

Das Projekt wird mit `pytest` und `pytest-cov` getestet (**91 % Testabdeckung** über 2.026 Zeilen):

```bash
# Alle 93 Tests ausführen
uv run pytest

# Ausführlicher Coverage-Bericht
uv run pytest --cov=py_seudo --cov-report=term-missing
```

### Test-Aufbau:
- `tests/test_error_mirroring.py`: 14 Tests für ARGE-IK- und § 290 SGB V-Prüfziffern, Defekt-Spiegelung und Rejection-Parsing.
- `tests/test_manual_edits.py`: 5 Tests für In-Place-Bearbeitung, Dialoge, direktes Diff-Editieren und Audit-Logging.
- `tests/test_email_names.py`: 43 Tests für kontextbasierte Erkennung, Rollenzuordnung und stilgetreue deutsche Namen.
- `tests/test_esol_anonymizer.py` & `test_tokenizer.py`: EDIFACT/ESOL-Parsing, Segmentintegrität und Idempotenz.
- `tests/test_engine.py` & `test_gui.py`: End-to-End-Pipeline, CSV/JSON-Exporte und PySide6-GUI-Interaktionen.

---

## 📄 Lizenz & Datenschutzhinweis
Entwickelt für den datenschutzkonformen Austausch von Abrechnungs- und Fehlerdaten gemäß DSGVO. Achten Sie bei der Weitergabe von Mappings darauf, dass diese ausschließlich lokal zur internen Zuordnung verbleiben und niemals öffentlich geteilt werden.
