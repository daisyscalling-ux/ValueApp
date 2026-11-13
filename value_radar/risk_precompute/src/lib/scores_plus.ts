/**
 * scores_plus.ts - Verbesserte Bilanz-, Momentum- und Katalysator-Scores.
 *
 * Der scoreStock-Kern (scoring.ts) bleibt unangetastet (bitgenau gegen Python).
 * Diese Schicht ueberschreibt NUR die drei schwachen Kategorien mit den
 * reicheren Daten, die inzwischen im fund stecken (Finanzlage, Analysten,
 * Earnings-Surprise, 3-Jahres-Reihen).
 *
 * - BILANZ: statt 2 jetzt bis zu 7 Kennzahlen (Verschuldung, Liquiditaet,
 *   Kapitalrendite, Cashflow-Deckung, Altman Z).
 * - MOMENTUM: Position im 52W-Band, aber mit Ueberhitzungs-Daempfung nahe Hoch.
 * - KATALYSATOR: endlich echte Signale (Analysten, Surprise, Beschleunigung)
 *   statt konstant 50 - und ehrlich null, wenn gar keine Signale da sind.
 */

export interface ScorePlus {
  health: number | null;
  momentum: number | null;
  catalyst: number | null;
  health_teile: [string, number][];     // fuer Transparenz
  catalyst_teile: [string, number][];
}

type Fund = Record<string, unknown>;
const z = (x: unknown): number | null => {
  const n = Number(x);
  return isFinite(n) ? n : null;
};

/** Stufenbewertung: Wert -> 0..100 nach Schwellen. */
function stufe(v: number | null, schwellen: [number, number][], hoch: boolean): number | null {
  if (v === null) return null;
  // schwellen: [grenze, punkte], absteigend nach punkte. hoch=true: groesser ist besser.
  for (const [g, p] of schwellen) {
    if (hoch ? v >= g : v <= g) return p;
  }
  return hoch ? 10 : 10;
}

export function scoresPlus(fund: Fund, altmanZ: number | null): ScorePlus {
  const fl = (fund._finanzlage as Record<string, number | null>) ?? {};

  // ---------------------------------------------------------------------------
  // BILANZ (health) - bis zu 7 Kennzahlen, Mittel der verfuegbaren
  // ---------------------------------------------------------------------------
  const hTeile: [string, number][] = [];
  const nde = z(fund.net_debt_ebitda);
  const ndeScore = stufe(nde, [[0, 100], [1, 90], [2, 75], [3, 50], [4, 25], [999, 5]], false);
  if (ndeScore !== null) hTeile.push(["Nettoverschuldung", ndeScore]);

  const cr = z(fund.current_ratio);
  const crScore = stufe(cr, [[2, 100], [1.5, 85], [1.2, 70], [1, 50], [0.5, 25], [0, 10]], true);
  if (crScore !== null) hTeile.push(["Current Ratio", crScore]);

  const de = z(fl.debt_to_equity);
  const deScore = stufe(de, [[0.3, 100], [0.5, 85], [1, 65], [2, 40], [3, 20], [999, 5]], false);
  if (deScore !== null) hTeile.push(["Verschuldungsgrad", deScore]);

  const roic = z(fl.roic);
  const roicScore = stufe(roic, [[0.15, 100], [0.12, 85], [0.08, 65], [0.05, 45], [0, 25], [-1, 5]], true);
  if (roicScore !== null) hTeile.push(["Kapitalrendite", roicScore]);

  const cfl = z(fl.cf_to_liab);
  const cflScore = stufe(cfl, [[0.5, 100], [0.3, 80], [0.2, 60], [0.1, 40], [0, 20], [-1, 5]], true);
  if (cflScore !== null) hTeile.push(["Cashflow-Deckung", cflScore]);

  const azScore = stufe(altmanZ, [[3, 100], [2.5, 80], [1.8, 55], [1, 30], [0, 15], [-99, 5]], true);
  if (azScore !== null) hTeile.push(["Altman Z", azScore]);

  const cashR = z(fl.cash_ratio);
  const cashScore = stufe(cashR, [[1, 100], [0.5, 80], [0.2, 55], [0.1, 35], [0, 20], [-1, 5]], true);
  if (cashScore !== null) hTeile.push(["Cash Ratio", cashScore]);

  const health = hTeile.length
    ? Math.round(hTeile.reduce((s, t) => s + t[1], 0) / hTeile.length * 10) / 10
    : null;

  // ---------------------------------------------------------------------------
  // MOMENTUM - Position im 52W-Band mit Ueberhitzungs-Daempfung
  // ---------------------------------------------------------------------------
  let momentum: number | null = null;
  const price = z(fund.price), hi = z(fund["52w_high"]), lo = z(fund["52w_low"]);
  if (price && hi && lo && hi > lo) {
    const pos = Math.max(0, Math.min(1, (price - lo) / (hi - lo)));  // 0..1
    // Gesunder Aufwaertstrend (Mitte-oben) wird belohnt, Extreme gedaempft:
    // nahe Tief (0-0.2)   -> schwach: 15..40
    // Aufbau    (0.2-0.5) -> 40..70
    // stark     (0.5-0.85)-> 70..92  (bester Bereich)
    // Hoch      (0.85-1)  -> 92 runter auf 72 (Ueberhitzung)
    let m: number;
    if (pos < 0.2) m = 15 + (pos / 0.2) * 25;
    else if (pos < 0.5) m = 40 + ((pos - 0.2) / 0.3) * 30;
    else if (pos < 0.85) m = 70 + ((pos - 0.5) / 0.35) * 22;
    else m = 92 - ((pos - 0.85) / 0.15) * 20;   // Ueberhitzung daempft
    momentum = Math.round(m * 10) / 10;
  }

  // ---------------------------------------------------------------------------
  // KATALYSATOR - echte Signale statt konstant 50
  // ---------------------------------------------------------------------------
  const cTeile: [string, number][] = [];

  // (1) Analystenempfehlungen: buy vs sell
  const buy = z(fund.analyst_buy), hold = z(fund.analyst_hold), sell = z(fund.analyst_sell);
  if (buy !== null && (buy + (hold ?? 0) + (sell ?? 0)) >= 3) {
    const ges = buy + (hold ?? 0) + (sell ?? 0);
    const richtung = (buy - (sell ?? 0)) / ges;   // -1..+1
    cTeile.push(["Analystenvotum", Math.round((50 + richtung * 50) * 10) / 10]);
  }

  // (2) Earnings-Surprise: schlaegt die Firma ihre Schaetzungen?
  const beat = z(fund.surprise_beat_quote), med = z(fund.surprise_median);
  if (beat !== null && med !== null) {
    // beat 0..1 (Quote) + Richtung des Median-Surprise
    const s = Math.max(0, Math.min(100, beat * 70 + (med > 0 ? 30 : med < -2 ? 0 : 15)));
    cTeile.push(["Earnings-Surprise", Math.round(s * 10) / 10]);
  }

  // (3) Gewinnbeschleunigung aus 3-Jahres-EBITDA-Reihe
  const reihe = fund.reihe_ebitda as { wert: number | null }[] | undefined;
  if (reihe && reihe.length >= 3) {
    const w = reihe.map((r) => r.wert ?? 0);
    if (w[0] && w[1]) {
      const g1 = w[1] / w[0] - 1, g2 = w[2] / w[1] - 1;
      // beschleunigt -> hoch, verlangsamt -> tief
      const delta = g2 - g1;
      const s = Math.max(0, Math.min(100, 50 + delta * 300));
      cTeile.push(["Gewinntrend", Math.round(s * 10) / 10]);
    }
  }

  // (4) Umsatzwachstum als Basissignal
  const rg = z(fund.revenue_growth);
  if (rg !== null) {
    const s = Math.max(0, Math.min(100, 30 + rg * 200));  // 15% Wachstum -> 60
    cTeile.push(["Umsatzdynamik", Math.round(s * 10) / 10]);
  }

  // Katalysator: Mittel der Signale, oder null wenn gar keine da
  const catalyst = cTeile.length
    ? Math.round(cTeile.reduce((s, t) => s + t[1], 0) / cTeile.length * 10) / 10
    : null;

  return { health, momentum, catalyst, health_teile: hTeile, catalyst_teile: cTeile };
}
