import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import registry from './market-proxies.json';
import {auditUniverse} from './universe-coverage';
process.env.RISK_EXPORT_LIBRARY='1';
const {exportRisk}=await import('./export-risk');
import {buildSectorComparisons,compactSectorSeries,seriesCheck,selectSectorComparison,currencyUnit} from './sector-comparison';
import {weeklyCalendar,verifiedClosureGap} from './trading-calendar';
const DAY=86400000,now=Date.parse('2026-10-21T12:00:00Z');
const dates=Array.from({length:560},(_,i)=>new Date(now-(560-i)*DAY).toISOString().slice(0,10)).filter(d=>![0,6].includes(new Date(d).getUTCDay()));
const rows=Array.from({length:7},(_,i)=>({listing_symbol:`NYSE:T${i}`,name_full:`Company ${i}`,industry:'Major banks',isin:`TEST${i}`,currency:'USD',security_type:'stock',sub_industry:null}));
function fixture(){
 const universe={kandidaten:structuredClone(rows)},listings:any={},issuers:any[]=[],series:any={};
 for(const [i,r] of universe.kandidaten.entries()){
  const s=r.listing_symbol,id='issuer'+i;
  listings[s]={issuerId:id,group:'bank',level:'industry_context',inputIdentity:r};
  issuers.push({id,representative:s,listings:[s],classification:{group:'bank',label:'Banks'}});
  series[s]=compactSectorSeries({symbol:s,currency:'USD',adjustment:'total_return',retrievedAt:new Date(now-3600000).toISOString(),bars:dates.map((date,j)=>({date,close:100*Math.exp((i-2)*.0005*j)}))},now);
 }
 return {universe,groups:{schema:1,method:'issuer-business-groups-v1',generatedAt:new Date(now-300000).toISOString(),listings,issuers},cache:{schema:1,series}};
}
const calculate=(f:ReturnType<typeof fixture>)=>buildSectorComparisons(f.universe,f.groups,f.cache,now);
let passed=0;function check(name:string,fn:()=>void){fn();passed++;console.log('PASS '+name)}
check('fixed common dates, medians and relative strength',()=>{
 const f=fixture(),r=calculate(f).stocks['NYSE:T0'];assert.equal(r.state,'available');assert.equal(r.peerIssuers,6);assert.equal(r.quality,'provisional_industry');assert.equal(r.score,null);
 const a=r.returns.threeMonths;assert.equal(a.to,r.observationDate);assert.ok(a.value<0);assert.ok(a.peerMedian>0);assert.ok(a.differencePercentagePoints<0);assert.equal(a.strengthPercentile,0);
 assert.equal(r.window.weeklyObservations,53);assert.ok(r.window.commonObservations>=200);
 const x=f.cache.series['NYSE:T0'].points as [string,number][];const m=new Map(x);assert.ok(Math.abs(a.value-(m.get(a.to)!/m.get(a.from)!-1))<1e-12);
});
check('scale invariance and pence currency',()=>{
 const f=fixture(),before=calculate(f).stocks['NYSE:T0'];for(const h of Object.values(f.cache.series) as any[])h.points=h.points.map(([d,v]:any)=>[d,v*100]);
 const after=calculate(f).stocks['NYSE:T0'];assert.ok(Math.abs(before.returns.threeMonths.value-after.returns.threeMonths.value)<1e-12);assert.equal(currencyUnit('GBp'),'GBP');
});
check('currency mismatch and cross currency peers excluded',()=>{
 const f=fixture();for(let i=1;i<4;i++){const s=`NYSE:T${i}`;f.universe.kandidaten[i].currency='EUR';f.cache.series[s].currency='EUR'}
 assert.equal(calculate(f).stocks['NYSE:T0'].reason,'fewer_than_five_same_currency_issuers');
 f.cache.series['NYSE:T0'].currency='JPY';assert.equal(calculate(f).stocks['NYSE:T0'].reason,'series_currency_mismatch');
});
check('peer alternative listing in target currency, no issuer double count',()=>{
 const f=fixture(),old=f.universe.kandidaten[1];f.universe.kandidaten.push({...old,listing_symbol:'LSE:T1',currency:'GBP'});
 f.groups.issuers[1].listings.push('LSE:T1');f.groups.issuers[1].representative='LSE:T1';f.groups.listings['LSE:T1']={...f.groups.listings['NYSE:T1'],inputIdentity:f.universe.kandidaten.at(-1)};
 f.groups.issuers.push(structuredClone(f.groups.issuers[1]));const r=calculate(f).stocks['NYSE:T0'];assert.equal(r.peerIssuers,6);assert.ok(r.peerSymbols.includes('NYSE:T1'));assert.ok(!r.peerSymbols.includes('LSE:T1'));
});
check('self excluded even across alternate listings',()=>{
 const f=fixture();f.groups.issuers[0].listings.push('NYSE:SELF');const r=calculate(f).stocks['NYSE:T0'];assert.ok(!r.peerSymbols.includes('NYSE:T0'));assert.ok(!r.peerSymbols.includes('NYSE:SELF'));
});
check('changed identity not accepted under old grouping',()=>{
 const f=fixture();f.groups.listings['NYSE:T0'].inputIdentity={...f.universe.kandidaten[0]};f.universe.kandidaten[0].isin='CHANGED';
 assert.equal(calculate(f).stocks['NYSE:T0'].reason,'membership_identity_mismatch');
});
check('stale and future reports rejected; old algorithm not used',()=>{
 const f=fixture(),report=calculate(f);assert.ok(selectSectorComparison(report,'NYSE:T0',rows[0],now));
 assert.equal(selectSectorComparison(report,'NYSE:T0',rows[0],now+2*DAY),null);
 f.groups.generatedAt=new Date(now+DAY).toISOString();assert.equal(calculate(f).stocks['NYSE:T0'].reason,'group_snapshot_missing_or_stale');
});
check('invalid closes, duplicate dates, stale prices and false adjustment rejected',()=>{
 for(const mutate of [(h:any)=>h.points[4][1]=0,(h:any)=>h.points[4][0]=h.points[3][0],(h:any)=>h.adjustment='split',(h:any)=>h.retrievedAt='2026-01-01T00:00:00Z',(h:any)=>h.points.at(-1)[0]='2026-10-21']){
  const f=fixture();mutate(f.cache.series['NYSE:T0']);assert.ok(seriesCheck(f.cache.series['NYSE:T0'],now));assert.equal(calculate(f).stocks['NYSE:T0'].state,'missing');
 }
});
check('common holiday intersection and insufficient history',()=>{
 const f=fixture();f.cache.series['NYSE:T1'].points=f.cache.series['NYSE:T1'].points.filter((_:any,i:number)=>i%20!==0);
 const r=calculate(f).stocks['NYSE:T0'];assert.equal(r.state,'available');assert.ok(r.window.commonObservations<262);
 f.cache.series['NYSE:T0'].points=f.cache.series['NYSE:T0'].points.slice(-150);assert.equal(calculate(f).stocks['NYSE:T0'].state,'missing');
});
check('no forced comparison for a small reviewed group',()=>{
 const f=fixture();f.groups.issuers=f.groups.issuers.slice(0,3);f.groups.listings['NYSE:T0'].level='reviewed_business_model';
 const r=calculate(f).stocks['NYSE:T0'];assert.equal(r.reason,'fewer_than_five_same_currency_issuers');assert.equal(r.quality,'reviewed_business_model');
});
check('flat series produces zero volatility and drawdown, tied percentile 50',()=>{
 const f=fixture();for(const h of Object.values(f.cache.series) as any[])h.points=h.points.map(([d]:any)=>[d,100]);
 const r=calculate(f).stocks['NYSE:T0'];assert.equal(r.volatility.value,0);assert.equal(r.maxDrawdown.value,0);assert.equal(r.returns.threeMonths.strengthPercentile,50);assert.equal(r.currentDrawdown.higherRiskPercentile,50);
});
check('known peak and 50 percent fall',()=>{
 const f=fixture(),h=f.cache.series['NYSE:T0'];h.points=h.points.map(([d]:any,i:number)=>[d,i<h.points.length-30?100:50]);
 const r=calculate(f).stocks['NYSE:T0'];assert.equal(r.drawdown,.5);assert.equal(r.maxDrawdown.value,.5);assert.ok(r.volatility.value>0);
});
check('malformed groups safely produce missing data',()=>{
 const f=fixture();const r=buildSectorComparisons(f.universe,null as any,null as any,now);assert.equal(r.summary.states.missing,7);
});
check('coverage consumes aligned context and rejects stale report without legacy fallback',()=>{
 const f=fixture(),report=calculate(f);
 const result=auditUniverse(f.universe,{}, {},now,{}, {},report);
 assert.equal(result.stocks[0].domains.sector.method,'aligned-cohort-v1');assert.equal(result.stocks[0].domains.sector.quality,'provisional_industry');
 assert.ok(result.jobs.some(j=>j.kind==='peer_classification'));
 report.generatedAt='2026-01-01T00:00:00Z';
 assert.equal(auditUniverse(f.universe,{}, {},now,{}, {},report).stocks[0].domains.sector.reason,'aligned_sector_report_missing_or_stale');
});
const folder=fs.mkdtempSync(path.join(os.tmpdir(),'sector-cache-test-')),output=path.join(folder,'risk.json'),input=path.join(folder,'universe.json'),sectorPath=path.join(folder,'series.json');
const summary=(s:string)=>({schema:1,format:'risk-summary',symbol:s,currency:'USD',adjustment:'total_return',retrievedAt:new Date(now-3600000).toISOString(),statistics:{observations:620,first:'2024-01-01',last:'2026-10-20',error:'',es:.02,dd:.2,worst:.1,drawdown:.1}});
fs.writeFileSync(input,JSON.stringify({kandidaten:[rows[0]]}));
fs.writeFileSync(output,JSON.stringify({schema:1,stocks:{'NYSE:T0':summary('NYSE:T0')},benchmarks:Object.fromEntries(registry.map(r=>[r.proxy,summary('AMEX:'+r.proxy)]))}));
let calls=0;
const fetcher:any=async()=>{calls++;return new Response(JSON.stringify({symbol:'NYSE:T0',currency:'USD',data:dates.map((date,i)=>({date,close:100+i*.01}))}))};
const env={ROIC_API_KEY:'fixture-only',RISK_UNIVERSE_PATH:input,RISK_OUTPUT_PATH:output,RISK_SECTOR_ENABLED:'1',RISK_SECTOR_STATE:sectorPath,RISK_BUDGET_MIN:'1',RISK_QUEUE_PATH:path.join(folder,'none.json')};
await exportRisk({env,fetcher,clock:()=>now,sleep:async()=>{}});
check('migration fetches missing raw series despite fresh old summary',()=>{assert.equal(calls,1);const cache=JSON.parse(fs.readFileSync(sectorPath,'utf8'));assert.ok(cache.series['NYSE:T0'].points.length>=200);assert.ok(cache.series['NYSE:T0'].points.length<=400)});
await exportRisk({env,fetcher,clock:()=>now,sleep:async()=>{}});
check('fresh series cache avoids repeated provider calls',()=>assert.equal(calls,1));
check('a sparse peer cannot invalidate five complete peers',()=>{
 const f=fixture();f.cache.series['NYSE:T6'].points=f.cache.series['NYSE:T6'].points.filter((_:any,i:number)=>i%3!==0);
 const r=calculate(f).stocks['NYSE:T0'];assert.equal(r.state,'available');assert.equal(r.peerIssuers,5);
 assert.equal(r.excludedPeers.incompatible_calendar,1);assert.ok(!r.peerSymbols.includes('NYSE:T6'));
});
check('calendar selection independent of prices and input ordering',()=>{
 const f=fixture();f.cache.series['NYSE:T6'].points=f.cache.series['NYSE:T6'].points.filter((_:any,i:number)=>i%3!==0);
 const before=calculate(f).stocks['NYSE:T0'];f.groups.issuers.reverse();f.universe.kandidaten.reverse();
 for(const h of Object.values(f.cache.series) as any[])h.points=h.points.map(([d,v]:any)=>[d,1/v]);
 const after=calculate(f).stocks['NYSE:T0'];assert.deepEqual(after.peerSymbols,before.peerSymbols);assert.deepEqual(after.window,before.window);
});
check('calendar exclusion never lowers the minimum five peers',()=>{
 const f=fixture();for(const s of ['NYSE:T5','NYSE:T6'])f.cache.series[s].points=f.cache.series[s].points.filter((_:any,i:number)=>i%3!==0);
 const r=calculate(f).stocks['NYSE:T0'];assert.equal(r.state,'missing');assert.equal(r.peerIssuers,4);
});
console.log(passed+' sector comparison checks passed');
check('JPX Golden Week and September closure are evidenced, not generic tolerance',()=>{
 for(const [previous,wanted] of [['2026-05-01','2026-05-06'],['2026-09-18','2026-09-23']]){
  assert.ok(verifiedClosureGap(previous,Date.parse(wanted),['TSE:A','JPX:B']));
  assert.ok(!verifiedClosureGap(previous,Date.parse(wanted),['OTC:A']));
  assert.ok(!verifiedClosureGap(previous,Date.parse(wanted),['TSE:A','NYSE:B']));
 }
 assert.ok(!verifiedClosureGap('2026-09-17',Date.parse('2026-09-23'),['TSE:A']));
 assert.ok(!verifiedClosureGap('2028-05-01',Date.parse('2028-05-06'),['TSE:A']));
});
check('53 distinct observations retained with verified holiday shifts',()=>{
 const ds=dates.filter(d=>!['2026-05-04','2026-05-05','2026-05-06','2026-09-21','2026-09-22','2026-09-23'].includes(d));
 const cal=weeklyCalendar(ds,'2026-10-14',['TSE:A']);assert.equal(cal.error,null);
 assert.equal(cal.dates.length,53);assert.equal(new Set(cal.dates).size,53);assert.equal(cal.adjustments.length,2);
 assert.equal(weeklyCalendar(ds,'2026-10-14',['OTC:A']).error,'unverified_weekly_gap');
});
check('missing trading day before holidays remains a real gap',()=>{
 const ds=dates.filter(d=>d<'2026-09-18'||d>'2026-09-23');
 assert.equal(weeklyCalendar(ds,'2026-10-14',['TSE:A']).error,'unverified_weekly_gap');
});
check('normal calendars unchanged and new year closure verified',()=>{
 assert.deepEqual(weeklyCalendar(dates,'2026-10-14',['TSE:A']).dates,weeklyCalendar(dates,'2026-10-14',[]).dates);
 assert.ok(verifiedClosureGap('2025-12-30',Date.parse('2026-01-04'),['TSE:A']));
});
console.log(passed+' total sector/calendar checks passed');
check('complete JPX cohort uses same holiday-adjusted dates for all peers',()=>{
 const f=fixture();for(let i=0;i<7;i++){
  const old=`NYSE:T${i}`,s=`TSE:T${i}`,r=f.universe.kandidaten[i];r.listing_symbol=s;
  f.groups.listings[s]=f.groups.listings[old];delete f.groups.listings[old];
  f.groups.issuers[i].representative=s;f.groups.issuers[i].listings=[s];
  const h=f.cache.series[old];h.symbol=s;h.points=h.points.filter(([d]:any)=>!['2026-05-04','2026-05-05','2026-05-06','2026-09-21','2026-09-22','2026-09-23'].includes(d));
  h.points.push(['2026-10-21',h.points.at(-1)[1]]);f.cache.series[s]=h;delete f.cache.series[old];
 }
 const r=buildSectorComparisons(f.universe,f.groups,f.cache,now+DAY).stocks['TSE:T0'];
 assert.equal(r.state,'available');assert.equal(r.peerIssuers,6);assert.equal(r.holidayCalendar.adjustments.length,2);assert.equal(r.window.weeklyObservations,53);
});
console.log(passed+' final sector/calendar checks passed');
