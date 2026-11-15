/**
 * scanner-evaluation.ts - Scanner-Werte aus demselben Rechenweg wie die Einzelanalyse (evaluateStock).
 * Die Pipeline (ValueApp, export_cf.py) ruft diese Funktion seit 13.11.2026 fuer jede Zeile von
 * cf_universum.json auf; vorher rechnete sie mit einer eigenen Python-Fassung (Abweichungen siehe
 * BEWERTUNG_RISIKODATEN.md). Identische Kopie unter ValueApp/value_radar/risk_precompute/src/lib.
 */
import {evaluateStock} from './evaluation';
import {analystTarget,reverseDcfImpliedGrowth,type Fund} from './valuation';
import {valuationDataCheck} from './valuation-data';
import type {HealthDistribution} from './financial-health';

export const SCANNER_METHOD='ts-evaluate-v1';
type Row=Record<string,any>;
const r1=(v:unknown)=>typeof v==='number'&&Number.isFinite(v)?Math.round(v*10)/10:null;
const r2=(v:unknown)=>typeof v==='number'&&Number.isFinite(v)?Math.round(v*100)/100:null;

/**
 * Erwartungslücke als Kontext (seit 15.11.2026, Entscheidung des Nutzers: nur anzeigen, scoreContribution 0).
 * Wie im Risikoscore (risk-construct.ts, valuationMetrics): Reverse DCF (vom Kurs vorausgesetztes Cashflow-Wachstum)
 * minus Umsatzwachstum des letzten Geschäftsjahres. Banken, Versicherer und Spezialfinanzierer: eigenes Finanzmodell in
 * der Risikokarte, hier offen. Kein Einfluss auf Quantum, Composite, Fair Value oder Urteil: unkalibriert, und hohe
 * Investitionen drücken den freien Cashflow (kapitalintensive Firmen erschienen sonst systematisch zu teuer).
 */
export const EXPECTATION_GAP_METHOD='reverse_dcf_minus_revenue_growth_v1';
export function expectationGap(fund:Fund&Row,profile:string|null,blocked:boolean){
 const base={method:EXPECTATION_GAP_METHOD,scoreContribution:0 as const};
 if(blocked)return {...base,status:'Bewertungsdaten gesperrt'};
 if(profile==='bank'||profile==='insurer'||profile==='specialist_financial')return {...base,status:'Finanzmodell: siehe Risikokarte der Einzelanalyse'};
 if(!(typeof fund.free_cashflow==='number'&&fund.free_cashflow>0))return {...base,status:'Freier Cashflow negativ oder nicht berichtet, Reverse DCF nicht anwendbar'};
 const implied=reverseDcfImpliedGrowth(fund),g=fund.revenue_growth;
 if(typeof implied!=='number'||!Number.isFinite(implied))return {...base,status:'Reverse DCF liefert kein eindeutiges vorausgesetztes Wachstum'};
 if(typeof g!=='number'||!Number.isFinite(g)||g<=-0.9||g>=5)return {...base,status:'Gültiges Umsatzwachstum fehlt'};
 return {...base,status:null,implied_growth:r1(implied*100),revenue_growth:r1(g*100),gap_pp:r1((implied-g)*100)};
}

/** Kauf-Urteil wie bisher in der Pipeline: Abschlag UND Qualitaet UND keine Value-Trap, nur auf geprueften Daten. */
export function kaufUrteil(x:{blocked:boolean;fallback:boolean;upside:number|null;quality:number|null;composite:number|null;valueTrap:boolean}):'kauf'|'beobachten'|'meiden'|'Daten prüfen'{
 if(x.blocked)return 'Daten prüfen';
 const belastbar=!x.fallback,comp=x.composite??0;
 const kauf=belastbar&&x.upside!==null&&x.upside>=10&&(x.quality??0)>=55&&comp>=55&&!x.valueTrap;
 const knapp=belastbar&&x.upside!==null&&x.upside>=0&&comp>=50&&!kauf;
 return kauf?'kauf':knapp?'beobachten':'meiden';
}

/** Angezeigter Upside wie bisher: Modellwert, bei gedeckeltem Fair Value das gepruefte Analystenziel. */
export function displayUpside(fund:Fund&Row,fv:{upside_pct:number|null;capped:boolean}):number|null{
 if(fv.capped){const t=analystTarget(fund);if(t&&fund.price)return Math.round((t/fund.price-1)*1000)/10;}
 return fv.upside_pct;
}

export function scannerFields(input:Fund&Row,peerRows:Row[]|null=null,riskCoverage:Row|null=null,healthDistribution:HealthDistribution|null=null){
 const e=evaluateStock({...input},null,peerRows,riskCoverage,healthDistribution),fv=e.fv,cats=e.scores.category_scores as Record<string,number>;
 // Prüfung auf dem bewerteten Fund (Börsenwert, Berichtswährung und Prognose bereits normalisiert wie in der Einzelanalyse).
 const norm=e.fund as Fund&Row;
 const check=input.valuation_data??valuationDataCheck(norm),blocked=!!check.blocked;
 const upside=blocked?null:displayUpside(e.fund as Fund&Row,fv);
 const composite=blocked?null:e.scores.composite;
 return {
  scanner_method:SCANNER_METHOD,playbook:e.playbook,lifecycle_phase:fv.lifecycle?.id??null,
  composite:composite===null?null:Math.round(composite),
  fair_value:blocked?null:r2(fv.fair_value),upside:r1(upside),entry:blocked?null:r2(fv.entry_price),
  quantum:blocked?null:e.q.score,target_12m:blocked?null:r2(e.kz?.ziel),
  valuation_issues:blocked?check.issues:[],
  market_cap:r2(norm.market_cap),market_cap_source:norm.market_cap_source??null,
  expectation_gap:expectationGap(norm,(e.scores as Row)._health_profile??null,blocked),
  eps_forward:typeof e.fund.eps_forward==='number'?Math.round(e.fund.eps_forward*10000)/10000:null,eps_forward_method:e.fund.eps_forward_method??null,
  eps_forward_source:e.fund.eps_forward_source??null,eps_forward_status:e.fund.eps_forward_status??null,
  peer_count:e.peerCount,composite_peer_metrics:Object.entries((e.scores as Row).metric_source??{}).filter(([,v])=>v==='peers').map(([k])=>k).sort(),
  ev_ebitda_anchor:fv.ev_ebitda_anchor?.source??null,
  health_source:(e.scores as Row)._health_source??null,health_raw:(e.scores as Row)._health_raw??null,health_profile:(e.scores as Row)._health_profile??null,health_parts:((e.scores as Row)._health_risk?.parts??[]).map((p:Row)=>p.name),
  cash_conversion:typeof e.fund.cash_conversion==='number'?Math.round(e.fund.cash_conversion*1000)/1000:null,cash_conversion_source:e.fund.cash_conversion_source??null,fv_confidence:fv.confidence,fv_reliable:fv.reliable,
  momentum:r1(cats.momentum),quality:r1(cats.quality),value:r1(cats.valuation),growth:r1(cats.growth),catalyst:r1(cats.catalyst),health:r1(cats.health),
  cat_neutral:(e.scores as Row).cat_neutral??{},value_trap:!!e.scores.value_trap,vt_warnung:e.q.value_trap_warnung??[],
  kauf_urteil:kaufUrteil({blocked,fallback:fv.used_fallback,upside,quality:cats.quality??null,composite,valueTrap:!!e.scores.value_trap}),
 };
}
