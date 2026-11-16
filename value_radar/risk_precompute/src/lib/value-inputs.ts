/**
 * value-inputs.ts - Forward-KGV, PEG und FCF-Rendite für die Kategorie Bewertung (seit 17.11.2026, Entscheidung des Nutzers).
 *
 * Vorher rechnete die Einzelanalyse diese drei Kennzahlen nie aus (sie zählten neutral mit 50), der Screener nahm Yahoo
 * forwardPE/pegRatio und die ROIC-FCF-Rendite. Jetzt rechnen beide Wege dieselbe Funktion aus denselben geprüften Feldern:
 *
 *  - pe_forward = Kurs / geprüftes 12M-Prognose-EPS (eps_forward mit FORWARD_METHOD aus applyForwardEstimate).
 *  - peg        = pe_forward / erwartetes EPS-Wachstum in % (Prognose-EPS gegenüber berichtetem EPS, gleiche Basis geprüft).
 *  - fcf_yield  = freier Cashflow des Unternehmens (FCFF, ROIC ttm_free_cash_flow_firm) / Unternehmenswert
 *                 (Börsenwert + Nettoschulden). FCFF ist der Cashflow vor Zinsen; geteilt durch den Börsenwert würde er
 *                 verschuldete Firmen systematisch billig erscheinen lassen.
 *
 * Fehlt ein Eingang, bleibt die Kennzahl offen und nennt den Grund (zählt nicht in die Kategorie, siehe scoring.ts).
 * Gegen Verzerrung (Grundsatz 8): Erwartet der geprüfte Konsens keinen Gewinn, erhalten Forward-KGV und PEG die schlechteste
 * Note; erwartet er positiven, aber nicht wachsenden Gewinn, erhält PEG die schlechteste Note. Sonst stünden Verlust- und
 * Schrumpffirmen durch die fehlende Kennzahl besser da als Firmen mit hohem, aber positivem KGV.
 *
 * Identische Kopie unter ValueApp/value_radar/risk_precompute/src/lib.
 */
import {FORWARD_METHOD} from './fundamental-supplement';

export const VALUE_INPUTS_METHOD = 'value_inputs_v1';
export type ValueMetric = 'pe_forward' | 'peg' | 'fcf_yield';
export interface ValueInputs {
  method: typeof VALUE_INPUTS_METHOD;
  pe_forward: number | null;
  peg: number | null;
  fcf_yield: number | null;
  /** Offen: zählt nicht in die Kategorie. */
  open: Partial<Record<ValueMetric, string>>;
  /** Schlechteste Note (0) mit Grund, ohne Zahlenwert. */
  worst: Partial<Record<ValueMetric, string>>;
}
type Row = Record<string, any>;
const pos = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v) && v > 0;
const fin = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v);

export function valueInputs(f: Row): ValueInputs {
  const out: ValueInputs = {method: VALUE_INPUTS_METHOD, pe_forward: null, peg: null, fcf_yield: null, open: {}, worst: {}};
  const price = f.price, epsF = f.eps_forward, epsT = f.eps_trailing;
  const verified = f.eps_forward_method === FORWARD_METHOD && pos(epsF);

  if (!pos(price)) {
    out.open.pe_forward = 'Kurs fehlt';
    out.open.peg = 'Kurs fehlt';
  } else if (f.eps_forward_no_profit === true) {
    out.worst.pe_forward = 'Geprüfter Konsens erwartet keinen Gewinn';
    out.worst.peg = 'Geprüfter Konsens erwartet keinen Gewinn';
  } else if (!verified) {
    const why = 'Kein geprüftes Prognose-EPS' + (typeof f.eps_forward_status === 'string' && f.eps_forward_status ? ': ' + f.eps_forward_status : '');
    out.open.pe_forward = why;
    out.open.peg = why;
  } else {
    out.pe_forward = price / epsF;
    if (!pos(epsT)) out.open.peg = 'Berichtetes EPS fehlt oder ≤ 0';
    else {
      const growthPct = (epsF / epsT - 1) * 100;
      if (growthPct <= 0) out.worst.peg = 'Kein erwartetes Gewinnwachstum (Prognose-EPS ≤ berichtetes EPS)';
      else out.peg = out.pe_forward / growthPct;
    }
  }

  const fcf = f.free_cashflow, mc = f.market_cap, nd = f.net_debt;
  if (typeof f.report_fx_status === 'string' && f.report_fx_status) out.open.fcf_yield = 'Abschlusswährung nicht umgerechnet';
  else if (!fin(fcf)) out.open.fcf_yield = 'Freier Cashflow fehlt';
  else if (!pos(mc)) out.open.fcf_yield = 'Börsenwert fehlt';
  else if (!fin(nd)) out.open.fcf_yield = 'Nettoschulden fehlen (Unternehmenswert nicht bestimmbar)';
  else if (!(mc + nd > 0)) out.open.fcf_yield = 'Unternehmenswert ≤ 0 (Nettokasse größer als Börsenwert)';
  else out.fcf_yield = fcf / (mc + nd);
  return out;
}

/** Setzt die drei Kennzahlen auf dem Fund und überschreibt mitgelieferte Fremdwerte (Yahoo forwardPE/pegRatio, ROIC-Rendite). */
export function applyValueInputs(f: Row): ValueInputs {
  const v = valueInputs(f);
  f.pe_forward = v.pe_forward; f.peg = v.peg; f.fcf_yield = v.fcf_yield;
  f.value_inputs = v;
  return v;
}
