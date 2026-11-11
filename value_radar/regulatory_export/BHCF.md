# Consolidated holding-company capital evidence

The manually supplied `BHCF20260630.ZIP` and `Financial_Download_Dictionary.xlsx`
produce `daten/regulatory/bhcf-import.json`. The importer stores source hashes,
dictionary rows and effective dates, reporting period, raw ratios and normalized
fractions. It does not publish the source spreadsheet or the full financial archive.

Dictionary sheet `Financial`: BHCAP793 (row 290) is CET1; BHCA7206 (243) is
Tier 1, BHCA7205 (242) total capital, BHCA7204 (241) Tier 1 leverage.
These are distinct ratios. Units are percentage points, as documented in the
Federal Reserve FR Y-9C HC-R form linked in the export. Normalize by 100 once.
No parent-only BHCP or advanced-approaches BHCW values are substituted.

## Repeat for a new quarter

Download the official FFIEC BHCF archive and current dictionary manually. The
FFIEC download currently requires an interactive browser check. No automated
bypass is implemented. Locally install `openpyxl`, then run from the repo root:

```sh
python value_radar/regulatory_export/import_bhcf.py --archive /path/BHCF20260630.ZIP --dictionary /path/Financial_Download_Dictionary.xlsx --output value_radar/daten/regulatory/bhcf-import.json
python -m unittest discover -s value_radar/regulatory_export -p 'test_*.py'
```

Review and commit the JSON through a PR. `regulatory-daily` automatically
rebuilds `holding-links.json` using the FDIC holding RSSD identifier. The daily
job does **not** refresh the manually supplied holding snapshot. Its age remains
visible and is marked stale after 180 days; original publication time is unknown.
The data is not approved for point-in-time backtests.

## Scope boundaries

A matching RSSD identifies a holding reporting entity, possibly an intermediate
US holding of a foreign bank. It does not establish the listed ultimate parent's
identity. Name-only universe matches remain review candidates. Reviewed entries
in `holding-stock-map.json` authorize capital observations for exact NYSE common
stock listings only. `holding_stocks.py` checks the holding identifier/name,
listing name, unique universe symbol, review dates and snapshot age. It publishes
the ratios and evidence in `coverage.json`; it never creates a score. FDIC entity
and holding reporting periods are retained separately, including mismatches.
LCR, credit quality at holding level, bank-specific capital requirements, and
insurer solvency remain separate work. Missing entries stay null, never zero.

Initial June 2026 archive: 3,599 unique entities; 380 with at least one selected
ratio. Rows without these ratios are counted, not presented as covered entities.

The initial reviewed set is JPM, BAC, C, GS, WFC, SCHW, COF, USB and PNC on NYSE.
Each listing has an issuer/SEC source plus the official uploaded RSSD/name record
and original archive hash. Names are only a drift check after this manual review,
not an automatic identity match. Preferred shares, other exchanges and bare ticker
aliases receive no inherited mapping. A new listing needs its own documented
review. Existing mappings expire on 2027-04-18 and require renewed evidence.
No Cloudflare UI change is included: this publishes the verified data layer for
the subsequent single-stock display integration.

## Bankkonzerne im Profil „Spezialfinanzierer“ (9. November 2026)

Goldman Sachs und Charles Schwab ordnet der Datenanbieter als „Investment Banks/Brokers“ ein. Beide reichen aber FR Y-9C ein und sind Bankholdings. Für Spezialfinanzierer mit geprüftem Kapital der Ebene `listed_consolidated_holding` gilt deshalb:
- `risk_review.py` (`valid_credit`) nimmt ihre Kreditqualität in den gleichen US-Periodenvergleich auf.
- `regulatory-context.ts` zählt bei ihnen Kapitalquote, Anforderung und LCR als erfüllte Nachweise, wie bei Banken.
- `reviewed-liquidity.json` enthält ihre Konzern-LCR aus dem 10-Q zum 30.06.2026: GS 126 % aus berücksichtigungsfähigen HQLA, Schwab 135 %. Beide Dokumente lädt der Workflow `sec-bank-filings`.

Andere Spezialfinanzierer bleiben unverändert.

## S&P-500-Banken (11. November 2026)

Mit dem vollständigen S&P 500 kamen 13 weitere US-Bankholdings ins Universum: KeyCorp, Huntington, Regions, M&T, Fifth Third, Citizens, Truist, Northern Trust, State Street, BNY, Morgan Stanley, American Express und Synchrony.

- **Zuordnung** (`holding-stock-map.json`): Alle 13 stehen im vorhandenen FR-Y-9C-Bestand vom 30.06.2026 (gleiche Archivprüfsumme). Je Eintrag:
  - RSSD-ID und Name exakt wie im FR Y-9C.
  - Stammaktie mit Ticker und Börse laut SEC EDGAR (`data.sec.gov/submissions`, abgerufen 11.11.2026); Vorzugsaktien mit eigenem Kürzel ausgeschlossen.
  - ISIN aus dem Universum.
  - Für fünf Emittenten sperren die IR-Seiten automatisierte Abrufe. Deshalb dient einheitlich der SEC-Eintrag als Notierungsbeleg.
- **Anforderung** (`fed-capital-requirements.json`): Werte aus Tabelle 1 derselben Fed-Veröffentlichung vom 24.06.2026 (gleiche Prüfsumme). Fußnoten werden als `note` mitgeführt:
  - † bei KeyCorp, Huntington, Regions, Fifth Third und Citizens: SCB stammt aus dem Stresstest 2024.
  - ^ bei Synchrony: SCB von 2,5 % angenommen, noch keine stresstestbasierte SCB.
  - Raymond James reicht FR Y-9C ein, steht aber nicht in der Fed-Tabelle und bleibt deshalb ohne Zuordnung.
- **Spezialfinanzierer:** Northern Trust, State Street, BNY, Morgan Stanley, American Express und Synchrony werden mit geprüftem Holdingkapital als Bank bewertet (Regel vom 09.11.2026, wie Goldman Sachs und Schwab).
- **Test:** `RegistryFileTests` prüft jeden Eintrag gegen den FR-Y-9C-Bestand und die Fed-Tabelle.

**Probelauf** (Kopie von main, coverage.json offline neu gebaut):

| | vorher | nachher |
|---|---|---|
| geprüfte Holdings | 9 | 22 |
| S&P 500 gefüllt / offen | 80,69 % / 3,24 % | 80,95 % / 3,01 % |
| je neue Bank gefülltes Gewicht | 45–65 | 60–65 |

Kein Titel verschlechtert sich.

**Offen:**
- LCR: Die 10-Q-Berichte Q3 2026 von 18 Banken stehen in `sec-bank-filings.json`, folgt in einem eigenen PR. Banken der Kategorie IV veröffentlichen keine LCR; das wird je Bank aus dem 10-Q belegt.
- Kreditqualität: braucht das FFIEC-BHCF-Archiv lokal (Download nur interaktiv).
- Der FR-Y-9C-Bestand vom 30.06.2026 gilt nur bis 180 Tage nach Stichtag. Bis Ende Dezember muss das Q3-Archiv importiert werden, sonst verlieren alle 22 Holdings ihre Kapitaldaten.

## LCR der US-Banken zum 30.06.2026 (11. November 2026)

Die Konzern-LCR muss denselben Stichtag haben wie das FR-Y-9C-Kapital, also den 30.06.2026. Quelle sind die 10-Q-Berichte Q2 2026. Sie werden über `sec-bank-filings.json` und den Workflow `sec-bank-filings` mit `SEC_USER_AGENT` geladen. Für die Ausnahmen kommen die 10-K-Berichte 2025 hinzu.

- **Mit Beträgen** (HQLA / Nettoabflüsse, gegengeprüft):
  - American Express 18.922 / 9.626 Mio. USD = 197 %
  - Morgan Stanley 319.165 / 246.717 = 129 %
  - Wells Fargo 414.240 / 347.085 = 119 %
- **Nur Quote** (`basis: ratio_only`, Entscheidung des Nutzers):
  - Bank of America 112 % (HQLA 684 Mrd.)
  - State Street 107 % (111,55 Mrd.)
  - BNY 111 % (198 Mrd. Durchschnitt)
  - Truist 113 % (92,8 Mrd.)
  - U.S. Bancorp 107,6 %
  - Capital One 165 %
- **Ausnahme Kategorie IV** (`exemptions`, wörtliches Zitat): M&T (10-Q), KeyCorp, Regions, Citizens (je 10-K 2025, Kategorie IV im 10-Q Q2 bestätigt).
- **Offen:**
  - PNC, Northern Trust: keine LCR-Zahl im 10-Q; Beträge stehen in separaten LCR-Offenlegungen.
  - Fifth Third: 10-K nennt nur „calibrated LCR requirements“, ab Q3 2026 Kategorie III.
  - Huntington: im 10-K ausgenommen, zum 30.06. nicht belegt, ab Q3 Kategorie III.
  - Synchrony: kein Beleg gefunden.

Prüfung in `holding_liquidity.py` und `holding-liquidity.ts` (identisch mit valueapp-cf). Die Fundstelle ist jetzt Pflichtfeld.

Mit dem FR-Y-9C-Import für Q3 werden alle Einträge auf den 30.09.2026 umgestellt; die Q3-10-Q liegen bereits in `sec-bank-filings.json`.

**Probelauf** gegen main: US-LCR vorhanden 4 → 13, bewusst außerhalb 4, offen 19 → 6. S&P 500 offen 1,18 → 0,99 %. Kein Titel schlechter.
