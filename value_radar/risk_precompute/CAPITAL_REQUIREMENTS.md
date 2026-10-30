# Verified CET1 requirements and reported headroom

The daily job now verifies the reviewed Federal Reserve capital-requirements document, then joins individual CET1 requirements to the existing exact holding identity. The comparison is reported CET1 minus the applicable requirement, expressed in **percentage points**, not a relative percentage return. It does not alter valuation or the risk score.

Source: https://www.federalreserve.gov/publications/files/large-bank-capital-requirements-20260624.pdf , table 1, page 3. The reviewed file SHA256 is in `regulatory_export/fed-capital-requirements.json`. Nine rows are tied to the previously reviewed holding RSSD/name identities. Minimum ratio, stress buffer and GSIB surcharge must sum to the total. No fuzzy matching or borrowing a subsidiary's requirement.

## Dates and refresh

- The comparison uses report dates on/after publication (2026-06-24), not earlier quarters. The June 30 original capital ratios are eligible.
- Review expires on 2026-12-31 because the next annual GSIB update can change requirements. This is a conservative review boundary, not an assertion that all regulations expire then.
- Daily HTTPS fetch has a 20-second timeout and 2 MB cap, requires PDF content and the reviewed original URL, and verifies the complete document hash.
- A network failure may retain an unchanged registry's last successful verification for at most seven days. Its original verification timestamp is preserved. A changed document hash immediately blocks the requirement until reviewed; it is never silently parsed as a new rule.
- Initial source verification was performed live on 2026-10-30 and is included as a dated snapshot. No API key needed.
- To update the source, review the new official table, identities, effective dates and component sums and update the registry and allowed source in the collector/reader through a PR.

## What is and is not completed

Seven bank CET1 requirement checks can now be fulfilled; two specialist financial issuers receive the comparison as context. This checks CET1 only: other capital ratios, liquidity, credit mix and multi-quarter development remain distinct. Positive headroom is not an investment recommendation or a complete regulatory compliance opinion. The UI reopens the requirement if its source verification expires.

Validation: 219 risk Python tests; 15 new capital reader checks; existing regulatory-context and 33 universe checks; current 1,329-listing replay with unchanged basic balance metrics, nine comparisons and seven fulfilled bank CET1 requirements. UI tests and targeted TypeScript check pass. Live source fingerprint matches the reviewed PDF.

After merge, run daily-risk and deploy the prepared Desktop/cf app. The source-verification report is saved to `cf_capital_requirements.json`; app delivery continues through the existing bounded shards.
