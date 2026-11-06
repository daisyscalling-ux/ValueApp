# Original cashflow supply: period gaps and issuer definitions

The SEC annual collector now compares the available history with the annual
balance period in the current coverage snapshot. A newer known annual period
bypasses a fresh older history once and triggers the existing original annual
filing loader when companyfacts still has no matching observations. A seven-day
tolerance accommodates 52/53-week reporting. Repeated unsuccessful period
requests wait two days; existing error cooldowns, identity checks, time budgets
and annual observation validation remain in effect.

Attempts expose `requestedPeriod` and `requestedPeriodState`; run counters expose
`newerFiscalPeriodRequested` and `requestedPeriodStillMissing`. These are supply
diagnostics, not newly recovered financial values. Original filings still must
pass the same currency, period, issuer and concept checks before use.

EDINET parser v5 also saves local schema and label evidence for issuer-specific
purchase/acquisition facts from the downloaded filing ZIP. Definitions and labels
retain file hashes. References must resolve to the exact local schema; remote
references are not loaded. Files, expansion ratio, total bytes and candidates
are bounded. XML declarations with entities or DTDs are rejected.

`extensionEvidence` is review-only, has zero score contribution and never fills
capex or free cashflow. In particular, an issuer's
`PurchaseOfNonCurrentAssetsInvCFIFRS` is not a standard taxonomy concept merely
because its local name looks familiar. A broad investment amount cannot be
silently treated as complete PPE plus intangible purchases.

## Observed baseline, 6 November 2026

- The last production run added no financial metric coverage. Seven missing
  ROIC operating cashflows already have EDINET operating cashflow context.
- Across matching cached SEC identities, twelve histories end before the
  known annual balance period: QH, TRP, APP, BHP, CI, CNQ, COP, ROP, SONY, TM,
  VLO and VZ. This is a request inventory, not a recovery forecast; the normal
  collector scope and retry policy still apply.
- Three inspected Japanese issuer extensions (4324, 5411, 9201) use a similar
  non-current-asset purchase label. Their original definitions must be collected
  and reviewed before accounting equivalence can be decided.

After merging, run `daily-risk`. Existing archive publication includes the new
attempt diagnostics and EDINET evidence. No Cloudflare upload is needed. Compare
the resulting coverage delta and accepted fiscal periods, rather than equating
successful HTTP requests or parsed labels with recovered FCF.
