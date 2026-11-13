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
  // Historical market caps are not current valuation weights or a denominator
  // for deriving share counts from today's price.
  if (positive(f.price) && positive(f.shares_out) && positive(f.market_cap)) {
    const ratio = f.market_cap/(f.price*f.shares_out);
    if (ratio<0.5 || ratio>2) issues.push('Börsenwert passt nicht zu Kurs × Aktienzahl (Abweichung über Faktor 2). Stichtag/Aktienbasis ungeklärt.');
  }
  if (raw && incomeDate === null) issues.push('Berichtsperiode der Gewinnzahlen fehlt; Aktualität nicht belegt.');
  if(incomeDate!==null&&f.provider_latest_fiscal_end&&Date.parse(f.provider_latest_fiscal_end)-incomeDate>35*86400000)issues.push('Anbieter meldet ein neueres abgeschlossenes Geschäftsjahr als die verfügbaren Gewinnzahlen. Ersatzbericht noch ausstehend.');
  if (incomeDate !== null && Date.now()-incomeDate>460*86400000) issues.push('Jahresabschluss älter als 460 Tage; neuere Daten erforderlich.');
  if (!f.annual_supplement_applied && income && (income.currency??income.reporting_currency) && (income.currency??income.reporting_currency)!==f.currency) issues.push('Berichtswährung und Handelswährung unterscheiden sich; Umrechnung fehlt.');
  if(f.annual_supplement_applied)warnings.push('Datierter Jahresblock ersetzt ältere Kennzahlen. Nicht belegter FCFF und Prognose-EPS bleiben leer.');
  return {blocked:issues.length>0, issues, warnings, income_period:incomeDate === null?null:new Date(incomeDate).toISOString().slice(0,10), enterprise_period:evDate === null?null:new Date(evDate).toISOString().slice(0,10)};
}
