# Japan original filings and main-market financial supply

## Start after merge

Run **daily-risk** on main once. It performs both additions in the same run:
1. Bounded ROIC risk-statement refresh with targeted retry policy.
2. EDINET annual filing discovery/download, final coverage audit and supply plan.

The existing daily schedule also runs these steps. Set the GitHub Actions
repository secret **EDINET_API_KEY**. The key is read only in the collector and
never exported. No Cloudflare upload, extra service or separate manual company
list is required. ROIC uses its existing repository secret.

The first EDINET discovery can add up to 28 minutes. Its progress is saved and
published; another daily run resumes any unfinished discovery. The workflow
allows 31 minutes for this stage, with its own 28-minute budget and bounded
20-second requests. It waits at least two seconds between request starts.

## Source and parser

Primary documentation:
- FSA API v2 specification: https://disclosure2dl.edinet-fsa.go.jp/guide/static/disclosure/download/ESE140206.pdf
- Official XBRL sample instances: https://disclosure2dl.edinet-fsa.go.jp/guide/static/disclosure/download/ESE140116.zip
- JPX explanation of downloadable original filings: https://www.jpx.co.jp/english/equities/listed-co/disclosure-gate/availability/

`edinet_supply.py` requests `/api/v2/documents.json?date=...&type=2`, then
`/api/v2/documents/{docID}?type=1`. A persistent 461-day discovery window is
shared across all eligible Japanese listings, including companies added later.
The recent seven-day overlap is rechecked, and the selected filing's original
index day is revalidated before downloading it. Withdrawal/unavailable flags,
newer corrections and conflicting filers are not silently ignored. Download
failures preserve the true old retrieval date; a changed document invalidates
the previous filing before the replacement is fetched.

Only qualified Japanese listings, valid JP ISINs and JPY quotes qualify. The
EDINET security code is the four-character listing code followed by zero; the
filing's EDINET issuer code must also match both the XBRL DEI and entity contexts.
No name similarity is used. Annual reports and corrections (120/130) require
current disclosure status and annual periods of 330–380 days. Missing original
reports, unsupported issuer-specific tags and ambiguous revisions stay open.

The parser reads a single `XBRL/PublicDoc/*.xbrl` instance without extracting
ZIP paths. Bounds apply to response size, decompressed size and compression
ratio; DTD/entities are rejected. Namespace identity, JPY units, consolidated
DEI, dimension-free contexts, exact dates and duplicate conflicts are checked.
JPPFS and JPIGP are handled separately, never blended. XBRL `decimals` describes
precision: it is NOT a unit multiplier.

The observations are total assets, cash equivalents, operating cash flow, and
reported gross PPE + intangible acquisition payments. Both acquisition
components must be explicitly present (including explicit zero) and nonpositive.
Disposals, net investing flows, FCF subtraction and accrual capital additions
are not substitutes. The output does not infer total debt from liabilities.

## Risk integration

`cf_edinet_cashflow.json` stores the discovery index, exact input identities,
filing metadata, attempts and dated field provenance. The coverage audit reads
it automatically. An EDINET cash-flow/assets observation uses only values from
that one original filing. It can close a missing cash-flow ratio alongside an
existing debt ratio ONLY when fiscal end and currency match exactly and BOTH
assets and cash agree within 0.01% (minimum absolute tolerance JPY 1).

The ratios retain separate sources. No inputs to valuation are changed. Older
periods may remain separately dated context, but cannot close a current-period
gap. Expired observations (>7 days since download), withdrawals, issuer changes,
missing components and differing balance anchors do not improve completeness.
A debt gap remains a debt gap even if the cash-flow observation is complete.

## Second block: automatic main-market maintenance

`financial_supply_policy.py` makes ROIC requests responsive to the actual data
state. A new listing, changed identity, fiscal period or required field set
becomes due immediately. Audit timestamp changes alone do not trigger requests.
Persistent missing fields are revisited after seven days; transient failures
back off for 1/2/4/7 days. Used ROIC statements are normally refreshed after four
days, with a latest retry at day six to protect the seven-day validity limit.
A failed request never renews financial data. Companies fully covered by another
source do not consume redundant ROIC calls. Smaller markets remain explicitly
deferred rather than removed. Legacy attempts migrate with a one-day interval.

`cf_financial_supply_plan.json` records per-company expected/observed periods,
missing fields, period conflicts, next attempt, provider error and next source.
A summary is added to the GitHub run. The collector distinguishes downloaded
empty, partial and fully populated normalized records; download success is not
reported as risk coverage success.

## Validation and limits

The FSA sample annual instances were parsed locally: the IFRS sample supplied
both acquisition components and yielded a complete cash-flow observation; the
J-GAAP sample and its correction correctly remained partial with an unreported
intangible-acquisition component. These are OFFICIAL SAMPLE COMPANIES, not
production recoveries. Tests cover scaling/signs, missing and zero components,
consolidation, periods, namespaces, identity, corrections, withdrawals, resumable
index discovery, cooldowns and stale observations. Existing risk/peer tests are
also retained.

No EDINET production coverage number is claimed before the first authenticated
GitHub run. Initial targets: 49 incomplete Japanese balance observations in the
24 October audit. EDINET may not close debt-only cases, unusual extensions or
omitted capex components. Every unresolved case remains explicit in the supply
plan. Neither this source nor the plan calibrates risk probabilities or changes
Fair Value, EPS, 12-month targets or score weights.
