import {depositaryOrigin} from './depositary';
// Banken außerhalb EU/EWR/USA: veröffentlichte Basel-Kennzahlen (APRA, Basel-Offenlegung KM1, Kapitalangaben aus Zwischen-/Quartalsberichten).
// Gemeinsame Prüfung für Score und Anzeige; Spiegel von verifiedIntlCapital in der täglichen Vorberechnung.
type Row=Record<string,any>;
export const INTL_MAX_AGE_DAYS=270;
const DAY=86400000;
const dateOnly=(v:any)=>typeof v==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(v)&&Number.isFinite(Date.parse(v));
const fraction=(v:any)=>typeof v==='number'&&Number.isFinite(v)&&v>=0&&v<=1;
export const SOURCE_LABELS:Record<string,string>={apra_adi_centralised_publication:'APRA · ADI centralised publication',basel_pillar3_km1:'Basel-Offenlegung KM1 (Säule 3)',bank_capital_release:'Kapitalangaben im Zwischen- bzw. Quartalsbericht der Bank (keine KM1-Tabelle)'};
// Quellen, die selbst keine Kapitalanforderung enthalten können, sondern nur das, was die Bank im Bericht nennt.
export const REPORT_SOURCES=new Set(['bank_capital_release']);
// Kreditqualität (CR1) mit eigenem Stichtag: in Japan erscheint CR1 nur im Jahres-/Halbjahresbericht, KM1 vierteljährlich.
// Methoden: Basel CR1 (ausgefallene Kredite) und UK CR1 (notleidende Kredite nach EBA-Definition, seit 12.11.2026).
export const CREDIT_METHODS:Record<string,{source:string;label:string;definition:string}>={
 'basel-cr1-default-v1':{source:'basel_pillar3_cr1',label:'Ausgefallene Kredite (Basel CR1)',definition:'Ausgefallene / gesamte Kredite nach Basel-Ausfalldefinition (90 Tage überfällig oder Zahlung unwahrscheinlich), Tabelle CR1.'},
 'uk-cr1-npl-v1':{source:'uk_pillar3_cr1',label:'Notleidende Kredite (UK CR1)',definition:'Notleidende / gesamte Kredite und Darlehen (Zeile 010), Bruttobuchwert, Säule-3-Tabelle UK CR1 nach EBA-Definition – wie die EU-NPL-Quote.'}};
export type IntlCredit={period:string;separate:boolean;sourceUrl:string;sourceDetail:string;method:string};
export type IntlBank={period:string;holdingName:string;regulator:string;source:string;cet1:number;lcr:number|null;nsfr:number|null;requirement:{value:number;headroom:number}|null;defaulted:number|null;credit:IntlCredit|null;sourceUrl:string;sourceKind:string;sourceDetail:string};
const SHA=/^[0-9a-f]{64}$/;
// Gesonderter CR1-Stichtag: höchstens 270 Tage alt, nicht nach dem KM1-Stichtag, eigene Quelle mit SHA-256 und Fundstelle.
function separateCr1(cr:Row,c:Row,now:number){
 const age=(now-Date.parse(cr.period))/DAY;
 return cr.periodBasis==='separate_cr1'&&dateOnly(cr.period)&&cr.period<=c.period&&age>=0&&age<=INTL_MAX_AGE_DAYS&&CREDIT_METHODS[cr.method]?.source===cr.sourceType&&SHA.test(cr.sourceFileSha256||'')&&typeof cr.sourceUrl==='string'&&cr.sourceUrl.startsWith('https://')&&typeof cr.sourceDetail==='string'&&cr.sourceDetail.trim()!=='';
}
// Begründung, wenn keine Anforderung vorliegt: bei Berichtsquellen fehlt sie in der Quelle, sonst veröffentlicht die Aufsicht keine.
export function missingRequirementReason(x:IntlBank){return REPORT_SOURCES.has(x.sourceKind)?'Der verwendete Bericht der Bank nennt keine CET1-Anforderung; eine KM1-Tabelle mit Anforderung liegt zu diesem Stichtag nicht vor.':'Die Aufsicht ('+x.regulator+') veröffentlicht keine bankspezifische Anforderung.'}
export function intlBankCapital(c:Row|null|undefined,now=Date.now()):IntlBank|null{
 if(depositaryOrigin(c,now)?.valid===false)return null;
 const t=c?.sourceType,m=c?.metrics?.cet1_ratio,age=(now-Date.parse(c?.period))/DAY,today=new Date(now).toISOString().slice(0,10);
 if(c?.state!=='available'||c.scope!=='basel_key_metrics'||typeof t!=='string'||!SOURCE_LABELS[t]||!dateOnly(c.period)||!(age>=0&&age<=INTL_MAX_AGE_DAYS)||!dateOnly(c.identityReviewExpires)||c.identityReviewExpires<today)return null;
 if(m?.state!=='available'||m.unit!=='fraction'||m.sourceField!==t+':cet1_ratio'||!fraction(m.value))return null;
 const l=c.liquidity,q=c.capitalRequirement;
 const lcr=l?.state==='available'&&l.method==='intl-lcr-v1'&&l.period===c.period&&typeof l.reportedRatio==='number'&&l.reportedRatio>0&&l.reportedRatio<10?l.reportedRatio:null;
 const requirement=q?.state==='available'&&q.method==='basel-km1-cet1-requirement-v1'&&q.comparisonPeriod===c.period&&dateOnly(q.reviewExpires)&&q.reviewExpires>=today&&typeof q.value==='number'&&q.value>0&&q.value<.3?{value:q.value,headroom:(m.value-q.value)*100}:null;
 const cr=c.creditQuality,base=cr?.state==='available'&&!!CREDIT_METHODS[cr.method]&&fraction(cr.ratio);
 // UK CR1 nur über den gesonderten, belegten Block; Basel CR1 auch mit gleichem Stichtag wie KM1 (bisherige Regel).
 const separate=base&&separateCr1(cr,c,now),defaulted=base&&(separate||cr.method==='basel-cr1-default-v1'&&cr.period===c.period)?cr.ratio:null;
 const credit:IntlCredit|null=defaulted===null?null:separate?{period:cr.period,separate:cr.period!==c.period||cr.method!=='basel-cr1-default-v1',sourceUrl:cr.sourceUrl,sourceDetail:cr.sourceDetail,method:cr.method}:{period:c.period,separate:false,sourceUrl:String(c.sourceUrl||''),sourceDetail:String(c.sourceDetail||''),method:cr.method};
 return {defaulted,credit,period:c.period,holdingName:String(c.holdingName||''),regulator:String(c.regulator||''),source:SOURCE_LABELS[t],cet1:m.value,lcr,nsfr:typeof l?.nsfr==='number'&&Number.isFinite(l.nsfr)?l.nsfr:null,requirement,sourceUrl:String(c.sourceUrl||''),sourceKind:t,sourceDetail:String(c.sourceDetail||'')};
}
