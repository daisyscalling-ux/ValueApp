import {depositaryOrigin} from './depositary';
// EU/EWR-Banken: EBA-Transparenzdaten (CET1, Leverage, NPL); Saeule-3-KM1 aus dem EBA Pillar 3 Data Hub (vollstaendige
// CET1-Anforderung, LCR, NSFR), sonst Teilanforderung aus EZB-P2R.
// Gemeinsame Prüfung für Score und Anzeige; Spiegel von verifiedEuCapital in der täglichen Vorberechnung.
type Row=Record<string,any>;
export const EU_MAX_AGE_DAYS=730;
const DAY=86400000;
const dateOnly=(v:any)=>typeof v==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(v)&&Number.isFinite(Date.parse(v));
const fraction=(v:any)=>typeof v==='number'&&Number.isFinite(v)&&v>=0&&v<=1;
export const KM1_MAX_AGE_DAYS=270;
// Vollstaendige Anforderung (EU KM1, EBA Pillar 3 Data Hub) oder Teilanforderung ohne Systempuffer (EZB-P2R).
// Herleitungen der vollständigen EU-Anforderung (Pipeline import_eu_pillar3.py); unbekannte Werte werden neutral als „abgeleitet“ gekennzeichnet.
export const EU_REQUIREMENT_DERIVATIONS:Record<string,string>={
 p2r_cet1_zero_because_total_srep_equals_pillar1_8pct:'keine Säule-2-Zusatzanforderung gemeldet (SREP-Gesamtanforderung 8 %)',
 reviewed_unit_correction_p2r_cet1_percent:'CET1-Anteil der SREP-Zusatzanforderung im Hub als Prozentwert gemeldet; geprüft auf den Anteil korrigiert und mit der von der Bank veröffentlichten CET1-Anforderung abgeglichen'};
export const derivationText=(d:string|null|undefined)=>d?(EU_REQUIREMENT_DERIVATIONS[d]||'Anforderung abgeleitet ('+d+')'):'';
// Herleitung erneut prüfen: unbekannte Herleitung -> keine vollständige Anforderung; Einheitenkorrektur nur mit gültigem Nachweis (Faktor 100, Quelle, Prüfsumme, Ablauf).
const derivationOk=(q:any,today:string)=>{
 const d=q?.derivation;if(d==null)return true;
 if(d==='p2r_cet1_zero_because_total_srep_equals_pillar1_8pct')return true;
 if(d!=='reviewed_unit_correction_p2r_cet1_percent')return false;
 const u=q.unitCorrection;
 return !!u&&u.field==='srep_additional_cet1'&&typeof u.reportedValue==='number'&&typeof u.correctedValue==='number'&&Math.abs(u.correctedValue*100-u.reportedValue)<1e-9
  &&typeof u.statedRequirement==='number'&&Math.abs(q.value-u.statedRequirement)<=.001&&typeof u.evidenceUrl==='string'&&u.evidenceUrl.startsWith('https://')&&/^[0-9a-f]{64}$/.test(u.evidenceSha256||'')
  &&dateOnly(u.reviewedOn)&&u.reviewedOn<=today&&dateOnly(u.reviewExpires)&&u.reviewExpires>=today;
};
export type EuRequirement={kind:'full';value:number;headroom:number;cet1:number;period:string;sourceUrl:string;derivation:string|null}|{kind:'partial';value:number;headroom:number;p2r:number;p2rYear:number};
export type EuBank={period:string;ageDays:number;holdingName:string;exercise:string;cet1:number;leverage:number|null;
 requirement:EuRequirement|null;npl:number|null;nplSource:{kind:'cr1'|'eba';period:string}|null;sourceUrl:string;capitalSource:'eba_transparency'|'eba_p3dh_km1';lcr:{value:number;nsfr:number|null;period:string;sourceUrl:string}|null};
const p3dh=(x:any)=>typeof x?.sourceUrl==='string'&&x.sourceUrl.startsWith('https://errp.eba.europa.eu/public-documents/')&&/^[0-9a-f]{64}$/.test(x.sourceFileSha256||'');
const recent=(v:any,now:number,days:number)=>dateOnly(v)&&now-Date.parse(v)>=0&&now-Date.parse(v)<=days*DAY;
export function euBankCapital(c:Row|null|undefined,now=Date.now()):EuBank|null{
 if(depositaryOrigin(c,now)?.valid===false)return null;
 const m=c?.metrics?.cet1_ratio,age=(now-Date.parse(c?.period))/DAY,today=new Date(now).toISOString().slice(0,10);
 if(c?.state!=='available'||c.scope!=='eu_prudential_group'||!dateOnly(c.period)||!(age>=0&&age<=EU_MAX_AGE_DAYS)||!dateOnly(c.identityReviewExpires)||c.identityReviewExpires<today)return null;
 // Banken ohne EBA-Transparenzdaten: Quoten ausschliesslich aus EU KM1 (Pillar 3 Data Hub), nur mit Hub-Originaldatei und hoechstens 270 Tage alt.
 const p3only=c.capitalSource==='eba_p3dh_km1';
 if(p3only&&!(p3dh(c)&&age<=KM1_MAX_AGE_DAYS))return null;
 const code=p3only?{cet1:'P3DH:K_61.00/0050',lev:'P3DH:K_61.00/0220'}:{cet1:'EBA:2520140',lev:'EBA:2520905'};
 if(m?.state!=='available'||m.unit!=='fraction'||m.sourceField!==code.cet1||!fraction(m.value))return null;
 const q=c.capitalRequirement,cr=c.creditQuality,lev=c.metrics?.leverage_ratio;
 const full=q?.state==='available'&&q.method==='eba-p3dh-km1-cet1-requirement-v1'&&q.unit==='fraction'&&typeof q.value==='number'&&q.value>0&&q.value<.3&&typeof q.cet1Ratio==='number'&&q.cet1Ratio>0&&q.cet1Ratio<1
  &&recent(q.comparisonPeriod,now,KM1_MAX_AGE_DAYS)&&dateOnly(q.reviewExpires)&&q.reviewExpires>=today&&p3dh(q)&&derivationOk(q,today);
 const requirement:EuRequirement|null=full?{kind:'full',value:q.value,cet1:q.cet1Ratio,headroom:(q.cet1Ratio-q.value)*100,period:q.comparisonPeriod,sourceUrl:q.sourceUrl,derivation:q.derivation??null}
  :q?.state==='available'&&q.method==='ecb-p2r-partial-cet1-v1'&&q.comparisonPeriod===c.period&&dateOnly(q.reviewExpires)&&q.reviewExpires>=today&&typeof q.value==='number'&&q.value>0&&q.value<.3
  ?{kind:'partial',value:q.value,headroom:(m.value-q.value)*100,p2r:q.p2r,p2rYear:q.p2rYear}:null;
 const l=c.liquidity;
 const lcr=l?.state==='available'&&l.method==='eba-p3dh-km1-lcr-v1'&&l.unit==='fraction'&&typeof l.reportedRatio==='number'&&l.reportedRatio>0&&l.reportedRatio<10&&recent(l.period,now,KM1_MAX_AGE_DAYS)&&p3dh(l)
  ?{value:l.reportedRatio,nsfr:typeof l.nsfr==='number'&&Number.isFinite(l.nsfr)?l.nsfr:null,period:l.period,sourceUrl:l.sourceUrl}:null;
 // NPL aus EU CR1 (Pillar 3 Data Hub, FINDIS) mit eigenem Stichtag <= 270 Tage, sonst EBA-Transparenz-NPL desselben Stichtags.
 const cr1=cr?.state==='available'&&cr.method==='eba-p3dh-cr1-npl-v1'&&cr.unit==='fraction'&&cr.lei===c.lei&&fraction(cr.ratio)&&recent(cr.period,now,KM1_MAX_AGE_DAYS)&&p3dh(cr)&&String(cr.sourceUrl).includes('/public-documents/FINDIS/');
 const eba=!cr1&&cr?.state==='available'&&cr.method==='eba-npl-v1'&&cr.period===c.period&&fraction(cr.ratio);
 const npl=cr1||eba?cr.ratio:null,nplSource=cr1?{kind:'cr1' as const,period:cr.period}:eba?{kind:'eba' as const,period:c.period}:null;
 return {period:c.period,ageDays:Math.floor(age),holdingName:String(c.holdingName||''),exercise:String(c.exercise||'EBA EU-wide Transparency Exercise'),cet1:m.value,
  leverage:lev?.state==='available'&&lev.sourceField===code.lev&&fraction(lev.value)?lev.value:null,requirement,npl,nplSource,sourceUrl:String(c.sourceUrl||''),capitalSource:p3only?'eba_p3dh_km1':'eba_transparency',lcr};
}
