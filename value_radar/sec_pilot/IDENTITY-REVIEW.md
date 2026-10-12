# Historische Wertpapierzuordnung der kostenlosen Daten

Der Workflow `free-source-research` erzeugt nach dem Abruf einen zusätzlichen Ordner `identity-review`. Diese Prüfung ist Teil jedes neuen vollständigen Laufs. Es sind keine neuen Secrets und kein Cloudflare-Deployment nötig.

## Dateien

- `identity_audit.json`: verbleibende Widersprüche und Anzahl Fälle je Status.
- `identitaetspruefung.csv`: alle erwarteten Forschungsidentitäten einschließlich fehlender und gesperrter Werte.
- `offene_faelle.csv`: fehlende Kursreihen, falsche Identitäten, fehlende zeitliche Überschneidung und unzureichende Kursreihen.
- `mitglieder_korrigiert_vorlaeufig.csv`: rekonstruierte Intervalle, Anfang einschließlich / Ende ausschließlich. Symbol ist hier eine Forschungsidentität, nicht zwingend ein tatsächlich damals verwendetes Börsenkürzel.
- `belegte_zuordnungen.csv`: angewandte Änderungen, ursprüngliches Kürzel, Ereignisdatum und Primärquelle.
- `security_identity_evidence.json`: versionierte Recherchebelege mit Wirksamkeitsdatum.
- `abwicklung_nur_konditionen.csv`: belegte Übernahmekonditionen, noch keine Abwicklungsrenditen.

Rohdateien bleiben zur Nachvollziehbarkeit unverändert und können falsche historische Zuordnungen enthalten. Für weitere Forschung immer die Prüfdateien berücksichtigen. Ein gesperrter Datensatz hat dort keinen `price_file`-Verweis. Auch ein gesetzter Verweis bestätigt noch keine universell geprüfte Identität oder Gesamtrendite.

## Regeln

1. Belegte reine Umbenennungen verbinden die historische Mitgliedschaft mit derselben Forschungsidentität. Aktuell: ADS→BFH, FBHS→FBIN, FLT→CPAY, RE→EG, SATS→ECHO, GPS→GAP, WLTW→WTW.
2. Schon in der Quelldatei ausdrücklich erfasste Tickerwechsel erzeugen keine zusätzliche Mitgliedschaft oder Indexentfernung.
3. Under Armour: frühere Class-A-Aktie UA wird dem heutigen UAA zugeordnet. Die spätere Class-C-Aktie UA bleibt getrennt. Die Gesamtrendite der Klassenausschüttung ist gesondert zu prüfen.
4. Allergan Inc. vor 2015 und Actavis/Allergan plc sind getrennte Identitäten. Keine Verkettung aufgrund desselben Kürzels AGN; keine Verwendung heutiger ACT-Kurse.
5. STI/Solidion wird für SunTrust gesperrt. Auch TFC wird nicht rückwirkend als SunTrust-Ersatz verwendet.
6. Kursreihen ohne einen Kurstag innerhalb einer rekonstruierten Mitgliedschaft werden gesperrt. Dies allein beweist keine Tickerwiederverwendung, sondern zunächst fehlende zeitliche Abdeckung.
7. Mindestens zwei Kurstage innerhalb der Mitgliedschaft sind nötig, um eine Reihe als Forschungs-Kandidat zu führen. Diese sehr niedrige Schwelle ist kein Vollständigkeitsnachweis.
8. Abwicklungsbedingungen wie 1,295 TFC-Aktien je SunTrust-Aktie sind nur Konditionen. Ohne passende Ausgangspreise und zeitgerechte Bewertung werden keine Renditen eingesetzt.

## Grenzen und nächster Forschungsbedarf

Alle Identitäten bleiben im erwarteten Universum; offene Fälle werden nicht zugunsten besserer Abdeckung entfernt. Übernahmehinweise in der Prüfliste stammen aus Wikipedia und sind nur Hinweise. Null Rekonstruktionswidersprüche bedeutet nicht, dass historische Mitgliedschaften, Kurse, Kapitalmaßnahmen oder der Börsenkalender vollständig geprüft sind.

Für die verifizierte Studie fehlen insbesondere dauerhafte Kennungen für alle Aktiengattungen, historische Kurse ausgeschiedener Werte, belegte terminale Renditen und der Kalenderabgleich. Die Datei `historical_universe.py` bleibt eine separate strengere Importprüfung. Kein automatischer Import dieser Forschungsdaten und keine Änderung am Produktions-Riskscore.

## Bereits vorhandenes Paket prüfen

`python value_radar/sec_pilot/identity_audit.py free-source-results.zip identity-review`

Dies arbeitet lokal ohne Netzabruf. Ein neuer Gesamtlauf lädt zusätzlich die in der Quellenliste dokumentierten Zielkürzel.

## Ergänzung vom 12.10.2026

ADS/BFH und FBHS/FBIN wurden mit SEC-Berichten abgeglichen. Der Indexausschluss von Fortune Brands am 19.12.2022 verwendete noch FBHS; eine ausschließlich auf Datum, Ereignisseite und Unternehmensname passende Ausnahme ordnet diesen Eintrag FBIN zu. Fremde oder spätere Verwendungen von FBHS bleiben unberührt.

`kapitalmassnahmen_pruefen.csv` und das Feld `capital_actions_to_review` dokumentieren die Loyalty-Ventures- und MasterBrand-Abspaltungen. Die Behandlung in Yahoo-Gesamtrenditen ist weiterhin ungeprüft.

Gezielter Yahoo-Abruf 2019-01-01 bis 2020-01-01 für EA, AVB, LEG, QRVO und WBD lieferte YFPricesMissingError; daraus folgt keine endgültige Unverfügbarkeit anderer Quellen. Die Sperren bleiben bestehen. BFH und FBIN lieferten je 3.212 Tageswerte im vollständigen Abruf ab 2014 bis einschließlich 09.10.2026.
