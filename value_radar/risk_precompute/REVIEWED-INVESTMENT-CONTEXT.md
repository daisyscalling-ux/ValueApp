# Reviewed investment context and batch SEC evidence

Production run 42228818842 published all 1,333 listings with verified input
integrity. Twelve SEC period-gap requests parsed eleven original filings;
BHP's history now includes 2026-06-30 (three accepted observations, two replacing
older observations). Eleven requested periods remain unresolved. Financial metric
availability did not increase; updated history is not a newly available metric.
EDINET downloaded 52 filings: 29 complete cashflows, 23 partial.

## Reuse of reviewed EDINET evidence

The original English labels for 4324, 5411 and 9201 explicitly describe purchases
of non-current assets. A document-scoped registry now permits the existing broad
investment context to use these amounts. The registry binds symbol, document,
annual period, original file hash, concept QName, schema hash and label hash.
Definitions for a different year or revised filing require a new review.

Replay checks duration, monetary amount, exact definition, conflicting values and
source identity. It does not overwrite a reported standard value, change capex,
mark the annual statement complete, alter risk-score weights or renew retrievedAt.
The current archive replays three contexts: 26.916bn, 321.720bn and 202.424bn JPY.
These are broad purchases, not confirmed full capex; corresponding cashflow ratios
are descriptive context only. No missing intangible outflow is assumed zero.

## SEC batch evidence

The original annual filing parser now preserves up to 100 unmapped current-year
investment facts per report, with exact concept, namespace, original accession,
period, currency, amount and filing hash. Only dimension-free matching-issuer
annual monetary contexts pass. Unknown concepts do not enter normalized financial
facts. These diagnostics allow a common review of issuer extensions instead of
repeating manual downloads company by company.

Previously parsed reports with an unresolved requested period get one evidence
capture; normal error cooldowns remain. Once investmentEvidence exists, ordinary
period retry rules apply. No additional workflow, secret or Cloudflare deployment
is required: merge and run daily-risk. The EDINET replay uses existing evidence;
it does not trigger a parser-version migration or force 52 repeat downloads.
