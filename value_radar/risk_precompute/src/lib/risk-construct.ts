// Risiko-Konstrukt Version 0.4: vollständige Blockstruktur mit vorläufigen, nicht kalibrierten Schwellen.
// riskScore (Version 0.3) bleibt unverändert und wird für Kurs-, Finanz- und Umfeldblock wiederverwendet.
import {riskScore,type RiskMetric} from './risk-score';
import {contextMetrics} from './risk-context';
import {reverseDcfImpliedGrowth,szenarioMatrix,type FairValueResult,type Fund} from './valuation';
import {valuationRisk} from './valuation-risk';
import {capitalRequirementPresentation} from '../risk_capital_requirement_view';
import {verifiedLiquidity,verifiedLiquidityExemption,liquiditySourceLabel} from '../holding-liquidity';
import {verifiedInsurer} from '../insurer-solvency';
import {reviewedPresentation} from '../risk_review_view';
import {euBankCapital,derivationText} from './eu-bank';
import {intlBankCapital,missingRequirementReason,CREDIT_METHODS} from './intl-bank';
import {depositaryOrigin} from './depositary';
import {domesticStandard,DOMESTIC_CAPITAL_REASON,DOMESTIC_LCR_REASON} from './domestic-standard';

type Row=Record<string,any>;
export const CONSTRUCT_VERSION='0.9';
export type Block='Kursrisiko'|'Finanzielle Verwundbarkeit'|'Umfeldstress'|'Bewertungsrisiko'|'Wettbewerbsanfälligkeit';
export type ConstructMetric=RiskMetric&{block:Block};
export const BLOCK_WEIGHTS:Record<Block,number>={'Kursrisiko':30,'Finanzielle Verwundbarkeit':25,'Umfeldstress':15,'Bewertungsrisiko':15,'Wettbewerbsanfälligkeit':15};
export const EVENT_POINTS=5,EVENT_CAP=10;
const FINANCIAL_PROFILES=['bank','insurer','specialist_financial'];
const CORPORATE_FINANCIAL=['Nettoschulden / EBITDA','Cashflow-Puffer · berichteter FCFF / Umsatz'];

const finite=(v:unknown):v is number=>typeof v==='number'&&Number.isFinite(v);
// Linear 0–100 zwischen zero (0 Punkte) und full (100 Punkte); funktioniert in beide Richtungen.
export const lin=(v:number,zero:number,full:number)=>Math.max(0,Math.min(100,100*(v-zero)/(full-zero)));
const pct=(v:number,digits=1)=>(v*100).toLocaleString('de-DE',{maximumFractionDigits:digits})+' %';
const pp=(v:number)=>(v>=0?'+':'')+v.toLocaleString('de-DE',{maximumFractionDigits:1})+' Pp.';
const metric=(block:Block,name:string,weight:number,score:number|null,value:string,reason:string):ConstructMetric=>({block,name,weight,score,value,reason});
const open=(block:Block,name:string,weight:number,reason:string)=>metric(block,name,weight,null,'—',reason);
function median(values:number[]){const s=[...values].sort((a,b)=>a-b),n=s.length;return n?(s[Math.floor(n/2)]+s[Math.floor((n-1)/2)])/2:null}

// Jahresreihe: neueste zuerst, mindestens drei aufeinanderfolgende Geschäftsjahre, eine Währung.
export function annualSeries(rows:unknown,count=3):Row[]|null{
 if(!Array.isArray(rows))return null;
 const r=rows.slice(0,count);
 if(r.length<count||!r.every(x=>finite(x?.value)&&typeof x.period==='string'&&Number.isFinite(Date.parse(x.period))))return null;
 const currencies=new Set(r.map(x=>x.currency).filter(Boolean));if(currencies.size>1)return null;
 for(let i=1;i<r.length;i++){const gap=(Date.parse(r[i-1].period)-Date.parse(r[i].period))/86400000;if(gap<300||gap>430)return null}
 return r;
}

// Banken und Versicherer: Bewertung über Buchwert und Eigenkapitalrendite statt Cashflow.
// Begründetes KBV (Gordon): KBV = (ROE − g) / (Kapitalkosten − g). Umgestellt setzt ein Kurs die Eigenkapitalrendite g + KBV × (Kapitalkosten − g) voraus.
export const FIN_COST_OF_EQUITY=.10,FIN_GROWTH=.03;
export function financialValuationMetrics(fund:Fund&Row,fv:FairValueResult|undefined):ConstructMetric[]{
 const B:Block='Bewertungsrisiko',gapName='Erwartungslücke · vorausgesetzte minus erzielte Eigenkapitalrendite',bearName='Abstand des Kurses über dem Bear-Szenario';
 const out:ConstructMetric[]=[];
 const blocked=fund.valuation_data?.blocked,price=fund.price,bvps=fund.book_value_ps,roe=fund.roe;
 const pb=finite(price)&&price>0&&finite(bvps)&&bvps>0?price/bvps:fund.pb;
 if(blocked)out.push(open(B,gapName,10,'Bewertungsdaten widersprüchlich (z. B. Berichts- und Handelswährung verschieden); siehe Datenprüfung der Bewertung.'));
 else if(!finite(pb)||pb<=.05||pb>=15)out.push(open(B,gapName,10,'Gültiges Kurs-Buchwert-Verhältnis fehlt.'));
 else if(!finite(roe)||roe<=-1||roe>=1)out.push(open(B,gapName,10,'Gültige Eigenkapitalrendite des letzten Geschäftsjahres fehlt.'));
 else{const implied=FIN_GROWTH+pb*(FIN_COST_OF_EQUITY-FIN_GROWTH),gap=implied-roe;out.push(metric(B,gapName,10,lin(gap,0,.10),pct(implied)+' vorausgesetzt (KBV '+pb.toLocaleString('de-DE',{maximumFractionDigits:2})+') · '+pct(roe)+' erzielt','Begründetes KBV mit '+pct(FIN_COST_OF_EQUITY,0)+' Kapitalkosten und '+pct(FIN_GROWTH,0)+' langfristigem Wachstum: Der Kurs setzt eine Eigenkapitalrendite von 3 % + KBV × 7 % voraus. Verglichen wird mit der Rendite des letzten Geschäftsjahres. 0 Punkte ohne Lücke, 100 Punkte ab 10 Prozentpunkten. Einheitliche Kapitalkosten (in Niedrigzinswährungen wie CHF oder JPY eher zu hoch) und bei Versicherern ein durch IFRS 17 niedrigerer Buchwert überzeichnen die Lücke: Hinweis auf hohe Erwartungen, kein Beweis.'))}
 if(!fv)out.push(open(B,bearName,5,'Fair-Value-Berechnung fehlt.'));
 else if(fv.playbook!=='financial')out.push(open(B,bearName,5,'Bewertung läuft nicht mit dem Finanzmodell (KBV, begründetes KGV, Forward-KGV).'));
 else{const r=valuationRisk(fund.price,fv,szenarioMatrix(fund,(fund as Row)._peer_funds??null,fv.playbook));
  if(r.reason||!r.values)out.push(open(B,bearName,5,r.reason||'Szenarien fehlen.'));
  else{const down=Math.max(0,1-r.values.bear/(fund.price as number));out.push(metric(B,bearName,5,lin(down,0,.6),down>0?pct(down)+' Abstand':'Kurs auf oder unter Bear','Rückgang bis zum Bear-Rechenwert des Finanzmodells (KBV, begründetes KGV, Forward-KGV; keine Cashflow-Methode). 0 Punkte auf oder unter Bear, 100 Punkte ab 60 % Abstand. Modellabstand, keine Kursprognose.'))}}
 return out;
}

// Spezialfinanzierer (Vermögensverwalter, Börsen, Holdings, Leasing): Reverse DCF auf Eigenkapitalebene.
// Jahresergebnis statt freiem Cashflow, keine Nettoschulden, Abzinsung mit den Eigenkapitalkosten (gleiche Maschine wie bei Unternehmen).
export function specialistValuationMetrics(fund:Fund&Row,fv:FairValueResult|undefined):ConstructMetric[]{
 const B:Block='Bewertungsrisiko',gapName='Erwartungslücke · vom Kurs vorausgesetztes Gewinnwachstum minus Umsatzwachstum',bearName='Abstand des Kurses über dem Bear-Szenario';
 // Vergleichswachstum: Durchschnitt über drei Geschäftsjahre, wo vorhanden (Erfolgsgebühren und Bewertungsgewinne schwanken stark), sonst letztes Jahr.
 const rev=annualSeries(fund.revenue_history),cagr=rev&&rev.every(x=>x.value>0)?Math.sqrt(rev[0].value/rev[2].value)-1:null;
 const out:ConstructMetric[]=[],ni=fund.net_income,growth=cagr??fund.revenue_growth,growthLabel=cagr!==null?' Umsatzwachstum p. a. ('+rev![2].period.slice(0,4)+'–'+rev![0].period.slice(0,4)+')':' Umsatzwachstum';
 if(fund.valuation_data?.blocked)out.push(open(B,gapName,10,'Bewertungsdaten widersprüchlich (z. B. Berichts- und Handelswährung verschieden); siehe Datenprüfung der Bewertung.'));
 else if(!finite(ni)||ni<=0)out.push(open(B,gapName,10,'Positives Jahresergebnis benötigt; bei Verlust ist kein vorausgesetztes Wachstum berechenbar.'));
 else{
  const implied=reverseDcfImpliedGrowth({...fund,free_cashflow:ni,net_debt:0,total_debt:0} as Fund);
  if(!finite(implied))out.push(open(B,gapName,10,'Reverse DCF auf Gewinnbasis liefert kein eindeutiges vorausgesetztes Wachstum.'));
  else if(!finite(growth))out.push(open(B,gapName,10,'Gültiges Umsatzwachstum fehlt.'));
  else if(Math.abs(growth)>.5)out.push(open(B,gapName,10,'Umsatzveränderung von '+pct(growth)+': bei Holdings und Vermögensverwaltern meist Bewertungs- oder Erfolgsgebühreneffekte, als Vergleich nicht aussagekräftig.'));
  else{const gap=implied-growth;out.push(metric(B,gapName,10,lin(gap,0,.15),pct(implied)+' vorausgesetzt · '+pct(growth)+growthLabel,'Reverse DCF auf Eigenkapitalebene: Jahresergebnis statt freiem Cashflow, abgezinst mit den Eigenkapitalkosten. Verglichen mit dem Umsatzwachstum über drei Geschäftsjahre (sonst des letzten Jahres); Umsatzsprünge über ±50 % bleiben offen. 0 Punkte ohne Lücke, 100 Punkte ab 15 Prozentpunkten (wie bei Unternehmen). Bewertungsgewinne von Beteiligungen und Einmaleffekte stecken im Jahresergebnis; Hinweis auf hohe Erwartungen, kein Beweis.'))}
 }
 if(!fv)out.push(open(B,bearName,5,'Fair-Value-Berechnung fehlt.'));
 else{const r=valuationRisk(fund.price,fv,szenarioMatrix(fund,(fund as Row)._peer_funds??null,fv.playbook));
  if(r.reason||!r.values)out.push(open(B,bearName,5,r.reason||'Szenarien fehlen.'));
  else{const down=Math.max(0,1-r.values.bear/(fund.price as number));out.push(metric(B,bearName,5,lin(down,0,.6),down>0?pct(down)+' Abstand':'Kurs auf oder unter Bear','Rückgang bis zum Bear-Rechenwert derselben Kernmethoden. 0 Punkte auf oder unter Bear, 100 Punkte ab 60 % Abstand. Modellabstand, keine Kursprognose.'))}}
 return out;
}

// Ersatz für die Erwartungslücke, wenn der Reverse DCF kein Wachstum liefert (freier Cashflow negativ oder fehlend):
// EV/EBITDA gegenüber dem Median der Peers aus derselben Universumsquelle. 0 Punkte ohne Aufschlag, 100 Punkte ab +100 %.
export const EV_EBITDA_FALLBACK='Bewertung gegenüber Peers · EV/EBITDA (Ersatz ohne positiven Cashflow)';
export function evEbitdaFallback(reference:Row|null,peerRows:Row[],why:string):ConstructMetric{
 const B:Block='Bewertungsrisiko',own=reference?.ev_ebitda,symbol=String(reference?.listing_symbol||reference?.ticker||'');
 const peers=peerRows.filter(p=>String(p.listing_symbol||p.ticker||'')!==symbol).map(p=>p.ev_ebitda).filter((x:unknown):x is number=>finite(x)&&x>0);
 const med=median(peers);
 if(!finite(own)||own<=0)return open(B,EV_EBITDA_FALLBACK,10,why+' Ersatz über EV/EBITDA nicht möglich: eigenes EV/EBITDA fehlt oder EBITDA negativ.');
 if(peers.length<3||med===null)return open(B,EV_EBITDA_FALLBACK,10,why+' Ersatz über EV/EBITDA braucht mindestens drei Peers mit positivem EV/EBITDA ('+peers.length+' verfügbar).');
 const premium=own/med-1;
 return metric(B,EV_EBITDA_FALLBACK,10,lin(premium,0,1),own.toLocaleString('de-DE',{maximumFractionDigits:1})+'× vs. Median '+med.toLocaleString('de-DE',{maximumFractionDigits:1})+'× ('+(premium>=0?'+':'')+pct(premium,0)+', '+peers.length+' Peers)',
  why+' Ersatzweise: Aufschlag des EV/EBITDA auf den Median der Peers (gleiche Universumsquelle). 0 Punkte ohne Aufschlag, 100 Punkte ab +100 %. Relative Bewertung, keine absolute Aussage; Peer-Auswahl ist keine bestätigte Wettbewerberliste.');
}
export function valuationMetrics(fund:Fund&Row,fv:FairValueResult|undefined,profile:string|null,reference:Row|null=null,peerRows:Row[]=[]):ConstructMetric[]{
 const B:Block='Bewertungsrisiko',gapName='Erwartungslücke · vorausgesetztes Wachstum minus Umsatzwachstum',bearName='Abstand des Kurses über dem Bear-Szenario';
 if(profile==='bank'||profile==='insurer')return financialValuationMetrics(fund,fv);
 if(profile==='specialist_financial')return specialistValuationMetrics(fund,fv);
 const noFcf=!(finite(fund.free_cashflow)&&fund.free_cashflow>0),fallbackWhy='Freier Cashflow negativ oder nicht berichtet, Reverse DCF nicht anwendbar.';
 if(!fv)return [noFcf?evEbitdaFallback(reference,peerRows,fallbackWhy):open(B,gapName,10,'Fair-Value-Berechnung fehlt.'),open(B,bearName,5,'Fair-Value-Berechnung fehlt.')];
 const out:ConstructMetric[]=[];
 const implied=reverseDcfImpliedGrowth(fund),growth=fund.revenue_growth;
 if(!finite(implied))out.push(noFcf?evEbitdaFallback(reference,peerRows,fallbackWhy):open(B,gapName,10,'Reverse DCF liefert kein eindeutiges vorausgesetztes Wachstum.'));
 else if(!finite(growth)||growth<=-0.9||growth>=5)out.push(open(B,gapName,10,'Gültiges Umsatzwachstum des letzten Geschäftsjahres fehlt.'));
 else{const gap=implied-growth;out.push(metric(B,gapName,10,lin(gap,0,.15),pct(implied)+' vorausgesetzt · '+pct(growth)+' Umsatzwachstum','Reverse DCF (Cashflow-Wachstum) gegen Umsatzwachstum des letzten Geschäftsjahres. 0 Punkte ohne Lücke, 100 Punkte ab 15 Prozentpunkten. Verschiedene Größen: Hinweis auf hohe Erwartungen, kein Beweis.'))}
 const r=valuationRisk(fund.price,fv,szenarioMatrix(fund,(fund as Row)._peer_funds??null,fv.playbook));
 if(r.reason||!r.values)out.push(open(B,bearName,5,r.reason||'Szenarien fehlen.'));
 else{const down=Math.max(0,1-r.values.bear/(fund.price as number));out.push(metric(B,bearName,5,lin(down,0,.6),down>0?pct(down)+' Abstand':'Kurs auf oder unter Bear','Rückgang bis zum Bear-Rechenwert derselben Kernmethoden. 0 Punkte auf oder unter Bear, 100 Punkte ab 60 % Abstand. Modellabstand, keine Kursprognose.'))}
 return out;
}

// EBITDA-Marge des Universums: ROIC-TTM oder gekennzeichneter Ersatz aus dem Jahresabschluss (ebitda_margin_source).
// Ein Ersatz zählt nur mit bekannter Methode und Stichtag <= 460 Tage; sonst gilt die Marge als fehlend.
export const EBITDA_MARGIN_FALLBACK='annual_statement_ebitda_over_revenue_v1';
export function margin(r:Row|null|undefined,now=Date.now()):number|null{
 const v=r?.ebitda_margin;if(!finite(v))return null;const src=r?.ebitda_margin_source;if(src==null)return v;
 const age=(now-Date.parse(src?.end))/86400000;
 return src?.method===EBITDA_MARGIN_FALLBACK&&typeof src.end==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(src.end)&&age>=0&&age<=460&&Math.abs(v)<=100?v:null;
}
export function competitionMetrics(fund:Row,reference:Row|null,peerRows:Row[],profile:string|null):ConstructMetric[]{
 const B:Block='Wettbewerbsanfälligkeit',gmName='Bruttomargen-Trend · drei Geschäftsjahre',peerName='EBITDA-Marge gegenüber Peer-Median',revName='Umsatzentwicklung · schwächstes der letzten zwei Jahre';
 const out:ConstructMetric[]=[],financial=!!profile&&FINANCIAL_PROFILES.includes(profile);
 const gm=annualSeries(fund.gross_margin_history);
 if(financial)out.push(open(B,gmName,5,'Bruttomarge ist für Finanzunternehmen nicht definiert.'));
 else if(!gm)out.push(open(B,gmName,5,'Drei aufeinanderfolgende Geschäftsjahre mit Bruttogewinn und Umsatz in einer Währung benötigt.'));
 else{const change=gm[0].value-gm[2].value;out.push(metric(B,gmName,5,lin(change,0,-.05),pp(change*100)+' ('+gm[2].period.slice(0,4)+'–'+gm[0].period.slice(0,4)+')','Veränderung der Bruttomarge über drei Geschäftsjahre. 0 Punkte ohne Rückgang, 100 Punkte ab 5 Prozentpunkten Rückgang. Kann auch Produktmix oder Einmaleffekte zeigen.'))}
 const own=margin(reference),symbol=String(reference?.listing_symbol||reference?.ticker||'');
 const peerList=peerRows.filter(p=>String(p.listing_symbol||p.ticker||'')!==symbol);
 const peers=peerList.map(p=>margin(p)).filter(finite);
 const substituted=[reference,...peerList].filter(r=>finite(margin(r))&&r?.ebitda_margin_source).length;
 const note=substituted?' Ersatz bei '+substituted+' Wert'+(substituted>1?'en':'')+': EBITDA / Umsatz aus dem Jahresabschluss, weil ROIC keine TTM-Marge liefert (Stichtag je Wert im Universum).':'';
 const med=median(peers);
 if(financial)out.push(open(B,peerName,5,'EBITDA-Marge ist für Finanzunternehmen nicht aussagekräftig.'));
 else if(!finite(own)||peers.length<3||med===null)out.push(open(B,peerName,5,'Eigene EBITDA-Marge und mindestens drei Peers aus dem Universum benötigt ('+peers.length+' verfügbar).'));
 else{const diff=med-own;out.push(metric(B,peerName,5,lin(diff,0,15),own.toLocaleString('de-DE',{maximumFractionDigits:1})+' % vs. Median '+med.toLocaleString('de-DE',{maximumFractionDigits:1})+' % ('+peers.length+' Peers)','Universumswerte für Unternehmen und Peers aus derselben Quelle. 0 Punkte ab Median, 100 Punkte bei 15 Prozentpunkten darunter. Peer-Auswahl ist keine bestätigte Wettbewerberliste.'+note))}
 const rev=annualSeries(fund.revenue_history);
 if(!rev||!rev.every(x=>x.value>0))out.push(open(B,revName,5,'Drei aufeinanderfolgende Geschäftsjahre mit positivem Umsatz in einer Währung benötigt.'));
 else{const g=[rev[0].value/rev[1].value-1,rev[1].value/rev[2].value-1],worst=Math.min(...g);out.push(metric(B,revName,5,lin(worst,0,-.2),pct(worst)+' (schwächstes Jahr)','Schwächere der beiden letzten Jahresveränderungen. 0 Punkte ohne Rückgang, 100 Punkte ab 20 % Rückgang. Übernahmen und Verkäufe können die Reihe verzerren.'))}
 return out;
}

// Vergleichbare Gruppen-Solvenzquote (Eigenmittel / SCR) gibt es nur unter Solvency II (EWR) und Solvency UK.
// Andere Systeme (US-RBC je Einzelgesellschaft, japanische Solvenzmarge/ESR, Schweizer SST, Bermuda-BSCR, Hongkong-GWS)
// werden bewusst nicht verglichen (Entscheidung 11.11.2026). Spiegel: SOLVENCY_COUNTRIES in risk_construct_coverage.py.
export const SOLVENCY_COUNTRIES=['AT','BE','BG','HR','CY','CZ','DK','EE','FI','FR','DE','GR','HU','IS','IE','IT','LV','LI','LT','LU','MT','NL','NO','PL','PT','RO','SK','SI','ES','SE','GB'];
// Gepruefte Ausnahmen: Sitzland im EWR/UK, Gruppenaufsicht ausserhalb.
export const SOLVENCY_EXCEPTIONS:Record<string,{regime:string;source:string}>={
 'GB0007099541':{regime:'Hongkong GWS (Insurance Authority als Gruppenaufsicht)',source:'https://www.prudentialplc.com/content/dam/prudential-plc/newsroom/company-news/2026/HY26_Additional_financial_information_26.08.2026.pdf'}
};
export function insurerSolvencyScope(fund:Row):{comparable:boolean;reason:string}{
 const isin=String(fund?.isin??'').toUpperCase();
 if(!/^[A-Z]{2}[A-Z0-9]{9}[0-9]$/.test(isin))return {comparable:true,reason:''};
 const ex=SOLVENCY_EXCEPTIONS[isin];
 if(ex)return {comparable:false,reason:'Kein vergleichbares Gruppen-Solvenzsystem: '+ex.regime+'. Kennzahl bewusst nicht geführt.'};
 const cc=isin.slice(0,2);
 return SOLVENCY_COUNTRIES.includes(cc)?{comparable:true,reason:''}:{comparable:false,reason:'Kein vergleichbares Gruppen-Solvenzsystem (Sitzland '+cc+'; z. B. US-RBC je Einzelgesellschaft, japanische Solvenzmarge, Schweizer SST). Kennzahl bewusst nicht geführt.'};
}
export function sectorFinancialMetrics(coverage:Row|null,profile:string,now:number,fund?:Row):ConstructMetric[]{
 const B:Block='Finanzielle Verwundbarkeit',c=coverage?.balance?.bankCapital;
 if(profile==='bank'&&c?.scope==='eu_prudential_group'){
  // EU/EWR: EBA-Daten bis 24 Monate (Nutzerentscheidung). Teilanforderung ohne Systempuffer -> Skala um 2 Prozentpunkte verschoben.
  const eu=euBankCapital(c,now),age=eu?' · Stichtag '+eu.period:'';
  const r=eu?.requirement,at=(d:string)=>' · Stichtag '+d;
  return [
   r?.kind==='full'?metric(B,'Kernkapital-Puffer über der Anforderung (CET1, EU)',10,lin(r.headroom,4,0),pp(r.headroom)+at(r.period),'CET1-Quote minus vollständige CET1-Anforderung laut Säule-3-Offenlegung (EU KM1, EBA Pillar 3 Data Hub): 4,5 % Mindestquote, CET1-Anteil der SREP-Zusatzanforderung und kombinierte Kapitalpuffer (inkl. antizyklischer, Systemrisiko- und O-SII/G-SII-Puffer)'+(r.derivation?'; '+derivationText(r.derivation):'')+'. Gleiche Skala wie bei den übrigen Banken: 0 Punkte ab 4 Prozentpunkten Puffer, 100 Punkte bei keinem Puffer.')
   :r?.kind==='partial'?metric(B,'Kernkapital-Puffer über der Teilanforderung (CET1, EU)',10,lin(r.headroom,6,2),pp(r.headroom)+age,'EBA-CET1-Quote minus 4,5 % Mindestquote, 2,5 % Kapitalerhaltungspuffer und 56,25 % der EZB-P2R '+r.p2rYear+'. Antizyklische, systemische und O-SII/G-SII-Puffer (typisch 1–3 Prozentpunkte) fehlen; deshalb 0 Punkte erst ab 6 und 100 Punkte bei 2 Prozentpunkten.')
    :open(B,'Kernkapital-Puffer über der Anforderung (CET1, EU)',10,eu?'Keine geprüfte Säule-3-Anforderung und keine EZB-P2R (z. B. gerundet gemeldete Werte). CET1-Quote '+pct(eu.cet1)+age+'.':'Geprüfte EBA-Kapitaldaten fehlen oder sind älter als 24 Monate.'),
   eu?.lcr?metric(B,'Liquiditätsdeckung (LCR)',7.5,lin(eu.lcr.value,1.3,1),pct(eu.lcr.value,0)+at(eu.lcr.period),'Konzern-LCR laut Säule-3-Offenlegung (EU KM1 Zeile 17, EBA Pillar 3 Data Hub). 0 Punkte ab 130 %, 100 Punkte bei der Mindestquote 100 %.')
    :open(B,'Liquiditätsdeckung (LCR)',7.5,'Keine geprüfte Säule-3-LCR (EBA Pillar 3 Data Hub) zu dieser Bank.'),
   eu?.npl!=null?metric(B,'Notleidende Kredite (NPL-Quote, EBA)',7.5,lin(eu.npl,.01,.05),pct(eu.npl,2)+(eu.nplSource?.kind==='cr1'?at(eu.nplSource.period):age),(eu.nplSource?.kind==='cr1'?'Säule 3, EU CR1 (EBA Pillar 3 Data Hub): notleidende / gesamte Kredite und Darlehen, brutto. ':'')+'Notleidende / gesamte Kredite und Darlehen nach EBA-Definition (breiter als die US-Kennzahl). 0 Punkte bis 1 %, 100 Punkte ab 5 %.')
    :open(B,'Notleidende Kredite (NPL-Quote, EBA)',7.5,eu?.capitalSource==='eba_p3dh_km1'?'Bank nicht in der EBA-Transparenzübung und keine aktuelle Säule-3-Tabelle EU CR1 im Hub.':'Geprüfte EBA-Kreditqualität fehlt oder ist älter als 24 Monate.'),
  ];
 }
 if(profile==='bank'&&c?.scope==='domestic_capital_standard'){
  // Japanischer Inlandsstandard: Kapitalpuffer und LCR bewusst nicht verglichen (Beleg je Bank), Kreditqualität bleibt anwendbar.
  const d=domesticStandard(c,now),src=d?' Beleg: '+d.sourceDetail+' (Stichtag '+d.period+').':'';
  return [
   open(B,'Kernkapital-Puffer über der offengelegten Anforderung (CET1)',10,d?DOMESTIC_CAPITAL_REASON+(d.domesticRatio!=null?' Gemeldete Quote nach Inlandsstandard '+pct(d.domesticRatio,2)+'.':'')+src:'Geprüfte Konzernkennzahlen fehlen oder der Beleg ist älter als 270 Tage.'),
   open(B,'Liquiditätsdeckung (LCR)',7.5,d?DOMESTIC_LCR_REASON+' Fundstelle: '+d.lcrRuleDetail+'.':'Geprüfte Konzern-LCR fehlt.'),
   open(B,'Ausgefallene Kredite (Basel CR1)',7.5,'Keine geprüfte Kreditqualität (CR1) zu dieser Bank.'),
  ];
 }
 if(profile==='bank'&&c?.scope==='basel_key_metrics'){
  // Außerhalb EU/USA: veröffentlichte Konzernkennzahlen (APRA, KM1, Bankberichte). Höchstalter 270 Tage.
  const x=intlBankCapital(c,now),at=x?' · Stichtag '+x.period:'';
  return [
   x?.requirement?metric(B,'Kernkapital-Puffer über der offengelegten Anforderung (CET1)',10,lin(x.requirement.headroom,4,0),pp(x.requirement.headroom)+at,'Gemeldete CET1-Quote minus Mindestquote, Kapitalpuffer und veröffentlichte Aufschläge laut '+x.source+' (UK mit Säule 2A, Kanada mit Domestic Stability Buffer, China und Singapur mit nationaler Mindestquote). Vergleichbar mit der Fed-Anforderung der US-Banken, daher dieselbe Skala: 0 Punkte ab 4 Prozentpunkten, 100 Punkte bei keinem Puffer.')
    :open(B,'Kernkapital-Puffer über der offengelegten Anforderung (CET1)',10,x?missingRequirementReason(x)+' CET1-Quote '+pct(x.cet1)+at+'.':'Geprüfte Konzernkennzahlen fehlen oder sind älter als 270 Tage.'),
   x?.lcr!=null?metric(B,'Liquiditätsdeckung (LCR)',7.5,lin(x.lcr,1.3,1),pct(x.lcr,0)+at,'Konzern-LCR laut '+x.source+'. 0 Punkte ab 130 %, 100 Punkte bei der Mindestquote 100 %.'):open(B,'Liquiditätsdeckung (LCR)',7.5,'Geprüfte Konzern-LCR fehlt.'),
   x?.defaulted!=null?metric(B,CREDIT_METHODS[x.credit?.method||'basel-cr1-default-v1'].label,7.5,lin(x.defaulted,.01,.05),pct(x.defaulted,2)+' · Stichtag '+(x.credit?.period||x.period),CREDIT_METHODS[x.credit?.method||'basel-cr1-default-v1'].definition+' Ähnlich breit wie die EBA-NPL-Quote, daher dieselbe Skala: 0 Punkte bis 1 %, 100 Punkte ab 5 %.'+(x.credit?.separate?' Eigener Stichtag '+x.credit.period+': Die Bank veröffentlicht CR1 nur im Jahres- bzw. Halbjahresbericht; die Kapitalquoten stammen vom '+x.period+'. Fundstelle: '+x.credit.sourceDetail+'.':''))
    :open(B,'Ausgefallene Kredite (Basel CR1)',7.5,'Keine CR1-Angabe zu diesem Stichtag in der Quelle.'),
  ];
 }
 if(profile==='bank'){
  const cap=c?.state==='available'?capitalRequirementPresentation(c,now):null;
  const liq=c?.state==='available'?verifiedLiquidity(c.liquidity,c,now):null;
  const lcrExempt=!liq&&c?.state==='available'?verifiedLiquidityExemption(c.liquidityExemption,c,now):null;
  const credit=reviewedPresentation(coverage,now)?.credit;
  return [
   cap?metric(B,'Kernkapital-Puffer über der Anforderung (CET1)',10,lin(cap.headroomPercentagePoints,4,0),pp(cap.headroomPercentagePoints),'Gemeldete CET1-Quote minus geltende Fed-Anforderung. 0 Punkte ab 4 Prozentpunkten Puffer, 100 Punkte bei keinem Puffer.'):open(B,'Kernkapital-Puffer über der Anforderung (CET1)',10,'Geprüfte Kapitalquote und Anforderung fehlen oder sind abgelaufen.'),
   liq?metric(B,'Liquiditätsdeckung (LCR)',7.5,lin(liq.reportedRatio,1.3,1),pct(liq.reportedRatio,0),'Geprüfte Konzern-LCR im Quartalsdurchschnitt, Quelle: '+liquiditySourceLabel(liq)+'.'+(liq.basis==='ratio_only'?' Quote laut Quartalsbericht (10-Q); HQLA und Nettoabflüsse dort nicht vollständig berichtet, daher ohne Gegenprüfung der Beträge.':'')+' 0 Punkte ab 130 %, 100 Punkte bei der Mindestquote 100 %.'):open(B,'Liquiditätsdeckung (LCR)',7.5,lcrExempt?'Keine LCR-Pflicht: US-Bankkonzern der Kategorie IV mit weniger als 50 Mrd. USD kurzfristiger Großkundenfinanzierung (belegt im SEC-Bericht). Kennzahl bewusst nicht geführt.':'Geprüfte Konzern-LCR fehlt oder ist abgelaufen.'),
   credit?metric(B,'Auffällige Kredite / Gesamtkredite',7.5,lin(credit.ratio,.005,.03),pct(credit.ratio,2),'Kredite ohne Zinsvereinnahmung oder mindestens 90 Tage überfällig. 0 Punkte bis 0,5 %, 100 Punkte ab 3 %. Kein erwarteter Kreditausfall.'):open(B,'Auffällige Kredite / Gesamtkredite',7.5,'Geprüfte Kreditqualität fehlt oder ist abgelaufen.'),
  ];
 }
 if(profile==='insurer'){
  const r=verifiedInsurer(coverage?.balance?.insurerSolvency,now) as Row|null,ratio=r?.primary?.ratio;
  return [
   finite(ratio)?metric(B,'Solvenzquote (Solvency II)',15,lin(ratio,2,1),pct(ratio,0)+' · '+r!.framework+' · Stichtag '+r!.primary.period,'Geprüfte Gruppen-Solvenzquote (Solvency II in EU/EWR, Solvency UK in Großbritannien; gleiche Definition: Eigenmittel / Solvenzkapitalanforderung).'+(r!.primary.amountsVerified?'':' Der Bericht nennt nur die Quote, nicht die Beträge.')+' 0 Punkte ab 200 %, 100 Punkte bei der Mindestanforderung 100 %.'):open(B,'Solvenzquote (Solvency II)',15,insurerSolvencyScope(fund??{}).comparable?'Geprüfte Solvenzquote fehlt oder ist abgelaufen.':insurerSolvencyScope(fund??{}).reason),
   open(B,'Reserve- und Kapitalanlagerisiko',10,'Für Versicherer noch nicht umgesetzt.'),
  ];
 }
 return specialistFinancialMetrics(fund??{});
}

// Spezialfinanzierer ohne geprüfte Bankkapitaldaten (Vermögensverwalter, Holdings, Leasing, Börsen, Broker, Zahlungsnetzwerke).
// Verschuldung nur bei Bilanzen mit mindestens 10 % Eigenkapital: darunter stecken Kunden-, Clearing- oder Bankvermögen in der Bilanz.
export const SPECIALIST_MIN_EQUITY_RATIO=.10;
export function specialistFinancialMetrics(fund:Row):ConstructMetric[]{
 const B:Block='Finanzielle Verwundbarkeit',levName='Verschuldung · Nettofinanzschulden / Eigenkapital',roeName='Ertragskraft · Eigenkapitalrendite';
 const out:ConstructMetric[]=[],blocked=fund.valuation_data?.blocked;
 const equity=finite(fund.book_value_ps)&&finite(fund.shares_out)&&fund.book_value_ps>0&&fund.shares_out>0?fund.book_value_ps*fund.shares_out:finite(fund.market_cap)&&finite(fund.pb)&&fund.pb>0?fund.market_cap/fund.pb:null;
 const ratio=equity!==null&&finite(fund.total_assets)&&fund.total_assets>0?equity/fund.total_assets:null;
 if(blocked)out.push(open(B,levName,15,'Bilanzdaten widersprüchlich (z. B. Berichts- und Handelswährung verschieden); siehe Datenprüfung der Bewertung.'));
 else if(equity===null||!finite(fund.net_debt))out.push(open(B,levName,15,'Eigenkapital und Nettofinanzschulden aus demselben Abschluss benötigt.'));
 else if(ratio===null)out.push(open(B,levName,15,'Bilanzsumme fehlt; Bilanzstruktur nicht prüfbar.'));
 else if(ratio<SPECIALIST_MIN_EQUITY_RATIO)out.push(open(B,levName,15,'Eigenkapital nur '+pct(ratio)+' der Bilanzsumme: Die Bilanz enthält Kunden-, Clearing- oder Bankvermögen. Verschuldungskennzahl nicht aussagekräftig; dafür wären geprüfte Kapitalquoten nötig.'));
 else{const x=fund.net_debt/equity;out.push(metric(B,levName,15,lin(x,.5,3),x.toLocaleString('de-DE',{maximumFractionDigits:2})+'× (Eigenkapital '+pct(ratio,0)+' der Bilanz)','Finanzschulden minus Kasse im Verhältnis zum bilanziellen Eigenkapital. 0 Punkte bis 0,5×, 100 Punkte ab 3×; Netto-Kasse zählt 0. Leasing- und Konsumkreditgeschäft ist naturgemäß fremdfinanziert, Beteiligungsholdings können stille Reserven haben.'))}
 const roe=fund.roe;
 if(!finite(roe)||roe<=-1||roe>=2)out.push(open(B,roeName,10,'Gültige Eigenkapitalrendite des letzten Geschäftsjahres fehlt.'));
 else out.push(metric(B,roeName,10,lin(roe,.12,0),pct(roe),'Jahresergebnis / Eigenkapital des letzten Geschäftsjahres. 0 Punkte ab 12 %, 100 Punkte bei 0 % oder Verlust. Ein Jahr; Bewertungsgewinne von Beteiligungen können schwanken.'));
 return out;
}

const CONTEXT_BLOCK:Record<string,Block>={'Marktumfeld · Abstand zum Jahreshoch':'Umfeldstress','Peer-Stress · mittlerer Abstand zum Jahreshoch':'Umfeldstress','Nettoschulden / EBITDA':'Finanzielle Verwundbarkeit','Cashflow-Puffer · berichteter FCFF / Umsatz':'Finanzielle Verwundbarkeit'};

// Vorzugsaktien liegen bewusst ausserhalb des Modells (Nutzerentscheidung 10.11.2026): fester Dividendenanspruch und Rang vor
// Stammaktien machen sie anleiheaehnlich; Kurs-, Bewertungs- und Wettbewerbsbloecke sind fuer Stammaktien gebaut.
// Erkennung wie in der Notierungsreparatur der Pipeline (Ticker BAC-PB) oder ueber die Wertpapierart.
export function preferredInstrument(r:Row):boolean{
 const t=String(r.ticker??r.symbol??'').trim().toUpperCase().split(':').pop()!;
 return /^[A-Z]+-P[A-Z]+$/.test(t)||/^[A-Z]+\.PR[A-Z]$/.test(t)||/preferred|preference/i.test(String(r.security_type??''));
}
export function profileCorrection(balance:Row|null|undefined,fund:Row,now:number):{valid:boolean;note:string|null}{
 const src=balance?.profileSource;if(!src)return {valid:true,note:null};
 const today=new Date(now).toISOString().slice(0,10),date=(v:any)=>typeof v==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(v);
 const industry=(v:any)=>String(v??'').trim().toLowerCase();
 const ok=src.kind==='reviewed_isin_override'&&['bank','insurer','specialist_financial'].includes(src.profile)&&src.profile===balance?.profile&&date(src.reviewedOn)&&date(src.reviewExpires)&&src.reviewedOn<=today&&src.reviewExpires>=today
  &&/^https:\/\//.test(String(src.evidenceUrl??''))&&/^[0-9a-f]{64}$/.test(String(src.evidenceSha256??''))&&(!fund?.industry||industry(fund.industry)===industry(src.vendorIndustry));
 const label:Record<string,string>={bank:'Bank',insurer:'Versicherer',specialist_financial:'spezialisiertes Finanzunternehmen'};
 return ok?{valid:true,note:'Profil korrigiert: Der Datenanbieter führt das Unternehmen als „'+src.vendorIndustry+'“. Nach geprüfter Quelle ('+String(src.issuer??'Emittent')+', geprüft '+src.reviewedOn+', gültig bis '+src.reviewExpires+') wird es als '+label[src.profile]+' bewertet.'}
  :{valid:false,note:'Profilkorrektur abgelaufen oder ungültig: Sektorprofil bleibt offen, bis die Prüfung erneuert ist.'};
}
export const FCFF_METRIC='Cashflow-Puffer · berichteter FCFF / Umsatz';
// Jahres-FCF / Umsatz aus dem datierten Abschluss der Pipeline (balance.supplementalMetrics.fcfRevenue), erneut geprueft:
// Zustand, Wertebereich, Abschluss hoechstens 550 Tage alt, alle drei Felder aus demselben Abschluss.
export function fcfSubstitute(balance:Row|null|undefined,now:number):{value:number;period:string;note:string}|null{
 const m=balance?.supplementalMetrics?.fcfRevenue,b=m?.basis,fields=b?.fields||{};
 if(m?.state!=='available'||typeof m.value!=='number'||!Number.isFinite(m.value)||m.value<-5||m.value>5)return null;
 const period=String(b?.period||''),age=(now-Date.parse(period))/86400000;
 if(!/^\d{4}-\d{2}-\d{2}$/.test(period)||!Number.isFinite(age)||age<0||age>550)return null;
 if(!['operating_cashflow','capex','revenue'].every(k=>fields[k]&&String(fields[k].end||period)===period))return null;
 const source=String(fields.revenue?.source||'Jahresabschluss');
 return {value:m.value,period,note:'Ersatz: ROIC liefert keinen FCFF. Jahres-FCF (operativer Cashflow minus Investitionen) / Umsatz aus dem Abschluss zum '+period+' ('+source+'). Ohne Zinsbereinigung, daher bei verschuldeten Firmen eher niedriger als FCFF. Gleiche Skala: 0 Punkte ab +15 %, 100 Punkte bei −10 %.'};
}
export type ConstructInput={history:Row|null;fund:Row;now?:number;market?:Row|null;peerHistories?:Row[];coverage?:Row|null;valuation?:FairValueResult;reference?:Row|null;peerRows?:Row[]};
export function riskConstruct(input:ConstructInput){
 const now=input.now??Date.now(),fund=input.fund,coverage=input.coverage??null;
 const context=contextMetrics(input.market??null,input.peerHistories??[],now),base=riskScore(input.history,fund,now,context),legacy=riskScore(input.history,fund,now,context,'v0.3');
 // Spezialfinanzierer mit geprüften Bankkapitaldaten (z. B. US-Holdings nach FR Y-9C) sind Bankkonzerne und werden wie Banken bewertet.
 // Gepruefte Profilkorrektur der Pipeline (reviewed-profile-overrides.json): beim Lesen erneut pruefen, sonst kein Profil uebernehmen.
 const correction=profileCorrection(coverage?.balance,fund,now);
 const sourceProfile:string|null=correction.valid?coverage?.balance?.profile??null:null,bankLike=sourceProfile==='specialist_financial'&&coverage?.balance?.bankCapital?.state==='available';
 const profile:string|null=bankLike?'bank':sourceProfile,financial=!!profile&&FINANCIAL_PROFILES.includes(profile);
 const bankCoverage=bankLike?{...coverage,balance:{...coverage!.balance,profile:'bank'}}:coverage;
 let metrics:ConstructMetric[]=base.metrics.map(m=>({...m,block:CONTEXT_BLOCK[m.name]??'Kursrisiko'}));
 // Ersatz fuer die FCFF-Marge, nur wenn ROIC keinen Wert liefert (Entscheidung 11.11.2026).
 const fcf=!financial&&profile==='corporate'?fcfSubstitute(coverage?.balance,now):null;
 if(fcf)metrics=metrics.map(m=>m.name===FCFF_METRIC&&m.score===null?{...m,score:lin(fcf.value,.15,-.10),value:pct(fcf.value),reason:fcf.note}:m);
 if(financial)metrics=[...metrics.filter(m=>!CORPORATE_FINANCIAL.includes(m.name)),...sectorFinancialMetrics(bankCoverage,profile!,now,fund)];
 metrics=[...metrics,...valuationMetrics(fund as Fund&Row,input.valuation,profile,input.reference??null,input.peerRows??[]),...competitionMetrics(fund,input.reference??null,input.peerRows??[],profile)];
 const order=Object.keys(BLOCK_WEIGHTS);metrics.sort((a,b)=>order.indexOf(a.block)-order.indexOf(b.block));
 const available=metrics.filter(m=>m.score!==null),coverageWeight=Math.round(available.reduce((s,m)=>s+m.weight,0)*10)/10;
 const baseScore=coverageWeight?Math.round(available.reduce((s,m)=>s+m.weight*m.score!,0)/available.reduce((s,m)=>s+m.weight,0)):null;
 const events=(reviewedPresentation(coverage,now)?.events??[]).filter((e:Row)=>e.state==='confirmed_event');
 const surcharge=baseScore===null?0:Math.min(EVENT_CAP,events.length*EVENT_POINTS);
 const blocks=order.map(b=>{const ms=metrics.filter(m=>m.block===b),av=ms.filter(m=>m.score!==null),w=av.reduce((s,m)=>s+m.weight,0);return {block:b as Block,weight:BLOCK_WEIGHTS[b as Block],filled:Math.round(w*10)/10,score:w?Math.round(av.reduce((s,m)=>s+m.weight*m.score!,0)/w):null}});
 return {
  version:CONSTRUCT_VERSION,profile,sourceProfile,bankLike,metrics,blocks,
  partialScore:baseScore===null?null:Math.min(100,baseScore+surcharge),baseScore,surcharge,events,
  coverage:coverageWeight,period:base.period,observations:base.observations,financialAsOf:base.financialAsOf,
  legacy:{version:'0.3',score:legacy.partialScore,coverage:legacy.coverage},
  notes:['Version '+CONSTRUCT_VERSION+' · vollständiges Konstrukt mit fünf Blöcken. Kursblock anhand historischer Verluste ausgewählt; übrige Schwellen vorläufig und nicht historisch kalibriert.','Bestätigte Ereignisse: +'+EVENT_POINTS+' Punkte je geprüftem, nicht abgelaufenem Ereignis, höchstens +'+EVENT_CAP+'.','Teilscore ist keine Verlustwahrscheinlichkeit und kein Kauf-/Verkaufssignal.',...(correction.note?[correction.note]:[]),...((d=>d?.valid?[d.note]:[])(depositaryOrigin(coverage?.balance?.bankCapital??coverage?.balance?.insurerSolvency,now))),...(bankLike?['Als Bank bewertet: Der Datenanbieter ordnet das Unternehmen als spezialisiertes Finanzunternehmen ein, es liegen aber geprüfte Bankkapitaldaten des Konzerns vor.']:[])],
 };
}
