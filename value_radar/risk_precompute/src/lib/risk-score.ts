import {historyStatistics} from './risk-statistics';
type Row=Record<string,any>;
export type RiskMetric={name:string;weight:number;score:number|null;value:string;reason:string};
const num=(v:unknown)=>v===null||v===undefined||v===''?null:typeof v==='number'&&Number.isFinite(v)?v:null;
const scale=(v:number,low:number,high:number)=>Math.max(0,Math.min(100,100*(v-low)/(high-low)));
const pct=(v:number)=>(v*100).toLocaleString('de-DE',{maximumFractionDigits:1})+' %';
export function financialRiskInput(raw:Row){
 const list=(v:any):Row[]=>Array.isArray(v)?v:Array.isArray(v?.data)?v.data:[];
 const dated=list(raw.enterprise_value).filter(r=>/^\d{4}-\d{2}-\d{2}$/.test(String(r.period_end_date||r.date||''))).sort((a,b)=>String(b.period_end_date||b.date).localeCompare(String(a.period_end_date||a.date)));
 const r=dated[0];if(!r)return null;
 return {asof:r.period_end_date||r.date,currency:r.currency,source:'ROIC Enterprise Value · dieselbe Berichtszeile',debt:r.short_and_long_term_debt,cash:r.bs_cash_near_cash_item,ebitda:r.ttm_ebitda,fcff:r.ttm_free_cash_flow_firm,revenue:r.ttm_net_sales};
}
// Kursblock 'v0.5': in price_block_study.py (ValueApp) gegen spätere Verluste ausgewählt und im Testzeitraum bestätigt.
// 'v0.3' bleibt für Vergleich und Nachvollziehbarkeit erhalten.
export type PriceModel='v0.5'|'v0.3';
export function riskScore(history:Row|null,fund:Row,now=Date.now(),extra:RiskMetric[]=[],priceModel:PriceModel='v0.5'){
 const metrics:RiskMetric[]=[],notes:string[]=[];let period='',observations=0;
 const add=(name:string,weight:number,score:number|null,value:string,reason:string)=>metrics.push({name,weight,score,value,reason});
 const stats=historyStatistics(history,now),{error,es,dd,worst,vol}=stats;observations=stats.observations;period=stats.first?stats.first+' bis '+stats.last:'';
 add('Verlust an den schlechtesten 5 % der Handelstage',15,es===null?null:scale(es,.01,.07),es===null?'—':pct(es),error||'Historischer Tages-Expected-Shortfall; kein prognostizierter Verlust.');
 if(priceModel==='v0.3'){
 add('Größter historischer Rückgang',10,dd===null?null:scale(dd,.15,.70),dd===null?'—':pct(dd),error||'Vom vorherigen Höchststand zum Tiefststand.');
 add('Schlechteste 20-Handelstage-Phase',5,worst===null?null:scale(worst,.05,.35),worst===null?'—':pct(worst),error||'Überlappende Fenster; keine unabhängigen Ereignisse.');
 }else{
 add('Schwankungsbreite · Jahresvolatilität',10,vol===null||vol===undefined?null:scale(vol,.15,.60),vol===null||vol===undefined?'—':pct(vol),error||(vol===null||vol===undefined?'Volatilität fehlt in dieser Vorberechnung; nächster täglicher Lauf ergänzt sie.':'Annualisierte Schwankung der letzten 252 Tagesrenditen. 0 Punkte bei 15 %, 100 Punkte bei 60 %.'));
 add('Größter historischer Rückgang',5,dd===null?null:scale(dd,.15,.70),dd===null?'—':pct(dd),error||'Vom vorherigen Höchststand zum Tiefststand.');
 }
 const f=fund.risk_financial,asof=Date.parse(f?.asof),age=(now-asof)/86400000;
 const financial=/finance|financial|bank|insurance|versicher/i.test(String(fund.sector)+' '+String(fund.industry));
 const reason=financial?'Für Finanzunternehmen sind Kapital- und Kreditkennzahlen erforderlich.':!f?.currency?'Berichtswährung fehlt.':!Number.isFinite(asof)||age<0||age>550?'Finanzstichtag fehlt oder ist nicht aktuell.':'';
 const debt=num(f?.debt),cash=num(f?.cash),ebitda=num(f?.ebitda),fcff=num(f?.fcff),revenue=num(f?.revenue);
 const leverage=!reason&&debt!==null&&debt>=0&&cash!==null&&cash>=0&&ebitda!==null&&ebitda>0?(debt-cash)/ebitda:null;
 add('Nettoschulden / EBITDA',15,leverage===null?null:scale(leverage,1,6),leverage===null?'—':leverage.toFixed(1)+'×',reason||(leverage===null?'Gültige Schulden, Cash und positives EBITDA benötigt.':'Gemeinsame Berichtszeile, kein Währungsmix.'));
 const margin=!reason&&fcff!==null&&revenue!==null&&revenue>0?fcff/revenue:null;
 add('Cashflow-Puffer · berichteter FCFF / Umsatz',10,margin===null?null:100-scale(margin,-.10,.15),margin===null?'—':pct(margin),reason||(margin===null?'Berichteter FCFF oder Umsatz fehlt.':'FCFF des Anbieters; nicht mit Eigenkapital-FCF gleichgesetzt.'));
 metrics.push(...extra);
 const available=metrics.filter(m=>m.score!==null),coverage=available.reduce((s,m)=>s+m.weight,0),partialScore=coverage?Math.round(available.reduce((s,m)=>s+m.weight*m.score!,0)/coverage):null;
 notes.push(priceModel==='v0.3'?'Kursblock Version 0.3 · feste heuristische Schwellen.':'Kursblock Version 0.5 · Gewichte 15/10/5 (Expected Shortfall, Volatilität, größter Rückgang) anhand historischer S&P-500-Verluste ausgewählt; Schwellen nicht als Wahrscheinlichkeit kalibriert.','Teilscore ist keine Verlustwahrscheinlichkeit und kein Kauf-/Verkaufssignal.');
 return {partialScore,coverage,metrics,period,observations,financialAsOf:f?.asof||null,notes};
}
