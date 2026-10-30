# Holding loan-quality observations

The reviewed FR-Y9C archive now supplies credit-quality observations alongside capital ratios. `regulatory_export/import_credit_quality.py` reads a local official BHCF ZIP plus the supplied effective-date dictionary and writes `daten/regulatory/bhcf-credit-quality.json`. The daily risk bridge consumes this file automatically; no extra provider credentials or downloads are required.

## Method and sources

- Nonaccrual: BHCK1403; 30–89 days past due and still accruing: BHCK1406; 90+ days past due and still accruing: BHCK1407.
- Denominator: loans held for investment BHCKB528 plus loans held for sale BHCK5369, before allowance. All amounts are from the same consolidated report and expressed in USD thousands.
- The headline observation is (BHCK1403 + BHCK1407) / (BHCKB528 + BHCK5369). The 30–89 day bucket remains separate. This is not expected loss and is not claimed to be a universally comparable IFRS NPL ratio.
- Official series definitions: https://www.federalreserve.gov/apps/mdrm/data-dictionary/search/item?keyword=1407 and https://www.federalreserve.gov/apps/mdrm/data-dictionary/search/item?keyword=1403 . Financial Download Dictionary active rows 414–416, 899 and 1319 substantiate the June 2026 archive field names. The current form's dollar-thousands convention and loan denominator are also visible in the issuer's published FR-Y9C: https://s203.q4cdn.com/711684571/files/doc_downloads/9C/2026/05/FR-Y-9C-1Q26.pdf .

## Boundaries

Exact reviewed RSSD/name and source archive digest must match the already verified capital record. Reporting period, source import time, dictionary dates and units are checked. Negative, missing, malformed, boolean and inconsistent components are rejected; explicit zero survives. The TypeScript reader independently reconstructs the arithmetic.

Credit mix, guarantees, recoverability and trend remain open. Therefore this observation does not close the entire asset-quality requirement and does not change the score or fair value. There is no LCR in this import; cash balances are not substituted. The original publication date remains unknown, so these observations are not approved for historical point-in-time backtests.

The importer refuses a replacement that removes previously imported holdings or moves backwards in quarter. The supplied September file has only one row and no reviewed holding, so the June evidence is retained. A newly reviewed holding requires an original-archive import, not an inferred mapping.

## Validation, 2026-10-30

214 risk Python tests and 19 regulatory Python tests pass, alongside regulatory/universe TypeScript tests. Replay of the current 1,329 listings preserves every existing basic balance metric and accepts loan-quality context for all nine reviewed holdings. The previous published universe contained 1,330; the current main snapshot already contained 1,329 before this change. UI tests and targeted TypeScript checks pass.

Merge this PR, run daily-risk, and deploy the updated Desktop/cf app. The original source is quarterly: daily processing never redates its reporting period.
