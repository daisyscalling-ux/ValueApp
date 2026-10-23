# Listing and history recovery — 2026-10-23

This block separates missing security metadata from unavailable history. It does not relax the five-peer minimum or change Fair Value, financial inputs or risk-score weights.

## Missing listing metadata

The current universe contains 70 entries without an exchange-qualified listing: 50 European suffixed tickers and 20 unsuffixed instruments. Sixteen have preferred-share ticker syntax and remain outside automatic common-equity recovery. An additional stapled/unsupported security remains outside the existing peer-group policy.

The daily-risk workflow now performs a bounded ROIC ticker-search recovery BEFORE its normal universe audit and history collection. Acceptance requires the correct exchange and full ticker/class, a valid ISIN checksum, supported security type, matching issuer name, no conflicting supplied ISIN/currency, and no duplicate target listing. Missing identifiers are never guessed. Price, currency, fundamentals, Fair Value and company/industry names are not copied from search results. Original metadata observation dates are retained; listing verification has separate source/date fields.

Scandinavian class delimiters and a London trailing dot are normalized only on their relevant exchanges. Class A and B remain distinct. Failed lookups have a one-day cooldown, confirmed repairs can be reapplied for 30 days only to an unchanged input fingerprint after the large export rewrites the universe. Every attempt is checkpointed into cf_listing_recovery.json. Network errors are sanitized. The job uses at most 120 search requests/minute and an eight-minute collection budget.

The ROIC recovery itself has not been run locally: its key is provided by GitHub Secrets. The next daily-risk run supplies the actual accepted/rejected counts.

## Live history inspection

The current snapshot had 41 history/calendar cases (three more than the preceding snapshot). Live Yahoo inspection found:

- 9 same-listing adjusted series passed both series checks and the annual 53-week calendar check.
- 9 provider series had insufficient length; this is not proof of the company's IPO date or that no other vendor has older data.
- 20 name/class mismatches, 2 venue/identity mismatches and 1 invalid adjusted-price series remain rejected.
- 18 of the inspected rows already report a profile-versus-listing ISIN conflict. Do not fix these by stripping the share class from the name.

The nine series are included in cf_sector_recovered_series.json, with original identity fingerprints and retrieval times. Yahoo fallback imports them only while under 36 hours old, only for unchanged identities/currencies, and never over a newer matching cache entry. Expired seeds are ignored; the existing collector remains responsible for fresh observations. Normal peer cohort/calendar checks still run, so nine valid individual histories do not guarantee nine new comparisons.

Provider observations (without raw prices) are recorded in sector-recovery-observations.json. No alternative ADR, currency or parent-company history has been substituted.

## Activation and verification

Merge the PR, then run daily-risk on main. No precompute-3tage rerun or Cloudflare upload is required. Avoid simultaneous precompute publication; the workflow fails on a Git rebase conflict rather than silently overwriting another universe snapshot.

Local checks: 81 Python tests in risk_precompute, 2 existing listing-resolution tests, 24 sector/calendar checks, plus all 9 imported series checked against the production calendar metrics. Production metadata recovery and resulting coverage must be checked after the run.

