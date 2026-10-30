type Row=Record<string,any>;
const codes:Row={nonaccrual:'BHCK1403',past_due_30_89:'BHCK1406',past_due_90:'BHCK1407',held_for_investment:'BHCKB528',held_for_sale:'BHCK5369'};
export function verifiedCreditQuality(c:Row|undefined|null,parent:Row,now:number):Row{
 const missing={state:'missing',reason:'verified_same_period_credit_fields_unavailable'};
 if(c?.state!=='available'||c.method!=='bhcf-loan-quality-v1'||c.period!==parent.period||c.rssdId!==parent.rssdId||c.sourceFileSha256!==parent.sourceFileSha256||c.unit!=='fraction'||c.amountUnit!=='USD_thousands')return missing;
 const imported=Date.parse(c.sourceImportedAt);if(!Number.isFinite(imported)||imported>now||imported<Date.parse(c.period))return missing;
 const f=c.components;
 if(!f||!Object.entries(codes).every(([name,code])=>c.sourceFields?.[name]===code&&Number.isSafeInteger(f[name])&&f[name]>=0&&f[name]<=9007199254740))return missing;
 const total=f.held_for_investment+f.held_for_sale;
 if(total<=0||f.nonaccrual+f.past_due_30_89+f.past_due_90>total||total!==c.totalLoans)return missing;
 const ratios:Row={nonaccrual:f.nonaccrual/total,past_due_30_89:f.past_due_30_89/total,past_due_90:f.past_due_90/total,nonaccrual_or_90_past_due:(f.nonaccrual+f.past_due_90)/total};
 if(!Object.entries(ratios).every(([k,v])=>typeof c.ratios?.[k]==='number'&&Number.isFinite(c.ratios[k])&&Math.abs(c.ratios[k]-v)<1e-12))return missing;
 return {...c,ratios,score:null,pointInTimeUsable:false};
}
