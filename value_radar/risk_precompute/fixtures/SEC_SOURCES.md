# Regression data provenance

The XHTML files contain only selected machine-readable facts, their contexts,
units and document identity metadata, extracted from public original annual
filings. They are not entire reports and are not point-in-time training data.

- PDD 2025 Form 20-F, filed 2026-04-29:
  https://www.sec.gov/Archives/edgar/data/1737806/000110465926050727/pdd-20251231x20f.htm
  Downloaded public distribution copy:
  https://cdn.yahoofinance.com/prod/sec-filings/0001737806/000110465926050727/pdd-20251231x20f.htm
  Full downloaded document SHA256:
  `c048eee1d1b6193c560301157059f7352623d9adc70611419ee8add9c9d7949a`
- TSMC 2025 Form 20-F, filed 2026-04-16:
  https://www.sec.gov/Archives/edgar/data/1046179/000162828026025362/tsm-20251231.htm
  Downloaded public distribution copy:
  https://cdn.yahoofinance.com/prod/sec-filings/0001046179/000162828026025362/tsm-20251231.htm
  Full downloaded document SHA256:
  `c3ebd05cd8fb383f53fc21a0ac497ee12cf908b709c380f9bec4f39c4916647b`

The component JSON is a minimal reconstruction of SEC observations in the
project's 2026-11-01 sourceEvidence export, retaining the original values,
accessions, forms, dates and units. It is a regression fixture, not a replacement
for CompanyFacts. Sources:

- Air Products: accession `0000002969-25-000055` (2025-11-20).
- GE HealthCare: accession `0001932393-26-000007` (2026-02-04).

For GE HealthCare 2024, continuing operations of USD 1,955 million and
discontinued operations of USD -4 million give total OCF of USD 1,951 million.
Zero discontinued OCF is accepted only when explicitly reported.

PDD's extension `PaymentsToAcquirePropertyEquipmentAndSoftwareAndIntangibleAssets`
is reviewed only for CIK 1737806 with its pinduoduo.com taxonomy URI. It includes
software and intangible investment payments and is never aliased to pure PPE
or unrestricted free cashflow. Its 2025 CNY payment is 1,145,077,000 after the
reported scale of 3 is applied. Other issuers' similar labels are not matched.
