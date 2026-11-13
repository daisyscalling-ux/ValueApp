/**
 * scoring.ts - Kategorie-Scores, Composite und Quantum, portiert aus scoring.py
 *
 * score_stock: bewertet je Kennzahl per Perzentil (mit Peers) oder absoluter
 *   Heuristik, buendelt zu 6 Kategorien, gewichtet zum Composite, zieht den
 *   Value-Trap-Malus ab.
 * quantum_score: Meta-Score ueber Qualitaet/Bewertung/Analysten/Momentum mit
 *   Ueberbewertungs- und Value-Trap-Mali.
 *
 * Methode wie immer: 1:1 aus Python, gegen Python-Ausgabe getestet.
 */

import type { Fund } from "./valuation";
import { PEER_PERCENTILE_MIN } from "./peer-valuation";

export type Category = "valuation" | "quality" | "growth" | "health" | "momentum" | "catalyst";

// METRIC_MAP: Kennzahl -> [Kategorie, higher_is_better], exakt aus Python
const METRIC_MAP: Record<string, [Category, boolean]> = {
  ev_ebitda: ["valuation", false],
  pb: ["valuation", false],
  pe_forward: ["valuation", false],
  peg: ["valuation", false],
  fcf_yield: ["valuation", true],
  roe: ["quality", true],
  roa: ["quality", true],
  gross_margin: ["quality", true],
  operating_margin: ["quality", true],
  revenue_growth: ["growth", true],
  earnings_growth: ["growth", true],
  current_ratio: ["health", true],
  net_debt_ebitda: ["health", false],
};

const PATHOLOGICAL_IF_NEGATIVE = new Set(["pe_forward", "peg", "ev_ebitda", "pb"]);

// SCORE_PRESETS, exakt aus config
const SCORE_PRESETS: Record<string, Record<Category, number>> = {
  quality:    { valuation: 0.25, quality: 0.25, growth: 0.20, health: 0.15, momentum: 0.10, catalyst: 0.05 },
  cyclical:   { valuation: 0.30, quality: 0.15, growth: 0.15, health: 0.20, momentum: 0.15, catalyst: 0.05 },
  inflection: { valuation: 0.15, quality: 0.20, growth: 0.35, health: 0.10, momentum: 0.15, catalyst: 0.05 },
  financial:  { valuation: 0.30, quality: 0.30, growth: 0.10, health: 0.10, momentum: 0.15, catalyst: 0.05 },
};
const VALUE_TRAP_PENALTY = 20.0;

const FALLBACK_SCALES: Record<string, [number, number]> = {
  ev_ebitda: [5, 25], pb: [0.5, 6], pe_forward: [8, 40], peg: [0.5, 3],
  fcf_yield: [0.0, 0.12], roe: [0.0, 0.30], roa: [0.0, 0.15],
  gross_margin: [0.1, 0.7], operating_margin: [0.0, 0.35],
  revenue_growth: [-0.1, 0.4], earnings_growth: [-0.1, 0.5],
  current_ratio: [0.5, 3.0], net_debt_ebitda: [0.0, 5.0],
};

function percentileRank(
  value: number | null, peers: (number | null | undefined)[], hib: boolean,
): number {
  const vals = peers.filter((v): v is number => v !== null && v !== undefined);
  if (value === null || !vals.length) return 50.0;
  const below = vals.filter((v) => v < value).length;
  const equal = vals.filter((v) => v === value).length;
  const pct = ((below + 0.5 * equal) / vals.length) * 100;
  return hib ? pct : 100 - pct;
}

function absoluteFallback(metric: string, value: number | null, hib: boolean): number {
  if (value === null || value === undefined) return 50.0;
  const [lo, hi] = FALLBACK_SCALES[metric] ?? [0, 1];
  const x = Math.max(lo, Math.min(hi, value));
  const pct = ((x - lo) / (hi - lo)) * 100;
  return hib ? pct : 100 - pct;
}

function valueTrap(fund: Fund): boolean {
  const revG = fund.revenue_growth;
  const opM = fund.operating_margin;
  const nde = fund.net_debt_ebitda;
  const shrinking = revG !== null && revG !== undefined && revG < 0;
  const weakMargin = opM !== null && opM !== undefined && opM < 0.05;
  const levered = nde !== null && nde !== undefined && nde > 4;
  return !!(shrinking && weakMargin && levered);
}

export interface ScoreResult {
  ticker?: string; name?: string; sector?: string;
  category_scores: Record<string, number>;
  cat_neutral: Record<string, boolean>;
  composite: number;
  value_trap: boolean;
  breakdown: Record<string, number>;
  /** Je Kennzahl: "peers" = Perzentil gegen >= PEER_PERCENTILE_MIN Peers, "scale" = feste Ersatzskala. */
  metric_source: Record<string, "peers" | "scale">;
  peer_count: Record<string, number>;
}

type ScoreFund = Fund & {
  fcf_yield?: number | null; pe_forward?: number | null; peg?: number | null;
  roa?: number | null; "52w_high"?: number | null; "52w_low"?: number | null;
  _catalyst_score?: number | null;
};

export function scoreStock(
  fund: ScoreFund, peerFunds: ScoreFund[] | null, preset: string = "quality",
): ScoreResult {
  const weights = SCORE_PRESETS[preset] ?? SCORE_PRESETS.quality;
  const catValues: Record<string, number[]> = {};
  for (const k of Object.keys(weights)) catValues[k] = [];
  const breakdown: Record<string, number> = {};
  const metricSource: Record<string, "peers" | "scale"> = {};
  const peerCount: Record<string, number> = {};

  for (const [metric, [cat, hib]] of Object.entries(METRIC_MAP)) {
    const val = (fund as Record<string, number | null>)[metric] ?? null;
    let s: number;
    if (PATHOLOGICAL_IF_NEGATIVE.has(metric) && val !== null && val <= 0) {
      s = 0.0;
    } else {
      // Peer-Perzentil nur mit mindestens PEER_PERCENTILE_MIN gueltigen Peer-Werten (negative Multiples sind nicht vergleichbar).
      const peerVals = (peerFunds ?? [])
        .map((p) => (p as Record<string, number | null>)[metric])
        .filter((v): v is number => typeof v === "number" && Number.isFinite(v) && (!PATHOLOGICAL_IF_NEGATIVE.has(metric) || v > 0));
      if (val !== null && peerVals.length >= PEER_PERCENTILE_MIN) {
        s = percentileRank(val, peerVals, hib); metricSource[metric] = "peers";
      } else {
        s = absoluteFallback(metric, val, hib); metricSource[metric] = "scale";
      }
      peerCount[metric] = peerVals.length;
    }
    breakdown[metric] = Math.round(s * 10) / 10;
    catValues[cat].push(s);
  }

  const catScores: Record<string, number> = {};
  const catNeutral: Record<string, boolean> = {};
  for (const cat of Object.keys(weights)) {
    const vals = catValues[cat] ?? [];
    catScores[cat] = vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : 50.0;
    catNeutral[cat] = !vals.length;
  }

  const price = fund.price;
  const hi = fund["52w_high"], lo = fund["52w_low"];
  if (price && hi && lo && hi > lo) {
    let pos = ((price - lo) / (hi - lo)) * 100;
    pos = Math.max(0.0, Math.min(100.0, pos));
    catScores.momentum = pos;
    breakdown.price_position_52w = Math.round(pos * 10) / 10;
  } else {
    catScores.momentum = 50.0;
  }
  if (!("catalyst" in catScores)) catScores.catalyst = fund._catalyst_score ?? 50.0;

  let composite = Object.entries(weights).reduce(
    (s, [c, w]) => s + catScores[c] * w, 0);
  const vt = valueTrap(fund);
  if (vt) composite -= VALUE_TRAP_PENALTY;
  composite = Math.max(0.0, Math.min(100.0, composite));

  const roundCats: Record<string, number> = {};
  for (const [k, v] of Object.entries(catScores)) roundCats[k] = Math.round(v * 10) / 10;

  return {
    ticker: fund.ticker, name: fund.name, sector: fund.sector,
    category_scores: roundCats,
    cat_neutral: catNeutral,
    composite: Math.round(composite * 10) / 10,
    value_trap: vt,
    breakdown,
    metric_source: metricSource,
    peer_count: peerCount,
  };
}

export interface QuantumInput {
  upside_pct?: number | null;
  confidence?: "hoch" | "mittel" | "niedrig" | null;
  spread_pct?: number | null;
}
export interface QuantumAnalyst { buy?: number; hold?: number; sell?: number; }
export interface QuantumResult {
  score: number | null;
  parts: Record<string, number>;
  n: number;
  value_trap_warnung?: string[];
}

export function quantumScore(
  composite: number | null,
  valu: QuantumInput | null,
  analyst: QuantumAnalyst | null = null,
  momentum: number | null = null,
  radar: number | null = null,
  analystSkepsis: number | null = null,
  analystTrend: { richtung?: string; target_delta_pct?: number | null } | null = null,
): QuantumResult {
  const comps: number[] = [], wts: number[] = [];
  const parts: Record<string, number> = {};

  if (composite !== null && composite !== undefined) {
    comps.push(composite); wts.push(0.30);
    parts["Qualit\u00e4t"] = Math.round(composite);
  }

  const up = valu?.upside_pct ?? null;
  if (up !== null && up !== undefined) {
    const conf = valu?.confidence;
    const pull = ({ hoch: 1.0, mittel: 0.75, niedrig: 0.45 } as Record<string, number>)[conf ?? ""] ?? 0.6;
    const qVal = 50.0 + Math.max(Math.min(up, 40.0), -40.0) * 0.8 * pull;
    comps.push(qVal); wts.push(0.40);
    parts["Bewertung"] = Math.round(qVal);
  }

  const a = analyst ?? {};
  const b = a.buy ?? 0, h = a.hold ?? 0, se = a.sell ?? 0;
  const tot = b + h + se;
  if (tot >= 3) {
    const net = (b - se) / tot;
    const qAnl = 50.0 + net * 45.0;
    comps.push(qAnl); wts.push(0.15);
    parts["Analysten"] = Math.round(qAnl);
  }

  let qMom = radar !== null ? radar : momentum;
  if (qMom !== null && qMom !== undefined) {
    qMom = Math.max(0.0, Math.min(100.0, qMom));
    comps.push(qMom); wts.push(0.15);
    parts["Momentum" + (radar !== null ? "/Radar" : "")] = Math.round(qMom);
  }

  if (!comps.length) return { score: null, parts: {}, n: 0 };
  const wsum = wts.reduce((a, b) => a + b, 0);
  let score = comps.reduce((s, c, i) => s + c * wts[i], 0) / wsum;

  // Ueberbewertungs-Malus
  if (up !== null && up < -5) {
    const malus = Math.min((Math.abs(up) - 5) * 0.3, 11.0);
    score -= malus;
    if (malus >= 1) parts["\u00dcberbewertungs-Malus"] = -Math.round(malus);
  }

  // Value-Trap-Mali
  const vtSignale: string[] = [];
  let vtMalus = 0.0;
  const spread = valu?.spread_pct ?? null;
  if (up !== null && up > 80) {
    vtMalus += Math.min((up - 80) * 0.15, 8.0);
    vtSignale.push(`extrem hoher Upside (${up.toFixed(0)} %) - Fair Value pruefen`);
  }
  if (up !== null && up > 25 && momentum !== null && momentum < 40) {
    vtMalus += 5.0;
    vtSignale.push("guenstig, aber fallender Kurs (moegliches fallendes Messer)");
  }
  if (up !== null && up > 40 && spread !== null && spread > 60) {
    vtMalus += 4.0;
    vtSignale.push(`hoher Upside auf unsicherer Bewertungsbasis: Methoden weichen um ${spread.toFixed(0)} % ab`);
  }
  if (analystSkepsis !== null && up !== null && up > 25 && analystSkepsis < -20) {
    vtMalus += 4.0;
    vtSignale.push("Analysten deutlich vorsichtiger als unser Fair Value");
  }
  if (analystTrend && analystTrend.richtung === "fallend") {
    vtMalus += 6.0;
    const d = analystTrend.target_delta_pct;
    let txt = "Analysten SENKEN ihre Kursziele";
    if (d !== null && d !== undefined) txt += ` (${d.toFixed(0)} % seit Beobachtungsbeginn)`;
    vtSignale.push(txt);
  }
  if (vtMalus > 0) {
    vtMalus = Math.min(vtMalus, 12.0);
    score -= vtMalus;
    parts["Value-Trap-Malus"] = -Math.round(vtMalus);
  }

  return {
    score: Math.round(Math.max(0.0, Math.min(100.0, score)) * 10) / 10,
    parts, n: comps.length,
    value_trap_warnung: vtSignale,
  };
}
