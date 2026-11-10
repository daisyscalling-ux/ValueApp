import assert from 'node:assert/strict';
import {withRegulatoryContext as merge,verifiedEuCapital} from './regulatory-context';
const now=Date.parse('2026-11-09T18:00:00Z');
const row={listing_symbol:'MIL:EX',isin:'IT0000072618',currency:'EUR',name:'Esempio',security_type:'stock'};
const base={profile:'bank',state:'context_only',sectorRequirements:['asset_quality_nonperforming_loans']};
const record={state:'available',scope:'eu_prudential_group',lei:'2W8N8UU78PMDQKZENC08',inputIdentity:row,period:'2025-06-30',sourceImportedAt:'2026-11-09T17:00:00Z',identityReviewExpires:'2027-05-08',sourceFileSha256:'a'.repeat(64),
 metrics:{cet1_ratio:{state:'available',unit:'fraction',sourceField:'EBA:2520140',value:.13},tier1_ratio:{state:'available',unit:'fraction',sourceField:'EBA:2520141',value:.15},leverage_ratio:{state:'available',unit:'fraction',sourceField:'EBA:2520905',value:.058}},
 capitalRequirement:{state:'available',method:'ecb-p2r-partial-cet1-v1',unit:'fraction',value:.0784375,comparisonPeriod:'2025-06-30',reviewExpires:'2027-05-08',sourceSha256:'b'.repeat(64),headroomPercentagePoints:99},
 creditQuality:{state:'available',method:'eba-npl-v1',unit:'fraction',ratio:.022,period:'2025-06-30',lei:'2W8N8UU78PMDQKZENC08',sourceFileSha256:'c'.repeat(64)},liquidity:{state:'available'}};
const archive=(r:any=record,extra:any={})=>({schema:1,generatedAt:'2026-11-09T17:30:00Z',stocks:{},euBanks:{schema:1,source:'eba_transparency_ecb_p2r',state:'ready',stocks:{'MIL:EX':r}},...extra});
let checks=0;
function test(name:string,f:()=>void){f();checks++;console.log('OK '+name)}
test('EU bank capital, partial requirement and NPL reach the balance context',()=>{
 const r=merge(base,row,archive(),true,now);
 assert.equal(r.bankCapital.scope,'eu_prudential_group');
 assert.ok(Math.abs(r.bankCapital.capitalRequirement.headroomPercentagePoints-(.13-.0784375)*100)<1e-9,'headroom recomputed, stored value ignored');
 assert.equal(r.bankCapital.creditQuality.ratio,.022);
 assert.equal(r.bankCapital.liquidity,null,'no LCR in this source');
 assert.deepEqual(r.sectorAssessment.fulfilledRequirements,['regulatory_capital_CET1','asset_quality_nonperforming_loans']);
 assert.ok(r.sectorRequirements.includes('institution_specific_capital_requirement'),'partial requirement does not close the bank-specific requirement');
});
test('data up to 24 months count, older or future periods do not',()=>{
 assert.ok(verifiedEuCapital(archive(),row,true,now));
 assert.equal(verifiedEuCapital(archive({...record,period:'2024-10-31'}),row,true,now),null);
 assert.equal(verifiedEuCapital(archive({...record,period:'2026-12-31'}),row,true,now),null);
});
test('identity, expired review, stale archive and wrong source reject the record',()=>{
 assert.equal(verifiedEuCapital(archive(),row,false,now),null);
 assert.equal(verifiedEuCapital(archive({...record,inputIdentity:{...row,isin:'IT0005239360'}}),row,true,now),null);
 assert.equal(verifiedEuCapital(archive({...record,identityReviewExpires:'2026-11-01'}),row,true,now),null);
 assert.equal(verifiedEuCapital(archive(record,{generatedAt:'2026-11-07T00:00:00Z'}),row,true,now),null);
 assert.equal(verifiedEuCapital({...archive(),euBanks:{...archive().euBanks,source:'other'}},row,true,now),null);
});
test('inconsistent capital hierarchy is rejected; foreign codes and mismatched requirement or credit are dropped',()=>{
 assert.equal(verifiedEuCapital(archive({...record,metrics:{...record.metrics,tier1_ratio:{...record.metrics.tier1_ratio,value:.12}}}),row,true,now),null);
 const r=verifiedEuCapital(archive({...record,metrics:{...record.metrics,leverage_ratio:{...record.metrics.leverage_ratio,sourceField:'BHCA7204'}},
  capitalRequirement:{...record.capitalRequirement,comparisonPeriod:'2025-03-31'},creditQuality:{...record.creditQuality,lei:'X'.repeat(20)}}),row,true,now)!;
 assert.equal(r.metrics.leverage_ratio,undefined);assert.equal(r.capitalRequirement,null);assert.equal(r.creditQuality,null);
});
test('Pillar 3 KM1: full CET1 requirement and LCR close the bank-specific requirements',()=>{
 const src={sourceUrl:'https://errp.eba.europa.eu/public-documents/CODIS/input/X.zip',sourceFileSha256:'d'.repeat(64)};
 const km1Req={state:'available',method:'eba-p3dh-km1-cet1-requirement-v1',unit:'fraction',value:.0992,cet1Ratio:.13,comparisonPeriod:'2026-06-30',reviewExpires:'2027-05-08',headroomPercentagePoints:99,...src};
 const lcr={state:'available',method:'eba-p3dh-km1-lcr-v1',unit:'fraction',reportedRatio:1.376,nsfr:1.198,period:'2026-06-30',...src};
 const r=merge(base,row,archive({...record,capitalRequirement:km1Req,liquidity:lcr}),true,now);
 assert.ok(Math.abs(r.bankCapital.capitalRequirement.headroomPercentagePoints-(.13-.0992)*100)<1e-9,'headroom from KM1 CET1 of the same date, stored value ignored');
 assert.equal(r.bankCapital.liquidity.reportedRatio,1.376);
 assert.deepEqual(r.sectorAssessment.fulfilledRequirements,['regulatory_capital_CET1','asset_quality_nonperforming_loans','institution_specific_capital_requirement','liquidity_LCR_or_local_equivalent']);
 for(const bad of [{comparisonPeriod:'2025-12-31'},{sourceUrl:'https://example.org/x.zip'},{sourceFileSha256:'x'},{reviewExpires:'2026-01-01'},{value:.4},{cet1Ratio:2}])
  assert.equal(verifiedEuCapital(archive({...record,capitalRequirement:{...km1Req,...bad}}),row,true,now)!.capitalRequirement,null,JSON.stringify(bad));
 for(const bad of [{period:'2025-12-31'},{reportedRatio:20},{sourceUrl:'https://example.org/x.zip'},{method:'intl-lcr-v1'}])
  assert.equal(verifiedEuCapital(archive({...record,liquidity:{...lcr,...bad}}),row,true,now)!.liquidity,null,JSON.stringify(bad));
});
test('US holdings keep precedence and non-banks are untouched',()=>{
 assert.equal(merge({...base,profile:'corporate'},row,archive(),true,now).bankCapital,undefined);
 const us={state:'available',scope:'listed_consolidated_holding',inputIdentity:row,period:'2026-06-30',sourceImportedAt:'2026-10-19T12:00:00Z',identityReviewExpires:'2027-04-18',sourceFileSha256:'a'.repeat(64),metrics:{cet1_ratio:{state:'available',unit:'fraction',sourceField:'BHCAP793',value:.14}}};
 const r=merge(base,row,archive(record,{source:'reviewed_FR_Y9C_holding_capital',stocks:{'MIL:EX':us}}),true,now);
 assert.equal(r.bankCapital.scope,'listed_consolidated_holding');
});
console.log(checks+' EU capital checks passed');
