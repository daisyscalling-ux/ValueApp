import {verifiedLiquidity,verifiedLiquidityExemption} from './holding-liquidity';
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
// Banken ohne EBA-Transparenzdaten: Quoten ausschliesslich aus EU KM1 (EBA Pillar 3 Data Hub), nur mit Originaldatei aus dem Hub.
const P3_CODES:Row={cet1_ratio:'P3DH:K_61.00/0050',tier1_ratio:'P3DH:K_61.00/0060',total_capital_ratio:'P3DH:K_61.00/0070',leverage_ratio:'P3DH:K_61.00/0220'};
export function verifiedEuCapital(archive:Row|undefined|null,row:Row,identityOK:boolean,now:number):Row|null{
 const eu=archive?.euBanks,r=eu?.stocks?.[row.listing_symbol],today=new Date(now).toISOString().slice(0,10);
 if(!identityOK||archive?.schema!==1||!fresh(archive.generatedAt,now,1.5)||eu?.schema!==1||eu.source!=='eba_transparency_ecb_p2r'||eu.state!=='ready'||r?.state!=='available'||r.scope!=='eu_prudential_group')return null;
 if(!keys.every(k=>(row[k]??null)===(r.inputIdentity?.[k]??null))||!dateOnly(r.period)||!fresh(r.period,now,730)||typeof r.sourceImportedAt!=='string'||Date.parse(r.sourceImportedAt)>now||Date.parse(r.sourceImportedAt)<Date.parse(r.period))return null;
 if(!dateOnly(r.identityReviewExpires)||r.identityReviewExpires<today||!/^[0-9a-f]{64}$/.test(r.sourceFileSha256||'')||!/^[A-Z0-9]{20}$/.test(r.lei||''))return null;
 const p3only=r.capitalSource==='eba_p3dh_km1';if(p3only&&!(typeof r.sourceUrl==='string'&&r.sourceUrl.startsWith('https://errp.eba.europa.eu/public-documents/')&&fresh(r.period,now,270)))return null;
 const codes=p3only?P3_CODES:EU_CODES;
 const metrics=Object.fromEntries(Object.entries(r.metrics||{}).filter(([key,v]:any)=>codes[key]===v.sourceField&&v.state==='available'&&v.unit==='fraction'&&typeof v.value==='number'&&Number.isFinite(v.value)&&v.value>=0&&v.value<=1));
 const chain=['cet1_ratio','tier1_ratio','total_capital_ratio'].map(k=>(metrics[k] as any)?.value).filter(v=>v!==undefined);
 if(!metrics.cet1_ratio||!chain.every((v,i)=>!i||chain[i-1]<=v+1e-6))return null;
 const cet1=(metrics.cet1_ratio as any).value,q=r.capitalRequirement,c=r.creditQuality;
 const p3dh=(x:any)=>typeof x?.sourceUrl==='string'&&x.sourceUrl.startsWith('https://errp.eba.europa.eu/public-documents/')&&/^[0-9a-f]{64}$/.test(x.sourceFileSha256||'');
 // Vollstaendige CET1-Anforderung aus EU KM1 (EBA Pillar 3 Data Hub): eigener Stichtag, hoechstens 270 Tage; Puffer mit der CET1-Quote desselben Stichtags.
 const full=q?.state==='available'&&q.method==='eba-p3dh-km1-cet1-requirement-v1'&&q.unit==='fraction'&&typeof q.value==='number'&&q.value>0&&q.value<.3&&typeof q.cet1Ratio==='number'&&q.cet1Ratio>0&&q.cet1Ratio<1
  &&dateOnly(q.comparisonPeriod)&&fresh(q.comparisonPeriod,now,270)&&dateOnly(q.reviewExpires)&&q.reviewExpires>=today&&p3dh(q);
 const requirement=full?{...q,headroomPercentagePoints:(q.cet1Ratio-q.value)*100}
  :q?.state==='available'&&q.method==='ecb-p2r-partial-cet1-v1'&&q.unit==='fraction'&&typeof q.value==='number'&&q.value>0&&q.value<.3&&q.comparisonPeriod===r.period&&dateOnly(q.reviewExpires)&&q.reviewExpires>=today&&/^[0-9a-f]{64}$/.test(q.sourceSha256||'')
  ?{...q,headroomPercentagePoints:(cet1-q.value)*100}:null;
 const l=r.liquidity;
 const liquidity=l?.state==='available'&&l.method==='eba-p3dh-km1-lcr-v1'&&l.unit==='fraction'&&typeof l.reportedRatio==='number'&&l.reportedRatio>0&&l.reportedRatio<10&&dateOnly(l.period)&&fresh(l.period,now,270)&&p3dh(l)?l:null;
 // NPL aus EU CR1 (Pillar 3 Data Hub, FINDIS): eigener Stichtag <= 270 Tage, Hub-Quelle; sonst EBA-Transparenz-NPL desselben Stichtags.
 const cr1=c?.state==='available'&&c.method==='eba-p3dh-cr1-npl-v1'&&c.unit==='fraction'&&c.lei===r.lei&&typeof c.ratio==='number'&&Number.isFinite(c.ratio)&&c.ratio>=0&&c.ratio<=1&&dateOnly(c.period)&&fresh(c.period,now,270)&&p3dh(c)&&c.sourceUrl.includes('/public-documents/FINDIS/');
 const credit=cr1||c?.state==='available'&&c.method==='eba-npl-v1'&&c.unit==='fraction'&&c.period===r.period&&c.lei===r.lei&&typeof c.ratio==='number'&&Number.isFinite(c.ratio)&&c.ratio>=0&&c.ratio<=1&&/^[0-9a-f]{64}$/.test(c.sourceFileSha256||'')?c:null;
 return {...r,metrics,capitalRequirement:requirement,creditQuality:credit,liquidity};
}
// CR1 mit eigenem Stichtag (Japan: CR1 nur im Jahres-/Halbjahresbericht): <= 270 Tage, nicht nach dem KM1-Stichtag, eigene Quelle mit SHA-256.
function separateCr1(c:Row,r:Row,now:number){
 return c.periodBasis==='separate_cr1'&&dateOnly(c.period)&&c.period<=r.period&&fresh(c.period,now,270)&&c.sourceType==='basel_pillar3_cr1'&&/^[0-9a-f]{64}$/.test(c.sourceFileSha256||'')&&typeof c.sourceUrl==='string'&&c.sourceUrl.startsWith('https://')&&typeof c.sourceDetail==='string'&&c.sourceDetail.trim()!=='';
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
 const credit=c?.state==='available'&&c.method==='basel-cr1-default-v1'&&c.unit==='fraction'&&typeof c.ratio==='number'&&Number.isFinite(c.ratio)&&c.ratio>=0&&c.ratio<=1&&(c.period===r.period||separateCr1(c,r,now))?c:null;
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
  if(consistent&&m?.state==='available'&&m.unit==='fraction'&&m.sourceField==='BHCAP793'&&typeof m.value==='number'&&Number.isFinite(m.value)&&m.value>=0&&m.value<=1)capital={...r,metrics,liquidity:verifiedLiquidity(r.liquidity,r,now),liquidityExemption:verifiedLiquidity(r.liquidity,r,now)?null:verifiedLiquidityExemption(r.liquidityExemption,r,now),creditQuality:verifiedCreditQuality(r.creditQuality,r,now),capitalRequirement:verifiedCapitalRequirement(r.capitalRequirement,{...r,metrics},now)};
 }
 if(!capital&&base.profile==='bank')capital=verifiedEuCapital(archive,row,identityOK,now);
 if(!capital&&base.profile==='bank')capital=verifiedIntlCapital(archive,row,identityOK,now);
 // Spezialfinanzierer mit geprueftem US-Holding-Kapital (FR Y-9C) sind Bankkonzerne und erfuellen dieselben Nachweise.
 const bankLike=base.profile==='bank'||base.profile==='specialist_financial'&&capital?.scope==='listed_consolidated_holding';
 const fulfilled=capital&&bankLike?['regulatory_capital_CET1']:[];
 // EU: Teilanforderung ohne systemische Puffer erfuellt die bankspezifische Anforderung nicht vollstaendig; NPL schliesst die Kreditqualitaet.
 if(['eu_prudential_group','basel_key_metrics'].includes(capital?.scope)&&capital.creditQuality)fulfilled.push('asset_quality_nonperforming_loans');
 // EU: nur die vollstaendige Anforderung aus KM1 erfuellt die bankspezifische Anforderung, nicht die Teilanforderung ohne Systempuffer.
 if(capital?.capitalRequirement&&(capital.scope!=='eu_prudential_group'||capital.capitalRequirement.method==='eba-p3dh-km1-cet1-requirement-v1')&&bankLike)fulfilled.push('institution_specific_capital_requirement');
 if(capital?.liquidity&&bankLike)fulfilled.push('liquidity_LCR_or_local_equivalent');
 requirements=requirements.filter(k=>!fulfilled.includes(k));
 return {...base,sectorRequirements:requirements,bankCapital:capital,
  sectorAssessment:{state:'open',fulfilledRequirements:fulfilled,openRequirements:requirements,capitalContextAvailable:!!capital,scoreContribution:0,
   explanation:'Reported capital is distinct from the institution-specific requirement, liquidity and credit quality. No safety verdict or calibrated risk score.'}};
}
