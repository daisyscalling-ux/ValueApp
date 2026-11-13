/**
 * bundle-fetch.ts - Rohdaten-Bundle einer Notierung, wie es /api/bundle liefert (seit 13.11.2026 als Modul, unveraendert).
 * Die App formt es mit bundleLight (src/lib/roic.ts) zum Fund. Die Pipeline nutzt eine identische Kopie, um denselben
 * Datenweg zu messen (ValueApp, bundle-compare). Abhaengigkeiten (Ergaenzungsdaten, Nachforderung) werden uebergeben.
 */
export type BundleEnv={ROIC_API_KEY?:string;FINNHUB_API_KEY?:string;FMP_API_KEY?:string};
type Env=BundleEnv;
export const ROIC_BASE = "https://api.roic.ai/v3.0.0";
export type BundleDeps={prepared?:(sym:string)=>Promise<unknown>;requestSupplement?:(sym:string)=>Promise<unknown>};

export async function finnhub(path: string, sym: string, env: Env, extra = "", fetcher: typeof fetch = fetch): Promise<unknown> {
  if (!env.FINNHUB_API_KEY) return null;
  const basis = sym.split(":").pop() ?? sym;  // Finnhub will den nackten Ticker
  try {
    const r = await fetcher(
      `https://finnhub.io/api/v1/${path}?symbol=${encodeURIComponent(basis)}${extra}&token=${env.FINNHUB_API_KEY}`, {signal:AbortSignal.timeout(10000)});
    return r.ok ? await r.json() : null;
  } catch { return null; }
}

export async function fmp(path: string, sym: string, env: Env, fetcher: typeof fetch = fetch): Promise<unknown> {
  if (!env.FMP_API_KEY) return null;
  const basis = sym.split(":").pop() ?? sym;
  try {
    const r = await fetcher(
      `https://financialmodelingprep.com/stable/${path}?symbol=${encodeURIComponent(basis)}&apikey=${env.FMP_API_KEY}`, {signal:AbortSignal.timeout(10000)});
    return r.ok ? await r.json() : null;
  } catch { return null; }
}

/** Rohdaten zu einer bereits aufgeloesten Notierung (z. B. NASDAQ:AAPL). */
export async function fetchRawBundle(sym: string, env: Env, deps: BundleDeps = {}, fetcher: typeof fetch = fetch): Promise<Record<string, unknown>> {
  const paths: Record<string, string> = {
    profile: `company/profile/${sym}`,
    quote: `stock-prices/latest/${sym}`,
    enterprise_value: `fundamental/enterprise-value/${sym}`,
    ratios: `fundamental/ratios/profitability/${sym}`,
    liquidity: `fundamental/ratios/liquidity/${sym}`,
    multiples: `fundamental/multiples/${sym}?period_type=annual&limit=5`,
    income: `fundamental/income-statement/${sym}?period_type=annual&limit=3`,
    balance: `fundamental/balance-sheet/${sym}?period_type=annual&limit=3`,
    cashflow: `fundamental/cash-flow/${sym}?period_type=annual&limit=3`,
  };
  const raw: Record<string, unknown> = {resolved_symbol:sym};
  await Promise.all([
    (async () => { raw.fundamental_supplement = deps.prepared?await deps.prepared(sym):null; const saved=raw.fundamental_supplement as any; if(!saved || Date.now()-Date.parse(saved.retrieved_at)>86400000) raw.supplement_status=deps.requestSupplement?await deps.requestSupplement(sym):null; })(),
    ...Object.entries(paths).map(async ([key, p]) => {
      try {
        const r = await fetcher(`${ROIC_BASE}/${p}`, {
          headers: { Authorization: `Bearer ${env.ROIC_API_KEY}` },
          signal: AbortSignal.timeout(12000),
        });
        raw[key] = r.ok ? await r.json() : null;
      } catch { raw[key] = null; }
    }),
    (async () => { raw.price_target = await finnhub("stock/price-target", sym, env, "", fetcher); })(),
    (async () => { raw.recommendation = await finnhub("stock/recommendation", sym, env, "", fetcher); })(),
    (async () => { raw.metric = await finnhub("stock/metric", sym, env, "&metric=all", fetcher); })(),
    (async () => { raw.earnings_surprise = await finnhub("stock/earnings", sym, env, "", fetcher); })(),
    (async () => { raw.fmp_target = await fmp("price-target-consensus", sym, env, fetcher); })(),
  ]);

  // Kurs-Fallback: hat roic keinen Kurs (quote+profile leer), aus Yahoo
  // holen - wie die Streamlit-Variante. Yahoo kennt praktisch jeden Titel.
  const hatKurs = (() => {
    const q = raw.quote as Record<string, unknown> | null;
    const q0 = Array.isArray(q) ? q[0] : q;
    if (q0 && (q0 as any).close) return true;
    const p = raw.profile as Record<string, unknown> | null;
    const p0 = p && (p as any).data ? (p as any).data[0] : p;
    return !!(p0 && (p0 as any).price);
  })();
  if (!hatKurs) {
    try {
      const basis = sym.split(":").pop() ?? sym;
      const yr = await fetcher(
        `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(basis)}?range=1d&interval=1d`,
        { headers: { "User-Agent": "Mozilla/5.0" } });
      if (yr.ok) {
        const yd = await yr.json() as any;
        const meta = yd?.chart?.result?.[0]?.meta;
        if (meta?.regularMarketPrice) {
          raw.quote = {
            close: meta.regularMarketPrice,
            currency: meta.currency,
          };
          // 52w-Band von Yahoo mitnehmen, falls roic-metric leer
          if (meta.fiftyTwoWeekHigh) (raw as any)._yahoo_52w_high = meta.fiftyTwoWeekHigh;
          if (meta.fiftyTwoWeekLow) (raw as any)._yahoo_52w_low = meta.fiftyTwoWeekLow;
        }
      }
    } catch { /* roic-Daten bleiben wie sie sind */ }
  }
  return raw;
}
