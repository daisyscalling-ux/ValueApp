import assert from 'node:assert/strict';
import {AdaptiveRoicRate} from './adaptive-roic-rate';
process.env.RISK_EXPORT_LIBRARY='1';
const {exportRisk}=await import('./export-risk');
import fs from 'node:fs';import os from 'node:os';import path from 'node:path';
for(const rpm of [0,19,241,NaN,Infinity])assert.throws(()=>new AdaptiveRoicRate(rpm));
const p=new AdaptiveRoicRate(240);assert.equal(p.delay(0),0);p.start(0);assert.equal(p.delay(100),150);
p.response(429,'90',100);assert.equal(p.blockedUntil,90100);assert.equal(p.delay(100),90000);assert.equal(p.spacing,375);
for(let i=0;i<20;i++)p.response(200,null,90100+i*1000);
assert.equal(p.spacing,375);p.response(200,null,150100);assert.equal(p.spacing,300);
p.response(500,null,150101);for(let i=0;i<19;i++)p.response(200,null,220000+i);
assert.equal(p.spacing,300);p.response(200,null,221000);assert.equal(p.spacing,250);
for(let i=0;i<500;i++)p.response(200,null,300000+i*1000);assert.equal(p.spacing,250);
const q=new AdaptiveRoicRate(240);
for(let i=0;i<11;i++)q.response(429,null,i*1000);assert.equal(q.spacing,3000);
q.response(429,'Wed, 01 Jan 2031 00:00:00 GMT',0);assert.equal(q.blockedUntil,Date.parse('2031-01-01T00:00:00Z'));
// Sustained recovery under a fake clock; minimum pacing remains enforced.
const a=new AdaptiveRoicRate(240);let t=0;
for(let i=0;i<11;i++)a.response(429,null,t);
t=a.blockedUntil;
for(let i=0;i<3000;i++){t+=a.delay(t);a.start(t);a.response(200,null,t)}
assert.equal(a.spacing,250);assert.ok(a.recoveries>0);
const temp=fs.mkdtempSync(path.join(os.tmpdir(),'risk-paced-'));
try{
 const input=path.join(temp,'u.json');fs.writeFileSync(input,JSON.stringify({kandidaten:[{listing_symbol:'NYSE:X'}]}));
 let tick=Date.parse('2026-11-06T00:00:00Z');const calls:number[]=[];
 const result=await exportRisk({env:{ROIC_API_KEY:'fixture',RISK_UNIVERSE_PATH:input,RISK_OUTPUT_PATH:path.join(temp,'out.json'),RISK_YAHOO_PATH:path.join(temp,'none'),RISK_QUEUE_PATH:path.join(temp,'none'),RISK_REQUESTS_PER_MINUTE:'240',RISK_BUDGET_MIN:'5'},clock:()=>tick,sleep:async(ms:number)=>{tick+=ms},fetcher:async()=>{calls.push(tick);return calls.length===1?new Response('',{status:429,headers:{'retry-after':'90'}}):new Response('',{status:401})}});
 assert.equal(calls.length,2);assert.ok(calls[1]-calls[0]>=90000);assert.equal(result.report.rateLimitEvents,1);assert.equal(result.ok,false);
 assert.equal(result.report.pacing.configuredRequestsPerMinute,240);
 let longCalls=0;
 const exhausted=await exportRisk({env:{ROIC_API_KEY:'fixture',RISK_UNIVERSE_PATH:input,RISK_OUTPUT_PATH:path.join(temp,'long.json'),RISK_YAHOO_PATH:path.join(temp,'none'),RISK_QUEUE_PATH:path.join(temp,'none'),RISK_BUDGET_MIN:'1'},clock:()=>tick,sleep:async()=>{throw Error('Must not sleep beyond budget')},fetcher:async()=>{longCalls++;return new Response('',{status:429,headers:{'retry-after':'3600'}})}});
 assert.equal(longCalls,1);assert.equal(exhausted.report.budgetReached,true);
}finally{fs.rmSync(temp,{recursive:true,force:true})}
console.log('Adaptive pacing, bounded recovery and real exporter Retry-After checks passed');
