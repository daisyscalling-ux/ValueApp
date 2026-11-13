// Messung Datenweg (Schritt 2, 13.11.2026): Fuer eine feste Stichprobe des Universums dasselbe Rohdaten-Bundle wie die
// Einzelanalyse abrufen (worker/bundle-fetch.ts, Kopie aus valueapp-cf), mit bundleLight zum Fund formen und mit demselben
// Rechenweg bewerten (scannerFields). Vergleich mit den Scanner-Zeilen in cf_universum.json: Eingaenge und Ergebnisse.
// Nur Messung, schreibt nichts in die Daten. Aufruf: node bundle-compare.mjs <daten-ordner> <ausgabe.json> [anzahl]
import fs from 'node:fs';import path from 'node:path';import {createHash} from 'node:crypto';
import {fetchRawBundle} from './worker/bundle-fetch';
import {bundleLight} from './src/lib/roic';
import {scannerFields} from './src/lib/scanner-evaluation';
import {selectPeers} from './src/lib/peer-selection';
import {safeUniverse} from './src/lib/listing-identity';
import {healthDistributionFromRows} from './src/lib/financial-health';
type Row=Record<string,any>;
const [folder,output,count]=process.argv.slice(2);const n=Number(count||50);
const read=(name:string)=>JSON.parse(fs.readFileSync(path.join(folder,name),'utf8'));
const universe=safeUniverse(read('cf_universum.json').kandidaten||[]) as Row[];
const coverage=new Map<string,Row>(((read('cf_risk_coverage.json').stocks)||[]).map((r:Row)=>[r.symbol,{balance:r.domains?.balance}]));
const dist=healthDistributionFromRows(universe);
// Feste, reproduzierbare Stichprobe: nach SHA-256 der Notierung sortiert
const sample=universe.filter(r=>typeof r.listing_symbol==='string'&&r.scanner_method==='ts-evaluate-v1')
 .map(r=>({r,k:createHash('sha256').update(r.listing_symbol).digest('hex')})).sort((a,b)=>a.k.localeCompare(b.k)).slice(0,n).map(x=>x.r);
const prepared=async(sym:string)=>{const p=path.join(folder,'fundamentals',sym.replace(/[^A-Za-z0-9._-]/g,'_')+'.json');try{const s=JSON.parse(fs.readFileSync(p,'utf8'));return s?.schema===1&&s.symbol===sym?s:null}catch{return null}};
const env={ROIC_API_KEY:process.env.ROIC_API_KEY,FINNHUB_API_KEY:process.env.FINNHUB_API_KEY,FMP_API_KEY:process.env.FMP_API_KEY};
// Eingaenge im Universum (Prozentfelder des Exports) gegen das App-Bundle in gleicher Einheit
const INPUTS:[string,(f:Row)=>number|null,(u:Row)=>number|null][]=[
 ['price',f=>f.price,u=>u.price],['52w_high',f=>f['52w_high'],u=>u['52w_high']],['52w_low',f=>f['52w_low'],u=>u['52w_low']],
 ['eps_trailing',f=>f.eps_trailing,u=>u.eps_trailing],['eps_forward',f=>f.eps_forward,u=>u.eps_forward],['target_mean',f=>f.target_mean,u=>u.target_mean],
 ['revenue_growth_pct',f=>typeof f.revenue_growth==='number'?f.revenue_growth*100:null,u=>u.revenue_growth],['roe_pct',f=>typeof f.roe==='number'?f.roe*100:null,u=>u.roe],
 ['ev_ebitda',f=>f.ev_ebitda,u=>u.ev_ebitda],['market_cap',f=>f.market_cap,u=>u.market_cap]];
const OUTPUTS=['playbook','composite','fair_value','upside','quantum','target_12m','health','kauf_urteil'];
const rel=(a:any,b:any)=>typeof a==='number'&&typeof b==='number'&&Number.isFinite(a)&&Number.isFinite(b)&&b!==0?Math.abs(a/b-1):null;
(async()=>{
 const rows:Row[]=[];
 for(const u of sample){
  const sym=u.listing_symbol;
  try{
   const raw=await fetchRawBundle(sym,env,{prepared},fetch);
   // Leere ROIC-Bloecke getrennt zaehlen: Abrufgrenze oder Ausfall, keine echte Datenluecke der App.
   const roicEmpty=['profile','quote','enterprise_value','ratios','liquidity','multiples','income','balance','cashflow'].filter(k=>(raw as Row)[k]==null);
   const fund=bundleLight(raw as any) as Row;fund.ticker=sym;fund._roic_empty=roicEmpty;
   if(!(typeof fund.price==='number'&&fund.price>0))throw new Error('Kein Kurs im App-Bundle (Abruf fehlgeschlagen oder Notierung unbekannt)');
   const peers=selectPeers(u,universe);
   const app=scannerFields(fund as any,peers,coverage.get(sym)??null,dist) as Row;
   const inputs=Object.fromEntries(INPUTS.map(([k,fa,fu])=>[k,{app:fa(fund)??null,scanner:fu(u)??null,relDiff:rel(fa(fund),fu(u))}]));
   const outputs=Object.fromEntries(OUTPUTS.map(k=>[k,{app:app[k]??null,scanner:u[k]??null}]));
   rows.push({symbol:sym,inputs,outputs,appBlocked:app.kauf_urteil==='Daten prüfen',appIssues:app.valuation_issues,roicEmpty:fund._roic_empty});
  }catch(e){rows.push({symbol:sym,error:String(e).slice(0,200)})}
  // 4,5 s je Titel: ROIC 9 Abrufe (120/min, Plan 300/min, Rest fuer parallele Laeufe), Finnhub 4 Abrufe (53/min, Grenze 60/min).
  // Der erste Lauf (13.11.2026, 1,1 s, parallel zu precompute) lief in Abrufgrenzen; Felder fehlten dadurch scheinbar.
  await new Promise(r=>setTimeout(r,4500));
 }
 const ok=rows.filter(r=>!r.error),q=(xs:number[],p:number)=>{const s=[...xs].sort((a,b)=>a-b);return s.length?s[Math.floor(p*(s.length-1))]:null};
 const inputSummary=Object.fromEntries(INPUTS.map(([k])=>{const d=ok.map(r=>r.inputs[k].relDiff).filter((x:any)=>x!==null) as number[];
  return [k,{compared:d.length,appOnly:ok.filter(r=>r.inputs[k].app!==null&&r.inputs[k].scanner===null).length,scannerOnly:ok.filter(r=>r.inputs[k].app===null&&r.inputs[k].scanner!==null).length,medianRel:q(d,.5),p90Rel:q(d,.9),over10pct:d.filter(x=>x>.1).length}]}));
 const num=(k:string)=>{const d=ok.map(r=>[r.outputs[k].app,r.outputs[k].scanner]).filter(([a,b])=>typeof a==='number'&&typeof b==='number').map(([a,b])=>k==='fair_value'||k==='target_12m'?Math.abs(a/b-1)*100:Math.abs(a-b));return {compared:d.length,median:q(d,.5),p90:q(d,.9)}};
 const outputSummary={composite:num('composite'),fair_value_pct:num('fair_value'),upside_pp:num('upside'),quantum:num('quantum'),target_12m_pct:num('target_12m'),health:num('health'),
  playbookDiffers:ok.filter(r=>r.outputs.playbook.app!==r.outputs.playbook.scanner).length,verdictDiffers:ok.filter(r=>r.outputs.kauf_urteil.app!==r.outputs.kauf_urteil.scanner).length,
  appBlocked:ok.filter(r=>r.appBlocked).length,scannerBlocked:ok.filter(r=>r.outputs.kauf_urteil.scanner==='Daten prüfen').length,
  titlesWithEmptyRoicBlocks:ok.filter(r=>(r.roicEmpty||[]).length).length};
 const report={schema:1,method:'bundle-vs-scanner-v1',generatedAt:new Date().toISOString(),sample:sample.length,fetched:ok.length,errors:rows.length-ok.length,inputSummary,outputSummary,rows};
 fs.writeFileSync(output,JSON.stringify(report,null,1));
 console.log(JSON.stringify({sample:report.sample,fetched:report.fetched,errors:report.errors,outputSummary},null,1));
})();
