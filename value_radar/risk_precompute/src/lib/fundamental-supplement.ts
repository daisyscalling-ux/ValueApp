import {latestRows,period,annualUnitsPerListingUnit} from './valuation-data';
type Row=Record<string,any>;
const DAY=86400000;
const finite=(x:unknown):x is number=>typeof x==='number'&&Number.isFinite(x);
// Unit conversion only. FX rates come from the ECB file; ADR ratios only from share_basis (issuer-reviewed or the double check below).
const unitRate=(from:unknown,to:unknown):number|null=>{
 if(typeof from!=='string'||typeof to!=='string')return null;
 if(from===to)return 1;
 const units:Record<string,number>={GBP:1,GBp:0.01,GBX:0.01};
 return units[from]&&units[to]?units[from]/units[to]:null;
};
const age=(s:unknown,now:number,max:number)=>typeof s==='string'&&Number.isFinite(Date.parse(s))&&now-Date.parse(s)>=0&&now-Date.parse(s)<=max;
// ADR-Verhältnis ungleich 1:1 nur aus der doppelten Prüfung der Pipeline (Aktienzahl auf 2 %, Kurs auf 10 % am selben Standardwert).
export const DERIVED_ADR_METHOD='share_count_and_price_ratio_v1';
const STANDARD_RATIOS=[0.01,0.02,0.04,0.05,0.1,0.2,0.25,1/3,0.5,1,2,3,4,5,6,8,10,12,15,16,20,25,30,40,50,100];
// Die Pipeline speichert Verhältnisse auf 6 Nachkommastellen (1/3 = 0,333333); Toleranz deshalb 1e-5.
export function sharesPerUnit(b:Row|undefined):number|null{
 const r=b?.ordinary_shares_per_unit;
 if(r===1)return 1;
 if(b?.kind!=='ADR'||b?.method!==DERIVED_ADR_METHOD||!finite(r)||!STANDARD_RATIOS.some(x=>Math.abs(x/r-1)<1e-5))return null;
 const e=b.evidence;if(!finite(e?.byShareCount)||!finite(e?.byPrice)||Math.abs(e.byShareCount/r-1)>.02||Math.abs(e.byPrice/r-1)>.10)return null;
 return r;
}
function verifiedFxScale(s:Row,target:string,now:number):number|null{
 const fx=s.fx,b=s.share_basis,a=s.annual;
 if(!a||!b||b.symbol!==s.symbol||b.report_currency!==a.currency||b.quote_currency!==s.market?.currency||annualUnitsPerListingUnit(s)===null||!['ADR','ordinary'].includes(b.kind)||!age(b.reviewed_at,now,180*DAY)||!String(b.source_url??'').startsWith('https://'))return null;
 if(!fx||fx.base!=='EUR'||!age(fx.observed_at,now,7*DAY)||fx.source_url!=='https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml')return null;
 const baseTarget=['GBp','GBX'].includes(target)?'GBP':target;
 const from=fx.rates?.[a.currency],to=fx.rates?.[baseTarget];
 if(!finite(from)||from<=0||!finite(to)||to<=0)return null;
 const scale=to/from*(baseTarget===target?1:100);
 return Number.isFinite(scale)&&scale>0?scale:null;
}
const FINANCIAL=['eps_trailing','eps_forward','net_income','revenue','ebit','ebitda','free_cashflow','cash','total_debt','net_debt','total_assets','book_value_ps','gross_margin','operating_margin','profit_margin','roe','roic','revenue_growth','earnings_growth','net_debt_ebitda','ev_ebitda','pe_trailing','pb'];
export function applySupplement(f:Row,raw:Row,now=Date.now()):void {
 const s=raw.fundamental_supplement;
 f.data_sources=[];
 if(!s||s.schema!==1||s.symbol!==raw.resolved_symbol){f.supplement_status=raw.supplement_status??'Keine datierte Ersatzquelle verfügbar';return;}
 if(!age(s.retrieved_at,now,7*DAY)){f.supplement_status='Ersatzdaten veraltet oder ungültig datiert';return;}
 f.supplement_status=[raw.supplement_status,...(s.issues??[])].filter(Boolean).join(' · ')||'Datierte Ersatzquelle verfügbar';
 const m=s.market;
 const quoteScale=unitRate(m?.currency,f.currency);
 if(quoteScale!==null&&age(m.quote_at,now,4*DAY)&&age(s.retrieved_at,now,36*3600000)){
  // Prefer the quote with the verifiable newer observation timestamp.
  const quote=latestRows(raw.quote)[0];
  const primaryTime=quote ? period(quote) : null;
  if(finite(m.fields?.price)&&m.fields.price>0&&(primaryTime===null||Date.parse(m.quote_at)>primaryTime)){f.price=m.fields.price*quoteScale;f.price_observed_at=m.quote_at;}
  for(const key of ['shares_out','52w_high','52w_low','target_mean','analyst_count','beta']){
   if(finite(m.fields?.[key])&&m.fields[key]>0)f[key]=m.fields[key]*(['52w_high','52w_low','target_mean'].includes(key)?quoteScale:1);
  }
  if(finite(f.price)&&finite(f.shares_out))f.market_cap=f.price*f.shares_out;
  f.data_sources.push({source:m.source,url:m.source_url,observed_at:m.quote_at,retrieved_at:s.retrieved_at,basis:'Kurs/Aktienzahl/Band; Analystenziel als Anbieterbeobachtung, kein Berichtswert'});
 }
 const a=s.annual;
 if(s.latest_fiscal_end) f.provider_latest_fiscal_end=s.latest_fiscal_end;
 if(!a){f.supplement_status+=' · Kein aktueller datierter Jahresabschluss verfügbar';return;}
 const unitScale=unitRate(a.currency,f.currency);
 const annualScale=unitScale??verifiedFxScale(s,f.currency,now);
 if(annualScale===null){f.supplement_status+=` · Jahresabschluss in ${a.currency??'unbekannter Währung'}, Notierung in ${f.currency}: Währungs- und ggf. ADR-Überleitung fehlt`;return;}
 if(a.period_type!=='annual'||!age(a.end,now,460*DAY)||!age(s.annual_retrieved_at??s.retrieved_at,now,7*DAY))return;
 if(s.latest_fiscal_end&&Date.parse(s.latest_fiscal_end)-Date.parse(a.end)>35*DAY)return;
 const primary=latestRows(raw.income,true)[0];
 const primaryDate=primary?period(primary):null;
 const candidate=Date.parse(a.end);
 if(primaryDate!==null&&candidate<primaryDate)return;
 const fields:Row={...a.fields};
 if(!finite(fields.revenue)||fields.revenue<=0)return;
 for(const key of ['eps_trailing','revenue','net_income','gross_profit','ebit','ebitda','cash','total_debt','total_assets','equity','operating_cashflow','capex'])if(finite(fields[key]))fields[key]*=annualScale;
 // Gewinn je Aktie gilt je Stammaktie; je ADR-Einheit mal Verhältnis. Firmenweite Beträge bleiben, die Aktienzahl ist bereits in ADR-Einheiten.
 // Einheit des Abschlusses je ADR wird gegen die Aktienzahlen geprüft (annualUnitsPerListingUnit), nicht nur behauptet.
 const perUnit=unitScale===null?annualUnitsPerListingUnit(s)??1:1;
 const ratio=unitScale===null?sharesPerUnit(s.share_basis)??1:1;
 if(finite(fields.eps_trailing))fields.eps_trailing*=perUnit;
 // Replace a coherent annual block, not isolated numbers from different years.
 for(const k of FINANCIAL)delete f[k];
 delete f.reported_equity_fcf;
 for(const k of ['eps_trailing','net_income','revenue','ebit','ebitda','cash','total_debt','total_assets','revenue_growth'])if(finite(fields[k]))f[k]=fields[k];
 if(finite(fields.cash)&&finite(fields.total_debt))f.net_debt=fields.total_debt-fields.cash;
  if(!finite(f.net_debt)){delete f.ebitda;delete f.ebit;} // EV methods must not silently assume zero net debt.
 if(finite(fields.gross_profit))f.gross_margin=fields.gross_profit/fields.revenue;
 if(finite(fields.ebit))f.operating_margin=fields.ebit/fields.revenue;
 if(finite(fields.net_income))f.profit_margin=fields.net_income/fields.revenue;
 if(finite(fields.equity)&&fields.equity>0&&finite(fields.net_income))f.roe=fields.net_income/fields.equity;
 if(finite(fields.equity)&&finite(f.shares_out)&&f.shares_out>0)f.book_value_ps=fields.equity/f.shares_out;
 if(finite(f.net_debt)&&finite(f.ebitda)&&f.ebitda>0)f.net_debt_ebitda=f.net_debt/f.ebitda;
 if(finite(fields.operating_cashflow)&&finite(fields.capex))f.reported_equity_fcf=fields.operating_cashflow-Math.abs(fields.capex);
 // CFO-capex is not unlevered FCFF. Never insert it in the existing EV-DCF.
 f.eps_trailing_basis=finite(fields.eps_trailing)?`Jahresabschluss ${a.end} · verwässert · ${a.source}`:`Jahresabschluss ${a.end} · verwässertes EPS nicht gemeldet`;
 f.eps_trailing_comparable=finite(fields.eps_trailing);
 if(!finite(fields.eps_trailing))f.supplement_status+=' · Jahreszahlen übernommen; EPS fehlt, KGV-Modell nicht verfügbar';
 if(unitScale===null){
  f.supplement_status+=` · Umrechnung ${a.currency} → ${f.currency} zum EZB-Referenzkurs ${s.fx.observed_at}; `+(ratio===1?'Aktienbasis 1:1 geprüft':`1 ADR = ${+ratio.toFixed(4)} Stammaktien (aus Aktienzahl und Kurs abgeleitet)`+(perUnit===1?'; Abschluss bereits je ADR (Aktienzahl geprüft), EPS unverändert':''));
  f.data_sources.push({source:s.fx.source,url:s.fx.source_url,observed_at:s.fx.observed_at,basis:`Bewertungsumrechnung ${a.currency} → ${f.currency}, Faktor ${annualScale}; keine historische Neuberechnung des Abschlusses`});
  f.data_sources.push({source:'Aktienbasis · Emittent',url:s.share_basis.source_url,observed_at:s.share_basis.reviewed_at,basis:ratio===1?'1 handelbare Einheit = 1 gewöhnliche Aktie; Zuordnung zeitlich befristet geprüft':`1 ADR = ${+ratio.toFixed(4)} Stammaktien; Abschluss ${perUnit===1?'je ADR':'je Stammaktie'} (Aktienzahl geprüft); doppelt geprüft über Aktienzahl (${s.share_basis.evidence.byShareCount}) und Kurs (${s.share_basis.evidence.byPrice}) gegenüber ${s.share_basis.evidence.homeListing}`});
 }else if(annualScale!==1||quoteScale!==null&&quoteScale!==1)f.supplement_status+=' · Pfund/Pence-Einheiten abgeglichen (1 GBP = 100 Pence)';
 f.annual_supplement_applied=true;
 f.supplement_annual_end=a.end;
 // Old phase and forensic inputs cannot explain the newly selected period.
 delete f.phase_history;delete f.capital_return_period;delete f._forensik_akt;delete f._forensik_vorjahr;
 for(const key of Object.keys(f))if(key.startsWith('reihe_')||key==='umsatz_3j')delete f[key];
 f._finanzlage={};
 f.data_sources.push({source:a.source,url:a.source_url,period_end:a.end,published_at:a.published_at,retrieved_at:s.annual_retrieved_at??s.retrieved_at,basis:'Jahresabschluss; CFO − Capex separat, kein bestätigter FCFF'});
 const labels:Record<string,string>={total_debt:'Finanzschulden',cash:'Liquide Mittel',capex:'Investitionsausgaben',operating_cashflow:'Operativer Cashflow',ebit:'EBIT',ebitda:'EBITDA',gross_profit:'Bruttogewinn',net_income:'Jahresüberschuss',total_assets:'Bilanzsumme',equity:'Eigenkapital',revenue_growth:'Umsatzwachstum',weighted_shares:'Verwässerte Aktienzahl'};
 const additions=new Map<string,{source:Row,fields:string[]}>();
 for(const [key,src] of Object.entries(a.field_sources??{}) as [string,Row][]){
  if(!src||src.end!==a.end||!finite(a.fields?.[key])||!labels[key]||!String(src.source_url??'').startsWith('https://'))continue;
  const id=JSON.stringify([src.source,src.source_url,src.end]);
  if(!additions.has(id))additions.set(id,{source:src,fields:[]});
  additions.get(id)!.fields.push(labels[key]);
 }
 for(const {source,fields:provided} of additions.values())f.data_sources.push({source:source.source,url:source.source_url,period_end:source.end,published_at:source.published_at,retrieved_at:s.annual_retrieved_at??s.retrieved_at,basis:`Ergänzt und periodenabgeglichen: ${provided.join(', ')}`});
}

/**
 * Geprüfte Prognose-EPS (seit 14.11.2026, Entscheidung des Nutzers): Analystenkonsens als 12-Monats-Mix aus laufendem
 * (0y) und nächstem Geschäftsjahr (+1y), gewichtet nach Restlaufzeit des laufenden Jahres. Gilt nur, wenn
 * – der Block zur Notierung gehört und höchstens ESTIMATE_MAX_AGE_DAYS alt ist,
 * – beide Jahre mindestens FORWARD_MIN_ANALYSTS Analysten haben und das laufende Jahr noch nicht abgelaufen ist,
 * – die Währung gleich, Pfund/Pence oder per frischem EZB-Kurs überleitbar ist (ADR mit Verhältnis ≠ 1: offen),
 * – das Ergebnis höchstens Faktor FORWARD_MAX_FACTOR vom berichteten EPS abweicht (Schutz gegen bereinigte Gewinne).
 * Sonst bleibt eps_forward offen (eps_forward_status nennt den Grund); ungeprüfte Anbieterwerte und die mechanische
 * Fortschreibung werden entfernt, damit Scanner und Einzelanalyse dieselbe Prognose verwenden.
 */
export const FORWARD_METHOD='consensus_ntm_blend_v1';
export const ESTIMATE_SOURCE_METHOD='consensus_0y_1y_v1';
export const FORWARD_MIN_ANALYSTS=3, FORWARD_MAX_FACTOR=2, ESTIMATE_MAX_AGE_DAYS=7;
export function applyForwardEstimate(f:Row,s:Row|null|undefined,now=Date.now(),symbol?:string|null):void{
 const open=(reason:string)=>{delete f.eps_forward;delete f.eps_forward_estimate;f.eps_forward_source=null;f.eps_forward_method=null;f.eps_forward_status=reason;};
 const e=s?.estimates;
 if(!s||s.schema!==1||(symbol!=null&&s.symbol!==symbol))return open('Keine Konsensschätzung für diese Notierung');
 if(!e||e.method!==ESTIMATE_SOURCE_METHOD)return open('Konsensschätzung fehlt (noch nicht im geprüften Format)');
 if(!e.usable)return open('Konsensschätzung unvollständig: '+(e.reason??'ohne Grund'));
 if(!age(e.as_of,now,ESTIMATE_MAX_AGE_DAYS*DAY))return open('Konsensschätzung veraltet oder ungültig datiert');
 const p0=e.periods?.['0y'],p1=e.periods?.['+1y'];
 if(!finite(p0?.avg)||!finite(p1?.avg))return open('Konsens für laufendes oder nächstes Geschäftsjahr fehlt');
 if(!(finite(p0.analysts)&&p0.analysts>=FORWARD_MIN_ANALYSTS&&finite(p1.analysts)&&p1.analysts>=FORWARD_MIN_ANALYSTS))return open(`Weniger als ${FORWARD_MIN_ANALYSTS} Analysten je Geschäftsjahr`);
 const end0=Date.parse(p0.fiscal_end),end1=Date.parse(p1.fiscal_end);
 if(!Number.isFinite(end0)||!Number.isFinite(end1)||end1<=end0)return open('Geschäftsjahresende der Schätzung fehlt');
 if(end0<=now)return open('Laufendes Geschäftsjahr abgelaufen, Konsens noch nicht fortgeschrieben');
 const w0=Math.min(1,(end0-now)/(365*DAY));
 const ntm=w0*p0.avg+(1-w0)*p1.avg;
 const b=s.share_basis;
 if(b?.kind==='ADR'&&sharesPerUnit(b)!==1)return open('ADR: Aktienbasis der Konsensschätzung ungeklärt');
 let scale=unitRate(e.currency,f.currency);
 if(scale===null){
  const fx=s.fx,base=['GBp','GBX'].includes(f.currency)?'GBP':f.currency;
  if(!fx||fx.base!=='EUR'||!age(fx.observed_at,now,7*DAY)||fx.source_url!=='https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml')return open(`Schätzung in ${e.currency}, Notierung in ${f.currency}: kein aktueller EZB-Kurs`);
  const from=fx.rates?.[e.currency],to=fx.rates?.[base];
  if(!finite(from)||from<=0||!finite(to)||to<=0)return open(`Schätzung in ${e.currency}, Notierung in ${f.currency}: Kurs fehlt`);
  scale=to/from*(base===f.currency?1:100);
 }
 const value=ntm*scale,t=f.eps_trailing;
 if(!(finite(t)&&t>0))return open('Prognose nicht prüfbar: berichtetes EPS fehlt oder ≤ 0');
 if(!(value>0))return open('Konsens erwartet keinen Gewinn');
 if(Math.max(value/t,t/value)>FORWARD_MAX_FACTOR)return open(`Konsens weicht mehr als Faktor ${FORWARD_MAX_FACTOR} vom berichteten EPS ab (bereinigte Gewinnbasis oder Sondereffekt)`);
 f.eps_forward=value;f.eps_forward_method=FORWARD_METHOD;f.eps_forward_status=null;
 f.eps_forward_estimate={weight_0y:Math.round(w0*1000)/1000,avg_0y:p0.avg,avg_1y:p1.avg,analysts_0y:p0.analysts,analysts_1y:p1.analysts,currency:e.currency,as_of:e.as_of,fiscal_end_0y:p0.fiscal_end,source_url:e.source_url};
 f.eps_forward_source=`Analystenkonsens 12 Monate (${e.source}; ${Math.round(w0*100)} % laufendes, ${100-Math.round(w0*100)} % nächstes Geschäftsjahr; ${p0.analysts}/${p1.analysts} Analysten; Stand ${String(e.as_of).slice(0,10)})`;
}
