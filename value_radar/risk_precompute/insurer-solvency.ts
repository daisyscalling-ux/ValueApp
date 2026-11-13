type Row=Record<string,any>;
const DAY=86400000;
const keys=['listing_symbol','ticker','isin','currency','name','name_full','security_type','share_class'];
const date=(v:any)=>typeof v==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(v)&&Number.isFinite(Date.parse(v))&&new Date(v).toISOString().slice(0,10)===v;
const num=(v:any)=>typeof v==='number'&&Number.isFinite(v);
const url=(v:any)=>{try{return typeof v==='string'&&new URL(v).protocol==='https:'}catch{return false}};
export const insurerRequirements=['eligible_own_funds','solvency_requirement','jurisdiction_and_regulatory_scope'];
// Vergleichbare Gruppen-Solvenzsysteme: Eigenmittel / Solvenzkapitalanforderung, 100 % = Mindestanforderung. Spiegel von REGIMES in regulatory_insurer.py (ValueApp).
export const INSURER_REGIMES=['Solvency II|DE|BaFin','Solvency II|FR|ACPR','Solvency II|NL|DNB','Solvency II|FI|FIN-FSA','Solvency II|IT|IVASS','Solvency II|NO|Finanstilsynet','Solvency II|DK|Finanstilsynet','Solvency II|ES|DGSFP','Solvency II|BE|NBB','Solvency II|PL|KNF','Solvency UK|GB|PRA'];
const CURRENCIES=['EUR','GBP','NOK','PLN','DKK'];
export function verifiedInsurer(r:Row|undefined|null,now:number){
 const today=new Date(now).toISOString().slice(0,10);
 if(r?.state!=='available'||r.scope!=='insurance_group'||!INSURER_REGIMES.includes(r.framework+'|'+r.jurisdiction+'|'+r.regulator)||!url(r.scopeSourceUrl)||!r.scopeSourcePages||!date(r.reviewedOn)||!date(r.reviewExpires)||r.reviewedOn>today||r.reviewExpires<today)return null;
 const valid=(o:Row)=>{
  if(!o||!date(o.period)||o.period>r.reviewedOn||!['annual','interim'].includes(o.reportKind))return false;
  const age=now-Date.parse(o.period),limit=o.reportKind==='annual'?550:210;
  if(age<0||age>limit*DAY||!CURRENCIES.includes(o.currency)||o.unit!=='currency_units'||!url(o.sourceUrl)||!['basis','basisNote','sourcePages'].every(k=>typeof o[k]==='string'&&o[k].trim()))return false;
  if(!num(o.ratio)||o.ratio<0||o.ratio>20)return false;
  const complete=o.eligibleOwnFunds!=null||o.solvencyRequirement!=null;
  return !complete||(num(o.eligibleOwnFunds)&&o.eligibleOwnFunds>=0&&num(o.solvencyRequirement)&&o.solvencyRequirement>0&&Math.abs(o.eligibleOwnFunds/o.solvencyRequirement-o.ratio)<=.015);
 };
 const observations=(Array.isArray(r.observations)?r.observations:[]).filter(valid).map((o:Row)=>({...o,amountsVerified:o.eligibleOwnFunds!=null&&o.solvencyRequirement!=null}));
 // Neueste Periode; dort Quote mit belegten Betraegen vor reiner Quote. Gleichrangige Varianten sind mehrdeutig.
 const latest=observations.map((o:Row)=>o.period).sort().pop();
 const candidates=observations.filter((o:Row)=>o.period===latest),withAmounts=candidates.filter((o:Row)=>o.amountsVerified),best=withAmounts.length?withAmounts:candidates;
 if(best.length!==1)return null;
 // Re-select the primary from validated observations; never trust a cached primary or coverage flag.
 return {...r,primary:best[0],observations,scoreContribution:0,pointInTimeUsable:false};
}
export function withInsurerSolvency(base:Row,row:Row,archive:Row|undefined|null,identityOK:boolean,now:number){
 const r=archive?.stocks?.[row.listing_symbol];
 const age=now-Date.parse(archive?.generatedAt);
 const accepted=identityOK&&archive?.schema===1&&archive.source==='reviewed_insurer_original_reports'&&Number.isFinite(age)&&age>=0&&age<=1.5*DAY&&keys.every(k=>(row[k]??null)===(r?.inputIdentity?.[k]??null));
 const insurerSolvency=accepted?verifiedInsurer(r,now):null;
 // Reine Quote belegt Aufsichtsrahmen und Quote, aber nicht die Betraege von Eigenmitteln und Anforderung.
 const fulfilled=insurerSolvency?(insurerSolvency.primary.amountsVerified?[...insurerRequirements]:['jurisdiction_and_regulatory_scope']):[];
 const requirements=[...new Set([...(base.sectorRequirements||[]),...insurerRequirements])].filter(k=>!fulfilled.includes(k));
 return {...base,bankCapital:null,insurerSolvency,sectorRequirements:requirements,sectorAssessment:{state:'open',fulfilledRequirements:fulfilled,openRequirements:requirements,capitalContextAvailable:!!insurerSolvency,scoreContribution:0,explanation:'Capital data coverage only. Underwriting, reserve, investment and liquidity risks are not calibrated by these disclosures.'}};
}
