import assert from 'node:assert/strict';
import {addFxPeerContext,convertToEuro,fxCheck} from './fx-peer-context';
import {buildSectorComparisons,selectSectorComparison} from './sector-comparison';
const now=Date.parse('2026-10-26T22:00:00Z'),DAY=86400000;
const dates=Array.from({length:560},(_,i)=>new Date(now-(560-i)*DAY).toISOString().slice(0,10)).filter(d=>![0,6].includes(new Date(d).getUTCDay())).slice(-390);
function fixture(){
 const rows:any[]=[],listings:any={},issuers:any[]=[],series:any={},rates:any={};
 dates.forEach((d,i)=>rates[d]={USD:1+i*.001,JPY:150+i*.1,GBP:.8+i*.0001});
 for(let i=0;i<7;i++){const s='NYSE:T'+i,currency=i===0?'EUR':i<4?'USD':'JPY';const row={listing_symbol:s,currency,isin:'TEST'+i,name_full:'Firm'+i,industry:'Same business',security_type:'stock'};rows.push(row);
  listings[s]={issuerId:'issuer'+i,group:'one-business',level:'provider_subindustry',inputIdentity:{...row}};issuers.push({id:'issuer'+i,representative:s,listings:[s],classification:{group:'one-business',label:'Same business'}});
  series[s]={schema:1,format:'sector-series',adjustment:'total_return',symbol:s,currency,retrievedAt:new Date(now-3600000).toISOString(),points:dates.map((d,j)=>[d,(100+j*(i+1)*.1)*(currency==='EUR'?1:rates[d][currency])])};
 }
 return {universe:{kandidaten:rows},groups:{schema:1,method:'issuer-business-groups-v1',generatedAt:new Date(now-3600000).toISOString(),listings,issuers},cache:{schema:1,series},fx:{schema:1,source:'ECB euro foreign exchange reference rates',base:'EUR',quoteConvention:'currency_units_per_EUR',retrievedAt:new Date(now-3600000).toISOString(),lastObservation:dates.at(-1),rates}};
}
function calculate(f:ReturnType<typeof fixture>){return addFxPeerContext(buildSectorComparisons(f.universe,f.groups,f.cache,now),f.universe,f.groups,f.cache,f.fx,now);}
let count=0;function check(name:string,fn:()=>void){fn();count++;console.log('OK '+name);}
check('converts by dividing currency per EUR and preserves strict result',()=>{const f=fixture(),before=JSON.stringify(f);const r=calculate(f).stocks['NYSE:T0'];assert.equal(r.state,'missing');assert.equal(r.reason,'fewer_than_five_same_currency_issuers');const c=r.currencyAdjustedContext;assert.equal(c.state,'available');assert.equal(c.peerIssuers,6);assert.equal(c.score,null);assert.equal(c.currency,'EUR');assert.deepEqual(c.fxCurrencies,['EUR','JPY','USD']);assert.equal(JSON.stringify(f),before);
 const s=convertToEuro(f.cache.series['NYSE:T1'],f.fx,now).series!;assert.ok(Math.abs(s.points[20][1]-104)<1e-9);
});
check('constant foreign price with changing FX has EUR return',()=>{const f=fixture();const h=f.cache.series['NYSE:T1'];h.points=h.points.map(([d]:any)=>[d,100]);const s=convertToEuro(h,f.fx,now).series!;assert.ok(s.points.at(-1)![1]<s.points[0][1]);});
check('pence and pounds convert identically',()=>{const f=fixture(),h=f.cache.series['NYSE:T1'];h.currency='GBP';const a=convertToEuro(h,f.fx,now).series!;h.currency='GBp';h.points=h.points.map(([d,v]:any)=>[d,v*100]);const b=convertToEuro(h,f.fx,now).series!;a.points.forEach(([d,v]:any,i:number)=>{assert.equal(b.points[i][0],d);assert.ok(Math.abs(b.points[i][1]-v)<1e-10);});});
check('no forward filling missing dates',()=>{const f=fixture();delete f.fx.rates[dates[40]];const s=convertToEuro(f.cache.series['NYSE:T1'],f.fx,now).series!;assert.ok(!s.points.some((p:any)=>p[0]===dates[40]));});
check('stale FX does not produce comparison',()=>{const f=fixture();f.fx.retrievedAt='2026-10-20T00:00:00Z';assert.equal(calculate(f).summary.currencyAdjustedContext.available,0);});
check('invalid and future rates rejected',()=>{for(const rate of [0,-1,NaN,Infinity]){const f=fixture();f.fx.rates[dates[0]].USD=rate;assert.ok(fxCheck(f.fx,now));}const f=fixture();f.fx.rates['2026-10-26']={USD:1};assert.ok(fxCheck(f.fx,now));});
check('wrong source convention rejected',()=>{const f=fixture();f.fx.quoteConvention='EUR_per_currency';assert.ok(fxCheck(f.fx,now));});
check('wrong history currency or membership cannot enter context',()=>{const f=fixture();f.cache.series['NYSE:T0'].currency='JPY';assert.ok(!calculate(f).stocks['NYSE:T0'].currencyAdjustedContext);const g=fixture();g.groups.listings['NYSE:T0'].inputIdentity.isin='WRONG';assert.ok(!calculate(g).stocks['NYSE:T0'].currencyAdjustedContext);});
check('unsupported currency never guessed',()=>{const f=fixture();for(const d of dates)delete f.fx.rates[d].JPY;assert.equal(calculate(f).summary.currencyAdjustedContext.available,0);});
check('five independent peers still required',()=>{const f=fixture();f.groups.issuers=f.groups.issuers.slice(0,5);assert.ok(!calculate(f).stocks['NYSE:T0'].currencyAdjustedContext);});
check('duplicate issuer not counted twice',()=>{const f=fixture();f.groups.issuers.push(structuredClone(f.groups.issuers[1]));assert.equal(calculate(f).stocks['NYSE:T0'].currencyAdjustedContext.peerIssuers,6);});
check('other business groups cannot fill gap',()=>{const f=fixture();f.groups.issuers[1].classification.group='unrelated';f.groups.listings['NYSE:T1'].group='unrelated';f.groups.issuers[2].classification.group='unrelated';f.groups.listings['NYSE:T2'].group='unrelated';assert.ok(!calculate(f).stocks['NYSE:T0'].currencyAdjustedContext);});
check('reader rejects stale or wrong identity context',()=>{const f=fixture(),report=calculate(f),row=f.universe.kandidaten[0];assert.ok(selectSectorComparison(report,'NYSE:T0',row,now)?.currencyAdjustedContext);report.stocks['NYSE:T0'].currencyAdjustedContext.originalCurrency='JPY';assert.ok(!selectSectorComparison(report,'NYSE:T0',row,now)?.currencyAdjustedContext);});
check('cached history tied to another input is excluded',()=>{const f=fixture();f.cache.series['NYSE:T0'].inputIdentity={...f.universe.kandidaten[0],isin:'WRONG'};assert.ok(!calculate(f).stocks['NYSE:T0'].currencyAdjustedContext);});
check('consumer removes old FX despite fresh sector report',()=>{const f=fixture(),report=calculate(f);report.stocks['NYSE:T0'].currencyAdjustedContext.fxRetrievedAt='2026-10-20T00:00:00Z';assert.ok(!selectSectorComparison(report,'NYSE:T0',f.universe.kandidaten[0],now)?.currencyAdjustedContext);});
console.log(count+' FX context checks passed');

