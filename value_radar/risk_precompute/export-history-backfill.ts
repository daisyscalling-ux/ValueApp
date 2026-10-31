import fs from 'node:fs';import path from 'node:path';
import {assessBalance} from './balance-profile';
type Row=Record<string,any>;
const keys=['listing_symbol','ticker','isin','currency','security_type','share_class'];
export function historyBalances(universe:Row,coverage:Row,cache:Row,now=Date.now()){
 const qualified=new Set((coverage.stocks||[]).filter((r:Row)=>r.domains?.identity?.state==='available').map((r:Row)=>r.symbol));
 const stocks:Row={},seen=new Set(),duplicates=new Set();
 for(const r of universe.kandidaten||[]){if(seen.has(r.listing_symbol))duplicates.add(r.listing_symbol);seen.add(r.listing_symbol)}
 if(cache.schema!==1||cache.method!=='roic-annual-history-v1')return {schema:1,method:'roic-history-balances-v1',generatedAt:new Date(now).toISOString(),stocks};
 for(const row of universe.kandidaten||[]){
  const s=row.listing_symbol,c=cache.stocks?.[s],age=now-Date.parse(c?.retrievedAt);
  if(!qualified.has(s)||duplicates.has(s)||!c||!Number.isFinite(age)||age<0||age>45*86400000||!keys.every(k=>(c.inputIdentity?.[k]??null)===(row[k]??null)))continue;
  const balances=[];const ends=new Set(),duplicateEnds=new Set();
  for(const a of c.annuals||[]){if(ends.has(a.end))duplicateEnds.add(a.end);ends.add(a.end)}
  for(const a of c.annuals||[]){
   if(a.symbol!==s||a.source!=='ROIC v3 annual statements'||a.purpose!=='standalone_balance_risk_context'||a.period_type!=='annual'||duplicateEnds.has(a.end))continue;
   const b=assessBalance(row,a,c.retrievedAt,true,now,8*366,45);
   if(Object.values({...b.metrics,...b.supplementalMetrics}).some((m:any)=>m.state==='available'))balances.push(b);
  }
  if(balances.length)stocks[s]={inputIdentity:c.inputIdentity,retrievedAt:c.retrievedAt,balances:balances.sort((a,b)=>a.period.localeCompare(b.period)),pointInTimeUsable:false};
 }
 return {schema:1,method:'roic-history-balances-v1',generatedAt:new Date(now).toISOString(),stocks};
}
if(['export-history-backfill.ts','history-backfill.mjs'].includes(path.basename(process.argv[1]||''))){
 const folder=process.argv[2]||'value_radar/daten';const read=(name:string)=>{const p=path.join(folder,name);return fs.existsSync(p)?JSON.parse(fs.readFileSync(p,'utf8')):{}};
 const result=historyBalances(read('cf_universum.json'),read('cf_risk_coverage.json'),read('cf_roic_history.json'));
 const dest=path.join(folder,'cf_history_backfill_balances.json');fs.writeFileSync(dest+'.tmp',JSON.stringify(result));fs.renameSync(dest+'.tmp',dest);console.log(JSON.stringify({historicalListings:Object.keys(result.stocks).length}));
}
