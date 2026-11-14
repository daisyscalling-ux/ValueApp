import { applySupplement, applyForwardEstimate } from './fundamental-supplement';
import { normalizeFinancialRows, normalizeMarketCap, valuationDataCheck } from './valuation-data';
import {financialRiskInput} from './risk-score';
/**
 * roic.ts - Datenanbindung: rohe roic-API-Antworten -> Fund-Objekt.
 *
 * ARCHITEKTUR (Cloudflare):
 *   Der Worker holt die roic-Endpunkte (profile, enterprise-value, ratios,
 *   multiples, income-statement) - er hat den Schluessel. Dieses Modul
 *   TRANSFORMIERT die Rohantworten zum Fund-Objekt, das valuation.ts und
 *   scoring.ts verstehen. Kein Netzcode hier - reine Formung, damit sie
 *   testbar bleibt und im Browser laeuft.
 *
 * bundleLight: die 5 Rohantworten -> Fund (fuer Einzelanalyse UND Scanner).
 * jahresPaar: roic-Jahreslisten -> {akt, vorjahr} fuer scores.ts.
 *
 * Methode wie immer: 1:1 aus roic.py (bundle_light), gegen Python getestet.
 */

import type { Fund } from "./valuation";
import { phaseInputs, peObservations } from "./phase-data";
import { historicalPe } from "./lifecycle";

type Row = Record<string, unknown>;

// --- Helfer, exakt aus roic.py ---------------------------------------------

/** roic liefert je Endpunkt Liste oder Objekt - erste Zeile holen. */
export function first(data: unknown): Row | null {
  if (Array.isArray(data)) return (data[0] as Row) ?? null;
  if (data && typeof data === "object") {
    for (const k of ["data", "results", "rows"]) {
      const v = (data as Row)[k];
      if (Array.isArray(v)) return (v[0] as Row) ?? null;
    }
    return (data as Row) ?? null;
  }
  return null;
}

function num(x: unknown): number | null {
  if (x === null || x === undefined) return null;
  if (typeof x === "string" && !x.trim()) return null;
  const v = typeof x === "number" ? x : parseFloat(x as string);
  return Number.isFinite(v) ? v : null;
}

/** Prozentwert der Ratio-Endpunkte -> Dezimalbruch (12.5 -> 0.125). */
function pct(x: unknown): number | null {
  const v = num(x);
  return v !== null ? v / 100.0 : null;
}

/** Erster vorhandener Schluessel; prueft auch camelCase. */
function gval(d: Row | null | undefined, ...keys: string[]): unknown {
  if (!d) return null;
  for (const k of keys) {
    if (k in d && d[k] !== null && d[k] !== undefined) return d[k];
    const camel = k.split("_").map((w, i) => i ? w.charAt(0).toUpperCase() + w.slice(1) : w).join("");
    if (camel in d && d[camel] !== null && d[camel] !== undefined) return d[camel];
  }
  return null;
}

/** Umsatz einer Abschlusszeile. */
function yr(inc: Row | null): number | null {
  return num(gval(inc, "is_sales_revenue_turnover", "is_sales_and_services_revenues"));
}

// --- Rohantworten, wie der Worker sie liefert ------------------------------
export interface RoicRaw {
  fundamental_supplement?: unknown;
  resolved_symbol?: string;
  supplement_status?: string;
  profile?: unknown;          // company/profile/{sym}
  quote?: unknown;            // stock-prices/latest/{sym} - der aktuelle Kurs
  enterprise_value?: unknown; // fundamental/enterprise-value/{sym}
  ratios?: unknown;           // fundamental/ratios/profitability/{sym}
  multiples?: unknown;        // fundamental/multiples/{sym}
  income?: unknown[];         // fundamental/income-statement/{sym}?limit=3
  balance?: unknown;          // fundamental/balance-sheet/{sym}
  liquidity?: unknown;        // fundamental/ratios/liquidity/{sym}
  cashflow?: unknown;         // fundamental/cash-flow/{sym}
  price_target?: unknown;     // Finnhub stock/price-target
  fmp_target?: unknown;       // FMP price-target-consensus (Rueckfall)
  recommendation?: unknown;   // Finnhub stock/recommendation
  metric?: unknown;           // Finnhub stock/metric?metric=all (52w-Band)
  earnings_surprise?: unknown; // Finnhub stock/earnings (Schaetzung vs Ist)
  _yahoo_52w_high?: number;    // Yahoo-Fallback, wenn roic/Finnhub leer
  _yahoo_52w_low?: number;
}

/**
 * bundleLight - 5 Rohantworten -> Fund. 1:1 aus roic.bundle_light.
 * Enthaelt Stammdaten, Groesse, Margen, Renditen, Umsatz, Multiples und
 * Wachstum aus zwei Geschaeftsjahren.
 */
// Boerse (aus dem roic-Symbol TSE:7269 / SIX:NESN) -> Handelswaehrung.
// Verhindert, dass ein Yen-Kurs (1728) faelschlich als EUR angezeigt wird.
const BOERSE_WAEHRUNG: Record<string, string> = {
  NASDAQ: "USD", NYSE: "USD", AMEX: "USD", ARCA: "USD", BATS: "USD", OTC: "USD",
  TSE: "JPY", JPX: "JPY", TYO: "JPY",
  SIX: "CHF", SWX: "CHF",
  LSE: "GBP", LON: "GBP",
  XETR: "EUR", FRA: "EUR", ETR: "EUR", GER: "EUR",
  EPA: "EUR", PAR: "EUR", AMS: "EUR", EBR: "EUR", MIL: "EUR", BME: "EUR",
  MCE: "EUR", VIE: "EUR", ELI: "EUR", HEL: "EUR", MUN: "EUR",
  STO: "SEK", OSL: "NOK", CPH: "DKK", WSE: "PLN", WAR: "PLN",
  TSX: "CAD", TSXV: "CAD", ASX: "AUD", HKEX: "HKD", HKG: "HKD",
};

function waehrungAusSymbol(sym: string | null | undefined): string | null {
  if (!sym || !sym.includes(":")) return null;
  const boerse = sym.split(":")[0].toUpperCase();
  return BOERSE_WAEHRUNG[boerse] ?? null;
}

export function bundleLight(raw: RoicRaw): Fund & Record<string, unknown> {
  raw = normalizeFinancialRows(raw) as RoicRaw;
  const prof = first(raw.profile);
  const quote = first(raw.quote);
  const ev = first(raw.enterprise_value);
  const rp = first(raw.ratios);
  const lq = first(raw.liquidity);
  const mu = first(raw.multiples);
  // income kann {data:[...]}, {results:[...]} oder direkt ein Array sein.
  let inc: Row[] = [];
  const incRaw = raw.income;
  if (Array.isArray(incRaw)) inc = incRaw as Row[];
  else if (incRaw && typeof incRaw === "object") {
    const d = (incRaw as Row).data ?? (incRaw as Row).results ?? (incRaw as Row).rows;
    if (Array.isArray(d)) inc = d as Row[];
  }

  const out: Record<string, unknown> = {
    _src: "roic_light",
    risk_financial: financialRiskInput(raw as unknown as Record<string,any>),
    name: gval(prof, "name", "company_name"),
    isin: gval(prof, "isin"),
    cik: gval(prof,"cik"),
    sub_industry: gval(prof,"sub_industry","subIndustry"),
    sector: gval(prof, "sector"),
    industry: gval(prof, "industry"),
    country: gval(prof, "country_code"),
    currency: (gval(prof, "trading_currency", "currency") as string | null)
              || waehrungAusSymbol(gval(ev, "symbol") as string ?? gval(prof, "symbol") as string)
              || waehrungAusSymbol(gval(quote, "symbol") as string),
    price: num(gval(quote, "close", "adj_close")) ?? num(gval(prof, "price")),
    market_cap: num(gval(ev, "market_cap")),
    enterprise_value: num(gval(ev, "enterprise_value")),
    total_debt: num(gval(ev, "short_and_long_term_debt")),
    cash: num(gval(ev, "bs_cash_near_cash_item")),
    revenue: num(gval(ev, "ttm_net_sales")),
    ebitda: num(gval(ev, "ttm_ebitda")),
    ebit: num(gval(ev, "ttm_oper_inc")),
    free_cashflow: num(gval(ev, "ttm_free_cash_flow_firm")),
    gross_margin: pct(gval(rp, "gross_margin")),
    operating_margin: pct(gval(rp, "oper_margin")),
    profit_margin: pct(gval(rp, "profit_margin")),
    ebitda_margin: pct(gval(rp, "ebitda_margin")),
    roe: pct(gval(rp, "return_com_eqy")),
    roa: pct(gval(rp, "return_on_asset")),
    roic: pct(gval(rp, "return_on_inv_capital")),
  };

  // Mehrjahresreihen fuer die Saeulendiagramme (Umsatz/EBITDA/FCF/Netto).
  // enterprise_value liefert 5 Jahre, neuestes zuerst - wir nehmen die
  // letzten 3, aeltestes zuerst fuer die Achse.
  const evAlle = (() => {
    const r = raw.enterprise_value;
    if (Array.isArray(r)) return r as Row[];
    if (r && typeof r === "object") {
      const d = (r as Row).data ?? (r as Row).results;
      if (Array.isArray(d)) return d as Row[];
    }
    return [];
  })();
  if (evAlle.length >= 2) {
    const drei = evAlle.slice(0, 3).reverse();  // aeltestes zuerst
    out.reihe_umsatz = drei.map((z) => ({ jahr: num(gval(z, "fiscal_year")), wert: num(gval(z, "ttm_net_sales")) }));
    out.reihe_ebitda = drei.map((z) => ({ jahr: num(gval(z, "fiscal_year")), wert: num(gval(z, "ttm_ebitda")) }));
    out.reihe_fcf = drei.map((z) => ({ jahr: num(gval(z, "fiscal_year")), wert: num(gval(z, "ttm_free_cash_flow_firm")) }));
    // Wachstum ueber 3 Jahre (aeltestes -> neuestes)
    const u0 = num(gval(drei[0], "ttm_net_sales")), uN = num(gval(drei[drei.length-1], "ttm_net_sales"));
    if (u0 && uN && u0 > 0) out.umsatz_3j = uN / u0 - 1;
  }

  // net_debt aus total_debt - cash (in valuation.ts gebraucht)
  const td = out.total_debt as number | null, cash = out.cash as number | null;
  if (td !== null && cash !== null) out.net_debt = td - cash;

  // shares_out: bevorzugt die echte Aktienzahl aus den multiples (bs_sh_out),
  // sonst aus market_cap/price ableiten. bs_sh_out ist genauer als der
  // Quotient (der die diluted shares verfehlt).
  const shOut = num(gval(mu, "bs_sh_out", "shares_out"));
  if (shOut && shOut > 0) {
    out.shares_out = shOut;
  } else {
    const mc = out.market_cap as number | null, pr = out.price as number | null;
    if (mc && pr && pr > 0) out.shares_out = mc / pr;
  }

  // KGV-Band aus 5 Jahren multiples (fuer die Bewertungshistorie)
  const muAlle = (() => {
    const r = raw.multiples;
    if (Array.isArray(r)) return r as Row[];
    if (r && typeof r === "object") {
      const d = (r as Row).data ?? (r as Row).results;
      if (Array.isArray(d)) return d as Row[];
    }
    return [];
  })();
  const peHistory = peObservations(muAlle);
  out.pe_history = peHistory;
  const peSummary = historicalPe({pe_history: peHistory});
  if (peHistory.length >= 3) {
    out.pe_hist_min = Math.min(...peHistory.map(p => p.value));
    out.pe_hist_max = Math.max(...peHistory.map(p => p.value));
    out.pe_hist_median = peSummary.median;
  }
  Object.assign(out, phaseInputs(raw));
  out.ticker = gval(prof, 'symbol', 'ticker') ?? gval(quote, 'symbol') ?? gval(ev, 'symbol');
  out.dividend_yield = num(gval(prof, 'dividend_yield'));

  if (mu) {
    out.pe_trailing = num(gval(mu, "pe_ratio"));
    out.ps = num(gval(mu, "pr_to_sales_ratio"));
    out.pb = num(gval(mu, "pr_to_book_ratio"));
    out.ev_ebitda = num(gval(mu, "ev_to_ttm_ebitda"));
  }

  if (inc.length >= 2) {
    const r0 = yr(inc[0]), r1 = yr(inc[1]);
    if (r0 && r1 && r1 > 0) out.revenue_growth = r0 / r1 - 1.0;
    const e0 = num(gval(inc[0], "diluted_eps", "eps"));
    const e1 = num(gval(inc[1], "diluted_eps", "eps"));
    if (e0 !== null && e1 && e1 > 0) {
      const eg = e0 / e1 - 1.0;
      if (eg > -0.95 && eg < 10.0) out.earnings_growth = eg;
    }
    if (out.eps_trailing === undefined && e0 !== null) {
      out.eps_trailing = e0;
      const period = gval(inc[0], 'period_end_date', 'fiscal_year') ?? 'Stichtag fehlt';
      out.eps_trailing_basis = `letztes Geschäftsjahr (${String(period).slice(0,10)}), kein TTM`;
      const reporting = gval(inc[0], 'currency', 'reporting_currency');
      out.eps_trailing_comparable = !!reporting && reporting === out.currency;
    }
  }

  // net_debt_ebitda ableiten (health-Score)
  const nd = out.net_debt as number | null, eb = out.ebitda as number | null;
  if (nd !== null && eb && eb > 0) out.net_debt_ebitda = nd / eb;

  // Liquiditaet: current_ratio + quick_ratio (roic-Endpunkt ratios/liquidity).
  if (lq) {
    const cr = num(gval(lq, "cur_ratio", "current_ratio"));
    if (cr !== null) out.current_ratio = cr;
    const qr = num(gval(lq, "quick_ratio"));
    if (qr !== null) out.quick_ratio = qr;
  }

  // Analysten-Kursziel (Finnhub) - fuer fairValue-Anker, Quantum, 12M-Ziel.
  const pt = first(raw.price_target);
  if (pt) {
    const tm = num(gval(pt, "targetMean", "target_mean"));
    if (tm && tm > 0) out.target_mean = tm;
  }
  // Rueckfall: FMP price-target-consensus (Finnhub liefert oft null)
  if (!out.target_mean) {
    const fmpt = first(raw.fmp_target);
    if (fmpt) {
      const tm = num(gval(fmpt, "targetConsensus", "targetMedian", "targetMean"));
      if (tm && tm > 0) out.target_mean = tm;
    }
  }
  // Analystenempfehlungen (Finnhub, neueste Zeile) -> buy/hold/sell fuer Quantum
  const recArr = Array.isArray(raw.recommendation) ? raw.recommendation as Row[] : [];
  if (recArr.length) {
    const r0 = recArr[0];
    const buy = (num(gval(r0, "strongBuy")) ?? 0) + (num(gval(r0, "buy")) ?? 0);
    const hold = num(gval(r0, "hold")) ?? 0;
    const sell = (num(gval(r0, "sell")) ?? 0) + (num(gval(r0, "strongSell")) ?? 0);
    out.analyst_buy = buy; out.analyst_hold = hold; out.analyst_sell = sell;
    out.analyst_count = buy + hold + sell;
  }

  // hist_pe_median NICHT aus dem heutigen KGV erfinden - das verzerrt den
  // Fair Value (falsche Methode im Mix). Fehlt echte KGV-Historie, bleibt es
  // leer, genau wie in Pythons Light-Pfad. Nur fuers 12M-Kursziel brauchen
  // wir eine KGV-Basis; das setzt das Frontend separat mit dem heutigen KGV,
  // klar als Naeherung markiert.

  // 52-Wochen-Band (Finnhub-Metriken) -> Momentum-Score. Ohne diese Felder
  // faellt Momentum auf 50 (neutral) statt den echten Wert zu zeigen.
  const metricObj = raw.metric && typeof raw.metric === "object"
    ? ((raw.metric as Row).metric as Row) ?? (raw.metric as Row) : null;
  if (metricObj) {
    const hi = num(gval(metricObj, "52WeekHigh"));
    const lo = num(gval(metricObj, "52WeekLow"));
    if (hi) out["52w_high"] = hi;
    if (lo) out["52w_low"] = lo;
    // Forward-EPS kommt nur noch aus dem geprüften Konsens (applyForwardEstimate), nicht aus epsForward ohne Horizont.
  }

  // Earnings-Surprise: schlaegt die Firma regelmaessig ihre Schaetzungen?
  // Die einzige Forward-naheliegende Quelle, die der Tarif hergibt. Aus den
  // letzten Quartalen den Median-Surprise (%) - positiv = uebertrifft meist.
  const surpArr = Array.isArray(raw.earnings_surprise)
    ? raw.earnings_surprise as Row[] : [];
  if (surpArr.length >= 2) {
    const sp = surpArr
      .map((q) => num(gval(q, "surprisePercent")))
      .filter((v): v is number => v !== null && isFinite(v))
      .slice(0, 8);
    if (sp.length >= 2) {
      const sortiert = [...sp].sort((a, b) => a - b);
      out.surprise_median = sortiert[Math.floor(sortiert.length / 2)];
      // Trefferquote: Anteil der Quartale ueber Schaetzung
      out.surprise_beat_quote = sp.filter((x) => x > 0).length / sp.length;
      out.surprise_n = sp.length;
    }
  }

  // Yahoo-52w-Band als Fallback (wenn roic/Finnhub keins hatten)
  if (!out["52w_high"] && raw._yahoo_52w_high) out["52w_high"] = raw._yahoo_52w_high;
  if (!out["52w_low"] && raw._yahoo_52w_low) out["52w_low"] = raw._yahoo_52w_low;

  // Keine mechanische Fortschreibung als Prognose mehr (seit 14.11.2026): fehlt ein geprüfter Konsens, bleibt eps_forward offen.

  // Rohreihen fuer die Forensik (scores.ts): income+balance+cashflow je Jahr
  // gemischt, damit piotroskiF/altmanZ/beneishM ihre Felder finden.
  const listOf = (r: unknown): Row[] => {
    if (Array.isArray(r)) return r as Row[];
    if (r && typeof r === "object") {
      const d = (r as Row).data ?? (r as Row).results;
      if (Array.isArray(d)) return d as Row[];
    }
    return [];
  };
  const incL = listOf(raw.income), balL = listOf(raw.balance), cfL = listOf(raw.cashflow);

  // Jahresreihen fuer das Risiko-Konstrukt (neueste zuerst). Fehlende Werte werden ausgelassen, nie null gesetzt.
  const annual = incL.map(r => ({
    period: String(gval(r, "period_end_date", "date") ?? "").slice(0, 10),
    revenue: yr(r), gross: num(gval(r, "is_gross_profit")),
    currency: (gval(r, "currency", "reporting_currency") as string | undefined) ?? null,
  })).filter(a => /^\d{4}-\d{2}-\d{2}$/.test(a.period) && a.revenue !== null && a.revenue > 0);
  out.revenue_history = annual.map(a => ({ period: a.period, value: a.revenue, currency: a.currency }));
  out.gross_margin_history = annual.filter(a => a.gross !== null)
    .map(a => ({ period: a.period, value: (a.gross as number) / (a.revenue as number), currency: a.currency }));

  // Finanzlage-Kennzahlen aus dem aktuellen Jahr (balance + income + cashflow).
  const bal0 = balL[0] ?? {}, inc0 = incL[0] ?? {}, cf0 = cfL[0] ?? {};
  const totAsset = num(gval(bal0, "bs_tot_asset", "total_assets"));
  const totLiab = num(gval(bal0, "bs_tot_liab", "total_liabilities"));
  const curLiab = num(gval(bal0, "bs_cur_liab"));
  const curAsset = num(gval(bal0, "bs_cur_asset_report", "bs_cur_asset"));
  const cashBs = num(gval(bal0, "bs_cash_near_cash_item")) ?? (out.cash as number | null);
  const receivables = num(gval(bal0, "bs_accounts_receivable"));
  const ltDebt = num(gval(bal0, "bs_lt_borrow"));
  const netInc = num(gval(inc0, "is_net_income", "net_income")) ?? (out.net_income as number | null);
  const rev0 = num(gval(inc0, "is_sales_revenue_turnover")) ?? (out.revenue as number | null);
  const operInc = num(gval(inc0, "is_oper_income")) ?? (out.ebit as number | null);
  const operCf = num(gval(cf0, "cf_cash_from_oper"));
  const eigenkapital = totAsset !== null && totLiab !== null ? totAsset - totLiab : null;
  const totDebt = out.total_debt as number | null;

  const fl: Record<string, number | null> = {};
  if (netInc !== null && rev0 && rev0 > 0) fl.profit_margin = netInc / rev0;
  if (out.ebitda && rev0 && rev0 > 0) fl.ebitda_margin = (out.ebitda as number) / rev0;
  if (operInc !== null && eigenkapital !== null && totDebt !== null && (eigenkapital + totDebt) > 0)
    fl.roic = (operInc * 0.79) / (eigenkapital + totDebt);
  if (totDebt !== null && eigenkapital && eigenkapital > 0) fl.debt_to_equity = totDebt / eigenkapital;
  if (totDebt !== null && totAsset && totAsset > 0) fl.debt_to_capital = totDebt / totAsset;
  if (totDebt !== null && operInc && operInc > 0) fl.debt_to_ebit = totDebt / operInc;
  if (ltDebt !== null && totAsset && totAsset > 0) fl.lt_debt_assets = ltDebt / totAsset;
  if (cashBs !== null && curLiab && curLiab > 0) fl.cash_ratio = cashBs / curLiab;
  if (operCf !== null && totLiab && totLiab > 0) fl.cf_to_liab = operCf / totLiab;
  if (receivables !== null && rev0 && rev0 > 0) fl.dso = receivables / rev0 * 365;
  // current/quick haben wir schon aus liquidity; sonst aus Bilanz
  if (!out.current_ratio && curAsset !== null && curLiab && curLiab > 0) fl.current_ratio = curAsset / curLiab;
  out._finanzlage = fl;
  if (incL.length && balL.length) {
    const merge = (i: number): Row => ({ ...(balL[i] ?? {}), ...(cfL[i] ?? {}), ...(incL[i] ?? {}) });
    out._forensik_akt = merge(0);
    out._forensik_vorjahr = merge(1);
  }

  applySupplement(out, raw);
  normalizeMarketCap(out, raw.fundamental_supplement as Record<string, unknown> | null, Date.now(), typeof raw.resolved_symbol === 'string' ? raw.resolved_symbol : '');
  // Prognose-EPS nur als geprüfter 12-Monats-Konsens (ersetzt Finnhub-Wert und mechanische Fortschreibung).
  applyForwardEstimate(out, raw.fundamental_supplement as Record<string, unknown> | null, Date.now(), typeof raw.resolved_symbol === 'string' ? raw.resolved_symbol : '');
  out.valuation_data = valuationDataCheck(out, raw);
  const clean: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(out)) {
    if (v !== null || k === "_src") clean[k] = v;
  }
  return clean as Fund & Record<string, unknown>;
}

/**
 * jahresPaar - roic-Jahreslisten (income + balance + cashflow) -> {akt, vorjahr}
 * fuer die Forensik in scores.ts. Verschmilzt die drei Quellen je Jahr.
 * 1:1 aus roic.jahres_paar (die Kernidee: gleiches Jahr aus 3 Listen mischen).
 */
export function jahresPaar(
  inc: Row[], bal: Row[], cf: Row[],
): { akt: Row; vorjahr: Row } | null {
  if (!inc || inc.length < 2) return null;
  const merge = (i: number): Row => ({
    ...(bal[i] ?? {}), ...(cf[i] ?? {}), ...(inc[i] ?? {}),
  });
  return { akt: merge(0), vorjahr: merge(1) };
}

/** Die roic-Endpunkt-Pfade, die der Worker fuer bundleLight holen muss. */
export function lightEndpoints(sym: string): Partial<Record<keyof RoicRaw, string>> {
  return {
    profile: `company/profile/${sym}`,
    enterprise_value: `fundamental/enterprise-value/${sym}`,
    ratios: `fundamental/ratios/profitability/${sym}`,
    multiples: `fundamental/multiples/${sym}`,
    income: `fundamental/income-statement/${sym}?period_type=annual&limit=2`,
  };
}

// --- News + Earnings: Transformation der Rohantworten ----------------------
export interface NewsItem {
  datum: string; titel: string; quelle: string | null;
  url: string | null; text: string | null;
}
export function parseNews(raw: unknown): NewsItem[] {
  const reihen = Array.isArray(raw) ? raw
    : (raw && typeof raw === "object" ? ((raw as Row).data as unknown[]) : null) ?? [];
  const out: NewsItem[] = [];
  for (const z of reihen as Row[]) {
    if (!z || typeof z !== "object") continue;
    const url = gval(z, "url", "link", "article_url", "news_url", "source_url", "story_url", "href", "web_url");
    const titel = gval(z, "title", "headline", "heading");
    if (!titel) continue;
    out.push({
      datum: String(gval(z, "published_date", "date", "datetime", "published_at", "publishedDate") ?? "").slice(0, 19),
      titel: String(titel),
      quelle: (gval(z, "site", "source", "publisher", "provider") as string) ?? null,
      url: url ? String(url) : null,
      text: (gval(z, "text", "summary", "content", "description") as string) ?? null,
    });
  }
  return out;
}

export interface EarningsCall { jahr: number | null; quartal: number | null; datum: string; }
export function parseEarnings(raw: unknown): EarningsCall[] {
  let reihen: unknown = Array.isArray(raw) ? raw
    : (raw && typeof raw === "object" ? ((raw as Row).data ?? (raw as Row).earnings_calls) : null) ?? [];
  if (reihen && typeof reihen === "object" && !Array.isArray(reihen)) reihen = [reihen];
  const out: EarningsCall[] = [];
  for (const z of (reihen as Row[])) {
    if (!z || typeof z !== "object") continue;
    const j = num(gval(z, "fiscal_year", "year"));
    const q = num(gval(z, "fiscal_quarter", "quarter"));
    const datum = String(gval(z, "date") ?? "").slice(0, 10);
    if (!datum && !j) continue;
    out.push({ jahr: j ? Math.floor(j) : null, quartal: q ? Math.floor(q) : null, datum });
  }
  out.sort((a, b) => (b.datum || "").localeCompare(a.datum || ""));
  return out;
}

