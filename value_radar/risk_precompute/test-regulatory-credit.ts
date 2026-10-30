import assert from 'node:assert/strict';
import {verifiedCreditQuality as verify} from './regulatory-credit';
const now=Date.parse('2026-10-30T12:00:00Z'),parent={period:'2026-06-30',rssdId:'1',sourceFileSha256:'a'.repeat(64)};
const c={...parent,state:'available',method:'bhcf-loan-quality-v1',sourceImportedAt:'2026-10-29T10:00:00Z',unit:'fraction',amountUnit:'USD_thousands',totalLoans:1000,components:{nonaccrual:10,past_due_30_89:5,past_due_90:2,held_for_investment:900,held_for_sale:100},ratios:{nonaccrual:.01,past_due_30_89:.005,past_due_90:.002,nonaccrual_or_90_past_due:.012},sourceFields:{nonaccrual:'BHCK1403',past_due_30_89:'BHCK1406',past_due_90:'BHCK1407',held_for_investment:'BHCKB528',held_for_sale:'BHCK5369'}};
assert.equal(verify(c,parent,now).state,'available');assert.equal(verify(c,parent,now).score,null);
for(const patch of [{period:'2026-09-30'},{rssdId:'2'},{sourceFileSha256:'b'.repeat(64)},{sourceImportedAt:'2027-01-01'},{unit:'percent'},{totalLoans:1001},{ratios:{...c.ratios,nonaccrual:1}},{components:{...c.components,nonaccrual:-1}},{components:{...c.components,nonaccrual:NaN}},{sourceFields:{...c.sourceFields,nonaccrual:'BHCP1403'}}])assert.equal(verify({...c,...patch},parent,now).state,'missing');
assert.equal(verify({...c,components:{...c.components,nonaccrual:0},ratios:{...c.ratios,nonaccrual:0,nonaccrual_or_90_past_due:.002}},parent,now).state,'available');
console.log('12 credit-quality acceptance and rejection checks passed');
