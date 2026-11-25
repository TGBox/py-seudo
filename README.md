# py-seudo 🛡️ (v1.0.0)

[![Automated Tests & CI](https://github.com/TGBox/py-seudo/actions/workflows/test.yml/badge.svg)](https://github.com/TGBox/py-seudo/actions/workflows/test.yml)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue.svg)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-114%20passed-success.svg)](https://github.com/TGBox/py-seudo)
[![Coverage](https://img.shields.io/badge/coverage-90%25-brightgreen.svg)](https://github.com/TGBox/py-seudo)

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
- **Syntaktische Validität:** EDIFACT-Trennzeichen (`+`, `:`, `'`, `?`) und Segmentstrukturen (`UNA`, `UNB`, `UNH`, `FKT`, `REC`, `INV`, `NAD`, `NAM`, `COM`, `FTX`, `DTM`, `BES`, `ZHE`, `EHE`, `UNT`, `UNZ`) werden strikt gewahrt.
- **Fail-closed bei Unbekanntem:** `NAD`-Segmente mit unbekanntem Qualifier oder Layout werden vollständig ersetzt und gemeldet. `COM` (Telefon/E-Mail) wird immer ersetzt, `FTX`-Freitext durch die Namenserkennung geschickt und zusätzlich zur Prüfung gemeldet.
- **Konsistente Pseudonyme:** Derselbe Patient erhält überall dieselben Pseudonyme (KVNR, Name, Adresse aus einer gemeinsamen Nummer). Dummy-PLZ beginnen mit `00` und können keiner echten PLZ gleichen.
- **Leistungsdaten bleiben:** Geburtsdaten werden über den DTM-Qualifier erkannt; ein Datum direkt nach einem Patienten-`NAD` gilt nur dann als Geburtsdatum, wenn es mehr als zwei Jahre vor dem Dateidatum liegt.

### 5. ✉️ Konsistente E-Mail-Bereinigung & Namenserkennung
- Gleiche Pseudonyme wie in der ESOL-Datei (derselbe Dummy-Name, dieselbe Dummy-KVNR).
- **Header-Allowlist:** Nur `From`, `To`, `Cc` (pseudonymisiert), `Date`, `Subject`, `MIME-Version` und `Content-*` bleiben; alle anderen Kopfzeilen (`Reply-To`, `Return-Path`, `X-…` usw.) werden entfernt.
- **Anhänge:** Nicht-Text-Anhänge (PDF, Bilder, angehängte E-Mails) werden durch einen sichtbaren Platzhalter ersetzt. Text-Anhänge werden anonymisiert und neutral umbenannt. Lässt sich ein Textteil nicht sicher verarbeiten, wird er entfernt und gemeldet.
- **Binärdateien wie Outlook-`.msg`** werden abgelehnt – bitte als `.eml` oder „Nur Text“ speichern.
- Automatische Maskierung von E-Mail-Adressen, Versichertennummern, Geburtsdaten (mit Kontext), Telefon- und Faxnummern. Ziffernketten im Kontext von IK, Beleg- oder Rechnungsnummern werden nicht als Telefonnummer behandelt.
- **Kontextbasierte Namenserkennung:** Namen aus Anreden (`Sehr geehrte Frau …`), Titeln (`Dr. med. …`), Feldbeschriftungen (`Patient:`, `Verordnender Arzt:`) und Signaturen werden mit realistischen deutschen Namen ersetzt (z. B. `Frau Schmidt`, `Ulla Winkler`).
- **Umlaut-Erhalt:** Verlustfreies UTF-8-Encoding schützt deutsche Sonderzeichen (ä, ö, ü, ß).

### 6. ⚠️ Restrisiko-Meldung & lückenloser Audit-Trail
- **Abschlussprüfung:** Nach jeder Anonymisierung und jeder manuellen Änderung prüft `verify.py` ESOL, E-Mail und englischen Report auf übrig gebliebene Versichertennummern, Kennnummern, Geburtsdaten, E-Mail-Adressen, Telefonnummern, PLZ mit Ort und nicht ersetzte Originale.
- **Exportsperre:** Solange eine Stelle offen ist, sind Speichern, Einzel-Export, Kopieren und KI-Versand gesperrt. Über *„🔎 Verdachtsfälle prüfen…“* wird jede Stelle einzeln ersetzt oder ausdrücklich freigegeben.
- **Neutrale Dateinamen:** Exporte übernehmen den Eingabenamen nur, wenn er eine technische Kennung ist (z. B. `ESOL0001`); vor dem Überschreiben wird gefragt.
- **Audit-Export:**
  - **JSON-Export:** Enthält alle Ersetzungen, `total_errors_mirrored`, `total_manual_edits` sowie Diagnosehinweise.
  - **CSV-Export (Excel-optimiert):** Mit UTF-8-BOM und den Spalten `Original`, `Pseudonym`, `Kategorie`, `Anzahl`, `FehlerGespiegelt`, `DiagnoseHinweis`, `ManuellGeaendert`, `Beschreibung`.
- **Sicherheit:** Zuordnungen verbleiben standardmäßig ausschließlich im RAM. Der Audit-Export enthält Klardaten; beim Speichern in einen synchronisierten Ordner (OneDrive, Dropbox, Netzlaufwerk) wird gewarnt.

### 7. 🇬🇧 Neu: Englischer Entwickler-Report & E-Mail-Übersetzung
Um Fehleranalysen und abgewiesene Abrechnungsdaten nahtlos mit internationalen Softwareentwicklern teilen zu können, erstellt `py-seudo` automatisch einen kombinierten englischen Übergabereport (`*_summary_and_email_en.txt`):
- **Strukturierter Aufbau (strikt ohne personenbezogene Segmentauszüge):**
  1. **Summary of Problems & Rejection Reasons:** Technische Zusammenfassung der Abweisungsgründe (z. B. Prüfzifferndefekte, unzulässige Sonderzeichen, Doppelabrechnungen oder Diagnose-/Heilmittel-Konflikte) mit konkreten Hinweisen für Entwickler zur Fehlerbehebung im Code.
  2. **Vollständige E-Mail-Übersetzung:** Kontexttreue Übersetzung der anonymisierten Kassen-E-Mail ins Englische unter Erhalt aller Dummy-Identifikatoren.
- **Hybrid-Architektur (Offline-First):**
  - **Lokaler Generator (Standard):** Arbeitet zu 100 % offline, datenschutzkonform und ohne API-Schlüssel direkt auf Ihrem Computer.
  - **Optionale KI-APIs:** Unterstützt OpenAI / OpenAI-kompatible Endpunkte (z. B. Ollama, GPT-4o-mini), Google Gemini und Anthropic Claude zur Übersetzung.
  - **Absicherung:** Vor jedem Versand zeigt ein Dialog den exakten Text und den Zielserver. Bei offenen Verdachtsfällen wird nichts gesendet. `https://` ist Pflicht (`http://` nur für `localhost`), API-Schlüssel werden unter Windows per DPAPI verschlüsselt gespeichert, der Gemini-Schlüssel geht im Header statt in der URL.
  - **Organisationsweit abschaltbar:** Mit der Umgebungsvariable `PY_SEUDO_DISABLE_CLOUD=1` (z. B. per Gruppenrichtlinie) bietet die Anwendung nur noch den lokalen Generator an.
  - **Hinweis:** Für den Versand an Cloud-Anbieter ist ein Vertrag zur Auftragsverarbeitung mit dem Anbieter und die Freigabe durch den Datenschutz erforderlich.
- **Benutzeroberfläche:** Eigener Reiter `🇬🇧 Englisch (Summary & E-Mail)` mit Live-Vorschau, Bearbeitungsmöglichkeit (`✏️ Manuell bearbeitbar`), Anbieter-Auswahl und Einstellungsdialog (`⚙️ API-Einstellungen`).
- **Automatischer Export:** Wird beim Klick auf *„💾 Anonymisierte Dateien speichern...“* automatisch als zusätzliche Textdatei in das Zielverzeichnis exportiert.

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

Das Projekt wird mit `pytest` und `pytest-cov` getestet (**91 % Testabdeckung** über 2.659 Zeilen, 114 Tests):

```bash
# Alle 114 Tests ausführen
uv run pytest

# Ausführlicher Coverage-Bericht
uv run pytest --cov=py_seudo --cov-report=term-missing
```

### Test-Aufbau:
- `tests/test_translation_local.py`: Tests für den lokalen Offline-Report-Generator, EDIFACT-Segmentanalyse und E-Mail-Übersetzung.
- `tests/test_translation_api.py`: Tests für OpenAI-, Gemini- und Claude-API-Integrationen, Mock-Aufrufe, Fehlerbehandlung und QSettings.
- `tests/test_translation_gui.py`: Tests für den Reiter `EnglishTabWidget`, `ApiSettingsDialog`, Zwischenablage und automatischen Export.
- `tests/test_error_mirroring.py`: 14 Tests für ARGE-IK- und § 290 SGB V-Prüfziffern, Defekt-Spiegelung und Rejection-Parsing.
- `tests/test_manual_edits.py`: 5 Tests für In-Place-Bearbeitung, Dialoge, direktes Diff-Editieren und Audit-Logging.
- `tests/test_email_names.py`: 43 Tests für kontextbasierte Erkennung, Rollenzuordnung und stilgetreue deutsche Namen.
- `tests/test_esol_anonymizer.py` & `test_tokenizer.py`: EDIFACT/ESOL-Parsing, Segmentintegrität und Idempotenz.
- `tests/test_engine.py` & `test_gui.py`: End-to-End-Pipeline, CSV/JSON-Exporte und PySide6-GUI-Interaktionen.
- `tests/test_verify.py`: Abschlussprüfung, Freigaben und Sperre des KI-Versands.
- `tests/test_email_hardening.py` & `test_esol_hardening.py`: Header, Anhänge, Binärdateien, Telefonerkennung, unbekannte Segmente, Pseudonym-Konsistenz, Leistungsdaten.
- `tests/test_translation_security.py`: HTTPS-Pflicht, Modellnamen, Gemini-Header, Richtlinie, Schlüsselablage.
- `tests/test_export_paths.py`: Neutrale Dateinamen und Erkennung synchronisierter Ordner.

---

## 📄 Lizenz & Datenschutzhinweis
Entwickelt für den datenschutzkonformen Austausch von Abrechnungs- und Fehlerdaten gemäß DSGVO. Achten Sie bei der Weitergabe von Mappings darauf, dass diese ausschließlich lokal zur internen Zuordnung verbleiben und niemals öffentlich geteilt werden.
