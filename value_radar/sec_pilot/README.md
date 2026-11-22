# SEC financial pilot

Read-only audit for Microsoft and Oracle. Does not update production scores or universes.

Set the Actions secret SEC_USER_AGENT to `ValueApp <real operator email>`. Do not commit the contact address. Merge this workflow into main and run **sec-financial-pilot** manually from Actions. Pull requests run offline tests only; they do not receive the SEC secret.

The run summary and artifact contain report.md, report.json and original SEC JSON responses with retrieval timestamps and SHA-256 checksums. Artifacts expire after 90 days: download and retain them if they are needed for a durable historical archive. HTTP failures produce an incomplete report and fail the job; a green job only confirms the audit executed, not that every financial field is available or a risk model is validated.

This pilot checks standard USD CFO and PP&E-capex annual observations against matching submission accession, form and filing date. It retains all filing versions and excludes same-day and future filings at each cutoff. The point_in_time section selects the latest eligible filing carrying standard CFO for each exact annual duration, once per period. Conflicting latest values do not fall back to earlier complete filings. Amendments without standard CFO are not reconstructed, so this is not a complete reconstruction of every amendment. Fields in a selected row must share the same filing, unit and period. Annual values are not TTM.

Debt uses an explicit combined amount or all three explicit components (current long-term, noncurrent long-term, short-term borrowing); missing borrowing is not zero. Conflicting totals are withheld. Cash is cash and cash equivalents, not all near-cash investments. Depreciation and intangible amortization are separate duration fields. Operating income plus those two expenses is a provisional proxy, not reconciled ROIC EBITDA. CFO minus capex is not ROIC FCFF. No risk scores are produced. Standard tag absence does not mean a company failed to report that item.

To inspect a previously downloaded artifact without more API calls: `python analyze_archive.py results.zip selection.json`. This verifies the archived response checksums before selecting versions. Eight offline tests cover the audit and selection rules.

Only SEC data.sec.gov paths are used. At least 0.6 seconds between requests, 20-second per-request timeout, at most two retries for rate limits/server failures, bounded archive count and response size. No retry for HTTP 403. For broad production use, review SEC fair-access requirements and identity metadata.

References: https://www.sec.gov/search-filings/edgar-application-programming-interfaces and https://www.sec.gov/about/developer-resources

## Messung US-Leasing in den Nettoschulden (22.11.2026)

Anlass: Prüfung der 64 Titel mit „Nettoschulden über Unternehmenswert“. Unter US-GAAP mindert die Miete den operativen Cashflow, „Total Debt“ im Jahresblock (Yahoo) enthält die Leasingverbindlichkeiten aber vermutlich zusätzlich (MGM 31,4 Mrd $). Dann zählt die Miete im DCF doppelt. Der Nutzer hat entschieden, erst zu messen und dann zu entscheiden.

- Skript `us_leasing_messung.py` (Methode `us_operating_lease_in_net_debt_measure_v1`), Workflow `us-leasing-messung` (manuell).
- Je US-Titel (USD, CIK, ohne Finanzmodell; im Universum vom 22.11.: 421) aus dem 10-K zum Stichtag des Jahresblocks (±5 Tage): `OperatingLeaseLiability` (sonst Current + Noncurrent) und Finanzschulden ohne Leasing (`LongTermDebt` bzw. Teile, dazu kurzfristige Kredite und Commercial Paper).
- Einordnung: Liegt „Total Debt“ näher an Finanzschulden + Leasing als an den Finanzschulden allein, gilt das Leasing als enthalten. Ohne SEC-Finanzschulden bleibt die Einordnung offen.
- Wirkung: DCF je Aktie aus den offengelegten Teilen (`dcf_inputs`) mit Nettoschulden minus Leasing. Näherung: Der Fremdkapitalanteil im Zins bleibt gleich (ohne Leasing wäre der Zins etwas höher, die Wirkung also überschätzt).
- Herkunft je Titel: Quell-URL, SHA-256 der Antwort, Accession, Stichtag, Abrufzeit. Ergebnis nur als Artefakt; keine Datei in `daten/`, keine Bewertungsänderung.
- Abruf nur mit `SEC_USER_AGENT`, mindestens 0,6 s Abstand, kein Wiederholen nach Fehlern (gezählt).
- Tests: `test_us_leasing_messung.py` (12): nur 10-K, Stichtag, jüngste Einreichung, Teilsummen, ungültige Werte, Einordnung, Wirkung, Auswahl, Abruffehler, ohne User-Agent kein Abruf.
