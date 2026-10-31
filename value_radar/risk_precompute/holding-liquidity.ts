type Row=Record<string,any>;
const day=86400000;
const date=(v:any)=>typeof v==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(v)&&Number.isFinite(Date.parse(v))&&new Date(v).toISOString().slice(0,10)===v;
export function verifiedLiquidity(r:Row|undefined|null,parent:Row,now=Date.now()){
 if(!r||r.state!=='available'||r.method!=='reviewed-holding-lcr-v1'||r.rssdId!==parent.rssdId||r.holdingName!==parent.holdingName||r.period!==parent.period||r.scope!=='listed_consolidated_holding'||r.averaging!=='quarter_average'||r.unit!=='fraction'||r.currency!=='USD')return null;
 if(![r.period,r.reviewedOn,r.reviewExpires].every(date)||Date.parse(r.period)>now||now-Date.parse(r.period)>180*day||r.reviewedOn<r.period||Date.parse(r.reviewedOn)>now||Date.parse(r.reviewExpires+'T23:59:59Z')<now)return null;
 if(!/^https:\/\/www\.sec\.gov\/Archives\/edgar\/data\/\d+\/\d+\/[A-Za-z0-9_.-]+\.htm$/.test(r.sourceUrl||''))return null;
 if(!['hqla','netOutflows','reportedRatio','ratioRoundingTolerance'].every(k=>typeof r[k]==='number'&&Number.isFinite(r[k])))return null;
 if(r.hqla<0||r.netOutflows<=0||r.reportedRatio<0||r.reportedRatio>10||r.ratioRoundingTolerance<0||r.ratioRoundingTolerance>.005||Math.abs(r.hqla/r.netOutflows-r.reportedRatio)>r.ratioRoundingTolerance)return null;
 return r;
}
