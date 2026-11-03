# Risk run continuity and publication integrity

Verified production run 41532691963 (2026-11-02): manifest has 1,330 listings again. SEC collector parsed 22 original reports, accepted 21 observations, updated 8 companies and retained 217 stock histories. APD and Novartis original 2024/2025 comparisons are present in published app shards. This verifies PR87 recovery after PR88 restored the universe; it does not imply every risk domain is complete.

Three coordinated protections:
1. daily-risk follows successful precompute-3tage completion on main. Same repository and non-PR producer checks; checkout remains trusted main. Failed producers do not start collection. Existing manual/scheduled runs remain available. Reference: https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#workflow_run
2. Capture the exact input universe hash before local identity enrichment. At completion verify current universe listing set against coverage and manifest, matching timestamps/counts, all shard hashes, shard indexes and exact published stock values. Results must originate after capture. Store both original and processed hashes in cf_risk_run_integrity.json and manifest inputUniverse. No risk or valuation values modified.
3. Before each push fetch current main and reject if its universe differs from the captured input. Unrelated repository changes may rebase normally. A changed universe leaves the completed calculation downloadable as an artifact, requiring another run instead of publishing stale membership. Only a successful final packaging/integrity step allows publication.

Tests: 316 local risk tests pass, including nine new cases for missing listings, stale results, tampered payloads, altered scores, concurrent exports, local identity enrichment, invalid input and workflow ordering. Offline check of all 32 current production shards agrees exactly with coverage for 1,330 listings. The offline check used a reconstructed capture record solely for testing, not as evidence of the original job input hash; actual capture starts with the next deployed workflow.

Rollout: merge and run daily-risk once to verify the new capture/report. Future successful precompute runs trigger the follow-up automatically. No Cloudflare UI upload. Published provenance is additive; old clients can ignore it.

Limitations: file consistency does not establish economic correctness, completeness of vendor financial fields or calibrated risk probabilities. Concurrent universe changes intentionally fail publication; artifacts retain progress. Non-universe source files are not yet guarded by this hash.
