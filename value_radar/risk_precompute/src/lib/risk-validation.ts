import {riskScore} from './risk-score';
type Row=Record<string,any>;
export const VALIDATION_VERSION=1;
export const SPLIT_DATE='2025-01-01';
export type Observation={date:string;entry:string;end:string;horizon:number;score:number;volatility:number;loss:number;drawdown:number;return:number};
export function validateHistory(h:Row,now=Date.now()):Observation[]{
 if(h.adjustment!=='total_return'||!Array.isArray(h.bars))return [];
 const today=new Date(now).toISOString().slice(0,10),seen=new Map<string,number>();
 for(const b of h.bars){if(!/^\d{4}-\d{2}-\d{2}$/.test(b.date)||!Number.isFinite(Date.parse(b.date))||typeof b.close!=='number'||!Number.isFinite(b.close)||b.close<=0)return [];if(b.date>=today)continue;if(seen.has(b.date)&&seen.get(b.date)!==b.close)return [];seen.set(b.date,b.close)}
 const bars=[...seen].sort((a,b)=>a[0].localeCompare(b[0])).map(([date,close])=>({date,close})),out:Observation[]=[];
 for(let i=504;i<bars.length-1;i++){
  const month=Number(bars[i].date.slice(5,7));if(month%3!==0||bars[i].date.slice(0,7)===bars[i+1].date.slice(0,7))continue;
  const past=bars.slice(0,i+1),score=riskScore({adjustment:'total_return',bars:past},{},Date.parse(bars[i].date)+86400000);if(score.coverage!==30||score.partialScore===null)continue;
  const tail=past.slice(-253),rets=tail.slice(1).map((b,j)=>b.close/tail[j].close-1),mean=rets.reduce((a,b)=>a+b,0)/rets.length,volatility=Math.sqrt(rets.reduce((a,b)=>a+(b-mean)**2,0)/(rets.length-1)*252);
  for(const [horizon,sessions] of [[1,21],[3,63],[6,126]]){
   const entry=i+1,end=entry+sessions;if(end>=bars.length)continue;
   const future=bars.slice(entry,end+1);if(future.some((b,j)=>j>0&&Date.parse(b.date)-Date.parse(future[j-1].date)>14*86400000))continue;
   // Exclude outcome windows crossing the fixed time split.
   if(bars[i].date<SPLIT_DATE&&bars[end].date>=SPLIT_DATE)continue;
   const start=bars[entry].close;let peak=start,drawdown=0,loss=0;for(const b of future){peak=Math.max(peak,b.close);drawdown=Math.max(drawdown,1-b.close/peak);loss=Math.max(loss,1-b.close/start)}
   out.push({date:bars[i].date,entry:bars[entry].date,end:bars[end].date,horizon,score:score.partialScore,volatility,loss,drawdown,return:bars[end].close/start-1});
  }
 }
 return out;
}
const average=(a:number[])=>a.length?a.reduce((s,x)=>s+x,0)/a.length:null;
const ranks=(a:number[])=>{const sorted=a.map((v,i)=>({v,i})).sort((a,b)=>a.v-b.v),r:number[]=[];for(let i=0;i<sorted.length;){let j=i+1;while(j<sorted.length&&sorted[j].v===sorted[i].v)j++;for(let k=i;k<j;k++)r[sorted[k].i]=(i+j-1)/2;i=j}return r};
export function rankCorrelation(x:number[],y:number[]):number|null{
 if(x.length!==y.length||x.length<3)return null;const a=ranks(x),b=ranks(y),am=average(a)!,bm=average(b)!;let ab=0,aa=0,bb=0;for(let i=0;i<a.length;i++){ab+=(a[i]-am)*(b[i]-bm);aa+=(a[i]-am)**2;bb+=(b[i]-bm)**2}return aa&&bb?ab/Math.sqrt(aa*bb):null;
}
export function validationReport(series:Row,now=Date.now()){
 const rows:any[]=[],symbols=new Set<string>();let oldest='',newest='';
 for(const [symbol,s] of Object.entries(series) as [string,Row][]){if(s.version!==VALIDATION_VERSION||!Array.isArray(s.observations))continue;for(const o of s.observations){rows.push({...o,symbol});symbols.add(symbol);if(!oldest||s.retrievedAt<oldest)oldest=s.retrievedAt;if(s.retrievedAt>newest)newest=s.retrievedAt}}
 const periods=['earlier','later'],results:any[]=[];
 for(const period of periods)for(const horizon of [1,3,6]){
  const sample=rows.filter(r=>r.horizon===horizon&&(period==='earlier'?r.end<SPLIT_DATE:r.date>=SPLIT_DATE));
  const groups=[0,25,50,75].map(low=>{const a=sample.filter(r=>r.score>=low&&(low===75?r.score<=100:r.score<low+25));return {label:low+'–'+(low===75?100:low+24),n:a.length,companies:new Set(a.map(r=>r.symbol)).size,loss20Rate:a.length?a.filter(r=>r.loss>=.2).length/a.length:null,meanLoss:average(a.map(r=>r.loss)),meanDrawdown:average(a.map(r=>r.drawdown)),meanReturn:average(a.map(r=>r.return))}});
  const dates=[...new Set<string>(sample.map(r=>r.date.slice(0,7)))],crossSections=dates.map(date=>{const a=sample.filter(r=>r.date.slice(0,7)===date);return {date,n:a.length,score:a.length>=20?rankCorrelation(a.map(r=>r.score),a.map(r=>r.loss)):null,volatility:a.length>=20?rankCorrelation(a.map(r=>r.volatility),a.map(r=>r.loss)):null}});
  results.push({period,horizon,n:sample.length,companies:new Set(sample.map(r=>r.symbol)).size,groups,crossSections,meanScoreCorrelation:average(crossSections.flatMap(r=>r.score===null?[]:[r.score])),meanVolatilityCorrelation:average(crossSections.flatMap(r=>r.volatility===null?[]:[r.volatility]))});
 }
 return {schema:VALIDATION_VERSION,generatedAt:new Date(now).toISOString(),status:rows.length?'exploratory':'pending',scope:'Kursbasierter Teil: 30 % Modellgewicht, für diese Prüfung auf 0–100 normiert',splitDate:SPLIT_DATE,companies:symbols.size,observations:rows.length,firstDecision:rows.length?rows.map(r=>r.date).sort()[0]:null,lastDecision:rows.length?rows.map(r=>r.date).sort().at(-1):null,retrievedFrom:oldest||null,retrievedTo:newest||null,results,limitations:[
 'Heutiges Aktienuniversum; ausgeschiedene Unternehmen fehlen. Survivorship- und Auswahlverzerrung.',
 'Nur eindeutige primäre Stammaktien aus dem vorhandenen Universum. ADRs und Vorzugsaktien werden nicht als zusätzliche unabhängige Unternehmen gezählt.',
 'Zwei bis knapp fünf Jahre verfügbarer Rückblick je Stichtag; kein konstanter Fünfjahres-Backtest. Aktuell restatierte Total-Return-Daten sind keine archivierten Point-in-Time-Daten.',
 'Quartalsstichtage; Einstieg zum Schlusskurs der nächsten Sitzung. Horizonte: 21, 63 und 126 weitere Handelstage.',
 'Fenster über den Trennstichtag werden ausgeschlossen. Die spätere Periode ist keine garantiert unangetastete Teststichprobe.',
 'Sechsmonatsfenster überlappen; auch 63-Handelstage-Fenster können sich zwischen Quartalen leicht überschneiden; Unternehmen teilen Marktereignisse. Beobachtungen sind nicht unabhängig. Keine Signifikanz- oder Wahrscheinlichkeitskalibrierung.',
 '20-%-Ereignis bedeutet mindestens 20 % Rückgang vom Einstiegsschlusskurs innerhalb des Fensters. Historische Häufigkeit ist keine individuelle Verlustwahrscheinlichkeit.',
 'Vergleich: Rangkorrelation mit späterem Verlust je Stichtag (ab 20 Aktien), zusätzlich einfache historische Jahresvolatilität. Keine automatische Änderung der Score-Gewichte.',
 'Finanzberichte, Nachrichten, Markt-/Peer-Komponenten und Derivate werden hier nicht rückwirkend validiert.'
 ]};
}
