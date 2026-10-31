# SEC recovery and reviewed holding liquidity (2026-11-01)

The first SEC history batch recovered 128 issuers/939 periods. The remaining 42 name mismatches and 78 missing matching-period cases require separate treatment.

The new SEC-only comparator removes explicit formatting (incorporation suffixes, terminal The/Common Stock/REIT/Holding Company descriptors and legal suffixes). Short exact issuer names are allowed, with no fuzzy matching or renamed-issuer aliases. Exchange, ticker, qualified listing and CIK checks remain mandatory. Policy v2 retries old failures once. Diagnostic records retain expected/SEC names, available namespaces/forms, concept counts and alternative concept names. IFRS-only and unsupported forms retry after 28 days; other failures after two days. Alternative spending concepts and negative payments are not silently treated as cash PPE.

Holding liquidity has independent Python, TypeScript and UI validation: exact consolidated holding/RSSD, same quarter, quarterly average, units, source, review expiry and HQLA/outflow arithmetic. Maximum rounding tolerance is 0.5 percentage points. Expiry is 180 days after the reporting period or the review deadline. Only the liquidity data requirement is fulfilled, with zero score contribution.

First reviewed record: Citigroup Inc., RSSD 1951350, quarter 2026-06-30; average HQLA USD 641.2bn, net outflows USD 567.5bn, reported LCR 113%. Source: https://www.sec.gov/Archives/edgar/data/831001/000083100126000045/c-20260630.htm , Liquidity Risk, page 65. Reviewed 2026-11-01; expires 2026-12-27. Publication date is not inferred. Other holdings remain open. This is not automated global LCR supply.

Additional official report locations: https://investor.bankofamerica.com/regulatory-and-other-filings/basel-pillar-3-disclosures/pillar-3-regulatory-liquidity-disclosures ; https://www.wellsfargo.com/about/investor-relations/disclosures/ ; https://www.morganstanley.com/about-us-ir/lcr-disclosures-us ; https://investor.pnc.com/sec-filings/regulatory-disclosures . BAC's linked report returned AccessDenied locally; no figure was inserted. A direct SEC Company Facts request returned 403; live recovery must be measured after the merged job.

257 Python tests pass. Targeted TypeScript regulatory/liquidity/universe tests pass. Replay preserves nine verified holdings and accepts liquidity only for Citigroup. Six isolated UI tests and UI typechecking pass. Desktop/cf source files were updated and backed up, but the final Desktop build was not executed because automatic approval review hit a usage limit; it was not rejected as unsafe. Workspace copies were used for independent UI validation, without writing to Desktop/dist.

Activate by merging, running daily-risk on main and running npm run deploy in Desktop/cf. No new secret. ROIC's historical queue continues independently.

Measured progress from the latest downloaded report: main-market core-data intersection 872/949 (91.9%); full-universe 1106/1330 (83.2%). These are coverage percentages, not full risk-model completion. Sector-specific original disclosures, verified news events, full-model historical validation and end-to-end acceptance remain uncertified.
