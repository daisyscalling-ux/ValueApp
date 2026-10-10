import assert from 'node:assert/strict';
import {validateHistory,rankCorrelation} from './src/lib/risk-validation';
const now=Date.parse('2026-10-10T12:00:00Z'),bars:{date:string;close:number}[]=[];
for(let day=Date.parse('2021-10-12');day<Date.parse('2026-10-10');day+=86400000){const d=new Date(day);if(d.getUTCDay()%6)bars.push({date:d.toISOString().slice(0,10),close:100+Math.sin(bars.length/30)*10})}
const h={adjustment:'total_return',bars},out=validateHistory(h,now);assert.ok(out.length>10);const first=out[0];const changed=validateHistory({...h,bars:bars.map(b=>b.date>first.entry?{...b,close:b.close*.3}:b)},now).filter(o=>o.date===first.date);
for(const o of changed)assert.equal(o.score,out.find(x=>x.date===o.date&&x.horizon===o.horizon)!.score);
assert.ok(changed[0].loss>first.loss);assert.ok(out.every(o=>o.date<o.entry&&o.end<'2026-10-10'&&!(o.date<'2025-01-01'&&o.end>='2025-01-01')));
assert.equal(validateHistory({...h,adjustment:'none'},now).length,0);assert.equal(rankCorrelation([1,1,1],[1,2,3]),null);
console.log('Historical validation: no future-score leakage; dates, purge and adjustment checks passed.');
