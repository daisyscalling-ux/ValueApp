import {classifyPlaybook,fairValue,kursziel12m,analystTarget,type Fund} from './valuation';
import {scoreStock,quantumScore} from './scoring';
import {altmanZ,type Row} from './scores';
import {scoresPlus} from './scores_plus';
import {fundInEur,type EurRate} from './currency';
import {peerFundsFromRows} from './peer-valuation';
import {verifiedCashConversion,cashConversionFromSupplement,gewinnKnick} from './cash-conversion';
import {finanzsparte} from './finanzsparte';
import {normalizeMarketCap,convertReportCurrency} from './valuation-data';
import {applyForwardEstimate,applySupplement,applyAnalystRatings,applyEarningsSurprises} from './fundamental-supplement';
import {applyValueInputs} from './value-inputs';
import {historyFromRoicRaw,HISTORY_FIELDS,ROIC_RAW_METHOD} from './roic';
import {financialHealth,healthProfile,healthRank,type HealthDistribution} from './financial-health';

/** One evaluation path; scoring always uses the native statement units. */
/** peerRows: Universumszeilen aus selectPeers (Einzelanalyse: /api/peers; Pipeline: dieselbe Auswahl). Ohne Peers wie bisher. */
/** riskCoverage: vorberechnete Bilanzpruefung der Risikopipeline ({balance,...}; Einzelanalyse /api/risk-coverage,
 *  Scanner cf_risk_coverage.json). Ohne sie rechnet die Bilanz-Kategorie wie bisher. */
/** healthDistribution: Rohwerte der Bilanz je Profil im Universum (Rang statt absoluter Skala). */
/** KGV, KBV und EV/EBITDA zum aktuellen Kurs (seit 20./21.11.2026, QA-Befunde F1/F2). Ohne übernommenen Jahresabschluss kam pe_trailing aus
 *  ROIC-multiples (pe_ratio) und war das KGV zum Geschäftsjahresende; Peer-Vergleich und Checkliste zeigten es als aktuelles
 *  KGV. Der ROIC-Wert bleibt als pe_year_end (bzw. pb_year_end) erhalten. Ohne positive Basis bleibt der ROIC-Wert und trägt
 *  pe_trailing_basis bzw. pb_basis „Geschäftsjahresende“ (das KBV ist Eingang der Bankbewertung und soll nicht wegfallen). */
export function aktuelleMultiples(f:Record<string,any>):void{
 const p=f.price,ok=(v:unknown):v is number=>typeof v==='number'&&Number.isFinite(v);
 if(!ok(p)||p<=0)return;
 for(const [m,basis,jahr] of [['pe_trailing','eps_trailing','pe_year_end'],['pb','book_value_ps','pb_year_end']] as const){
  const b=f[basis];
  if(ok(b)&&b>0){const neu=p/b;if(ok(f[m])&&Math.abs(f[m]/neu-1)>0.005&&f[jahr]===undefined)f[jahr]=f[m];f[m]=neu;}
  else if(ok(f[m]))f[m+'_basis']='Geschäftsjahresende (ROIC), kein aktueller '+(basis==='eps_trailing'?'Gewinn je Aktie':'Buchwert je Aktie');
 }
 // EV/EBITDA zum aktuellen Kurs (seit 21.11.2026, Entscheidung des Nutzers nach QA-Befund F2: 830 Titel mit ROIC-Wert zum
 // Geschäftsjahresende). Geht mit 40 % in die EV/EBITDA-Methode ein (multipleEvEbitda). ROIC-Wert bleibt als ev_ebitda_year_end.
 const mc=f.market_cap,nd=f.net_debt,eb=f.ebitda;
 if(ok(mc)&&mc>0&&ok(nd)&&ok(eb)&&eb>0){const neu=(mc+nd)/eb;if(neu>0){if(ok(f.ev_ebitda)&&Math.abs(f.ev_ebitda/neu-1)>0.005&&f.ev_ebitda_year_end===undefined)f.ev_ebitda_year_end=f.ev_ebitda;f.ev_ebitda=neu;}}
 else if(ok(f.ev_ebitda))f.ev_ebitda_basis='Geschäftsjahresende (ROIC), aktueller Wert nicht berechenbar';
}
export function evaluateStock(input:Fund & Record<string,any>,eur:EurRate|null=null,peerRows:Record<string,unknown>[]|null=null,riskCoverage:Record<string,any>|null=null,healthDistribution:HealthDistribution|null=null){
 const fund={...input};
 // Scanner (seit 17.11.2026): Historienfelder aus denselben ROIC-Rohblöcken wie bundleLight (historyFromRoicRaw), vor dem
 // Jahresblock-Schritt wie in der Einzelanalyse. Von der Pipeline mitgelieferte Werte zählen nicht; ohne gültige Blöcke
 // derselben Notierung bleiben KGV-Band, Reihen und Gewinnhistorie offen.
 if('_fundamental_supplement' in fund){
  for(const k of HISTORY_FIELDS)delete fund[k];
  const rr=fund._roic_raw;delete fund._roic_raw;
  if(rr&&typeof rr==='object'&&rr.method===ROIC_RAW_METHOD&&typeof rr.symbol==='string'&&rr.symbol===fund._supplement_symbol){Object.assign(fund,historyFromRoicRaw(rr));fund.roic_history_status=null;}
  else fund.roic_history_status=!rr?'ROIC-Mehrjahresblöcke fehlen':rr.method!==ROIC_RAW_METHOD?'ROIC-Mehrjahresblöcke in unbekanntem Format':'ROIC-Mehrjahresblöcke gehören zu einer anderen Notierung';
 }
 // Scanner: derselbe Jahresblock-Schritt wie die Einzelanalyse (bundleLight → applySupplement; Entscheidung des Nutzers
 // 16.11.2026). Der ROIC-Gewinnstichtag (income_period) entscheidet, ob der Abschluss der Ergänzungsdatei gleich alt oder neuer ist.
 if('_fundamental_supplement' in fund)applySupplement(fund,{fundamental_supplement:fund._fundamental_supplement,resolved_symbol:fund._supplement_symbol,
  income:fund.income_period?[{period_end_date:fund.income_period,period_type:'annual',currency:fund.income_currency}]:null});
 // Börsenwert = Kurs × Aktienzahl (idempotent; Scanner übergibt die Ergänzungsdatei als _fundamental_supplement).
 normalizeMarketCap(fund,fund._fundamental_supplement??null,Date.now(),fund._supplement_symbol??'');
 // Scanner: Berichtswährung umrechnen und Prognose-EPS nur als geprüfter Konsens (Einzelanalyse: bereits in bundleLight).
 if('_fundamental_supplement' in fund)convertReportCurrency(fund,fund._fundamental_supplement?.fx??null);
 if('_fundamental_supplement' in fund)applyForwardEstimate(fund,fund._fundamental_supplement??null,Date.now(),fund._supplement_symbol??'');
 // Scanner: Analystenempfehlungen aus derselben Ergänzungsdatei (Einzelanalyse: bereits in bundleLight).
 if('_fundamental_supplement' in fund)applyAnalystRatings(fund,fund._fundamental_supplement??null,Date.now(),fund._supplement_symbol??'');
 if('_fundamental_supplement' in fund)applyEarningsSurprises(fund,fund._fundamental_supplement??null,Date.now(),fund._supplement_symbol??'');
 aktuelleMultiples(fund);
 // Mehrjaehrige Cash-Conversion aus der geprueften Historie (Pipeline: balance.cashConversion), beim Lesen erneut geprueft.
 // Ersatz aus der Yahoo-Jahreshistorie derselben Ergänzungsdatei, nur wenn ROIC keine gültige Conversion liefert (gekennzeichnet).
 // Scanner: _fundamental_supplement.cash_history; Einzelanalyse: _fundamental_cash_history (bundleLight, Identität geprüft).
 const roicCc=verifiedCashConversion(fund._cash_conversion_history);
 const supCc=roicCc?null:cashConversionFromSupplement(fund._fundamental_supplement?.cash_history??fund._fundamental_cash_history);
 const cc=roicCc??(supCc?verifiedCashConversion(supCc):null);
 const origin=roicCc?'ROIC, geprüft':'Yahoo-Jahresabschlüsse, Ersatz für fehlende ROIC-Historie';
 if(cc){fund.cash_conversion=cc.value;fund.cash_conversion_origin=roicCc?'roic_history':'yahoo_annual_history';fund.cash_conversion_source=cc.years+' Geschäftsjahre bis '+cc.periods[cc.periods.length-1].end+' ('+origin+')'+(cc.clamped?', nach oben begrenzt auf 1,5':'')+(cc.value<=0?'; freier Cashflow in Summe nicht positiv, DCF offen':'');}
 else{fund.cash_conversion=null;fund.cash_conversion_source=null;fund.cash_conversion_origin=null;}
 // DCF-Sperren (seit 22.11.2026): immer hier neu bestimmt, mitgelieferte Werte zählen nicht (valuation.ts, dcfSperre).
 fund.gewinn_knick=cc&&cc.value>0?gewinnKnick(cc):null;
 fund.finanzsparte=finanzsparte(fund.isin);
 // Forward-KGV, PEG, FCF-Rendite in beiden Wegen aus denselben geprüften Feldern (seit 17.11.2026, value-inputs.ts).
 applyValueInputs(fund);
 const playbook=classifyPlaybook(fund);
 // Finanz- und Zykliker-Modell rechnen keinen DCF: fehlende Cash-Conversion ist dort kein Datenmangel (seit 16.11.2026).
 if(fund.cash_conversion==null&&(playbook==='financial'||playbook==='cyclical')){fund.cash_conversion_origin='not_required';fund.cash_conversion_source='nicht benötigt: '+(playbook==='financial'?'Finanzmodell':'Zykliker-Modell')+' ohne DCF';}
 const peers=peerFundsFromRows(peerRows),peerArg=peers.length?peers:null;
 const nativeValue=fairValue(fund,peerArg,playbook);
 fund._fv_wert=nativeValue.fair_value;
  const scores = scoreStock(fund as never, peerArg as never, playbook);
  // Für die Anzeige (Einzelanalyse rendert mit dem Original-Fund, nicht mit dieser Kopie).
  Object.assign(scores,{_value_inputs:fund.value_inputs??null});

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
 // 12M-Ziel: fundamentaler Teil Richtung Fair Value, nur wenn dieser verlässlich ist (seit 17.11.2026).
 targetFund._fv_anker={value:fv.fair_value,reliable:fv.reliable};
 // Rückfall für das historische KGV: das KGV zum letzten Geschäftsjahresende (ROIC), nicht das heutige (seit 20.11.2026).
 if(!targetFund.hist_pe_median&&targetFund.pe_year_end)targetFund.hist_pe_median=targetFund.pe_year_end;
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
