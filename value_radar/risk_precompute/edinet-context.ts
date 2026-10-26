type Row=Record<string,any>;
const finite=(x:any)=>typeof x==='number'&&Number.isFinite(x);
const recent=(x:any,now:number,days:number)=>typeof x==='string'&&Number.isFinite(Date.parse(x))&&Date.parse(x)<=now&&now-Date.parse(x)<=days*86400000;
const match=(a:any,b:any)=>finite(a)&&finite(b)&&Math.abs(a-b)<=Math.max(1,Math.abs(a)*.0001);
export function withEdinetCashflow(base:Row,row:Row,archive:Row|undefined|null,identityOK:boolean,now:number):Row{
 if(!identityOK||base.profile!=='corporate'||archive?.schema!==1||!/^((TSE|TYO|JPX):)[0-9A-Z]{4}$/.test(row.listing_symbol||''))return base;
 const record=archive.stocks?.[row.listing_symbol],a=record?.annual,doc=record?.filing;
 if(!record||!['listing_symbol','ticker','isin','currency','security_type','share_class'].every(k=>(record.inputIdentity?.[k]??null)===(row[k]??null)))return base;
 if(['expired','input_mismatch'].includes(row.listing_reference_status)||a?.symbol!==row.listing_symbol||a?.purpose!=='standalone_cashflow_risk_context'
    ||a?.source!=='EDINET annual XBRL'||a?.currency!=='JPY'||a?.period_type!=='annual'||!['available','partial'].includes(a?.state)
    ||!recent(record.retrievedAt,now,7)||!recent(a.end,now,550)||!recent(a.published_at,now,550)
    ||a.docID!==doc?.docID||doc?.periodEnd!==a.end||doc?.periodStart!==a.start
    ||doc?.withdrawalStatus!=='0'||doc?.disclosureStatus!=='0'||doc?.docInfoEditStatus!=='0'
    ||doc?.secCode!==row.listing_symbol.split(':')[1]+'0')return base;
 const duration=(Date.parse(a.end)-Date.parse(a.start))/86400000;
 if(!Number.isFinite(duration)||duration<330||duration>380||Date.parse(a.published_at)<Date.parse(a.end))return base;
 const f=a.fields||{};
 const verified=(keys:string[])=>keys.every(k=>finite(f[k])&&a.field_sources?.[k]?.source===a.source
    &&a.field_sources[k].end===a.end&&a.field_sources[k].currency==='JPY'&&a.field_sources[k].docID===a.docID);
 if(!verified(['total_assets','cash'])||f.total_assets<=0||f.cash<0)return base;
 const context=(value:number,extra:Row={})=>({state:'available',value,period:a.end,currency:'JPY',source:a.source,sourceUrl:a.source_url,docID:a.docID,retrievedAt:record.retrievedAt,publicationDate:a.published_at,...extra});
 const observations:Row={};
 if(verified(['operating_cashflow'])&&finite(f.operating_cashflow/f.total_assets))observations.operatingCashflowAssets=context(f.operating_cashflow/f.total_assets);
 if(verified(['operating_cashflow','capex'])&&f.capex>=0&&finite((f.operating_cashflow-f.capex)/f.total_assets))observations.fcfAssets=context((f.operating_cashflow-f.capex)/f.total_assets);
 if(verified(['interest_bearing_debt'])&&f.interest_bearing_debt>=0&&a.debtScope&&finite((f.interest_bearing_debt-f.cash)/f.total_assets))observations.netDebtAssets=context((f.interest_bearing_debt-f.cash)/f.total_assets,{debtScope:a.debtScope});
 if(verified(['operating_cashflow','noncurrent_asset_purchases'])&&f.noncurrent_asset_purchases>=0&&finite((f.operating_cashflow-f.noncurrent_asset_purchases)/f.total_assets))
  observations.cashflowAfterNoncurrentPurchasesAssets=context((f.operating_cashflow-f.noncurrent_asset_purchases)/f.total_assets,{scope:'Operating cashflow minus reported noncurrent asset purchases; broader scope than PPE and intangibles. Not FCF, not a valuation input.',label:'Cashflow nach gemeldeten Kaeufen langfristiger Vermoegenswerte / Bilanzsumme'});
 if(!Object.keys(observations).length)return base;
 // A missing primary statement cannot be reconciled against real figures.
 // Select one independently verified filing, never borrow stale base values.
 if(base.state==='missing'&&!Object.values(base.metrics||{}).some((m:any)=>m.state==='available')&&(observations.fcfAssets||observations.netDebtAssets)){
  const metrics:Row={},missing:string[]=[];
  for(const key of ['fcfAssets','netDebtAssets'])metrics[key]=observations[key]||{state:'missing',value:null};
  if(!observations.netDebtAssets)missing.push('missing_total_debt');
  if(!observations.fcfAssets){if(!verified(['operating_cashflow']))missing.push('missing_operating_cashflow');if(!verified(['capex'])||f.capex<0)missing.push('missing_capex');if(!missing.includes('missing_capex')&&!missing.includes('missing_operating_cashflow'))missing.push('fcf_not_verified');}
  const complete=Object.values(metrics).every((m:any)=>m.state==='available');
  const expiry=Math.min(Date.parse(record.retrievedAt)+7*86400000,Date.parse(a.end)+550*86400000,Date.parse(a.published_at)+550*86400000);
  return {...base,state:complete?'available':'partial',reason:missing.join(',')||'edinet_standalone_annual_ratios',
   source:a.source,sourceUrl:a.source_url,sourceSelection:'edinet_standalone_original_filing',period:a.end,currency:'JPY',publicationDateConfirmed:true,
   retrievedAt:record.retrievedAt,expiresAt:new Date(expiry).toISOString(),refreshDue:now>=expiry-2*86400000,refreshLeadDays:2,
   anchors:{totalAssets:f.total_assets,cash:f.cash},metrics,metricSources:Object.fromEntries(Object.entries(metrics).filter(([,m]:any)=>m.state==='available')),
   ratios:complete?{fcfAssets:metrics.fcfAssets.value,netDebtAssets:metrics.netDebtAssets.value}:null,needsFinancialRefresh:!complete,
   fieldQuality:Object.fromEntries(['total_assets','cash','operating_cashflow','capex'].map(k=>[k,verified([k])?[]:['missing_or_unverified']]).concat([['total_debt',observations.netDebtAssets?[]:['missing_or_unverified']]])),
   supplementalMetrics:{operatingCashflowAssets:observations.operatingCashflowAssets||{state:'missing',value:null},cashAssets:finite(f.cash/f.total_assets)?context(f.cash/f.total_assets):{state:'missing',value:null}},
   capexNormalization:'EDINET_verified_reported_spend',edinetObservations:observations,
   edinetReconciliation:{state:'not_comparable',reasons:['previous_primary_statement_unavailable'],existingPeriod:base.period,edinetPeriod:a.end},
   ...(observations.fcfAssets?{edinetCashflow:{...observations.fcfAssets,alignedWithBalance:true}}:{}),
   previousUnavailableSource:{source:base.source,period:base.period,reason:base.reason},
   interpretation:'Independent EDINET annual filing selected because primary ratios were unavailable. No fields copied from the old statement; missing debt remains missing. Reported debt is not a lease reconciliation. Valuation unchanged.'};
 }
 const period=base.period===a.end,currency=base.currency==='JPY',assets=match(base.anchors?.totalAssets,f.total_assets),cash=match(base.anchors?.cash,f.cash);
 const aligned=period&&currency&&assets&&cash;
 const reasons=[...(!period?['period_mismatch']:[]),...(!currency?['currency_mismatch']:[]),...(!assets?['assets_mismatch']:[]),...(!cash?['cash_mismatch']:[])];
 const differences:Row={};
 for(const key of ['fcfAssets','netDebtAssets'])if(observations[key]&&base.metrics?.[key]?.state==='available')differences[key]={existing:base.metrics[key].value,edinet:observations[key].value,delta:observations[key].value-base.metrics[key].value};
 const enriched={...base,edinetObservations:observations,
  edinetReconciliation:{state:aligned?'aligned':'not_aligned',reasons,existingPeriod:base.period,edinetPeriod:a.end,existingAssets:base.anchors?.totalAssets??null,edinetAssets:f.total_assets,existingCash:base.anchors?.cash??null,edinetCash:f.cash,metricDifferences:differences},
  ...(observations.fcfAssets?{edinetCashflow:{...observations.fcfAssets,alignedWithBalance:aligned}}:{})};
 if(!aligned)return enriched;
 const metrics={...base.metrics},sources={...base.metricSources},filled:string[]=[];
 for(const key of ['fcfAssets','netDebtAssets'])if(observations[key]&&metrics[key]?.state!=='available'){
  metrics[key]=observations[key];sources[key]=observations[key];filled.push(key);
 }
 if(!filled.length)return enriched;
 const removed=filled.flatMap(k=>k==='fcfAssets'?['missing_operating_cashflow','missing_capex']:['missing_total_debt']);
 const reason=String(base.reason||'').split(',').filter(x=>!removed.includes(x)).join(',');
 const complete=['fcfAssets','netDebtAssets'].every(k=>metrics[k]?.state==='available')&&!reason;
 for(const k of ['fcfAssets','netDebtAssets'])if(!sources[k]&&metrics[k]?.state==='available')sources[k]={source:base.source,period:base.period};
 return {...enriched,metrics,state:complete?'available':'partial',reason:reason||'independently_sourced_aligned_ratios',
  ratios:complete?{netDebtAssets:metrics.netDebtAssets.value,fcfAssets:metrics.fcfAssets.value}:base.ratios,
  needsFinancialRefresh:!complete,sourceSelection:'independent_aligned_cashflow_observation',metricSources:sources,
  interpretation:base.interpretation+' Missing ratios independently calculated from an EDINET consolidated annual filing; same period, currency, assets and cash verified. Reported interest-bearing debt is not a lease reconciliation. Valuation unchanged.'};
}
