# Prüffristen (Stand 16.11.2026)

`review_deadlines.py` listet alle Fristen, ohne etwas abzurufen. Es gibt zwei Arten:
- ausdrückliche Prüfdaten in kuratierten Dateien (`reviewExpires`, `review_expires`, `mappingReviewExpires`);
- abgeleitete Fristen: Stichtag + 270 Tage für internationale Bankkennzahlen und die Kreditqualität (CR1).

daily-risk schreibt die Fristen der nächsten 60 Tage in die Zusammenfassung jedes Laufs. Abgelaufene Werte zählen nicht mehr; die Kennzahl wird dann offen mit Grund, nicht falsch.

## Fällig bis Jahresende

| Ablauf | Was | Erneuerung | frühestens |
|---|---|---|---|
| 26.12.2026 | Kreditqualität (CR1) von 7 japanischen Banken: MUFG, SMFG, Mizuho, SMTH, Shizuoka, Chiba, Yokohama; Stichtag 31.03.2026 | CR1 zum 30.09.2026 aus den Halbjahres-Offenlegungen (Basel III, Pillar 3) der Banken, wie bei der Erstprüfung in `reviewed-key-metrics.json` | Ende November bis Dezember (Veröffentlichung der Halbjahresberichte) |
| 31.12.2026 | Fed-Kapitalanforderungen (CET1) von 9 US-Banken | siehe unten | jetzt |
| 31.12.2026 | Crédit Agricole: Einheitenkorrektur der Säule-2-Anforderung (P2R 2026) | neue SREP-Mitteilung der EZB für 2027 (Pflichtmitteilung der Bank) als Beleg | Dezember 2026 |

## Fed-Kapitalanforderungen (geprüft am 16.11.2026)

**Was feststeht:**
- Das Dokument vom 24.06.2026 ist unverändert (SHA-256 gleich) und laut Fed-Seite weiterhin die neueste Fassung.
- Laut Board-Beschluss vom Februar 2026 bleiben die Stresskapitalpuffer bis 2027 unverändert.

**Offen:** Ob sich die G-SIB-Zuschläge der Banken zum 01.01.2027 ändern. Wegen dieser Möglichkeit wurde die Frist auf den 31.12. gelegt. Beleg wären die Angaben der Banken zum erwarteten Zuschlag im 10-Q für Q3 2026. Die SEC-Abrufe laufen mit dem User-Agent-Secret nur in der Pipeline.

**Erst wenn die Zuschläge bestätigt sind:** Frist bis 30.06.2027 verlängern, also vor der nächsten Jahresveröffentlichung. Bis dahin keine Verlängerung.
