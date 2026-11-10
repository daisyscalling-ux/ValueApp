// Heimatnotierungen ausserhalb des Universums fuer den Kursrisiko-Ersatz.
// Fehlt einer Notierung eine verwertbare eigene Kurshistorie und steht keine Heimatnotierung derselben ISIN im
// Universum, sucht dieses Programm ueber die ROIC-Ticker-Suche genau eine Hauptnotierung (keine OTC-Linie,
// Wertpapierart Aktie) mit exakt derselben ISIN und laedt deren Historie. Ablage in cf_risk.json unter
// homeListings; risk_history_proxy.py verwendet sie wie eine Heimatnotierung aus dem Universum.
import fs from 'node:fs';
import {pathToFileURL} from 'node:url';
import {riskHistory} from './worker/risk-data';
import {compactHistory,historyStatistics,RISK_SCHEMA} from './src/lib/risk-statistics';
type Row=Record<string,any>;
const MIN_OBSERVATIONS=505,DAY=86400000,RESOLVE_DAYS=7,FRESH_HOURS=18;
const ISIN=/^[A-Z]{2}[A-Z0-9]{9}[0-9]$/;
const read=(file:string)=>{try{return JSON.parse(fs.readFileSync(file,'utf8'))}catch{return null}};
const usable=(h:any,now:number)=>{const s=h?.statistics||{};const age=now-Date.parse(h?.retrievedAt);
 return h?.format==='risk-summary'&&!h.historySource&&!s.error&&Number.isInteger(s.observations)&&s.observations>=MIN_OBSERVATIONS&&s.es!=null&&age>=0&&age<=36*3600000};

// Notierungen ohne verwertbare eigene Historie, deren ISIN keine verwertbare Heimatnotierung im Universum hat.
export function targets(universe:Row,risk:Row,now:number){
 const rows=(universe?.kandidaten||[]).filter((r:Row)=>typeof r.listing_symbol==='string'&&ISIN.test(r.isin||''));
 const homeInUniverse=new Set<string>();
 for(const r of rows)if(!r.listing_symbol.startsWith('OTC:')&&usable(risk?.stocks?.[r.listing_symbol],now))homeInUniverse.add(r.isin);
 const out=new Map<string,Row>();
 for(const r of rows){
  if(usable(risk?.stocks?.[r.listing_symbol],now)||homeInUniverse.has(r.isin))continue;
  const t=out.get(r.isin)||{isin:r.isin,name:r.name,tickers:new Set<string>(),listings:[]};
  t.tickers.add(String(r.listing_symbol.split(':').pop()));t.listings.push(r.listing_symbol);out.set(r.isin,t);
 }
 return [...out.values()];
}

// Genau eine Hauptnotierung derselben ISIN: keine OTC-Linie, Aktie, nicht delistet.
export function chooseHome(isin:string,candidates:Row[],exclude:Set<string>){
 const ok=candidates.filter(c=>c&&c.isin===isin&&typeof c.symbol==='string'&&/^[A-Z0-9_-]+:[A-Z0-9._-]+$/i.test(c.symbol)
  &&!c.symbol.toUpperCase().startsWith('OTC:')&&c.type==='stock'&&c.status!=='delisted'&&!exclude.has(c.symbol));
 // Nur die Hauptnotierung: Regional- oder Zweitboersen liefern oft luecken- oder sprunghafte Kurse.
 const primary=[...new Map(ok.filter(c=>c.is_primary===true).map(c=>[c.symbol,c])).values()];
 return primary.length===1?primary[0]:null;
}

async function search(query:string,key:string,fetcher:typeof fetch){
 const r=await fetcher('https://api.roic.ai/v3.0.0/tickers/search?query='+encodeURIComponent(query),{headers:{Authorization:'Bearer '+key},signal:AbortSignal.timeout(12000),redirect:'error'});
 if(!r.ok)throw Error('ROIC-Symbolsuche HTTP '+r.status);
 const d=await r.json() as any;return Array.isArray(d)?d:Array.isArray(d?.data)?d.data:[];
}

export async function exportHomeHistories(options:Row={}){
 const env=options.env||process.env,fetcher:typeof fetch=options.fetcher||fetch,clock=options.clock||Date.now,sleep=options.sleep||((ms:number)=>new Promise(r=>setTimeout(r,ms)));
 if(!env.ROIC_API_KEY)throw Error('ROIC_API_KEY fehlt.');
 const universePath=env.RISK_UNIVERSE_PATH||'value_radar/daten/cf_universum.json',riskPath=env.RISK_OUTPUT_PATH||'value_radar/daten/cf_risk.json';
 const universe=read(universePath),risk=read(riskPath);
 if(!Array.isArray(universe?.kandidaten)||risk?.schema!==RISK_SCHEMA)throw Error('Universum oder Risikodatei fehlt.');
 const now=clock(),deadline=now+Number(env.HOME_HISTORY_BUDGET_MIN||8)*60000,gap=Number(env.HOME_HISTORY_GAP_MS||400);
 risk.homeListings=risk.homeListings||{};risk.homeResolution=risk.homeResolution||{};
 const universeSymbols=new Set<string>(universe.kandidaten.map((r:Row)=>r.listing_symbol).filter(Boolean));
 const list=targets(universe,risk,now);
 const report:Row={targets:list.length,resolved:0,unresolved:0,cachedResolution:0,updated:0,fresh:0,failed:0,errors:[] as string[],budgetReached:false};
 const wanted=new Set<string>();
 for(const t of list){
  if(clock()>deadline){report.budgetReached=true;break}
  let res=risk.homeResolution[t.isin];
  if(!(res&&now-Date.parse(res.at)>=0&&now-Date.parse(res.at)<RESOLVE_DAYS*DAY)){
   let home:Row|null=null;const queries=[t.isin,...t.tickers,String(t.name||'').split(/[,.(]/)[0].trim()].filter(q=>q&&q.length>=2);
   try{for(const q of queries){const c=await search(q,env.ROIC_API_KEY,fetcher);await sleep(gap);home=chooseHome(t.isin,c,universeSymbols);if(home)break}
    res={at:new Date(now).toISOString(),symbol:home?.symbol||null,exchange:home?.exchange||null,isPrimary:home?.is_primary===true,queries:queries.length,source:'ROIC v3 tickers/search · exact ISIN'};
    risk.homeResolution[t.isin]=res;
   }catch(e){report.failed++;report.errors.push(t.isin+': '+String((e as Error).message).slice(0,80));continue}
  }else report.cachedResolution++;
  if(!res.symbol){report.unresolved++;continue}
  report.resolved++;wanted.add(res.symbol);
  const old=risk.homeListings[res.symbol];
  if(old&&old.isin===t.isin&&now-Date.parse(old.retrievedAt)>=0&&now-Date.parse(old.retrievedAt)<FRESH_HOURS*3600000){old.homeOf=t.listings;report.fresh++;continue}
  try{const h=await riskHistory(res.symbol,env.ROIC_API_KEY,fetcher,now,5);await sleep(gap);
   const s=compactHistory(h,now),v=historyStatistics(s,now);
   if(v.error||!v.observations)throw Error('Historie unbrauchbar: '+(v.error||'leer'));
   risk.homeListings[res.symbol]={...s,isin:t.isin,homeOf:t.listings,resolvedAt:res.at};report.updated++;
  }catch(e){report.failed++;report.errors.push(res.symbol+': '+String((e as Error).message).slice(0,80));if(old&&old.isin===t.isin)old.homeOf=t.listings}
 }
 // Heimatnotierungen ohne Zielnotierung entfernen (eigene Historie wieder da oder Notierung nicht mehr im Universum).
 if(!report.budgetReached)for(const k of Object.keys(risk.homeListings))if(!wanted.has(k))delete risk.homeListings[k];
 risk.homeListingsReport={...report,errors:report.errors.slice(0,20),generatedAt:new Date(clock()).toISOString()};
 fs.writeFileSync(riskPath+'.tmp',JSON.stringify(risk));fs.renameSync(riskPath+'.tmp',riskPath);
 console.log(JSON.stringify(risk.homeListingsReport));
 return report;
}
if(process.env.RISK_EXPORT_LIBRARY!=='1'&&process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href){
 exportHomeHistories().catch(e=>{console.error('Heimatnotierungen: '+String(e?.message||e));process.exitCode=1});
}
