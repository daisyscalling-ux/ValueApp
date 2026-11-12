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
  - Japan, Stand 12.11.2026: Shizuoka jetzt aus der japanischen KM1 zum 30.06.2026 (Anforderung 7,02 %, LCR, NSFR; die englische Seite enthält nur die Kapitalmeldung). Chiba und Yokohama FG rechnen nach **internationalem** Standard (die frühere Annahme „Inlandsstandard“ war falsch) und haben KM1 zum 30.09.2026. Resona und Fukuoka rechnen nach Inlandsstandard und werden belegt als „nicht anwendbar“ geführt (Abschnitt unten). Japan Post Bank ist nicht im Universum.
  - China, Stichtag 30.09.2026, Quelle Hongkonger Börse (www1.hkexnews.hk, die H-Aktien-Meldungen der Banken): ICBC, CCB, Bank of China, Agricultural Bank (KM1, CET1-Anforderung = 5 % Mindestquote der NFRA + Zeile 11 mit Erhaltungspuffer 2,5 % und G-SIB-Zuschlag 1,5 %; LCR als Tagesdurchschnitt des Quartals, NSFR). China Merchants Bank: Quartalsbericht, Anforderung 8,25 % laut Bank (5 % + 2,5 % + 0,75 % D-SIB), LCR, keine NSFR. Bank of Communications: nur Kapitalquoten aus der Quartalsmitteilung; der KM1-Bericht liegt nur auf www.bankcomm.com, das aus dieser Umgebung nicht erreichbar ist. Bei ICBC steigt der G-SIB-Zuschlag ab 01.01.2027 auf 2,0 %.
  - Schweiz, Stichtag 30.06.2026 (halbjährlich): BCV und Valiant (KM1, CET1-Anforderung = Zeile 12c: 4,5 % + 3,3 % Puffer nach Anhang 8 ERV + antizyklischer Puffer; LCR, NSFR). Der befristete FINMA-Zuschlag von 1 % für BCV (Art. 45 ERV) gilt für das Gesamtkapital und ist nicht enthalten. Kreditqualität BCV (seit 12.11.2026): CR1 zum selben Stichtag 30.06.2026 (Tabelle 10, PDF-Seite 24, Zeile „Loans“, Spalten a/b): 189 Mio. CHF ausgefallen, 52.702 Mio. CHF nicht ausgefallen, also **0,36 %** (`basel-cr1-default-v1`). Valiant bleibt bei der Kreditqualität offen: CR1 erscheint nur im jährlichen Offenlegungsbericht, und der Stand 31.12.2025 ist über 270 Tage alt. Der Halbjahresbericht 2026 enthält nur KM1 und LIQ1. Cembra: nur Kapitalquoten aus dem Halbjahresbericht, KM1 erscheint nur jährlich.
  - Singapur, Stichtag 30.09.2026: DBS (KM1, CET1-Anforderung = 6,5 % MAS-Mindestquote + Zeile 11; LCR, NSFR). OCBC offen: Website (Incapsula) und SGX-Mitteilungen (Akamai) sperren automatisierte Abrufe, eine SEC-Einreichung gibt es nicht.
  - Quellenart: `basel_pillar3_km1` für KM1-Tabellen, `bank_capital_release` für Kapitalangaben aus dem Zwischen- oder Quartalsbericht, wenn zum Stichtag keine KM1-Tabelle vorliegt (Cembra, China Merchants Bank, Bank of Communications, Shizuoka). Die App beschriftet beide getrennt und zeigt die Fundstelle an (ab valueapp-cf mit dem Quellen-Nachtrag; ältere App-Versionen lehnen `bank_capital_release` ab).

## Kreditqualität mit eigenem CR1-Stichtag (11. November 2026)

Japanische Banken veröffentlichen KM1 vierteljährlich, die Tabelle CR1 (Kreditqualität) aber nur im Jahres- und Halbjahresbericht. Bisher zählte CR1 nur, wenn ihr Stichtag dem KM1-Stichtag entsprach; bei den japanischen Großbanken blieb die Kreditqualität deshalb offen.

Regel: Ein Eintrag in `reviewed-key-metrics.json` kann einen Block `credit` mit eigenem Stichtag tragen (`period`, `defaultedLoans`, `nonDefaultedLoans`, `loanUnit`, `type` = `basel_pillar3_cr1`, `url`, `sha256`, `location`).

| Prüfung | Stelle | Folge bei Verstoß |
|---|---|---|
| Stichtag gültig und nicht nach dem KM1-Stichtag | Import, Kontext, Vorberechnung, App | Kreditqualität offen |
| Höchstalter 270 Tage (wie Bankquartal) | Import, Kontext, Vorberechnung, App | Kreditqualität offen |
| Quelle `basel_pillar3_cr1`, https, SHA-256, Fundstelle | Import, Kontext, Vorberechnung, App | Kreditqualität offen |
| Ausgefallene ≤ 50 % der Kredite, nicht ausgefallene > 0 | Import | Kreditqualität offen |
| Nicht zugleich `defaultedLoans` am Eintrag (Doppelangabe) | Import | Kreditqualität offen |

Ein fehlerhafter CR1-Block verwirft nur die Kreditqualität, nicht die Kapitalquoten (`creditRejected` im Import). Die App zeigt den abweichenden Stichtag und die Fundstelle unter „Berechnung und Datenqualität“ und im Quellenblock.

Werte (Kredite, Zeile 1 der CR1, Millionen Yen, Konzern, Stichtag 31.03.2026):

| Bank | Ausgefallen | Nicht ausgefallen | Quote | Fundstelle |
|---|---:|---:|---:|---|
| MUFG | 1.315.526 | 122.176.641 | 1,07 % | Basel III Disclosure FY2025, PDF-Seite 30 |
| SMFG | 1.379.454 | 110.071.947 | 1,24 % | SMBC Group Annual Report 2026, Basel-Teil, PDF-Seite 6 (gedruckt 62) |
| Mizuho | 905.598 | 91.108.974 | 0,98 % | Integrated Report 2026 (Appendix), PDF-Seite 67 |
| Sumitomo Mitsui Trust | 77.231 | 31.904.850 | 0,24 % | Annual Report 2026 Financial Data Section, PDF-Seite 277 |

Der Bericht von Sumitomo Mitsui Trust stammt aus der Einreichung bei der Singapurer Börse (SGX), weil www.smtg.jp den Jahresbericht 2026 noch nicht bereitstellt. Die quartalsweisen Basel-Dateien auf www.smtg.jp enthalten keine CR1.

Verzerrung: Die CR1-Quote ist bis zu neun Monate älter als die Kapitalquoten. In einer Phase steigender Ausfälle wirkt die Bank dadurch zu gut. Das Höchstalter von 270 Tagen begrenzt den Abstand. Der Stichtag ist in der App sichtbar. Die Halbjahreswerte zum 30.09.2026 erscheinen etwa im Dezember und werden dann eingetragen. Ohne Aktualisierung laufen die Märzwerte am 26.12.2026 ab und die Kreditqualität ist wieder offen.

Probelauf 11.11.2026: Kreditqualität bei 4 Notierungen neu gefüllt (TSE:8306, 8316, 8411, 8309), sonst keine Änderung. Shizuoka bleibt offen, weil keine CR1 erhoben wurde (Quelle `bank_capital_release`). Die übrigen japanischen Banken sind im Abschnitt „Japan: Inlandsstandard und Nachträge“ beschrieben.

## Japan: Inlandsstandard und Nachträge (12. November 2026)

Entscheidung des Nutzers: Banken nach japanischem Inlandsstandard (国内基準) werden „bewusst außerhalb“ geführt, mit Beleg je Bank. Bei der Prüfung zeigte sich, dass zwei der vier vermuteten Inlandsstandard-Banken in Wahrheit nach internationalem Standard rechnen.

| Bank | Standard | Beleg | Ergebnis |
|---|---|---|---|
| Chiba Bank | international | Wertpapierbericht 19.06.2026, PDF-S. 40; KM1 30.09.2026 | CET1 15,36 %, Anforderung 7,03 % (4,5 % + Zeile 11 2,53 %), LCR 129,4 %, NSFR 121,7 % |
| Yokohama FG | international | Kapitalmeldung 14.08.2026 (Fußnote); KM1 30.09.2026 | CET1 14,93 %, Anforderung 7,00 %, LCR 120,1 %; NSFR folgt (Fußnote der Bank) |
| Shizuoka FG | international | KM1 30.06.2026 (japanische Seite) | CET1 16,24 %, Anforderung 7,02 %, LCR 162,0 %, NSFR 106,4 % |
| Resona HD | Inland | TDnet 07.08.2026: 国内基準 12,65 %; internationale Werte dort nur 〔参考〕 | CET1-Puffer und LCR nicht anwendbar |
| Fukuoka FG | Inland | Meldung 12.08.2026 (Core Capital 11,66 %); Wertpapierbericht 19.06.2026, PDF-S. 31: „当社は、国内基準を適用“ | CET1-Puffer und LCR nicht anwendbar |

Fundstellen: Die KM1 von Yokohama FG liegt beim IR-Dokumentdienst der Bank (ssl4.eir-parts.net). Die Website lädt die Liste per Skript; die Liste wurde direkt abgerufen, ohne Bot-Schutz zu umgehen. Die Fukuoka-Meldung stammt von der Fukuokaer Börse (www.fse.or.jp), weil die Website der Bank automatisierte Abrufe sperrt.

**Regel Inlandsstandard** (`domesticStandard` in `reviewed-key-metrics.json`):
- Beleg je Bank: https, SHA-256, Fundstelle, Stichtag höchstens 270 Tage alt.
- Beleg für den LCR-Geltungsbereich (`domesticStandardLcrRule`): FSA-Bekanntmachung Nr. 62/2014, Art. 2 (PDF-Seite 13). Die Konzern-LCR gilt nur für Holdings mit Banktöchtern mit Auslandsgeschäftsstellen; genau diese Banken müssen den internationalen Kapitalstandard anwenden.
- Geprüft wird in Import, `regulatory_context.py`, `regulatory-context.ts` (`verifiedDomesticStandard`) und App (`src/lib/domestic-standard.ts`). Fehlt ein Beleg oder ist er zu alt, bleiben die Kennzahlen einfach offen.
- Messung: CET1-Puffer und LCR `by_design`. Die Kreditqualität bleibt anwendbar und offen.
- Die gemeldete Quote nach Inlandsstandard wird nur angezeigt, nicht bewertet.

**Verzerrung:** Inlandsstandard-Banken haben zwei Finanzkennzahlen weniger. Ihr Teilscore stützt sich damit stärker auf Kurs- und Bewertungsdaten. Ein Vergleich mit CET1-Banken wäre aber falsch: Core Capital hat andere Abzüge, und die Mindestquote liegt bei 4 % statt 7 %. Die Referenzwerte nach internationalem Standard, die Resona freiwillig nennt, sind keine Aufsichtsgröße und werden nicht verwendet.

## Kreditqualität der japanischen Regionalbanken (12. November 2026)

CR1 zum 31.03.2026 aus den Jahresoffenlegungen, als `credit`-Block mit eigenem Stichtag (gleiche Regel wie bei den Großbanken):

| Bank | Ausgefallen / nicht ausgefallen (Mio. Yen) | Quote | Fundstelle |
|---|---|---:|---|
| Chiba (Bank, Konzern) | 170.533 / 14.018.136 | 1,20 % | Offenlegungsheft 2026, Kapitel „自己資本の充実の状況“, Abschnitt „銀行連結“, PDF-S. 52 |
| Yokohama FG (Holding) | 251.654 / 17.344.234 | 1,43 % | Integrierter Bericht 2026, Datenteil, PDF-S. 105 |
| Shizuoka FG (Holding) | 93.087 / 10.863.276 | 0,85 % | Integrierter Bericht 2026, Anhang, Abschnitt „銀行持株“, PDF-S. 52 |

Die Halbjahresoffenlegung zum 30.09.2025 ist älter als 270 Tage und wurde deshalb nicht verwendet.

Probelauf: Kreditqualität bei TSE:8331, 7186 und 5831 gefüllt, sonst keine Änderung. Die Werte laufen am 26.12.2026 ab (wie bei den Großbanken; die Quartalsaufgabe im Dezember sucht die Halbjahreswerte).

Weiter offen: Resona und Fukuoka. **Entscheidung des Nutzers (12.11.2026): offen lassen.**
- Beide Websites sperren automatisierte Abrufe: resona-gr.co.jp mit Akamai „Access Denied“, Fukuoka FG siehe oben.
- Die Säule-3-Offenlegung mit CR1 ist deshalb nicht prüfbar zu beschaffen.
- Verworfene Alternative: die risikobehafteten Kredite (リスク管理債権) aus dem Wertpapierbericht über EDINET. Sie haben eine andere Abgrenzung (inklusive drei Monate überfälliger und gestundeter Kredite) und wären mit CR1 nicht vergleichbar.
- Angezeigter Grund: „Geprüfte Kreditqualität fehlt“.
- Neu prüfen, falls die Bank die Offenlegung über TDnet oder einen offenen Host bereitstellt.

## Britische Banken: notleidende Kredite aus UK CR1 (12. November 2026)

Britische Banken veröffentlichen statt der Basel-CR1 (ausgefallen / nicht ausgefallen) die Tabelle **UK CR1** nach EBA-Definition (performing / non-performing). Das ist dieselbe Vorlage wie EU CR1.

Neu in `reviewed-key-metrics.json` ist ein `credit`-Block mit `type = uk_pillar3_cr1` und den Feldern `nonPerformingLoans` und `performingLoans`. Der Import setzt die Methode `creditMethod = uk-cr1-npl-v1`. Kontext, Vorberechnung und App lassen den Wert nur zu, wenn Methode und Quellenart zusammenpassen und der Block mit eigenem Stichtag belegt ist. Die App bezeichnet ihn als „Notleidende Kredite (UK CR1)“.

| Bank | Non-performing / performing (Zeile 010 Loans and advances) | NPL-Quote | Fundstelle |
|---|---|---:|---|
| NatWest | 5.036 / 450.574 Mio. £ | 1,11 % | Säule 3 H1 2026, PDF-S. 36 |
| Standard Chartered | 5.785 / 433.417 Mio. $ | 1,32 % | Säule 3 HY 2026, Tabelle 24, PDF-S. 28 |
| HSBC | 25,0 / 1.488,3 Mrd. $ | 1,65 % | Säule 3 zum 30.06.2026 (bei der HKMA hinterlegt), Tabelle 23, PDF-S. 30 |

Probelauf: Kreditqualität bei LSE:NWG, LSE:STAN und NYSE:HSBC gefüllt, sonst keine Änderung.

Verzerrung: „Non-performing“ ist breiter als „defaulted“. Die drei Banken wirken dadurch eher schlechter, nicht besser.

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

## Aktiengattungen desselben Konzerns (10. November 2026)

Chinesische Banken notieren A-Aktien (Shanghai) und H-Aktien (Hongkong). Die Kennzahlen gelten für den Konzern. Geprüfte Einträge in `reviewed-key-metrics.json` können deshalb weitere ISINs desselben Konzerns unter `shareClassIsins` führen (Quelle: HKEX List of Securities). Der Import legt sie mit `shareClassOf` (Haupt-ISIN) ab. In `regulatory_context.py` trägt jeder Eintrag `issuerIsin`. Depositary Receipts übernehmen die Quoten einer im selben Lauf geprüften Stammaktie desselben Konzerns: bei EU-Banken über die LEI, bei internationalen über `issuerIsin`. Betroffen sind ICBC, CCB, Bank of China, ABC, China Merchants Bank und Bank of Communications.

## Depositary Receipts ohne Stammaktie im Universum (12. November 2026)

Die Regel „ein DR übernimmt die Kennzahlen einer im selben Lauf geprüften Stammaktie“ greift nicht, wenn das DR im Universum allein steht:
- **HSBC:** Der Universumsexport ersetzt die Londoner Pence-Notierung HSBA.L durch das NYSE-ADR.
- **ABN AMRO:** An Euronext Amsterdam handeln nur Depositary Receipts der Stiftung STAK AAB.

Für solche Fälle gibt es das Register `reviewed-depositary-listings.json` (Methode `reviewed-standalone-depositary-v1`).

Voraussetzungen:
- Notierung, ISIN, Währung und Wertpapierart (`dr`) stimmen exakt.
- Der Konzernschlüssel stimmt (LEI bzw. Emittenten-ISIN).
- Die Prüfung ist gültig.
- Ein Beleg mit https, SHA-256 und Text liegt vor.

Der Datensatz trägt `standaloneDepositary`. Die App prüft die Kennzeichnung erneut und zeigt sie unter „Berechnung und Datenqualität“.

Belege:
- HSBC: Investor Relations von HSBC USA (ADR-Programm an der NYSE, 1 ADS = 5 Stammaktien).
- ABN AMRO: Euronext-Produktseite (ABN AMRO BANK N.V., NL0011540547) und GLEIF-Zuordnung der ISIN zur LEI. abnamro.com lehnt automatisierte Abrufe ab (HTTP 503).

Probelauf:
- ABN AMRO: CET1-Puffer, LCR und Kreditqualität gefüllt.
- HSBC: CET1-Puffer und LCR gefüllt. Eine Kreditqualität (CR1) liegt in keiner Quelle vor.
- Offenes Gewicht 1,2 → 1,1 %.

Nordea Finnland (NDA-FI.HE), Nachtrag 12.11.2026:
- Die Notierung ist jetzt bestätigt. Das Protokoll von precompute-3tage (12.11.2026, 12:03 UTC) zeigt, dass ROIC `HEL:NDA_FI` anbietet (Aktie, primär, ISIN-Land FI). Der Abgleich lehnte sie nur ab, weil er bei Nordic-Notierungen bisher nur einbuchstabige Gattungen kannte.
- Behoben in `listing_identity.py` und `listing-identity.ts`, identisch in valueapp-cf. Das Trennzeichen vor einem oder zwei Großbuchstaben am Ende wird vereinheitlicht, sonst bleibt alles exakt.
- Weiterhin abgelehnt: `HEL:NDA_SE`, `HEL:NDA`, `HEL:NDAFI`, `STO:NDA_FI` und `STO:HMB` gegen `HM-B.ST`.
- Wirksam ab dem nächsten precompute-3tage-Lauf, der die Notierung neu auflöst.
