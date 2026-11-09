# Kursverfall- und Insolvenzfaelle im historischen Universum

Stand 09.11.2026. Forschungsdaten, keine Aenderung produktiver Risikoscores oder Gewichte.

## Warum diese Faelle zuerst

Die Fensterpruefung (`WINDOW-COVERAGE.md`, Lauf 38209892625) nennt 48 Wertpapiere mit unvollstaendigen Fenstern. Etwa 35 davon verliessen den Index wegen einer Uebernahme. Zehn verliessen ihn ohne Uebernahmehinweis: nach Kursverfall (Marktkapitalisierung) oder durch Bankenzusammenbruch. Genau diese Faelle enthalten die Verluste, die ein Risikoscore vorher erkennen soll. Sie fehlten vollstaendig.

Die Reihenfolge der Beschaffung richtet sich nach der Austrittsart laut Wikipedia, nicht nach spaeteren Renditen. Alle 48 Faelle bleiben im Nenner der erwarteten Fenster.

## Vorgehen

`loss_case_review.py` (Workflow `loss-case-review`) prueft je Fall:

- SEC-Stammdaten ueber die CIK: aktueller und frueherer Name, Ticker, Boerse. Der vorab angenommene Firmenname muss passen, sonst `sec_identity_mismatch_review_cik`.
- Status-Meldungen: Form 25/25-NSE, Form 15 sowie 8-K mit Item 1.03 (Insolvenz/Zwangsverwaltung), 2.01, 3.01 (Delisting), 3.03 oder 5.03.
- Auszuege aus den 8-K mit Item 1.03 oder 3.01 seit dem Entscheidungsbeginn 12.10.2020: Saetze zu Umtausch, Barabfindung, Handelsaussetzung und Ticker. Nur zum Lesen, keine automatische Betragsuebernahme.
- Yahoo-Kandidatenreihen je vermutetem Ticker: Name, Wertpapierart, Waehrung, Abdeckung ab Entscheidungsbeginn, Zeilen vor und nach dem Indexaustritt, Luecken ueber sieben Tage.

Nichts wird automatisch in `security_identity_evidence.json` uebernommen (`admitted_automatically: 0`).

## Ergebnis (Lauf 42635847606)

Alle acht SEC-CIKs bestaetigen den erwarteten Emittenten. FRC und SBNY sind Banken ohne Holding und berichteten an die FDIC, nicht an die SEC.

| Wertpapier | Austritt S&P 500 | Spaeterer Verlauf laut Originalmeldung | Kursreihe |
|---|---|---|---|
| SIVB | 2023-03-15 | Bank am 10.03.2023 geschlossen, FDIC als Zwangsverwalter; Handel an der Nasdaq ab 10.03.2023 angehalten, Aussetzung 28.03.2023; Chapter 11 am 17.03.2023; Plan am 02.08.2024 bestaetigt | keine (SIVB, SIVBQ leer) |
| FRC | 2023-05-04 | FDIC-Zwangsverwaltung; keine SEC-Meldungen | FRCB: 1.526 Zeilen ab 12.10.2020, keine Luecke ueber sieben Tage. Identitaetsbeleg ausserhalb der SEC fehlt noch |
| SBNY | 2023-03-15 | FDIC-Zwangsverwaltung; keine SEC-Meldungen | SBNY erst ab 15.08.2024, davor keine Reihe |
| HFC | 2021-06-04 | 1:1-Umtausch in HF Sinclair, ab 15.03.2022 als DINO an der NYSE | DINO: 1.526 Zeilen ab 12.10.2020, keine Luecke. **Zuordnung uebernommen** |
| DISH | 2023-06-20 | Fusion mit EchoStar zum 31.12.2023: 0,350877 EchoStar-Aktien je DISH-Aktie | keine; der Ticker SATS gehoert heute einer anderen Firma |
| HBI | 2021-12-20 | Uebernahme durch Gildan, 8-K 01.12.2025: 0,102 Gildan-Aktien plus 0,80 USD je Aktie | keine |
| CMA | 2024-06-24 | Uebernahme durch Fifth Third, 8-K 02.02.2026: 1,8663 Fifth-Third-Aktien je Aktie | keine |
| SEE | 2023-12-18 | Uebernahme, Handel an der NYSE ab 09.04.2026 ausgesetzt | keine |
| LEG | 2021-12-20 | Uebernahme, 8-K 26.08.2026: 0,1455 Aktien der Erwerberin je Aktie | Yahoo liefert nur einen Tag |
| QRVO | 2024-12-23 | Uebernahme, 8-K 05.10.2026 | Yahoo liefert nur einen Tag |

Folgerung: Sieben der zehn Faelle wurden nach dem Indexaustritt spaeter uebernommen und sind inzwischen delistet. Yahoo fuehrt ihre Historie nicht mehr. Die Abfindungskonditionen sind jetzt belegt, die Kursreihe davor fehlt weiterhin.

## Uebernommene Zuordnung

`HFC -> DINO` ab 2022-03-15 in `security_identity_evidence.json`. Beleg: SEC 8-K vom 16.03.2022 (https://www.sec.gov/Archives/edgar/data/48039/000119312522077293/d260898d8k.htm). Jede HFC-Aktie wurde automatisch in eine HF-Sinclair-Aktie mit denselben Rechten umgewandelt; HF Sinclair uebernahm die NYSE-Notierung.

Die Yahoo-Reihe DINO reicht vor den Umtausch zurueck. Sie bleibt eine Anbieterreihe ohne archivierte Point-in-Time-Version.

Kontrolllauf free-source-research 42636211468 (09.11.2026) mit dieser Zuordnung: `HFC -> DINO` erscheint unter den aufgeloesten Zuordnungen mit Kursen. Wertpapiere mit Fensterluecken: 46 statt 48. Dreimonatsfenster: 694.453 lueckenlos, 31.649 unvollstaendig (vorher 694.244 und 31.898). Der Sechsjahreszeitraum hat sich dabei um vier Wochen verschoben (jetzt ab 09.11.2020); die Differenz ist deshalb nicht allein dieser Zuordnung zuzurechnen.

## Noch offen

1. **FRC -> FRCB**: Reihe vorhanden und lueckenlos. Es fehlt ein Originalbeleg ausserhalb der SEC (FDIC oder OTC Markets), dass FRCB dieselbe Aktie ist. Erst danach uebernehmen.
2. **SIVB, SBNY**: Kursreihen bis zur Handelsaussetzung und danach fehlen. Bei SIVB ist die Behandlung der Stammaktie im Insolvenzplan noch zu pruefen. Die Meldung vom 08.11.2024 betrifft die Beteiligung der Gesellschaft an ihrer Tochter, nicht die Ansprueche der Aktionaere.
3. **HBI, LEG, SEE, QRVO, CMA, DISH**: Kursreihen bis zum Delisting fehlen. Die Abfindung ist belegt. Fuer Aktienabfindungen braucht die Abwicklungsrendite zusaetzlich den Kurs der Erwerberaktie am Vollzugstag.
4. Die Abfindungsbetraege wurden aus Textauszuegen gelesen. Vor einer Verwendung in `settlement_evidence` jeweils das vollstaendige 8-K pruefen.
