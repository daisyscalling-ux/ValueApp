# Empty archive repair and independent EDINET source

Production baseline: 2026-10-26T17:24:19Z. 1,330 listings, 176 industry contexts and 1,057 listings with at least one comparison context. Main-market open balance cases: 58.

The prior normalizer fix did not immediately retry older completely empty ROIC archives: their normal cooldown was still active. The migration now schedules one repair attempt per legacy empty archive, records normalizationVersion on every attempt, and then restores normal retry limits. Explicit zero remains a reported value. Identity and market gates remain active. Snapshot replay schedules six such repairs.

When every primary balance ratio is unavailable, a verified EDINET annual filing can independently supply its own ratios. It must pass identity, filing status, provenance, annual duration, currency and freshness checks. No stale primary fields are copied into the replacement. Existing available metrics are never replaced. Partial originals remain partial; absent debt never becomes zero.

Snapshot replay recovers FCF/assets for TSE:3697 (18.4076%) and TSE:7453 (6.2246%). Both still lack verified total debt. All 2,444 previously available balance metric values are unchanged. The workplan separates the automatic ROIC retry from the remaining original debt-scope review. Valuation and scoring formulas are unchanged.

Validation: Python suite; 14 EDINET integration checks, 33 universe/queue checks, 12 field-level checks; whole-universe replay at the original audit timestamp. Replay files are not published as production data.

Deployment: merge and run daily-risk on main. No new secrets or Cloudflare deployment. Production results must be checked after that run; local replay does not prove provider availability.
