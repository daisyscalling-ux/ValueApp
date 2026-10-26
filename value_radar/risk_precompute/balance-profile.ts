type Row=Record<string,any>;
const finite=(v:any):v is number=>typeof v==='number'&&Number.isFinite(v);
const DAY=86400000;
const recent=(v:any,now:number,days:number)=>typeof v==='string'&&Number.isFinite(Date.parse(v))&&Date.parse(v)<=now&&now-Date.parse(v)<=days*DAY;
const banks=new Set(['major banks','regional banks','savings banks','banks - diversified','banks - regional']);
const insurers=new Set(['multi-line insurance','life/health insurance','property/casualty insurance','insurance - diversified','insurance - life','insurance - property & casualty','reinsurance','insurance - reinsurance']);
const specialist=new Set(['investment banks/brokers','capital markets','financial conglomerates','finance/rental/leasing','investment trusts','investment managers','asset management','asset management & custody banks']);
export function balanceProfile(row:Row,now:number){
 if(!row.industry||!recent(row.metadata_asof,now,90))return 'unclassified';
 const industry=String(row.industry).trim().toLowerCase();
 return banks.has(industry)?'bank':insurers.has(industry)?'insurer':specialist.has(industry)?'specialist_financial':'corporate';
}
export function assessBalance(row:Row,a:Row|undefined,retrievedAt:any,identityOK:boolean,now:number){
 const profile=balanceProfile(row,now),financial=['bank','insurer','specialist_financial'].includes(profile);
 const fields=a?.fields||{},required=financial?['total_assets','equity','net_income']:['total_assets','total_debt','cash','operating_cashflow','capex'];
 const fieldIssues=(k:string)=>{
  const source=a?.field_sources?.[k],issues:string[]=[];
  if(source?.end&&source.end!==a?.end)issues.push('period_mismatch');
  if(source?.currency&&source.currency!==a?.currency)issues.push('currency_mismatch');
  if(source?.published_at&&!recent(source.published_at,now,700))issues.push('publication_invalid');
  if(source?.retrieved_at&&!recent(source.retrieved_at,now,7))issues.push('field_retrieval_stale');
  if(!finite(fields[k]))issues.push('value_missing');
  return issues;
 };
 const consistent=!!a?.source&&required.every(k=>fieldIssues(k).every(x=>x==='value_missing'));
 const fresh=!!a?.source&&a?.period_type==='annual'&&recent(a?.end,now,550)&&recent(retrievedAt,now,7)&&(!a?.published_at||recent(a.published_at,now,700));
 const capex=finite(fields.capex)&&fields.capex<0&&(a?.field_sources?.capex?.source||a?.source)==='Yahoo annual statements'?-fields.capex:fields.capex;
 const reasons:string[]=[];
 if(!identityOK)reasons.push('listing_identity_unconfirmed');
 if(!fresh)reasons.push('annual_missing_or_stale');
 if(!consistent)reasons.push('annual_source_or_field_period_inconsistent');
 if(!a?.currency)reasons.push('annual_currency_missing');
 for(const k of required)if(!finite(fields[k]))reasons.push('missing_'+k);
 const validBase=identityOK&&fresh&&typeof a?.currency==='string'&&!!a.currency&&finite(fields.total_assets)&&fields.total_assets>0&&fieldIssues('total_assets').length===0;
 const invalid=finite(fields.total_assets)&&fields.total_assets<=0||!financial&&(finite(fields.total_debt)&&fields.total_debt<0||finite(fields.cash)&&fields.cash<0||finite(capex)&&capex<0);
 if(invalid)reasons.push('invalid_financial_values');
 let complete=validBase&&consistent&&!invalid&&required.every(k=>finite(fields[k]));
 const applicable=profile==='corporate';
 const metrics:Row={};
 const metric=(name:string,needed:string[],value:()=>number,valid=true)=>{
  const keys=['total_assets',...needed],fieldProblems=Object.fromEntries(keys.map(k=>[k,fieldIssues(k)]).filter(([,v])=>(v as string[]).length));
  const candidate=validBase&&valid&&Object.keys(fieldProblems).length===0?value():null;
  const available=finite(candidate);
  metrics[name]={state:available?'available':'missing',value:available?candidate:null,
    unavailableFields:fieldProblems,reason:!validBase?'annual_or_assets_unverified':!valid?'invalid_inputs':!available?'field_missing_inconsistent_or_nonfinite':null,
    basis:available?{period:a?.end,currency:a?.currency,retrievedAt,fields:Object.fromEntries(keys.map(k=>[k,{source:a?.field_sources?.[k]?.source||a?.source,end:a?.field_sources?.[k]?.end||a?.end,currency:a?.field_sources?.[k]?.currency||a?.currency,retrievedAt:a?.field_sources?.[k]?.retrieved_at||retrievedAt}]))}:null};
 };
 if(financial){
  metric('bookEquityAssets',['equity'],()=>fields.equity/fields.total_assets);
  metric('netIncomeEndingAssets',['net_income'],()=>fields.net_income/fields.total_assets);
  metrics.netDebtAssets={state:'not_applicable',value:null};
  metrics.fcfAssets={state:'not_applicable',value:null};
 }else if(applicable){
  metric('netDebtAssets',['total_debt','cash'],()=>(fields.total_debt-fields.cash)/fields.total_assets,fields.total_debt>=0&&fields.cash>=0);
  metric('fcfAssets',['operating_cashflow','capex'],()=>(fields.operating_cashflow-capex)/fields.total_assets,finite(capex)&&capex>=0&&(!a?.field_sources?.operating_cashflow?.start||!a?.field_sources?.capex?.start||a.field_sources.operating_cashflow.start===a.field_sources.capex.start));
 }
 complete=complete&&(!applicable||['netDebtAssets','fcfAssets'].every(k=>metrics[k]?.state==='available'))&&(!financial||['bookEquityAssets','netIncomeEndingAssets'].every(k=>metrics[k]?.state==='available'));
 const investmentManager=['investment managers','asset management','asset management & custody banks'].includes(String(row.industry||'').trim().toLowerCase());
 const needed=profile==='bank'?['regulatory_capital_CET1','liquidity_LCR_or_local_equivalent','asset_quality_nonperforming_loans']:profile==='insurer'?['eligible_own_funds','solvency_requirement','jurisdiction_and_regulatory_scope']:profile==='specialist_financial'?(investmentManager?['business_model_and_applicable_capital_framework','client_assets_or_assets_under_management','net_flows_and_fee_dependence']:['business_model_and_applicable_capital_framework']):profile==='unclassified'?['current_industry_classification']:[];
 const supplemental:Row={};
 if(applicable){
  for(const [name,key] of [['operatingCashflowAssets','operating_cashflow'],['cashAssets','cash'],['bookEquityAssets','equity'],['netIncomeEndingAssets','net_income']]){
   metric(name,[key],()=>fields[key]/fields.total_assets,key!=='cash'||fields.cash>=0);supplemental[name]=metrics[name];delete metrics[name];
  }
 }
 const expirations=[Date.parse(retrievedAt)+7*DAY,Date.parse(a?.end)+550*DAY,
  ...required.flatMap(k=>{const f=a?.field_sources?.[k];return [f?.retrieved_at?Date.parse(f.retrieved_at)+7*DAY:NaN,f?.published_at?Date.parse(f.published_at)+700*DAY:NaN]}),
  a?.published_at?Date.parse(a.published_at)+700*DAY:NaN].filter(Number.isFinite);
 const expires=expirations.length?Math.min(...expirations):null;
 const refreshDue=expires!==null&&now>=expires-2*DAY;
 const state=complete?(applicable?'available':'context_only'):Object.values(metrics).some((m:any)=>m.state==='available')?'partial':'missing';
 return {state,reason:reasons.join(',')||(applicable?'annual_book_ratios':'sector_specific_assessment_pending'),profile,
  retrievedAt:retrievedAt||null,expiresAt:expires===null?null:new Date(expires).toISOString(),refreshDue,refreshLeadDays:2,
  period:a?.end||null,currency:a?.currency||null,publicationDateConfirmed:!!a?.published_at&&recent(a.published_at,now,700),
  source:a?.source||null,sourceUrl:a?.source_url||null,
  anchors:validBase?{totalAssets:fields.total_assets,cash:fieldIssues('cash').length===0&&fields.cash>=0?fields.cash:null}:null,
  capexNormalization:capex!==fields.capex?'yahoo_cash_outflow_to_positive_spend':'unchanged',
  supplementalMetrics:supplemental,fieldQuality:Object.fromEntries(required.map(k=>[k,fieldIssues(k)])),
  ratios:applicable&&complete?{netDebtAssets:metrics.netDebtAssets.value,fcfAssets:metrics.fcfAssets.value}:null,metrics,
  sectorRequirements:needed,needsFinancialRefresh:!complete,
  interpretation:financial?'Book equity and income over ending assets are context only, not regulatory capital, solvency or a calibrated risk score.':profile==='unclassified'?'Industry classification must be verified before selecting ratios.':'Book ratios, no calibrated risk probability.'};
}

export function assessBalanceSnapshot(row:Row,snapshot:Row|undefined,identityOK:boolean,now:number,roic?:Row){
 let best=assessBalance(row,snapshot?.annual,snapshot?.annual_retrieved_at||snapshot?.retrieved_at,identityOK,now);
 if(!identityOK)return best;
 const previous=snapshot?.annual;
 const strength=(x:ReturnType<typeof assessBalance>)=>['available','context_only'].includes(x.state)?100:
   Object.values(x.metrics).filter((m:any)=>m.state==='available').length;
 const candidates=[
  {annual:snapshot?.risk_annual,at:snapshot?.retrieved_at,symbol:snapshot?.symbol,source:'Yahoo annual statements',selection:'provider_native_whole_statement'},
  {annual:roic?.annual,at:roic?.retrievedAt,symbol:row.listing_symbol,source:'ROIC v3 annual statements',selection:'roic_native_whole_statement'}
 ];
 for(const entry of candidates){
  const candidate=entry.annual;
  if(!candidate||candidate.symbol!==entry.symbol||candidate.purpose!=='standalone_balance_risk_context'||candidate.source!==entry.source)continue;
  // Independent whole statements only: never transfer fields, dates or EPS.
  // Retain the existing same-period safeguard (52/53-week rounding <=7 days).
  if(previous&&(previous.currency!==candidate.currency||!Number.isFinite(Date.parse(previous.end))
     ||Math.abs(Date.parse(previous.end)-Date.parse(candidate.end))>7*DAY))continue;
  if(entry.source==='ROIC v3 annual statements'&&Object.entries(candidate.fields||{}).some(([k,v])=>finite(v)&&
     (candidate.field_sources?.[k]?.source!==entry.source||candidate.field_sources[k].end!==candidate.end||candidate.field_sources[k].currency!==candidate.currency)))continue;
  const alternative=assessBalance(row,candidate,entry.at,identityOK,now);
  if(strength(alternative)<=strength(best))continue;
  best={...alternative,sourceSelection:entry.selection,
    valuationPeriod:previous?.end||null,valuationSource:previous?.source||null,
    interpretation:alternative.interpretation+' Separate provider-native statement; valuation source unchanged. No cross-source field merge.'+
      (entry.source==='ROIC v3 annual statements'?' Provider-defined debt maturities; lease scope not separately reconciled.':'')} as typeof best;
 }
 return best;
}
