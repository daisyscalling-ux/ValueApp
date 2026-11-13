/**
 * cash-conversion.ts - Mehrjaehrige Cash-Conversion fuer den DCF (seit 13.11.2026, Entscheidung des Nutzers).
 * Conversion = Summe(operativer Cashflow - Investitionen) / Summe(Jahresueberschuss) ueber 3 bis 5 aufeinanderfolgende
 * Geschaeftsjahre aus der geprueften ROIC-Historie (cf_roic_history.json), nur bei positiver Gewinnsumme, nach oben begrenzt auf 1,5.
 * Keine Untergrenze (Entscheidung des Nutzers 13.11.2026): eine Untergrenze haette investitionsstarke Firmen beschoenigt.
 * Wert <= 0 (Summe freier Cashflow nicht positiv): DCF bleibt offen (valuation.ts, fcfBasis), kein Rueckfall auf ein Einzeljahr.
 * Die Pipeline rechnet (export-history-backfill.ts), App und Scanner pruefen beim Lesen erneut (verifiedCashConversion).
 * Identische Kopie unter ValueApp/value_radar/risk_precompute/src/lib.
 */
export const CASH_CONVERSION_METHOD='sum_fcf_over_sum_net_income_v1';
export const CC_MIN_YEARS=3,CC_MAX_YEARS=5,CC_MAX=1.5,CC_MAX_AGE_DAYS=550;
type Row=Record<string,any>;
const DAY=86400000;
const finite=(v:unknown):v is number=>typeof v==='number'&&Number.isFinite(v);
const dateOnly=(v:unknown):v is string=>typeof v==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(v)&&Number.isFinite(Date.parse(v));
export type CashConversionPeriod={end:string;fcf:number;netIncome:number};
export type CashConversion={state:'available';method:string;value:number;raw:number;clamped:boolean;years:number;currency:string;sumFcf:number;sumNetIncome:number;periods:CashConversionPeriod[]}|{state:'missing';method:string;reason:string};

function check(periods:CashConversionPeriod[],now:number):{raw:number;sumFcf:number;sumNetIncome:number}|string{
 if(periods.length<CC_MIN_YEARS)return 'Weniger als drei geprüfte Geschäftsjahre.';
 if(periods.length>CC_MAX_YEARS)return 'Mehr als fünf Geschäftsjahre.';
 for(let i=0;i<periods.length;i++){
  const p=periods[i];
  if(!dateOnly(p.end)||!finite(p.fcf)||!finite(p.netIncome))return 'Ungültiges Geschäftsjahr.';
  if(i>0){const gap=(Date.parse(p.end)-Date.parse(periods[i-1].end))/DAY;if(gap<300||gap>430)return 'Geschäftsjahre nicht aufeinanderfolgend.';}
 }
 const last=Date.parse(periods[periods.length-1].end);
 if(last>now||now-last>CC_MAX_AGE_DAYS*DAY)return 'Letztes Geschäftsjahr älter als 550 Tage.';
 const sumFcf=periods.reduce((s,p)=>s+p.fcf,0),sumNetIncome=periods.reduce((s,p)=>s+p.netIncome,0);
 if(!(sumNetIncome>0))return 'Gewinnsumme nicht positiv; Conversion nicht aussagekräftig.';
 return {raw:sumFcf/sumNetIncome,sumFcf,sumNetIncome};
}

/** Aus den geprueften Jahresabschluessen (aelteste zuerst oder beliebig sortiert). */
export function cashConversionFromAnnuals(annuals:Row[],now=Date.now()):CashConversion{
 const miss=(reason:string):CashConversion=>({state:'missing',method:CASH_CONVERSION_METHOD,reason});
 const usable=(annuals||[]).filter(a=>a&&dateOnly(a.end)&&finite(a.fields?.operating_cashflow)&&finite(a.fields?.capex)&&a.fields.capex>=0&&finite(a.fields?.net_income));
 const currencies=new Set(usable.map(a=>a.currency));
 if(currencies.size>1)return miss('Geschäftsjahre in unterschiedlichen Währungen.');
 const ends=usable.map(a=>a.end);if(new Set(ends).size!==ends.length)return miss('Geschäftsjahr doppelt.');
 const periods=usable.sort((a,b)=>a.end.localeCompare(b.end)).slice(-CC_MAX_YEARS).map(a=>({end:a.end,fcf:a.fields.operating_cashflow-a.fields.capex,netIncome:a.fields.net_income}));
 const r=check(periods,now);if(typeof r==='string')return miss(r);
 const value=Math.min(CC_MAX,r.raw);
 return {state:'available',method:CASH_CONVERSION_METHOD,value,raw:r.raw,clamped:value!==r.raw,years:periods.length,currency:String([...currencies][0]??''),sumFcf:r.sumFcf,sumNetIncome:r.sumNetIncome,periods};
}

/** Erneute Pruefung beim Lesen: Methode, Jahre, Abstand, Alter, Summen und Begrenzung werden nachgerechnet. */
export function verifiedCashConversion(x:unknown,now=Date.now()):(CashConversion&{state:'available'})|null{
 const c=x as Row;
 if(!c||c.state!=='available'||c.method!==CASH_CONVERSION_METHOD||!Array.isArray(c.periods))return null;
 const r=check(c.periods,now);if(typeof r==='string')return null;
 const value=Math.min(CC_MAX,r.raw);
 if(Math.abs(r.raw-c.raw)>1e-9||Math.abs(value-c.value)>1e-9||c.years!==c.periods.length||c.clamped!==(value!==r.raw))return null;
 return c as CashConversion&{state:'available'};
}
