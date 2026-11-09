import {verifiedLiquidity} from './holding-liquidity';
import {verifiedCapitalRequirement} from './capital-requirement';
import {verifiedCreditQuality} from './regulatory-credit';
import {withInsurerSolvency} from './insurer-solvency';
type Row=Record<string,any>;
const DAY=86400000;
const dateOnly=(v:any)=>typeof v==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(v)&&Number.isFinite(Date.parse(v))&&new Date(v).toISOString().slice(0,10)===v;
const fresh=(v:any,now:number,days:number)=>typeof v==='string'&&Number.isFinite(Date.parse(v))&&Date.parse(v)<=now&&now-Date.parse(v)<=days*DAY;
const keys=['listing_symbol','ticker','isin','currency','name','name_full','security_type','share_class'];
// EU/EWR-Banken (EBA-Transparenz, EZB-P2R): eigener Zweig mit eigenen Methoden-IDs, 730 Tage Hoechstalter (Nutzerentscheidung 09.11.2026).
const EU_CODES:Row={cet1_ratio:'EBA:2520140',tier1_ratio:'EBA:2520141',total_capital_ratio:'EBA:2520142',leverage_ratio:'EBA:2520905'};
export function verifiedEuCapital(archive:Row|undefined|null,row:Row,identityOK:boolean,now:number):Row|null{
 const eu=archive?.euBanks,r=eu?.stocks?.[row.listing_symbol],today=new Date(now).toISOString().slice(0,10);
 if(!identityOK||archive?.schema!==1||!fresh(archive.generatedAt,now,1.5)||eu?.schema!==1||eu.source!=='eba_transparency_ecb_p2r'||eu.state!=='ready'||r?.state!=='available'||r.scope!=='eu_prudential_group')return null;
 if(!keys.every(k=>(row[k]??null)===(r.inputIdentity?.[k]??null))||!dateOnly(r.period)||!fresh(r.period,now,730)||typeof r.sourceImportedAt!=='string'||Date.parse(r.sourceImportedAt)>now||Date.parse(r.sourceImportedAt)<Date.parse(r.period))return null;
 if(!dateOnly(r.identityReviewExpires)||r.identityReviewExpires<today||!/^[0-9a-f]{64}$/.test(r.sourceFileSha256||'')||!/^[A-Z0-9]{20}$/.test(r.lei||''))return null;
 const metrics=Object.fromEntries(Object.entries(r.metrics||{}).filter(([key,v]:any)=>EU_CODES[key]===v.sourceField&&v.state==='available'&&v.unit==='fraction'&&typeof v.value==='number'&&Number.isFinite(v.value)&&v.value>=0&&v.value<=1));
 const chain=['cet1_ratio','tier1_ratio','total_capital_ratio'].map(k=>(metrics[k] as any)?.value).filter(v=>v!==undefined);
 if(!metrics.cet1_ratio||!chain.every((v,i)=>!i||chain[i-1]<=v+1e-6))return null;
 const cet1=(metrics.cet1_ratio as any).value,q=r.capitalRequirement,c=r.creditQuality;
 const requirement=q?.state==='available'&&q.method==='ecb-p2r-partial-cet1-v1'&&q.unit==='fraction'&&typeof q.value==='number'&&q.value>0&&q.value<.3&&q.comparisonPeriod===r.period&&dateOnly(q.reviewExpires)&&q.reviewExpires>=today&&/^[0-9a-f]{64}$/.test(q.sourceSha256||'')
  ?{...q,headroomPercentagePoints:(cet1-q.value)*100}:null;
 const credit=c?.state==='available'&&c.method==='eba-npl-v1'&&c.unit==='fraction'&&c.period===r.period&&c.lei===r.lei&&typeof c.ratio==='number'&&Number.isFinite(c.ratio)&&c.ratio>=0&&c.ratio<=1&&/^[0-9a-f]{64}$/.test(c.sourceFileSha256||'')?c:null;
 return {...r,metrics,capitalRequirement:requirement,creditQuality:credit,liquidity:null};
}
// Banken ausserhalb EU/EWR/USA: veroeffentlichte Basel-Kennzahlen (APRA, spaeter KM1). Hoechstalter 270 Tage (Quartalsdaten).
export function verifiedIntlCapital(archive:Row|undefined|null,row:Row,identityOK:boolean,now:number):Row|null{
 const x=archive?.intlBanks,r=x?.stocks?.[row.listing_symbol],today=new Date(now).toISOString().slice(0,10);
 if(!identityOK||archive?.schema!==1||!fresh(archive.generatedAt,now,1.5)||x?.schema!==1||x.source!=='intl_basel_key_metrics'||x.state!=='ready'||r?.state!=='available'||r.scope!=='basel_key_metrics')return null;
 if(!keys.every(k=>(row[k]??null)===(r.inputIdentity?.[k]??null))||!dateOnly(r.period)||!fresh(r.period,now,270)||!dateOnly(r.identityReviewExpires)||r.identityReviewExpires<today||!/^[0-9a-f]{64}$/.test(r.sourceFileSha256||'')||typeof r.sourceType!=='string')return null;
 const metrics=Object.fromEntries(Object.entries(r.metrics||{}).filter(([key,v]:any)=>v.sourceField===r.sourceType+':'+key&&v.state==='available'&&v.unit==='fraction'&&typeof v.value==='number'&&Number.isFinite(v.value)&&v.value>=0&&v.value<=1));
 const chain=['cet1_ratio','tier1_ratio','total_capital_ratio'].map(k=>(metrics[k] as any)?.value).filter(v=>v!==undefined);
 if(!metrics.cet1_ratio||!chain.every((v,i)=>!i||chain[i-1]<=v+1e-6))return null;
 const l=r.liquidity,q=r.capitalRequirement,cet1=(metrics.cet1_ratio as any).value;
 const liquidity=l?.state==='available'&&l.method==='intl-lcr-v1'&&l.period===r.period&&typeof l.reportedRatio==='number'&&l.reportedRatio>0&&l.reportedRatio<10?l:null;
 const requirement=q?.state==='available'&&q.method==='basel-km1-cet1-requirement-v1'&&q.comparisonPeriod===r.period&&typeof q.value==='number'&&q.value>0&&q.value<.3&&dateOnly(q.reviewExpires)&&q.reviewExpires>=today?{...q,headroomPercentagePoints:(cet1-q.value)*100}:null;
 const c=r.creditQuality;
 const credit=c?.state==='available'&&c.method==='basel-cr1-default-v1'&&c.unit==='fraction'&&c.period===r.period&&typeof c.ratio==='number'&&Number.isFinite(c.ratio)&&c.ratio>=0&&c.ratio<=1?c:null;
 return {...r,metrics,liquidity,capitalRequirement:requirement,creditQuality:credit};
}
export function withRegulatoryContext(base:Row,row:Row,archive:Row|undefined|null,identityOK:boolean,now:number){
 if(!['bank','insurer','specialist_financial'].includes(base.profile))return base;
 if(base.profile==='insurer')return withInsurerSolvency(base,row,archive?.insurers,identityOK,now);
 let requirements=[...(base.sectorRequirements||[])];
 if(base.profile==='bank'&&!requirements.includes('institution_specific_capital_requirement'))requirements.push('institution_specific_capital_requirement');
 const r=archive?.stocks?.[row.listing_symbol];let capital:Row|null=null;
 if(identityOK&&base.profile!=='insurer'&&archive?.schema===1&&archive.source==='reviewed_FR_Y9C_holding_capital'&&fresh(archive.generatedAt,now,1.5)&&r?.state==='available'&&r.scope==='listed_consolidated_holding'
  &&keys.every(k=>(row[k]??null)===(r.inputIdentity?.[k]??null))&&fresh(r.period,now,180)&&typeof r.sourceImportedAt==='string'&&Date.parse(r.sourceImportedAt)<=now&&Date.parse(r.sourceImportedAt)>=Date.parse(r.period)
  &&dateOnly(r.period)&&dateOnly(r.identityReviewExpires)&&r.identityReviewExpires>=new Date(now).toISOString().slice(0,10)&&/^[0-9a-f]{64}$/.test(r.sourceFileSha256||'')){
  const m=r.metrics?.cet1_ratio;
  const metricCodes:Row={cet1_ratio:'BHCAP793',tier1_ratio:'BHCA7206',total_capital_ratio:'BHCA7205',tier1_leverage_ratio:'BHCA7204'};
  const metrics=Object.fromEntries(Object.entries(r.metrics||{}).filter(([key,v]:any)=>metricCodes[key]===v.sourceField&&v.state==='available'&&v.unit==='fraction'&&typeof v.value==='number'&&Number.isFinite(v.value)&&v.value>=0&&v.value<=1));
  const values=['cet1_ratio','tier1_ratio','total_capital_ratio'].map(k=>(metrics[k] as any)?.value).filter(v=>v!==undefined);
  const consistent=values.every((v,i)=>!i||values[i-1]<=v+1e-6);
  if(consistent&&m?.state==='available'&&m.unit==='fraction'&&m.sourceField==='BHCAP793'&&typeof m.value==='number'&&Number.isFinite(m.value)&&m.value>=0&&m.value<=1)capital={...r,metrics,liquidity:verifiedLiquidity(r.liquidity,r,now),creditQuality:verifiedCreditQuality(r.creditQuality,r,now),capitalRequirement:verifiedCapitalRequirement(r.capitalRequirement,{...r,metrics},now)};
 }
 if(!capital&&base.profile==='bank')capital=verifiedEuCapital(archive,row,identityOK,now);
 if(!capital&&base.profile==='bank')capital=verifiedIntlCapital(archive,row,identityOK,now);
 const fulfilled=capital&&base.profile==='bank'?['regulatory_capital_CET1']:[];
 // EU: Teilanforderung ohne systemische Puffer erfuellt die bankspezifische Anforderung nicht vollstaendig; NPL schliesst die Kreditqualitaet.
 if(['eu_prudential_group','basel_key_metrics'].includes(capital?.scope)&&capital.creditQuality)fulfilled.push('asset_quality_nonperforming_loans');
 if(capital?.capitalRequirement&&capital.scope!=='eu_prudential_group'&&base.profile==='bank')fulfilled.push('institution_specific_capital_requirement');
 if(capital?.liquidity&&base.profile==='bank')fulfilled.push('liquidity_LCR_or_local_equivalent');
 requirements=requirements.filter(k=>!fulfilled.includes(k));
 return {...base,sectorRequirements:requirements,bankCapital:capital,
  sectorAssessment:{state:'open',fulfilledRequirements:fulfilled,openRequirements:requirements,capitalContextAvailable:!!capital,scoreContribution:0,
   explanation:'Reported capital is distinct from the institution-specific requirement, liquidity and credit quality. No safety verdict or calibrated risk score.'}};
}
