/** Unternehmensphase: erklärbare Heuristik, getrennt von Branche und Bewertung. */
import type { Fund, Playbook } from './valuation';
export type PhaseId = 'startup'|'hypergrowth'|'operating_leverage'|'capital_return'|'mature'|'decline'|'unknown';
export interface PhaseYear { year:number; revenue:number|null; netIncome:number|null; operatingMargin:number|null }
export interface CapitalPeriod { date:string; currency:string; fcf:number|null; dividends:number|null; buybacks:number|null; dilutedShares:number|null; priorDilutedShares:number|null }
export interface PeObservation { year:number; value:number }
export interface PhaseResult { id:PhaseId; label:string; confidence:'mittel'|'niedrig'; reasons:string[]; warnings:string[]; metrics:string[]; years:number[]; capital:ReturnType<typeof capitalReturn> }
const LABELS:Record<PhaseId,string>={startup:'Aufbau / Verluste',hypergrowth:'Starkes Wachstum',operating_leverage:'Steigende Profitabilität',capital_return:'Etabliert / Kapitalrückgabe',mature:'Etabliert / Kapitalrückgabe offen',decline:'Anhaltender Rückgang',unknown:'Phase offen'};
const METRICS:Record<PhaseId,string[]>={
 startup:['Umsatz / Bruttogewinn','Liquiditätsreichweite','Weg zur Profitabilität'],
 hypergrowth:['Umsatzwachstum','Bruttomarge','Forward-Gewinn','DCF-Szenarien'],
 operating_leverage:['Operative Marge','Forward-KGV','Free Cashflow','DCF-Szenarien'],
 capital_return:['Realisierter Gewinn / KGV','P/FCF','ROIC','Kapitalrückgabe','DCF / Reverse DCF'],
 mature:['Nachhaltiger Gewinn','KGV / P/FCF','ROIC','DCF / Reverse DCF'],
 decline:['Normalisierte Ertragskraft','Verschuldung','Konservative Zukunftsszenarien'],unknown:['Datenbasis ergänzen','Branchenmodell prüfen']};
export function finite(x:unknown):number|null {
 if(x===null||x===undefined||typeof x==='boolean'||(typeof x==='string'&&!x.trim()))return null;
 const n=Number(x);return Number.isFinite(n)?n:null;
}
export function paymentNetwork(f:Fund):boolean {
 return ['MA','V','NYSE:MA','NYSE:V'].includes((f.ticker??'').toUpperCase())&&/credit services|payment|finance\/rental\/leasing|miscellaneous commercial services/i.test(f.industry??'');
}
export function capitalReturn(f:Fund){
 const p=f.capital_return_period,valid=!!p?.date&&!!p?.currency;
 const fcf=valid?finite(p.fcf):null,div=valid?finite(p.dividends):null,buy=valid?finite(p.buybacks):null;
 const paid=div!==null&&div>=0&&buy!==null&&buy>=0?div+buy:null;
 const covered=paid!==null&&fcf!==null?(fcf>0?paid<=fcf:paid===0&&fcf===0):null;
 const shares=valid?finite(p.dilutedShares):null,prior=valid?finite(p.priorDilutedShares):null;
 const change=shares!==null&&shares>0&&prior!==null&&prior>0?shares/prior-1:null;
 const returning=(div!==null&&div>0)||(buy!==null&&buy>0)||(finite(f.dividend_yield)??0)>0;
 const notes:string[]=[];
 if(covered===null)notes.push('FCF-Deckung offen: periodengleiche Ausschüttungen oder Rückkäufe fehlen.');
 if(covered===false)notes.push('Dividenden und Rückkäufe sind in diesem Jahr nicht durch den FCF gedeckt.');
 if(change===null)notes.push('Nettoeffekt der Rückkäufe offen: vergleichbare verwässerte Aktienzahlen fehlen.');
 if(change!==null&&change>=0&&buy!==null&&buy>0)notes.push('Trotz Rückkäufen sinkt die verwässerte Aktienanzahl nicht.');
 return {returning,covered,shareChange:change,payoutFcf:paid!==null&&fcf!==null&&fcf>0?paid/fcf:null,period:valid?p.date:null,notes};
}
export function analysePhase(f:Fund):PhaseResult {
 const rows=[...(f.phase_history??[])].sort((a,b)=>a.year-b.year).slice(-3);
 const contiguous=rows.length===3&&rows[1].year===rows[0].year+1&&rows[2].year===rows[1].year+1;
 const rev=rows.map(r=>finite(r.revenue)),ni=rows.map(r=>finite(r.netIncome)),margin=rows.map(r=>finite(r.operatingMargin));
 const revenueOK=contiguous&&rev.every(x=>x!==null&&x>0);
 const falling=revenueOK&&ni.every(x=>x!==null)&&rev[0]!>rev[1]!&&rev[1]!>rev[2]!&&ni[0]!>ni[1]!&&ni[1]!>ni[2]!;
 const leverage=revenueOK&&margin.every(x=>x!==null)&&rev[1]!>rev[0]!&&rev[2]!>rev[1]!&&margin[2]!-margin[0]!>=.02&&margin[2]!>margin[1]!;
 const latest=rows[rows.length-1],prior=rows[rows.length-2];
 const annualGrowth=latest&&prior&&latest.year===prior.year+1&&latest.revenue!==null&&prior.revenue!==null&&prior.revenue>0
  ?latest.revenue/prior.revenue-1:null;
 const growth=rows.length?finite(annualGrowth):finite(f.revenue_growth);
 const profit=finite(f.net_income)??finite(f.eps_trailing)??finite(latest?.netIncome),fcf=finite(f.free_cashflow),capital=capitalReturn(f);
 let id:PhaseId='unknown';const reasons:string[]=[],warnings:string[]=[];
 if(falling&&(growth===null||growth<0)){id='decline';reasons.push('Umsatz und Nettogewinn fallen über zwei aufeinanderfolgende Jahresvergleiche.');warnings.push('Der Rückgang kann zyklisch sein. Struktur, Sondereffekte und Erholung separat prüfen.');}
 else if(profit!==null&&profit<=0&&growth!==null){id=growth>=.25?'hypergrowth':'startup';reasons.push('Noch kein positiver realisierter Gewinn; Einordnung nach Umsatzwachstum.');}
 else if(profit!==null&&profit>0&&growth!==null&&growth>=.25){id='hypergrowth';reasons.push('Mindestens 25 % Umsatzwachstum bei positivem Gewinn.');}
 else if(profit!==null&&profit>0&&leverage){id='operating_leverage';reasons.push('Steigender Umsatz und mindestens 2 Prozentpunkte operative Margenverbesserung über drei Geschäftsjahre.');}
 else if(profit!==null&&profit>0&&fcf!==null&&fcf>0&&growth!==null&&growth>=0){id=capital.returning?'capital_return':'mature';reasons.push('Positiver Gewinn und FCF bei nicht schrumpfendem Umsatz.');reasons.push(capital.returning?'Kapitalrückgabe gemeldet; ihre Deckung wird gesondert geprüft.':'Eine Kapitalrückgabe ist durch die vorhandenen Daten nicht belegt.');}
 else reasons.push('Die vorhandenen Daten erlauben keine eindeutige Phase.');
 if(growth!==null)reasons.push(`Umsatzwachstum: ${(growth*100).toFixed(1)} %.`);
 if(!contiguous)warnings.push('Keine drei lückenlosen Geschäftsjahre: längerfristiger Margentrend und Rückgang nicht bestätigt.');
 if(['startup','hypergrowth','decline'].includes(id))warnings.push('Der vorhandene DCF bildet Verlustphasen bis zum Break-even bzw. strukturelle Schrumpfung nicht explizit ab. Bewertung ist ein Prüffall.');
 warnings.push('Regelbasierte Einordnung mit möglichen Übergangsphasen; Schwellen sind keine kalibrierte Renditeprognose.');
 return {id,label:LABELS[id],confidence:id==='unknown'?'niedrig':'mittel',reasons,warnings,metrics:METRICS[id],years:rows.map(r=>r.year),capital};
}
export function phaseWeights(f:Fund,preset:Playbook,defaults:Record<string,number>,phase=analysePhase(f)):Record<string,number>{
 if(preset==='financial'||preset==='cyclical')return {...defaults};
 if(phase.id==='capital_return'||phase.id==='mature')return {dcf:.40,justified_pe:.30,ev_ebitda:.15,analyst:.15};
 if(['operating_leverage','hypergrowth'].includes(phase.id)&&(finite(f.eps_forward)??0)>0)return {fwd_pe:.30,fwd_composite:.25,dcf:.30,analyst:.15};
 if(phase.id==='decline')return {epv:.40,dcf:.30,justified_pe:.15,analyst:.15};
 return {...defaults};
}
function quantile(xs:number[],q:number):number{const pos=(xs.length-1)*q,lo=Math.floor(pos),hi=Math.ceil(pos);return xs[lo]+(xs[hi]-xs[lo])*(pos-lo);}
export function historicalPe(f:Fund){
 // Nur realisierter Gewinn. Kein Forward-Ersatz bei Verlust oder fehlender Basis.
 const price=finite(f.price),eps=finite(f.eps_trailing);
 const current=f.eps_trailing_comparable!==false&&price!==null&&price>0&&eps!==null&&eps>0?price/eps:null;
 const values=(f.pe_history??[]).map(r=>finite(r.value)).filter((x):x is number=>x!==null&&x>0).sort((a,b)=>a-b);
 const median=values.length?quantile(values,.5):null,enough=values.length>=3;
 // Empirischer Rang mit halbem Gewicht für Gleichstände. Kein Min-Max-Rang.
 const rank=enough&&current!==null?100*(values.filter(x=>x<current).length+.5*values.filter(x=>x===current).length)/values.length:null;
 return {current,median,n:values.length,rank,p25:enough?quantile(values,.25):null,p75:enough?quantile(values,.75):null,
 discount:current!==null&&median!==null?1-current/median:null,reversion:current!==null&&median!==null?median/current-1:null,
 returnValue:eps!==null&&eps>0&&median!==null?eps*median:null,years:(f.pe_history??[]).map(r=>r.year).sort((a,b)=>a-b)};
}
