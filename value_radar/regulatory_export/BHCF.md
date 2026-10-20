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
