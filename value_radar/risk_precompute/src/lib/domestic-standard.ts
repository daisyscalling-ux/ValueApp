// Banken nach japanischem Inlandsstandard (国内基準): Sie melden eine „Core Capital“-Quote (Mindestquote 4 %), keine CET1-Quote
// mit Basel-III-Anforderung, und unterliegen keiner LCR-Pflicht. Kapitalpuffer und LCR werden deshalb bewusst nicht verglichen.
// Prüfung beim Lesen: Kennzeichnung, Beleg (https, SHA-256, Fundstelle), Stichtag des Belegs <= 270 Tage, gültige Prüfung.
type Row=Record<string,any>;
export const DOMESTIC_MAX_AGE_DAYS=270;
export const DOMESTIC_STANDARDS:Record<string,string>={jp_domestic_core_capital:'Japanischer Inlandsstandard (Core Capital, Mindestquote 4 %)'};
const DAY=86400000,SHA=/^[0-9a-f]{64}$/;
const dateOnly=(v:any)=>typeof v==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(v)&&Number.isFinite(Date.parse(v));
const https=(v:any)=>{try{return new URL(v).protocol==='https:'}catch{return false}};
const text=(v:any)=>typeof v==='string'&&v.trim()!=='';
export type DomesticStandard={standard:string;label:string;period:string;holdingName:string;domesticRatio:number|null;sourceUrl:string;sourceDetail:string;lcrRuleUrl:string;lcrRuleDetail:string};
export function domesticStandard(c:Row|null|undefined,now=Date.now()):DomesticStandard|null{
 const age=(now-Date.parse(c?.period))/DAY,today=new Date(now).toISOString().slice(0,10),l=c?.lcrRule;
 if(c?.state!=='not_applicable'||c.scope!=='domestic_capital_standard'||!DOMESTIC_STANDARDS[c.standard]||!dateOnly(c.period)||!(age>=0&&age<=DOMESTIC_MAX_AGE_DAYS))return null;
 if(!dateOnly(c.identityReviewExpires)||c.identityReviewExpires<today||!SHA.test(c.sourceFileSha256||'')||!https(c.sourceUrl)||!text(c.sourceDetail))return null;
 if(!https(l?.url)||!SHA.test(l?.sha256||'')||!text(l?.location))return null;
 const r=c.domesticCapitalRatio;
 return {standard:c.standard,label:DOMESTIC_STANDARDS[c.standard],period:c.period,holdingName:String(c.holdingName||''),domesticRatio:typeof r==='number'&&Number.isFinite(r)&&r>=0&&r<=1?r:null,
  sourceUrl:c.sourceUrl,sourceDetail:c.sourceDetail,lcrRuleUrl:l.url,lcrRuleDetail:l.location};
}
export const DOMESTIC_CAPITAL_REASON='Inlandsstandard: Die Bank rechnet nach dem japanischen Inlandsstandard mit „Core Capital“ (Mindestquote 4 %). Eine CET1-Quote mit Basel-III-Anforderung gibt es dafür nicht; die Kennzahl wird bewusst nicht verglichen.';
export const DOMESTIC_LCR_REASON='Keine LCR-Pflicht: Die japanische LCR gilt nur für Banken mit Auslandsgeschäftsstellen (FSA-Bekanntmachung Nr. 62/2014, Art. 2), also nicht für Banken nach Inlandsstandard. Kennzahl bewusst nicht geführt.';
