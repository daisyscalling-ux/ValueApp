import {historyStatistics} from './risk-statistics';
type Row=Record<string,any>;
export function currentDrawdown(h:Row|null,now=Date.now()):number|null{return historyStatistics(h,now).drawdown}
// Land fuer den Marktvergleich: Profilland, sonst das Land der Universumszeile (wie die Pipeline in universe-coverage.ts).
// row ist die unveraenderte Universumszeile aus /api/peers (universeRow, ohne Anfragewerte). Sie zaehlt nur bei gleicher
// Notierung (fund.ticker = listing_symbol, z. B. NASDAQ:MU) oder gleicher ISIN; ein aehnlicher Name genuegt nie.
export function marketCountry(fund:Row,row:Row|null|undefined):string{
 const own=String(fund?.country??'').trim();if(own)return own;
 if(!row||typeof row!=='object')return '';
 const up=(v:unknown)=>String(v??'').trim().toUpperCase();
 const listing=up(fund?.ticker).includes(':')&&up(fund?.ticker)===up(row.listing_symbol);
 const isin=/^[A-Z]{2}[A-Z0-9]{9}[0-9]$/.test(up(fund?.isin))&&up(fund?.isin)===up(row.isin);
 return listing||isin?String(row.country??'').trim():'';
}
export function contextMetrics(market:Row|null,peers:Row[],now=Date.now()){
 const m=currentDrawdown(market,now);const seen=new Set<string>();const usable=peers.filter(p=>p.symbol&&!seen.has(p.symbol)&&(seen.add(p.symbol),true)).map(p=>currentDrawdown(p,now)).filter((x):x is number=>x!==null).sort((a,b)=>a-b);
 const median=usable.length>=3?(usable[Math.floor(usable.length/2)]+usable[Math.floor((usable.length-1)/2)])/2:null;
 const item=(name:string,weight:number,value:number|null,reason:string)=>({name,weight,score:value===null?null:Math.max(0,Math.min(100,(value-.05)/.30*100)),value:value===null?'—':(value*100).toFixed(1)+' %',reason});
 return [item('Marktumfeld · Abstand zum Jahreshoch',10,m,market?.proxy?market.proxy+' · '+market.note:'Passender bereinigter Marktvergleich fehlt.'),item('Peer-Stress · mittlerer Abstand zum Jahreshoch',5,median,usable.length+' verwertbare direkte Peers; mindestens 3 erforderlich. Kleine Stichprobe, kein vollständiger Branchenindex.')];
}
const rules:[string,RegExp][]=[['Wettbewerb',/competit|price war|preiskrieg|new entrant|starlink|spacex|wettbewerb/i],['Finanzierung',/default|bankrupt|liquidity crisis|debt matur|insolvenz|zahlungsunfähig|refinanc/i],['Regulierung',/antitrust|sanction|regulat|kartell|export ban|exportverbot/i],['Betrieb',/cyberattack|data breach|recall|outage|rückruf|produktionsstopp/i],['Ertrag',/profit warning|cuts? (?:its )?(?:outlook|forecast|guidance)|gewinnwarnung|senkt.*prognose|margin pressure/i]];
export function eventCandidates(company:Row[],general:Row[],fund:Row,now=Date.now()){
 const name=String(fund.name||'').toLowerCase().replace(/[^\p{L}\p{N} ]/gu,' ').split(/\s+/).filter(x=>x.length>3&&!['corporation','company','incorporated','limited','group','holdings'].includes(x));
 const telecom=/telecom|telekommun|wireless/i.test(String(fund.industry)+' '+String(fund.sector))||/verizon|at&t|deutsche telekom|t-mobile/i.test(String(fund.name));
 const seen=new Set<string>();return [...company.map(a=>({...a,scope:'Unternehmensfeed'})),...general.map(a=>({...a,scope:'Marktfeed'}))].flatMap((a:Row)=>{const title=String(a.titel||a.title||''),date=String(a.datum||a.publishedAt||''),age=now-Date.parse(date);let u:URL;try{u=new URL(a.url)}catch{return []}if(!['http:','https:'].includes(u.protocol)||!Number.isFinite(age)||age<0||age>7*86400000)return [];
 const named=name.length>0&&name.every(n=>title.toLowerCase().includes(n));const industryLink=telecom&&/starlink|spacex/i.test(title)&&/spectrum|mobile|wireless|mobilfunk|telecom/i.test(title);
 const related=a.scope==='Unternehmensfeed'||named||industryLink;if(!related)return [];
 const relation=named?'Namensbezug in der Überschrift':industryLink?'Möglicher Branchenbezug: Satelliten- und Mobilfunkangebot':'Vom Anbieter dem Unternehmensfeed zugeordnet; direkte Betroffenheit unbestätigt';
 const category=rules.find(([,r])=>r.test(title))?.[0];if(!category)return [];const id=title.toLowerCase().replace(/[^\p{L}\p{N}]/gu,'');if(seen.has(id))return [];seen.add(id);return [{title,url:u.href,date,source:String(a.quelle||a.publisher||''),category,scope:a.scope,relation,status:'Automatisch zugeordnet · wirtschaftliche Wirkung ungeprüft'}];}).sort((a,b)=>Date.parse(b.date)-Date.parse(a.date)).slice(0,8);
}
