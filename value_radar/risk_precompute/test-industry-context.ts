import assert from 'node:assert/strict';
import {buildSectorComparisons,compactSectorSeries,selectSectorComparison} from './sector-comparison';
import {addIndustryContext} from './industry-context';
const now=Date.parse('2026-10-22T12:00:00Z'),DAY=86400000;
const dates=Array.from({length:560},(_,i)=>new Date(now-(560-i)*DAY).toISOString().slice(0,10)).filter(d=>![0,6].includes(new Date(d).getUTCDay()));
function fixture(n=12){
 const rows:any[]=[],listings:any={},issuers:any[]=[],series:any={},profiles:any={};
 for(let i=0;i<n;i++){
  const s=`NYSE:T${i}`,r={ticker:`T${i}`,listing_symbol:s,isin:`ISIN${i}`,name_full:`Company ${i}`,currency:'USD',industry:'Software',metadata_asof:new Date(now-3600000).toISOString(),metadata_source:'ROIC',security_type:'stock'};
  rows.push(r);listings[s]={issuerId:`issuer${i}`,group:`niche${i}`,level:'provider_subindustry',inputIdentity:r};
  issuers.push({id:`issuer${i}`,representative:s,listings:[s],classification:{group:`niche${i}`}});
  series[s]=compactSectorSeries({symbol:s,currency:'USD',adjustment:'total_return',retrievedAt:new Date(now-3600000).toISOString(),bars:dates.map((date,j)=>({date,close:100+j*(i+1)/100}))},now);
  profiles[s]={source:'Yahoo Finance',sectorKey:'technology',retrievedAt:new Date(now-3600000).toISOString(),evidence:{symbol:r.ticker},inputIdentity:r};
 }
 return {universe:{kandidaten:rows},groups:{schema:1,method:'issuer-business-groups-v1',generatedAt:new Date(now-3600000).toISOString(),listings,issuers},metadata:{profiles},cache:{schema:1,series}};
}
const calculate=(f:ReturnType<typeof fixture>)=>addIndustryContext(buildSectorComparisons(f.universe,f.groups,f.cache,now),f.universe,f.groups,f.cache,now);
let passed=0;function check(name:string,fn:()=>void){fn();console.log('PASS '+name);passed++}
check('five same-currency industry peers form separate context',()=>{
 const r=calculate(fixture(6)),t=r.stocks['NYSE:T0'];assert.equal(t.state,'missing');assert.equal(t.industryContext.peerIssuers,5);
 assert.equal(t.industryContext.quality,'provider_industry_context');assert.equal(t.industryContext.directCompetitorsVerified,false);assert.equal(r.summary.states.available,undefined);
});
check('minimum number, currency and stale metadata restrictions stay active',()=>{
 assert(!calculate(fixture(5)).stocks['NYSE:T0'].industryContext);
 for(const change of [(f:any)=>f.universe.kandidaten[1].currency='EUR',(f:any)=>f.universe.kandidaten[1].metadata_asof='2020-01-01',(f:any)=>f.universe.kandidaten[1].industry='Energy']){
  const f=fixture(6);change(f);assert(!calculate(f).stocks['NYSE:T0'].industryContext);
 }
});
check('conflicting issuer industries and duplicate listings are rejected',()=>{
 const f=fixture(6),alt={...f.universe.kandidaten[1],ticker:'ALT',listing_symbol:'NYSE:ALT',industry:'Energy'};
 f.universe.kandidaten.push(alt);f.groups.issuers[1].listings.push(alt.listing_symbol);f.groups.listings[alt.listing_symbol]={...f.groups.listings['NYSE:T1'],inputIdentity:alt};
 assert(!calculate(f).stocks['NYSE:T0'].industryContext);
 const d=fixture(6);d.universe.kandidaten.push({...d.universe.kandidaten[1]});assert(!calculate(d).stocks['NYSE:T0'].industryContext);
});
check('strict existing peers and reviewed business models never replaced',()=>{
 const f=fixture(6);for(const l of Object.values(f.groups.listings) as any[])l.group='one';for(const i of f.groups.issuers)i.classification.group='one';
 const strict=buildSectorComparisons(f.universe,f.groups,f.cache,now),before=JSON.stringify(strict.stocks);addIndustryContext(strict,f.universe,f.groups,f.cache,now);assert.equal(JSON.stringify(strict.stocks),before);
 const g=fixture(6);g.groups.listings['NYSE:T0'].level='reviewed_business_model';assert(!calculate(g).stocks['NYSE:T0'].industryContext);
});
check('missing history and changed identity cannot leak through context',()=>{
 const f=fixture(6);delete f.cache.series['NYSE:T0'];assert(!calculate(f).stocks['NYSE:T0'].industryContext);
 const g=fixture(6),r=calculate(g),row=g.universe.kandidaten[0];assert(selectSectorComparison(r,'NYSE:T0',row,now)?.industryContext);
 assert(!selectSectorComparison(r,'NYSE:T0',{...row,isin:'other'},now)?.industryContext);
 r.stocks['NYSE:T0'].industryContext.observationDate='2020-01-01';assert(!selectSectorComparison(r,'NYSE:T0',row,now)?.industryContext);
});
check('invalid count or nonavailable supplemental report is rejected',()=>{
 for(const change of [{peerIssuers:null},{peerIssuers:4},{state:'missing'},{method:'other'}]){
  const f=fixture(6),r=calculate(f);Object.assign(r.stocks['NYSE:T0'].industryContext,change);assert(!selectSectorComparison(r,'NYSE:T0',f.universe.kandidaten[0],now)?.industryContext);
 }
});
console.log(passed+' intermediate industry checks passed');
