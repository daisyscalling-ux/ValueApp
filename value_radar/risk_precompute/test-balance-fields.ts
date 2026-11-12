import assert from 'node:assert/strict';
import {assessBalance,balanceProfile,profileOverride} from './balance-profile';
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
test('refresh starts two days before expiry without redating values',()=>{
 const a=annual(),observed='2026-10-20T19:00:00Z';const b=assessBalance(row,a,observed,true,now);
 assert.equal(b.state,'available');assert.equal(b.refreshDue,true);assert.equal(b.expiresAt,'2026-10-27T19:00:00.000Z');assert.equal(b.retrievedAt,observed);
 assert.equal(calc(a).refreshDue,false);
});
test('older retained field sets the earliest refresh deadline',()=>{
 const a=annual();a.field_sources.capex={retrieved_at:'2026-10-20T18:00:00Z'};const b=calc(a);
 assert.equal(b.refreshDue,true);assert.equal(b.expiresAt,'2026-10-27T18:00:00.000Z');
});
test('reviewed ISIN override: insurer behind a broker classification, flagged and bounded',()=>{
 const t=Date.parse('2026-11-10T20:00:00Z'),ta='2026-11-10T19:00:00Z',g={industry:'Insurance brokers/Services',metadata_asof:ta,isin:'IT0000062072'};
 const an=()=>({...annual(),end:'2025-12-31'}),run=(r:any)=>assessBalance(r,an(),ta,true,t);
 assert.equal(balanceProfile(g,t),'insurer');
 const b=run(g);assert.equal(b.profile,'insurer');assert.equal(b.profileSource.kind,'reviewed_isin_override');assert.equal(b.profileSource.vendorIndustry,'Insurance brokers/Services');
 assert.deepEqual(b.sectorRequirements,['eligible_own_funds','solvency_requirement','jurisdiction_and_regulatory_scope']);assert.equal(b.ratios,null);
 assert.equal(balanceProfile({...g,isin:'IT0000062071'},t),'corporate','other ISIN');
 assert.equal(balanceProfile({...g,industry:'Multi-line insurance'},t),'insurer');assert.equal(run({...g,industry:'Multi-line insurance'}).profileSource,undefined,'vendor fixed: no override flag');
 assert.equal(balanceProfile({...g,industry:'Software'},t),'corporate','vendor industry changed: override lapses');
 assert.equal(balanceProfile({industry:'Insurance brokers/Services',metadata_asof:at,isin:'US3635761097'},t),'corporate','real broker stays corporate');
 assert.equal(balanceProfile({...g,metadata_asof:'2026-01-01T00:00:00Z'},t),'unclassified','stale metadata wins');
 const e={isin:'IT0000062072',vendorIndustry:'Insurance brokers/Services',profile:'insurer',evidenceUrl:'https://x.example/a.pdf',evidenceSha256:'a'.repeat(64),reviewed_on:'2026-11-10',review_expires:'2027-05-10'};
 const reg=(x:any)=>({schema:1,method:'reviewed-isin-profile-v1',entries:x});
 const late=Date.parse('2027-05-11T00:00:00Z'),early=Date.parse('2026-11-09T00:00:00Z'),mid=Date.parse('2026-12-01T00:00:00Z');
 assert.ok(profileOverride(g,mid,reg([e])));
 assert.equal(profileOverride(g,late,reg([e])),null,'expired review');assert.equal(profileOverride(g,early,reg([e])),null,'review in the future');
 assert.equal(profileOverride(g,mid,reg([e,e])),null,'duplicate ISIN ambiguous');
 assert.equal(profileOverride(g,mid,reg([{...e,profile:'corporate'}])),null,'only financial profiles');
 assert.equal(profileOverride(g,mid,reg([{...e,evidenceSha256:''}])),null,'hash required');
 assert.equal(profileOverride(g,mid,{...reg([e]),method:'other'}),null,'method');
});
test('FCF / revenue substitute from the same dated annual record (11.11.2026)',()=>{
 const a:any=annual();a.fields.revenue=200;const b=calc(a);
 assert.equal(b.supplementalMetrics.fcfRevenue.state,'available');assert.equal(b.supplementalMetrics.fcfRevenue.value,(15-5)/200);
 assert.ok(b.supplementalMetrics.fcfRevenue.basis.fields.revenue,'revenue provenance kept');
 assert.equal(b.metrics.fcfRevenue,undefined,'never a main metric');
 const mismatch:any=annual();mismatch.fields.revenue=200;mismatch.field_sources={operating_cashflow:{start:'2025-07-01'},capex:{start:'2025-07-01'},revenue:{start:'2025-01-01'}};
 assert.equal(calc(mismatch).supplementalMetrics.fcfRevenue.state,'missing','different periods');
 for(const rev of [0,-5,undefined]){const x:any=annual();x.fields.revenue=rev;assert.equal(calc(x).supplementalMetrics.fcfRevenue.state,'missing',String(rev))}
 const old:any=annual();old.fields.revenue=200;old.end='2024-01-31';assert.equal(calc(old).supplementalMetrics.fcfRevenue.state,'missing','stale annual');
 const fin=assessBalance({industry:'Major Banks',metadata_asof:at},{...annual(),fields:{...annual().fields,revenue:200}},at,true,now);
 assert.equal(fin.supplementalMetrics.fcfRevenue,undefined,'financials never get it');
});
console.log(count+' field-level balance checks passed');
test('Storebrand: vendor "Savings banks" corrected to insurer from the real registry entry (12.11.2026)',()=>{
 const t=Date.parse('2026-11-12T20:00:00Z'),row={industry:'Savings banks',metadata_asof:'2026-11-12T12:00:00Z',isin:'NO0003053605'};
 assert.equal(balanceProfile(row,t),'insurer');assert.equal(profileOverride(row,t)?.evidencePages,'37');
 assert.equal(balanceProfile({...row,industry:'Regional Banks'},t),'bank','vendor industry changed: override no longer applies');
 assert.equal(balanceProfile({...row,isin:'NO0003053606'},t),'bank','other ISIN');
 assert.equal(balanceProfile(row,Date.parse('2027-05-13T00:00:00Z')),'unclassified','metadata stale; override would also have expired');
});
