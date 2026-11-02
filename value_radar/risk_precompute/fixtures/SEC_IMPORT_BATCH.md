# Annual original import: date formats, large filings, targeted retry

APD and Novartis selected fixtures contain only contexts, units and allowed facts extracted from the original reports. Full-document offline tests recover two 2024/2025 periods each. PDD and TSM full-document results are identical to the preceding parser.

APD: https://www.sec.gov/Archives/edgar/data/2969/000000296925000055/apd-20250930.htm
SHA256: 8b9a416edea2c6995cc577ecea30b25b5cc09496cacaacdc9e74c6b6fda7ffa1
Novartis: https://www.sec.gov/Archives/edgar/data/1114448/000111444826000004/nvs-20251231.htm
SHA256: 1a8da4a6659c4dc8cd9f4a8a6af3d382a20172587528eaa8361a15be50507717
Downloaded public distribution copies: https://cdn.yahoofinance.com/prod/sec-filings/0000002969/000000296925000055/apd-20250930.htm and https://cdn.yahoofinance.com/prod/sec-filings/0001114448/000111444826000004/nvs-20251231.htm

The parser retains selected subtrees in one pass instead of building two full document trees. Reader and parser share a 40,000,000-byte ceiling. An 18 MB synthetic prose extension preserves all original PDD facts. Existing timeout and collector budgets remain active. BP and Rio Tinto full-document validation is pending: additional downloads were not executed because automatic approval review hit a usage limit. A higher size limit does not guarantee those issuers have supported complete facts.

Policy v8 retries cached partial results once after previous metadata/size errors. Other identity, namespace, currency, period and filing checks remain unchanged. No risk score weights, valuation assumptions, or UI changes.

Validation: 307 Python tests passed. After merge run daily-risk once; no new Cloudflare UI upload is required. Check originalError, originalObservations and published history periods before claiming production coverage.
