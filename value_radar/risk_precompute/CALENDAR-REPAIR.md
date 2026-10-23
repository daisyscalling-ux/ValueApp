# Feiertage und echte Kalenderlücken

Die Wochenstichtage lagen bisher maximal vier Kalendertage nach der letzten verfügbaren Beobachtung. Für den Endstichtag 21.10.2026 traf dies japanische Aktien am 06.05.2026 und 23.09.2026: Der letzte Handelstag lag jeweils fünf Tage zurück. Beide Zwischenräume enthalten ausschließlich reguläre JPX-Schließtage und Wochenenden.

Die Ausnahme prüft jetzt jeden dazwischenliegenden Tag gegen einen expliziten Kalender und gilt nur für TSE/TYO/JPX-Aktien. Alle Unternehmen des jeweiligen Vergleichs müssen die Ausnahme erfüllen. Fehlende Kurse an einem offenen Handelstag, unbekannte Börsen, OTC und Zeiträume außerhalb des dokumentierten Kalenders werden dadurch nicht freigegeben. Es werden keine Kurse interpoliert oder künstliche Nullrenditen ergänzt. 53 unterschiedliche Wochenstände, mindestens 200 gemeinsame Beobachtungen, ein vollständiges Kursjahr und fünf andere Emittenten bleiben Pflicht.

Quellen (geprüft 23.10.2026):
- JPX Market Holidays, vollständige Listen 2026 und 2027: https://www.jpx.co.jp/english/corporate/about-jpx/calendar/index.html
- JPX FAQ, Aktienhandel: Jahresanfang 1.–3. Januar und 31. Dezember geschlossen; Grundlage für 31.12.2025: https://www.jpx.co.jp/faq/others_general.html

Der explizite Ausnahmekalender deckt 31.12.2025 bis 31.12.2027 ab. Für spätere Jahre müssen veröffentlichte Kalender ergänzt werden; unbekannte Schließtage werden nicht geraten. Die Volatilität bleibt die vorhandene annualisierte Schätzung aus 52 Wochenrenditen. Feiertagsbedingte Verschiebungen werden mit tatsächlichem Beobachtungstag und Quelle ausgewiesen, nicht als exakte gleichlange Tagesintervalle dargestellt.

## OTC und andere echte Lücken

Der Workflow berechnet den aktuellen Kalenderstatus bereits vor dem Yahoo-Ergänzungslauf. Dadurch können auch formal frische ROIC-Reihen mit unzureichendem Kalender eine identitätsgeprüfte Ersatzabfrage auslösen. Die regulären Zeitbudgets und Pausen gelten weiter. Im Versorgungsbericht erscheinen der erste nicht belegte Wochenstichtag und die vorherige Beobachtung. Keine Übertragung japanischer Feiertage auf OTC-Notierungen.

## Nachweis

Live-Prüfung von vier betroffenen TSE- und acht OTC-Notierungen, auf denselben historischen Endtag 21.10.2026 begrenzt:
- Alle vier bestätigten japanischen Reihen scheitern ohne die Ausnahme und erfüllen die Kalenderprüfung mit den zwei belegten Feiertagsverschiebungen.
- Fünf identitätsgeprüfte OTC-Yahoo-Reihen erfüllen die bestehende Kalenderprüfung bereits ohne Ausnahme. Das belegt einen nutzbaren Ersatzdatenpfad, nicht die Qualität aller OTC-Reihen.
- Drei OTC-Namenszuordnungen wurden abgewiesen. Sie bleiben offen.
- 24 TypeScript-Sektor-/Kalenderprüfungen und 15 Python-Ergänzungsprüfungen bestanden. Die Tests schließen erfundene Handelspausen, gemischte Börsen, unbekannte Jahre, fehlende offene Handelstage und eine Absenkung der Gruppengröße aus.

Die produktive Wirkung auf sämtliche 67 japanischen und acht OTC-Fälle ist nach dem nächsten daily-risk-Lauf zu messen. Keine vorab behauptete Vollabdeckung.
