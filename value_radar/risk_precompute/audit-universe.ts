import fs from 'node:fs';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {auditUniverse} from './universe-coverage';
const read=(p:string)=>{try{return JSON.parse(fs.readFileSync(p,'utf8'))}catch{return null}};
export function runAudit(folder='value_radar/daten',now=Date.now()){
 const index=read(path.join(folder,'fundamentals/index.json')),funds:Record<string,any>={};
 for(const [symbol,file] of Object.entries(index?.listings||{})){
  if(typeof file!=='string'||!file.endsWith('.json')||path.basename(file)!==file||/[\\/]/.test(file))continue;
  const f=read(path.join(folder,'fundamentals',file));if(f)funds[symbol]=f;
 }
 const result=auditUniverse(read(path.join(folder,'cf_universum.json')),read(path.join(folder,'cf_risk.json'))||{},funds,now,index||{},read(path.join(folder,'cf_company_news.json'))||{},read(path.join(folder,'cf_sector_context.json')),read(path.join(folder,'cf_roic_risk_annual.json')));
 const save=(name:string,value:any)=>{const p=path.join(folder,name);fs.writeFileSync(p+'.tmp',JSON.stringify(value));fs.renameSync(p+'.tmp',p)};
 const {jobs,...coverage}=result;
 save('cf_risk_coverage.json',coverage);save('cf_risk_queue.json',{schema:1,generatedAt:result.generatedAt,jobs});
 return result;
}
if(process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href){
 const r=runAudit(process.argv[2]||'value_radar/daten');console.log(JSON.stringify(r.summary));
 if(process.env.GITHUB_STEP_SUMMARY){const lines=['## Risiko-Datenabdeckung',`Aktive Notierungen: ${r.summary.uniqueListings}; doppelte Zeilen: ${r.summary.duplicateRows}`,'','| Bereich | Status | Anzahl |','|---|---|---:|'];
 for(const [domain,counts] of Object.entries(r.summary.domains))for(const [state,count] of Object.entries(counts as any))lines.push(`| ${domain} | ${state} | ${count} |`);
 lines.push('','Dies ist eine Datenprüfung, kein kalibrierter Risikoscore. Nachrichten und direkte Wettbewerber sind noch nicht automatisch geprüft.');fs.appendFileSync(process.env.GITHUB_STEP_SUMMARY,lines.join('\n')+'\n');}
}
