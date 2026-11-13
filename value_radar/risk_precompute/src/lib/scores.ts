/**
 * scores.ts - Forensik-Kennzahlen, portiert aus scores.py
 *
 * Piotroski F (Qualitaet), Altman Z (Pleiterisiko), Beneish M (Bilanz-
 * manipulation). Anders als valuation.ts brauchen diese ZEITREIHEN:
 * ein aktuelles Jahr + Vorjahr, als roic-Datensaetze (income+balance+cashflow
 * gemischt).
 *
 * Methode wie immer: 1:1 aus Python, gegen Python-Ausgabe getestet.
 */

export type Row = Record<string, unknown>;

function num(x: unknown): number | null {
  const f = typeof x === "number" ? x : parseFloat(x as string);
  return Number.isFinite(f) ? f : null;
}

/** Erstes vorhandenes Feld aus einem roic-Datensatz. */
function g(d: Row | null | undefined, ...keys: string[]): unknown {
  if (!d || typeof d !== "object") return null;
  for (const k of keys) {
    const v = (d as Row)[k];
    if (v !== null && v !== undefined) return v;
  }
  return null;
}

// roic-Feldnamen, exakt aus scores.py
const F_NETINCOME = ["is_net_income", "is_earn_for_common"];
const F_REVENUE = ["is_sales_revenue_turnover", "is_sales_and_services_revenues"];
const F_GROSSPROFIT = ["is_gross_profit"];
const F_SGA = ["is_sg_and_a_expense", "is_operating_expn"];
const F_DEPR = ["cf_depr_amort", "is_depr_exp"];
const F_OPCF = ["cf_cash_from_oper", "ttm_cash_from_oper"];
const F_ASSETS = ["bs_tot_asset", "bs_total_assets"];
const F_CURASSETS = ["bs_cur_asset_report", "bs_total_current_assets"];
const F_CURLIAB = ["bs_cur_liab", "bs_total_current_liabilities"];
const F_LTDEBT = ["bs_lt_borrow", "bs_long_term_borrowings"];
const F_TOTLIAB = ["bs_tot_liab"];
const F_SHARES = ["is_sh_for_diluted_eps", "bs_sh_out"];
const F_RECEIV = ["bs_accounts_receivable", "bs_acct_note_rcv"];
const F_RETEARN = ["bs_retain_earnings", "bs_pure_retained_earnings"];
const F_EBIT = ["is_oper_income"];
const F_MKTCAP = ["market_cap"];

export function istFinanzwert(
  sektor: string | null | undefined, fund?: Row | null,
): boolean {
  const s = (sektor ?? "").toLowerCase();
  if (["financ", "bank", "insur", "reit", "versicher"].some((k) => s.includes(k)))
    return true;
  if (fund && (fund as Row)._ist_bank) return true;
  return false;
}

// --- Piotroski F (0-9) -----------------------------------------------------
export interface PiotroskiResult {
  score: number; max: number;
  details: Record<string, number>;
  stark: boolean; schwach: boolean;
}

export function piotroskiF(
  akt: Row, vorjahr: Row, sektor?: string | null, fund?: Row | null,
): PiotroskiResult | null {
  if (istFinanzwert(sektor, fund)) return null;
  if (!akt || typeof akt !== "object" || !vorjahr || typeof vorjahr !== "object")
    return null;

  const ni = num(g(akt, ...F_NETINCOME));
  const rev = num(g(akt, ...F_REVENUE));
  const assets = num(g(akt, ...F_ASSETS));
  const opcf = num(g(akt, ...F_OPCF));
  const gross = num(g(akt, ...F_GROSSPROFIT));
  const curA = num(g(akt, ...F_CURASSETS));
  const curL = num(g(akt, ...F_CURLIAB));
  const ltdebt = num(g(akt, ...F_LTDEBT)) ?? 0.0;
  const shares = num(g(akt, ...F_SHARES));

  const niV = num(g(vorjahr, ...F_NETINCOME));
  const revV = num(g(vorjahr, ...F_REVENUE));
  const assetsV = num(g(vorjahr, ...F_ASSETS));
  const grossV = num(g(vorjahr, ...F_GROSSPROFIT));
  const curAV = num(g(vorjahr, ...F_CURASSETS));
  const curLV = num(g(vorjahr, ...F_CURLIAB));
  const ltdebtV = num(g(vorjahr, ...F_LTDEBT)) ?? 0.0;
  const sharesV = num(g(vorjahr, ...F_SHARES));

  if ([ni, assets, opcf, rev].some((x) => x === null)) return null;
  if ([assetsV, revV].some((x) => x === null)) return null;
  if (assets! <= 0 || assetsV! <= 0) return null;

  const roa = ni! / assets!;
  const roaV = niV !== null && assetsV ? niV / assetsV : null;

  const d: Record<string, number> = {};
  d.ni_positiv = ni! > 0 ? 1 : 0;
  d.opcf_positiv = opcf! > 0 ? 1 : 0;
  d.roa_steigt = roaV !== null && roa > roaV ? 1 : 0;
  d.accruals = opcf! / assets! > roa ? 1 : 0;

  const lev = assets ? ltdebt / assets! : null;
  const levV = assetsV ? ltdebtV / assetsV : null;
  d.leverage_faellt = lev !== null && levV !== null && lev < levV ? 1 : 0;
  const cr = curA && curL && curL > 0 ? curA / curL : null;
  const crV = curAV && curLV && curLV > 0 ? curAV / curLV : null;
  d.current_ratio_steigt = cr !== null && crV !== null && cr > crV ? 1 : 0;
  d.keine_neuen_aktien =
    shares !== null && sharesV !== null && shares <= sharesV * 1.01 ? 1 : 0;

  const gm = gross && rev && rev > 0 ? gross / rev : null;
  const gmV = grossV && revV && revV > 0 ? grossV / revV : null;
  d.bruttomarge_steigt = gm !== null && gmV !== null && gm > gmV ? 1 : 0;
  const at = rev! / assets!;
  const atV = revV! / assetsV!;
  d.asset_turnover_steigt = at > atV ? 1 : 0;

  const score = Object.values(d).reduce((s, x) => s + x, 0);
  return { score, max: 9, details: d, stark: score >= 7, schwach: score <= 3 };
}

// --- Altman Z --------------------------------------------------------------
export interface AltmanResult { z: number; zone: string; gefahr: boolean; }

export function altmanZ(
  akt: Row, sektor?: string | null, fund?: Row | null,
): AltmanResult | null {
  if (istFinanzwert(sektor, fund)) return null;
  const assets = num(g(akt, ...F_ASSETS));
  if (!assets || assets <= 0) return null;
  const curA = num(g(akt, ...F_CURASSETS));
  const curL = num(g(akt, ...F_CURLIAB));
  const retEarn = num(g(akt, ...F_RETEARN));
  const ebit = num(g(akt, ...F_EBIT));
  const rev = num(g(akt, ...F_REVENUE));
  const totLiab = num(g(akt, ...F_TOTLIAB));
  let mktcap: number | null = null;
  if (fund) mktcap = num((fund as Row).market_cap);
  if (mktcap === null) mktcap = num(g(akt, ...F_MKTCAP));

  if ([curA, curL, retEarn, ebit, rev, totLiab, mktcap].some((x) => x === null))
    return null;
  if (totLiab! <= 0) return null;

  const wc = curA! - curL!;
  const x1 = wc / assets;
  const x2 = retEarn! / assets;
  const x3 = ebit! / assets;
  const x4 = mktcap! / totLiab!;
  const x5 = rev! / assets;
  const z = 1.2 * x1 + 1.4 * x2 + 3.3 * x3 + 0.6 * x4 + 1.0 * x5;

  const zone = z > 2.99 ? "sicher" : z >= 1.81 ? "grau" : "gefahr";
  return { z: Math.round(z * 100) / 100, zone, gefahr: z < 1.81 };
}

// --- Beneish M -------------------------------------------------------------
export interface BeneishResult {
  m: number;
  teile: Record<string, number>;
  treiber: string[];
  wachstumsgetrieben: boolean;
  tata_unauffaellig: boolean;
  verdaechtig: boolean;
  verdaechtig_streng: boolean;
  schwelle_warnung: number;
  schwelle_streng: number;
}

export function beneishM(
  akt: Row, vorjahr: Row, sektor?: string | null, fund?: Row | null,
): BeneishResult | null {
  if (istFinanzwert(sektor, fund)) return null;
  const rev = num(g(akt, ...F_REVENUE)), revV = num(g(vorjahr, ...F_REVENUE));
  const recv = num(g(akt, ...F_RECEIV)), recvV = num(g(vorjahr, ...F_RECEIV));
  const gross = num(g(akt, ...F_GROSSPROFIT));
  const grossV = num(g(vorjahr, ...F_GROSSPROFIT));
  const assets = num(g(akt, ...F_ASSETS)), assetsV = num(g(vorjahr, ...F_ASSETS));
  const curA = num(g(akt, ...F_CURASSETS)), curAV = num(g(vorjahr, ...F_CURASSETS));
  const ppe = num(g(akt, "bs_net_fix_asset", "bs_gross_fix_asset"));
  const ppeV = num(g(vorjahr, "bs_net_fix_asset", "bs_gross_fix_asset"));
  const depr = num(g(akt, ...F_DEPR)), deprV = num(g(vorjahr, ...F_DEPR));
  const sga = num(g(akt, ...F_SGA)), sgaV = num(g(vorjahr, ...F_SGA));
  const ni = num(g(akt, ...F_NETINCOME));
  const opcf = num(g(akt, ...F_OPCF));
  const totLiab = num(g(akt, ...F_TOTLIAB));
  const totLiabV = num(g(vorjahr, ...F_TOTLIAB));

  if ([rev, revV, gross, grossV, assets, assetsV].some((x) => x === null))
    return null;
  if (revV === 0 || assets === 0 || assetsV === 0 || rev === 0) return null;

  const dsri = recv && recvV && rev && revV
    ? (recv / rev!) / (recvV / revV!) : 1.0;
  const gm = gross! / rev!, gmV = grossV! / revV!;
  const gmi = gm ? gmV / gm : 1.0;
  const aqi = curA !== null && ppe !== null && curAV !== null && ppeV !== null
    ? (1 - (curA + ppe) / assets!) / (1 - (curAV + ppeV) / assetsV!) : 1.0;
  const sgi = rev! / revV!;
  let depi = 1.0;
  if (depr && deprV && ppe && ppeV) {
    const dr = depr / (depr + ppe), drV = deprV / (deprV + ppeV);
    depi = dr ? drV / dr : 1.0;
  }
  const sgai = sga && sgaV && rev && revV
    ? (sga / rev!) / (sgaV / revV!) : 1.0;
  const lvgi = totLiab && totLiabV
    ? (totLiab / assets!) / (totLiabV / assetsV!) : 1.0;
  const tata = ni !== null && opcf !== null ? (ni - opcf) / assets! : 0.0;

  const m = -4.84 + 0.92 * dsri + 0.528 * gmi + 0.404 * aqi + 0.892 * sgi
    + 0.115 * depi - 0.172 * sgai + 4.679 * tata - 0.327 * lvgi;

  const r3 = (x: number) => Math.round(x * 1000) / 1000;
  const teile: Record<string, number> = {
    DSRI: r3(dsri), GMI: r3(gmi), AQI: r3(aqi), SGI: r3(sgi),
    DEPI: r3(depi), SGAI: r3(sgai), LVGI: r3(lvgi),
    TATA: Math.round(tata * 10000) / 10000,
  };
  const beitrag: Record<string, number> = {
    DSRI: 0.92 * dsri, GMI: 0.528 * gmi, AQI: 0.404 * aqi,
    SGI: 0.892 * sgi, DEPI: 0.115 * depi, SGAI: -0.172 * sgai,
    TATA: 4.679 * tata, LVGI: -0.327 * lvgi,
  };
  const treiber = Object.entries(beitrag)
    .filter(([k]) => (teile[k] ?? 1) > 1.05)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 3)
    .map(([k]) => k);
  const maxKey = Object.entries(beitrag).reduce((a, b) => (b[1] > a[1] ? b : a))[0];

  return {
    m: Math.round(m * 100) / 100,
    teile, treiber,
    wachstumsgetrieben: tata < 0.03 && ["SGI", "DEPI", "AQI"].includes(maxKey) && sgi > 1.15,
    tata_unauffaellig: tata < 0.03,
    verdaechtig: m > -2.22,
    verdaechtig_streng: m > -1.78,
    schwelle_warnung: -2.22,
    schwelle_streng: -1.78,
  };
}
