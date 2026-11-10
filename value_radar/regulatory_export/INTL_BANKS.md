# Banken außerhalb von EU/EWR und USA

Stand 09.11.2026. Gemeinsames Format `intl-bank-metrics-v1` für veröffentlichte Basel-Kennzahlen von Bankkonzernen.

## Quellen

- **APRA, Authorised deposit-taking institution centralised publication** (höchste Konsolidierungsebene, quartalsweise; Tabelle 1 Kapital, Tabelle 3 LCR/NSFR): https://www.apra.gov.au/quarterly-authorised-deposit-taking-institution-statistics. Lizenz CC BY 3.0 AU.
- **Basel-Offenlegung KM1 und CR1** aus den Säule-3-Berichten der Banken, von Hand gelesen und mit Fundstelle (Blatt/Seite, Zeile, Spalte) sowie SHA-256 des Originals in `reviewed-key-metrics.json` abgelegt. Der Import prüft Pflichtfelder, Kapitalhierarchie, Quelle und dass die Anforderung genau der Summe ihrer Bestandteile entspricht.
  - Kanada, Stichtag 31.07.2026: RBC, TD, CIBC, Scotiabank. CET1-Anforderung = 4,5 % + KM1-Zeile 11 + Domestic Stability Buffer 3,0 % (OSFI, Meldung vom 19.06.2026). Bei RBC deckt sich das mit der ausgewiesenen Zeile 12a (11,1 %). Ausgefallene Kredite aus CR1. Keine LCR in KM1.
  - Vereinigtes Königreich, Stichtag 30.09.2026: HSBC, NatWest, Standard Chartered. CET1-Anforderung = 4,5 % + UK-7a (Säule 2A in CET1) + Zeile 11 (kombinierter Puffer). LCR (12-Monats-Durchschnitt) und NSFR aus KM1. CR1 ist in den Quartalsberichten nicht enthalten.
  - BMO (31.07.2026) und Lloyds (30.09.2026) über ihre SEC-Einreichungen (Form 6-K), weil beide Websites automatisierte Abrufe sperren. Der Workflow `sec-bank-filings` lädt die in `sec-bank-filings.json` gelisteten Einreichungen mit dem Secret `SEC_USER_AGENT` und legt sie mit SHA-256 als Artefakt ab. BMO: Quartalsbericht (MD&A), Anforderung 11,0 % laut Tabelle 11 (4,5 % + 3,5 % Säule-1-Puffer + 3,0 % DSB), LCR, NSFR. Lloyds: nur Kapitalquoten und Leverage aus dem Q3-Zwischenbericht; die Säule-3-Tabelle mit Anforderung und LCR liegt nur auf der gesperrten Website. Quellenart jeweils `bank_capital_release`.
  - Japan, Stichtag 30.06.2026: MUFG und SMFG (KM1, Anforderung = 4,5 % + Zeile 11; LCR, NSFR), Mizuho (Basel-Überblick der Bank: CET1-Mindestquote 8,0 % ohne antizyklischen Puffer, LCR; Tier 1 und Gesamtkapital aus der Mitteilung vom 14.08.2026), Shizuoka Financial Group (nur Kapitalquoten, internationaler Standard, keine Anforderung offengelegt). Japan veröffentlicht keine bankspezifische Säule-2-Anforderung.
  - Japan, Nachtrag: Sumitomo Mitsui Trust Group (neue Domain www.smtg.jp; KM1, Anforderung = 4,5 % + Zeile 11 mit 0,5 % D-SIB-Zuschlag, LCR, NSFR).
  - Japan offen: Japan Post Bank rechnet nachweislich nach dem Inlandsstandard („Core Capital“, nicht mit CET1 vergleichbar). Resona und Fukuoka sperren automatisierte Abrufe (Akamai). Chiba und Yokohama Financial Group (früher Concordia, jetzt www.yokohamafg.co.jp) laden ihre Dokumentlisten per Skript. Für diese vier wird der Inlandsstandard erwartet. Banken nach japanischem Inlandsstandard melden eine „Core Capital Ratio“, die mit CET1 nicht vergleichbar ist.
  - China, Stichtag 30.09.2026, Quelle Hongkonger Börse (www1.hkexnews.hk, die H-Aktien-Meldungen der Banken): ICBC, CCB, Bank of China, Agricultural Bank (KM1, CET1-Anforderung = 5 % Mindestquote der NFRA + Zeile 11 mit Erhaltungspuffer 2,5 % und G-SIB-Zuschlag 1,5 %; LCR als Tagesdurchschnitt des Quartals, NSFR). China Merchants Bank: Quartalsbericht, Anforderung 8,25 % laut Bank (5 % + 2,5 % + 0,75 % D-SIB), LCR, keine NSFR. Bank of Communications: nur Kapitalquoten aus der Quartalsmitteilung; der KM1-Bericht liegt nur auf www.bankcomm.com, das aus dieser Umgebung nicht erreichbar ist. Bei ICBC steigt der G-SIB-Zuschlag ab 01.01.2027 auf 2,0 %.
  - Schweiz, Stichtag 30.06.2026 (halbjährlich): BCV und Valiant (KM1, CET1-Anforderung = Zeile 12c: 4,5 % + 3,3 % Puffer nach Anhang 8 ERV + antizyklischer Puffer; LCR, NSFR). Der befristete FINMA-Zuschlag von 1 % für BCV (Art. 45 ERV) gilt für das Gesamtkapital und ist nicht enthalten. Cembra: nur Kapitalquoten aus dem Halbjahresbericht, KM1 erscheint nur jährlich.
  - Singapur, Stichtag 30.09.2026: DBS (KM1, CET1-Anforderung = 6,5 % MAS-Mindestquote + Zeile 11; LCR, NSFR). OCBC offen: Website (Incapsula) und SGX-Mitteilungen (Akamai) sperren automatisierte Abrufe, eine SEC-Einreichung gibt es nicht.
  - Quellenart: `basel_pillar3_km1` für KM1-Tabellen, `bank_capital_release` für Kapitalangaben aus dem Zwischen- oder Quartalsbericht, wenn zum Stichtag keine KM1-Tabelle vorliegt (Cembra, China Merchants Bank, Bank of Communications, Shizuoka). Die App beschriftet beide getrennt und zeigt die Fundstelle an (ab valueapp-cf mit dem Quellen-Nachtrag; ältere App-Versionen lehnen `bank_capital_release` ab).

## Zuordnung (`intl-bank-map.json`)

Eine notierte Stammaktie (ISIN) wird nur dem Konzern zugeordnet, dessen Zahlen veröffentlicht werden, und nur, wenn die notierte Gesellschaft selbst dieser Konzern ist. Holdings ohne Banklizenz bleiben offen. Depositary Receipts mit derselben ISIN übernehmen ab 10.11.2026 den Eintrag einer im selben Lauf geprüften Stammaktie, weil Kapital-, Liquiditäts- und Kreditquoten den Konzern beschreiben, nicht die Aktie (`depositaryOf`). Ohne geprüfte Stammaktie bleibt das DR offen.

- Zugeordnet: Commonwealth Bank of Australia, National Australia Bank, Westpac.
- Offen: ANZ Group Holdings (Holding ohne Banklizenz; APRA veröffentlicht die Banktochter).

Im Universum sind nur US-OTC-Notierungen dieser Banken. Die drei Stammaktien (OTC:CBAUF, OTC:NAUBF, OTC:WEBNF) werden übernommen, die ADRs über `depositaryOf` ebenfalls.

## Ablauf

`import_intl_banks.py APRA.xlsx daten/regulatory/intl-bank-metrics.json` → `regulatory_context.py` (Abschnitt `intlBanks`) → `regulatory-context.ts` (`verifiedIntlCapital`, Höchstalter 270 Tage, eigene Quellkennung je Kennzahl) → App (`src/lib/intl-bank.ts`).

Bewertet werden der Abstand der CET1-Quote zur Anforderung (wo offengelegt), die LCR und die Quote ausgefallener Kredite (CR1). Die APRA veröffentlicht keine bankspezifische Anforderung, deshalb bleibt der Kapitalpuffer bei den australischen Banken offen.

Probelauf 09.11.2026: 31 internationale Notierungen mit Kapitaldaten (8 Japan, 6 China, 3 Schweiz, 1 Singapur, dazu BMO und zwei Lloyds-Notierungen), insgesamt 75 von 142 Banken. Depositary Receipts wurden damals abgelehnt; seit 10.11.2026 kommen 15 ADRs über ihre Stammaktie hinzu.

Eine Anforderung ist nur bei offengelegten Bestandteilen gesetzt; Einträge ohne Anforderung (z. B. Shizuoka) liefern nur die Kapitalquoten.

## Aktualisierung

Die APRA veröffentlicht vierteljährlich. Die neue Datei herunterladen und den Import erneut ausführen. Der Dateiname enthält den Zeitraum, siehe die Seite oben.

KM1-Werte müssen je Quartal neu gelesen werden: neue Werte, Fundstelle und SHA-256 in `reviewed-key-metrics.json` eintragen. Werte älter als 270 Tage zählen nicht mehr.
