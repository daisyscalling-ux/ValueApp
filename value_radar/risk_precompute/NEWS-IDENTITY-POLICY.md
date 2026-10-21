# Systematic news identity checks

Scope: Yahoo company-news attribution only. These rules neither repair the universe security master nor change financial valuations, price mappings or risk weights.

## Decisions

1. Duplicate Yahoo tickers or duplicate listing keys in the current universe block fallback retrieval.
2. Yahoo symbol, currency (GBp/GBX converted to GBP) and EQUITY type must still match. Conflicting explicit share-class labels are rejected before any name comparison.
3. Exact names and existing explicitly reviewed name pairs retain their paths.
4. A new normalized-name path handles punctuation, accents, German umlaut spelling, Nordic characters, a leading “The”, and trailing legal forms. It uses Yahoo's long name, never a truncated short name. Meaningful words such as Bank, Holding and subsidiary descriptors, and class annotations, are retained. It requires a syntactically valid ISIN with valid checksum, exchange/listing metadata, and no canonical-name collision with another ISIN in the universe. Names shorter than five letters after normalization do not qualify. This is not fuzzy matching.
5. Names shared by different ISINs can represent legitimate share classes, ADRs or different companies. They are not automatically declared corrupt; the relaxed matching path is simply unavailable.

The ISIN is the universe's existing identifier, not independently verified against Yahoo. An accepted normalized name is evidence of provider-name equivalence for news, not a certified security identity.

## Daily lifecycle

- Every run builds ambiguity/collision context from the entire current universe, including newly added stocks.
- Input fingerprints include ticker, listing, exchange, ISIN, currency, names and ambiguity flags. A changed fingerprint discards old news and retry timestamps instead of reusing another identity's cache. The first migration establishes fingerprints without claiming to have rechecked all old entries.
- A changed identity-policy version permits one priority retry of old name failures within existing limits (100 Yahoo attempts, existing total budget). The attempt stores the policy version even on failure, so persistent conflicts do not loop on every invocation.
- Existing 26 reviewed aliases remain; this change adds no per-company aliases for the twelve new cases.
- `cf_news_identity_audit.json` is published and attached to the daily-risk run. Each listing is marked not_checked, legacy_check, rejected or accepted_current_policy. Last attempt and reason remain visible in the report. Old evidence is not retroactively labeled as checked under the new policy.
- Reports and archive contain no API keys or provider exception strings.

## Validation, 21 October 2026

Metadata audit on the available 1,330-row universe: zero ambiguous listing/ticker rows; 33 rows whose normalized names collide across ISINs; 70 missing/invalid ISINs (the snapshot's 70 missing identifiers). This is an offline metadata audit, not 1,330 new Yahoo requests.

Twelve current Yahoo profiles were fetched and retained as regression fixtures. Eight pass the general rules without new aliases: Ørsted, Magnum Ice Cream, Continental, Beiersdorf, Konecranes, Sartorius, Ringkjøbing Landbobank and Edenred. Orion, Kesko and Stora Enso expose conflicting class labels and remain rejected; Elisa retains an unresolved class-name mismatch. These require security-master investigation, not a relaxed news filter.

29 tests cover normalization, collisions, wrong symbols/currencies/security types, short brands, subsidiaries, share classes, ISIN checksums, policy retry limits, legacy report labeling, cache invalidation, stored-news cleaning, time bounds and fixed diagnostic codes. Passing profile checks does not imply Yahoo supplies articles; production recovered counts must be checked after the next run.

After merge: run daily-risk on main. No new secret or Cloudflare deployment needed. Scheduled runs use the same policy and report automatically.

