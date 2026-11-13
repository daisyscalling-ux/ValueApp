// Scanner-Werte aus dem App-Rechenweg (evaluateStock). Eingabe: JSON {universe:[Zeilen], funds:{ticker: fund}},
// Ausgabe: JSON {ticker: Felder|{error}}. Peers wie in der App: selectPeers ueber das (identitaetsgepruefte) Universum.
// Bilanz als Rang im Profil (financial-health.ts): erster Durchgang sammelt die Rohwerte aller frisch gerechneten Titel
// (ergaenzt um uebernommene Zeilen aus dem App-Rechenweg), zweiter Durchgang rechnet mit dieser Verteilung.
// Aufruf aus export_cf.py ueber ts_bewertung.py; gebaut im Workflow precompute-3tage mit esbuild.
import {scannerFields} from './src/lib/scanner-evaluation';
import {selectPeers} from './src/lib/peer-selection';
import {safeUniverse} from './src/lib/listing-identity';
import {financialHealth,healthProfile,type HealthDistribution} from './src/lib/financial-health';
import fs from 'node:fs';
const [input,output]=process.argv.slice(2);
const data=JSON.parse(fs.readFileSync(input,'utf8')) as {universe?:Record<string,unknown>[];funds:Record<string,any>};
const universe=safeUniverse(Array.isArray(data.universe)?data.universe:[]),byTicker=new Map(universe.map(r=>[String(r.ticker),r]));
const coverageOf=(fund:any)=>fund._risk_coverage&&typeof fund._risk_coverage==='object'?fund._risk_coverage:null;
const raw=new Map<string,{raw:number;profile:string}>();
for(const r of universe)if(r.scanner_method==='ts-evaluate-v1'&&typeof r.health_raw==='number'&&Number.isFinite(r.health_raw)&&typeof r.health_profile==='string')raw.set(String(r.ticker),{raw:r.health_raw,profile:r.health_profile});
for(const [ticker,fund] of Object.entries(data.funds??{})){
 raw.delete(ticker);
 try{const h=financialHealth(fund,coverageOf(fund)),p=healthProfile(h);if(h.score!==null&&p)raw.set(ticker,{raw:h.score,profile:p});}catch{}
}
const dist:HealthDistribution={};
for(const v of raw.values())(dist[v.profile]??=[]).push(v.raw);
const out:Record<string,unknown>={};
for(const [ticker,fund] of Object.entries(data.funds??{})){
 try{
  const row=byTicker.get(ticker);
  const peers=row?selectPeers({...row,...Object.fromEntries(['sector','industry','currency','isin','sub_industry'].filter(k=>fund[k]).map(k=>[k,fund[k]]))},universe):null;
  out[ticker]=scannerFields(fund,peers,coverageOf(fund),dist);
 }catch(e){out[ticker]={error:String(e).slice(0,200)}}
}
fs.writeFileSync(output,JSON.stringify(out));
