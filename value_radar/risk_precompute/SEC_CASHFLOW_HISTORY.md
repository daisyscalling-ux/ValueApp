# Independent SEC annual cashflow history

## Data and interpretation

The daily risk job fetches Company Facts for qualified corporate listings in the current SEC ticker/exchange directory. Exact venue and ticker, valid ISIN and the current identity audit are required. A contradictory existing CIK blocks collection. The Company Facts CIK must match; normalized full issuer names must also agree. No fuzzy ticker search or manual Oracle/Micron exception is used.

Three US-GAAP concepts in USD must come from the same accession, filing date and period end: Assets, NetCashProvidedByUsedInOperatingActivities, and PaymentsToAcquirePropertyPlantAndEquipment. Cashflow durations must have the same start and span 330 to 400 days. Only 10-K and 10-K/A filings available at collection time qualify. Nonfinite amounts, conflicting duplicate facts, nonpositive assets and negative cash PPE are rejected. The newest complete eligible filing per period is selected; conflicting values on the same latest filing date are excluded. This is not point-in-time historical research: later comparative restatements can be selected, and collection dates are never backdated.

The metric is (operating cashflow minus cash purchases of property, plant and equipment) / ending assets. Its distinct key is cashAfterPpeAssets. It does NOT claim complete capital expenditure, does not include all intangible investment or finance lease cash payments, and is not a replacement for fcfAssets or an input to DCF. Positive means cash remains after these particular expenditures; it is not a buy signal. It appears in the expandable historical financial section with an explicit explanation.

## Operations

Existing SEC_USER_AGENT is reused. No additional secret or API subscription is needed. The job has a 15-minute collector budget, up to 300 listings, maximum 12 seconds per request and at most about 100 request starts/minute. Each completed attempt checkpoints. Successful data refreshes weekly; failures cool down for two days. HTTP 403 and 429 stop the batch while preserving prior records. New qualified listings enter automatically, ordered by existing main-market priority and rotation. The source cache expires from display after 14 days if it cannot be refreshed.

cf_sec_cashflow_history.json stores compact normalized source periods and provenance, not full Company Facts payloads. It is committed with the other risk outputs. Financial history merges only the independent source-specific ratio series; current financial metrics, fair values, full-FCF availability and risk scores remain unchanged. Banks and insurers are excluded from this corporate cashflow context.

## Verification

251 risk Python tests pass, including six-period ingestion, matching accessions/durations/currency, wrong CIK/name, restatements, zero/negative observations, identity changes, freshness, budget/checkpoint and independent archive integration. Seven UI tests, type checking and build pass. No authenticated live SEC history batch was run locally; actual issuer coverage will be established by daily-risk after merge.

## Remaining bank liquidity work

FR Y-9C capital and holding loan-quality data do not supply a verified LCR for the listed holding. Public LCR disclosure requires a separate consolidated report, correct reporting scope, period-average methodology, denominator and units. A subsidiary LCR cannot substitute for its listed parent. These fields remain open; no loans/deposits proxy and no assumed 100% ratio is introduced. Existing bank capital and credit quality coverage is preserved.

Sources:
- https://www.sec.gov/search-filings/edgar-application-programming-interfaces
- https://www.sec.gov/about/developer-resources
- https://www.federalreserve.gov/frrs/regulations/section-24991-disclosure-requirements.htm


## Extension — 2026-11-01: native currencies and separate accounting concepts

This extension supersedes the USD-only and 10-K-only restrictions above. The parser evaluates each accounting namespace, investment concept and common three-letter reporting currency separately. Supported annual-duration facts may be filed on 10-K, 20-F, 40-F or their amendments. The 330–400 day duration, identical cashflow start, accession, filed date and end constraints remain in force. No quarterly sums or currency conversion are performed. If the same concept and period has complete facts in multiple currencies, that period is excluded as ambiguous.

Three explicitly defined variants are collected:
- US-GAAP Assets / NetCashProvidedByUsedInOperatingActivities / PaymentsToAcquirePropertyPlantAndEquipment: existing cashAfterPpeAssets.
- IFRS-full Assets / CashFlowsFromUsedInOperatingActivities / PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities: cashAfterPpeAssets with separate IFRS source and reporting currency. Never stitched into US-GAAP observations.
- US-GAAP Assets / NetCashProvidedByUsedInOperatingActivities / PaymentsToAcquireProductiveAssets: separate cashAfterProductiveAssets metric. Its scope is the issuer's reported productive-assets concept, not presumed equivalent to PPE or full capex. No sum with the PPE amount is made.

Negative payment values remain rejected, not absolutized. Unknown concepts, incomplete components and statements from different accessions/frameworks remain excluded. Old USD/PPE cache rows retain compatibility. New rows carry namespace, concept and metric, validated again on consumption. Period counts now count source-series observations and need not equal distinct fiscal years when multiple concepts are reported. Full FCF, DCF, current metrics and risk scores are unaffected.

Name policy v3 handles terminal jurisdiction suffixes without closing slash or with whitespace (actual observed examples /DE, / MA, /UK and /CN), and explicit dotted legal abbreviations. Renames, class changes, unknown suffixes and subsidiary mismatches remain blocked. Previous failures are rechecked once; successful cached issuers refresh normally rather than forcing a universe refetch.

Validation: 266 Python risk tests; eight UI tests, UI typecheck and build pass. New cases exercise IFRS/EUR, foreign annual forms, native US-GAAP currency, missing/mixed currencies, namespace separation, negative amounts, ambiguous dual currency, separate productive-asset history and actual observed SEC name pairs. Authenticated live recovery has not been measured locally; daily-risk must run after merge. No new secret, no manual ticker exceptions. Foreign issuers without supported XBRL facts remain open.

Primary references:
- SEC Form 20-F and 40-F: https://www.sec.gov/files/form20-f.pdf and https://www.sec.gov/files/form40-f.pdf
- Official IFRS taxonomy concepts in ESEF: https://www.esma.europa.eu/sites/default/files/2024-05/ESMA32-2009130576-3011_Final_Report_amending_RTS_on_ESEF_-_2024.pdf
