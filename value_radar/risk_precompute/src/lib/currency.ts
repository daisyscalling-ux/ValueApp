type Row=Record<string,any>;
export interface EurRate {rate:number;from:string;observed_at:string;source:string}
const DAY=86400000;
export function validEurRate(value:any,from:string,now=Date.now()):value is EurRate {
 const date=typeof value?.observed_at==='string'?Date.parse(value.observed_at):NaN;
 return value?.from===from&&typeof value.rate==='number'&&Number.isFinite(value.rate)&&value.rate>0&&Number.isFinite(date)&&now-date>=0&&now-date<=7*DAY;
}
export async function loadEurRate(from:string,password:string,fetcher:typeof fetch=fetch):Promise<EurRate|null>{
 if(from==='EUR')return {from,rate:1,observed_at:new Date().toISOString(),source:'EUR'};
 try{
  const r=await fetcher(`/api/fx/${encodeURIComponent(from)}`,{headers:{'x-app-password':password},signal:AbortSignal.timeout(20000)});
  if(!r.ok)return null;
  const data=await r.json();return validEurRate(data,from)?data:null;
 }catch{return null;}
}
// Display conversion only. ADR/report-currency verification happens upstream.
export function fundInEur(input:Row,quote:EurRate|null,now=Date.now()):Row {
 const fund={...input},from=String(input.currency??'USD');
 if(from==='EUR'||!quote||!validEurRate(quote,from,now))return fund;
 const rate=quote.rate;
 const scale=(v:any)=>typeof v==='number'&&Number.isFinite(v)?v*rate:v;
 for(const key of ['price','market_cap','enterprise_value','total_debt','cash','net_debt','revenue','ebitda','ebit','free_cashflow','reported_equity_fcf','net_income','total_assets','eps_trailing','eps_forward','book_value_ps','target_mean','52w_high','52w_low'])fund[key]=scale(fund[key]);
 for(const key of ['reihe_umsatz','reihe_ebitda','reihe_fcf'])if(Array.isArray(fund[key]))fund[key]=fund[key].map((r:Row)=>({...r,wert:scale(r.wert)}));
 if(Array.isArray(fund.phase_history))fund.phase_history=fund.phase_history.map((r:Row)=>({...r,revenue:scale(r.revenue),netIncome:scale(r.netIncome)}));
 if(fund.capital_return_period?.currency===from){const p={...fund.capital_return_period,currency:'EUR'};for(const k of ['fcf','dividends','buybacks'])p[k]=scale(p[k]);fund.capital_return_period=p;}
 fund.currency='EUR';fund._native_currency=from;fund._fx=rate;fund._fx_live=true;
 fund.data_sources=[...(input.data_sources??[]),{source:quote.source,observed_at:quote.observed_at,retrieved_at:new Date(now).toISOString(),basis:`Anzeigeumrechnung ${from} → EUR, Faktor ${rate}`}];
 return fund;
}
