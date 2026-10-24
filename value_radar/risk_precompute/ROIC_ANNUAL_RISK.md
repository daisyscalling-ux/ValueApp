# ROIC annual statements for risk coverage

The daily-risk workflow now collects standalone annual ROIC v3 statements for
missing/partial balance observations in the primary markets and major European
venues defined in market-priority.json. Other venues remain in the universe;
this collector defers them. New listings are automatically discovered by the
coverage audit. Successfully recovered records are refreshed after one day too.

## Data contract

Archive: `daten/cf_roic_risk_annual.json`, schema 1. Every listing has its input
identity (listing, ticker, ISIN, currency, security type and share class), its
own retrieval timestamp, and an independent annual statement. Changed or
conflicting input identities invalidate the archive entry. ISIN checksum and
qualified listing are required before requesting data. API response symbol
must match the requested listing exactly.

Three endpoints, `period_type=annual&limit=2`:
- `/v3.0.0/fundamental/balance-sheet/{EXCHANGE:SYMBOL}`
- `/v3.0.0/fundamental/cash-flow/{EXCHANGE:SYMBOL}`
- `/v3.0.0/fundamental/income-statement/{EXCHANGE:SYMBOL}`

Official schemas:
- https://www.roic.ai/api/docs/financial-statements/balance-sheet
- https://www.roic.ai/api/docs/financial-statements/cash-flow
- https://www.roic.ai/api/docs/financial-statements/income-statement

Total debt requires both `bs_st_borrow` and `bs_lt_borrow`; missing is not zero.
Cash and assets use `bs_cash_near_cash_item` and `bs_tot_asset`. Equity uses
`bs_eqty_bef_minority_int_detailed` (not equity including minorities).
Operating cash flow uses `cf_cash_from_oper`. Capex uses negative
`cf_cap_expenditures`, otherwise the reported gross fixed/intangible acquisition
aggregate, otherwise BOTH reported acquisition components. Net investing flows
and asset disposals are never substituted. Valid negative outflows become
positive investment spending. Unexpected positive capex stays missing.

Cash flow and income must match the newest eligible balance-sheet period AND
reporting currency. Converted responses (`fx_applied` other than false), future
or >550-day-old annual periods and conflicting duplicate periods are excluded.
Reporting currency need not equal the stock's trading currency: these ratios
are dimensionless, calculated wholly within the same reporting currency.

The audit selects the stronger WHOLE statement, with original primary/Yahoo
source winning ties. Where a valuation annual statement exists, the existing
same-currency and <=7-day fiscal-period alignment safeguards remain. It does
not assemble a synthetic balance sheet from individually convenient sources.
ROIC provenance is mandatory for every numeric field. Records older than seven
days are ineligible even if another attempt or the overall archive is recent.

These are current standardized consolidated statements, not point-in-time
history. Debt follows the provider's short/long maturity definitions; leasing
scope is not separately reconciled. Bank/insurance book ratios remain context,
not regulatory capital, solvency or a calibrated risk score.

## Daily operation

The existing GitHub Actions secret ROIC_API_KEY is used. Budget: 12 minutes,
maximum 120 requests/minute, individual timeout <=12 seconds, response <=2 MB.
Attempts are checkpointed. 401/402/403/429 stop further requests for this run.
Failures retain the original successful retrieval date; errors never include
API keys. A missing key or stale coverage audit is reported explicitly.
The final audit consumes the new archive in the SAME run, then publishes both
archive and coverage report. No Cloudflare deployment is required.

Baseline before this change: 90 incomplete balance observations across 951
primary/major-European listings (2026-10-24 production audit). This is a target
set, NOT a claim that ROIC will resolve all 90. The first production run must
verify actual response coverage, endpoint access and remaining field gaps.
A newly complete independent statement must not alter EPS, Fair Value,
12-month targets or score weights.

## Validation

17 Python collector tests cover source/period/currency, missing and zero values,
capex definitions, identity invalidation, rate/access failures, cooldown,
refresh and checkpoint age. Universe regression tests additionally verify
whole-source selection, no field blending, no valuation mutation, stale data,
conflicting listings and source provenance. Live ROIC responses are verified
only by the subsequent daily-risk run with the repository secret.
