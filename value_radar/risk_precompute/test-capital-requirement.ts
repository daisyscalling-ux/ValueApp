import assert from 'node:assert/strict';import {verifiedCapitalRequirement as check} from './capital-requirement';
const now=Date.parse('2026-10-30T12:00:00Z');
const cap={rssdId:'1',holdingName:'Example',period:'2026-06-30',metrics:{cet1_ratio:{value:.1}}};
const r={...cap,state:'available',method:'fed-cet1-requirement-v1',unit:'fraction',comparisonPeriod:cap.period,publicationDate:'2026-06-24',applicableFrom:'2026-06-24',reviewExpires:'2026-12-31',sourceVerifiedAt:'2026-10-30T10:00:00Z',sourceUrl:'https://www.federalreserve.gov/publications/files/large-bank-capital-requirements-20260624.pdf',sourceSha256:'7a628b4395bca88cbd21f0600424fe41bc353058c7b3b6e386edb43ec8d17290',minimumBps:450,stressBufferBps:250,gsibBps:0,totalBps:700,value:.07};
assert.ok(Math.abs(check(r,cap,now)!.headroomPercentagePoints-3)<1e-10);
for(const patch of [{rssdId:'2'},{holdingName:'Other'},{comparisonPeriod:'2026-03-31'},{reviewExpires:'2026-02-30'},{sourceVerifiedAt:'2026-10-01'},{sourceVerifiedAt:'2027-01-01'},{sourceSha256:'bad'},{unit:'percent'},{totalBps:710},{value:7},{minimumBps:true},{applicableFrom:'2026-07-01'}])assert.equal(check({...r,...patch},cap,now),null);
assert.equal(check(r,cap,Date.parse('2027-01-01')),null);
assert.ok(check(r,{...cap,metrics:{cet1_ratio:{value:.05}}},now)!.headroomPercentagePoints<0);
console.log('15 capital-requirement checks passed');
