# SEC annual cashflow context

This collector adds historical context for corporate issuers. It does not supply
complete free cashflow, change valuation inputs, award risk-score points or
claim point-in-time backtest data. Banking/insurance/REIT-specific coverage is
handled separately.

## Multiple reported currencies

Some annual reports publish both a reporting-currency statement and a convenience
translation. For example, TSMC's 2025 Form 20-F, note 3, explains that its TWD
statements also appear in USD at a single convenience exchange rate:
https://www.sec.gov/Archives/edgar/data/1046179/000162828026025362/tsm-20251231.htm

The collector previously excluded all periods with more than one complete
currency. It now retains those separate currency series only when:

- Each series independently has assets, operating cashflow and the supported
  cash investment concept, in a single currency/framework/filing.
- All currency series have identical accession, filing date, annual start/end,
  namespace, investment concept and metric scope.
- Both operating cashflow / assets and investment cash payments / assets agree
  across every reported currency. Comparing only their difference would permit
  offsetting errors.

Selection is now performed across complete filings **before** comparing
currencies. For each annual end date and metric variant, only complete
observations with the newest filing date are considered. An older USD
convenience translation does not invalidate a newer complete TWD observation.
No fields are combined between filings. Same-day conflicting values stay
excluded, and a disagreement in the newest complete currency pair does not
fall back to an older agreeing pair. A single retained currency is not labelled
as cross-currency verified. This is still the latest complete observation,
not a guarantee that all newer filings have sufficient standardized facts.

The older independent-per-currency selection could compare different accessions
and reject a valid annual observation. This failure is reproduced in regression
tests. Its exact contribution to each live issuer's remaining gaps must be
measured after the next run; no live recovery count is inferred from fixtures.

The concordance threshold is a conservative numerical policy, not an inferred
issuer rounding precision: relative tolerance 0.0001 (0.01%) or absolute ratio
tolerance 0.000001 (0.0001 percentage points). Values outside it remain excluded,
even if a human might establish that they are translations. Neither native
currency nor an exchange rate is inferred. Values are never converted, averaged
or joined across currencies. Currency remains part of the historical series key.

US-GAAP property/plant/equipment cash payments and broader productive-asset cash
payments retain distinct metric names. IFRS and US-GAAP observations are never
combined to complete a missing statement. Negative investment payments are not
silently reversed. Assets must be an instant balance, cashflows 330–400 days.

## Audit and rollout

Every attempted normalization now records counters for date, duration, malformed
facts, conflicting filings, missing same-filing fields, sign failures and
currency conflicts. These are processing counters, not unique companies:
one source fact can be examined for more than one supported metric variant.
Missing-source diagnostics list currencies for each required field and support
both US-GAAP and IFRS. No raw responses, credentials or contact details are logged.

The run report keeps `periods` (stored observations) and additionally reports
`fiscalYears` (distinct annual end dates per updated listing). Different currency
or metric versions are not extra fiscal years. `currencyConcordantPeriods` and
`currencyConflictPeriods` count period/metric-variant checks in this run.

Failed attempts under the old collection policy are eligible for retry on the
next daily-risk run. Successful caches keep the existing seven-day refresh rule.
An exception applies to partial successes under an older policy with recorded
currency conflicts: these are retried once, so the four partially recovered
issuers do not wait seven days for the corrected filing selection. Other
successful caches are retained. After the retry, the normal refresh rule applies.
The separate issuer-name policy remains unchanged. Existing ambiguous identities
remain blocked; numeric concordance does not verify an issuer identity.

After merge run daily-risk on main. Inspect `cf_sec_cashflow_history.json`, its
report/attempt diagnostics, and the resulting financial-history export. No new
secret or Cloudflare code deployment is needed for this collector-only change.
Additional production coverage can only be established after that live run;
synthetic regression tests do not prove how many issuers will be recovered.
