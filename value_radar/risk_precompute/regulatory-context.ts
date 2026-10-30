type Row=Record<string,any>;
const DAY=86400000;
const dateOnly=(v:any)=>typeof v==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(v)&&Number.isFinite(Date.parse(v))&&new Date(v).toISOString().slice(0,10)===v;
const fresh=(v:any,now:number,days:number)=>typeof v==='string'&&Number.isFinite(Date.parse(v))&&Date.parse(v)<=now&&now-Date.parse(v)<=days*DAY;
const keys=['listing_symbol','ticker','isin','currency','name','name_full','security_type','share_class'];
export function withRegulatoryContext(base:Row,row:Row,archive:Row|undefined|null,identityOK:boolean,now:number){
 if(!['bank','insurer','specialist_financial'].includes(base.profile))return base;
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
  if(consistent&&m?.state==='available'&&m.unit==='fraction'&&m.sourceField==='BHCAP793'&&typeof m.value==='number'&&Number.isFinite(m.value)&&m.value>=0&&m.value<=1)capital={...r,metrics};
 }
 const fulfilled=capital&&base.profile==='bank'?['regulatory_capital_CET1']:[];
 requirements=requirements.filter(k=>!fulfilled.includes(k));
 return {...base,sectorRequirements:requirements,bankCapital:capital,
  sectorAssessment:{state:'open',fulfilledRequirements:fulfilled,openRequirements:requirements,capitalContextAvailable:!!capital,scoreContribution:0,
   explanation:'Reported capital is distinct from the institution-specific requirement, liquidity and credit quality. No safety verdict or calibrated risk score.'}};
}
