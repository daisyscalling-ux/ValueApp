type Row=Record<string,any>;
export const RISK_SCHEMA=1;
// Volle Historie ab zwei Handelsjahren. Verkürzte Historie (ein bis zwei Jahre, z. B. nach Börsengang oder Abspaltung):
// Volatilität (ohnehin nur die letzten 252 Renditen) und Expected Shortfall werden berechnet und gekennzeichnet;
// der größte Rückgang bleibt offen, weil er über einen kürzeren Zeitraum systematisch zu niedrig ausfällt.
export const FULL_OBSERVATIONS=505,SHORT_OBSERVATIONS=253;
export const RSI_TAGE=14,SMA_TAGE=200;
/** RSI 14 (Wilder-Glättung über alle verfügbaren Renditen des lückenlosen Endstücks) und Abstand zum SMA 200. */
export function kurslage(a:[string,number][]):{rsi14:number;sma200:number;abstand:number}|null{
 let k=a.length-1;while(k>0&&Date.parse(a[k][0])-Date.parse(a[k-1][0])<=14*86400000)k--;
 const z=a.slice(k).map(x=>x[1]);if(z.length<SMA_TAGE)return null;
 let auf=0,ab=0;for(let i=1;i<=RSI_TAGE;i++){const d=z[i]-z[i-1];if(d>0)auf+=d;else ab-=d}auf/=RSI_TAGE;ab/=RSI_TAGE;
 for(let i=RSI_TAGE+1;i<z.length;i++){const d=z[i]-z[i-1];auf=(auf*(RSI_TAGE-1)+Math.max(d,0))/RSI_TAGE;ab=(ab*(RSI_TAGE-1)+Math.max(-d,0))/RSI_TAGE}
 const rsi14=ab===0?(auf===0?50:100):100-100/(1+auf/ab);
 const sma200=z.slice(-SMA_TAGE).reduce((x,y)=>x+y,0)/SMA_TAGE;
 return {rsi14:Math.round(rsi14*10)/10,sma200,abstand:z.at(-1)!/sma200-1};
}
export function historyStatistics(h:Row|null,now=Date.now()):Row{
 const empty=(error:string)=>({observations:0,first:'',last:'',error,es:null,dd:null,worst:null,vol:null,drawdown:null});
 if(!h)return empty('Bereinigte Kurshistorie fehlt.');
 if(h.format==='risk-summary'){
  const s=h.statistics,validDate=(v:any)=>typeof v==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(v)&&Number.isFinite(Date.parse(v));
  const fraction=(v:any)=>v===null||typeof v==='number'&&Number.isFinite(v)&&v>=0&&v<=1;
  const short=s?.shortHistory===true;
  if(h.schema!==RISK_SCHEMA||h.adjustment!=='total_return'||!s||!Number.isInteger(s.observations)||s.observations<1||!validDate(s.first)||!validDate(s.last)||s.first>s.last||typeof s.error!=='string'||![s.es,s.dd,s.worst,s.drawdown].every(fraction)||!(s.shortHistory===undefined||s.shortHistory===true)||short&&(s.observations<SHORT_OBSERVATIONS||s.observations>=FULL_OBSERVATIONS||!!s.error||s.dd!==null||s.worst!==null)||s.observations<FULL_OBSERVATIONS&&!short&&[s.es,s.dd,s.worst].some(v=>v!==null)||s.observations<200&&s.drawdown!==null||s.error&&[s.es,s.dd,s.worst].some(v=>v!==null)||!(s.vol===undefined||s.vol===null||typeof s.vol==='number'&&Number.isFinite(s.vol)&&s.vol>=0&&s.vol<=5)||(s.observations<FULL_OBSERVATIONS&&!short||s.error)&&typeof s.vol==='number')return empty('Ungültige vorberechnete Risikodaten.');
  // Abschnitt nach Lücke: Kennzeichnung muss stimmig sein, größter Rückgang und 20-Tage-Phase offen.
  if(s.rsi14!==undefined&&!(typeof s.rsi14==='number'&&s.rsi14>=0&&s.rsi14<=100))return empty('Ungültige vorberechnete Risikodaten.');
  if(s.sma200Abstand!==undefined&&!(typeof s.sma200Abstand==='number'&&Number.isFinite(s.sma200Abstand)&&s.sma200Abstand>-1&&s.sma200Abstand<20))return empty('Ungültige vorberechnete Risikodaten.');
  const g=s.historySegment;
  if(g!==undefined&&!(g&&typeof g==='object'&&g.from===s.first&&Number.isInteger(g.pauseDays)&&g.pauseDays>14&&Number.isInteger(g.droppedObservations)&&g.droppedObservations>=1&&s.dd===null&&s.worst===null&&!s.error&&s.observations>=SHORT_OBSERVATIONS))return empty('Ungültige vorberechnete Risikodaten.');
  if(Date.parse(s.last)>=new Date(now).setUTCHours(0,0,0,0)||now-Date.parse(s.last)>7*86400000)return {...s,error:'Letzter Kurs nicht aktuell oder in der Zukunft.',es:null,dd:null,worst:null,vol:null,drawdown:null,rsi14:null,sma200Abstand:null};
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
 // Kurslage (seit 26.11.2026, Entscheidung des Nutzers; nur Anzeige, kein Score): RSI 14 nach Wilder und Abstand zum
 // 200-Tage-Durchschnitt, aus den letzten lückenlosen Kursen (dividendenbereinigt wie die übrige Statistik).
 if(!basic){const k=kurslage(a);if(k){s.rsi14=k.rsi14;s.sma200=k.sma200;s.sma200Abstand=k.abstand}}
 // Abschnitt nach der letzten Lücke (seit 23.11.2026, Entscheidung des Nutzers; Anlass Nebius: Handel 02/2022 bis 10/2024
 // ausgesetzt): Hat der lückenlose Abschnitt nach der letzten Lücke > 14 Tage mindestens ein Handelsjahr, rechnen
 // Volatilität und Expected Shortfall auf diesem Abschnitt, gekennzeichnet (historySegment). Größter Rückgang und
 // schlechteste 20-Tage-Phase bleiben offen: Der Verlust vor oder während der Pause fehlt in den Daten.
 let seg:{from:string;pauseDays:number;droppedObservations:number}|null=null;
 if(!basic&&gaps(a)){let k=0;for(let i=1;i<a.length;i++)if(Date.parse(a[i][0])-Date.parse(a[i-1][0])>14*86400000)k=i;
  if(a.length-k>=SHORT_OBSERVATIONS){seg={from:a[k][0],pauseDays:Math.round((Date.parse(a[k][0])-Date.parse(a[k-1][0]))/86400000),droppedObservations:k};a.splice(0,k);s.observations=a.length;s.first=a[0][0];s.historySegment=seg}}
 s.error=basic||(a.length<SHORT_OBSERVATIONS?'Weniger als ein Handelsjahr vorhanden.':gaps(a)?'Kurshistorie enthält längere Lücken.':'');
 const short=!s.error&&a.length<FULL_OBSERVATIONS;if(short)s.shortHistory=true;
 if(!s.error){const raw=a.slice(1).map((b,i)=>b[1]/a[i][1]-1),last=raw.slice(-252),mean=last.reduce((x,y)=>x+y,0)/last.length;s.vol=Math.sqrt(last.reduce((x,y)=>x+(y-mean)**2,0)/(last.length-1)*252);const returns=[...raw].sort((a,b)=>a-b),tail=returns.slice(0,Math.max(1,Math.floor(returns.length*.05)));s.es=Math.max(0,-tail.reduce((a,b)=>a+b,0)/tail.length);
  if(!short&&!seg){let peak=a[0][1];s.dd=0;s.worst=0;a.forEach((b,i)=>{peak=Math.max(peak,b[1]);s.dd=Math.max(s.dd,1-b[1]/peak);if(i>=20)s.worst=Math.max(s.worst,1-b[1]/a[i-20][1])})}}
 return s;
}
export function compactHistory(h:Row,now=Date.now()){
 return {format:'risk-summary',schema:RISK_SCHEMA,symbol:h.symbol,currency:h.currency,adjustment:h.adjustment,retrievedAt:h.retrievedAt,requestedFrom:h.requestedFrom,requestedYears:h.requestedYears,historyNote:h.historyNote,provider:h.provider,statistics:historyStatistics(h,now),...(h.proxy?{proxy:h.proxy,region:h.region,note:h.note}:{})};
}
