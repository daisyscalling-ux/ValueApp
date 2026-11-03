# Independent operating cashflow history

Production integrity run41661945531 verified1331input/published listings with identical input/processed hashes. The following extension addresses missing capex without substituting zero or changing valuation/risk scores.

Normalize annual operating cashflow / ending total assets independently for standard US-GAAP and IFRS concepts. Require matching accession, filed date, year end, annual form and currency; assets must be positive and instantaneous, operating duration330â€“400days. Retain signed negative cashflow. Detect conflicting duplicate facts and same-day revisions. Compare currency ratios only within matching filings; do not convert currency or merge reported amounts.

Store separately in operatingStocks, retaining original filing metadata and signed continuing/discontinued OCF derivation evidence. Revalidate on cache read and append solely to financial-history backfill. Missing PPE keeps its existing diagnostic and never becomes a complete FCF model. Existing UI already labels operatingCashflowAssets. Policy v9 makes older successful caches eligible once for the new series under the existing300company/900second budget; unfinished candidates continue in later runs. No new API endpoint or secret.

Original tests:
- BP: https://www.sec.gov/Archives/edgar/data/313807/000031380726000006/bp-20251231.htm
  Public copy: https://cdn.yahoofinance.com/prod/sec-filings/0000313807/000031380726000006/bp-20251231.htm
  Raw SHA256 db9a01a9f936a437fa70749d2442246687e4e354cee17f42d325944b4c101663 (29,303,477bytes).
  2024OCF/assets27,297/282,228=0.09671967345550406;2025 24,493/278,526=0.08793793039069961 (amountsUSDmillions).
- Rio Tinto: https://www.sec.gov/Archives/edgar/data/863064/000162828026009531/rio-20251231.htm
  Public copy: https://cdn.yahoofinance.com/prod/sec-filings/0000863064/000162828026009531/rio-20251231.htm
  Raw SHA256 0679e7d766da3e49aa3fe8e650bfe15f12051486e2a40034d18d418a5c6c8212 (24,692,666bytes).
  2024OCF/assets15,599/102,786=0.15176191310100598;2025 16,832/128,102=0.13139529437479508.

Selected fixtures preserve facts, referenced contexts and units, not whole reports. Public-copy hashes need not equal SEC distribution byte hashes. All original metadata checks still apply. Full originals tested locally; stored fixtures exercise collector -> independent cache -> history -> app shards, with unchanged example score and absent FCF.

322 Python tests pass. Two existing tests now cover both independent caches/metrics rather than assuming only one series. Review production operatingUpdated/operatingPeriods/remainingCandidates after merge and daily-risk. No Cloudflare UI upload. This series is not a substitute for full investment, financing, liquidity or solvency analysis.
