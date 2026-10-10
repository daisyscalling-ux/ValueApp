# SEC financial pilot

Read-only audit for Microsoft and Oracle. Does not update production scores or universes.

Set the Actions secret SEC_USER_AGENT to `ValueApp <real operator email>`. Do not commit the contact address. Merge this workflow into main and run **sec-financial-pilot** manually from Actions. Pull requests run offline tests only; they do not receive the SEC secret.

The run summary and artifact contain report.md, report.json and original SEC JSON responses with retrieval timestamps and SHA-256 checksums. Artifacts expire after 90 days: download and retain them if they are needed for a durable historical archive. HTTP failures produce an incomplete report and fail the job; a green job only confirms the audit executed, not that every financial field is available or a risk model is validated.

This pilot checks standard USD CFO and PP&E-capex annual observations against matching submission accession, form and filing date. It retains all filing versions and excludes same-day and future filings at each cutoff. The point_in_time section selects the latest eligible filing carrying standard CFO for each exact annual duration, once per period. Conflicting latest values do not fall back to earlier complete filings. Amendments without standard CFO are not reconstructed, so this is not a complete reconstruction of every amendment. Fields in a selected row must share the same filing, unit and period. Annual values are not TTM.

Debt uses an explicit combined amount or all three explicit components (current long-term, noncurrent long-term, short-term borrowing); missing borrowing is not zero. Conflicting totals are withheld. Cash is cash and cash equivalents, not all near-cash investments. Depreciation and intangible amortization are separate duration fields. Operating income plus those two expenses is a provisional proxy, not reconciled ROIC EBITDA. CFO minus capex is not ROIC FCFF. No risk scores are produced. Standard tag absence does not mean a company failed to report that item.

To inspect a previously downloaded artifact without more API calls: `python analyze_archive.py results.zip selection.json`. This verifies the archived response checksums before selecting versions. Eight offline tests cover the audit and selection rules.

Only SEC data.sec.gov paths are used. At least 0.6 seconds between requests, 20-second per-request timeout, at most two retries for rate limits/server failures, bounded archive count and response size. No retry for HTTP 403. For broad production use, review SEC fair-access requirements and identity metadata.

References: https://www.sec.gov/search-filings/edgar-application-programming-interfaces and https://www.sec.gov/about/developer-resources
