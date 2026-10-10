import fs from 'node:fs';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {riskHistory} from './worker/risk-data';
import {benchmarkHistory,marketProxy} from './worker/risk-benchmark';
import {validYahooBenchmark} from './yahoo-benchmark-check';
import {resolveRiskListing} from './worker/risk-listing';
import {compactHistory,historyStatistics,RISK_SCHEMA} from './src/lib/risk-statistics';
const read=(file:string)=>{try{return JSON.parse(fs.readFileSync(file,'utf8'))}catch{return null}};
export async function exportRisk(options:any={}){
 const env=options.env||process.env,fetcher=options.fetcher||fetch,clock=options.clock||Date.now;
 if(!env.ROIC_API_KEY)throw Error('ROIC_API_KEY fehlt.');
 const input=env.RISK_UNIVERSE_PATH||'value_radar/daten/cf_universum.json',output=env.RISK_OUTPUT_PATH||'value_radar/daten/cf_risk.json';
 const universe=read(input);if(!Array.isArray(universe?.kandidaten)||!universe.kandidaten.length)throw Error('Universum fehlt oder ist leer.');
 const budget=Number(env.RISK_BUDGET_MIN||90);if(!Number.isFinite(budget)||budget<1||budget>110)throw Error('Ungültiges Zeitbudget.');
 const yahoo=read(env.RISK_YAHOO_PATH||'/tmp/risk-yahoo.json');
 const previous=read(output),data:any=previous?.schema===RISK_SCHEMA?previous:{schema:RISK_SCHEMA,stocks:{},benchmarks:{}};
 data.attempts=data.attempts||{};
 const inputs=[...new Set<string>(universe.kandidaten.map((r:any)=>String(r.listing_symbol||r.ticker||'').trim().toUpperCase()).filter((s:string)=>/^[A-Z0-9._:-]{1,100}$/.test(s)))];
 inputs.sort((a,b)=>(Date.parse(data.attempts[a])||0)-(Date.parse(data.attempts[b])||0));
 const sleep=options.sleep||((ms:number)=>new Promise(r=>setTimeout(r,ms)));
 const started=clock(),deadline=started+budget*60000;let last=0,spacing=650,blockedUntil=0,requests=0,aborted=false,historyDenied=0;let preferredYears:2|5=5;
 const report:any={attempted:0,updated:0,failed:0,skippedFresh:0,universe:inputs.length,errors:[],failureReasons:{},rateLimitEvents:0,retries:0,benchmarkFallbacks:0,benchmarkWarnings:[],budgetReached:false};
 const save=()=>{data.generatedAt=new Date(clock()).toISOString();data.report={...report,requests};fs.mkdirSync(path.dirname(output),{recursive:true});fs.writeFileSync(output+'.tmp',JSON.stringify(data));fs.renameSync(output+'.tmp',output)};
 const paced:typeof fetch=async(url,opts)=>{
  if(clock()>deadline)throw Error('Zeitbudget erreicht.');
  const wait=Math.max(0,spacing-(clock()-last));if(wait)await sleep(wait);
  opts?.signal?.throwIfAborted();last=clock();requests++;
  const r=await fetcher(url,opts);if([401,403].includes(r.status)){aborted=true;throw Error('ROIC-Zugang abgelehnt HTTP '+r.status)}
  if(r.status===429){report.rateLimitEvents++;const header=r.headers.get('retry-after'),n=header===null?NaN:Number(header),date=header?Date.parse(header):NaN;const delay=Math.max(30000,Number.isFinite(n)?n*1000:Number.isFinite(date)?date-clock():60000);blockedUntil=Math.max(blockedUntil,clock()+delay);spacing=Math.min(3000,spacing*1.5);throw Error('ROIC-Ratenlimit HTTP 429')}
  return r;
 };
 const retry=async<T>(task:()=>Promise<T>):Promise<T>=>{for(let attempt=0;;attempt++){
  const wait=Math.max(0,blockedUntil-clock());if(clock()+wait>=deadline)throw Error('Zeitbudget erreicht.');if(wait)await sleep(wait);
  try{return await task()}catch(e){if(!/HTTP 429/.test((e as Error).message)||attempt>=2)throw e;report.retries++}
 }};
 const fresh=(v:any)=>v?.schema===RISK_SCHEMA&&clock()-Date.parse(v.retrievedAt)>=0&&clock()-Date.parse(v.retrievedAt)<18*3600000;
 const accept=(h:any)=>{const s=compactHistory(h,clock()),v=historyStatistics(s,clock());if(!v.observations||[v.es,v.dd,v.worst,v.drawdown].every(x=>x===null))throw Error('Keine gültige Risiko-Historie: '+(v.error||'Weniger als 200 aktuelle Handelstage oder Lücken.'));return s};
 const failure=(symbol:string,e:any)=>{report.failed++;const category=/HTTP \d+/.exec(e?.message||'')?.[0]||(/Notierung/.test(e?.message||'')?'Notierung':'Sonstige');report.failureReasons[category]=(report.failureReasons[category]||0)+1;if(!symbol.startsWith('Markt ')&&/Kurshistorie HTTP 402/.test(e?.message||'')){historyDenied++;if(historyDenied>=3)aborted=true}if(report.errors.length<2000)report.errors.push({symbol,reason:/^(ROIC|Kurshistorie|Notierung|Markt|Keine|Zeitbudget|Eindeutige|Ungültige)/.test(e?.message||'')?e.message:'Abruf fehlgeschlagen'});};
 for(const country of ['US','DE','JP','GB','FR','HK','IN','CN','KR','TW']){
  if(clock()>deadline||aborted)break;
  try{const h=await retry(()=>benchmarkHistory(country,env.ROIC_API_KEY,paced));data.benchmarks[h.proxy]=accept(h)}catch(e){const proxy=marketProxy(country),candidate=yahoo?.benchmarks?.[proxy||''];if(validYahooBenchmark(candidate,proxy,clock())){try{data.benchmarks[proxy!]=accept(candidate);report.benchmarkFallbacks++;report.benchmarkWarnings.push({country,reason:'ROIC-Marktvergleich nicht verfügbar; Yahoo-ETF übernommen.'});continue}catch{}}failure('Markt '+country,e)}
 }
 let processed=0;
 for(const inputSymbol of inputs){
  if(clock()>deadline||blockedUntil>=deadline||aborted){report.budgetReached=clock()>deadline||blockedUntil>=deadline;break}
  processed++;data.attempts[inputSymbol]=new Date(clock()).toISOString();
  if(fresh(data.stocks[inputSymbol])){report.skippedFresh++;continue}
  report.attempted++;
  try{const symbol=inputSymbol.includes(':')?inputSymbol:String((await retry(()=>resolveRiskListing(inputSymbol,env.ROIC_API_KEY,paced))).symbol);
   if(fresh(data.stocks[symbol])){report.skippedFresh++;continue}
   const h=await retry(()=>riskHistory(symbol,env.ROIC_API_KEY,paced,clock(),preferredYears));preferredYears=h.requestedYears;historyDenied=0;data.stocks[symbol]=accept(h);report.updated++;
  }catch(e){failure(inputSymbol,e)}
  if(processed%25===0){save();console.log('Risiko: '+processed+'/'+inputs.length+' geprüft; '+report.updated+' aktualisiert; '+report.failed+' fehlgeschlagen.')}
 }
 report.remaining=inputs.length-processed;report.accessDenied=aborted;report.historyWindowYears=preferredYears;report.storedStocks=Object.keys(data.stocks).length;const auditNow=clock(),freshRows=Object.values(data.stocks).filter((h:any)=>auditNow-Date.parse(h.retrievedAt)>=0&&auditNow-Date.parse(h.retrievedAt)<=36*3600000) as any[];report.freshStocks=freshRows.length;report.freshBenchmarks=Object.values(data.benchmarks).filter((h:any)=>auditNow-Date.parse(h.retrievedAt)>=0&&auditNow-Date.parse(h.retrievedAt)<=36*3600000&&historyStatistics(h,auditNow).drawdown!==null).length;report.historicalCoverage=freshRows.filter(h=>historyStatistics(h,auditNow).es!==null).length;report.contextCoverage=freshRows.filter(h=>historyStatistics(h,auditNow).drawdown!==null).length;save();
 console.log(JSON.stringify(data.report));if(report.failed||report.remaining)console.log('::warning::Risikodaten teilweise offen; Bericht in cf_risk.json prüfen. Alte Stände bleiben datiert erhalten.');
 return {ok:!aborted&&(report.updated>0||report.skippedFresh>0),report:data.report};
}
if(process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href){exportRisk().then(r=>{if(!r.ok)process.exitCode=1}).catch(()=>{console.error('Risikoexport abgebrochen: Eingabe, Konfiguration oder Dateizugriff prüfen.');process.exitCode=1})}
