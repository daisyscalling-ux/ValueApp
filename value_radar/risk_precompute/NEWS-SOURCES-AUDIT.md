# News coverage audit — 2026-10-20

All 15 previously generic Yahoo ValueErrors were reproduced as issuer-name mismatches. Examples: Bayer AG vs Bayer Aktiengesellschaft; Air Liquide SA vs L'Air Liquide S.A. All 15 passed after adding explicit observed provider-name pairs bound to the exact universe listing and existing ROIC ISIN. Yahoo symbol, currency and EQUITY checks still apply. These aliases are not a new security master or an independent ISIN verification. Recheck them when provider names/listings change. All 15 live Yahoo responses still contained zero articles.

The child process now returns allowlisted diagnostic codes, distinguishing identity checks, dependency failure, rate limits, timeout and generic provider errors. Provider exception messages, URLs and keys are never published.

Google News RSS was tested against HSBC, SAP, Rolls-Royce and Air Liquide. It returned candidates for all four, but many were quote pages, metrics pages or unrelated headlines. The collector requires the full supplied company name in the headline, seven-day dated results and a Google RSS article link; known quote/forecast/metric/crypto landing-page patterns are excluded. HSBC, SAP and Rolls-Royce retained candidates; Air Liquide did not with its full ROIC name. No broad fuzzy-name relaxation is used to force coverage.

Google is a search index, not an original news provider. Dates and events are not independently confirmed. Headlines are review candidates, never proof of adverse events or low risk. Links remain Google redirect links; publisher bodies are not fetched. The provider label is carried by the existing frontend. Google empty results are recorded separately and do not turn unknown primary coverage into a successful empty company feed.

The daily job attempts at most 50 Google queries after ROIC/Yahoo, prioritizes oldest attempts, waits 20 hours between retries, and respects the existing total budget. This rotates over missing listings; it is not daily complete news coverage of the whole universe. Query language is English. No new API secret required.

Validation: 15 Python tests, including false matches, old/future dates, invalid links/schema, diagnostic privacy, alias identity constraints and persistence of cached alternative news. Live provider probes described above. Production added coverage must be measured after merge and daily-risk run using googleAttempted/googleRecoveredListings.

After merge: run daily-risk on main. No Cloudflare code change or redeployment is needed for this change; the existing provider label supports the added source.

