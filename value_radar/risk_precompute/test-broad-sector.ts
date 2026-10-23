import assert from 'node:assert/strict';
import {buildSectorComparisons,compactSectorSeries,selectSectorComparison} from './sector-comparison';
import {addBroadSectorContext} from './broad-sector-context';
const now=Date.parse('2026-10-22T12:00:00Z'),DAY=86400000;
const dates=Array.from({length:560},(_,i)=>new Date(now-(560-i)*DAY).toISOString().slice(0,10)).filter(d=>![0,6].includes(new Date(d).getUTCDay()));
function fixture(n=12){
 const rows:any[]=[],listings:any={},issuers:any[]=[],series:any={},profiles:any={};
 for(let i=0;i<n;i++){
  const s=`NYSE:T${i}`,r={ticker:`T${i}`,listing_symbol:s,isin:`ISIN${i}`,name_full:`Company ${i}`,currency:'USD',industry:'Software',security_type:'stock'};
  rows.push(r);listings[s]={issuerId:`issuer${i}`,group:`niche${i}`,level:'provider_subindustry',inputIdentity:r};
  issuers.push({id:`issuer${i}`,representative:s,listings:[s],classification:{group:`niche${i}`}});
  series[s]=compactSectorSeries({symbol:s,currency:'USD',adjustment:'total_return',retrievedAt:new Date(now-3600000).toISOString(),bars:dates.map((date,j)=>({date,close:100+j*(i+1)/100}))},now);
  profiles[s]={source:'Yahoo Finance',sectorKey:'technology',retrievedAt:new Date(now-3600000).toISOString(),evidence:{symbol:r.ticker},inputIdentity:r};
 }
 return {universe:{kandidaten:rows},groups:{schema:1,method:'issuer-business-groups-v1',generatedAt:new Date(now-3600000).toISOString(),listings,issuers},metadata:{profiles},cache:{schema:1,series}};
}
const calculate=(f:ReturnType<typeof fixture>)=>addBroadSectorContext(buildSectorComparisons(f.universe,f.groups,f.cache,now),f.universe,f.groups,f.metadata,f.cache,now);
let passed=0;function check(name:string,fn:()=>void){fn();console.log('PASS '+name);passed++}
check('separate broad context does not upgrade strict peer coverage',()=>{
 const r=calculate(fixture());assert.equal(r.summary.states.available,undefined);assert.equal(r.summary.states.missing,12);
 const t=r.stocks['NYSE:T0'];assert.equal(t.state,'missing');assert.equal(t.broaderContext.state,'available');assert.equal(t.broaderContext.peerIssuers,11);
 assert.equal(t.broaderContext.quality,'broad_sector_context');assert.equal(t.broaderContext.score,null);assert.ok(!t.broaderContext.peerSymbols.includes('NYSE:T0'));
});
check('ten other issuers required; currency and identity restrictions remain',()=>{
 assert.ok(!calculate(fixture(10)).stocks['NYSE:T0'].broaderContext);
 for(const mutate of [(f:any)=>{f.universe.kandidaten[1].currency='EUR'},(f:any)=>{f.metadata.profiles['NYSE:T1'].retrievedAt='2020-01-01'},(f:any)=>{f.metadata.profiles['NYSE:T1'].sectorKey='unrecognized'}]){
  const f=fixture(11);mutate(f);assert.ok(!calculate(f).stocks['NYSE:T0'].broaderContext);
 }
});
check('existing strict comparison remains identical and has no fallback',()=>{
 const f=fixture();for(const x of Object.values(f.groups.listings) as any[])x.group='one';for(const x of f.groups.issuers)x.classification.group='one';
 const strict=buildSectorComparisons(f.universe,f.groups,f.cache,now);const before=JSON.stringify(strict.stocks);
 addBroadSectorContext(strict,f.universe,f.groups,f.metadata,f.cache,now);assert.equal(JSON.stringify(strict.stocks),before);
});
check('missing target history is not bypassed; stale groups remain invalid',()=>{
 const f=fixture();delete f.cache.series['NYSE:T0'];assert.ok(!calculate(f).stocks['NYSE:T0'].broaderContext);
 f.groups.generatedAt='2020-01-01';assert.equal(calculate(f).summary.broaderContext.available,0);
});
check('conflicting issuer sector profiles are excluded rather than majority voted',()=>{
 const f=fixture(11),s='NYSE:ALT';f.universe.kandidaten.push({...f.universe.kandidaten[1],ticker:'ALT',listing_symbol:s});
 f.groups.listings[s]={...f.groups.listings['NYSE:T1']};f.groups.issuers[1].listings.push(s);
 f.metadata.profiles[s]={...f.metadata.profiles['NYSE:T1'],sectorKey:'energy',evidence:{symbol:'ALT'},inputIdentity:f.universe.kandidaten.at(-1)};
 assert.ok(!calculate(f).stocks['NYSE:T0'].broaderContext);
});
check('stale or changed broad result cannot leak through a missing strict result',()=>{
 const f=fixture(),r=calculate(f),row={...f.universe.kandidaten[0]};assert.ok(selectSectorComparison(r,'NYSE:T0',row,now)?.broaderContext);
 assert.ok(!selectSectorComparison(r,'NYSE:T0',{...row,isin:'changed'},now)?.broaderContext);
 r.stocks['NYSE:T0'].broaderContext.observationDate='2020-01-01';assert.ok(!selectSectorComparison(r,'NYSE:T0',row,now)?.broaderContext);
});
console.log(`${passed} broad context checks passed`);

