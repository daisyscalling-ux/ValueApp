import assert from 'node:assert/strict';
import {withRegulatoryContext as merge} from './regulatory-context';
const now=Date.parse('2026-10-27T12:00:00Z');
const row={listing_symbol:'NYSE:EX',isin:'US0378331005',currency:'USD',name:'Example',security_type:'common_stock'};
const base={profile:'bank',state:'context_only',metrics:{bookEquityAssets:{value:.1}},sectorRequirements:['regulatory_capital_CET1','liquidity_LCR_or_local_equivalent','asset_quality_nonperforming_loans']};
const record={state:'available',scope:'listed_consolidated_holding',inputIdentity:row,period:'2026-06-30',sourceImportedAt:'2026-10-19T12:00:00Z',identityReviewExpires:'2027-04-18',sourceFileSha256:'a'.repeat(64),metrics:{cet1_ratio:{state:'available',unit:'fraction',sourceField:'BHCAP793',value:.14}}};
const archive={schema:1,source:'reviewed_FR_Y9C_holding_capital',generatedAt:'2026-10-27T10:00:00Z',stocks:{'NYSE:EX':record}};
const run=(r:any=record,b:any=base,a:any=archive)=>merge(b,row,{...a,stocks:{'NYSE:EX':r}},true,now);
let checks=0;
function test(name:string,f:()=>void){f();checks++;console.log('OK '+name)}
test('only CET1 fulfilled, other requirements remain and baseline preserved',()=>{
 const r=run();assert.deepEqual(r.metrics,base.metrics);assert.equal(r.state,base.state);assert.equal(r.sectorAssessment.scoreContribution,0);
 assert.deepEqual(r.sectorAssessment.fulfilledRequirements,['regulatory_capital_CET1']);assert.equal(r.sectorRequirements.length,3);assert.ok(r.sectorRequirements.includes('institution_specific_capital_requirement'));assert.equal(base.sectorRequirements.length,3);
});
test('identity, period, expiry, source and dates fail closed',()=>{
 for(const patch of [{inputIdentity:{...row,isin:'other'}},{period:'2025-01-01'},{period:'2026-11-01'},{period:'2026-02-30'},{identityReviewExpires:'unknown'},{identityReviewExpires:'2026-10-26'},{sourceImportedAt:'bad'},{sourceImportedAt:'2026-01-01'},{sourceFileSha256:'bad'},{scope:'subsidiary'}]){
  const r=run({...record,...patch});assert.equal(r.bankCapital,null);assert.ok(r.sectorRequirements.includes('regulatory_capital_CET1'));
 }
 for(const generatedAt of ['2026-10-25T00:00:00Z','2026-10-28T00:00:00Z','bad'])assert.equal(run(record,base,{...archive,generatedAt}).bankCapital,null);
 assert.equal(merge(base,row,archive,false,now).bankCapital,null);
});
test('insurers cannot inherit bank ratios, specialists remain open, corporates unchanged',()=>{
 assert.equal(run(record,{...base,profile:'insurer'}).bankCapital,null);
 const s=run(record,{...base,profile:'specialist_financial',sectorRequirements:['business_model_and_applicable_capital_framework']});assert.ok(s.bankCapital);assert.deepEqual(s.sectorAssessment.fulfilledRequirements,[]);assert.equal(s.sectorRequirements.length,1);
 const c={...base,profile:'corporate'};assert.equal(run(record,c),c);
});
test('units, finite values and hierarchy validated; zero is a real observation',()=>{
 for(const value of [NaN,Infinity,-.1,14,true])assert.equal(run({...record,metrics:{cet1_ratio:{...record.metrics.cet1_ratio,value}}}).bankCapital,null);
 assert.equal(run({...record,metrics:{cet1_ratio:{...record.metrics.cet1_ratio,value:0}}}).bankCapital.metrics.cet1_ratio.value,0);
 assert.equal(run({...record,metrics:{...record.metrics,tier1_ratio:{state:'available',unit:'fraction',sourceField:'BHCA7206',value:.1}}}).bankCapital,null);
});
console.log(`${checks} regulatory integration tests passed`);
