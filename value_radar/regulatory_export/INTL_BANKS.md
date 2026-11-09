# Banken außerhalb von EU/EWR und USA

Stand 09.11.2026. Gemeinsames Format `intl-bank-metrics-v1` für veröffentlichte Basel-Kennzahlen von Bankkonzernen.

## Quellen

- **APRA, Authorised deposit-taking institution centralised publication** (höchste Konsolidierungsebene, quartalsweise; Tabelle 1 Kapital, Tabelle 3 LCR/NSFR): https://www.apra.gov.au/quarterly-authorised-deposit-taking-institution-statistics. Lizenz CC BY 3.0 AU.
- Geplant: **Basel-Offenlegung KM1 „Key metrics“** aus den Säule-3-Berichten der Banken. Dort stehen CET1, Kapitalpuffer-Anforderung, Leverage Ratio, LCR und NSFR einheitlich.

## Zuordnung (`intl-bank-map.json`)

Eine notierte Stammaktie (ISIN) wird nur dem Konzern zugeordnet, dessen Zahlen veröffentlicht werden, und nur, wenn die notierte Gesellschaft selbst dieser Konzern ist. Depositary Receipts und Holdings ohne Banklizenz bleiben offen.

- Zugeordnet: Commonwealth Bank of Australia, National Australia Bank, Westpac.
- Offen: ANZ Group Holdings (Holding ohne Banklizenz; APRA veröffentlicht die Banktochter).

Im Universum sind nur US-OTC-Notierungen dieser Banken. Die drei Stammaktien (OTC:CBAUF, OTC:NAUBF, OTC:WEBNF) werden übernommen, die ADRs nicht.

## Ablauf

`import_intl_banks.py APRA.xlsx daten/regulatory/intl-bank-metrics.json` → `regulatory_context.py` (Abschnitt `intlBanks`) → `regulatory-context.ts` (`verifiedIntlCapital`, Höchstalter 270 Tage, eigene Quellkennung je Kennzahl) → App (`src/lib/intl-bank.ts`).

Bewertet werden die LCR und, sobald offengelegt, der Abstand der CET1-Quote zur Anforderung. Die APRA veröffentlicht keine bankspezifische Anforderung, deshalb bleibt der Kapitalpuffer bei den australischen Banken offen.

## Aktualisierung

Die APRA veröffentlicht vierteljährlich. Die neue Datei herunterladen und den Import erneut ausführen. Der Dateiname enthält den Zeitraum, siehe die Seite oben.
