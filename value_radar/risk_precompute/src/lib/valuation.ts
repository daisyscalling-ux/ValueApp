import { valuationDataCheck } from './valuation-data';
/**
 * valuation.ts - Portierung des Bewertungskerns aus valuation.py
 * Methode: Python lesen, 1:1 uebersetzen, gegen Python-Ausgabe testen.
 *
 * FORTSCHRITT:
 *   [x] classifyPlaybook  [x] wacc  [x] fcfBasis  [x] dcfTwoStage  [x] fairesKgv
 *   [ ] justifiedPe  [ ] multipleEvEbitda  [ ] epv  [ ] fairValue (Mischer)
 *   [ ] reverseDcf  [ ] kursziel12m  [ ] kursProjektion
 */

import { analysePhase, phaseWeights, paymentNetwork, type PhaseResult, type PhaseYear, type CapitalPeriod, type PeObservation } from './lifecycle';

export interface Fund {
  valuation_data?: ReturnType<typeof valuationDataCheck>;
  phase_history?: PhaseYear[];
  capital_return_period?: CapitalPeriod;
  pe_history?: PeObservation[];
  dividend_yield?: number | null;
  ticker?: string; name?: string; sector?: string; industry?: string;
  price?: number | null; market_cap?: number | null; shares_out?: number | null;
  free_cashflow?: number | null; cash_conversion?: number | null;
  net_income?: number | null; ebitda?: number | null; ebit?: number | null;
  revenue?: number | null; net_debt?: number | null; total_debt?: number | null;
  total_assets?: number | null; eps_trailing?: number | null;
  eps_forward?: number | null; book_value_ps?: number | null;
  eps_forward_source?: string;
  eps_trailing_basis?: string;
  eps_trailing_comparable?: boolean;
  revenue_growth?: number | null; earnings_growth?: number | null;
  beta?: number | null; roe?: number | null; roic?: number | null;
  gross_margin?: number | null; operating_margin?: number | null;
  net_debt_ebitda?: number | null; current_ratio?: number | null;
  ev_ebitda?: number | null; pb?: number | null; target_mean?: number | null;
  analyst_count?: number | null; hist_pe_median?: number | null;
  pe_hist_min?: number | null; pe_hist_max?: number | null; pe_hist_median?: number | null;
  reihe_ebitda?: { jahr?: number | null; wert: number | null }[];
  analyst_buy?: number | null; analyst_hold?: number | null; analyst_sell?: number | null;
  surprise_median?: number | null; surprise_beat_quote?: number | null;
  '52w_high'?: number | null; '52w_low'?: number | null;
  _ist_zyklisch?: boolean; currency?: string;
}

export type Playbook = "quality" | "inflection" | "cyclical" | "financial";

export const V = {
  risk_free_rate: 0.042, equity_risk_premium: 0.05, default_beta: 1.1,
  tax_rate: 0.21, terminal_growth: 0.025, projection_years: 10,
};

const DEFENSIVE_SECTORS = new Set(["Utilities", "Consumer Defensive", "Healthcare"]);
const CYCLICAL_SECTORS = new Set(["Energy", "Basic Materials"]);
const CYCLICAL_INDUSTRIES = [
  "oil", "gas", "coal", "mining", "metals", "steel", "copper", "aluminum",
  "gold", "silver", "auto manufacturers", "auto parts", "airlines", "shipping",
  "marine", "homebuild", "memory", "semiconductor equipment", "chemicals",
  "paper", "lumber", "agricultural inputs", "building materials", "drilling",
];

export const WEIGHTS: Record<Playbook, Record<string, number>> = {
  quality:    { dcf: 0.30, justified_pe: 0.30, ev_ebitda: 0.25, analyst: 0.15 },
  inflection: { fwd_pe: 0.30, fwd_composite: 0.25, dcf: 0.30, analyst: 0.15 },
  cyclical:   { ev_ebitda: 0.35, pb: 0.25, epv: 0.25, analyst: 0.15 },
  financial:  { pb: 0.35, justified_pe: 0.30, fwd_pe: 0.20, analyst: 0.15 },
};

// Sektor-Aliase, 1:1 aus sektor._SEKTOR_ALIAS. Vereinheitlicht roic/FactSet-
// Namen ("Technology services" -> "Technology"). Ohne das fallen viele Titel
// still auf _default (Audit-Befund SK1: Techwert bekam 11 statt 16).
const SEKTOR_ALIAS: Record<string, string> = {
  "electronic technology": "Technology",
  "technology services": "Technology",
  "producer manufacturing": "Industrials",
  "electronic technology services": "Technology",
  "health technology": "Healthcare",
  "health services": "Healthcare",
  "energy minerals": "Energy",
  "industrial services": "Energy",
  "non-energy minerals": "Basic Materials",
  "process industries": "Basic Materials",
  "finance": "Financial Services",
  "consumer non-durables": "Consumer Defensive",
  "consumer services": "Consumer Cyclical",
  "consumer durables": "Consumer Cyclical",
  "retail trade": "Consumer Cyclical",
  "distribution services": "Industrials",
  "transportation": "Industrials",
  "commercial services": "Industrials",
  "communications": "Communication Services",
  "utilities": "Utilities",
  "miscellaneous": "Unknown",
};

export function normalisierenSektor(name: string | null | undefined): string {
  if (!name) return "";
  const s = String(name).trim();
  return SEKTOR_ALIAS[s.toLowerCase()] ?? s;
}


export function classifyPlaybook(fund: Fund): Playbook {
  const sector = normalisierenSektor(fund.sector);
  const industry = (fund.industry ?? "").toLowerCase();
  if (fund._ist_zyklisch) return "cyclical";
  if (sector === "Financial Services" && !paymentNetwork(fund)) return "financial";
  if (!DEFENSIVE_SECTORS.has(sector)) {
    if (CYCLICAL_SECTORS.has(sector) ||
        CYCLICAL_INDUSTRIES.some((k) => industry.includes(k))) return "cyclical";
  }
  let g = fund.revenue_growth;
  if (g === null || g === undefined) g = fund.earnings_growth ?? 0;
  if (g >= 0.25) return "inflection";
  return "quality";
}

export function wacc(beta: number | null | undefined,
  market_cap: number | null | undefined,
  total_debt: number | null | undefined, tax_rate?: number): number {
  const tax = tax_rate ?? V.tax_rate;
  const re = V.risk_free_rate + (beta ?? V.default_beta) * V.equity_risk_premium;
  const rd = V.risk_free_rate + 0.015;
  const e = market_cap ?? 0.0;
  const d = total_debt ?? 0.0;
  const tot = e + d;
  const w = tot <= 0 ? re : (e / tot) * re + (d / tot) * rd * (1 - tax);
  return Math.max(w, 0.085);
}

export interface FcfBasis {
  basis: number | null; gemeldet: number | null; normalisiert: number | null;
  conversion: number | null; quelle: "normalisiert" | "gemeldet";
}

export function fcfBasis(fund: Fund, conversion?: number | null): FcfBasis {
  const gemeldet = fund.free_cashflow ?? null;
  const conv = conversion ?? fund.cash_conversion ?? null;
  const ni = fund.net_income ?? null;
  const normal = conv && ni && ni > 0 ? ni * conv : null;
  let basis: number | null, quelle: "normalisiert" | "gemeldet";
  if (normal && normal > 0) { basis = normal; quelle = "normalisiert"; }
  else { basis = gemeldet; quelle = "gemeldet"; }
  return { basis, gemeldet, normalisiert: normal, conversion: conv, quelle };
}

export function dcfTwoStage(fund: Fund, preset: Playbook = "quality",
  conversion?: number | null): number | null {
  if (preset === "cyclical") return null;
  const shares = fund.shares_out;
  const fcf = fcfBasis(fund, conversion).basis;
  if (fund.net_debt == null) return null;
  if (!fcf || !shares || fcf <= 0) return null;
  const years = Math.max(Math.floor(V.projection_years), 2);
  const gTerm = V.terminal_growth;
  let g1 = fund.revenue_growth;
  if (g1 === null || g1 === undefined) g1 = fund.earnings_growth ?? 0.06;
  const cap = preset === "inflection" ? 0.25 : 0.16;
  g1 = Math.max(Math.min(g1, cap), -0.03);
  let r = wacc(fund.beta, fund.market_cap, fund.total_debt);
  if (r - gTerm < 0.045) r = gTerm + 0.045;
  let pv = 0.0, cf = fcf;
  for (let t = 1; t <= years; t++) {
    const gT = g1 + ((gTerm - g1) * (t - 1)) / (years - 1);
    cf *= 1 + gT;
    pv += cf / Math.pow(1 + r, t);
  }
  const terminal = (cf * (1 + gTerm)) / (r - gTerm) / Math.pow(1 + r, years);
  const equity = pv + terminal - (fund.net_debt ?? 0.0);
  return equity > 0 ? equity / shares : null;
}

/**
 * ungehebelteEkr - Schmidlins ungehebelte Eigenkapitalrendite.
 * 1:1 aus valuation.ungehebelte_ekr. Normalisiert ROE auf eine angemessene
 * EK-Basis, damit hohe Verschuldung nicht falsche Profitabilitaet vortaeuscht.
 */
export function ungehebelteEkr(fund: Fund & { operating_cashflow?: number | null }): number | null {
  const ni = fund.net_income;
  let assets = fund.total_assets ?? null;
  if (!assets) {
    const bvps = fund.book_value_ps, shares = fund.shares_out;
    const eq = bvps && shares ? bvps * shares : null;
    const debt = fund.total_debt ?? 0;
    if (eq) assets = eq + (debt ?? 0);
  }
  if (!ni || !assets || assets <= 0) return null;
  const opcf = fund.operating_cashflow ?? null;
  const fcf = fund.free_cashflow ?? null;
  let capex: number | null = null;
  if (opcf !== null && fcf !== null) capex = Math.abs(opcf - fcf);
  let sach: number | null = null;
  if (capex !== null && opcf && opcf > 0) sach = capex / opcf;
  if (sach === null) sach = 0.35;
  sach = Math.min(Math.max(sach, 0.25), 0.80);
  const fiktivesEk = assets * sach;
  if (fiktivesEk <= 0) return null;
  return ni / fiktivesEk;
}

/**
 * fairesKgv - die KGV-Leiter, ECHTE Portierung (gestufte Punkte).
 * 1:1 aus valuation.faires_kgv. Nutzt ungehebelte ROE, gestufte Rentabilitaets-
 * und Margenpunkte, differenziertes Wachstum. Cap je Playbook.
 */
export function fairesKgv(fund: Fund, preset: Playbook = "quality"): number | null {
  const base = 7.0;
  let stab = 0.0;
  if ((fund.free_cashflow ?? 0) > 0) stab += 1;
  const nde = fund.net_debt_ebitda;
  if (nde !== null && nde !== undefined) {
    stab += nde < 2 ? 1 : nde < 3 ? 0.5 : 0;
  }
  const cr = fund.current_ratio;
  if (cr && cr > 1.2) stab += 1;
  stab = Math.min(stab, 3);

  const uroe = ungehebelteEkr(fund);
  const roe = fund.roe ?? null;
  const basisRoe = uroe !== null ? uroe : roe;
  let prof: number;
  if (basisRoe === null) prof = 1.5;
  else prof = basisRoe < 0.05 ? 0 : basisRoe < 0.10 ? 1 : basisRoe < 0.15 ? 2
            : basisRoe < 0.20 ? 3 : 4;

  const gm = fund.gross_margin;
  const pos = (gm === null || gm === undefined || gm < 0.30) ? 1
            : gm < 0.40 ? 1.5 : gm < 0.50 ? 2 : gm < 0.65 ? 2.8 : 3.5;
  const moat = Math.min(prof * pos, 14);

  let g = fund.revenue_growth;
  if (g === null || g === undefined) g = fund.earnings_growth ?? 0;
  const gp = g < 0 ? 0 : g < 0.03 ? 0.5 : g < 0.05 ? 1 : g < 0.07 ? 2
           : g < 0.10 ? 3 : g < 0.15 ? 4 : g < 0.20 ? 5 : g < 0.25 ? 6
           : g < 0.35 ? 7.5 : 9;

  let fairPe = base + stab + moat + gp;
  if (preset === "inflection") fairPe *= 1.1;
  const cap = preset === "inflection" ? 50 : preset === "quality" ? 42
            : preset === "financial" ? 18 : 16;
  return Math.max(6.0, Math.min(fairPe, cap));
}

// --- Sektor-Multiples, exakt aus config ------------------------------------
export const SECTOR_EV_EBITDA: Record<string, number> = {
  "Technology": 16, "Communication Services": 9, "Consumer Cyclical": 10,
  "Consumer Defensive": 12, "Healthcare": 13, "Financial Services": 10,
  "Industrials": 12, "Energy": 6, "Basic Materials": 7, "Utilities": 10,
  "Real Estate": 16, "_default": 11,
};
export const SECTOR_PB: Record<string, number> = {
  "Technology": 6, "Communication Services": 3, "Consumer Cyclical": 4,
  "Consumer Defensive": 5, "Healthcare": 4, "Financial Services": 1.3,
  "Industrials": 4, "Energy": 1.6, "Basic Materials": 1.8, "Utilities": 1.6,
  "Real Estate": 1.8, "_default": 2.5,
};

function median(xs: number[]): number | null {
  const s = [...xs].sort((a, b) => a - b);
  const n = s.length;
  if (n === 0) return null;
  return n % 2 ? s[Math.floor(n / 2)] : (s[n / 2 - 1] + s[n / 2]) / 2;
}

/** Sektoranker aus einer Tabelle, mit vereinheitlichtem Namen (Audit SK1). */
function sectorAnchor(fund: Fund, table: Record<string, number>): number {
  const sek = normalisierenSektor(fund.sector);
  return table[sek] ?? table["_default"];
}

function epsIst(fund: Fund): number | null {
  return fund.eps_trailing ?? null;   // Audit V1: laufendes Ergebnis, nicht Prognose
}

function ebitEstimate(fund: Fund & { ps?: number | null }): number | null {
  const om = fund.operating_margin;
  let rev = fund.revenue ?? null;
  const mc = fund.market_cap, ps = fund.ps ?? null;
  if (!(rev && rev > 0) && mc && ps && ps > 0) {
    const derived = mc / ps;
    if (0.01 * mc <= derived && derived <= 100 * mc) rev = derived;
  }
  if (om && om > 0 && rev && rev > 0) return om * rev;
  const ebitda = fund.ebitda;
  return ebitda && ebitda > 0 ? 0.8 * ebitda : null;
}

/** justifiedPeNumber - faires KGV, nur bei positivem laufendem Ergebnis. */
export function justifiedPeNumber(fund: Fund, preset: Playbook = "quality"): number | null {
  const eps = epsIst(fund);
  if (!eps || eps <= 0) return null;
  return fairesKgv(fund, preset);
}

/** justifiedPe = faires KGV x laufendes EPS. 1:1 aus valuation.justified_pe. */
export function justifiedPe(fund: Fund, preset: Playbook = "quality"): number | null {
  const pe = justifiedPeNumber(fund, preset);
  const eps = epsIst(fund);
  return pe && eps && eps > 0 ? pe * eps : null;
}

/** fwdPe = erwartetes EPS x faires KGV. 1:1 aus valuation.fwd_pe. */
export function fwdPe(fund: Fund, preset: Playbook = "quality"): number | null {
  const eps1 = fund.eps_forward;
  if (!eps1 || eps1 <= 0) return null;
  const kgv = fairesKgv(fund, preset);
  return kgv ? eps1 * kgv : null;
}

/** multipleEvEbitda - EV/EBITDA-Verfahren mit Sektor-Multiple, Wachstums-
 *  aufschlag und Teil-Reversion. 1:1 aus valuation.multiple_ev_ebitda. */
export function multipleEvEbitda(
  fund: Fund, peerFunds: Fund[] | null, preset: Playbook = "quality",
): number | null {
  const shares = fund.shares_out, ebitda = fund.ebitda;
  if (fund.net_debt == null) return null;
  if (!shares || !ebitda || ebitda <= 0) return null;
  const cyclical = preset === "cyclical";
  let target: number;
  if (peerFunds && peerFunds.length) {
    const ms = peerFunds
      .map((p) => p.ev_ebitda)
      .filter((v): v is number => !!v && v > 0 && v < 60);
    target = median(ms) ?? sectorAnchor(fund, SECTOR_EV_EBITDA);
  } else {
    target = sectorAnchor(fund, SECTOR_EV_EBITDA);
  }
  if (!cyclical) {
    const g = fund.revenue_growth ?? 0;
    if (g > 0.10) target *= 1 + Math.min((g - 0.10) * 2.0, 0.6);
    const cur = fund.ev_ebitda;
    if (cur && cur > 0) target = 0.6 * target + 0.4 * Math.min(cur, 2.5 * target);
  } else {
    target = Math.min(target, 8.5);
  }
  const equity = target * ebitda - (fund.net_debt ?? 0.0);
  return equity > 0 ? equity / shares : null;
}

/** epv - Earnings Power Value (Greenwald). 1:1 aus valuation.epv. */
export function epv(fund: Fund, _preset: Playbook = "quality"): number | null {
  if (fund.net_debt == null) return null;
  const ebit = ebitEstimate(fund);
  const shares = fund.shares_out;
  if (!ebit || !shares || ebit <= 0) return null;
  const nopat = ebit * (1 - V.tax_rate);
  const w = wacc(fund.beta, fund.market_cap, fund.total_debt);
  const evEpv = nopat / w;
  const equity = evEpv - (fund.net_debt ?? 0.0);
  return equity > 0 ? equity / shares : null;
}

/** multiplePb - Kurs-Buchwert-Verfahren. 1:1 aus valuation.multiple_pb. */
export function multiplePb(fund: Fund, preset: Playbook = "quality"): number | null {
  let bvps = fund.book_value_ps;
  if ((!bvps || bvps <= 0) && preset === "financial") {
    const price = fund.price, pb = fund.pb;
    if (price && pb && pb > 0) bvps = price / pb;
  }
  if (!bvps || bvps <= 0) return null;
  const targetPb = preset === "cyclical" ? 1.8 : sectorAnchor(fund, SECTOR_PB);
  return targetPb * bvps;
}

/** analystTarget - Analysten-Konsensziel, plausibilitaetsgeprueft (0.3-3.5x Kurs). */
export function analystTarget(fund: Fund): number | null {
  const tgt = fund.target_mean, price = fund.price;
  if (!tgt || !price || price <= 0) return null;
  if (!(0.3 * price <= tgt && tgt <= 3.5 * price)) return null;
  return tgt;
}

/** histPe - Forward-EPS x historischer Median-KGV (gedeckelt 60). */
export function histPe(fund: Fund, _preset: Playbook = "quality"): number | null {
  const eps1 = fund.eps_forward ?? fund.eps_trailing;
  let med = fund.hist_pe_median;
  if (!eps1 || eps1 <= 0 || !med || med <= 0) return null;
  med = Math.min(med, 60.0);
  return eps1 * med;
}

/** fwdComposite - Mittel aus fwdPe und Forward-EV/EBITDA. */
export function fwdComposite(fund: Fund, preset: Playbook = "quality"): number | null {
  const parts: number[] = [];
  const a = fwdPe(fund, preset);
  if (a) parts.push(a);
  const ebitda = fund.ebitda, shares = fund.shares_out;
  if (ebitda && ebitda > 0 && shares) {
    let g = fund.revenue_growth;
    g = Math.max(Math.min(g ?? 0.0, 0.30), -0.10);
    const ebitdaFwd = ebitda * (1 + g);
    let target = sectorAnchor(fund, SECTOR_EV_EBITDA);
    if (preset === "cyclical") target = Math.min(target, 8.5);
    const equity = ebitdaFwd * target - (fund.net_debt ?? 0.0);
    if (equity > 0) parts.push(equity / shares);
  }
  if (!parts.length) return null;
  return parts.reduce((s, x) => s + x, 0) / parts.length;
}

// --- config-Konstanten fuer fairValue --------------------------------------
const FAIR_VALUE_MAX_MULT = 3.0;
const FAIR_VALUE_MIN_MULT = 0.3;
export const TERMINAL_ANTEIL_WARN = 0.75;
const METHODEN_HERKUNFT: Record<string, string> = {
  justified_pe: "multiple", fwd_pe: "multiple", fwd_composite: "multiple",
  hist_pe: "multiple", ev_ebitda: "multiple", pb: "substanz",
  epv: "ertragskraft", dcf: "cashflow", analyst: "markt", fallback: "notbehelf",
};

const MARGIN_OF_SAFETY: Record<Playbook, number> = {
  quality: 0.18, cyclical: 0.25, inflection: 0.25, financial: 0.20,
};

export interface FairValueResult {
  lifecycle: PhaseResult;
  method_weights: Record<string, number>;
  core_methods: Record<string, number>;
  used_fallback: boolean;
  fair_value: number | null;
  upside_pct: number | null;
  entry_price: number | null;
  target_12m: number | null;
  methods: Record<string, number>;
  verworfen: Record<string, { wert: number; vs_kurs: number | null; grund: string }>;
  confidence: "hoch" | "mittel" | "niedrig";
  reliable: boolean;
  spread_pct: number | null;
  n_methods: number;
  capped: boolean;
  margin_of_safety: number;
  playbook: Playbook;
  nach_herkunft: Record<string, number>;
}

/**
 * fairValue - bestehender Modellmischer, erweitert um Unternehmensphasen.
 * Methodenauswahl -> Plausibilitaetsfilter -> Median-Core -> Analysten-Anker
 * -> gewichteter Schnitt -> Deckel -> Verlaesslichkeit.
 */
export function fairValue(
  fund: Fund, peerFunds: Fund[] | null = null, preset: Playbook = "quality",
  phase: PhaseResult = analysePhase(fund),
): FairValueResult {
  const dataCheck = fund.valuation_data ?? valuationDataCheck(fund);
  const methods: Record<string, number | null> = {
    justified_pe: justifiedPe(fund, preset),
    ev_ebitda: multipleEvEbitda(fund, peerFunds, preset),
    dcf: dcfTwoStage(fund, preset),
    pb: multiplePb(fund, preset),
    epv: epv(fund, preset),
    fwd_pe: fwdPe(fund, preset),
    fwd_composite: fwdComposite(fund, preset),
    hist_pe: histPe(fund, preset),
    analyst: analystTarget(fund),
  };
  const weights = phaseWeights(fund, preset, WEIGHTS[preset] ?? WEIGHTS.quality, phase);
  const price = fund.price ?? null;

  // 1) verfuegbare positive Methoden im Playbook
  const raw: Record<string, number> = {};
  for (const [k, v] of Object.entries(methods)) {
    if (v && v > 0 && k in weights) raw[k] = v;
  }

  // 2) Plausibilitaetsfilter
  const untergrenze = preset === "cyclical" ? 0.12 : 0.25;
  const obergrenze = preset === "cyclical" ? 5.0 : 4.0;
  const rohWerte = Object.values(raw).filter((v) => isFinite(v) && v > 0).sort((a, b) => a - b);
  const medianRoh = rohWerte.length ? rohWerte[Math.floor(rohWerte.length / 2)] : null;
  const kursTaugtAlsAnker = !(price && medianRoh && medianRoh < 0.30 * price);
  const plausible = (v: number): boolean => {
    if (!price || !kursTaugtAlsAnker) return true;
    return untergrenze * price <= v && v <= obergrenze * price;
  };
  const sane: Record<string, number> = {};
  for (const [k, v] of Object.entries(raw)) if (plausible(v)) sane[k] = v;

  const verworfen: FairValueResult["verworfen"] = {};
  for (const [k, v] of Object.entries(raw)) {
    if (!(k in sane)) {
      verworfen[k] = {
        wert: Math.round(v * 100) / 100,
        vs_kurs: price ? Math.round((v / price - 1) * 1000) / 10 : null,
        grund: price && v < untergrenze * price
          ? `unter ${untergrenze.toFixed(2)}x Kurs`
          : `ueber ${obergrenze.toFixed(0)}x Kurs`,
      };
    }
  }

  // 3) Median-Core
  let core: Record<string, number>;
  if (Object.keys(sane).length >= 3) {
    const med0 = median(Object.values(sane));
    core = {};
    for (const [k, v] of Object.entries(sane)) {
      if (med0 && med0 / 2.0 <= v && v <= med0 * 2.0) core[k] = v;
      else verworfen[k] = {
        wert: Math.round(v * 100) / 100,
        vs_kurs: price ? Math.round((v / price - 1) * 1000) / 10 : null,
        grund: `mehr als Faktor 2 vom Median (${med0?.toFixed(0)}) entfernt`,
      };
    }
    if (Object.keys(core).length < 2) core = { ...sane };
  } else {
    core = { ...sane };
  }

  // 4) Analysten-Anker
  const anlRaw = methods.analyst;
  const anlOk = !!(anlRaw && anlRaw > 0 && plausible(anlRaw));
  if (anlOk) core["analyst"] = anlRaw!;

  // 5) Rueckfall
  let usedFallback = false;
  if (!Object.keys(core).length) {
    let fb = anlRaw && anlRaw > 0 ? anlRaw : median(Object.values(raw));
    if (fb && price) fb = Math.max(Math.min(fb, 2.0 * price), 0.5 * price);
    if (fb) { core = { fallback: fb }; usedFallback = true; }
  }

  // gewichteter Schnitt + Deckel
  let fv: number | null = null, capped = false, spread: number | null = null;
  if (Object.keys(core).length) {
    const vals = Object.values(core);
    const lo = Math.min(...vals), hi = Math.max(...vals);
    const med = median(vals);
    spread = med ? Math.round(((hi - lo) / med) * 100) : null;
    const wsum = Object.keys(core).reduce((s, k) => s + (weights[k] ?? 0.15), 0);
    fv = wsum
      ? Object.keys(core).reduce((s, k) => s + core[k] * (weights[k] ?? 0.15), 0) / wsum
      : med;
    if (fv && price) {
      if (fv > price * FAIR_VALUE_MAX_MULT) { fv = price * FAIR_VALUE_MAX_MULT; capped = true; }
      else if (fv < price * FAIR_VALUE_MIN_MULT) { fv = price * FAIR_VALUE_MIN_MULT; capped = true; }
    }
  }

  // Herkunftszerlegung: welcher Anteil des FV stammt aus Multiple/Cashflow/...
  const nachHerkunft: Record<string, number> = {};
  if (fv && Object.keys(core).length) {
    const wsum = Object.keys(core).reduce((s, k) => s + (weights[k] ?? 0.15), 0);
    for (const k of Object.keys(core)) {
      const beitrag = core[k] * (weights[k] ?? 0.15) / wsum;
      const h = METHODEN_HERKUNFT[k] ?? "unbekannt";
      nachHerkunft[h] = (nachHerkunft[h] ?? 0) + beitrag / fv;
    }
  }

  // Anzeige auf 3 naechste Methoden
  let avail: Record<string, number> = { ...core };
  if (fv && Object.keys(avail).length > 3) {
    const near = Object.entries(avail).sort((a, b) => Math.abs(a[1] - fv!) - Math.abs(b[1] - fv!)).slice(0, 3);
    avail = Object.fromEntries(near);
  }

  // Inconsistent inputs cannot become a valuation recommendation.
  if (dataCheck.blocked) { fv = null; avail = {}; core = {}; capped = false; }

  // Margin of Safety mit Risikoaufschlag
  let mos = MARGIN_OF_SAFETY[preset] ?? 0.20;
  let riskAdd = 0.0;
  const nde = fund.net_debt_ebitda;
  if (nde !== null && nde !== undefined && nde > 3) riskAdd += nde <= 4 ? 0.04 : 0.08;
  if ((fund.free_cashflow ?? 0) < 0) riskAdd += 0.04;
  const cr = fund.current_ratio;
  if (cr !== null && cr !== undefined && cr < 1.0) riskAdd += 0.03;
  if (fund._ist_zyklisch) riskAdd += 0.03;
  mos = Math.min(mos + riskAdd, 0.55);
  const entry = fv ? fv * (1 - mos) : null;

  let g1 = fund.revenue_growth;
  if (g1 === null || g1 === undefined) g1 = V.terminal_growth;
  g1 = Math.max(Math.min(g1, 0.12), 0.0);
  const target12m = fv ? fv * (1 + g1) : null;
  const upside = fv && price ? (fv / price - 1) * 100 : null;

  // Verlaesslichkeit
  const nCore = Object.keys(core).filter((k) => k !== "fallback").length;
  const hasAnchor = "analyst" in core;
  const sp = spread ?? 999;
  let confidence: "hoch" | "mittel" | "niedrig", reliable: boolean;
  if (usedFallback || nCore === 0) { confidence = "niedrig"; reliable = false; }
  else if (nCore >= 3 && sp <= 35) { confidence = "hoch"; reliable = true; }
  else if (nCore >= 2 && sp <= 60) { confidence = "mittel"; reliable = true; }
  else if (nCore === 1 && hasAnchor) { confidence = "mittel"; reliable = true; }
  else if (nCore >= 2 && sp <= 90) { confidence = "mittel"; reliable = true; }
  else { confidence = "niedrig"; reliable = false; }
  if (capped && confidence === "hoch") confidence = "mittel";
  if (dataCheck.blocked) { confidence = "niedrig"; reliable = false; }

  if (['startup', 'hypergrowth', 'decline'].includes(phase.id)) {
    reliable = false; confidence = 'niedrig';
  }
  return {
    lifecycle: phase, method_weights: weights, core_methods: core, used_fallback: usedFallback,
    fair_value: fv ? Math.round(fv * 100) / 100 : null,
    upside_pct: upside !== null ? Math.round(upside * 10) / 10 : null,
    entry_price: entry ? Math.round(entry * 100) / 100 : null,
    target_12m: target12m ? Math.round(target12m * 100) / 100 : null,
    methods: Object.fromEntries(Object.entries(avail).map(([k, v]) => [k, Math.round(v * 100) / 100])),
    verworfen,
    confidence, reliable,
    spread_pct: spread,
    n_methods: Object.keys(avail).length,
    capped,
    margin_of_safety: Math.round(mos * 1000) / 1000,
    playbook: preset,
    nach_herkunft: Object.fromEntries(
      Object.entries(nachHerkunft).sort((a, b) => b[1] - a[1])
        .map(([k, v]) => [k, Math.round(v * 10000) / 10000])),
  };
}

/**
 * reverseDcfImpliedGrowth - welches Anfangswachstum rechtfertigt den heutigen
 * Kurs? Bisektion ueber dasselbe zweistufige DCF. 1:1 aus Python.
 */
export function reverseDcfImpliedGrowth(fund: Fund, years?: number): number | null {
  const price = fund.price, fcf = fund.free_cashflow, shares = fund.shares_out;
  if (![price,fcf,shares].every(x=>typeof x==='number'&&Number.isFinite(x)&&x>0)) return null;
  if (price == null || fcf == null || shares == null) return null;
  const targetEquity = price * shares + (fund.net_debt ?? 0.0);
  let r = wacc(fund.beta, fund.market_cap, fund.total_debt);
  const gTerm = V.terminal_growth;
  if (r - gTerm < 0.04) r = gTerm + 0.04;
  const yrs = years ?? V.projection_years;
  if(!Number.isInteger(yrs)||yrs<2||yrs>50||!Number.isFinite(targetEquity)||targetEquity<=0)return null;

  const equityForG = (g: number): number => {
    let pv = 0.0, cf = fcf;
    for (let t = 1; t <= yrs; t++) {
      cf *= 1 + g;
      pv += cf / Math.pow(1 + r, t);
    }
    pv += (cf * (1 + gTerm)) / (r - gTerm) / Math.pow(1 + r, yrs);
    return pv;
  };

  let lo = -0.20, hi = 0.60;
  if(targetEquity<equityForG(lo)||targetEquity>equityForG(hi))return null;
  for (let i = 0; i < 60; i++) {
    const mid = (lo + hi) / 2;
    if (equityForG(mid) < targetEquity) lo = mid;
    else hi = mid;
  }
  return Math.round(((lo + hi) / 2) * 10000) / 10000;
}

export interface Kursziel12m {
  ziel: number;
  upside_pct: number;
  eps_annahme: number;
  kgv_annahme: number;
  kgv_heute: number | null;
  kgv_hist: number | null;
  analyst_target: number | null;
  vs_analyst: number | null;
  herleitung: string[];
  extrem: boolean;
  ziel_fundamental: number | null;
  ziel_analyst: number | null;
  ziel_momentum: number | null;
  spanne_tief: number;
  spanne_hoch: number;
  konfidenz: string;
}

/**
 * kursziel12m - MEHRFAKTORIELLES 12-Monats-Kursziel. Drei unabhaengige
 * Schaetzungen (Fundamental mit Guidance-Proxy, Analystenkonsens, Momentum)
 * werden adaptiv gewichtet gemischt; ihre Streuung ergibt Spanne + Konfidenz.
 */
export function kursziel12m(fund: Fund, _preset: Playbook = "quality"): Kursziel12m | null {
  if ((fund.valuation_data ?? valuationDataCheck(fund)).blocked) return null;
  const kurs = fund.price;
  if (!kurs || kurs <= 0) return null;
  const epsTtm = fund.eps_trailing;
  const epsFwd = fund.eps_forward;
  const herleitung: string[] = [];

  // A) FUNDAMENTAL
  let zielFund: number | null = null;
  let epsAnnahme = 0, kgvAnnahme = 0;
  const kgvHeute = epsTtm && epsTtm > 0 ? kurs / epsTtm : null;
  const kgvHist = (fund.pe_hist_median as number | null) ?? null;
  let eps = epsFwd && epsFwd > 0 ? epsFwd : null;
  let epsQuelle = fund.eps_forward_source ?? "Forward-EPS (Quelle nicht ausgewiesen)";
  if (!eps) {
    const g = (fund.earnings_growth as number | null) ?? (fund.revenue_growth as number | null) ?? null;
    if (epsTtm && epsTtm > 0 && g !== null) {
      eps = epsTtm * (1 + Math.max(Math.min(g, 0.30), -0.20));
      epsQuelle = "Realisierter Gewinn x Wachstum (kein Konsens)";
    }
  }
  if (eps && eps > 0) {
    let guidanceFaktor = 1.0;
    const begruendung: string[] = [];

    // (1) Gewinntrend aus 3-Jahres-EBITDA-Reihe (beschleunigt/verlangsamt)
    const reihe = fund.reihe_ebitda as { wert: number | null }[] | undefined;
    let beschleunigt = 0;
    if (reihe && reihe.length >= 3) {
      const w = reihe.map((r) => r.wert ?? 0);
      const g1 = w[0] ? w[1] / w[0] - 1 : 0;
      const g2 = w[1] ? w[2] / w[1] - 1 : 0;
      if (g2 > g1 + 0.03) { beschleunigt = 1; begruendung.push("Gewinntrend beschleunigt"); }
      else if (g2 < g1 - 0.03) { beschleunigt = -1; begruendung.push("Gewinntrend verlangsamt"); }
    }

    // (2) Analystensentiment (buy vs sell)
    const buy = (fund.analyst_buy as number) ?? 0;
    const hold = (fund.analyst_hold as number) ?? 0;
    const sell = (fund.analyst_sell as number) ?? 0;
    const gesamt = buy + hold + sell;
    const sentiment = gesamt >= 3 ? (buy - sell) / gesamt : 0;
    if (sentiment > 0.2) begruendung.push("Analysten optimistisch");
    else if (sentiment < -0.2) begruendung.push("Analysten vorsichtig");

    // (3) Earnings-Surprise (Finnhub): schlaegt die Firma ihre Schaetzungen?
    // Die einzige echte Forward-nahe Datenquelle, die der Tarif liefert.
    const surpMed = (fund.surprise_median as number | null) ?? null;   // in %
    const beatQ = (fund.surprise_beat_quote as number | null) ?? null; // 0..1
    let surpFaktor = 0;
    if (surpMed !== null && beatQ !== null) {
      // konstante Uebertreffer (>60% Quote, positiver Median) -> leicht hoch
      if (beatQ >= 0.6 && surpMed > 1) { surpFaktor = 0.02; begruendung.push(`schlaegt Schaetzungen meist (${(beatQ * 100).toFixed(0)}%)`); }
      else if (beatQ <= 0.4 && surpMed < -1) { surpFaktor = -0.02; begruendung.push(`verfehlt Schaetzungen oft`); }
    }

    // Guidance-Faktor: drei Signale, gedeckelt auf +/-7%
    guidanceFaktor = 1.0 + Math.max(Math.min(beschleunigt * 0.025 + sentiment * 0.025 + surpFaktor, 0.07), -0.07);
    eps = eps * guidanceFaktor;
    if (Math.abs(guidanceFaktor - 1) >= 0.01 && begruendung.length) {
      herleitung.push(`Guidance-Proxy (${begruendung.join(", ")}) -> EPS ${guidanceFaktor >= 1 ? "+" : ""}${((guidanceFaktor - 1) * 100).toFixed(0)}% auf ${eps.toFixed(2)}`);
    } else {
      herleitung.push(`Erwarteter Gewinn: ${eps.toFixed(2)} je Aktie (${epsQuelle})`);
    }
    epsAnnahme = eps;
    let kgvZiel: number;
    if (kgvHist && kgvHist > 0 && kgvHeute && kgvHeute > 0) {
      const peMin = fund.pe_hist_min as number | null;
      const peMax = fund.pe_hist_max as number | null;
      let bandPos = 0.5;
      if (peMin && peMax && peMax > peMin) bandPos = Math.max(0, Math.min(1, (kgvHeute - peMin) / (peMax - peMin)));
      const teuer = kgvHeute > kgvHist;
      const anteil = teuer ? 0.40 + bandPos * 0.25 : 0.20 + (1 - bandPos) * 0.15;
      const abstand = kgvHist - kgvHeute;
      let schritt = abstand * anteil;
      const grenzeAuf = kgvHeute * 0.15;
      const grenzeAb = teuer ? kgvHeute * 0.45 : kgvHeute * 0.20;
      schritt = Math.max(Math.min(schritt, grenzeAuf), -grenzeAb);
      kgvZiel = kgvHeute + schritt;
      herleitung.push(`Multiple: ${kgvHeute.toFixed(0)}x heute -> ${kgvZiel.toFixed(0)}x (Richtung Median ${kgvHist.toFixed(0)}x, Position im 5J-Band ${(bandPos * 100).toFixed(0)}%)`);
    } else if (kgvHeute && kgvHeute > 0) {
      kgvZiel = kgvHeute;
      herleitung.push(`Multiple: ${kgvHeute.toFixed(0)}x gehalten (keine KGV-Historie)`);
    } else kgvZiel = kgvHist ?? 15;
    kgvAnnahme = kgvZiel;
    zielFund = eps * kgvZiel;
  }

  // B) ANALYSTEN
  let zielAnalyst: number | null = null;
  const target = fund.target_mean as number | null;
  const nAnalyst = (fund.analyst_count as number) ?? 0;
  if (target && target > 0 && target >= 0.3 * kurs && target <= 3.5 * kurs) {
    zielAnalyst = target;
    herleitung.push(`Analysten-Konsensziel: ${target.toFixed(0)} (${nAnalyst} Analysten)`);
  }

  // C) MOMENTUM
  let zielMom: number | null = null;
  const hi = fund["52w_high"] as number | null;
  const lo = fund["52w_low"] as number | null;
  if (hi && lo && hi > lo) {
    const pos = Math.max(0, Math.min(1, (kurs - lo) / (hi - lo)));
    const mitte = (hi + lo) / 2;
    zielMom = kurs + (mitte - kurs) * 0.35 + (hi - kurs) * 0.15 * (1 - pos);
    herleitung.push(`Marktlage: Kurs bei ${(pos * 100).toFixed(0)}% im 52W-Band (${lo.toFixed(0)}-${hi.toFixed(0)})`);
  }

  // MISCHUNG
  const schaetzungen: { wert: number; gewicht: number }[] = [];
  if (zielFund) schaetzungen.push({ wert: zielFund, gewicht: 0.50 });
  if (zielAnalyst) schaetzungen.push({ wert: zielAnalyst, gewicht: Math.min(0.40, 0.20 + nAnalyst * 0.012) });
  if (zielMom) schaetzungen.push({ wert: zielMom, gewicht: 0.15 });
  if (!schaetzungen.length) return null;
  const gSum = schaetzungen.reduce((a, x) => a + x.gewicht, 0);
  let ziel = schaetzungen.reduce((a, x) => a + x.wert * x.gewicht, 0) / gSum;
  ziel = Math.max(Math.min(ziel, kurs * 1.60), kurs * 0.60);
  const werte = schaetzungen.map((x) => x.wert);
  const spanneTief = Math.min(ziel * 0.92, ...werte);
  const spanneHoch = Math.max(ziel * 1.08, ...werte);
  const streuung = werte.length > 1 ? (Math.max(...werte) - Math.min(...werte)) / ziel : 0.5;
  let konfidenz = "mittel";
  if (schaetzungen.length >= 3 && streuung < 0.15) konfidenz = "hoch";
  else if (schaetzungen.length === 1 || streuung > 0.40) konfidenz = "niedrig";
  const upside = (ziel / kurs - 1) * 100;
  const vsAnalyst = target && target > 0 ? (ziel / target - 1) * 100 : null;
  const extrem = Math.abs(upside) > 45;
  if (extrem) herleitung.push(`! ${upside >= 0 ? "+" : ""}${upside.toFixed(0)}% in 12 Monaten ist viel - als Richtung lesen, nicht als Punktziel.`);

  return {
    ziel: Math.round(ziel * 100) / 100,
    upside_pct: Math.round(upside * 10) / 10,
    eps_annahme: Math.round(epsAnnahme * 100) / 100,
    kgv_annahme: Math.round(kgvAnnahme * 10) / 10,
    kgv_heute: kgvHeute ? Math.round(kgvHeute * 10) / 10 : null,
    kgv_hist: kgvHist,
    analyst_target: target ?? null,
    vs_analyst: vsAnalyst !== null ? Math.round(vsAnalyst * 10) / 10 : null,
    herleitung, extrem,
    ziel_fundamental: zielFund ? Math.round(zielFund * 100) / 100 : null,
    ziel_analyst: zielAnalyst ? Math.round(zielAnalyst * 100) / 100 : null,
    ziel_momentum: zielMom ? Math.round(zielMom * 100) / 100 : null,
    spanne_tief: Math.round(spanneTief * 100) / 100,
    spanne_hoch: Math.round(spanneHoch * 100) / 100,
    konfidenz,
  };
}

export interface Projektionspunkt {
  horizont: string; monate: number; mitte: number;
  tief: number; hoch: number; spanne_pct: number;
}
export interface KursProjektion {
  kurs: number; ziel_12m: number | null; vola_pct: number;
  punkte: Projektionspunkt[]; warnung: string;
}

/**
 * kursProjektion - Kursband 1/3/6 Monate. Trichter, der sich oeffnet.
 * 1:1 aus valuation.kurs_projektion. Spanne = Vola x sqrt(t).
 */
export function kursProjektion(
  fund: Fund, kursziel12mWert?: number | null, volaPct?: number | null,
  preset: Playbook = "quality",
): KursProjektion | null {
  const kurs = fund.price;
  if (!kurs || kurs <= 0) return null;

  let ziel = kursziel12mWert ?? null;
  if (ziel === null || ziel === undefined) {
    const kz = kursziel12m(fund, preset);
    ziel = kz ? kz.ziel : null;
  }
  const jahresRendite = ziel ? ziel / kurs - 1 : 0.0;

  let vp = volaPct ?? null;
  if (vp === null || vp === undefined) {
    const beta = fund.beta ?? 1.0;
    vp = 18.0 * Math.max(0.5, Math.min(beta, 2.5));
  }
  const vola = vp / 100.0;

  const horizonte: [string, number][] = [
    ["1 Monat", 1 / 12], ["3 Monate", 3 / 12], ["6 Monate", 6 / 12],
  ];
  const punkte: Projektionspunkt[] = horizonte.map(([name, t]) => {
    const mitte = kurs * (1 + jahresRendite * t);
    const band = kurs * vola * Math.sqrt(t);
    return {
      horizont: name,
      monate: Math.round(t * 12),
      mitte: Math.round(mitte * 100) / 100,
      tief: Math.round((mitte - band) * 100) / 100,
      hoch: Math.round((mitte + band) * 100) / 100,
      spanne_pct: Math.round((band / kurs) * 1000) / 10,
    };
  });

  return {
    kurs: Math.round(kurs * 100) / 100,
    ziel_12m: ziel ? Math.round(ziel * 100) / 100 : null,
    vola_pct: Math.round(vp * 10) / 10,
    punkte,
    warnung: "Mechanische Fortschreibung, keine Vorhersage. Die Spanne ist die eigentliche Aussage - sie zeigt, wie gross die Unsicherheit auf kurze Sicht ist.",
  };
}

// --- DCF-Diagnose: Terminalwert-Anteil und Multiple-Ampel ------------------
interface DcfTeile {
  barwert_explizit: number; terminal_roh: number; terminal_barwert: number;
  terminal_anteil: number | null; fcf_endjahr: number;
  equity: number; wert_je_aktie: number | null;
}
function dcfTeile(
  fcf: number, shares: number, netDebt: number,
  g1: number, gTerm: number, r: number, years: number,
): DcfTeile {
  let pv = 0.0, cf = fcf;
  for (let t = 1; t <= years; t++) {
    const gT = g1 + ((gTerm - g1) * (t - 1)) / (years - 1);
    cf *= 1 + gT;
    pv += cf / Math.pow(1 + r, t);
  }
  const terminalRoh = (cf * (1 + gTerm)) / (r - gTerm);
  const terminalBw = terminalRoh / Math.pow(1 + r, years);
  const equity = pv + terminalBw - (netDebt ?? 0.0);
  const gesamt = pv + terminalBw;
  return {
    barwert_explizit: pv, terminal_roh: terminalRoh, terminal_barwert: terminalBw,
    terminal_anteil: gesamt ? terminalBw / gesamt : null,
    fcf_endjahr: cf, equity,
    wert_je_aktie: shares && equity > 0 ? equity / shares : null,
  };
}

export interface DcfDiagnose {
  terminal_anteil: number | null;
  terminal_lastig: boolean;
  multiple_genutzt: number;
  multiple_impliziert: number | null;
  multiple_heute: number | null;
  wacc: number;
  jahre: number;
  hinweise: string[];
}

/** dcfDiagnose - Terminalwert-Anteil + impliziertes vs. genutztes vs. heutiges
 *  Multiple ("Woher der Wert kommt"). 1:1 aus valuation.dcf_diagnose. */
export function dcfDiagnose(fund: Fund, preset: Playbook = "quality"): DcfDiagnose | null {
  if (preset === "cyclical") return null;
  const basis = fcfBasis(fund);
  const fcf = basis.basis, shares = fund.shares_out;
  if (!fcf || !shares || fcf <= 0) return null;

  const years = Math.max(Math.floor(V.projection_years), 2);
  const gTerm = V.terminal_growth;
  let g1 = fund.revenue_growth;
  if (g1 === null || g1 === undefined) g1 = fund.earnings_growth ?? 0.06;
  const cap = preset === "inflection" ? 0.25 : 0.16;
  g1 = Math.max(Math.min(g1, cap), -0.03);
  let r = wacc(fund.beta, fund.market_cap, fund.total_debt);
  if (r - gTerm < 0.045) r = gTerm + 0.045;

  const netDebt = fund.net_debt ?? 0.0;
  const teile = dcfTeile(fcf, shares, netDebt, g1, gTerm, r, years);

  const multGenutzt = (1 + gTerm) / (r - gTerm);
  const price = fund.price;
  let multImpliziert: number | null = null;
  if (price && price > 0) {
    const zielEquity = price * shares + netDebt;
    const rest = zielEquity - teile.barwert_explizit;
    if (rest > 0 && teile.fcf_endjahr) {
      multImpliziert = (rest * Math.pow(1 + r, years)) / teile.fcf_endjahr;
    }
  }
  const mcap = fund.market_cap ?? (price ? price * shares : null);
  const multHeute = mcap && fcf ? mcap / fcf : null;

  const hinweise: string[] = [];
  const ta = teile.terminal_anteil;
  if (ta && ta > TERMINAL_ANTEIL_WARN) {
    hinweise.push(`${Math.round(ta * 100)}% des DCF-Werts stecken im Terminalwert. Das Modell ist im Kern eine Wette auf das Endmultiple, nicht auf die naechsten ${years} Jahre.`);
  }
  if (multImpliziert && multGenutzt && multImpliziert > multGenutzt * 1.25) {
    hinweise.push(`Der Kurs verlangt ein Terminal-Multiple von ${multImpliziert.toFixed(1)}x auf den Endjahres-Cashflow; das Modell unterstellt ${multGenutzt.toFixed(1)}x.`);
  }
  if (basis.quelle === "normalisiert" && basis.normalisiert && basis.gemeldet) {
    const abw = basis.normalisiert / basis.gemeldet - 1.0;
    hinweise.push(`DCF rechnet mit normalisiertem Cashflow: Nettogewinn x ${Math.round((basis.conversion ?? 0) * 100)}% Conversion = ${(basis.normalisiert / 1e9).toFixed(1)} Mrd statt gemeldeter ${(basis.gemeldet / 1e9).toFixed(1)} Mrd (${abw >= 0 ? "+" : ""}${Math.round(abw * 100)}%).`);
  }

  return {
    terminal_anteil: ta ? Math.round(ta * 10000) / 10000 : null,
    terminal_lastig: !!(ta && ta > TERMINAL_ANTEIL_WARN),
    multiple_genutzt: Math.round(multGenutzt * 10) / 10,
    multiple_impliziert: multImpliziert !== null ? Math.round(multImpliziert * 10) / 10 : null,
    multiple_heute: multHeute ? Math.round(multHeute * 10) / 10 : null,
    wacc: Math.round(r * 10000) / 10000,
    jahre: years,
    hinweise,
  };
}

// --- Szenarien: Bear / Base / Bull -----------------------------------------
const SEKUNDAER_DAEMPFUNG = 0.5;
const SZENARIEN: ("bear" | "base" | "bull")[] = ["bear", "base", "bull"];

function playbookGewicht(preset: Playbook, methode: string): number {
  const w = WEIGHTS[preset] ?? WEIGHTS.quality;
  return w[methode] ?? 0.15;
}

/** Kopie des Fund mit verschobenen PRIMITIVEN Treibern. 1:1 aus _szenario_fund.
 *  Nicht die Methodenergebnisse verschieben, sondern die Eingangsgroessen -
 *  dann rechnen alle Methoden das Szenario selbst durch. */
function szenarioFund(
  fund: Fund, szenario: string, gDelta: number, opDelta: number,
  bewDelta: number, betaDelta: number,
): Fund {
  if (szenario === "base") return { ...fund };
  const vz = szenario === "bear" ? -1.0 : 1.0;
  const d = SEKUNDAER_DAEMPFUNG;
  const f: Record<string, unknown> = { ...fund };

  for (const k of ["revenue_growth", "earnings_growth"]) {
    if (f[k] !== null && f[k] !== undefined) f[k] = (f[k] as number) + vz * gDelta;
  }
  const op = 1.0 + vz * opDelta;
  for (const k of ["free_cashflow", "ebitda", "eps_forward", "eps_trailing", "net_income"]) {
    if (f[k] !== null && f[k] !== undefined) f[k] = (f[k] as number) * op;
  }
  if (f.operating_margin !== null && f.operating_margin !== undefined) {
    f.operating_margin = (f.operating_margin as number) * op;
  }
  const bw = 1.0 + vz * bewDelta * d;
  for (const k of ["hist_pe_median", "ev_ebitda"]) {
    if (f[k] !== null && f[k] !== undefined) f[k] = (f[k] as number) * bw;
  }
  if (f.beta !== null && f.beta !== undefined) {
    f.beta = Math.max(0.3, (f.beta as number) - vz * betaDelta * d);
  }
  return f as Fund;
}

export interface SzenarioMatrix {
  methoden: Record<string, Record<string, number | null>>;
  blend: Record<string, number | null>;
  upside: Record<string, number | null>;
  blend_konsistent: Record<string, number | null>;
  warnungen: string[];
  preis: number;
}

/** szenarioMatrix - Bear/Base/Bull je Methode. Ruft fairValue dreimal mit
 *  verschobenen Eingangsgroessen und derselben Ausgangsphase. */
export function szenarioMatrix(
  fund: Fund, peerFunds: Fund[] | null = null, preset: Playbook = "quality",
): SzenarioMatrix | null {
  const price = fund.price;
  if (!price) return null;

  let g = fund.revenue_growth;
  if (g === null || g === undefined) g = fund.earnings_growth ?? 0.06;
  const gDelta = Math.max(0.03, Math.abs(g) * 0.5);
  const opDelta = preset !== "inflection" ? 0.12 : 0.18;
  const bewDelta = 0.20, betaDelta = 0.25;

  const methoden: Record<string, Record<string, number | null>> = {};
  const blend: Record<string, number | null> = {};
  const upside: Record<string, number | null> = {};

  const phase = analysePhase(fund);
  const weights = phaseWeights(fund, preset, WEIGHTS[preset], phase);
  for (const sz of SZENARIEN) {
    const fSz = szenarioFund(fund, sz, gDelta, opDelta, bewDelta, betaDelta);
    let v: FairValueResult | null = null;
    try { v = fairValue(fSz, peerFunds, preset, phase); } catch { v = null; }
    if (!v) { blend[sz] = null; upside[sz] = null; continue; }
    blend[sz] = v.fair_value;
    upside[sz] = v.upside_pct;
    for (const [k, val] of Object.entries(v.methods)) {
      (methoden[k] ??= {})[sz] = val;
    }
  }

  // Methoden ohne Base-Wert entfernen
  const cleaned: Record<string, Record<string, number | null>> = {};
  for (const [k, dd] of Object.entries(methoden)) {
    if (dd.base !== null && dd.base !== undefined) {
      cleaned[k] = { bear: dd.bear ?? null, base: dd.base ?? null, bull: dd.bull ?? null };
    }
  }
  if (blend.base === null || blend.base === undefined) return null;

  const gemeinsam = Object.entries(cleaned)
    .filter(([, dd]) => SZENARIEN.every((sz) => dd[sz] !== null && dd[sz] !== undefined))
    .map(([k]) => k);
  const blendKonsistent: Record<string, number | null> = {};
  if (gemeinsam.length) {
    const wGes = gemeinsam.reduce((s, k) => s + (weights[k] ?? 0.15), 0);
    for (const sz of SZENARIEN) {
      blendKonsistent[sz] = wGes
        ? Math.round((gemeinsam.reduce((s, k) => s + (cleaned[k][sz] ?? 0) * (weights[k] ?? 0.15), 0) / wGes) * 100) / 100
        : null;
    }
  }

  const warnungen: string[] = [];
  if ((blend.bear ?? 0) > (blend.base ?? 0)) {
    warnungen.push("Der Bear-Wert liegt über dem Base-Wert. Ursache ist der Methodenausfall, nicht ein besseres Szenario.");
  }

  return {
    methoden: cleaned, blend, upside,
    blend_konsistent: blendKonsistent, warnungen, preis: price,
  };
}

