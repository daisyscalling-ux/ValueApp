# SEC financial pilot

Read-only audit for Microsoft and Oracle. Does not update production scores or universes.

Set the Actions secret SEC_USER_AGENT to `ValueApp <real operator email>`. Do not commit the contact address. Merge this workflow into main and run **sec-financial-pilot** manually from Actions. Pull requests run offline tests only; they do not receive the SEC secret.

The run summary and artifact contain report.md, report.json and original SEC JSON responses with retrieval timestamps and SHA-256 checksums. Artifacts expire after 90 days: download and retain them if they are needed for a durable historical archive. HTTP failures produce an incomplete report and fail the job; a green job only confirms the audit executed, not that every financial field is available or a risk model is validated.

This pilot checks standard USD CFO and PP&E-capex annual observations against matching submission accession, form and filing date. It retains all filing versions and excludes same-day and future filings at each cutoff. It does not choose the final point-in-time financial statement, rebuild TTM, parse custom XBRL tags or compute a risk score. Coverage counts for other tags are diagnostic, not a financial-definition reconciliation. CFO minus capex is not equated with ROIC FCFF. Standard tag absence does not mean a company failed to report that item.

Only SEC data.sec.gov paths are used. At least 0.6 seconds between requests, 20-second per-request timeout, at most two retries for rate limits/server failures, bounded archive count and response size. No retry for HTTP 403. For broad production use, review SEC fair-access requirements and identity metadata.

References: https://www.sec.gov/search-filings/edgar-application-programming-interfaces and https://www.sec.gov/about/developer-resources
