import assert from 'node:assert/strict';
import {withRegulatoryContext as merge,verifiedIntlCapital,verifiedDomesticStandard} from './regulatory-context';
const now=Date.parse('2026-11-09T18:00:00Z');
const row={listing_symbol:'OTC:CBAUF',isin:'AU000000CBA7',currency:'USD',name:'Commonwealth Bank of Australia',security_type:'stock'};
const base={profile:'bank',state:'context_only',sectorRequirements:[]};
const T='apra_adi_centralised_publication';
const record={state:'available',scope:'basel_key_metrics',inputIdentity:row,period:'2026-06-30',identityReviewExpires:'2027-05-08',sourceFileSha256:'a'.repeat(64),sourceType:T,
 metrics:{cet1_ratio:{state:'available',unit:'fraction',sourceField:T+':cet1_ratio',value:.12},tier1_ratio:{state:'available',unit:'fraction',sourceField:T+':tier1_ratio',value:.135}},
 liquidity:{state:'available',method:'intl-lcr-v1',reportedRatio:1.32,nsfr:1.151,period:'2026-06-30',unit:'fraction'},capitalRequirement:null};
const archive=(r:any=record,extra:any={})=>({schema:1,generatedAt:'2026-11-09T17:30:00Z',stocks:{},intlBanks:{schema:1,source:'intl_basel_key_metrics',state:'ready',stocks:{'OTC:CBAUF':r}},...extra});
let checks=0;
function test(name:string,f:()=>void){f();checks++;console.log('OK '+name)}
test('APRA capital and LCR reach the balance context; no requirement means it stays open',()=>{
 const r=merge(base,row,archive(),true,now);
 assert.equal(r.bankCapital.scope,'basel_key_metrics');assert.equal(r.bankCapital.liquidity.reportedRatio,1.32);assert.equal(r.bankCapital.capitalRequirement,null);
 assert.deepEqual(r.sectorAssessment.fulfilledRequirements,['regulatory_capital_CET1','liquidity_LCR_or_local_equivalent']);
 assert.ok(r.sectorRequirements.includes('institution_specific_capital_requirement'));
});
test('a disclosed KM1 requirement is recomputed and closes the bank-specific requirement',()=>{
 const r=merge(base,row,archive({...record,capitalRequirement:{state:'available',method:'basel-km1-cet1-requirement-v1',unit:'fraction',value:.1025,comparisonPeriod:'2026-06-30',reviewExpires:'2027-05-08',headroomPercentagePoints:99}}),true,now);
 assert.ok(Math.abs(r.bankCapital.capitalRequirement.headroomPercentagePoints-1.75)<1e-9);
 assert.ok(r.sectorAssessment.fulfilledRequirements.includes('institution_specific_capital_requirement'));
});
test('stale quarter, wrong source tag, identity mismatch and inconsistent hierarchy are rejected',()=>{
 assert.ok(verifiedIntlCapital(archive(),row,true,now));
 assert.equal(verifiedIntlCapital(archive({...record,period:'2025-12-31'}),row,true,now),null);
 assert.equal(verifiedIntlCapital(archive({...record,metrics:{cet1_ratio:{...record.metrics.cet1_ratio,sourceField:'EBA:2520140'}}}),row,true,now),null);
 assert.equal(verifiedIntlCapital(archive({...record,inputIdentity:{...row,security_type:'dr'}}),row,true,now),null);
 assert.equal(verifiedIntlCapital(archive({...record,metrics:{...record.metrics,tier1_ratio:{...record.metrics.tier1_ratio,value:.11}}}),row,true,now),null);
 assert.equal(verifiedIntlCapital(archive({...record,liquidity:{...record.liquidity,period:'2026-03-31'}}),row,true,now)!.liquidity,null);
});
test('Basel CR1 defaulted-loan ratio passes only with matching method and period',()=>{
 const credit={state:'available',method:'basel-cr1-default-v1',unit:'fraction',ratio:.011,period:'2026-06-30'};
 const r=merge(base,row,archive({...record,creditQuality:credit}),true,now);
 assert.equal(r.bankCapital.creditQuality.ratio,.011);assert.ok(r.sectorAssessment.fulfilledRequirements.includes('asset_quality_nonperforming_loans'));
 assert.equal(verifiedIntlCapital(archive({...record,creditQuality:{...credit,period:'2026-03-31'}}),row,true,now)!.creditQuality,null);
 assert.equal(verifiedIntlCapital(archive({...record,creditQuality:{...credit,method:'eba-npl-v1'}}),row,true,now)!.creditQuality,null);
});
test('Basel CR1 with its own reporting date (Japan) needs source, SHA-256 and age <= 270 days',()=>{
 const credit={state:'available',method:'basel-cr1-default-v1',unit:'fraction',ratio:.0107,period:'2026-03-31',periodBasis:'separate_cr1',sourceType:'basel_pillar3_cr1',sourceUrl:'https://example.org/b3.pdf',sourceFileSha256:'d'.repeat(64),sourceDetail:'PDF page 30, CR1 row 1'};
 const ok=(c:any)=>verifiedIntlCapital(archive({...record,creditQuality:c}),row,true,now)!.creditQuality;
 assert.equal(ok(credit).ratio,.0107);
 assert.equal(ok({...credit,periodBasis:undefined}),null,'without the flag the period must match');
 assert.equal(ok({...credit,sourceFileSha256:'x'}),null);
 assert.equal(ok({...credit,sourceType:'basel_pillar3_km1'}),null);
 assert.equal(ok({...credit,sourceDetail:''}),null);
 assert.equal(ok({...credit,period:'2026-09-30'}),null,'not after the KM1 date');
 assert.equal(ok({...credit,period:'2026-02-10'}),null,'older than 270 days');
});
test('Japanese domestic standard: CET1 requirement and LCR not applicable, credit quality stays open; proofs and identity are rechecked',()=>{
 const drow={listing_symbol:'TSE:8308',ticker:'8308.T',isin:'JP3500610005',currency:'JPY',name:'Resona',security_type:'stock'};
 const dom={state:'not_applicable',scope:'domestic_capital_standard',standard:'jp_domestic_core_capital',inputIdentity:drow,period:'2026-06-30',identityReviewExpires:'2027-05-08',
  sourceUrl:'https://example.org/r.pdf',sourceFileSha256:'e'.repeat(64),sourceDetail:'p. 1',lcrRule:{url:'https://www.fsa.go.jp/x.pdf',sha256:'d'.repeat(64),location:'Notice 62 Art. 2'},domesticCapitalRatio:.1265};
 const arc=(r:any)=>({schema:1,generatedAt:'2026-11-09T17:30:00Z',stocks:{},intlBanks:{schema:1,source:'intl_basel_key_metrics',state:'ready',stocks:{'TSE:8308':r}}});
 const r=merge(base,drow,arc(dom),true,now);
 assert.equal(r.bankCapital.scope,'domestic_capital_standard');
 assert.deepEqual(r.sectorAssessment.notApplicableRequirements,['regulatory_capital_CET1','institution_specific_capital_requirement','liquidity_LCR_or_local_equivalent']);
 assert.deepEqual(r.sectorAssessment.openRequirements,['asset_quality_nonperforming_loans']);
 for(const bad of [{period:'2026-01-30'},{lcrRule:null},{sourceFileSha256:'x'},{standard:'x'},{state:'available'},{inputIdentity:{...drow,isin:'JP0000000001'}},{identityReviewExpires:'2026-11-01'}])
  assert.equal(verifiedDomesticStandard(arc({...dom,...bad}),drow,true,now),null,JSON.stringify(bad));
 assert.equal(verifiedDomesticStandard(arc(dom),drow,false,now),null,'identity check failed upstream');
});
console.log(checks+' international capital checks passed');
