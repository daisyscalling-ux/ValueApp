# Observed financial history across the universe

`financial_history.py` runs after the final risk audit and before app export. It retains qualified observations by exact listing identity (including ISIN), metric, reporting currency, frequency and source/method. Its persisted archive is `cf_financial_history.json`; each current app row gets a compact `balance.history` view through the existing bounded shards.

Annual ratios and regulatory quarterly ratios are separate. Different sources, profiles or identities never form a trend. Only adjacent plausible fiscal years (300–430 days) or quarters (70–110 days) produce changes, expressed in percentage points. Missing intervening periods remain visible. Repeated daily retrieval is not another reporting period.

Revisions to the same reporting period retain the original observation and append the new value. A changed value with the same or an older source-retrieval timestamp is quarantined instead of replacing the previous value. Archive timestamps record actual collection time; they are not imputed publication dates. No historical backtest eligibility is claimed.

The archive retains 12 annual or 32 quarterly periods per exact series. Within retained periods, revisions remain preserved. Removed listings remain in the archive; new qualified listings are collected automatically. Invalid archive schema/identity keys, future or nonfinite revisions, duplicate coverage symbols and out-of-order audit runs fail closed before overwriting the history. Input coverage is copied and its original metrics remain unchanged.

The UI places the financial history in a collapsible section. A single real period is explicitly labelled as collection in progress. The UI independently validates the period gap and change arithmetic. No price forecast, calibrated risk score or automatic good/bad investment verdict is added.

## Validation — 2026-10-31

230 risk Python tests pass, including annual/quarterly comparisons, revisions, source/identity changes, missing periods, zero/invalid values, archive protection and retention. Four UI tests and targeted TypeScript checking pass. Full-universe replay populates 6,492 observations for 1,256 listings, with no artificial comparisons on the first run. Repeating the same snapshot preserves every series without adding another period. All original audit fields remain unchanged.

## Initial activation (before historical backfill)

Merge, run daily-risk and deploy Desktop/cf. No additional keys or API calls are required. The first production run creates its own dated archive; the local replay archive is intentionally not committed. This prepares ongoing history collection and does not backfill six years of historical original disclosures. Earlier verified filings and regulatory liquidity disclosures remain separate data-supply work.

## Universe-wide historical backfill — 2026-10-31

`daily-risk` now runs `history_backfill.py` after current-data recovery, with the existing ROIC_API_KEY. It requests the latest eight annual balance sheets, income statements and cash-flow statements through documented ROIC v3 endpoints, ordered descending. Provider plan coverage can be shorter. Actual returned periods are retained; absent years are never synthesized.

Each run has a 30-minute budget, at most 500 listings and at most 120 request starts per minute, with bounded requests. It checkpoints after each listing into `cf_roic_history.json`. Authentication, subscription and rate-limit errors stop the batch. Other errors retain previous records and use a retry cooldown. Qualified new listings automatically enter the queue; major markets are prioritized and older attempts rotate back in. Successful histories with at least seven periods refresh monthly; shorter histories refresh weekly. The existing daily-risk schedule resumes the remaining queue automatically. Other jobs may share the provider limit; HTTP 429 still stops this batch safely.

All three statements must have the exact listing, annual cadence, unconverted reporting currency and matching period end before their fields can be combined. Missing components remain missing. Duplicate conflicting periods are rejected. `export-history-backfill.ts` reuses the current ratio calculations with an explicitly historical age window (eight years and 45-day retrieval cache), without changing the default freshness checks for current metrics. Same-identity saved archive periods survive partial later responses; the raw cache itself only claims statements actually returned in that request.

The temporary `cf_history_backfill_balances.json` is evaluated and merged before app export. Archive identity, source, frequency, profile and currency stay separated. The view selects one source-specific series per metric, preferring a valid period comparison, then its latest period and depth. It explicitly displays its own source and period because the current metric can use a different source. Up to eight real period values are expandable. No source stitching, valuation replacement, score adjustment or inferred historical release date is introduced. Current industry classification is used for these descriptive ratios; this is not a point-in-time industry backtest.

Validation: 240 risk Python tests, targeted TypeScript tests, six UI tests and UI TypeScript checking pass. Replaying 95 actual stored ROIC annual snapshots accepts 88 identities through the historical exporter; the full current universe produces 6,809 observations across 1,252 listings, with zero invented year-over-year comparisons. Every original current audit field is unchanged. Synthetic multi-year fixtures separately verify six/seven-year ingestion, revisions, identity/currency isolation, gaps and actual first-observed timestamps. No local authenticated ROIC historical request was made: production coverage and tariff depth must be checked after the first merged daily-risk run.

Activation: merge the PR, run **daily-risk** on main, and deploy the updated Desktop/cf app. No new secret is needed. The first run may only fill part of the universe; subsequent daily runs resume. Historical regulatory bank liquidity and a calibrated risk model remain separate work.

Official endpoint documentation: https://www.roic.ai/api/docs/financial-statements/balance-sheet , https://www.roic.ai/api/docs/financial-statements/income-statement , https://www.roic.ai/api/docs/financial-statements/cash-flow .
