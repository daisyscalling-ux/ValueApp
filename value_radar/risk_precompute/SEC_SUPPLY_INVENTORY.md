# SEC supplemental-history inventory

`cf_sec_cashflow_history.json.report.inventory` describes the current export universe. Existing top-level report counters continue to describe only work performed during this run. GitHub step summaries show inventory counts, while JSON retains listing-level details.

- `available`: at least one supplemental history metric passes the same arithmetic, identity, source and cache-age checks as application history. Latest dates are reported by metric. This does not mean current annual financial statements are complete.
- `stale`: matching historical data exist but their retrieval is older than the 14-day display window.
- `not_attempted`: no attempt matches the current listing identity.
- `failed`: current-identity attempt failed and no valid displayed history remains.
- `no_valid_periods` / `no_accepted_history`: stored material does not supply a validated history metric.
- `blocked`: duplicate listing, unconfirmed identity or conflicting CIK.
- `outside_scope`: no SEC listing mapping or a non-corporate balance profile; use the appropriate other source/framework, not a fabricated zero.
- `coverage_stale`: upstream identity/profile coverage is older than two days; no availability claim is made.

Counts cover unique resolved listings. Unresolved listing rows and archived listings no longer in the export are counted separately. Main-market counts use the existing market-priority rules. No risk score, valuation, primary financial statement or full-capex definition changes.

The collector and inventory share the same eligibility predicate. The inventory revalidates cached observations; it does not count a successful HTTP request as data availability. Ordinary cache and retry schedules remain unchanged. New companies enter the normal collector through the current universe and SEC listing map.
