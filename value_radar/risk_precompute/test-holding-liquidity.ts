import assert from 'node:assert/strict';
import {verifiedLiquidity} from './holding-liquidity';
const now=Date.parse('2026-11-01T12:00:00Z'),p={rssdId:'1951350',holdingName:'CITIGROUP INC.',period:'2026-06-30'};
const r={...p,state:'available',method:'reviewed-holding-lcr-v1',scope:'listed_consolidated_holding',averaging:'quarter_average',unit:'fraction',currency:'USD',hqla:641200000000,netOutflows:567500000000,reportedRatio:1.13,ratioRoundingTolerance:.005,reviewedOn:'2026-11-01',reviewExpires:'2026-12-27',sourceUrl:'https://www.sec.gov/Archives/edgar/data/831001/000083100126000045/c-20260630.htm'};
assert.equal(verifiedLiquidity(r,p,now)?.reportedRatio,1.13);
for(const patch of [{rssdId:'other'},{holdingName:'subsidiary'},{period:'2026-03-31'},{unit:'percent'},{reportedRatio:113},{hqla:NaN},{netOutflows:0},{scope:'bank_subsidiary'},{averaging:'end_of_period'},{reviewedOn:'2026-11-02'},{reviewExpires:'2026-10-31'},{ratioRoundingTolerance:.1},{sourceUrl:'javascript:alert(1)'}])assert.equal(verifiedLiquidity({...r,...patch},p,now),null);
console.log('Holding liquidity identity, scope, date, units and arithmetic checks passed');
