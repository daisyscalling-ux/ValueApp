# Main-market risk-data work block

This changes data-fetch order, not risk scores, fair values, liquidity requirements or eligibility thresholds.

## Ordering

`market-priority.json` is shared by the Python sector fallback and the TypeScript risk queue. Primary venues cover US exchange listings, Germany and Japan. A second tier covers London, Switzerland, Euronext, France, Netherlands, Italy and Spain. All other venues remain in the queue. This is a venue-based preference, not a claim that each constituent is large or liquid; raw market caps in different currencies are not compared.

An attempted item waiting at least seven days gets a rotation turn before ordinary priority work. This is not a promise of a successful refresh every seven days: source availability, time budgets and cooldowns still apply. Unknown and future attempt dates do not get a rotation advantage. Within each tier the existing risk-job severity and attempt age order apply; the Yahoo sector fallback uses attempt age. No entries are deleted due to priority.

The history exporter consumes the audited queue. The sector fallback uses the same market tiers. This does not reorder the independent fundamentals or news collectors. Coverage now includes `summary.markets` with complete domain-state counts for `primary`, `europe` and `rotation`; consumers of existing totals remain compatible.

## Identity repair

Eleven observed Yahoo name aliases are bound to exact listing, ISIN and expected input name. They address legal-name translation, abbreviation and descriptive provider annotations only. Source observations are in `evidence/main-markets-2026-10-24.json`. Exact ticker, currency, exchange, equity type and explicit share-class safeguards remain active. No fuzzy matching is added. A changed alias permits one targeted retry for a previous name rejection, then normal cooldown resumes.

Class/ADR ambiguities (including Petrobras, Novo Nordisk, Porsche preferred and other rejected cases) are deliberately not approved by this batch. An accepted profile does not imply an accepted price series or enough eligible peers.

## Baseline and follow-up

After merged PR62, daily-risk run 40034416755 completed successfully: 455 strict comparisons plus 561 additional broad contexts, out of 1330 listings. The audited main-market scope is 596 primary and 356 European listings; the other 378 remain in rotation. In this snapshot primary/European historical coverage is 585/596 and 348/356. Missing historical series therefore total 19. Finance data have 134 partial/missing cases across these tiers; another 133 have industry-specific context rather than generic corporate ratios. These categories must not be treated as low risk or silently combined.

Next: after the refreshed run, group those financial gaps by missing field, source and industry, then address shared acquisition/mapping failures. Regulatory bank/insurance fields stay distinct from generic balance-sheet ratios. Calibration remains a later step.

Activation: merge, then run `daily-risk` on main. No Cloudflare rebuild required.
