# Test-Fixtures

Alle Dateien in diesem Ordner sind **vollstaendig synthetisch**: erfundene Namen,
erfundene Praxis-IKs, erfundene LANR/BSNR, erfundene Versicherten- und Belegnummern.
Sie enthalten keine Echtdaten und duerfen committet werden.

Ausnahme: Die **Kostentraeger-IKs** (z. B. `660510336`, `104080005`) sind echt.
Das ist beabsichtigt und unbedenklich -- Kassen-IKs sind oeffentliche
Institutionskennzeichen und kein Personenbezug. Die Tests pruefen gerade,
dass diese erhalten bleiben.

**Echte Abrechnungsdateien gehoeren niemals hierher**, sondern nach `testdata/`
(per .gitignore ausgeschlossen).

## slla21_synthetic.txt

Nachgebautes § 302-Heilmittel-Paket im SLLA:21-/SLGA:21-Layout. Deckt ab:
`UNB`, `FKT` (Layout 2 mit leerem Feld 1), `REC`, `NAM`, `INV` mit KVNR,
`NAD` ohne Qualifier (Nachname+Vorname+Geburtsdatum), `ZHE`, `EHE`, `DIA`, `ENF`.

Die Struktur ist aus dem Verhalten des Anonymisierers und einer realen Datei
abgeleitet, aber nicht gegen die offizielle Spezifikation validiert. Wer eine
echte Datei zur Hand hat, sollte einmal abgleichen, ob Feldpositionen und
Qualifier stimmen.
