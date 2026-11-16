# News coverage audit — 2026-10-20

All 15 previously generic Yahoo ValueErrors were reproduced as issuer-name mismatches. Examples: Bayer AG vs Bayer Aktiengesellschaft; Air Liquide SA vs L'Air Liquide S.A. All 15 passed after adding explicit observed provider-name pairs bound to the exact universe listing and existing ROIC ISIN. Yahoo symbol, currency and EQUITY checks still apply. These aliases are not a new security master or an independent ISIN verification. Recheck them when provider names/listings change. All 15 live Yahoo responses still contained zero articles.

The child process now returns allowlisted diagnostic codes, distinguishing identity checks, dependency failure, rate limits, timeout and generic provider errors. Provider exception messages, URLs and keys are never published.

Google News RSS was tested against HSBC, SAP, Rolls-Royce and Air Liquide. It returned candidates for all four, but many were quote pages, metrics pages or unrelated headlines. The collector requires the full supplied company name in the headline, seven-day dated results and a Google RSS article link; known quote/forecast/metric/crypto landing-page patterns are excluded. HSBC, SAP and Rolls-Royce retained candidates; Air Liquide did not with its full ROIC name. No broad fuzzy-name relaxation is used to force coverage.

Google is a search index, not an original news provider. Dates and events are not independently confirmed. Headlines are review candidates, never proof of adverse events or low risk. Links remain Google redirect links; publisher bodies are not fetched. The provider label is carried by the existing frontend. Google empty results are recorded separately and do not turn unknown primary coverage into a successful empty company feed.

The daily job attempts at most 50 Google queries after ROIC/Yahoo, prioritizes oldest attempts, waits 20 hours between retries, and respects the existing total budget. This rotates over missing listings; it is not daily complete news coverage of the whole universe. Query language is English. No new API secret required.

Validation: 15 Python tests, including false matches, old/future dates, invalid links/schema, diagnostic privacy, alias identity constraints and persistence of cached alternative news. Live provider probes described above. Production added coverage must be measured after merge and daily-risk run using googleAttempted/googleRecoveredListings.

After merge: run daily-risk on main. No Cloudflare code change or redeployment is needed for this change; the existing provider label supports the added source.


## Financial Times (16.11.2026)

**Quelle:** die öffentlichen RSS-Feeds der FT-Rubriken Märkte, Unternehmen und Technologie (`https://www.ft.com/<rubrik>?format=rss`), je 25 Einträge.
- Die Feeds werden zusammengeführt; derselbe Link erscheint nur einmal.
- Übernommen werden wie bei den anderen Quellen nur Titel, Datum, Herausgeber und der **Originallink zu ft.com**.
- Kein Artikeltext und keine Umleitung über Dritte. FT-Artikel sind teils kostenpflichtig; der Link öffnet die FT-Seite selbst.

**Teilausfall:** Fällt eine Rubrik aus, liefern die anderen weiter. Erst wenn keine liefert, gilt die Quelle als gestört; die Artikel der letzten 7 Tage bleiben dann erhalten, mit Grund.

**Probelauf 16.11.:** 55 Artikel (75 Einträge, 20 doppelt über Rubriken).

**Tests:** `scripts/test_export_market_news.py` (im Workflow market-news).

## Bloomberg und Wall Street Journal (16.11.2026)

`scripts/export_market_news.py` exportiert zwei neue Quellen mit je vier öffentlichen Rubriken-Feeds, als Rückfall für den Worker-Marktfeed (valueapp-cf):
- `bloomberg`: Märkte, Wirtschaft, Konjunktur, Technologie unter `www.bloomberg.com/feeds/…`.
- `wsj`: Märkte, US-Wirtschaft, Konjunktur, Technologie, Dow-Jones-Feeds.

Exportiert werden nur Titel, Datum und Originallink; Artikel älter als 7 Tage fallen weg. Fallen alle Rubriken aus, steht der HTTP-Grund im Export, und es werden keine Artikel ergänzt. Die URLs sind identisch mit `worker/market-feed.ts`.

Livetest 16.11.2026, ca. 19:30 UTC: je 80 Artikel, neuester 19:05 UTC (Bloomberg) bzw. 19:17 UTC (WSJ). Tests: `scripts/test_export_market_news.py` mit 2 neuen Fällen.

Hinweis: Der stündlich geplante Lauf `market-news` startet bei GitHub derzeit nur alle 4–8 Stunden (13.–16.11.: 12 Läufe in 3 Tagen).
