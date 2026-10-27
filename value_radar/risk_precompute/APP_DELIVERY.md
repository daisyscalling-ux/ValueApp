# App delivery and EUR comparison display

Production PR73 verification: 486 supplementary EUR comparisons; 1,118 of 1,330 listings have some comparison context. Main markets: 892/948 (94.1%). Strict coverage remains separate at 452 overall; no claim that supplementary context certifies direct competitors or the risk model.

## Delivery defect and repair
The full coverage report is now 13,262,051 bytes, exceeding the Cloudflare reader's previous 10,000,000-character guard. A valid full report could therefore be rejected entirely.

risk_app_export.py publishes cf_risk_app_manifest.json and 32 deterministic hash buckets under risk_app/. Each JSON filename is its SHA-256 content digest. Original rows and timestamps are unchanged. Largest current shard: 546,838 bytes; manifest: 26,965 bytes. The previous generation is retained for cached manifests, while older generated digest files are pruned. Stale, duplicate, oversized or invalid input fails before manifest publication.

The Cloudflare patch in Patrick's local cf folder reads the manifest and only the selected shard. It checks stream byte limits, SHA-256, matching report timestamps, unique exchange-aware listing resolution, and the existing freshness/identity checks. The in-memory shard cache is limited to four entries. No whole-report download fallback.

## Local app change
The existing Desktop/cf app shows a supplementary EUR comparison when same-currency peers are insufficient. Provider-industry and broad-sector alternatives remain expandable. FX source, dates, local trading currency, unhedged FX exposure and non-synchronous close times are explained. Stale/malformed FX context is hidden. Fair Value and risk-score formulas are unchanged.

## Verification
202 Python tests passed, 13 frontend/worker tests passed, targeted strict TypeScript check and production build passed. Full 1,330-row reconstruction is exactly equal to the source. The actual shard reader was exercised against 20 real listings with unchanged selected data. The Applied Materials view was visually checked in the browser using the current production snapshot.

## Release order
1. Merge this PR and run daily-risk on main (or wait for schedule).
2. Confirm cf_risk_app_manifest.json and risk_app/ were published.
3. Deploy the updated existing Desktop/cf folder with npm run deploy.
No new secrets. App source changes are local, not automatically deployed by merging this data-pipeline PR. Until the manifest exists, the updated reader will report coverage unavailable. The old whole-universe audit files remain published for inspection.
