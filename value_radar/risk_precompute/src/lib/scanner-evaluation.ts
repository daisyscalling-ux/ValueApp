/**
 * scanner-evaluation.ts - Scanner-Werte aus demselben Rechenweg wie die Einzelanalyse (evaluateStock).
 * Die Pipeline (ValueApp, export_cf.py) ruft diese Funktion seit 13.11.2026 fuer jede Zeile von
 * cf_universum.json auf; vorher rechnete sie mit einer eigenen Python-Fassung (Abweichungen siehe
 * BEWERTUNG_RISIKODATEN.md). Identische Kopie unter ValueApp/value_radar/risk_precompute/src/lib.
 */
import {evaluateStock} from './evaluation';
import {analystTarget,reverseDcfImpliedGrowth,reverseDcfInput,type Fund} from './valuation';
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
 const inp=reverseDcfInput(fund);
 if(!inp)return {...base,status:'Weder Gewinn × geprüfte Cash-Conversion noch berichteter freier Cashflow positiv, Reverse DCF nicht anwendbar'};
 const implied=reverseDcfImpliedGrowth(inp.fund),g=fund.revenue_growth;
 if(typeof implied!=='number'||!Number.isFinite(implied))return {...base,status:'Reverse DCF liefert kein eindeutiges vorausgesetztes Wachstum'};
 if(typeof g!=='number'||!Number.isFinite(g)||g<=-0.9||g>=5)return {...base,status:'Gültiges Umsatzwachstum fehlt'};
 return {...base,status:null,implied_growth:r1(implied*100),revenue_growth:r1(g*100),gap_pp:r1((implied-g)*100),cashflow_basis:inp.quelle};
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
 // Gewinnstichtag der ROIC-Zeile als Rohdaten-Ersatz: dieselben Periodenprüfungen wie in der Einzelanalyse.
 const check=input.valuation_data??valuationDataCheck(norm,norm.income_period?{income:[{period_end_date:norm.income_period,period_type:'annual',currency:norm.income_currency}]}:undefined),blocked=!!check.blocked;
 const upside=blocked?null:displayUpside(e.fund as Fund&Row,fv);
 const composite=blocked?null:e.scores.composite;
 return {
  scanner_method:SCANNER_METHOD,playbook:e.playbook,lifecycle_phase:fv.lifecycle?.id??null,
  composite:composite===null?null:Math.round(composite),
  fair_value:blocked?null:r2(fv.fair_value),upside:r1(upside),entry:blocked?null:r2(fv.entry_price),
  quantum:blocked?null:e.q.score,target_12m:blocked?null:r2(e.kz?.ziel),
  valuation_issues:blocked?check.issues:[],
  market_cap:r2(norm.market_cap),market_cap_source:norm.market_cap_source??null,share_count_basis:norm.share_count_basis??null,
  annual_supplement_applied:!!norm.annual_supplement_applied,supplement_annual_end:norm.supplement_annual_end??null,supplement_retained_fields:norm.supplement_retained_fields??null,
  expectation_gap:expectationGap(norm,(e.scores as Row)._health_profile??null,blocked),
  // Umgerechnete Kennzahlen für Anzeige und Peers der Universumszeile (nur wenn umgerechnet; sonst bleiben die Pipeline-Werte).
  report_fx:norm.report_fx??null,report_fx_status:norm.report_fx_status??null,
  report_converted:(norm.report_fx||norm.annual_supplement_applied)?{eps_trailing:r2(norm.eps_trailing),book_value_ps:r2(norm.book_value_ps),pe:r1(norm.pe_trailing),pb:r2(norm.pb),ev_ebitda:r1(norm.ev_ebitda)}:null,
  eps_forward:typeof e.fund.eps_forward==='number'?Math.round(e.fund.eps_forward*10000)/10000:null,eps_forward_method:e.fund.eps_forward_method??null,
  eps_forward_source:e.fund.eps_forward_source??null,eps_forward_status:e.fund.eps_forward_status??null,eps_forward_check:e.fund.eps_forward_check??null,
  peer_count:e.peerCount,composite_peer_metrics:Object.entries((e.scores as Row).metric_source??{}).filter(([,v])=>v==='peers').map(([k])=>k).sort(),
  ev_ebitda_anchor:fv.ev_ebitda_anchor?.source??null,
  health_source:(e.scores as Row)._health_source??null,health_raw:(e.scores as Row)._health_raw??null,health_profile:(e.scores as Row)._health_profile??null,health_parts:((e.scores as Row)._health_risk?.parts??[]).map((p:Row)=>p.name),
  cash_conversion:typeof e.fund.cash_conversion==='number'?Math.round(e.fund.cash_conversion*1000)/1000:null,cash_conversion_source:e.fund.cash_conversion_source??null,cash_conversion_origin:e.fund.cash_conversion_origin??null,fv_confidence:fv.confidence,fv_reliable:fv.reliable,
  // Diagnose (seit 16.11.2026, keine Rechenwirkung): Eingang, Teilnote und Massstab je Bewertungskennzahl sowie die
  // Teile der Katalysator-Note, damit der Abgleich App gegen Screener die Ursache einer Composite-Abweichung zeigt.
  // Seit 17.11.2026: Forward-KGV, PEG und FCF-Rendite aus value-inputs.ts (gleiche Methode in App und Screener); die Peers
  // der Universumszeilen lesen sie von hier. Offene Kennzahlen mit Grund, schlechteste Note mit Grund.
  value_inputs:(()=>{const v=(e.fund as Row).value_inputs;return v?{method:v.method,pe_forward:r2(v.pe_forward),peg:r2(v.peg),fcf_yield:typeof v.fcf_yield==='number'?Math.round(v.fcf_yield*10000)/10000:null,open:v.open,worst:v.worst}:null})(),
  eps_forward_no_profit:e.fund.eps_forward_no_profit===true,
  score_diagnostics:{value:Object.fromEntries(['ev_ebitda','pb','pe_forward','peg','fcf_yield'].map(k=>[k,{input:typeof (e.scores as Row)._inputs?.[k]==='number'?r2((e.scores as Row)._inputs[k]):null,score:(e.scores as Row).breakdown?.[k]??null,basis:(e.scores as Row).metric_source?.[k]??((e.scores as Row).metric_open?.[k]?'open':null),open:(e.scores as Row).metric_open?.[k]??null}])),
   catalyst:((e.scores as Row)._catalyst_teile??[]).map(([n,v]:[string,number])=>[n,v]),
   // Seit 17.11.2026: Teilziele des 12M-Kursziels, damit der Abgleich App gegen Screener die Ursache zeigt.
   target:e.kz?{fundamental:r2(e.kz.ziel_fundamental),analyst:r2(e.kz.ziel_analyst),momentum:r2(e.kz.ziel_momentum),eps:r2(e.kz.eps_annahme),kgv:r1(e.kz.kgv_annahme),kgv_hist:r1(e.kz.kgv_hist)}:null},
  roic_history_status:(e.fund as Row).roic_history_status??null,
  eps_basis:fv.eps_basis?.source??null,
  terminal_growth:fv.terminal_growth?{value:fv.terminal_growth.value,source:fv.terminal_growth.source}:null,
  risk_free:fv.risk_free?{value:fv.risk_free.value,source:fv.risk_free.source,currency:fv.risk_free.currency,as_of:fv.risk_free.as_of}:null,
  momentum:r1(cats.momentum),quality:r1(cats.quality),value:r1(cats.valuation),growth:r1(cats.growth),catalyst:r1(cats.catalyst),health:r1(cats.health),
  cat_neutral:(e.scores as Row).cat_neutral??{},value_trap:!!e.scores.value_trap,vt_warnung:e.q.value_trap_warnung??[],
  kauf_urteil:kaufUrteil({blocked,fallback:fv.used_fallback,upside,quality:cats.quality??null,composite,valueTrap:!!e.scores.value_trap}),
 };
}
