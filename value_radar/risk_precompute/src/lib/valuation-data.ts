/** Data integrity checks, independent of the desired valuation or ticker. */
type Row = Record<string, any>;
export function period(r: Row): number | null {
  const d = r.period_end_date ?? r.periodEndDate ?? r.date;
  if (typeof d === 'string' && /^\d{4}-\d{2}-\d{2}/.test(d)) {
    const n = Date.parse(d.slice(0,10));
    if (Number.isFinite(n) && new Date(n).toISOString().slice(0,10)===d.slice(0,10)) return n;
  }
  return null; // A fiscal year is not a known balance-sheet date.
}
export function latestRows(value: unknown, annual = false): Row[] {
  let rows: Row[] = [];
  if (Array.isArray(value)) rows = value;
  else if (value && typeof value === 'object') {
    const r = value as Row;
    const nested = r.data ?? r.results ?? r.rows;
    rows = Array.isArray(nested) ? nested : [r];
  }
  const rank=(r:Row)=>period(r) ?? (Number.isInteger(Number(r.fiscal_year??r.fiscalYear)) ? Date.UTC(Number(r.fiscal_year??r.fiscalYear),0,1) : -Infinity);
  return rows.filter(r => r && typeof r === 'object' && (period(r)===null||period(r)!<=Date.now()) && (!annual || !(r.period_type??r.periodType) || ['annual','fy','yearly'].includes(String(r.period_type??r.periodType).toLowerCase())))
    .slice().sort((a,b)=>rank(b)-rank(a));
}
export function normalizeFinancialRows(raw: Row): Row {
  const out = {...raw};
  for (const key of ['enterprise_value','ratios','liquidity','multiples','income','balance','cashflow']) {
    if (raw[key]) out[key] = latestRows(raw[key], ['multiples','income','balance','cashflow'].includes(key));
  }
  return out;
}
const positive = (x: unknown): x is number => typeof x === 'number' && Number.isFinite(x) && x > 0;
export const MCAP_PROVIDER_MAX_AGE_DAYS = 120, ANNUAL_SHARES_MAX_AGE_DAYS = 550;
const DR_STANDARD = [0.01,0.02,0.04,0.05,0.1,0.2,0.25,1/3,0.5,1,2,3,4,5,6,8,10,12,15,16,20,25,30,40,50,100];
/** Aktien je Notierungseinheit aus der geprüften share_basis (Spiegel von sharesPerUnit in fundamental-supplement.ts). */
function unitsFromBasis(b: Row|undefined): number|null {
  const r=b?.ordinary_shares_per_unit;
  if(r===1)return 1;
  if(b?.kind!=='ADR'||b?.method!=='share_count_and_price_ratio_v1'||typeof r!=='number'||!Number.isFinite(r)||!DR_STANDARD.some(x=>Math.abs(x/r-1)<1e-5))return null;
  const e=b.evidence;if(!(typeof e?.byShareCount==='number')||!(typeof e?.byPrice==='number')||Math.abs(e.byShareCount/r-1)>.02||Math.abs(e.byPrice/r-1)>.10)return null;
  return r;
}
/**
 * Börsenwert aktuell (seit 13.11.2026, Entscheidung des Nutzers): ROIC liefert market_cap zum Stichtag des letzten
 * Abschlusses und bei Nordic-Titeln in USD (Micron: 130 statt 873 Mrd. USD). Börsenwert = Kurs × Aktienzahl,
 * gekennzeichnet; der Anbieterwert bleibt mit Stichtag/Währung (risk_financial, dieselbe Zeile) für die Prüfung erhalten.
 * annual_shares: Aktienzahl laut Jahresabschluss der Ergänzungsdatei in Notierungseinheiten (geprüfte share_basis;
 * ohne sie nur bei gleicher Berichts- und Handelswährung, sonst keine Prüfung). Idempotent.
 */
// symbol: erwartete Notierung der Ersatzdatei (Identität); weicht sie ab, wird die Datei für die Aktienzahl verworfen.
export function normalizeMarketCap(f: Row, supplement?: Row|null, now = Date.now(), symbol?: string|null): void {
  if (f.market_cap_source === 'kurs_x_aktien') return;
  const s = supplement, a = s?.annual, w = a?.fields?.weighted_shares;
  if (s && s.schema===1 && (symbol==null || s.symbol===symbol) && positive(w) && typeof a.end==='string' && Number.isFinite(Date.parse(a.end)) && now-Date.parse(a.end)<=ANNUAL_SHARES_MAX_AGE_DAYS*86400000) {
    // Aktienzahl ist einheitenfrei; Pfund und Pence (GBP/GBp/GBX) gelten deshalb als dieselbe Währung.
    const cur = (x: unknown) => (x==='GBp'||x==='GBX') ? 'GBP' : x;
    const units = s.share_basis ? unitsFromBasis(s.share_basis) : (a.currency && cur(a.currency)===cur(s.market?.currency) ? 1 : null);
    if (units) f.annual_shares = { value: w/units, end: a.end, source: a.source ?? null };
  }
  if (!(positive(f.price) && positive(f.shares_out))) return;
  const rf = f.risk_financial;
  f.market_cap_provider = positive(f.market_cap) ? { value: f.market_cap, asof: rf?.asof ?? null, currency: rf?.currency ?? null } : null;
  f.market_cap = f.price * f.shares_out;
  f.market_cap_source = 'kurs_x_aktien';
}
export function valuationDataCheck(f: Row, raw?: Row) {
  const issues: string[] = [];
  const warnings: string[] = [];
  const income = raw ? latestRows(raw.income,true)[0] : null;
  const ev = raw ? latestRows(raw.enterprise_value)[0] : null;
  const incomeDate = f.annual_supplement_applied ? Date.parse(f.supplement_annual_end) : income ? period(income) : null;
  const evDate = !f.annual_supplement_applied && ev ? period(ev) : null;
  if (incomeDate !== null && evDate !== null && incomeDate - evDate > 120*86400000) {
    issues.push('Gewinnbericht ist neuer als der Cashflow-/Unternehmenswertblock. Perioden müssen vor der Bewertung abgeglichen werden.');
  }
  const metric = raw?.metric?.metric ?? raw?.metric;
  const ttm = Number(metric?.epsTTM);
  if (positive(ttm) && positive(f.eps_trailing) && Math.max(ttm/f.eps_trailing,f.eps_trailing/ttm)>4) {
    (f.annual_supplement_applied ? warnings : issues).push('Jahres-EPS und Anbieter-TTM-EPS unterscheiden sich um mehr als Faktor 4. Berichtsperioden, Sondereffekte und Aktienbasis sind ungeklärt.');
  }
  const hi = f['52w_high'];
  if (positive(f.price) && positive(hi) && f.price>hi*2) {
    issues.push('Aktueller Kurs liegt über dem Doppelten des gelieferten 52-Wochen-Hochs. Kursbasis oder Datenstand widersprüchlich.');
  }
  // Börsenwert = Kurs × Aktienzahl (normalizeMarketCap). Gegengeprüft wird die Aktienbasis, in dieser Reihenfolge:
  // 1. Anbieterwert, wenn Stichtag ≤ 120 Tage und gleiche Währung; 2. Aktienzahl im Jahresabschluss (≤ 550 Tage);
  // 3. älterer Anbieterwert (andere Währung sperrt); 4. ohne jeden Vergleichswert nur Warnung.
  if (positive(f.price) && positive(f.shares_out)) {
    const own = f.price*f.shares_out, prov = f.market_cap_provider, ann = f.annual_shares;
    const provOk = prov && positive(prov.value) && typeof prov.asof==='string' && Number.isFinite(Date.parse(prov.asof)) && Date.now()-Date.parse(prov.asof)<=MCAP_PROVIDER_MAX_AGE_DAYS*86400000 && prov.currency===f.currency;
    if (provOk) {
      const ratio = prov.value/own;
      if (ratio<0.5 || ratio>2) issues.push('Börsenwert des Anbieters (Stichtag '+prov.asof+') passt nicht zu Kurs × Aktienzahl (Abweichung über Faktor 2). Aktienbasis ungeklärt.');
    } else if (ann && positive(ann.value)) {
      const ratio = f.shares_out/ann.value;
      if (ratio<0.5 || ratio>2) issues.push('Aktienzahl passt nicht zum Jahresabschluss '+ann.end+' (Abweichung über Faktor 2). Aktienbasis ungeklärt.');
    } else if (prov && positive(prov.value)) {
      // Kein belegter Jahresabschluss: dann bleibt der Anbieterwert der Prüfmaßstab, auch wenn er älter ist (offen statt falsch).
      const ratio = prov.value/own;
      if (prov.currency && prov.currency!==f.currency) issues.push('Aktienzahl nicht belegt: Anbieter-Börsenwert in '+prov.currency+', Notierung in '+f.currency+', kein passender Jahresabschluss. Aktienbasis (ADR?) ungeklärt.');
      else if (ratio<0.5 || ratio>2) issues.push('Börsenwert des Anbieters (Stichtag '+(prov.asof??'unbekannt')+') passt nicht zu Kurs × Aktienzahl (Abweichung über Faktor 2), kein Jahresabschluss zur Gegenprüfung. Aktienbasis ungeklärt.');
      else warnings.push('Aktienzahl nur gegen älteren Anbieterwert geprüft (Stichtag '+(prov.asof??'unbekannt')+').');
    } else if (positive(f.market_cap) && f.market_cap_source!=='kurs_x_aktien') {
      const ratio = f.market_cap/own;
      if (ratio<0.5 || ratio>2) issues.push('Börsenwert passt nicht zu Kurs × Aktienzahl (Abweichung über Faktor 2). Stichtag/Aktienbasis ungeklärt.');
    } else warnings.push('Aktienzahl nicht gegengeprüft (kein aktueller Anbieterwert, kein passender Jahresabschluss).');
  }
  if (raw && incomeDate === null) issues.push('Berichtsperiode der Gewinnzahlen fehlt; Aktualität nicht belegt.');
  if(incomeDate!==null&&f.provider_latest_fiscal_end&&Date.parse(f.provider_latest_fiscal_end)-incomeDate>35*86400000)issues.push('Anbieter meldet ein neueres abgeschlossenes Geschäftsjahr als die verfügbaren Gewinnzahlen. Ersatzbericht noch ausstehend.');
  if (incomeDate !== null && Date.now()-incomeDate>460*86400000) issues.push('Jahresabschluss älter als 460 Tage; neuere Daten erforderlich.');
  if (!f.annual_supplement_applied && income && (income.currency??income.reporting_currency) && (income.currency??income.reporting_currency)!==f.currency) issues.push('Berichtswährung und Handelswährung unterscheiden sich; Umrechnung fehlt.');
  if(f.annual_supplement_applied)warnings.push('Datierter Jahresblock ersetzt ältere Kennzahlen. Nicht belegter FCFF und Prognose-EPS bleiben leer.');
  return {blocked:issues.length>0, issues, warnings, income_period:incomeDate === null?null:new Date(incomeDate).toISOString().slice(0,10), enterprise_period:evDate === null?null:new Date(evDate).toISOString().slice(0,10)};
}
