import rules from './market-priority.json';
export function marketTier(symbol:string){
 const venue=String(symbol||'').split(':')[0].toUpperCase();
 return rules.primary.includes(venue)?0:rules.europe.includes(venue)?1:2;
}
export function rotationDue(at:unknown,now:number){
 const t=typeof at==='string'?Date.parse(at):NaN;
 return Number.isFinite(t)&&t<=now&&now-t>=rules.rotationDays*86400000;
}
