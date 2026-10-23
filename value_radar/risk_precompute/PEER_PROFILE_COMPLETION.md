# Peer profiles: completed batch, 2026-10-23

The remaining 460 eligible, due listings were fetched using the identity-checked Yahoo metadata collector. 434 profiles were updated; 23 issuer-name mismatches and 3 ambiguous listings were rejected. No ROIC calls or price-history requests were made. Collection resumed from its checkpoint after a local file-access interruption; counts below cover both segments, while the archive report describes the final segment.

There are now 1,142 stored listing profiles. This is not a count of independent companies or usable return comparisons.

## Membership audit of 1,329 listings

- 1,259 classified listings collapse to 1,072 issuers (187 additional listings).
- 979 issuers use provider subindustries, 12 reviewed business models, and 81 broad industry context groups.
- 70 listings remain excluded: 69 unconfirmed listings and one unsupported security type.
- 457 listings have at least five other issuers in their group and trading currency, BEFORE price-history eligibility checks.
- 299 listings have fewer than five other issuers even before the currency restriction.
- 503 listings have at least five other issuers globally, but fewer than five in the target trading currency.
- The 172 groups include 109 structurally small groups.

Small groups are not padded with unrelated companies. Alternative listings of the same issuer never count as additional peers. GBP/pence share a currency unit. Membership counts do not certify fresh prices, calendar coverage, independently verified competitors, or an investment signal.

## Activation

Merge this change, then run daily-risk on main after the current precompute-3tage run finishes to avoid competing ROIC usage. The existing workflow loads cf_peer_metadata.json, rebuilds issuer groups, and checks aligned return histories. No Cloudflare deployment is required.

The collector still refreshes profiles after 30 days, observes a one-day retry cooldown and checkpoints attempts. SECTOR_METADATA_ONLY=1 permits profile-only collection without reading as missing or overwriting the stored price-history cache. Existing daily-risk behavior remains unchanged unless that flag is explicitly set.

cf_peer_groups.json adds groupSizeReason and sameCurrencyPeerIssuerCount. cf_sector_supply_plan.json exposes them under membershipOnly, separately from actual eligible peer counts.

Validation: 33 profile/group tests and 24 sector/calendar checks passed locally. Actual production comparison coverage must be measured after daily-risk; the 457 membership candidates are not a coverage forecast.
