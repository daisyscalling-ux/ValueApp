import registry from './market-proxies.json';
import {marketProxy} from './worker/risk-benchmark';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {auditUniverse,failureState,retryDue} from './universe-coverage';
process.env.RISK_EXPORT_LIBRARY='1';
const {exportRisk}=await import('./export-risk');
const now=Date.parse('2026-10-18T12:00:00Z');let checks=0;
const test=(name:string,fn:()=>void)=>{fn();checks++;console.log('OK '+name)};
const row={listing_symbol:'NASDAQ:TEST',ticker:'TEST',name:'Test',currency:'USD',country:'US',industry:'Software',metadata_asof:'2026-10-18T00:00:00Z'};
const summary=(symbol='NASDAQ:TEST')=>({schema:1,format:'risk-summary',symbol,currency:'USD',adjustment:'total_return',retrievedAt:new Date(now).toISOString(),statistics:{observations:600,first:'2024-01-01',last:'2026-10-16',error:'',es:.03,dd:.3,worst:.2,drawdown:.1}});
const fund=()=>({symbol:row.listing_symbol,retrieved_at:new Date(now).toISOString(),annual:{end:'2026-06-30',period_type:'annual',currency:'USD',source:'Yahoo annual statements',fields:{total_assets:100,total_debt:0,cash:20,operating_cashflow:10,capex:-3}},market:{quote_at:'2026-10-16',currency:'USD',fields:{price:10}}});
const risk=()=>({stocks:{[row.listing_symbol]:summary()},benchmarks:{SPY:summary('AMEX:SPY')}});
const audit=(rows:any[]=[row],f:any=fund(),r:any=risk())=>auditUniverse({kandidaten:rows},r,{[row.listing_symbol]:f},now);

test('main-market queue priority retains smaller markets and weekly rotation',()=>{
 const rows=['GPW:PKO','LSE:AZN','NASDAQ:TEST','TSE:7203','XETR:SAP'].map(symbol=>({...row,listing_symbol:symbol}));
 const a=audit(rows,null,{}),jobs=a.jobs.filter(j=>j.kind==='history');
 assert.deepEqual(jobs.map(j=>j.marketTier),[0,0,0,1,2]);
 assert.equal(new Set(jobs.map(j=>j.symbol)).size,5);
 assert.equal(a.summary.markets.primary.listings,3);
 assert.equal(a.summary.markets.rotation.domains.historical.missing,1);
 const b=audit(rows,null,{attempts:{'GPW:PKO':'2026-10-10T00:00:00Z'}});
 assert.equal(b.jobs.filter(j=>j.kind==='history')[0].symbol,'GPW:PKO');
 assert(a.stocks.every(s=>s.score===null));
});
test('deduplicate exact listing only',()=>assert.equal(audit([row,row,{...row,listing_symbol:'XETR:TEST'}]).summary.uniqueListings,2));
test('missing history is not low risk',()=>{const a=audit([row],fund(),{});assert.equal(a.stocks[0].score,null);assert.equal(a.stocks[0].domains.historical.state,'missing')});

test('independent annual risk source recovers balance without changing valuation',()=>{
 const f:any=fund();f.annual.source='SEC companyfacts / US-GAAP';f.annual.fields.total_debt=null;f.annual.fields.eps_trailing=4;
 f.risk_annual={...fund().annual,symbol:row.listing_symbol,purpose:'standalone_balance_risk_context',fields:{...fund().annual.fields,eps_trailing:2}};
 const before=JSON.stringify(f),balance=audit([row],f).stocks[0].domains.balance;
 assert.equal(balance.state,'available');assert.equal(balance.sourceSelection,'provider_native_whole_statement');
 assert.equal(balance.source,'Yahoo annual statements');assert.equal(balance.valuationSource,'SEC companyfacts / US-GAAP');
 assert.equal(JSON.stringify(f),before);
});
test('native fallback rejects different issuer, currency, period, stale and mixed fields',()=>{
 const f:any=fund();f.annual.fields.total_debt=null;
 const native={...fund().annual,symbol:row.listing_symbol,purpose:'standalone_balance_risk_context'};
 for(const change of [{symbol:'NASDAQ:OTHER'},{currency:'EUR'},{end:'2025-06-30'},{end:'2027-06-30'},
  {source:'Unknown'},{purpose:'valuation'},{field_sources:{cash:{end:'2025-06-30'}}}]){
  f.risk_annual={...native,...change};assert.notEqual(audit([row],f).stocks[0].domains.balance.state,'available');
 }
 f.risk_annual=native;f.retrieved_at='2026-10-01T00:00:00Z';assert.notEqual(audit([row],f).stocks[0].domains.balance.state,'available');
});
test('native statement preserves rounded fiscal end and never makes a hybrid',()=>{
 const f:any=fund();f.annual.end='2026-07-03';f.annual.fields.capex=null;
 f.risk_annual={...fund().annual,symbol:row.listing_symbol,purpose:'standalone_balance_risk_context',fields:{...fund().annual.fields,total_debt:null}};
 assert.notEqual(audit([row],f).stocks[0].domains.balance.state,'available');
 f.risk_annual.fields.total_debt=0;
 const b=audit([row],f).stocks[0].domains.balance;assert.equal(b.period,'2026-06-30');assert.equal(b.valuationPeriod,'2026-07-03');
});
test('complete existing statements and legacy snapshots retain their source',()=>{
 const f:any=fund();f.annual.source='SEC companyfacts / US-GAAP';f.annual.fields.capex=3;
 f.risk_annual={...fund().annual,symbol:row.listing_symbol,purpose:'standalone_balance_risk_context'};
 assert.equal(audit([row],f).stocks[0].domains.balance.source,'SEC companyfacts / US-GAAP');
 delete f.risk_annual;assert.equal(audit([row],f).stocks[0].domains.balance.state,'available');
});

test('retained financial fields keep their own retrieval age',()=>{
 const f:any=fund();f.annual.field_sources={total_debt:{end:f.annual.end,currency:'USD',retrieved_at:'2026-10-01T00:00:00Z'}};
 const a=audit([row],f).stocks[0].domains.balance;
 assert.notEqual(a.state,'available');assert.equal(a.metrics.netDebtAssets.value,null);
 f.annual.field_sources.total_debt.retrieved_at='2026-10-17T00:00:00Z';
 assert.equal(audit([row],f).stocks[0].domains.balance.state,'available');
});

test('verified history aliases retain exact-request fundamental snapshots',()=>{
 const r:any=risk();r.aliases={'TEST.US':row.listing_symbol};
 const f={...fund(),symbol:'TEST.US'};
 const rows=[{...row,listing_symbol:'TEST.US'}];
 const check=(value:any,state=r)=>auditUniverse({kandidaten:rows},state,{'TEST.US':value},now).stocks[0];
 assert.equal(check(f).domains.balance.state,'available');
 assert.equal(check(f).domains.quote.state,'available');
 assert.equal(check({...f,symbol:'NYSE:OTHER'}).domains.balance.state,'missing');
 assert.equal(check(f,{...r,aliases:{}}).domains.balance.state,'missing');
 assert.equal(check(f,{...r,stocks:{[row.listing_symbol]:{...summary(),currency:'EUR'}}}).domains.balance.state,'missing');
});
test('zero debt valid and Yahoo cash outflow normalized',()=>{const a=audit().stocks[0].domains.balance;assert.equal(a.state,'available');assert.equal(a.ratios.fcfAssets,.07);assert.equal(a.ratios.netDebtAssets,-.2)});
test('unknown negative capex not normalized',()=>{const f=fund();f.annual.source='Unknown';const b=audit([row],f).stocks[0].domains.balance;assert.equal(b.state,'partial');assert.equal(b.metrics.fcfAssets.value,null);assert.equal(b.ratios,null)});

test('banks use dated book context without pretending to have regulatory capital',()=>{
 const f:any=fund();f.annual.fields={total_assets:100,equity:-2,net_income:-1};
 const a=audit([{...row,industry:'Major banks'}],f),b=a.stocks[0].domains.balance;
 assert.equal(b.state,'context_only');assert.equal(b.profile,'bank');assert.equal(b.metrics.bookEquityAssets.value,-.02);
 assert.equal(b.metrics.netDebtAssets.state,'not_applicable');assert.equal(b.ratios,null);
 assert(!a.jobs.some(j=>j.kind==='fundamentals'));assert(a.jobs.some(j=>j.kind==='sector_financials'&&j.state==='review_required'));
 assert.equal(a.stocks[0].score,null);
});
test('missing bank equity remains a real field gap',()=>{
 const f:any=fund();f.annual.fields={total_assets:100,net_income:1};
 const a=audit([{...row,industry:'Banks - Regional'}],f);
 assert.equal(a.stocks[0].domains.balance.state,'partial');
 assert.match(a.stocks[0].domains.balance.reason,/missing_equity/);
 assert(!a.stocks[0].domains.balance.reason.includes('capex'));assert(a.jobs.some(j=>j.kind==='fundamentals'));
});
test('insurers and brokers not conflated; stale classification gets no generic score',()=>{
 const f:any=fund();f.annual.fields.equity=10;f.annual.fields.net_income=2;
 assert.equal(audit([{...row,industry:'Life/Health insurance'}],f).stocks[0].domains.balance.profile,'insurer');
 assert.equal(audit([{...row,industry:'Insurance brokers/Services'}],f).stocks[0].domains.balance.profile,'corporate');
 assert.equal(audit([{...row,industry:'Investment banks/Brokers'}],f).stocks[0].domains.balance.profile,'specialist_financial');
 const b=audit([{...row,industry:'Major banks',metadata_asof:'2025-01-01'}],f).stocks[0].domains.balance;
 assert.equal(b.profile,'unclassified');assert.equal(b.ratios,null);
});
test('corporate missing capex retains independently valid debt observation',()=>{
 const f:any=fund();delete f.annual.fields.capex;
 const b=audit([row],f).stocks[0].domains.balance;
 assert.equal(b.state,'partial');assert.equal(b.metrics.netDebtAssets.value,-.2);assert.equal(b.metrics.fcfAssets.value,null);
});
test('bank context rejects stale or mixed period equity',()=>{
 const f:any=fund();f.annual.fields.equity=10;f.annual.fields.net_income=2;
 f.annual.field_sources={equity:{end:'2025-06-30'}};
 const b=audit([{...row,industry:'Major banks'}],f).stocks[0].domains.balance;
 assert.equal(b.state,'missing');assert.equal(b.metrics.bookEquityAssets.value,null);
});
test('future annual date blocks ratios',()=>{const f=fund();f.annual.end='2027-06-30';assert.equal(audit([row],f).stocks[0].domains.balance.ratios,null)});
test('mixed financial periods blocked',()=>{const f:any=fund();f.annual.field_sources={total_debt:{end:'2025-06-30'}};assert.equal(audit([row],f).stocks[0].domains.balance.ratios,null)});
test('stale retrieval hides current history',()=>{const r=risk();r.stocks[row.listing_symbol].retrievedAt='2026-10-01';assert.equal(audit([row],fund(),r).stocks[0].domains.price.state,'stale_or_invalid')});
test('listing currency conflict quarantined',()=>assert.equal(audit([row,{...row,currency:'EUR'}]).stocks[0].domains.identity.state,'blocked'));
test('pence and pounds not mistaken for different listings',()=>{const r=risk();r.stocks[row.listing_symbol].currency='GBP';assert.equal(audit([{...row,currency:'GBp'}],fund(),r).stocks[0].domains.identity.state,'available')});
test('general news never means company news covered',()=>assert.equal(audit().stocks[0].domains.news.state,'not_assessed'));
test('all reviewed countries and aliases match',()=>{for(const r of registry)for(const a of [r.country,...r.aliases])assert.equal(marketProxy(a.toLowerCase()),r.proxy);assert.equal(new Set(registry.map(r=>r.country)).size,registry.length)});
test('unsupported market explicit',()=>assert.equal(audit([{...row,country:'PT'}]).stocks[0].domains.market.state,'unsupported'));
test('new unresolved listing scheduled for resolution',()=>assert(auditUniverse({kandidaten:[{ticker:'NEW.DE'}]}, {}, {},now).jobs.some(j=>j.kind==='history'&&j.state==='queued')));
test('backoff bounded and expired retry allowed',()=>{const s=failureState('HTTP 503',undefined,now);assert(!retryDue(s,now));assert(retryDue(s,now+3*3600000));assert(retryDue({nextAttemptAt:'2099-01-01'},now))});
test('subscription failure cools down rather than repeated requests',()=>assert(!retryDue(failureState('HTTP 402',undefined,now),now+86400000)));

const folder=fs.mkdtempSync(path.join(os.tmpdir(),'risk-universe-test-'));
const universe=path.join(folder,'universe.json'),output=path.join(folder,'risk.json');
fs.writeFileSync(universe,JSON.stringify({kandidaten:[row]}));
const proxies=registry.map(r=>r.proxy);
fs.writeFileSync(output,JSON.stringify({schema:1,stocks:{},benchmarks:Object.fromEntries(proxies.map(p=>[p,summary('AMEX:'+p)]))}));
let time=now,requests=0,mode='fail';
const fetcher:any=async(url:string)=>{requests++;if(url.includes('/tickers/search'))return new Response(JSON.stringify([{symbol:row.listing_symbol,is_primary:true,type:'stock',type_specifications:['common'],listing_country_code:'US'}]));
 if(mode==='fail')return new Response('',{status:503});
 const data=Array.from({length:620},(_,i)=>({date:new Date(now-(i+1)*86400000).toISOString().slice(0,10),close:100+i*.01}));return new Response(JSON.stringify({symbol:row.listing_symbol,currency:'USD',data}));};
const env={ROIC_API_KEY:'test',RISK_UNIVERSE_PATH:universe,RISK_OUTPUT_PATH:output,RISK_VALIDATION_ENABLED:'1',RISK_VALIDATION_STATE:path.join(folder,'study.json'),RISK_VALIDATION_OUTPUT:path.join(folder,'validation.json'),RISK_QUEUE_PATH:path.join(folder,'queue.json'),RISK_BUDGET_MIN:'1'};
await exportRisk({env,fetcher,clock:()=>time,sleep:async(ms:number)=>{time+=ms}});
test('failure state checkpointed',()=>assert.equal(JSON.parse(fs.readFileSync(output,'utf8')).retryState[row.listing_symbol].category,'provider'));
const before=requests;
await exportRisk({env,fetcher,clock:()=>time,sleep:async(ms:number)=>{time+=ms}});
test('cooldown makes zero repeated network calls',()=>assert.equal(requests,before));
time+=3*3600000;mode='success';
await exportRisk({env,fetcher,clock:()=>time,sleep:async(ms:number)=>{time+=ms}});
test('successful resumed job clears failure and stores listing',()=>{const d=JSON.parse(fs.readFileSync(output,'utf8'));assert(!d.retryState[row.listing_symbol]);assert(d.stocks[row.listing_symbol]);assert.equal(d.aliases[row.listing_symbol],row.listing_symbol)});
console.log(`${checks} universe and queue checks passed. Temporary fixture: ${folder}`);
