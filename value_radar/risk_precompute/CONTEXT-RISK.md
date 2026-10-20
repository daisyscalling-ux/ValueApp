# Universe-wide news and industry context

`daily-risk` now collects company headlines after history collection, then
publishes both domains in `cf_risk_coverage.json`. It retains the existing score;
these observations are not calibrated probabilities and add no score points.

## Industry comparison

Same ROIC industry classification and quote currency, current total-return
history, metadata no older than 90 days, at least five other issuers. Each issuer
gets one vote using CIK, LEI, or normalized company name; fallback names can miss
legal-name variants, so this is not a complete global issuer identity registry.
Funds, preferred shares, duplicate listing rows and unsupported security types
are excluded. The statistic is drawdown from each stock's own recent high,
compared with the peer median; it is not a sector index, direct-competitor list,
correlation or causal contagion estimate. Price dates differ by at most three days.

## News

Official API: https://www.roic.ai/api/v2/docs/company/news

The collector uses ISIN or CIK, never an ambiguous bare ticker. Missing IDs remain
explicit. Queries retrieve at most 30 articles over seven days, without pagination:
this is a bounded sample, not exhaustive coverage. Save titles, publisher, links,
dates and unverified headline tags only; discard full article bodies. Headline
rules cover English/German earnings warnings, credit distress, legal/regulatory
issues, operational disruptions and competition. Negation, hypothetical language,
article subject and cross-company relevance require human review. Other languages
may yield no tags. Empty responses and no matching rule do not mean low risk.

The collector is sequential, at most ~85 requests/minute, bounded to 20 minutes,
checkpointed every 20 requests. It runs after the history step, not in parallel
with it. Other workflows may still share the account quota. A 429 stops this pass;
later runs resume oldest-attempt-first. Successful snapshots refresh after 20h;
failed attempts cool down for 6h. HTTP 401/402/403 stop the pass and fail the step.
No secret-bearing URLs or exception messages are published. A failed request keeps
the old observation timestamp; coverage requires a successful fetch within 36h.

`cf_company_news.json` contains the bounded snapshot. The coverage view includes
at most six recent articles per stock to keep Cloudflare payloads bounded. First
live API validation requires the existing ROIC_API_KEY GitHub secret. Schema and
network failures are not treated as successful empty responses. Initial collection
can need multiple daily runs when many upstream requests time out.

After merge run daily-risk. Deploy the updated local Cloudflare `cf/dist` build
to display the prepared comparison and collapsed source list. Existing direct
news feeds remain separately available. No new secret is required.
