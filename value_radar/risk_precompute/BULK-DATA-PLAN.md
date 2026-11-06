# Universe-wide recovery, evidence reuse and measurable progress

The workplan now distinguishes provider/field gaps, original sector disclosures,
definition reconciliation, unavailable sector context, strict peer extensions where
context already exists, and insufficient listing history. Existing requirements
remain open. A broader comparison is not promoted to a strict peer cohort, and
repeated downloads cannot manufacture a newly listed stock's two-year history.
Groups are deduplicated within each cause; counts across causes overlap.

Six financial metrics are reported independently, with applicable-profile
denominators. Valid zero values count; missing, NaN and invalid-identity rows do not.
The before/after report records individual metric gains and losses even if the
overall balance remains partial. It separates observation counts from affected
listing counts. Neither progress indicator is a calibrated risk score.

ROIC collection retains bounded numeric annual statement evidence for later
normalizer changes. It stores up to four rows per endpoint, at most500 fields per
row and150k characters per listing, with identity/date/currency metadata and a
canonical SHA256. It excludes response URLs, credentials, unrelated metadata and
arbitrary strings. Only known statement-field prefixes and the reported credit
debt total are retained; this is not a copy of every provider response field.

Reprocessing requires unchanged listing identity, matching original retrieval date,
valid digest and evidence no more than seven days old. It never renews that date.
Changing PARSER_VERSION schedules a replay; the existing freshness and provider
backoff policy separately decides whether a real network refresh is due.
For unresolved legacy successes without evidence there is one initial capture,
no earlier than one day after the preceding attempt. Errors do not bypass backoff.
Covered stocks are not all refetched for migration. Normal refresh continues.

Measured local audit of published2026-11-06T11:43:47.332Z coverage:
- Main markets:58 listings with incomplete basic financial observations.
- Main markets:549 strict peer gaps already have another comparison context;
  55 have no available sector comparison context.
- Seven main-market listings have less than two trading years.
- Corporate main-market metric coverage: net debt/assets766/793, FCF/assets758/793,
  operating cash flow/assets790/793.

These numbers are the observed baseline, **not newly recovered values**. The
latest universe grew during analysis; do not compare them mechanically with the
earlier951-main-listing snapshot. Actual next-run gains/losses use common listings
and are measured by coverage_delta.py. Scope changes are reported separately.
The investigated alternative statements mostly also lack the missing fields.
Older complete Apple/Qualcomm statements are not substituted for their newer
incomplete fiscal periods. No financial amounts or scores are imputed by this PR.

Deployment: merge and run daily-risk on main. No Cloudflare code change is needed.
The same workplan, coverage delta and ROIC archive paths are already published by
that workflow. The first capture creates evidence for subsequent broad parser work;
it does not by itself promise additional accepted financial values.
