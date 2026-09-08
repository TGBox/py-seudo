# py-seudo 🛡️

> **DSGVO-konforme Pseudonymisierung von ESOL-Abrechnungsdateien (§ 302 SGB V) und Kassen-Rückmeldungs-E-Mails für Heil- und Hilfsmittelerbringer.**

`py-seudo` ist eine moderne Windows-Desktop-Applikation (PySide6 mit Dark/Light-Mode), mit der Sie fehlerhafte Abrechnungsdateien (ESOL/EDIFACT) und die zugehörigen Rückweisungsemails von Krankenkassen und Abrechnungszentren (z. B. Syntela, TK, Barmer, AOK, Emmendingen, DMRZ) sicher und vollständig anonymisieren können – ohne dass der technische Kontext für die Fehlersuche verloren geht.

---

## ✨ Hauptfunktionen

- 🔒 **DSGVO-konforme Pseudonymisierung:**
  - **Patientendaten:** Namen, Vornamen, Anschriften und KVNRs werden durch syntaktisch valide Dummy-Werte ersetzt (z. B. `X000000001` mit 10 Zeichen).
  - **Geburtsdaten:** Das Geburtsjahr bleibt zur Prüfung von Volljährigkeit und Zuzahlungsbefreiung (§ 32 SGB V) erhalten, Tag und Monat werden standardisiert (15.06.JJJJ).
  - **Praxisdaten:** Eigene Praxis-IKs (9 Ziffern), Rechnungsnummern, Praxisadressen und Belegnummern werden neutralisiert.
  - **Arztdaten:** Arzt-Namen, LANR (Lebenslange Arztnummer) und BSNR (Betriebsstättennummer) werden pseudonymisiert.
- 🩺 **Erhalt der technischen Fehleranalyse-Daten:**
  - **Kostenträger-IKs (Krankenkassen):** Bleiben vollständig unverändert erhalten.
  - **Diagnosen (ICD-10):** Codes wie `M54.5` bleiben unverändert.
  - **Abrechnungspositionen:** Heilmittel-Positionsnummern (z. B. `21201`), Tarife, Mengen und Beträge bleiben für die Fehlersuche exakt erhalten.
  - **Syntaktische Validität:** EDIFACT-Trennzeichen (`+`, `:`, `'`, `?`) und Feldlängen werden strikt eingehalten, sodass Validatoren und Prüfmodule die Dateien weiterhin fehlerfrei parsen können.
- ✉️ **Konsistente E-Mail-Bereinigung:**
  - Gleiche Pseudonyme wie in der ESOL-Datei (derselbe Dummy-Patientenname, dieselbe Dummy-KVNR).
  - Bereinigung von Kopfzeilen (`From`, `To`, `Cc`, `Subject`, `Message-ID`).
  - Automatische Maskierung von E-Mail-Adressen, Telefon- und Faxnummern.
- 🎨 **Moderne Desktop-Oberfläche:**
  - Auswahl zwischen **Dark Mode** und **Light Mode**.
  - **Drag & Drop** von Dateien direkt ins Programmfenster.
  - **Side-by-Side Diff-Ansicht:** Synchronisiertes Scrollen mit farblicher Hervorhebung aller geänderten Segmente und Zeilen.
  - **Ersetzungs-Tabelle (Audit):** Durchsuchbare Liste aller ersetzten Entitäten mit Kategorien und Häufigkeiten.
  - **1-Klick-Demo:** Schaltfläche *"Beispieldaten laden"* für sofortiges Testen.
  - **Export-Funktionen:** Direkter Export der bereinigten Dateien oder Kopieren in die Zwischenablage.
- 🛡️ **Git- und Datenschutz-Schutz:**
  - Verarbeitungen finden standardmäßig rein im Arbeitsspeicher statt.
  - Optionale lokale Mapping-Audit-Dateien (JSON/CSV) sind über `.gitignore` gegen versehentliches Committen in Git-Repositories geschützt.

---

## 🚀 Schnellstart

### Option 1: Standalone `.exe` (Keine Python-Installation erforderlich)
Laden Sie einfach die Datei `dist/py-seudo.exe` herunter und starten Sie diese per Doppelklick auf jedem beliebigen Windows-PC (Windows 10 / 11).

### Option 2: Ausführen aus dem Quellcode (mit `uv`)
Voraussetzung: Python >= 3.11 und [uv](https://docs.astral.sh/uv/)

```bash
# Repository klonen
git clone https://github.com/ihr-benutzer/py-seudo.git
cd py-seudo

# Abhängigkeiten installieren
uv sync

# Anwendung starten
uv run py-seudo
```

---

## 🧪 Tests & Qualitätssicherung

Das Projekt wird mit `pytest` und `pytest-cov` getestet (über 90 % Testabdeckung):

```bash
# Tests ausführen
uv run pytest

# Tests mit ausführlichem Coverage-Bericht
uv run pytest --cov=py_seudo --cov-report=term-missing
```

### GitHub Actions CI
Bei jedem `push` und `pull_request` führt die konfigurierte GitHub Action (`.github/workflows/test.yml`) die gesamte Testsuite automatisch unter Windows und Linux aus.

---

## 🔨 Standalone-EXE selbst bauen

Um die `.exe`-Datei aus dem aktuellen Quellcode neu zu kompilieren:

```bash
uv run python build_exe.py
```
Die fertige, transportable `.exe` befindet sich anschließend im Ordner `dist/py-seudo.exe`.

---

## 📄 Lizenz & Datenschutzhinweis
Entwickelt für den datenschutzkonformen Austausch von Abrechnungs- und Fehlerdaten gemäß DSGVO. Achten Sie bei der Weitergabe von Mappings darauf, dass diese ausschließlich lokal zur internen Zuordnung verbleiben und niemals öffentlich geteilt werden.
