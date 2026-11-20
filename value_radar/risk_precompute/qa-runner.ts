// QA-Lauf der Einzelanalyse (QA-EINZELANALYSE.md, Phase 2, seit 20.11.2026). Für jeden Universumstitel dasselbe Rohdaten-
// Bundle wie die App (worker/bundle-fetch.ts), bundleLight, evaluateStock mit Peers und Branchenprüfung wie die Einzelanalyse,
// dann qaChecks (App-Kopie). Schreibt daten/qa/qa_einzelanalyse.json für den App-Tab „QA“. Nur Meldung, keine Änderung an Daten.
// Aufruf: node qa-runner.mjs <daten-ordner> <ausgabe.json> [anzahl|alle]
import fs from 'node:fs';import path from 'node:path';
import {fetchRawBundle} from './worker/bundle-fetch';
import {bundleLight} from './src/lib/roic';
import {evaluateStock} from './src/lib/evaluation';
import {selectPeers} from './src/lib/peer-selection';
import {safeUniverse} from './src/lib/listing-identity';
import {healthDistributionFromRows} from './src/lib/financial-health';
import {qaChecks,qaSummary,QA_METHOD,QA_LIMITS,type QaBefund} from './src/lib/qa-checks';
type Row=Record<string,any>;
export const QA_RUNNER_METHOD='qa_runner_v1';
const EUROPA=new Set(['DE','FR','CH','SE','IT','NL','ES','DK','NO','PL','FI','BE','GR','AT','IE','PT','LU','CZ','HU']);
export const region=(c:unknown)=>c==='US'||c==='United States'?'USA':c==='JP'?'Japan':c==='GB'?'Grossbritannien':EUROPA.has(String(c))?'Europa ohne GB':'sonstige';
/** Zusammenfassung je Gruppe (Region, Profil). */
export function nachGruppe(ergebnisse:{gruppe:string;befunde:QaBefund[]}[]){const out:Record<string,ReturnType<typeof qaSummary>>={};
 const g=new Map<string,QaBefund[][]>();for(const e of ergebnisse){if(!g.has(e.gruppe))g.set(e.gruppe,[]);g.get(e.gruppe)!.push(e.befunde)}for(const [k,v] of g)out[k]=qaSummary(v);return out}

async function main(){
 const [folder,output,count]=process.argv.slice(2);
 const read=(name:string)=>JSON.parse(fs.readFileSync(path.join(folder,name),'utf8'));
 const uni=read('cf_universum.json');const universe=safeUniverse(uni.kandidaten||[]) as Row[];
 const coverage=new Map<string,Row>(((read('cf_risk_coverage.json').stocks)||[]).map((r:Row)=>[r.symbol,{balance:r.domains?.balance}]));
 const dist=healthDistributionFromRows(universe);
 const titel=universe.filter(r=>typeof r.listing_symbol==='string').sort((a,b)=>a.listing_symbol.localeCompare(b.listing_symbol));
 const auswahl=count&&count!=='alle'?titel.slice(0,Number(count)):titel;
 const prepared=async(sym:string)=>{const p=path.join(folder,'fundamentals',sym.replace(/[^A-Za-z0-9._-]/g,'_')+'.json');try{const s=JSON.parse(fs.readFileSync(p,'utf8'));return s?.schema===1&&s.symbol===sym?s:null}catch{return null}};
 const env={ROIC_API_KEY:process.env.ROIC_API_KEY,FINNHUB_API_KEY:process.env.FINNHUB_API_KEY,FMP_API_KEY:process.env.FMP_API_KEY};
 const ergebnisse:{symbol:string;name:string;region:string;profil:string;befunde:QaBefund[]}[]=[],abrufFehler:{symbol:string;grund:string}[]=[];
 const start=Date.now(),budgetMs=Number(process.env.QA_BUDGET_MIN||150)*60000;
 for(const u of auswahl){
  if(Date.now()-start>budgetMs){abrufFehler.push({symbol:u.listing_symbol,grund:'Zeitbudget erreicht'});continue}
  const sym=u.listing_symbol;
  try{
   const raw=await fetchRawBundle(sym,env,{prepared},fetch) as Row;
   const fund=bundleLight(raw as any) as Row;fund.ticker=sym;
   if(!(typeof fund.price==='number'&&fund.price>0))throw new Error('Kein Kurs im App-Bundle');
   // Wie die Einzelanalyse: Zyklik aus der Universumszeile, Cash-Conversion aus der Branchenprüfung, Peers aus dem Universum.
   fund._cyclicality=u.cyclicality??null;const cov=coverage.get(sym)??null;if(cov?.balance)fund._cash_conversion_history=cov.balance.cashConversion??null;
   const ev=evaluateStock(fund as any,null,selectPeers(u,universe),cov,dist) as any;
   ergebnisse.push({symbol:sym,name:String(u.name??sym),region:region(u.country),profil:String(cov?.balance?.profile??'corporate'),befunde:qaChecks({raw,ev,universeRow:u})});
  }catch(e){abrufFehler.push({symbol:sym,grund:String(e instanceof Error?e.message:e).slice(0,160)})}
  // 4,5 s je Titel wie bundle-compare (ROIC- und Finnhub-Grenzen, nicht parallel zu precompute)
  await new Promise(r=>setTimeout(r,Number(process.env.QA_PAUSE_MS??4500)));
 }
 let vorher=null;try{const alt=JSON.parse(fs.readFileSync(output,'utf8'));if(alt?.method===QA_METHOD)vorher={generatedAt:alt.generatedAt,summary:alt.summary}}catch{}
 const befunde=ergebnisse.flatMap(e=>e.befunde.filter(b=>b.status!=='ok').map(b=>({symbol:e.symbol,name:e.name,region:e.region,profil:e.profil,...b})));
 const bericht={schema:1,method:QA_METHOD,runner:QA_RUNNER_METHOD,generatedAt:new Date().toISOString(),stand:uni.stand,titel:auswahl.length,abgerufen:ergebnisse.length,abrufFehler,limits:QA_LIMITS,
  summary:qaSummary(ergebnisse.map(e=>e.befunde)),nachRegion:nachGruppe(ergebnisse.map(e=>({gruppe:e.region,befunde:e.befunde}))),nachProfil:nachGruppe(ergebnisse.map(e=>({gruppe:e.profil,befunde:e.befunde}))),befunde,vorher};
 fs.mkdirSync(path.dirname(output),{recursive:true});fs.writeFileSync(output,JSON.stringify(bericht)+'\n');
 const kurz=Object.fromEntries(Object.entries(bericht.summary).map(([k,v])=>[k,`${v.fehler} F · ${v.auffaellig} A · ${v.offen} O · ${v.ok} ok`]));
 console.log(JSON.stringify({titel:bericht.titel,abgerufen:bericht.abgerufen,abrufFehler:abrufFehler.length,summary:kurz},null,1));
}
if(process.argv[1]?.endsWith('qa-runner.mjs'))main();
