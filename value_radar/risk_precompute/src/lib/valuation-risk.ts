import type {FairValueResult,SzenarioMatrix} from './valuation';
const positive=(n:unknown):n is number=>typeof n==='number'&&Number.isFinite(n)&&n>0;
export function valuationRisk(price:unknown,fv:FairValueResult,scenarios:SzenarioMatrix|null){
 const keys=Object.keys(fv.core_methods||{}).filter(k=>!['fallback','analyst'].includes(k)&&positive(fv.core_methods[k])&&positive(fv.method_weights[k]));
 const baseGap=positive(price)&&positive(fv.fair_value)?fv.fair_value/price-1:null;
 const reason=!positive(price)?'Gültiger Kurs fehlt.':fv.used_fallback||!fv.reliable?'Der Methodenmix ist vorläufig oder verwendet einen Ersatzwert.':keys.length<2?'Mindestens zwei geeignete Kernmethoden benötigt.':!scenarios?'Szenarien fehlen.':keys.some(k=>['bear','base','bull'].some(s=>!positive(scenarios.methoden[k]?.[s])))?'Nicht alle Kernmethoden sind in allen drei Szenarien verfügbar.':'';
 if(reason)return {reason,baseGap,values:null,distances:null,methods:keys,position:'Bewertungsrisiko offen'};
 const total=keys.reduce((s,k)=>s+fv.method_weights[k],0),values:Record<string,number>={},distances:Record<string,number>={};
 for(const s of ['bear','base','bull']){values[s]=keys.reduce((a,k)=>a+scenarios!.methoden[k][s]!*fv.method_weights[k],0)/total;distances[s]=values[s]/(price as number)-1}
 if(values.bear>values.base||values.base>values.bull)return {reason:'Szenarien sind nicht geordnet. Keine Risikoeinstufung aus widersprüchlichen Modellwerten.',baseGap,values,distances,methods:keys,position:'Bewertungsrisiko offen'};
 const position=(price as number)>values.bull?'Kurs oberhalb aller drei Rechenwerte':(price as number)>values.base?'Kurs zwischen Base und Bull':(price as number)>values.bear?'Kurs zwischen Bear und Base':'Kurs auf oder unter dem Bear-Rechenwert';
 return {reason:'',baseGap,values,distances,methods:keys,position};
}
