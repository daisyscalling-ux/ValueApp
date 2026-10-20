# Empty news / missing identifiers investigation

Published 2026-10-20 run: 70 rows lack complete listing metadata and ISIN/CIK;
851 rows have no accepted recent articles. The empty group is concentrated in
Tokyo, OTC and European listings. Most empties have zero raw articles, not a
parser rejection. This does not establish that no relevant news exists.

The collector now records rawArticleCount, primary roicResult, provider,
fallbackAttemptAt and fallbackError. The primary remains ROIC. Yahoo is a bounded
alternative for unique rows with no current articles, including missing ROIC IDs.
An exact Yahoo symbol, matching normalized legal name and quote currency, and
EQUITY type are required. GBP/GBp is the only unit normalization. No guessed ISIN,
CIK or fuzzy company mapping is written into the universe. The risk coverage's
existing identity block remains authoritative for the 20 unresolved listings.

Each Yahoo attempt runs in a separate subprocess killed after 18 seconds; at
most 100 listings per run and within the existing news time budget. Oldest
fallback attempts are prioritized. Failed/empty attempts retry after 20 hours.
No article bodies are saved. Provider and fallback state are exported to the UI.

Local real-source checks: RR.L, HSBC and SAP all passed issuer, currency and
symbol validation but returned zero Yahoo news items. Both news/all Yahoo tabs
were empty for SAP. Yahoo RSS attempts were HTTP errors, so no RSS workaround is
enabled. The first GitHub run must measure actual recovery; zero recovery is
possible. This change improves source coverage and diagnosis, not a guarantee
that all international issuers have articles.

Tests cover exact identity, wrong issuer/currency/symbol/type, timeouts, news
normalization and absence of full article bodies. No new API key is required;
daily-risk already installs the pinned yfinance package. Merge then run daily-risk.
