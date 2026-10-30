# Consolidated regulatory capital in the risk audit

The daily-risk job now bridges the reviewed FR-Y9C holding evidence into `cf_regulatory_context.json`, then into the existing coverage audit and content-addressed app shards. It runs before the initial and final audits. No additional API key or provider request is required.

## Acceptance boundaries

- Exact reviewed common-stock listing, valid ISIN, matching input identity, holding name/RSSD and source-file digest.
- Holding report no older than 180 days; source import not future or before the reporting period; identity review not expired.
- Field dictionary effective for the report date, percent-to-fraction conversion verified against the raw observation, finite numbers and coherent CET1/Tier1/total-capital ordering.
- The reader separately checks source freshness (36 hours), exact identity, dates, scope, metric codes and units.
- Zero is a legitimate reported observation; missing values are never converted to zero.
- No FDIC subsidiary aggregation, inferred LCR, inferred credit quality or generic minimum-capital threshold.
- The original publication date is unknown: no point-in-time backtest eligibility.

## Fulfilled and outstanding requirements

For banks, verified CET1 closes only `regulatory_capital_CET1`. The institution-specific required capital and buffer are explicitly outstanding, alongside liquidity and credit quality. Specialist financial companies receive capital context without closing their business-model requirements. Insurers cannot inherit bank ratios. Existing balance metrics, valuation and score remain unchanged.

The app explains CET1's risk-weighted denominator and shows source/period details on demand. It restores the missing-capital requirement if displayed evidence expires. This is reported context, not a safety rating.

## Validation (2026-10-30)

Replay against the published 2026-10-27 snapshot: 1,330 listings, unchanged basic balance metrics for every listing, nine accepted holdings (JPM, BAC, C, WFC, COF, USB, PNC, GS, SCHW). Seven bank CET1 requirements fulfilled; GS/SCHW remain specialist context. Shards retain all nine records; largest package 552,182 bytes. These are replay results, not a claim that the new daily run is already deployed.

209 Python risk tests; all TypeScript risk test suites; 16 focused app/reader tests; targeted UI TypeScript checking. Local Cloudflare source changes are in Desktop/cf and require its normal deployment. Merge this change and run daily-risk to publish the new data fields.

The next data gaps are holding-level liquidity, asset quality and institution-specific capital requirements, plus jurisdiction-specific insurer solvency. Existing source files still need new quarterly imports when available; running the bridge does not refresh the original report date.
