import {classifyPlaybook,fairValue,kursziel12m,analystTarget,type Fund} from './valuation';
import {scoreStock,quantumScore} from './scoring';
import {altmanZ,type Row} from './scores';
import {scoresPlus} from './scores_plus';
import {fundInEur,type EurRate} from './currency';

/** One evaluation path; scoring always uses the native statement units. */
export function evaluateStock(input:Fund & Record<string,any>,eur:EurRate|null=null){
 const fund={...input};
 const playbook=classifyPlaybook(fund);
 const nativeValue=fairValue(fund,null,playbook);
 fund._fv_wert=nativeValue.fair_value;
  const scores = scoreStock(fund as never, null, playbook);

  // VERBESSERTE Scores: Bilanz/Momentum/Katalysator mit den reicheren Daten
  // ueberschreiben. Der scoreStock-Kern bleibt, nur diese drei werden ersetzt.
  const akt0 = fund._forensik_akt as Row | undefined;
  const altZforHealth = akt0 ? (altmanZ(akt0, fund.sector as string, fund as Row)?.z ?? null) : null;
  const plus = scoresPlus(fund as Row, altZforHealth);
  if (plus.health !== null) scores.category_scores.health = plus.health;
  if (plus.momentum !== null) scores.category_scores.momentum = plus.momentum;
  // Katalysator: echten Wert ODER aus der Matrix nehmen (null)
  Object.assign(scores,{_catalyst_plus:plus.catalyst,_health_teile:plus.health_teile,_catalyst_teile:plus.catalyst_teile});
  if (plus.catalyst !== null) scores.category_scores.catalyst = plus.catalyst;

  // Composite mit den neuen Werten neu bilden (gleiche Gewichte, aber
  // Katalysator rausnehmen+renormalisieren, wenn keine Signale da).
  {
    const W: Record<string, Record<string, number>> = {
      quality:    { valuation: 0.25, quality: 0.25, growth: 0.20, health: 0.15, momentum: 0.10, catalyst: 0.05 },
      cyclical:   { valuation: 0.30, quality: 0.15, growth: 0.15, health: 0.20, momentum: 0.15, catalyst: 0.05 },
      inflection: { valuation: 0.15, quality: 0.20, growth: 0.35, health: 0.10, momentum: 0.15, catalyst: 0.05 },
      financial:  { valuation: 0.30, quality: 0.30, growth: 0.10, health: 0.10, momentum: 0.15, catalyst: 0.05 },
    };
    const w = { ...(W[playbook] ?? W.quality) };
    if (plus.catalyst === null) delete (w as Record<string, number>).catalyst;
    let num = 0, den = 0;
    for (const [k, g] of Object.entries(w)) {
      const v = (scores.category_scores as Record<string, number>)[k];
      if (v !== undefined && v !== null) { num += v * g; den += g; }
    }
    if (den > 0) scores.composite = Math.round(num / den * 10) / 10;
  }

 const display=fundInEur(fund,eur) as Fund & Record<string,any>;
 const fv=display.currency===fund.currency?nativeValue:fairValue(display,null,playbook);
 const targetFund={...display};
 if(!targetFund.hist_pe_median&&targetFund.pe_trailing)targetFund.hist_pe_median=targetFund.pe_trailing;
 const kz=kursziel12m(targetFund,playbook);
 const analyst=(fund.analyst_buy!==undefined||fund.analyst_hold!==undefined)
  ?{buy:Number(fund.analyst_buy??0),hold:Number(fund.analyst_hold??0),sell:Number(fund.analyst_sell??0)}:null;
 // Wie in der Pipeline (scoring.py, bis 12.11.2026): Analysten-Skepsis = Konsensziel gegen eigenen Fair Value;
 // Trend der Kursziele nur, wenn die Pipeline ihn aus ihrer Historie mitliefert (_analyst_trend).
 const target=analystTarget(display),skepsis=target&&fv.fair_value&&fv.fair_value>0?(target/fv.fair_value-1)*100:null;
 const trend=display._analyst_trend&&typeof display._analyst_trend==='object'?display._analyst_trend:null;
 const q=quantumScore(scores.composite,fv,analyst,scores.category_scores.momentum,null,skepsis,trend);
 display._fv_wert=fv.fair_value;display._composite_live=scores.composite;display._upside_live=fv.upside_pct;
 return {fund:display,playbook,fv,scores,altZforHealth,kz,q};
}
