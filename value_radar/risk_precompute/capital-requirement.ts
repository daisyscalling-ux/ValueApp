type Row=Record<string,any>;
export function verifiedCapitalRequirement(r:Row|null|undefined,capital:Row,now:number):Row|null{
 if(r?.state!=='available'||r.method!=='fed-cet1-requirement-v1'||r.rssdId!==capital.rssdId||r.holdingName!==capital.holdingName||r.comparisonPeriod!==capital.period||r.unit!=='fraction')return null;
 const date=(v:any)=>typeof v==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(v)&&Number.isFinite(Date.parse(v))&&new Date(v).toISOString().slice(0,10)===v;
 if(![r.publicationDate,r.applicableFrom,r.reviewExpires].every(date)||r.publicationDate>r.applicableFrom||r.applicableFrom>capital.period||capital.period>r.reviewExpires||new Date(now).toISOString().slice(0,10)>r.reviewExpires)return null;
 const age=now-Date.parse(r.sourceVerifiedAt);if(!Number.isFinite(age)||age<0||age>7*86400000)return null;
 if(r.sourceUrl!=='https://www.federalreserve.gov/publications/files/large-bank-capital-requirements-20260624.pdf'||r.sourceSha256!=='7a628b4395bca88cbd21f0600424fe41bc353058c7b3b6e386edb43ec8d17290')return null;
 const fields=['minimumBps','stressBufferBps','gsibBps','totalBps'];
 if(!fields.every(k=>Number.isInteger(r[k])&&r[k]>=0&&r[k]<=10000)||r.minimumBps!==450||r.stressBufferBps<250||r.minimumBps+r.stressBufferBps+r.gsibBps!==r.totalBps||r.value!==r.totalBps/10000)return null;
 const actual=capital.metrics?.cet1_ratio?.value;if(typeof actual!=='number'||!Number.isFinite(actual))return null;
 return {...r,headroomPercentagePoints:(actual-r.value)*100,comparison:'reported_quarter_end_to_applicable_fed_cet1',scoreContribution:0};
}
