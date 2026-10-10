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
export function riskScore(history:Row|null,fund:Row,now=Date.now(),extra:RiskMetric[]=[]){
 const metrics:RiskMetric[]=[],notes:string[]=[];let period='',observations=0;
 const add=(name:string,weight:number,score:number|null,value:string,reason:string)=>metrics.push({name,weight,score,value,reason});
 const stats=historyStatistics(history,now),{error,es,dd,worst}=stats;observations=stats.observations;period=stats.first?stats.first+' bis '+stats.last:'';
 add('Verlust an den schlechtesten 5 % der Handelstage',15,es===null?null:scale(es,.01,.07),es===null?'—':pct(es),error||'Historischer Tages-Expected-Shortfall; kein prognostizierter Verlust.');
 add('Größter historischer Rückgang',10,dd===null?null:scale(dd,.15,.70),dd===null?'—':pct(dd),error||'Vom vorherigen Höchststand zum Tiefststand.');
 add('Schlechteste 20-Handelstage-Phase',5,worst===null?null:scale(worst,.05,.35),worst===null?'—':pct(worst),error||'Überlappende Fenster; keine unabhängigen Ereignisse.');
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
 notes.push('Version 0.3 · feste heuristische Schwellen; noch nicht historisch kalibriert.','Wettbewerbsanfälligkeit und Bewertung (30 % des Konzepts) sowie bestätigte Ereigniszuschläge sind noch offen. Markt/Peer-Stress ist eine vorläufige Drawdown-Näherung.','Teilscore ist keine Verlustwahrscheinlichkeit und kein Kauf-/Verkaufssignal.');
 return {partialScore,coverage,metrics,period,observations,financialAsOf:f?.asof||null,notes};
}
