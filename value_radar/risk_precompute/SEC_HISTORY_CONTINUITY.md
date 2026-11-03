# SEC history continuity and latest-period selection

Production run41702294737 verified1331listings. Collector attempted248companies, updated229operating histories with1780observations and no remaining candidates. BP/Rio cashflow ratios appear in the app, currently selected from longer ROIC history; the new SEC source was artificially split by transport.

Use one accounting-method label for validated SEC companyfacts and original annual filing observations with the same namespace and OCF concept. Currency, identity, period, filing conflicts and derived continuing/discontinued distinctions remain enforced before joining. Each point retains its original URL and retrieval date. Other vendors or accounting definitions are not unified. Prior archive records are preserved; the joined series is first observed at the new run and never becomes point-in-time backtest data.

History selection now ranks the latest period before comparability, preventing an older multi-year series from hiding a current single observation or current gap. Comparable and longer series still win among equal periods. Historical missing comparisons remain null, never fabricated. Score values and valuation models unchanged.

Validation:325 Python tests passed. Offline replay of all229cached operating histories against current identity/coverage inputs produces172longer SEC-only views. Examples:BP/Rio/Novartis2->8periods,APD2->7. This is a controlled SEC-view comparison, not a promise that every displayed app view changes: ROIC/Yahoo sources can still be selected depending on period and comparable length. No additional source downloads required for history reconstruction.

Rollout:merge,run daily-risk once. Existing UI already supports points/source labels; no Cloudflare upload. Check BP/Rio latest2025and eight periods, provenance URLs, and remaining data gaps. Longer history does not supply missing capex or calibrate a risk probability.
