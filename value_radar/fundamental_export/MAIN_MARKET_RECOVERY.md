# Main-market annual financial recovery

Baseline: daily-risk run 40096333364 succeeded, dated 2026-10-24. Its coverage audit has 133 partial/missing financial cases in the priority markets (595 primary listings and 356 European listings). This batch fetched current Yahoo annual tables for all 133 cases and checked the same balance requirements again.

## Corrections

- London terminal-dot notation now maps `LSE:RR.` to `RR.L`, not `RR..L`. Seven failed cases (RR., NG., AV., UU., SN., TW., QQ.) were re-fetched successfully. Existing relevant failures get one retry after the mapping correction; timeouts and unrelated failures retain their cooldown.
- A reported total under `Cash Flowsfromusedin Operating Activities Direct` supplies operating cash flow when the ordinary label is absent. A reported `Capital Expenditure Reported` supplies capex when the ordinary total is absent. Statement, exact period, sign and source-label evidence are retained. Main labels take precedence. No continuing-operations cash flow, net investing flow, inferred zero or FCF subtraction is used as a replacement.
- A partial same-year refresh can retain a missing field from a recent earlier response only with the existing exact currency/period and matching earnings-anchor tests. Original per-field observation times are retained and expire independently after seven days; repeated partial responses cannot refresh that age. Current reported values take precedence. Conflicting anchors, mixed periods/currencies and expired fields are not merged.
- The risk balance validator now also checks retained per-field observation times.

## Batch replay, not a production completion claim

41 cases now meet generic corporate balance requirements; 2 meet their industry-specific book-context requirements. 71 remain partial and 19 remain missing. This includes data newly supplied by Yahoo, not only code effects. Production collection also uses SEC where eligible and may produce different results.

The 90 remaining cases split into 29 missing capex, 21 missing cash flow and capex, 20 missing debt, 2 missing debt/cash flow/capex, 1 missing cash and 17 without a usable annual block. In the debt cases the fresh balance table generally does not contain debt totals or complete components. Missing does not mean zero. The next source work should target those shared field groups, without relaxing financial definitions or risk-score thresholds.

Provider observation dates, endpoints, affected symbols and four observed direct-method cash-flow examples are in `evidence/main-market-financial-audit-2026-10-24.json`. Raw provider tables are not published.

## Activation

Merge, run `fundamentals-daily` on main (leave symbols empty), then run `daily-risk` on main. The second job evaluates the refreshed snapshots. No Cloudflare rebuild is required for the exported coverage update. This does not claim to complete a calibrated risk score or regulatory financial-sector data.
