# Business-group comparison in EUR

## Why
The 2026-10-26 membership snapshot has 537 listings whose business group has enough issuers but whose same-currency cohort does not. This is structural, not an API error. Existing strict same-currency comparisons remain unchanged. A supplementary EUR investor perspective uses the existing business groups, at least five other independent issuers and common historical observations. It does not broaden a business group or certify direct competitors.

## Source and calculation
ECB daily reference rates: https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html
Historical CSV: https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.zip

The ECB quotes currency units per EUR. Convert each adjusted local price as local price / units per EUR (GBp/GBX first divided by 100). Use actual same-date FX only; omit missing dates, with no forward fill, inversion guess or substitute currency. EUR prices use unity on dates in the ECB calendar. Changes in FX are included, not hedged out. ECB reference times and market closes differ; this is descriptive end-of-day context, not an executable return or backtested trading signal.

The bounded downloader stores 730 calendar days, ignores unfinished UTC days, validates dates, finite positive rates, freshness and archive structure. Failed downloads retain the original dated archive. The consumer requires FX retrieval within 36 hours and last observation within seven days, and validates each source series and identity before conversion. Existing annual/common-calendar history guards apply after conversion. Duplicates and self issuers remain excluded. Unsupported currencies stay missing.

## Integration
The daily-risk workflow fetches FX once, stores cf_ecb_fx.json, and adds currencyAdjustedContext to cf_sector_context.json. The supply plan and coverage/workplan carry it separately. Strict peer state is not promoted. Fair Value, risk-score weights and historical validation are unchanged. No credentials required.

This PR delivers the data pipeline and coverage reporting. The current Cloudflare UI has not been changed to render the new context; frontend presentation is a subsequent step after the full-universe output is checked.

## Validation
197 Python tests and 84 TypeScript checks passed (24 sector/calendar, 6 industry, 6 broad-context, 33 universe, 15 FX). The exporter was exercised end to end in a separate local pilot folder.

Live pilot: ECB archive provided 508 completed-day observations. Eight of nine requested equity histories passed the existing collector. ASM, Soitec, BESI, Aixtron, Lam Research, Teradyne, Applied Materials and Lasertec each gained seven same-business-group peers in EUR. Common window: 2025-10-23 to 2026-10-23. The Tokyo Electron request did not pass the collector and remained excluded. All existing strict fields were byte-equivalent in the replay. No production-snapshot coverage gain is claimed from this small pilot, and no pilot prices are committed.

After merge run daily-risk on main once, or wait for its schedule. The full-universe result depends on the fresh series cache and ECB availability. No Cloudflare upload required for this data pipeline step.
