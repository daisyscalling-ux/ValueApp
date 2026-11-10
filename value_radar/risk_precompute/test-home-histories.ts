import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
process.env.RISK_EXPORT_LIBRARY='1';
const {chooseHome,targets,exportHomeHistories}=await import('./export-home-histories');
const now=Date.parse('2026-11-10T12:00:00Z');let checks=0;
const test=async(name:string,fn:()=>any)=>{await fn();checks++;console.log('OK '+name)};
const ok=(sym:string,obs=600)=>({format:'risk-summary',schema:1,symbol:sym,currency:'USD',adjustment:'total_return',retrievedAt:new Date(now-3600000).toISOString(),statistics:{observations:obs,first:'2024-01-02',last:'2026-11-07',error:'',es:.03,dd:.3,worst:.1,vol:.2,drawdown:.05}});
const uni={kandidaten:[{listing_symbol:'OTC:CBAUF',isin:'AU000000CBA7',name:'Commonwealth Bank of Australia'},{listing_symbol:'OTC:CMWAY',isin:'AU000000CBA7',name:'Commonwealth Bank of Australia'},
 {listing_symbol:'OTC:ALIZF',isin:'DE0008404005',name:'Allianz'},{listing_symbol:'XETR:ALV',isin:'DE0008404005',name:'Allianz'},{listing_symbol:'NASDAQ:OK',isin:'US0378331005',name:'Ok'}]};
const risk={schema:1,stocks:{'XETR:ALV':ok('XETR:ALV'),'NASDAQ:OK':ok('NASDAQ:OK')}};
await test('targets skip own and in-universe home histories, group by ISIN',()=>{
 const t=targets(uni,risk,now);assert.equal(t.length,1);assert.equal(t[0].isin,'AU000000CBA7');assert.deepEqual(t[0].listings,['OTC:CBAUF','OTC:CMWAY']);
});
await test('choose exactly one exchange listing with the same ISIN',()=>{
 const c=[{symbol:'ASX:CBA',isin:'AU000000CBA7',type:'stock',is_primary:true},{symbol:'OTC:CBAUF',isin:'AU000000CBA7',type:'stock'},{symbol:'ASX:CBAPM',isin:'AU0000CBAPM1',type:'stock'}];
 assert.equal(chooseHome('AU000000CBA7',c,new Set())?.symbol,'ASX:CBA');
 assert.equal(chooseHome('AU000000CBA7',[{symbol:'ASX:CBA',isin:'AU000000CBA7',type:'stock'},{symbol:'CHIA:CBA',isin:'AU000000CBA7',type:'stock'}],new Set()),null,'no primary listing');
 assert.equal(chooseHome('DE0006062144',[{symbol:'XETR:1COV',isin:'DE0006062144',type:'stock',is_primary:true},{symbol:'FRA:1COV',isin:'DE0006062144',type:'stock'}],new Set(['XETR:1COV'])),null,'never a regional line when the primary is in the universe');
 assert.equal(chooseHome('AU000000CBA7',[{symbol:'ASX:CBA',isin:'AU000000CBA7',type:'dr',is_primary:true}],new Set()),null);
 assert.equal(chooseHome('AU000000CBA7',[{symbol:'ASX:CBA',isin:'AU000000CBA7',type:'stock',is_primary:true},{symbol:'ASX:CBA',isin:'AU000000CBA7',type:'stock',is_primary:true}],new Set())?.symbol,'ASX:CBA');
 assert.equal(chooseHome('AU000000CBA7',[{symbol:'ASX:CBA',isin:'AU000000CBA7',type:'stock',status:'delisted',is_primary:true}],new Set()),null);
 assert.equal(chooseHome('AU000000CBA7',[{symbol:'ASX:CBA',isin:'AU000000CBA7',type:'stock',is_primary:true}],new Set(['ASX:CBA'])),null,'universe listings are handled by the proxy itself');
});
await test('export resolves, fetches and stores the home history',async()=>{
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'home-'));const u=path.join(dir,'u.json'),r=path.join(dir,'r.json');
 fs.writeFileSync(u,JSON.stringify(uni));fs.writeFileSync(r,JSON.stringify(risk));
 const bars=Array.from({length:1000},(_,i)=>({date:new Date(now-(i+3)*86400000).toISOString().slice(0,10),close:100+Math.sin(i/7)*3})).filter(b=>![0,6].includes(new Date(b.date).getUTCDay()));
 const calls:string[]=[];
 const fetcher:any=async(url:string)=>{calls.push(url);const j=(v:any)=>new Response(JSON.stringify(v),{status:200});
  if(url.includes('tickers/search'))return j(url.includes('AU000000CBA7')?[{symbol:'ASX:CBA',isin:'AU000000CBA7',type:'stock',is_primary:true,exchange:'ASX'}]:[]);
  if(url.includes('/stock-prices/ASX%3ACBA'))return j({symbol:'ASX:CBA',currency:'AUD',data:bars});
  return new Response('',{status:404});};
 const rep=await exportHomeHistories({env:{ROIC_API_KEY:'x',RISK_UNIVERSE_PATH:u,RISK_OUTPUT_PATH:r},fetcher,clock:()=>now,sleep:async()=>{}});
 assert.equal(rep.updated,1);const out=JSON.parse(fs.readFileSync(r,'utf8'));const h=out.homeListings['ASX:CBA'];
 assert.equal(h.isin,'AU000000CBA7');assert.equal(h.currency,'AUD');assert.deepEqual(h.homeOf,['OTC:CBAUF','OTC:CMWAY']);assert(h.statistics.observations>=505);
 assert.equal(out.homeResolution['AU000000CBA7'].symbol,'ASX:CBA');assert.equal(calls.filter(c=>c.includes('search')).length,1);
 const again=await exportHomeHistories({env:{ROIC_API_KEY:'x',RISK_UNIVERSE_PATH:u,RISK_OUTPUT_PATH:r},fetcher,clock:()=>now,sleep:async()=>{}});
 assert.equal(again.cachedResolution,1);assert.equal(again.fresh,1);
});
console.log(checks+' checks passed');
