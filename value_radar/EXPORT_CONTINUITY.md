# Bounded universe updates

Incident verified on 2026-11-02: precompute run 41407940491 built 1,333 intended listings, stopped after 675 at its 160-minute export budget and published 673 rows. The following successful daily-risk run 41440333458 consequently considered only 673 listings, skipping APD/NVS/TSM/PDD entirely. Its eight original documents parsed successfully (including BP/RIO/TTE) but yielded no new complete cashflow observations. PR87 therefore remains only partially production-verified, not a failed date-format fix.

Changes:
- Read current and up to twelve prior committed exports; recover only currently requested tickers with matching qualified listing, ISIN, currency identity and observations no older than fourteen days. Conflicting security identities are excluded.
- Preserve export_observed_at on retained rows. The document stand is publication time, not a claim that every row is refreshed. export_status and scan refreshed/retained/pending make partial progress explicit.
- Missing/oldest observations are processed first, so a fixed budget no longer permanently starves the US end of the list.
- Fresh rows replace whole rows, not individual fields. Explicit identity rejections remove cached rows. Removed universe members are not restored.
- Publisher rejects removal of more than 10% (minimum 25) of an established >=100-listing universe, even if unrelated new rows hide the numerical loss.
- Full checkout history permits recovery from an already published incomplete snapshot. No previously cached quote is relabelled as a new market quote.

Validation: six continuity/export tests, seven real local Git publication tests and 307 risk tests pass. Against real Nov 1/Nov 2 exports, 1,309 of 1,330 rows pass recovery identity/date checks; 21 unqualified or conflicting rows remain excluded. Actual next-export count depends on current membership and successful fresh retrievals.

Rollout: merge, run precompute-3tage to regenerate the universe, then daily-risk against the regenerated file. No Cloudflare UI upload. Verify app manifest listing count, APD/NVS presence and original observations after daily-risk. Retention is bounded and is not proof of current index membership or fresh financial figures.
