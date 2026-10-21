# Listing repair and targeted news supply — 21 October 2026

## Confirmed identity defects

The existing universe combines B/R tickers with A-share profile identifiers:

| Listing | Previous ISIN | Correct ISIN | Class | Evidence |
|---|---|---|---|---|
| HEL:ORNBV | FI0009014369 | FI0009014377 | B | [Orion issuer report via Nasdaq](https://attachment.news.eu.nasdaq.com/a2b9b44b33b69ce0a09b31146c317ec56) |
| HEL:KESKOB | FI0009007900 | FI0009000202 | B | [Kesko share information](https://www.kesko.fi/en/investor/share-information/) |
| HEL:STERV | FI0009005953 | FI0009005961 | R | [Issuer share information](https://www.storaenso.com/en/investors/shares-and-shareholders), [Nasdaq conversion announcement](https://view.news.eu.nasdaq.com/view?id=b296c3dc1f33278cb70402faf127b1eb7&lang=en) |

`peer_metadata.metadata` previously preferred the profile ISIN over the selected listing ISIN. It now prefers the concrete listing's identifier and name, and records a profile/listing conflict. This prevents the same precedence error for future stocks when listing data is present.

Three guarded reference records additionally correct these confirmed cases during export and at news-loader runtime. They require exact ticker/listing/currency and a known input name/ISIN; unexpected inputs or an expired review fail closed. References expire on 21 April 2027. Original metadata and source URLs are retained. The new `share_class` field preserves the class distinction although the company display name is now the issuer name.

The remaining six rejected profiles (Elisa, Recordati, Swatch, Indra, Porsche and Verbund) use explicit provider-name pairs with source links. Their ISINs are not changed. In particular, Porsche AG is not mapped to Porsche Automobil Holding SE. All nine newly retrieved Yahoo profiles pass with these corrections; this does not promise that Yahoo returns articles.

Financial figures, share counts, price history and valuation outputs are not rewritten by the metadata correction. They have not been independently revalidated in this block.

## Supply bottleneck and change

The inspected snapshot contained 774 article-empty rows not yet queried through Google and 282 successful empty Yahoo records. The collector now:

- reserves the final five minutes of the 20-minute budget for fallback work;
- queries Google before Yahoo, prioritizing oldest/unattempted listings, with a maximum of 150 Google queries instead of 50;
- reserves up to two minutes of the remaining fallback budget for Yahoo;
- retains the 100-attempt Yahoo ceiling, but waits 72 hours after successful empty Yahoo replies and seven days after unresolved identity failures;
- overrides the wait once when a reviewed alias or identity rule changes;
- avoids a Yahoo request when Google has already recovered current articles, unless a corrected identity explicitly requires retesting;
- publishes `cf_news_supply_plan.json`, distinguishing current articles, identity review, not-yet-queried Google, failed Google requests, no eligible Google article and refresh due. No state is a risk score.

These are bounded rotating queues, not a guarantee to refresh every listing's news daily. No additional secret is required.

## Verification and rollout

36 Python tests pass, including listing/profile precedence, guarded/expired references, preservation of financial fields, fingerprint compatibility for unaffected stocks, retry intervals, distinct coverage states and the Google-before-Yahoo path. Nine live profile snapshots pass the repaired attribution. Existing stored news for an unchanged stock keeps its fingerprint; corrected listings invalidate their old news cache.

After merge run daily-risk on main. News uses the correction immediately. Screener metadata is corrected by the next export started from the merged main; a precompute job already running the old checkout will not adopt these changes. No Cloudflare deployment required. Production coverage gains must be assessed from the resulting report, not inferred from passing tests.

