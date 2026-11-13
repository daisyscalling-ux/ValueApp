/**
 * financial-health.ts - Bilanz-Kategorie des Composite aus den geprueften Finanzkennzahlen des Risikoscores
 * (seit 13.11.2026, Entscheidung des Nutzers: alle Profile).
 * Rohwert = 100 - gewichtetes Mittel der Kennzahlen im Block "Finanzielle Verwundbarkeit" (riskConstruct, gleiche
 * Skalen, Profile und Pruefungen wie im Risikoscore). Unternehmen: Nettoschulden/EBITDA, FCFF-Marge; Banken: CET1-Puffer,
 * LCR, Kreditqualitaet; Versicherer: Solvenzquote; Spezialfinanzierer: Nettofinanzschulden/EK, EKR.
 * Bilanz im Composite = Rang (Perzentil) des Rohwerts unter allen Titeln desselben Profils im Universum (Entscheidung des
 * Nutzers 13.11.2026): die Risikoskalen markieren nur Auffaelligkeiten (Median Unternehmen 82, Finanzwerte 90) und haetten
 * den Composite pauschal angehoben. Rang nur ab HEALTH_RANK_MIN Titeln im Profil; sonst und ohne gepruefte Kennzahl bleibt
 * die bisherige Bilanzrechnung (gekennzeichnet). Nie die absolute Skala.
 * Der Gesamt-Risikoscore fliesst nicht ein; nur dieser Block. Identische Kopie in ValueApp.
 */
import {riskConstruct} from './risk-construct';
export const HEALTH_METHOD='risk_block_financial_vulnerability_v1';
type Row=Record<string,any>;
export type HealthPart={name:string;weight:number;health:number;value:string};
export type FinancialHealth={method:string;score:number|null;profile:string|null;parts:HealthPart[];open:{name:string;reason:string}[];filledWeight:number;totalWeight:number};
export function financialHealth(fund:Row,coverage:Row|null,now=Date.now()):FinancialHealth{
 const r=riskConstruct({history:null,fund,now,coverage:coverage??null});
 const ms=r.metrics.filter(m=>m.block==='Finanzielle Verwundbarkeit'),av=ms.filter(m=>m.score!==null);
 const w=av.reduce((s,m)=>s+m.weight,0),total=ms.reduce((s,m)=>s+m.weight,0);
 const open=ms.filter(m=>m.score===null).map(m=>({name:m.name,reason:m.reason}));
 if(!w)return {method:HEALTH_METHOD,score:null,profile:r.profile,parts:[],open,filledWeight:0,totalWeight:total};
 const risk=av.reduce((s,m)=>s+m.weight*m.score!,0)/w;
 return {method:HEALTH_METHOD,score:Math.round((100-risk)*10)/10,profile:r.profile,
  parts:av.map(m=>({name:m.name,weight:m.weight,health:Math.round((100-m.score!)*10)/10,value:m.value})),open,filledWeight:w,totalWeight:total};
}

export const HEALTH_RANK_MIN=20;
export type HealthDistribution=Record<string,number[]>;
/** Profil fuer den Rang: ohne Bilanzpruefung (kein Profil) zaehlt ein Titel mit Unternehmenskennzahlen als Unternehmen. */
export const healthProfile=(h:FinancialHealth)=>h.score===null?null:(h.profile??'corporate');
/** Perzentil wie scoring.ts (unterhalb + halbe Gleichstaende), nur ab HEALTH_RANK_MIN gueltigen Werten im Profil. */
export function healthRank(raw:number|null,profile:string|null,dist:HealthDistribution|null|undefined):{score:number;n:number}|null{
 if(raw===null||!profile||!dist)return null;
 const vals=(dist[profile]??[]).filter(v=>typeof v==='number'&&Number.isFinite(v)&&v>=0&&v<=100);
 if(vals.length<HEALTH_RANK_MIN)return null;
 const below=vals.filter(v=>v<raw).length,equal=vals.filter(v=>v===raw).length;
 return {score:Math.round((below+0.5*equal)/vals.length*1000)/10,n:vals.length};
}
/** Verteilung aus Universumszeilen (cf_universum.json): health_raw je health_profile, nur aus dem App-Rechenweg. */
export function healthDistributionFromRows(rows:Row[]):HealthDistribution{
 const d:HealthDistribution={};
 for(const r of rows||[])if(r&&r.scanner_method==='ts-evaluate-v1'&&typeof r.health_profile==='string'&&typeof r.health_raw==='number'&&Number.isFinite(r.health_raw))(d[r.health_profile]??=[]).push(r.health_raw);
 return d;
}
