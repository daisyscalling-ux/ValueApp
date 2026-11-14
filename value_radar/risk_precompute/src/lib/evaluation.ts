import {classifyPlaybook,fairValue,kursziel12m,analystTarget,type Fund} from './valuation';
import {scoreStock,quantumScore} from './scoring';
import {altmanZ,type Row} from './scores';
import {scoresPlus} from './scores_plus';
import {fundInEur,type EurRate} from './currency';
import {peerFundsFromRows} from './peer-valuation';
import {verifiedCashConversion} from './cash-conversion';
import {normalizeMarketCap} from './valuation-data';
import {applyForwardEstimate} from './fundamental-supplement';
import {financialHealth,healthProfile,healthRank,type HealthDistribution} from './financial-health';

/** One evaluation path; scoring always uses the native statement units. */
/** peerRows: Universumszeilen aus selectPeers (Einzelanalyse: /api/peers; Pipeline: dieselbe Auswahl). Ohne Peers wie bisher. */
/** riskCoverage: vorberechnete Bilanzpruefung der Risikopipeline ({balance,...}; Einzelanalyse /api/risk-coverage,
 *  Scanner cf_risk_coverage.json). Ohne sie rechnet die Bilanz-Kategorie wie bisher. */
/** healthDistribution: Rohwerte der Bilanz je Profil im Universum (Rang statt absoluter Skala). */
export function evaluateStock(input:Fund & Record<string,any>,eur:EurRate|null=null,peerRows:Record<string,unknown>[]|null=null,riskCoverage:Record<string,any>|null=null,healthDistribution:HealthDistribution|null=null){
 const fund={...input};
 // Börsenwert = Kurs × Aktienzahl (idempotent; Scanner übergibt die Ergänzungsdatei als _fundamental_supplement).
 normalizeMarketCap(fund,fund._fundamental_supplement??null,Date.now(),fund._supplement_symbol??'');
 // Scanner: Prognose-EPS wie in der Einzelanalyse nur als geprüfter Konsens (Einzelanalyse: bereits in bundleLight).
 if('_fundamental_supplement' in fund)applyForwardEstimate(fund,fund._fundamental_supplement??null,Date.now(),fund._supplement_symbol??'');
 // Mehrjaehrige Cash-Conversion aus der geprueften Historie (Pipeline: balance.cashConversion), beim Lesen erneut geprueft.
 const cc=verifiedCashConversion(fund._cash_conversion_history);
 if(cc){fund.cash_conversion=cc.value;fund.cash_conversion_source=cc.years+' Geschäftsjahre bis '+cc.periods[cc.periods.length-1].end+' (ROIC, geprüft)'+(cc.clamped?', nach oben begrenzt auf 1,5':'')+(cc.value<=0?'; freier Cashflow in Summe nicht positiv, DCF offen':'');}
 else{fund.cash_conversion=null;fund.cash_conversion_source=null;}
 const playbook=classifyPlaybook(fund);
 const peers=peerFundsFromRows(peerRows),peerArg=peers.length?peers:null;
 const nativeValue=fairValue(fund,peerArg,playbook);
 fund._fv_wert=nativeValue.fair_value;
  const scores = scoreStock(fund as never, peerArg as never, playbook);

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
  // Bilanz aus den geprueften Finanzkennzahlen des Risikoscores (Block "Finanzielle Verwundbarkeit"), alle Profile.
  const health = financialHealth(fund as Record<string, any>, riskCoverage);
  const hProfile = healthProfile(health), hRank = healthRank(health.score, hProfile, healthDistribution);
  if (hRank) scores.category_scores.health = hRank.score;
  Object.assign(scores, { _health_source: hRank ? 'risiko_rang' : health.score !== null ? 'kennzahlen_ohne_rang' : 'kennzahlen', _health_risk: health, _health_raw: health.score, _health_profile: hProfile, _health_rank_n: hRank?.n ?? null });

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
 const fv=display.currency===fund.currency?nativeValue:fairValue(display,peerArg,playbook);
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
 // Dieselben Peers fuer Szenarien und Bewertungsrisiko (szenarioMatrix), sonst passt Base nicht zum Fair Value.
 display._peer_funds=peerArg;
 return {fund:display,playbook,fv,scores,altZforHealth,kz,q,peerCount:peers.length};
}
