/** Periodenbewusste Ergänzung aus bereits vorhandenen ROIC-Antworten. */
import type { RoicRaw } from './roic';
import type { Fund } from './valuation';
import { finite, type PhaseYear, type PeObservation } from './lifecycle';
type Row=Record<string,unknown>;
function rows(raw:unknown):Row[]{
 if(Array.isArray(raw))return raw.filter(r=>r&&typeof r==='object');
 if(raw&&typeof raw==='object'){const r=raw as Row;for(const k of ['data','results','rows'])if(Array.isArray(r[k]))return rows(r[k]);}
 return [];
}
function val(r:Row,...keys:string[]):unknown{for(const k of keys){const camel=k.replace(/_([a-z])/g,(_,c)=>c.toUpperCase());if(r[k]!==undefined&&r[k]!==null)return r[k];if(r[camel]!==undefined&&r[camel]!==null)return r[camel];}return null;}
function num(r:Row,...keys:string[]){return finite(val(r,...keys));}
function date(r:Row):string|null {const d=String(val(r,'period_end_date','date')??'').slice(0,10);return /^\d{4}-\d{2}-\d{2}$/.test(d)&&Number.isFinite(Date.parse(d))&&new Date(d).toISOString().slice(0,10)===d?d:null;}
function year(r:Row):number|null {const y=finite(val(r,'fiscal_year','year'))??(date(r)?Number(date(r)!.slice(0,4)):null);return y!==null&&Number.isInteger(y)&&y>=1900&&y<=new Date().getUTCFullYear()?y:null;}
function currency(r:Row):string|null{const c=val(r,'currency','reporting_currency');return typeof c==='string'&&/^[A-Z]{3}$/.test(c)?c:null;}
function annual(r:Row){const t=String(val(r,'period_type')??'annual').toLowerCase();return ['annual','fy','yearly'].includes(t);}
function datedRows(raw:unknown){return rows(raw).filter(r=>annual(r)&&year(r)!==null&&(!date(r)||Date.parse(date(r)!)<=Date.now())).sort((a,b)=>year(b)!-year(a)!);}
export function peObservations(raw:unknown):PeObservation[]{
 const map=new Map<number,number>();
 for(const r of datedRows(raw)){const y=year(r)!;const p=num(r,'average_price_earnings_ratio','pe_ratio');if(p!==null&&p>0&&!map.has(y))map.set(y,p);}
 return [...map].sort((a,b)=>b[0]-a[0]).slice(0,5).reverse().map(([year,value])=>({year,value}));
}
export function phaseInputs(raw:RoicRaw):Pick<Fund,'phase_history'|'capital_return_period'>{
 const inc=datedRows(raw.income),cf=datedRows(raw.cashflow),history:PhaseYear[]=[];
 const seen=new Set<number>();
 // Never combine a trend across explicitly different reporting currencies.
 const latestCurrency=inc.length?currency(inc[0]):null;
 for(const r of inc){if(seen.has(year(r)!))continue;seen.add(year(r)!);
  const rev=num(r,'is_sales_revenue_turnover','is_sales_and_services_revenues'),op=num(r,'is_oper_income');
  const compatible=currency(r)===latestCurrency;
  history.push({year:year(r)!,revenue:compatible?rev:null,netIncome:compatible?num(r,'is_net_income','net_income'):null,
   operatingMargin:compatible&&rev!==null&&rev>0&&op!==null?op/rev:null});
 }
 const out:Pick<Fund,'phase_history'|'capital_return_period'>={phase_history:history.reverse()};
 // Coverage needs explicit, matching date + currency; no positional joins.
 const c=cf[0];if(!c||!date(c)||!currency(c))return out;
 const income=inc.find(i=>date(i)===date(c)&&currency(i)===currency(c));
 const prior=income?inc.find(i=>currency(i)===currency(c)&&date(i)&&Date.parse(date(c)!)-Date.parse(date(i)!)>=330*86400000&&Date.parse(date(c)!)-Date.parse(date(i)!)<=400*86400000):null;
 const dividends=num(c,'cf_dvd_paid','cf_cash_dividends_paid');
 const buybacks=num(c,'cf_cash_for_repurch_com_stock','cf_repurchase_of_capital_stock');
 // Explicit equity cashflow only; enterprise-value FCFF must not fund shareholder distributions.
 let fcf=num(c,'cf_free_cash_flow');
 const ocf=num(c,'cf_cash_from_oper'),capex=num(c,'cf_cap_expenditures','cf_capital_expenditures');
 if(fcf===null&&ocf!==null&&capex!==null)fcf=ocf-Math.abs(capex);
 out.capital_return_period={date:date(c)!,currency:currency(c)!,fcf,
  dividends:dividends===null?null:Math.abs(dividends),buybacks:buybacks===null?null:Math.abs(buybacks),
  dilutedShares:income?num(income,'is_sh_for_diluted_eps'):null,priorDilutedShares:prior?num(prior,'is_sh_for_diluted_eps'):null};
 return out;
}
