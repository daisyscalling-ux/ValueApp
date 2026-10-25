import assert from 'node:assert/strict';
import {withEdinetCashflow} from './edinet-context';
const now=Date.parse('2026-10-24T12:00:00Z');let count=0;
const test=(name:string,fn:()=>void)=>{fn();count++;console.log('OK '+name)};
const row={listing_symbol:'TSE:7974',ticker:'7974.T',isin:'JP3756600007',currency:'JPY'};
const base=()=>({profile:'corporate',state:'partial',reason:'missing_operating_cashflow,missing_capex',period:'2026-03-31',currency:'JPY',source:'Yahoo annual statements',anchors:{totalAssets:100000000,cash:20000000},metrics:{netDebtAssets:{state:'available',value:.1},fcfAssets:{state:'missing',value:null}},interpretation:'Book ratios',ratios:null,needsFinancialRefresh:true});
const archive=()=>({schema:1,stocks:{[row.listing_symbol]:{inputIdentity:{...row,security_type:null,share_class:null},retrievedAt:'2026-10-24T11:00:00Z',filing:{docID:'S100TEST',periodStart:'2025-04-01',periodEnd:'2026-03-31',secCode:'79740',withdrawalStatus:'0',disclosureStatus:'0',docInfoEditStatus:'0'},annual:{symbol:row.listing_symbol,purpose:'standalone_cashflow_risk_context',docID:'S100TEST',period_type:'annual',state:'available',start:'2025-04-01',end:'2026-03-31',published_at:'2026-06-20T01:00:00Z',source:'EDINET annual XBRL',currency:'JPY',fields:{total_assets:100000000,cash:20000000,operating_cashflow:10000000,capex:4000000},field_sources:Object.fromEntries(['total_assets','cash','operating_cashflow','capex'].map(k=>[k,{source:'EDINET annual XBRL',end:'2026-03-31',currency:'JPY',docID:'S100TEST'}]))}}}});
test('same-period independent cashflow ratio closes the gap with source evidence',()=>{
 const b=base(),before=JSON.stringify(b),a=withEdinetCashflow(b,row,archive(),true,now);
 assert.equal(a.state,'available');assert.equal(a.ratios.fcfAssets,.06);assert.equal(a.ratios.netDebtAssets,.1);
 assert.equal(a.metricSources.fcfAssets.docID,'S100TEST');assert.equal(JSON.stringify(b),before);
});
test('date currency or anchor mismatch never creates mixed ratios',()=>{
 for(const change of [{period:'2025-03-31'},{currency:'USD'},{anchors:{totalAssets:999000000,cash:20000000}},{anchors:{totalAssets:100000000,cash:1}}]){
  const a=withEdinetCashflow({...base(),...change},row,archive(),true,now);assert.equal(a.state,'partial');assert.equal(a.edinetCashflow.alignedWithBalance,false);
 }
});
test('stale future withdrawn wrong-issuer and incomplete observations rejected',()=>{
 const mutations=[(r:any)=>r.retrievedAt='2026-10-01',(r:any)=>r.retrievedAt='2027-01-01',
  (r:any)=>r.inputIdentity.isin='other',(r:any)=>r.filing.withdrawalStatus='1',(r:any)=>r.annual.fields.capex=null,
  (r:any)=>r.annual.end='2027-01-01',(r:any)=>r.annual.field_sources.capex.currency='USD',
  (r:any)=>r.filing.secCode='99990',(r:any)=>r.annual.docID='S100WRNG'];
 for(const mutate of mutations){const a=archive();mutate(a.stocks[row.listing_symbol]);assert.deepEqual(withEdinetCashflow(base(),row,a,true,now),base());}
});
test('existing cashflow and bank observations are never replaced',()=>{
 const b=base();b.metrics.fcfAssets={state:'available',value:.02};
 assert.equal(withEdinetCashflow(b,row,archive(),true,now).metrics.fcfAssets.value,.02);
 const bank={...base(),profile:'bank'};assert.deepEqual(withEdinetCashflow(bank,row,archive(),true,now),bank);
 assert.deepEqual(withEdinetCashflow(base(),row,archive(),false,now),base());
});
test('unavailable debt stays unavailable despite complete cashflow',()=>{
 const b:any=base();b.reason='missing_total_debt,missing_capex';b.metrics.netDebtAssets={state:'missing',value:null};
 const result=withEdinetCashflow(b,row,archive(),true,now);assert.equal(result.state,'partial');assert.equal(result.reason,'missing_total_debt');
});
console.log(count+' EDINET integration checks passed');
