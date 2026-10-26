import assert from 'node:assert/strict';
import {assessBalance} from './balance-profile';
const now=Date.parse('2026-10-25T20:00:00Z'),at='2026-10-25T19:00:00Z';
const row={industry:'Software',metadata_asof:at};
const annual=()=>({source:'Yahoo annual statements',period_type:'annual',end:'2026-06-30',currency:'USD',fields:{total_assets:100,total_debt:10,cash:20,operating_cashflow:15,capex:-5,equity:40,net_income:10},field_sources:{} as any});
const calc=(a:any,r:any=row)=>assessBalance(r,a,at,true,now);
let count=0;const test=(name:string,fn:()=>void)=>{fn();count++;console.log('OK '+name)};
test('stale capex blocks only FCF, not debt or operating cashflow',()=>{
 const a=annual();a.field_sources.capex={retrieved_at:'2026-09-01',source:a.source};const b=calc(a);
 assert.equal(b.state,'partial');assert.equal(b.metrics.fcfAssets.value,null);assert.equal(b.metrics.netDebtAssets.value,-.1);assert.equal(b.supplementalMetrics.operatingCashflowAssets.value,.15);
 assert.deepEqual(b.fieldQuality.capex,['field_retrieval_stale']);assert.equal(b.ratios,null);
});
test('mixed equity does not erase same-period earnings in banks',()=>{
 const a=annual();a.field_sources.equity={end:'2025-06-30'};const b=calc(a,{...row,industry:'Major banks'});
 assert.equal(b.state,'partial');assert.equal(b.metrics.bookEquityAssets.value,null);assert.equal(b.metrics.netIncomeEndingAssets.value,.1);
});
test('unverified assets block every ratio',()=>{
 const a=annual();a.field_sources.total_assets={currency:'EUR'};const b=calc(a);
 assert.equal(b.state,'missing');assert(Object.values({...b.metrics,...b.supplementalMetrics}).every((m:any)=>m.value===null));
});
test('annual staleness and wrong identity still block all fields',()=>{
 for(const b of [assessBalance(row,annual(),'2026-09-01',true,now),assessBalance(row,annual(),at,false,now)]){
 assert.equal(b.state,'missing');assert.equal(b.supplementalMetrics.cashAssets.value,null);}
});
test('different duration starts cannot produce complete FCF',()=>{
 const a=annual();a.field_sources.capex={start:'2025-07-01'};a.field_sources.operating_cashflow={start:'2026-01-01'};
 const b=calc(a);assert.equal(b.state,'partial');assert.equal(b.metrics.fcfAssets.value,null);assert.equal(b.ratios,null);
});
test('invalid cash does not contaminate independent FCF',()=>{
 const a=annual();a.field_sources.cash={currency:'EUR'};const b=calc(a);
 assert.equal(b.metrics.netDebtAssets.value,null);assert.equal(b.metrics.fcfAssets.value,.1);assert.equal(b.anchors?.cash,null);
});
test('overflow is never available',()=>{
 const a=annual();a.fields.total_assets=1e-300;a.fields.total_debt=1e300;
 const b=calc(a);assert.equal(b.metrics.netDebtAssets.value,null);assert.notEqual(b.state,'available');
});
test('investment managers use explicit sector context with additional requirements',()=>{
 for(const industry of ['Investment managers','Asset Management','Asset Management & Custody Banks']){
 const b=calc(annual(),{...row,industry});assert.equal(b.profile,'specialist_financial');assert.equal(b.state,'context_only');
 assert.equal(b.metrics.fcfAssets.state,'not_applicable');assert(b.sectorRequirements.includes('net_flows_and_fee_dependence'));}
});
test('ambiguous brokers are not automatically pure asset managers',()=>{
 const b=calc(annual(),{...row,industry:'Capital markets'});assert(!b.sectorRequirements.includes('net_flows_and_fee_dependence'));
});
test('sources retained individually and input never mutated',()=>{
 const a=annual();a.field_sources.cash={source:'Other dated source',end:a.end,currency:a.currency};const before=JSON.stringify(a);const b=calc(a);
 assert.equal(b.metrics.netDebtAssets.basis?.fields.cash.source,'Other dated source');assert.equal(JSON.stringify(a),before);
});
console.log(count+' field-level balance checks passed');
