import assert from 'node:assert/strict';
import {verifiedLiquidity,verifiedLiquidityExemption,liquiditySourceLabel} from './holding-liquidity';
const now=Date.parse('2026-11-01T12:00:00Z'),p={rssdId:'1951350',holdingName:'CITIGROUP INC.',period:'2026-06-30'};
const r={...p,state:'available',method:'reviewed-holding-lcr-v1',scope:'listed_consolidated_holding',averaging:'quarter_average',unit:'fraction',currency:'USD',hqla:641200000000,netOutflows:567500000000,reportedRatio:1.13,ratioRoundingTolerance:.005,reviewedOn:'2026-11-01',reviewExpires:'2026-12-27',sourceUrl:'https://www.sec.gov/Archives/edgar/data/831001/000083100126000045/c-20260630.htm',sourceSection:'Liquidity Risk, page 65'};
assert.equal(verifiedLiquidity(r,p,now)?.reportedRatio,1.13);
for(const patch of [{rssdId:'other'},{holdingName:'subsidiary'},{period:'2026-03-31'},{unit:'percent'},{reportedRatio:113},{hqla:NaN},{netOutflows:0},{scope:'bank_subsidiary'},{averaging:'end_of_period'},{reviewedOn:'2026-11-02'},{reviewExpires:'2026-10-31'},{ratioRoundingTolerance:.1},{sourceUrl:'javascript:alert(1)'},{sourceSection:''},{basis:'estimate'}])assert.equal(verifiedLiquidity({...r,...patch},p,now),null);
// Nur Quote (ratio_only, 11.11.2026): HQLA optional, Nettoabfluesse nie zurueckgerechnet.
const q={...r,basis:'ratio_only',hqla:684000000000,netOutflows:null,ratioRoundingTolerance:null,reportedRatio:1.12};
assert.equal(verifiedLiquidity(q,p,now)?.reportedRatio,1.12);
assert.equal(verifiedLiquidity({...q,hqla:null},p,now)?.basis,'ratio_only');
for(const patch of [{netOutflows:610000000000},{reportedRatio:0},{reportedRatio:112},{hqla:-1},{period:'2026-03-31'}])assert.equal(verifiedLiquidity({...q,...patch},p,now),null);
// Gesetzliche LCR-Offenlegung der Bank (12 CFR 249 Subpart J, 12.11.2026): https, SHA-256 und Betraege Pflicht.
const d={...r,sourceKind:'bank_lcr_public_disclosure',sourceUrl:'https://d1io3yog0oux5.cloudfront.net/x/pnc/db/2467/24037/disclosure/Q3_2026_LCR_Disclosures_FINAL.pdf',sourceSha256:'e'.repeat(64)};
assert.equal(verifiedLiquidity(d,p,now)?.reportedRatio,1.13);assert.match(liquiditySourceLabel(d),/12 CFR 249/);assert.match(liquiditySourceLabel(r),/SEC/);
for(const patch of [{sourceSha256:undefined},{sourceSha256:'E'.repeat(64)},{sourceUrl:'http://d1io3yog0oux5.cloudfront.net/x.pdf'},{sourceUrl:'not a url'},{sourceKind:'press_release'},
  {basis:'ratio_only',netOutflows:null,ratioRoundingTolerance:null},{hqla:700000000000},{sourceSection:' '}])assert.equal(verifiedLiquidity({...d,...patch},p,now),null,JSON.stringify(patch));
assert.equal(verifiedLiquidity({...r,sourceUrl:d.sourceUrl},p,now),null,'without sourceKind only SEC documents count');
// Ausnahme Kategorie IV mit woertlichem Beleg
const e={...p,state:'not_applicable',method:'reviewed-holding-lcr-v1',scope:'listed_consolidated_holding',reason:'us_category_iv_lcr_not_applicable',quote:'As a Category IV institution with less than a $50 billion balance of weighted short-term wholesale funding, M&T is not subject to the LCR.',reviewedOn:'2026-11-01',reviewExpires:'2026-12-27',sourceUrl:r.sourceUrl,sourceSection:'Liquidity, page 70'};
assert.equal(verifiedLiquidityExemption(e,p,now)?.state,'not_applicable');
for(const patch of [{reason:'other'},{quote:'short'},{state:'available'},{period:'2026-03-31'},{reviewExpires:'2026-10-31'},{sourceUrl:'https://example.com/x.htm'},{holdingName:'x'}])assert.equal(verifiedLiquidityExemption({...e,...patch},p,now),null);
assert.equal(verifiedLiquidity(e,p,now),null,'an exemption is never a ratio');
console.log('Holding liquidity identity, scope, date, units, arithmetic, ratio-only and exemption checks passed');
