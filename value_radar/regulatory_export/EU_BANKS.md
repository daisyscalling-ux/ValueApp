# Europäische Banken: EBA-Kapital, EZB-Anforderung, NPL

Stand 09.11.2026. Erweitert die Bankdaten von US-Holdings (FR Y-9C) auf Banken in EU und EWR.

## Quellen

- **EBA EU-wide Transparency Exercise 2025**, Full database: `tr_oth.csv` (Kapital, Leverage), `tr_cre.csv` (Kreditqualität), `TR_Metadata.xlsx` (120 Institute mit LEI). Vier Stichtage, der jüngste ist der 30.06.2025. https://www.eba.europa.eu/risk-and-data-analysis/risk-analysis/eu-wide-transparency-exercise
- **EZB-Bankenaufsicht, Pillar 2 requirement**: P2R je direkt beaufsichtigter Bank für 2024, 2025 und 2026. https://www.bankingsupervision.europa.eu/activities/srep/pillar-2-requirement/html/index.en.html
- **GLEIF**: ISIN → LEI (`lei-records?filter[isin]=…`), nur bei genau einem Treffer.

Die Rohdateien (rund 140 MB) werden nicht eingecheckt. `daten/regulatory/eu-bank-capital.json` enthält die übernommenen Werte mit Quell-URLs und SHA-256 der Dateien.

## Zuordnung (`eu-bank-map.json`)

33 Banken: Die LEI aus GLEIF muss mit der berichtenden LEI bei der EBA übereinstimmen. Der EZB-Name ist von Hand geprüft (24 Banken unter direkter EZB-Aufsicht). Dänemark, Schweden, Norwegen und Polen haben keine P2R. Offen und begründet im Abschnitt `open`:

- Crédit Agricole (EBA meldet die Gruppe, nicht Crédit Agricole S.A.);
- Eurobank und Piraeus (EBA 2025 noch mit der LEI der früheren Holding);
- Bank of Ireland (keine eindeutige GLEIF-Zuordnung);
- Erste Group, mBank, Bank Millennium, Erste Bank Polska, Sydbank, Ringkjøbing, Sparebanken Norge, Storebrand (nicht in der EBA-Stichprobe 2025).

Depositary Receipts (z. B. NYSE:SAN, NYSE:ING) übernehmen seit 10.11.2026 den Eintrag der im selben Lauf geprüften Stammaktie mit derselben ISIN (`depositaryOf`); die Quoten gelten für den Konzern. Ohne geprüfte Stammaktie (ABN-AMRO-Zertifikate) bleiben sie offen.

## Berechnung (`import_eu_banks.py`)

- Kapital: CET1 (transitional, Position 2520140), Tier 1, Gesamtkapital, CET1 fully loaded, Leverage Ratio, jeweils vom jüngsten Stichtag. CET1 ≤ Tier 1 ≤ Gesamtkapital muss gelten, sonst wird die Bank abgelehnt.
- NPL: notleidende / gesamte Kredite und Darlehen (Position 2520603, konsolidiert, ohne Aufteilung nach Portfolio oder Land).
- Teilanforderung CET1: 4,5 % + 2,5 % + 56,25 % × P2R des Jahres des Kapitalstichtags. Ohne antizyklische, systemische und O-SII/G-SII-Puffer. 56,25 % ist der gesetzliche Mindestanteil; die Aufsicht kann mehr verlangen.

Ergebnis 09.11.2026: 33 Banken, alle mit NPL, 24 mit Teilanforderung, nichts abgelehnt. In der täglichen Vorberechnung werden daraus 37 Notierungen (7 Depositary Receipts abgelehnt). Zusammen mit den US-Holdings haben 44 statt 7 Bank-Notierungen geprüfte Kapitaldaten.

## Weiterleitung

`regulatory_context.py` schreibt `euBanks` in `cf_regulatory_context.json`. `regulatory-context.ts` übernimmt EU-Daten nur, wenn keine US-Holdingdaten vorliegen, prüft Identität, Stichtag (höchstens 730 Tage, Nutzerentscheidung), Prüffrist der Zuordnung, Quellprüfsummen und Kapitalhierarchie und rechnet den Puffer neu. Belegt gelten CET1 und Kreditqualität. Die bankspezifische Anforderung bleibt offen, weil sie nur teilweise belegt ist; LCR bleibt offen.

## Aktualisierung

Die EBA veröffentlicht die nächste Transparency Exercise üblicherweise im Dezember. Dann die neuen Dateien und die neue P2R-Tabelle in einen Ordner laden, in `import_eu_banks.py` `EBA_BASE` und `EXERCISE` anpassen, die Zuordnung prüfen (neue Institute, LEI-Änderungen) und so ausführen:

    python value_radar/regulatory_export/import_eu_banks.py ORDNER value_radar/daten/regulatory/eu-bank-capital.json
