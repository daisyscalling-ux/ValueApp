type Row=Record<string,any>;
export const RISK_SCHEMA=1;
// Volle Historie ab zwei Handelsjahren. Verkürzte Historie (ein bis zwei Jahre, z. B. nach Börsengang oder Abspaltung):
// Volatilität (ohnehin nur die letzten 252 Renditen) und Expected Shortfall werden berechnet und gekennzeichnet;
// der größte Rückgang bleibt offen, weil er über einen kürzeren Zeitraum systematisch zu niedrig ausfällt.
export const FULL_OBSERVATIONS=505,SHORT_OBSERVATIONS=253;
export function historyStatistics(h:Row|null,now=Date.now()):Row{
 const empty=(error:string)=>({observations:0,first:'',last:'',error,es:null,dd:null,worst:null,vol:null,drawdown:null});
 if(!h)return empty('Bereinigte Kurshistorie fehlt.');
 if(h.format==='risk-summary'){
  const s=h.statistics,validDate=(v:any)=>typeof v==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(v)&&Number.isFinite(Date.parse(v));
  const fraction=(v:any)=>v===null||typeof v==='number'&&Number.isFinite(v)&&v>=0&&v<=1;
  const short=s?.shortHistory===true;
  if(h.schema!==RISK_SCHEMA||h.adjustment!=='total_return'||!s||!Number.isInteger(s.observations)||s.observations<1||!validDate(s.first)||!validDate(s.last)||s.first>s.last||typeof s.error!=='string'||![s.es,s.dd,s.worst,s.drawdown].every(fraction)||!(s.shortHistory===undefined||s.shortHistory===true)||short&&(s.observations<SHORT_OBSERVATIONS||s.observations>=FULL_OBSERVATIONS||!!s.error||s.dd!==null||s.worst!==null)||s.observations<FULL_OBSERVATIONS&&!short&&[s.es,s.dd,s.worst].some(v=>v!==null)||s.observations<200&&s.drawdown!==null||s.error&&[s.es,s.dd,s.worst].some(v=>v!==null)||!(s.vol===undefined||s.vol===null||typeof s.vol==='number'&&Number.isFinite(s.vol)&&s.vol>=0&&s.vol<=5)||(s.observations<FULL_OBSERVATIONS&&!short||s.error)&&typeof s.vol==='number')return empty('Ungültige vorberechnete Risikodaten.');
  if(Date.parse(s.last)>=new Date(now).setUTCHours(0,0,0,0)||now-Date.parse(s.last)>7*86400000)return {...s,error:'Letzter Kurs nicht aktuell oder in der Zukunft.',es:null,dd:null,worst:null,vol:null,drawdown:null};
  // Ältere Vorberechnungen ohne Volatilität bleiben gültig; die Kennzahl ist dann offen.
  return {...s,vol:s.vol??null};
 }
 if(h.adjustment!=='total_return'||!Array.isArray(h.bars))return empty('Dividenden-/Splitbereinigung nicht bestätigt.');
 const seen=new Map<string,number>();let invalid=false;
 for(const b of h.bars){const stamp=Date.parse(b.date);if(!/^\d{4}-\d{2}-\d{2}$/.test(b.date)||!Number.isFinite(stamp)||stamp>=new Date(now).setUTCHours(0,0,0,0)||typeof b.close!=='number'||!Number.isFinite(b.close)||b.close<=0){invalid=true;continue}if(seen.has(b.date)&&seen.get(b.date)!==b.close)invalid=true;seen.set(b.date,b.close)}
 const a=[...seen].sort((a,b)=>a[0].localeCompare(b[0]));if(!a.length)return empty('Kurshistorie leer.');
 const s:Row={observations:a.length,first:a[0][0],last:a.at(-1)![0],error:'',es:null,dd:null,worst:null,vol:null,drawdown:null};
 const basic=invalid?'Ungültige oder widersprüchliche Kursdaten.':now-Date.parse(s.last)>7*86400000?'Letzter Kurs älter als sieben Tage.':'';
 const gaps=(v:[string,number][])=>v.some((b,i)=>i>0&&Date.parse(b[0])-Date.parse(v[i-1][0])>14*86400000);
 const recent=a.slice(-252);if(!basic&&recent.length>=200&&!gaps(recent))s.drawdown=1-recent.at(-1)![1]/Math.max(...recent.map(b=>b[1]));
 s.error=basic||(a.length<SHORT_OBSERVATIONS?'Weniger als ein Handelsjahr vorhanden.':gaps(a)?'Kurshistorie enthält längere Lücken.':'');
 const short=!s.error&&a.length<FULL_OBSERVATIONS;if(short)s.shortHistory=true;
 if(!s.error){const raw=a.slice(1).map((b,i)=>b[1]/a[i][1]-1),last=raw.slice(-252),mean=last.reduce((x,y)=>x+y,0)/last.length;s.vol=Math.sqrt(last.reduce((x,y)=>x+(y-mean)**2,0)/(last.length-1)*252);const returns=[...raw].sort((a,b)=>a-b),tail=returns.slice(0,Math.max(1,Math.floor(returns.length*.05)));s.es=Math.max(0,-tail.reduce((a,b)=>a+b,0)/tail.length);
  if(!short){let peak=a[0][1];s.dd=0;s.worst=0;a.forEach((b,i)=>{peak=Math.max(peak,b[1]);s.dd=Math.max(s.dd,1-b[1]/peak);if(i>=20)s.worst=Math.max(s.worst,1-b[1]/a[i-20][1])})}}
 return s;
}
export function compactHistory(h:Row,now=Date.now()){
 return {format:'risk-summary',schema:RISK_SCHEMA,symbol:h.symbol,currency:h.currency,adjustment:h.adjustment,retrievedAt:h.retrievedAt,requestedFrom:h.requestedFrom,requestedYears:h.requestedYears,historyNote:h.historyNote,provider:h.provider,statistics:historyStatistics(h,now),...(h.proxy?{proxy:h.proxy,region:h.region,note:h.note}:{})};
}
