type Row=Record<string,any>;
const finite=(x:any)=>typeof x==='number'&&Number.isFinite(x);
const recent=(x:any,now:number,days:number)=>typeof x==='string'&&Number.isFinite(Date.parse(x))&&Date.parse(x)<=now&&now-Date.parse(x)<=days*86400000;
const match=(a:any,b:any)=>finite(a)&&finite(b)&&Math.abs(a-b)<=Math.max(1,Math.abs(a)*.0001);
export function withEdinetCashflow(base:Row,row:Row,archive:Row|undefined|null,identityOK:boolean,now:number):Row{
 if(!identityOK||base.profile!=='corporate'||archive?.schema!==1||!/^((TSE|TYO|JPX):)[0-9A-Z]{4}$/.test(row.listing_symbol||''))return base;
 const record=archive.stocks?.[row.listing_symbol],a=record?.annual,doc=record?.filing;
 if(!record||!['listing_symbol','ticker','isin','currency','security_type','share_class'].every(k=>(record.inputIdentity?.[k]??null)===(row[k]??null)))return base;
 if(['expired','input_mismatch'].includes(row.listing_reference_status)||a?.symbol!==row.listing_symbol||a?.purpose!=='standalone_cashflow_risk_context'
    ||a?.source!=='EDINET annual XBRL'||a?.currency!=='JPY'||a?.period_type!=='annual'||a?.state!=='available'
    ||!recent(record.retrievedAt,now,7)||!recent(a.end,now,550)||!recent(a.published_at,now,550)
    ||a.docID!==doc?.docID||doc?.periodEnd!==a.end||doc?.periodStart!==a.start
    ||doc?.withdrawalStatus!=='0'||doc?.disclosureStatus!=='0'||doc?.docInfoEditStatus!=='0'
    ||doc?.secCode!==row.listing_symbol.split(':')[1]+'0')return base;
 const f=a.fields||{};
 if(!['total_assets','cash','operating_cashflow','capex'].every(k=>finite(f[k])&&a.field_sources?.[k]?.source===a.source
    &&a.field_sources[k].end===a.end&&a.field_sources[k].currency==='JPY'&&a.field_sources[k].docID===a.docID)
    ||f.total_assets<=0||f.cash<0||f.capex<0)return base;
 const context={state:'available',value:(f.operating_cashflow-f.capex)/f.total_assets,period:a.end,currency:'JPY',source:a.source,sourceUrl:a.source_url,docID:a.docID,retrievedAt:record.retrievedAt,publicationDate:a.published_at};
 // Each ratio remains wholly sourced. Joining two independently calculated
 // observations requires same period/currency plus matching assets and cash.
 const aligned=base.period===a.end&&base.currency==='JPY'&&match(base.anchors?.totalAssets,f.total_assets)&&match(base.anchors?.cash,f.cash);
 const enriched={...base,edinetCashflow:{...context,alignedWithBalance:aligned}};
 if(!aligned||base.metrics?.fcfAssets?.state==='available')return enriched;
 const metrics={...base.metrics,fcfAssets:context};
 const reason=String(base.reason||'').split(',').filter(x=>!['missing_operating_cashflow','missing_capex'].includes(x)).join(',');
 const complete=metrics.netDebtAssets?.state==='available'&&!reason;
 return {...enriched,metrics,state:complete?'available':'partial',reason:reason||'independently_sourced_aligned_ratios',
  ratios:complete?{netDebtAssets:metrics.netDebtAssets.value,fcfAssets:context.value}:base.ratios,
  needsFinancialRefresh:!complete,sourceSelection:'independent_aligned_cashflow_observation',
  metricSources:{netDebtAssets:{source:base.source,period:base.period},fcfAssets:context},
  interpretation:base.interpretation+' Cash-flow ratio independently calculated from an EDINET consolidated annual filing; same period, currency, assets and cash verified. Valuation unchanged.'};
}
