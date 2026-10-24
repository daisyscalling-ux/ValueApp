# Independent annual statement for balance-risk context

Production verification after PR64: fundamentals-daily 40101461282 and daily-risk 40104682440 succeeded. Main-market partial/missing balance cases fell from 133 to 121 (99 primary, 22 European). This is less than the earlier Yahoo-only replay: SEC replaces the valuation annual block, and exact-source enrichment properly rejects revenue-definition differences, split-adjusted EPS and different reported fiscal dates. Provider responses also differ between runs.

The collector now stores `risk_annual`, a deep copy of the eligible Yahoo annual block before SEC or reviewed-release enrichment. It is bound to the requested listing and marked `standalone_balance_risk_context`. The existing `annual` valuation path is unchanged. No SEC values are overwritten by this new field; no valuation formula or score weight changes.

The coverage audit assesses the existing annual block first. It may use the independent block only when that complete source block provides strictly more available balance context. It never merges fields between the two blocks. A complete existing block wins ties. Missing `risk_annual` preserves legacy behavior.

Checks: exact snapshot symbol, purpose, provider source, annual freshness, field dates, positive asset base and all existing financial checks. If a primary block exists, financial currency must match and reported dates must be within seven days. This limited comparison permits provider month-end notation versus a 52/53-week reporting date; it does not assert that dates are identical and does not rewrite either. The selected period, source, URL and original valuation period/source are included in coverage. Older years, mixed-period fields, stale observations, future dates, other issuers and other currencies cannot silently qualify.

The replay uses the dated Yahoo tables from the preceding 133-company audit against the newly downloaded production snapshots. It shows 32 stronger balance contexts (31 complete for their respective profile, one still partial); this is potential coverage, not a promised live result. Source differences at the next collection can change it. No point-in-time historical validation or calibrated risk score is implied.

Activation: merge; run `fundamentals-daily` on main with symbols empty; after completion run `daily-risk`. No Cloudflare rebuild is required for the exported coverage update.
