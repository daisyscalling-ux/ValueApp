# Tägliche Risikodaten für Cloudflare

Der neue Workflow daily-risk startet täglich um 07:23 UTC (09:23 deutsche Sommerzeit, 08:23 Winterzeit) und lässt sich manuell ausführen. GitHub kann geplante Läufe verzögern. Der bestehende precompute-3tage läuft laut main bereits täglich um 01:17 UTC. daily-risk arbeitet unabhängig auf der zuletzt veröffentlichten cf_universum.json; er erweitert das Aktienuniversum nicht.

## Einrichtung
1. Pull Request zusammenführen.
2. Actions → daily-risk → Run workflow auf main.
3. Nach Erfolg liegt value_radar/daten/cf_risk.json im Repository.
4. Die aktualisierte Cloudflare-App aus dem Ordner cf mit npm run deploy veröffentlichen.

ROIC_API_KEY muss in den GitHub Repository Secrets vorhanden sein; das bestehende Secret wird verwendet. Kein zusätzlicher API-Key. Die Ausgabe enthält abgeleitete Statistiken und keine API-Schlüssel oder vollständigen Kursreihen. Bei einem privaten Repository gelten die jeweiligen GitHub-Actions-Minutenkontingente; der neue Lauf verbraucht zusätzlich Laufzeit. Cloudflare benötigt denselben Lesezugriff auf die neue JSON wie auf das bestehende Universum.

## Inhalt und Grenzen
- Bis zu sechs Jahre Total-Return-Kurse (Dividenden und Splits), nur abgeschlossene UTC-Tage.
- Historische Verlustkennzahlen sowie aktueller Abstand zum Jahreshoch pro eindeutiger Börsennotierung.
- Zusätzlich zehn Markt-/Länder-ETF-Proxies, sofern ROIC sie eindeutig abdeckt.
- Dieselbe historyStatistics-Funktion wie im Browser. Die Kopien unter worker und src/lib werden aus cf übernommen und müssen bei Methodenänderungen gemeinsam aktualisiert werden.
- Finanzkennzahlen kommen weiterhin aus der beim Öffnen geladenen Unternehmensanalyse; ihr Berichtsdatum bleibt separat sichtbar. Nachrichten sind kein Bestandteil dieser täglichen JSON und laufen über die vorhandenen News-Endpunkte.
- Fehlende oder mehrdeutige Daten bleiben offen. Kein simuliertes Ergebnis, keine Verlustwahrscheinlichkeit. Maximal 70 % Grundmodellabdeckung; Wettbewerbs-/Bewertungsteil und bestätigte Ereigniszuschläge bleiben noch offen.

## Betrieb
Sequentielle Abfragen mit mindestens 650 ms Abstand (höchstens etwa 92/min), 90 Minuten Arbeitsbudget, 120 Minuten Joblimit. Jeder Netzabruf besitzt ein Zeitlimit. HTTP 429 löst eine Pause aus; 401/403 stoppen weitere Anbieterabfragen. Andere Apps und Jobs teilen weiterhin das ROIC-Kontingent; kein globaler kontenweiter Limiter.

Zwischenstände werden alle 25 bearbeiteten Einträge gespeichert; nicht erfolgreich erneuerte Daten behalten ihren ursprünglichen retrievedAt-Zeitstempel. Einträge mit ältestem Versuch werden zuerst geprüft, damit ein abgebrochener Lauf am Folgetag nicht dieselben Titel bevorzugt. Ein Bericht mit Fehlern und Restmenge steht unter report. Ein Teilfehler erzeugt eine Actions-Warnung; kompletter Fehlschlag einen roten Lauf. Der Veröffentlichungs-Schritt speichert Teilfortschritte auch nach einem Programmfehler, sofern die Ausgabedatei vorhanden ist. Bei hartem Runner-Abbruch können seit dem letzten veröffentlichten Lauf erzielte Fortschritte verloren gehen.

Die App übernimmt nur passende, gültige Einzelwerte mit Abrufalter maximal 36 Stunden. Der tatsächliche letzte Kurs darf höchstens sieben Tage alt sein (Wochenenden/Feiertage). Bei fehlenden/veralteten Exportdaten folgt der bestehende ROIC-Direktabruf mit 24-Stunden-KV-Cache. GitHub-Snapshots werden im Worker bis zu fünf Minuten wiederverwendet. Eine tägliche Aktualisierung ist keine Echtzeitüberwachung und garantiert keine vollständige Anbieterabdeckung.

## Korrektur nach dem ersten Live-Lauf (10. Oktober 2026)

Der erste Export vom 9. Oktober 23:22 UTC aktualisierte 0 von 1326 Aktien. Die Historienschnittstelle antwortete mit HTTP 402; dazu kamen nicht aufgelöste Notierungen und fehlende ETF-Treffer. Die Dokumentation nennt tarifabhängig zwei oder fünf Jahre, während der erste Export sechs Jahre anforderte. Das ist eine plausible, noch mit einem neuen Live-Lauf zu bestätigende Ursache.

Jetzt: zunächst knapp fünf Jahre (zwei Tage Abstand zur Tarifgrenze). Bei HTTP 402 auf der ersten Seite einmaliger Rückfall auf knapp zwei Jahre. Keine Wiederholung bei 401/403, keine Wiederholung oder Teilübernahme bei Fehlern späterer Seiten. Bei wiederholten 402 für drei Aktien stoppt der Lauf, statt alle Titel erfolglos abzufragen. Die Aktienauflösung erlaubt eindeutig zugeordnete US-ADRs, die nicht die primäre Emittentennotierung sind, und berücksichtigt bekannte Yahoo-Börsensuffixe. Für ETFs ist eine eindeutige US-Fondsnotierung ausreichend. Mehrdeutige Treffer bleiben ausgeschlossen.

Die 505 erforderlichen Handelstage für historische Verlustkennzahlen bleiben unverändert. Eine knapp zweijährige Reihe kann diese Mindestlänge unterschreiten; dann ist gegebenenfalls nur der Jahreshoch-Abstand verfügbar. Der Exportbericht nennt frische Datensätze und nutzbare Historien/Umfeldwerte gesondert. Das ist noch keine historische Kalibrierung des Scores.

Quelle: https://www.roic.ai/api/docs/stock-prices/historical und https://www.roic.ai/api/docs/tickers/search
