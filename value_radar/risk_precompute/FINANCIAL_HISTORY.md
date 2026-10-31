# Observed financial history across the universe

`financial_history.py` runs after the final risk audit and before app export. It retains qualified observations by exact listing identity (including ISIN), metric, reporting currency, frequency and source/method. Its persisted archive is `cf_financial_history.json`; each current app row gets a compact `balance.history` view through the existing bounded shards.

Annual ratios and regulatory quarterly ratios are separate. Different sources, profiles or identities never form a trend. Only adjacent plausible fiscal years (300–430 days) or quarters (70–110 days) produce changes, expressed in percentage points. Missing intervening periods remain visible. Repeated daily retrieval is not another reporting period.

Revisions to the same reporting period retain the original observation and append the new value. A changed value with the same or an older source-retrieval timestamp is quarantined instead of replacing the previous value. Archive timestamps record actual collection time; they are not imputed publication dates. No historical backtest eligibility is claimed.

The archive retains 12 annual or 32 quarterly periods per exact series. Within retained periods, revisions remain preserved. Removed listings remain in the archive; new qualified listings are collected automatically. Invalid archive schema/identity keys, future or nonfinite revisions, duplicate coverage symbols and out-of-order audit runs fail closed before overwriting the history. Input coverage is copied and its original metrics remain unchanged.

The UI places the financial history in a collapsible section. A single real period is explicitly labelled as collection in progress. The UI independently validates the period gap and change arithmetic. No price forecast, calibrated risk score or automatic good/bad investment verdict is added.

## Validation — 2026-10-31

230 risk Python tests pass, including annual/quarterly comparisons, revisions, source/identity changes, missing periods, zero/invalid values, archive protection and retention. Four UI tests and targeted TypeScript checking pass. Full-universe replay populates 6,492 observations for 1,256 listings, with no artificial comparisons on the first run. Repeating the same snapshot preserves every series without adding another period. All original audit fields remain unchanged.

## Activation and remaining work

Merge, run daily-risk and deploy Desktop/cf. No additional keys or API calls are required. The first production run creates its own dated archive; the local replay archive is intentionally not committed. This prepares ongoing history collection and does not backfill six years of historical original disclosures. Earlier verified filings and regulatory liquidity disclosures remain separate data-supply work.
