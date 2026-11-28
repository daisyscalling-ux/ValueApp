// Ein Stand für alle (seit 28.11.2026, Entscheidung des Nutzers): Einzelanalyse und Portfolio zeigen Fair Value, Einstieg,
// 12M-Ziel und die Methodenaufschlüsselung aus dem letzten Scannerlauf (cf_universum.json), damit Startseite, Scanner und
// Einzelanalyse dieselben Zahlen zeigen. Vorher rechnete die Einzelanalyse live mit anderen Eingängen (Kurs, Konsens zur
// Abrufzeit); an der Faktor-2-Grenze des Median-Kerns kippte dadurch die Methodenauswahl (Socionext 28.11.: Scanner
// 1.463 JPY, Einzelanalyse rund 1.130 JPY). Live bleiben Kurs, Abstand zum Kurs, Scores und die übrigen Diagnosen.
// Die Scannerzeile wird beim Lesen erneut geprüft: Methode, Notierung, ISIN, Währung, Alter, Wertebereiche und Nachrechnung
// des Fair Value aus den Kernmethoden. Scheitert eine Prüfung, rechnet die App live und nennt den Grund.
import type {FairValueResult, Kursziel12m} from './valuation';

export const SCANNER_STAND_METHOD = 'ts-evaluate-v1';
/** Höchstalter des Scannerlaufs (Abruf ≤ 36 h, wie die übrigen Tagesquellen). */
export const SCANNER_STAND_MAX_ALTER_H = 36;
/** Nachrechnung Fair Value aus Kernmethoden × Gewichten: Kernwerte sind auf Cent gerundet, der Deckel nutzt den Kurs zur
 *  Rechenzeit. Gemessen 28.11.2026: 1.298 von 1.325 Titeln ≤ 0,1 %, größte Abweichung 1,5 % (DDOG, gedeckelt). */
export const SCANNER_FV_TOLERANZ = 0.02;
const DECKEL_MIN = 0.3, DECKEL_MAX = 3.0, STANDARD_GEWICHT = 0.15;
const URTEILE = new Set(['kauf', 'beobachten', 'meiden']);

type Row = Record<string, any>;
export interface ScannerStand {
  fair_value: number; entry: number; price: number; target_12m: number | null;
  core: Record<string, number>; values: Record<string, number>; weights: Record<string, number>;
  confidence: 'hoch' | 'mittel' | 'niedrig'; reliable: boolean; fallback: boolean;
  ziel_teile: {fundamental: number | null; analyst: number | null; momentum: number | null; eps: number | null; kgv: number | null} | null;
  kauf_urteil: string; zeit: string;
}
export type StandHerkunft = {quelle: 'scanner'; zeit: string} | {quelle: 'live'; grund: string};

const zahl = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v);
const positiv = (v: unknown): v is number => zahl(v) && v > 0;
const r2 = (v: number) => Math.round(v * 100) / 100;

/** "2026-11-28 05:16 UTC" (export_observed_at) als Zeitpunkt; sonst null. */
export function scannerZeit(s: unknown): number | null {
  if (typeof s !== 'string') return null;
  const m = /^(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2})(?::\d{2})?(?: ?UTC|Z|\+00:00)$/.exec(s.trim());
  if (!m) return null;
  const t = Date.parse(`${m[1]}T${m[2]}:00Z`);
  return Number.isFinite(t) ? t : null;
}

function zahlenMap(v: unknown, erlaubtNull = false): Record<string, number> | null {
  if (!v || typeof v !== 'object' || Array.isArray(v)) return null;
  const out: Record<string, number> = {};
  for (const [k, x] of Object.entries(v as Row)) {
    if (erlaubtNull ? !(zahl(x) && x >= 0) : !positiv(x)) return null;
    out[k] = x as number;
  }
  return out;
}

/** Prüft die Scannerzeile gegen die Notierung der Einzelanalyse. fund: Ticker (Notierung), ISIN und Handelswährung vor der
 *  Euro-Umrechnung. Ergebnis: geprüfter Stand oder ein konkreter Grund, warum live gerechnet wird. */
export function pruefeScannerStand(row: Row | null | undefined, fund: {ticker?: unknown; isin?: unknown; currency?: unknown},
  now = Date.now()): {stand: ScannerStand | null; grund: string | null} {
  const nein = (grund: string) => ({stand: null, grund});
  if (!row || typeof row !== 'object' || !Object.keys(row).length) return nein('Keine Scannerzeile für diese Notierung');
  if (!('fair_value' in row) || !('scanner_method' in row)) return nein('Scannerzeile ohne Bewertungsfelder');
  if (row.scanner_method !== SCANNER_STAND_METHOD) return nein('Scannerzeile mit unbekannter Methode');
  const sym = String(fund.ticker ?? '').toUpperCase();
  if (!sym || String(row.listing_symbol ?? '').toUpperCase() !== sym) return nein('Scannerzeile gehört zu einer anderen Notierung');
  const isinA = String(row.isin ?? '').toUpperCase(), isinB = String(fund.isin ?? '').toUpperCase();
  if (isinA && isinB && isinA !== isinB) return nein('ISIN der Scannerzeile weicht ab');
  if (!row.currency || String(row.currency).toUpperCase() !== String(fund.currency ?? '').toUpperCase()) return nein('Währung der Scannerzeile weicht ab');
  const t = scannerZeit(row.export_observed_at);
  if (t === null) return nein('Scannerzeile ohne Zeitstempel');
  if (t > now + 3600_000) return nein('Zeitstempel der Scannerzeile liegt in der Zukunft');
  if (now - t > SCANNER_STAND_MAX_ALTER_H * 3600_000) return nein(`Scannerlauf älter als ${SCANNER_STAND_MAX_ALTER_H} h (${row.export_observed_at})`);
  const {fair_value: fv, entry, price} = row;
  if (!positiv(fv) || !positiv(price)) return nein('Scannerzeile ohne Fair Value');
  if (!positiv(entry) || entry > fv) return nein('Einstieg der Scannerzeile außerhalb des Bereichs');
  if (row.target_12m !== null && row.target_12m !== undefined && !positiv(row.target_12m)) return nein('12M-Ziel der Scannerzeile außerhalb des Bereichs');
  if (!URTEILE.has(row.kauf_urteil)) return nein('Urteil der Scannerzeile unbekannt');
  const diag = row.score_diagnostics ?? {};
  const fm = diag.fv_methods, check = diag.fv_check;
  const core = zahlenMap(fm?.core), values = zahlenMap(fm?.values), weights = zahlenMap(fm?.weights, true);
  if (!core || !values || !weights || !Object.keys(core).length) return nein('Methodenaufschlüsselung der Scannerzeile fehlt oder ist ungültig');
  for (const k of Object.keys(core)) if (k !== 'fallback' && !(k in values)) return nein(`Kernmethode ${k} ohne Rohwert`);
  if (!check || !['hoch', 'mittel', 'niedrig'].includes(check.confidence) || typeof check.reliable !== 'boolean' || typeof check.fallback !== 'boolean')
    return nein('Verlässlichkeit der Scannerzeile fehlt');
  // Doppelte Prüfung: Fair Value aus Kernmethoden und Gewichten nachrechnen (gleicher Schnitt und Deckel wie fairValue).
  const ks = Object.keys(core), wsum = ks.reduce((s, k) => s + (weights[k] ?? STANDARD_GEWICHT), 0);
  if (!(wsum > 0)) return nein('Gewichte der Scannerzeile ergeben null');
  let nach = ks.reduce((s, k) => s + core[k] * (weights[k] ?? STANDARD_GEWICHT), 0) / wsum;
  nach = Math.min(Math.max(nach, DECKEL_MIN * price), DECKEL_MAX * price);
  if (Math.abs(nach / fv - 1) > SCANNER_FV_TOLERANZ && Math.abs(nach - fv) > 0.01)
    return nein(`Fair Value der Scannerzeile lässt sich nicht nachrechnen (${r2(fv)} gegen ${r2(nach)})`);
  const tg = diag.target, opt = (v: unknown) => (positiv(v) ? v : null);
  return {grund: null, stand: {
    fair_value: fv, entry, price, target_12m: positiv(row.target_12m) ? row.target_12m : null, core, values, weights,
    confidence: check.confidence, reliable: check.reliable, fallback: check.fallback,
    ziel_teile: tg && typeof tg === 'object' ? {fundamental: opt(tg.fundamental), analyst: opt(tg.analyst), momentum: opt(tg.momentum), eps: opt(tg.eps), kgv: opt(tg.kgv)} : null,
    kauf_urteil: row.kauf_urteil, zeit: String(row.export_observed_at),
  }};
}

/** Fair Value der Anzeige aus dem geprüften Scannerstand. faktor: Umrechnung Handelswährung → Anzeigewährung (1 ohne
 *  Umrechnung); preis: aktueller Kurs in der Anzeigewährung (Abstand zum Kurs bleibt live). herkunft: Methode → Herkunft. */
export function fvAusScannerStand(live: FairValueResult, s: ScannerStand, faktor: number, preis: number | null,
  herkunft: Record<string, string>): FairValueResult {
  const sk = (v: number) => r2(v * faktor);
  const map = (m: Record<string, number>) => Object.fromEntries(Object.entries(m).map(([k, v]) => [k, sk(v)]));
  const fv = sk(s.fair_value), entry = sk(s.entry), core = map(s.core);
  const vals = Object.values(core), lo = Math.min(...vals), hi = Math.max(...vals);
  const sortiert = [...vals].sort((a, b) => a - b), mitte = sortiert.length / 2;
  const med = sortiert.length % 2 ? sortiert[Math.floor(mitte)] : (sortiert[mitte - 1] + sortiert[mitte]) / 2;
  const verworfen: FairValueResult['verworfen'] = {};
  for (const [k, v] of Object.entries(s.values)) if (!(k in s.core)) verworfen[k] = {
    wert: sk(v), vs_kurs: Math.round((v / s.price - 1) * 1000) / 10,
    grund: 'nicht im Kern des Scannerlaufs (außerhalb des Kursbands oder mehr als Faktor 2 vom Median)',
  };
  const wsum = Object.keys(s.core).reduce((x, k) => x + (s.weights[k] ?? STANDARD_GEWICHT), 0);
  const nachHerkunft: Record<string, number> = {};
  for (const [k, v] of Object.entries(core)) {
    const h = herkunft[k] ?? 'unbekannt';
    nachHerkunft[h] = (nachHerkunft[h] ?? 0) + v * (s.weights[k] ?? STANDARD_GEWICHT) / wsum / fv;
  }
  const naechste = Object.entries(core).sort((a, b) => Math.abs(a[1] - fv) - Math.abs(b[1] - fv)).slice(0, 3);
  const capped = Math.abs(s.fair_value / (DECKEL_MIN * s.price) - 1) < 0.005 || Math.abs(s.fair_value / (DECKEL_MAX * s.price) - 1) < 0.005;
  return {
    ...live,
    method_weights: {...s.weights}, core_methods: core, used_fallback: s.fallback,
    fair_value: fv, entry_price: entry,
    target_12m: live.target_12m && live.fair_value ? r2(live.target_12m * fv / live.fair_value) : live.target_12m,
    upside_pct: preis && preis > 0 ? Math.round((fv / preis - 1) * 1000) / 10 : null,
    methods: Object.fromEntries(naechste), method_values: map(s.values), verworfen,
    confidence: s.confidence, reliable: s.reliable,
    spread_pct: med ? Math.round((hi - lo) / med * 100) : null, n_methods: naechste.length,
    capped, margin_of_safety: Math.round((1 - s.entry / s.fair_value) * 1000) / 1000, nach_herkunft: nachHerkunft,
  };
}

/** 12M-Ziel der Anzeige aus dem Scannerstand; Spanne im selben Verhältnis verschoben, Konfidenz bleibt die Live-Regel.
 *  Ohne Scannerziel bleibt das Live-Ziel (gekennzeichnet in der Herleitung). */
export function zielAusScannerStand(live: Kursziel12m | null, s: ScannerStand, faktor: number, preis: number | null): Kursziel12m | null {
  if (!live) return live;
  if (s.target_12m === null) return {...live, herleitung: [...live.herleitung, 'Scannerlauf ohne 12M-Ziel: Ziel live gerechnet.']};
  const ziel = r2(s.target_12m * faktor), q = ziel / live.ziel, t = s.ziel_teile;
  const sk = (v: number | null | undefined) => (zahl(v) ? r2(v * faktor) : null);
  return {
    ...live, ziel,
    upside_pct: preis && preis > 0 ? Math.round((ziel / preis - 1) * 1000) / 10 : live.upside_pct,
    eps_annahme: t?.eps !== null && t?.eps !== undefined ? r2(t.eps * faktor) : live.eps_annahme,
    kgv_annahme: t?.kgv ?? live.kgv_annahme,
    ziel_fundamental: t ? sk(t.fundamental) : live.ziel_fundamental,
    ziel_analyst: t ? sk(t.analyst) : live.ziel_analyst,
    ziel_momentum: t ? sk(t.momentum) : live.ziel_momentum,
    spanne_tief: r2(live.spanne_tief * q), spanne_hoch: r2(live.spanne_hoch * q),
    herleitung: [...live.herleitung, `Ziel aus dem Scannerlauf ${s.zeit} übernommen (Startseite und Einzelanalyse gleich).`],
  };
}
