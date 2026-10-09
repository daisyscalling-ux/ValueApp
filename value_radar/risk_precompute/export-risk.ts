import fs from 'node:fs';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {riskHistory} from './worker/risk-data';
import {benchmarkHistory} from './worker/risk-benchmark';
import {resolveCompany} from './worker/company-data';
import {compactHistory,historyStatistics,RISK_SCHEMA} from './src/lib/risk-statistics';
const read=(file:string)=>{try{return JSON.parse(fs.readFileSync(file,'utf8'))}catch{return null}};
export async function exportRisk(options:any={}){
 const env=options.env||process.env,fetcher=options.fetcher||fetch,clock=options.clock||Date.now;
 if(!env.ROIC_API_KEY)throw Error('ROIC_API_KEY fehlt.');
 const input=env.RISK_UNIVERSE_PATH||'value_radar/daten/cf_universum.json',output=env.RISK_OUTPUT_PATH||'value_radar/daten/cf_risk.json';
 const universe=read(input);if(!Array.isArray(universe?.kandidaten)||!universe.kandidaten.length)throw Error('Universum fehlt oder ist leer.');
 const budget=Number(env.RISK_BUDGET_MIN||90);if(!Number.isFinite(budget)||budget<1||budget>110)throw Error('Ungültiges Zeitbudget.');
 const previous=read(output),data:any=previous?.schema===RISK_SCHEMA?previous:{schema:RISK_SCHEMA,stocks:{},benchmarks:{}};
 data.attempts=data.attempts||{};
 const inputs=[...new Set<string>(universe.kandidaten.map((r:any)=>String(r.listing_symbol||r.ticker||'').trim().toUpperCase()).filter((s:string)=>/^[A-Z0-9._:-]{1,100}$/.test(s)))];
 inputs.sort((a,b)=>(Date.parse(data.attempts[a])||0)-(Date.parse(data.attempts[b])||0));
 const started=clock(),deadline=started+budget*60000;let last=0,requests=0,aborted=false;
 const report:any={attempted:0,updated:0,failed:0,skippedFresh:0,universe:inputs.length,errors:[],budgetReached:false};
 const save=()=>{data.generatedAt=new Date(clock()).toISOString();data.report={...report,requests};fs.mkdirSync(path.dirname(output),{recursive:true});fs.writeFileSync(output+'.tmp',JSON.stringify(data));fs.renameSync(output+'.tmp',output)};
 const paced:typeof fetch=async(url,opts)=>{
  if(clock()>deadline)throw Error('Zeitbudget erreicht.');
  const wait=Math.max(0,650-(clock()-last));if(wait)await new Promise(r=>setTimeout(r,wait));
  opts?.signal?.throwIfAborted();last=clock();requests++;
  const r=await fetcher(url,opts);if([401,403].includes(r.status)){aborted=true;throw Error('ROIC-Zugang abgelehnt HTTP '+r.status)}
  if(r.status===429){await new Promise(r=>setTimeout(r,30000));throw Error('ROIC-Ratenlimit HTTP 429')}
  return r;
 };
 const fresh=(v:any)=>v?.schema===RISK_SCHEMA&&clock()-Date.parse(v.retrievedAt)>=0&&clock()-Date.parse(v.retrievedAt)<18*3600000;
 const accept=(h:any)=>{const s=compactHistory(h,clock()),v=historyStatistics(s,clock());if(!v.observations||[v.es,v.dd,v.worst,v.drawdown].every(x=>x===null))throw Error('Keine gültige Risiko-Historie');return s};
 const failure=(symbol:string,e:any)=>{report.failed++;if(report.errors.length<100)report.errors.push({symbol,reason:/^(ROIC|Kurshistorie|Notierung|Markt|Keine|Zeitbudget|Eindeutige|Ungültige)/.test(e?.message||'')?e.message:'Abruf fehlgeschlagen'});};
 for(const country of ['US','DE','JP','GB','FR','HK','IN','CN','KR','TW']){
  if(clock()>deadline||aborted)break;
  try{const h=await benchmarkHistory(country,env.ROIC_API_KEY,paced);data.benchmarks[h.proxy]=accept(h)}catch(e){failure('Markt '+country,e)}
 }
 let processed=0;
 for(const inputSymbol of inputs){
  if(clock()>deadline||aborted){report.budgetReached=clock()>deadline;break}
  processed++;data.attempts[inputSymbol]=new Date(clock()).toISOString();
  if(fresh(data.stocks[inputSymbol])){report.skippedFresh++;continue}
  report.attempted++;
  try{const symbol=inputSymbol.includes(':')?inputSymbol:String((await resolveCompany(inputSymbol,env.ROIC_API_KEY,paced)).symbol);
   if(fresh(data.stocks[symbol])){report.skippedFresh++;continue}
   data.stocks[symbol]=accept(await riskHistory(symbol,env.ROIC_API_KEY,paced,clock()));report.updated++;
  }catch(e){failure(inputSymbol,e)}
  if(processed%25===0){save();console.log('Risiko: '+processed+'/'+inputs.length+' geprüft; '+report.updated+' aktualisiert; '+report.failed+' fehlgeschlagen.')}
 }
 report.remaining=inputs.length-processed;report.accessDenied=aborted;save();
 console.log(JSON.stringify(data.report));if(report.failed||report.remaining)console.log('::warning::Risikodaten teilweise offen; Bericht in cf_risk.json prüfen. Alte Stände bleiben datiert erhalten.');
 return {ok:!aborted&&(report.updated>0||report.skippedFresh>0),report:data.report};
}
if(process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href){exportRisk().then(r=>{if(!r.ok)process.exitCode=1}).catch(()=>{console.error('Risikoexport abgebrochen: Eingabe, Konfiguration oder Dateizugriff prüfen.');process.exitCode=1})}
