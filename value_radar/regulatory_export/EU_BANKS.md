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

## Säule 3 aus dem EBA Pillar 3 Data Hub (10. November 2026)

Seit Januar 2026 veröffentlicht die EBA die Säule-3-Offenlegung großer EU-Institute zentral und unverändert, als PDF und als XBRL-CSV. Die Originaldateien liegen öffentlich unter `https://errp.eba.europa.eu/public-documents/<Modul>/input/<LEI>.<CON|IND>_<Land>_PILLAR3…_<Stichtag>_<Zeitstempel>.zip`. Für die Bewertung verwenden wir die Tabelle **EU KM1** (Modul CODIS, Taxonomie 4.2, Tabelle K_61.00, Spalte T).

**Ablauf (quartalsweise, von Hand):**
1. `node p3dh_collect.js p3dh-submissions.json` liest die öffentliche Einreichungsliste im EDAP-Portal (Power BI, ohne Anmeldung) und speichert die Adressen der CODIS-Einreichungen. Beim ersten Lauf waren es 1.999 von 7.936 Einreichungen.
2. `python import_eu_pillar3.py p3dh-submissions.json ../daten/regulatory/eu-pillar3-km1.json` lädt je LEI aus `eu-bank-map.json` die jüngste Einreichung (konsolidiert vor Einzelinstitut, bei HTTP 404 die nächstältere) und prüft sie:
   - Taxonomie 4.2
   - `entityID` = LEI und Konsolidierungskreis
   - `refPeriod` = Stichtag im Dateinamen, höchstens 270 Tage alt
   - Kapitalkette CET1 ≤ Tier 1 ≤ Gesamtkapital

   Je Bank werden Prüfsumme und Quelladresse gespeichert.
3. `regulatory_context.py` hängt LCR (`eba-p3dh-km1-lcr-v1`) und vollständige CET1-Anforderung (`eba-p3dh-km1-cet1-requirement-v1`) an. Die bisherige EZB-Teilanforderung bleibt als Rückfall. `regulatory-context.ts` und die App (`src/lib/eu-bank.ts`) prüfen erneut: Methode, Alter, Prüfsumme, Quellhost und Wertebereich, den Puffer rechnen sie selbst nach.

**CET1-Anforderung** = 4,5 % + CET1-Anteil der SREP-Zusatzanforderung (EU 7e) + kombinierte Kapitalpufferanforderung (Zeile 11). Sie wird übernommen, wenn die Gesamtanforderung (EU 11a) auf 0,05 Prozentpunkte der SREP-Gesamtanforderung (EU 7g) plus kombinierter Pufferanforderung entspricht. Fehlt EU 7e und beträgt die SREP-Gesamtanforderung genau 8 % (keine Säule-2-Zusatzanforderung), ist der CET1-Anteil 0. Das ist so gekennzeichnet (Pekao, PKO). Der Puffer wird mit der CET1-Quote desselben KM1-Stichtags berechnet.

**Erster Import:** 33 von 33 Banken, Stichtage 31.03.–30.09.2026, alle mit LCR und NSFR. 32 haben eine vollständige Anforderung. Offen bleibt BBVA, weil die Werte auf ganze Prozent gerundet sind (OCR 13 % ≠ SREP 10 % + Puffer 4 %). Bei KBC war die neueste Einreichung nicht abrufbar (404), verwendet wird der 31.03.2026.

**Probelauf** (Kette auf einer Kopie von main, gegen main ohne die Änderung):
- Bank-LCR-Lücken 93 → 50
- CET1-Puffer-Lücken 56 → 47
- Banken 55,2 → 58,0, gesamt 77,6 → 77,9

## Banken nur aus der Säule 3 (10. November 2026)

Elf EU-Banken des Universums stehen nicht in der EBA-Transparenzübung (`open`). Zehn davon reichen unter einer eindeutigen LEI im Pillar 3 Data Hub ein. Die LEI stammt aus GLEIF (`filter[isin]`, genau ein Treffer). Diese zehn stehen jetzt unter `pillar3Only` in `eu-bank-map.json`: Crédit Agricole S.A., Eurobank, Piraeus, Erste Group, mBank, Erste Bank Polska, Bank Millennium, Ringkjøbing Landbobank, Sydbank und Sparebanken Norge. Eurobank und Piraeus reichen bereits unter der LEI der börsennotierten Nachfolgegesellschaft ein. Offen bleiben Bank of Ireland (keine eindeutige LEI über die ISIN) und Storebrand (Versicherungskonzern).

Für diese Banken kommen CET1-, Tier-1-, Gesamtkapital- und Leverage-Quote, Anforderung und LCR **ausschließlich aus EU KM1** (`capitalSource: eba_p3dh_km1`, Feldcodes `P3DH:K_61.00/<Zeile>`), mit derselben Prüfung wie oben. Die Daten dürfen höchstens 270 Tage alt sein, und die Quelle muss die Originaldatei im Hub sein. Eine NPL-Quote gibt es dafür noch nicht: Die Kreditqualitätstabellen der Säule 3 sind noch nicht ausgewertet.

**Ergebnis:**
- 9 von 10 Banken übernommen.
- Bank Millennium ist abgelehnt: Ihre letzte Einreichung vom 31.12.2025 ist über 270 Tage alt.
- Bei Crédit Agricole S.A. bleibt die Anforderung offen: Sie meldet den CET1-Anteil der Säule-2-Anforderung als 0,9281 statt 0,009281, also in Prozent statt als Anteil. Er wird nicht stillschweigend umgerechnet.
- Bei Sydbank bleibt die Anforderung ebenfalls offen, weil die SREP-Zeilen fehlen.

**Probelauf:**
- Bank-LCR-Lücken 50 → 41
- CET1-Puffer 47 → 40
- Banken 58,0 → 59,0
