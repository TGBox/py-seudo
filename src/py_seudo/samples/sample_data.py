"""Realistic sample datasets for demonstration and automated testing."""

SAMPLE_ESOL = """UNA:+.? '
UNB+UNOC:3+123456789:2+101575519:2+20240410:1430+ESOL0001++DTA'
UNH+00001+SLGA:15:0:0'
FKT+01+123456789+101575519+123456789'
REC+123456789+RE202400123+20240405'
UNT+4+00001'
UNH+00002+SLLA:15:0:0'
FKT+01+123456789+101575519'
REC+123456789+RE202400123+20240405'
INV+RE202400123+00+20240405'
NAD+FPR+123456789+++Therapiezentrum Sonnenschein+Hauptstrasse 15+Musterhausen++12345+DE'
NAD+KTR+101575519+++Techniker Krankenkasse'
NAD+VP+A123456789+++Mustermann+Max+Gartenweg 7+Berlin++10115+DE'
DTM+102:19820314:102'
NAD+ARZ+345678901+++Dr. med. Johannes Schmidt'
BES+987654321+345678901+20240320'
EHE+9876543210'
DIA+M54.5'
ENF+21201+10+45.50'
UNT+13+00002'
UNZ+2+ESOL0001'"""

SAMPLE_EMAIL = """Hallo Frau Meier,

ich habe wieder eine Ablehnung von der Kasse bekommen. Können Sie mir hier weiterhelfen?

Liebe Grüße,
Simone Sonnenschein



From: Techniker Krankenkasse Abrechnungspruefung <abrechnung-fehler@tk.de>
To: Therapiezentrum Sonnenschein <abrechnung@sonnenschein-therapie.de>
Date: Thu, 11 Apr 2024 09:15:22 +0200
Subject: Ablehnung / Fehlerprotokoll Abrechnungsdatei ESOL0001 (IK 123456789)
Content-Type: text/plain; charset="utf-8"

Sehr geehrte Damen und Herren,

bei der maschinellen Pruefung Ihrer Abrechnungsdatei ESOL0001 zu IK 123456789 wurden formale und inhaltliche Abweisungs-Fehler festgestellt:

Fehlerdetails zu Belegnummer 9876543210 (Rechnung RE202400123):
- Patient: Max Mustermann, Geb. 14.03.1982, KVNR: A123456789
- Anschrift: Gartenweg 7, 10115 Berlin
- Verordnender Arzt: Dr. med. Johannes Schmidt (LANR: 345678901, BSNR: 987654321)
- Diagnose: M54.5 (Lumbale Rueckenschmerzen)
- Fehlermeldung: Die Positionsnummer 21201 (Krankengymnastik) ist zur angegebenen Diagnose M54.5 nicht abrechnungsfaehig gemaess Heilmittelkatalog (Paragraph 302 SGB V).
- Segment: SLLA Zeile 18 (ENF+21201)

Bitte korrigieren Sie den Datensatz in Ihrer Praxissoftware und uebermitteln Sie eine Neulieferung.

Mit freundlichen Gruessen
Alexander Testperson
Abrechnungsteam TK
Tel: 040 / 460661000
Fax: 040 / 460661009
E-Mail: service-abrechnung@tk.de
"""

SAMPLE_ESOL_WITH_ERRORS = """UNA:+.? '
UNB+UNOC:3+441234568:2+101575519:2+20240502:1015+ESOL0099++DTA'
UNH+00001+SLGA:15:0:0'
FKT+01+441234568+101575519+441234568'
REC+441234568+RE/2024/099+20240428'
UNT+4+00001'
UNH+00002+SLLA:15:0:0'
FKT+01+441234568+101575519'
REC+441234568+RE/2024/099+20240428'
INV+RE/2024/099+00+20240428'
NAD+FPR+441234568+++Praxis Physiotherapie Schulz+Kastanienallee 12+Potsdam++14467+DE'
NAD+KTR+101575519+++Techniker Krankenkasse'
NAD+VP+Z987654329+++Becker+Monika+Lindenstrasse 88+Potsdam++14469+DE'
DTM+102:19681120:102'
NAD+ARZ+234567890+++Dr. med. Stefan Weber'
BES+876543210+234567890+20240410'
EHE+BELEG_DOPPELT_77'
DIA+M54.4'
ENF+21201+6+45.50'
UNT+13+00002'
UNZ+2+ESOL0099'"""

SAMPLE_EMAIL_REJECTION = """Hallo Herr Becker,

anbei sende ich Ihnen das Abweisungsprotokoll der Techniker Krankenkasse zur Abrechnungsdatei ESOL0099.
Die Kasse meldet formale Fehler in den Identifikatoren:

From: TK Abrechnungszentrum <rueckweisung@tk.de>
To: Praxis Schulz <abrechnung@praxis-schulz-potsdam.de>
Date: Fri, 03 May 2024 08:45:00 +0200
Subject: Abweisung Abrechnungsdatei ESOL0099 - Formale Fehler in Identifikatoren

Sehr geehrte Damen und Herren,

Ihre Datensendung ESOL0099 konnte nicht verarbeitet werden und wurde maschinell abgewiesen.
Folgende Abweisungsgründe wurden festgestellt:

1. Institutionskennzeichen (IK): 441234568
   Fehler: Prüfziffer fehlerhaft (Prüfziffer stimmt nicht mit Modulo-10-Berechnung überein).

2. Versichertennummer (KVNR): Z987654329
   Patient: Monika Becker, Geb. 20.11.1968
   Fehler: Prüfziffer ungültig gemäß § 290 SGB V.

3. Rechnungsnummer: RE/2024/099
   Fehler: Unzulässige Zeichen (Schrägstrich '/' im REC-Segment verletzt Felddefinition).

4. Belegnummer: BELEG_DOPPELT_77
   Fehler: Doppelabrechnung - Belegnummer wurde bereits mit Rechnung RE202400101 abgerechnet.

Bitte korrigieren Sie die Daten in Ihrem Praxisverwaltungssystem und reichen Sie eine korrigierte Neulieferung ein.

Mit freundlichen Grüßen
Claudia Richter
TK Fachzentrum Abrechnung
"""
