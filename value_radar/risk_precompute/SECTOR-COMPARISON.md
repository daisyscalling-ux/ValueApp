# Schritt 2: zeitgleicher Branchenvergleich

Der tägliche `daily-risk`-Lauf berechnet `daten/cf_sector_context.json`. Die Abdeckungsprüfung übernimmt den Bericht in `cf_risk_coverage.json`, das die Cloudflare-App bereits lädt. Es entstehen keine neuen Zugangsdaten und keine Änderung der Fair-Value- oder Risikoscore-Gewichte.

## Vergleichsregeln

- Mindestens fünf andere Emittenten aus der Vergleichsgruppe; eigene Aktienklassen und doppelte Notierungen zählen nicht zusätzlich.
- Nur gleiche Kurswährung. GBP und GBp/GBX sind für relative Renditen dieselbe Währungseinheit. Keine implizite Währungsumrechnung.
- Geschäftsmodellprüfung, Anbieter-Unterbranche und vorläufige breite Branche werden getrennt gekennzeichnet. Eine breite Branche ist kein bestätigter Konkurrenzvergleich.
- Gruppen und Kursabrufe höchstens 36 Stunden alt; letzter gemeinsamer Handelstag höchstens sieben Tage alt. Identität und Währung müssen weiterhin zum Universum passen.
- Bereinigte Kurse, mindestens ein Jahr Historie und 200 gemeinsame Handelstage; keine Lücke über 14 Tage. Ungültige oder widersprüchliche Preise werden ausgeschlossen.
- Alle Aktien einer Berechnung verwenden denselben gemeinsamen Endtermin und dieselben Starttermine. Renditen für 30, 90 und 180 Kalendertage: Endkurs / Startkurs minus eins. Start ist der gemeinsame Handelstag am oder vor dem Zieltermin, maximal sieben Tage vorher.
- Volatilität: Stichproben-Standardabweichung von 52 logarithmischen Wochenrenditen mal Wurzel 52. Die 53 Wochenpreise werden an gemeinsamen Handelstagen mit maximal vier Tagen Abstand zum Wochenanker gewählt.
- Größter Rückgang vom zuvor erreichten Hoch sowie aktueller Abstand zum Hoch werden im gemeinsamen Einjahresfenster berechnet.
- Vergleichsgröße ist der Median der anderen Emittenten. Zusätzlich: Quartile, Anteil negativer Dreimonatsrenditen und relativer Rang mit mittlerer Behandlung gleicher Werte.

## Betrieb

`RISK_SECTOR_ENABLED=1` aktiviert einen separaten GitHub-Cache `.risk-sector-series.json` mit maximal 400 Preisen pro Notierung. Beim ersten Lauf werden auch bislang frische Zusammenfassungen erneut abgerufen, wenn ihre Kursreihe noch fehlt. Folgeabrufe nutzen frische Reihen. Der Cache wird bei Teilfortschritt gesichert. Er ist eine Beschleunigung, keine dauerhafte Datenquelle; ein Cacheverlust führt zu erneuten Abrufen.

Fehlende Reihen, zu kleine Gruppen oder veraltete Daten erzeugen einen erklärten offenen Status, niemals einen Nullwert oder einen Ersatz durch fachfremde Firmen. Die neue produktive Prüfung fällt nicht auf den alten Vergleich unterschiedlich datierter Rückgänge zurück.

Nach Zusammenführen dieses PR: `daily-risk` auf `main` starten und die aktualisierte lokale Cloudflare-App veröffentlichen. Erst der abgeschlossene Datenlauf zeigt die tatsächlich erreichte Abdeckung.

## Validierung und Grenzen

16 neue Prüfungen: Rechenformeln, gemeinsamer Zeitraum, Währung, Mehrfachnotierungen, Identitätswechsel, veraltete Daten, Lücken, Mindestgröße, konstante Kurse, bekannter Kurseinbruch, Integration und Cache-Migration. Bestehende Universums- und Gruppentests bleiben erhalten.

Zusätzlich lokal geprüft: acht identitätsgeprüfte Yahoo-Kursreihen aus Softwareunternehmen, jeweils sieben andere Emittenten und 252 gemeinsame Handelstage. Dreimonatsrenditen und Mediane wurden unabhängig nachgerechnet. Das ist ein technischer Pilot, keine Genauigkeitskalibrierung eines Risikoscores.

Ein Strukturtest mit dem vollständigen Universum und synthetischen Kursen ergab 525 potenziell vergleichbare Notierungen. Das ist ausdrücklich keine gemessene produktive Datenabdeckung. Die breiten Branchenzuordnungen bleiben vorläufig; weitere fachliche Unterbranchenprüfung ist erforderlich. Aktuelle Gruppenmitgliedschaft ist kein historisches Indexuniversum.
