// Kennzeichnung für Bankkennzahlen, die nicht von der eigenen Stammaktie stammen:
// - depositaryOf: DR übernimmt die Konzernkennzahlen der im selben Lauf geprüften Stammaktie (seit 10.11.2026).
// - standaloneDepositary: DR ohne Stammaktie im Universum, Konzernkennzahlen über geprüfte Zuordnung (seit 12.11.2026).
type Row=Record<string,any>;
const dateOnly=(v:any)=>typeof v==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(v);
const https=(v:any)=>{try{return new URL(v).protocol==='https:'}catch{return false}};
export const STANDALONE_KINDS:Record<string,string>={only_listed_instrument:'an der Börse sind nur Depositary Receipts notiert',adr_without_ordinary_in_universe:'ADR; die Stammaktie ist nicht im Universum'};
// null = keine DR-Herkunft; {valid:false} = Kennzeichnung unvollständig oder abgelaufen (dann Kennzahlen nicht verwenden).
export function depositaryOrigin(c:Row|null|undefined,now=Date.now()):{valid:boolean;note:string}|null{
 const s=c?.standaloneDepositary,today=new Date(now).toISOString().slice(0,10);
 if(s){
  const ok=!!STANDALONE_KINDS[s.kind]&&dateOnly(s.reviewedOn)&&dateOnly(s.reviewExpires)&&s.reviewedOn<=today&&today<=s.reviewExpires&&https(s.sourceUrl)&&/^[0-9a-f]{64}$/.test(s.sourceSha256||'')&&typeof s.evidence==='string'&&s.evidence.trim()!=='';
  return {valid:ok,note:'Depositary Receipt ohne Stammaktie im Universum ('+(STANDALONE_KINDS[s.kind]||'unbekannte Art')+'): Konzernkennzahlen über eine geprüfte Zuordnung, geprüft am '+s.reviewedOn+', gültig bis '+s.reviewExpires+'.'};
 }
 if(typeof c?.depositaryOf==='string'&&c.depositaryOf)return {valid:true,note:'Depositary Receipt: Die Konzernkennzahlen stammen von der im selben Lauf geprüften Stammaktie '+c.depositaryOf+'.'};
 return null;
}
