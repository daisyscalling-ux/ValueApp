# Banken außerhalb von EU/EWR und USA

Stand 09.11.2026. Gemeinsames Format `intl-bank-metrics-v1` für veröffentlichte Basel-Kennzahlen von Bankkonzernen.

## Quellen

- **APRA, Authorised deposit-taking institution centralised publication** (höchste Konsolidierungsebene, quartalsweise; Tabelle 1 Kapital, Tabelle 3 LCR/NSFR): https://www.apra.gov.au/quarterly-authorised-deposit-taking-institution-statistics. Lizenz CC BY 3.0 AU.
- **Basel-Offenlegung KM1 und CR1** aus den Säule-3-Berichten der Banken, von Hand gelesen und mit Fundstelle (Blatt/Seite, Zeile, Spalte) sowie SHA-256 des Originals in `reviewed-key-metrics.json` abgelegt. Der Import prüft Pflichtfelder, Kapitalhierarchie, Quelle und dass die Anforderung genau der Summe ihrer Bestandteile entspricht.
  - Kanada, Stichtag 31.07.2026: RBC, TD, CIBC, Scotiabank. CET1-Anforderung = 4,5 % + KM1-Zeile 11 + Domestic Stability Buffer 3,0 % (OSFI, Meldung vom 19.06.2026). Bei RBC deckt sich das mit der ausgewiesenen Zeile 12a (11,1 %). Ausgefallene Kredite aus CR1. Keine LCR in KM1.
  - Vereinigtes Königreich, Stichtag 30.09.2026: HSBC, NatWest, Standard Chartered. CET1-Anforderung = 4,5 % + UK-7a (Säule 2A in CET1) + Zeile 11 (kombinierter Puffer). LCR (12-Monats-Durchschnitt) und NSFR aus KM1. CR1 ist in den Quartalsberichten nicht enthalten.
  - Offen: BMO (Website antwortet aus dieser Umgebung nicht), Lloyds (Dokumentlinks werden per JavaScript geladen).

## Zuordnung (`intl-bank-map.json`)

Eine notierte Stammaktie (ISIN) wird nur dem Konzern zugeordnet, dessen Zahlen veröffentlicht werden, und nur, wenn die notierte Gesellschaft selbst dieser Konzern ist. Depositary Receipts und Holdings ohne Banklizenz bleiben offen.

- Zugeordnet: Commonwealth Bank of Australia, National Australia Bank, Westpac.
- Offen: ANZ Group Holdings (Holding ohne Banklizenz; APRA veröffentlicht die Banktochter).

Im Universum sind nur US-OTC-Notierungen dieser Banken. Die drei Stammaktien (OTC:CBAUF, OTC:NAUBF, OTC:WEBNF) werden übernommen, die ADRs nicht.

## Ablauf

`import_intl_banks.py APRA.xlsx daten/regulatory/intl-bank-metrics.json` → `regulatory_context.py` (Abschnitt `intlBanks`) → `regulatory-context.ts` (`verifiedIntlCapital`, Höchstalter 270 Tage, eigene Quellkennung je Kennzahl) → App (`src/lib/intl-bank.ts`).

Bewertet werden der Abstand der CET1-Quote zur Anforderung (wo offengelegt), die LCR und die Quote ausgefallener Kredite (CR1). Die APRA veröffentlicht keine bankspezifische Anforderung, deshalb bleibt der Kapitalpuffer bei den australischen Banken offen.

Probelauf 09.11.2026: 10 internationale Notierungen mit Kapitaldaten, insgesamt 54 statt 47 Banken. 4 Depositary Receipts abgelehnt.

## Aktualisierung

Die APRA veröffentlicht vierteljährlich. Die neue Datei herunterladen und den Import erneut ausführen. Der Dateiname enthält den Zeitraum, siehe die Seite oben.

KM1-Werte müssen je Quartal neu gelesen werden: neue Werte, Fundstelle und SHA-256 in `reviewed-key-metrics.json` eintragen. Werte älter als 270 Tage zählen nicht mehr.
