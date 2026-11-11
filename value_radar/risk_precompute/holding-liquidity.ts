type Row=Record<string,any>;
const day=86400000;
const date=(v:any)=>typeof v==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(v)&&Number.isFinite(Date.parse(v))&&new Date(v).toISOString().slice(0,10)===v;
const secUrl=(v:any)=>/^https:\/\/www\.sec\.gov\/Archives\/edgar\/data\/\d+\/\d+\/[A-Za-z0-9_.-]+\.htm$/.test(v||'');
const num=(v:any)=>typeof v==='number'&&Number.isFinite(v);
// Gemeinsame Pruefung: Holding, Stichtag wie das Kapital, Frische, Pruefdaten, SEC-Originaldokument.
function anchored(r:Row,parent:Row,now:number){
 if(r.method!=='reviewed-holding-lcr-v1'||r.rssdId!==parent.rssdId||r.holdingName!==parent.holdingName||r.period!==parent.period||r.scope!=='listed_consolidated_holding')return false;
 if(![r.period,r.reviewedOn,r.reviewExpires].every(date)||Date.parse(r.period)>now||now-Date.parse(r.period)>180*day||r.reviewedOn<r.period||Date.parse(r.reviewedOn)>now||Date.parse(r.reviewExpires+'T23:59:59Z')<now)return false;
 return secUrl(r.sourceUrl)&&typeof r.sourceSection==='string'&&r.sourceSection.trim().length>0;
}
// basis "amounts": HQLA und Nettoabfluesse berichtet, Quote gegengeprueft. basis "ratio_only" (seit 11.11.2026): nur die im
// Bericht genannte Durchschnitts-LCR; HQLA wo genannt, Nettoabfluesse nie zurueckgerechnet.
export function verifiedLiquidity(r:Row|undefined|null,parent:Row,now=Date.now()){
 if(!r||r.state!=='available'||!anchored(r,parent,now)||r.averaging!=='quarter_average'||r.unit!=='fraction'||r.currency!=='USD')return null;
 const basis=r.basis??'amounts';
 if(!num(r.reportedRatio)||r.reportedRatio<=0||r.reportedRatio>10)return null;
 if(basis==='amounts'){
  if(!['hqla','netOutflows','ratioRoundingTolerance'].every(k=>num(r[k])))return null;
  if(r.hqla<0||r.netOutflows<=0||r.ratioRoundingTolerance<0||r.ratioRoundingTolerance>.005||Math.abs(r.hqla/r.netOutflows-r.reportedRatio)>r.ratioRoundingTolerance)return null;
  return r;
 }
 if(basis==='ratio_only'){
  if(r.netOutflows!==null||!(r.hqla===null||num(r.hqla)&&r.hqla>=0))return null;
  return r;
 }
 return null;
}
// Gepruefte Ausnahme: keine LCR-Pflicht (US-Kategorie IV unter der Schwelle fuer kurzfristige Grosskundenfinanzierung).
export function verifiedLiquidityExemption(r:Row|undefined|null,parent:Row,now=Date.now()){
 if(!r||r.state!=='not_applicable'||!anchored(r,parent,now)||r.reason!=='us_category_iv_lcr_not_applicable')return null;
 return typeof r.quote==='string'&&r.quote.trim().length>=20?r:null;
}
