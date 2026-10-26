# Progress and acceptance

The daily workplan now reports data coverage with explicit denominators for all listings, main markets and deferred markets. Complete basic balance ratios, financial-sector context, strict peers and broader contexts remain separate. Joint coverage is an intersection across identity, quote, history, market and balance/context, not an average.

completionPercent remains null: snapshot coverage cannot certify project completion. Original sector disclosures, verified news events, historical validation of the full model and end-to-end acceptance remain uncertified. Article counts and price-only validation do not complete these gates.

Work blocks count each listing once across causes and retain deferred markets. A selected original statement whose predecessor was unavailable is not a reconciliation conflict. Real not-aligned sources remain open.

PR71 production verification (2026-10-26T18:27:55Z): TSE:3697 and TSE:7453 have complete basic balance ratios from ROIC. Main-market open balances fell from 58 to 56. Of 951 main-market listings, 895 have basic balance/context data (94.1%) and 932 usable history (98.0%). These are coverage percentages, not overall model completion.

The existing daily-risk step writes progress into cf_risk_workplan.json and the GitHub run summary. No extra API calls, credentials, workflow changes or Cloudflare deployment. Source data, valuations and risk formulas remain unchanged. After merge, the next scheduled run publishes the report; an immediate manual run is optional.

Validation: 189 Python tests passed, covering scope separation, unique counts, intersection semantics, empty denominators, context distinctions and source-conflict handling. Full current-snapshot report generated locally.

Missing quotes, price context and market proxies now also have explicit work blocks, rather than appearing only in coverage statistics.
