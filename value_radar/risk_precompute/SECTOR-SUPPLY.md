# Branchenvergleich: Versorgung und Kalenderauswahl

## Änderungen gegenüber Schritt 2

Der gemeinsame Kalender wird nicht mehr blind über alle Notierungen geschnitten. Zunächst wird der neueste Zielstichtag mit mindestens fünf anderen Emittenten gewählt. Kandidaten werden nach Zahl gemeinsamer Kurstage, bei Gleichstand nach Symbol sortiert. Eine Notierung wird nur aufgenommen, wenn der verbleibende gemeinsame Kalender weiterhin ein Kursjahr, mindestens 200 Beobachtungen, die Renditestichtage und 53 Wochenstände trägt. Die Reihenfolge hängt nicht von Renditen, Bewertung oder Volatilität ab. Diese deterministische Auswahl ist keine mathematische Maximierung der Gruppengröße.

Alle tatsächlich verglichenen Unternehmen behalten identische Stichtage. Ausgeschlossene Kalender werden gezählt. Ein unzureichender Kalender der Zielaktie bleibt offen. Mindestgruppengröße und Währungsprüfung bleiben bestehen; fehlende Werte werden nicht interpoliert.

## Automatischer Yahoo-Ergänzungslauf

`daily-risk` startet nach ROIC einen separaten Ergänzungslauf ohne zusätzliche Secrets:

- Höchstens 400 Notierungen und 20 Minuten pro Lauf; isolierte Unterprozesse mit maximal 25 Sekunden pro Unternehmen.
- Gültige Notierung, ISIN-Prüfziffer, Yahoo-Symbol, Börse, Aktienart, Währung und Unternehmensname müssen passen. Bestehende geprüfte Namensvarianten gelten; bei nicht eindeutiger Identität erfolgt keine Übernahme.
- Die originale Eingabeidentität wird gespeichert. Neue oder geänderte Aktien werden automatisch erkannt.
- Yahoo-Branchenangaben werden 30 Tage genutzt und danach erneuert. `sectorKey` und `industryKey` bilden eine eigene Anbieterklassifikation; sie werden nicht als GICS oder unabhängig geprüfte Konkurrenten ausgegeben.
- Bereits fachlich geprüfte Geschäftsmodelle haben Vorrang. Eine bestätigte Yahoo-Zuordnung kann innerhalb eines eindeutig zusammengefassten Emittenten auf dessen weitere Notierungen übertragen werden. Widersprüchliche Anbietergruppen werden zur Prüfung zurückgestellt.
- Frische ROIC-Kursreihen bleiben erhalten. Fehlende/veraltete Reihen werden durch vollständig geprüfte Yahoo-`Adj Close`-Reihen ergänzt. Rohkurse sind kein Ersatz; zu kurze IPO-/Notierungshistorien bleiben offen.
- Erfolgreiche Profile bleiben auch bei fehlgeschlagener Historie erhalten. Fehler erhalten einen Tag Pause; alte Abrufversuche kommen zuerst, damit neue Aktien nicht dauerhaft hinten bleiben. Bei Rate-Limit wird der Lauf beendet und später fortgesetzt.
- Jeder Versuch wird gespeichert. Der bestehende GitHub-Cache enthält die Kursreihen; `cf_peer_metadata.json` enthält Profile und Versuchszustand. Der globale Workflow hat nun 180 Minuten Sicherheitslimit.

Der neue `cf_sector_supply_plan.json` trennt Identitätsprüfung, Kursnachladung, Kalenderprüfung und fachliche Gruppen-/Währungsprüfung. Er enthält keine Rohkurse. Ein fehlender Gruppenvergleich ist nicht automatisch ein Fehler beim Kursanbieter.

## Abgrenzung

Die Zusatzhistorien versorgen hier den Branchenvergleich. Andere Risikodomänen und Fair-Value-Modelle werden nicht automatisch umgeschrieben. Die feinere Zuordnung kann zunächst kleinere Gruppen ergeben, solange andere Profile noch nicht geladen sind. Es werden keine unpassenden Unternehmen ergänzt, um eine bestimmte Abdeckungsquote zu erreichen.

## Prüfung

- 19 TypeScript-Prüfungen für Rechenlogik, gemeinsame Kalender, Identität, Cache und fehlende Daten.
- 14 Python-Prüfungen für Anbieteridentität, Kursvalidierung, Fortschritt, Konflikte und Aktualisierung; bestehende 16 Gruppentests bleiben bestehen.
- Live-Pilot am 22.10.2026 mit 48 gezielt ausgewählten Notierungen: 39 bestätigte Profile, 36 gültige Kursreihen, drei unzureichende Historien und neun abgewiesene Namenszuordnungen.
- Auf diesen Pilotdaten funktionieren 27 Vergleiche mit feineren Anbietergruppen; Renditen und Mediane wurden unabhängig nachgerechnet. Citigroup hat dort elf andere Emittenten in `banks-diversified`, Merck acht in `drug-manufacturers-general`. Diese Zahlen sind keine Abdeckung des vollständigen Universums.
- Der isolierte Kalenderwechsel erzeugte im Live-Pilot keine zusätzliche Abdeckung; seine Fehlerbehebung ist mit gezielt lückenhaften Testkalendern nachgewiesen. Die Wirkung auf die 166 produktiven Kalenderfälle muss der erste vollständige Lauf messen.

## Quellen und Betrieb

Yahoo-Profil- und historische Kursabfragen verwenden die bereits im Projekt eingesetzte yfinance-Version 0.2.66. Anbieterinformationen: https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.html und https://ranaroussi.github.io/yfinance/reference/api/yfinance.Industry.html . Fachliche Klassifikationen nach Geschäftstätigkeit sind von breiten Sektoren zu unterscheiden: https://www.msci.com/indexes/index-resources/gics . Es werden keine lizenzierten GICS-Daten behauptet oder erzeugt.

Nach Merge `daily-risk` auf `main` starten und den aktualisierten lokalen Cloudflare-Ordner veröffentlichen. Weitere tägliche Läufe ergänzen die übrigen Profile innerhalb des Budgets. Nach dem ersten Lauf `cf_sector_supply_plan.json` und den Vergleichsbericht prüfen, statt die Anzahl verfügbarer Vergleiche vorab zu versprechen.
