// QA-Prüfregeln der Einzelanalyse (QA-EINZELANALYSE.md, Phase 1, seit 20.11.2026). Laufen im Rechenweg der App auf dem Ergebnis
// von evaluateStock und melden je Prüfung ok / offen / auffaellig / fehler. Nur Meldung (Entscheidung des Nutzers), keine
// Änderung an Werten. Der Runner (Phase 2) ruft qaChecks je Titel auf und fasst über das Universum zusammen.
import {szenarioMatrix,FAIR_VALUE_MAX_MULT,FAIR_VALUE_MIN_MULT,type Fund,type FairValueResult} from './valuation';
import {BLOCK_WEIGHTS} from './risk-construct';
export const QA_METHOD='qa_einzelanalyse_v1';
export type QaStatus='ok'|'offen'|'auffaellig'|'fehler';
export type QaBefund={id:string;status:QaStatus;titel:string;detail:string;wert?:number|string|null;erwartet?:number|string|null};
type Rec=Record<string,any>;
export type QaInput={raw?:Rec|null;ev:{fund:Rec;fv:FairValueResult;scores:Rec;kz:Rec|null;q:Rec;playbook:string};universeRow?:Rec|null;now?:number};
/** Schwellen (Vorschläge, nach dem ersten Lauf zu schärfen). */
export const QA_LIMITS={formelToleranz:0.005,mcapToleranz:0.02,evToleranz:0.10,bandToleranz:0.05,quellenFaktor:1.5,ergaenzungMaxTage:7,kzFvAnteil:1/3,kzClip:[0.6,1.6] as [number,number]};
export const QA_TITEL:Record<string,string>={E1:'Identität',E2:'Frische',E3:'Einheit und Währung',E4:'52-Wochen-Band und Splits',E5:'Jahresreihe',E6:'Wertebereiche',E7:'Marktkapitalisierung = Kurs × Aktien',
 F1:'KGV = Kurs ÷ EPS',F2:'EV = Marktkapitalisierung + Nettoverschuldung',F3:'Margen',F4:'KBV = Kurs ÷ Buchwert je Aktie',F5:'Fair Value aus Kernmethoden',F6:'DCF-Annahmen',F8:'Szenarien Bear ≤ Base ≤ Bull',
 F9:'12M-Ziel aus Teilzielen',F10:'Composite aus Kategorien',F12:'Risikoscore-Gewichte',D1:'Offene Werte mit Grund',D3:'Währung',D5:'Keine Platzhalter im Text',D6:'Keine widersprüchlichen Ergebnisse',K1:'App gegen Scanner'};
const fin=(v:unknown):v is number=>typeof v==='number'&&Number.isFinite(v);
const rel=(a:number,b:number)=>Math.abs(a-b)/Math.max(Math.abs(b),1e-12);
const r2=(v:number)=>Math.round(v*100)/100;
const ISIN=/^[A-Z]{2}[A-Z0-9]{9}[0-9]$/;
export function isinValid(s:unknown):boolean{
 if(typeof s!=='string'||!ISIN.test(s))return false;
 const d=s.slice(0,-1).split('').map(c=>parseInt(c,36)).join('');let t=0;
 for(let i=0;i<d.length;i++){let n=Number(d[d.length-1-i]);if(i%2===0){n*=2;if(n>9)n-=9}t+=n}
 return (10-t%10)%10===Number(s[s.length-1]);
}

export function qaChecks(input:QaInput):QaBefund[]{
 const {raw,ev,universeRow}=input,now=input.now??Date.now(),f=ev.fund,fv=ev.fv,kz=ev.kz,L=QA_LIMITS;
 const out:QaBefund[]=[];const add=(id:string,status:QaStatus,detail='',wert?:QaBefund['wert'],erwartet?:QaBefund['erwartet'])=>out.push({id,status,titel:QA_TITEL[id]??id,detail,...(wert!==undefined?{wert}:{}),...(erwartet!==undefined?{erwartet}:{})});
 const price=f.price,cur=String(f.currency??''),nativ=String(f._native_currency??cur),sup=raw?.fundamental_supplement??f._fundamental_supplement??null;
 // E1 Identität
 {const prob:string[]=[];const sym=String(f.ticker??'').toUpperCase();
  if(raw?.resolved_symbol&&String(raw.resolved_symbol).toUpperCase()!==sym)prob.push(`Bundle ${raw.resolved_symbol} ≠ ${sym}`);
  if(sup&&sup.symbol&&String(sup.symbol).toUpperCase()!==sym)prob.push(`Ergänzungsdatei ${sup.symbol}`);
  if(f.isin&&!isinValid(f.isin))prob.push(`ISIN ${f.isin} ungültig`);
  const offen:string[]=[];
  if(universeRow){for(const [k,a,b] of [['Notierung',universeRow.listing_symbol,sym],['ISIN',universeRow.isin,f.isin],['Währung',universeRow.currency,nativ]] as const){if(a&&b&&String(a)!==String(b))prob.push(`${k} Universum ${a} ≠ ${b}`);else if(a&&!b)offen.push(`${k} in der App fehlt`)}}
  add('E1',prob.length?'fehler':offen.length?'offen':'ok',[...prob,...offen].join('; '))}
 // E2 Frische der Ergänzungsdatei und des Zinses
 {const t=Date.parse(String(sup?.retrieved_at??''));const tage=Number.isFinite(t)?(now-t)/86400000:null;
  if(!sup)add('E2','offen','Keine Ergänzungsdatei');else if(tage===null||tage<0||tage>L.ergaenzungMaxTage)add('E2','offen',`Ergänzungsdatei ${tage===null?'ohne Datum':Math.round(tage)+' Tage alt'}`,tage===null?null:Math.round(tage),L.ergaenzungMaxTage);
  else if(fv.risk_free&&String((fv.risk_free as Rec).source??'').startsWith('fallback'))add('E2','offen',`Zins ${nativ}: Rückfallwert, keine Tagesquelle`);else add('E2','ok')}
 // E3 Kurs der Quellen
 {const sp=sup?.market?.fields?.price,sc=sup?.market?.currency;
  if(f.price_source_conflict)add('E3','offen','Kurskonflikt erkannt, Bewertung gesperrt');
  else if(!fin(sp)||!fin(price)||!sc)add('E3','offen','Kein zweiter Kurs zum Abgleich');
  else{const faktor=sc===nativ?1:(sc==='GBp'&&nativ==='GBP')?0.01:(sc==='GBP'&&nativ==='GBp')?100:null;const p0=fin(f._fx)&&cur==='EUR'&&nativ!=='EUR'?price/f._fx:price;
   if(faktor===null)add('E3','offen',`Ergänzung in ${sc}, Notierung in ${nativ}`);else{const r=sp*faktor/p0;add('E3',r>L.quellenFaktor||r<1/L.quellenFaktor?'fehler':'ok',`Yahoo ÷ App-Kurs = ${r.toFixed(3)}`,r2(r),'0,67–1,5')}}}
 // E4 52-Wochen-Band
 {const hi=f['52w_high'],lo=f['52w_low'];
  if(!fin(hi)||!fin(lo)||!fin(price))add('E4','offen','Band oder Kurs fehlt');else if(hi<lo)add('E4','fehler',`Hoch ${hi} < Tief ${lo}`);
  else if(price>hi*(1+L.bandToleranz)||price<lo*(1-L.bandToleranz))add('E4','auffaellig',`Kurs ${price} außerhalb ${lo}–${hi} (möglicher Split oder Einheit)`,price,`${lo}–${hi}`);else add('E4','ok')}
 // E5 Jahresreihe
 {const jr=f.jahresreihe;if(!Array.isArray(jr))add('E5','offen',String(f.jahresreihe_status??'Keine Jahresreihe'));
  else{const j=jr.map((z:Rec)=>z.jahr),e=jr.map((z:Rec)=>String(z.ende??''));const steigt=j.every((x:number,i:number)=>!i||x>j[i-1])&&e.every((x:string,i:number)=>!i||x>e[i-1]);
   const neg=jr.some((z:Rec)=>fin(z.umsatz)&&z.umsatz<0);add('E5',!steigt||neg?'fehler':'ok',!steigt?'Jahre oder Stichtage nicht aufsteigend':neg?'negativer Umsatz':'')}}
 // E6 Wertebereiche
 {const prob:string[]=[];const chk=(n:string,v:unknown,ok:(x:number)=>boolean)=>{if(fin(v)&&!ok(v))prob.push(`${n} ${v}`)};
  chk('Kurs',price,x=>x>0);chk('Aktien',f.shares_out,x=>x>0);chk('Umsatz',f.revenue,x=>x>=0);chk('Bilanzsumme',f.total_assets,x=>x>0);
  for(const k of ['gross_margin','operating_margin','profit_margin'])chk(k,f[k],x=>x>-2&&x<=1.0001);chk('Beta',f.beta,x=>x>=-1&&x<=4);
  if(fv.risk_free)chk('Zins',(fv.risk_free as Rec).value,x=>x>=-0.01&&x<=0.15);add('E6',prob.length?'fehler':'ok',prob.join('; '))}
 // E7 Marktkapitalisierung
 if(fin(f.market_cap)&&fin(price)&&fin(f.shares_out)&&f.shares_out>0){const r=rel(price*f.shares_out,f.market_cap);add('E7',r>L.mcapToleranz?'auffaellig':'ok',`Abweichung ${(r*100).toFixed(1)} %`,r2(price*f.shares_out),r2(f.market_cap))}else add('E7','offen','Marktkapitalisierung oder Aktienzahl fehlt');
 // F1 KGV
 if(fin(f.pe_trailing)&&fin(price)&&fin(f.eps_trailing)&&f.eps_trailing>0){const e=price/f.eps_trailing;add('F1',rel(f.pe_trailing,e)>L.formelToleranz?'fehler':'ok','',r2(f.pe_trailing),r2(e))}else add('F1','offen','KGV oder positives EPS fehlt');
 // F2 EV
 if(fin(f.enterprise_value)&&fin(f.market_cap)&&fin(f.net_debt)){const e=f.market_cap+f.net_debt,r=rel(f.enterprise_value,e);add('F2',r>L.evToleranz?'auffaellig':'ok',`Abweichung ${(r*100).toFixed(1)} % (EV der Quelle kann anderen Stichtag haben)`,r2(f.enterprise_value),r2(e))}else add('F2','offen','EV, Marktkapitalisierung oder Nettoverschuldung fehlt');
 // F3 Margen
 {const prob:string[]=[];let n=0;for(const [m,z] of [['gross_margin','gross_profit'],['profit_margin','net_income'],['operating_margin','ebit']] as const){if(fin(f[m])&&fin(f[z])&&fin(f.revenue)&&f.revenue>0){n++;const e=f[z]/f.revenue;if(Math.abs(f[m]-e)>0.002)prob.push(`${m} ${(f[m]*100).toFixed(1)} % ≠ ${(e*100).toFixed(1)} %`)}}
  add('F3',prob.length?'auffaellig':n?'ok':'offen',prob.join('; ')||(n?'':'Keine Marge mit Bezugsgröße'))}
 // F4 KBV
 if(fin(f.pb)&&fin(price)&&fin(f.book_value_ps)&&f.book_value_ps>0){const e=price/f.book_value_ps;add('F4',rel(f.pb,e)>L.formelToleranz?'fehler':'ok','',r2(f.pb),r2(e))}else add('F4','offen','KBV oder Buchwert fehlt');
 // F5 Fair Value
 {const core=fv.core_methods??{},w=fv.method_weights??{};const keys=Object.keys(core);
  if(fv.fair_value===null)add('F5','offen','Kein Fair Value');else if(!keys.length)add('F5','fehler','Fair Value ohne Kernmethode');
  else{const ws=keys.reduce((s,k)=>s+(w[k]??0.15),0);let e=keys.reduce((s,k)=>s+core[k]*(w[k]??0.15),0)/ws;
   if(fin(price)){if(e>price*FAIR_VALUE_MAX_MULT)e=price*FAIR_VALUE_MAX_MULT;else if(e<price*FAIR_VALUE_MIN_MULT)e=price*FAIR_VALUE_MIN_MULT}
   add('F5',Math.abs(fv.fair_value-e)>Math.max(0.011,fv.fair_value*L.formelToleranz)?'fehler':'ok','',fv.fair_value,r2(e))}}
 // F6 DCF-Annahmen
 {const tg=fv.terminal_growth as Rec|undefined,rf=fv.risk_free as Rec|undefined;const prob:string[]=[];
  if(tg&&!(tg.value>=0&&tg.value<=0.025))prob.push(`Endwachstum ${tg.value}`);if(rf&&!(rf.value>=-0.01&&rf.value<=0.15))prob.push(`Zins ${rf.value}`);
  add('F6',prob.length?'fehler':tg?'ok':'offen',prob.join('; '))}
 // F8 Szenarien
 if(fv.fair_value!==null){const m=szenarioMatrix(f as Fund,(f._peer_funds as Fund[])??null,ev.fv.playbook);if(!m)add('F8','offen','Keine Szenarien');else{const prob:string[]=[];
  for(const [k,s] of Object.entries(m.methoden)){const b=s.bear,ba=s.base,bu=s.bull;if(fin(b)&&fin(ba)&&fin(bu)&&!(b<=ba+1e-9&&ba<=bu+1e-9))prob.push(`${k}: ${b} / ${ba} / ${bu}`);
   if(fin(ba)&&fin(fv.core_methods?.[k])&&Math.abs(ba-r2(fv.core_methods[k]))>0.011)prob.push(`${k}: Base ${ba} ≠ Kernwert ${r2(fv.core_methods[k])}`)}
  add('F8',prob.length?'fehler':'ok',prob.join('; '))}}else add('F8','offen','Kein Fair Value');
 // F9 12M-Ziel
 if(!kz)add('F9','offen','Kein 12M-Ziel');else{const teile=[kz.ziel_fundamental,kz.ziel_analyst,kz.ziel_momentum].filter(fin);const prob:string[]=[];
  if(fin(price)){const lo=Math.max(Math.min(...teile),price*L.kzClip[0]),hi=Math.min(Math.max(...teile),price*L.kzClip[1]);if(teile.length&&(kz.ziel<Math.min(lo,hi)-0.011||kz.ziel>Math.max(lo,hi)+0.011))prob.push(`Ziel ${kz.ziel} außerhalb der Teilziele/Kappung ${r2(lo)}–${r2(hi)}`)}
  const anker=f._fv_anker as Rec|undefined;if(anker?.reliable&&fin(anker.value)&&fin(price)&&fin(kz.ziel_fundamental)){const e=price+(anker.value-price)*L.kzFvAnteil;if(rel(kz.ziel_fundamental,e)>0.01)prob.push(`fundamental ${kz.ziel_fundamental} ≠ Kurs + (FV − Kurs)/3 = ${r2(e)}`)}
  add('F9',prob.length?'fehler':'ok',prob.join('; '))}
 // F10 Composite
 {const cats=Object.values(ev.scores.category_scores??{}).filter(fin) as number[],c=ev.scores.composite;
  if(!cats.length)add('F10',c===null?'ok':'fehler',c===null?'offen ohne Kategorie':`Composite ${c} ohne jede Kategorie (Platzhalter)`);
  else if(!fin(c))add('F10','fehler','Composite fehlt trotz Kategorien');else{const lo=Math.min(...cats)-15,hi=Math.max(...cats)+0.1;add('F10',c<lo||c>hi?'fehler':'ok',`Composite ${c}, Kategorien ${Math.min(...cats).toFixed(1)}–${Math.max(...cats).toFixed(1)}`)}}
 // F12
 {const s=Object.values(BLOCK_WEIGHTS).reduce((a,b)=>a+b,0);add('F12',s===100?'ok':'fehler','',s,100)}
 // D1 offene Werte mit Grund
 {const prob:string[]=[];if(fv.fair_value===null){const grund=(f.valuation_data?.issues??[]).length||Object.keys(fv.verworfen??{}).length||fv.used_fallback===false;if(!grund)prob.push('Fair Value offen ohne Grund')}
  if(!Array.isArray(f.jahresreihe)&&!f.jahresreihe_status)prob.push('Jahresreihe offen ohne Grund');
  for(const [k,v] of Object.entries((ev.scores.metric_open??{}) as Rec))if(v===true||v==='')prob.push(`Kennzahl ${k} offen ohne Grund`);
  add('D1',prob.length?'fehler':'ok',prob.join('; '))}
 // D3 Währung
 add('D3',/^[A-Z]{3}$|^GBp$/.test(cur)?'ok':'fehler',cur?'':'Währung fehlt',cur);
 // D5 Platzhalter im Text und in Zahlen
 {const prob:string[]=[];const seen=new Set<unknown>();const walk=(v:unknown,p:string,t=0)=>{if(t>6||v===null||v===undefined||seen.has(v))return;if(typeof v==='number'&&!Number.isFinite(v))prob.push(`${p} = ${v}`);
   else if(typeof v==='string'&&/\bundefined\b|\bNaN\b|Infinity|\[object Object\]/.test(v))prob.push(`${p}: „${v.slice(0,60)}“`);else if(typeof v==='object'){seen.add(v);for(const [k,x] of Object.entries(v as Rec))if(!k.startsWith('_'))walk(x,p+'.'+k,t+1)}};
  walk(fv,'fv');walk(kz,'kz');walk(ev.scores,'scores');walk(ev.q,'q');add('D5',prob.length?'fehler':'ok',prob.slice(0,5).join('; '))}
 // D6 widersprüchliche Ergebnisse
 {const prob:string[]=[];const blocked=!!f.valuation_data?.blocked;if(blocked&&fv.fair_value!==null)prob.push('Bewertung gesperrt, aber Fair Value');if(blocked&&kz)prob.push('Bewertung gesperrt, aber 12M-Ziel');
  if(fv.fair_value!==null&&fin(price)&&fin(fv.upside_pct)&&Math.abs((fv.fair_value/price-1)*100-fv.upside_pct)>0.15)prob.push(`Upside ${fv.upside_pct} ≠ FV/Kurs`);
  if(fv.reliable&&fv.confidence==='niedrig')prob.push('verlässlich bei Konfidenz niedrig');add('D6',prob.length?'fehler':'ok',prob.join('; '))}
 // K1 App gegen Scanner-Zeile (nur Kennzeichnung, Abweichungen sind auffällig)
 if(universeRow){const prob:string[]=[];const cmp=(n:string,a:unknown,b:unknown,tol:number)=>{if(fin(a)&&fin(b)&&rel(a,b)>tol)prob.push(`${n} App ${r2(a)} / Scanner ${r2(b)}`);else if((a===null)!==(b===null)&&(fin(a)||fin(b)))prob.push(`${n} nur ${fin(a)?'App':'Scanner'}`)};
  if(cur===nativ){cmp('Fair Value',fv.fair_value,universeRow.fair_value,0.02);cmp('12M-Ziel',kz?.ziel??null,universeRow.target_12m,0.02)}
  if(universeRow.playbook&&universeRow.playbook!==ev.playbook)prob.push(`Playbook ${ev.playbook} / ${universeRow.playbook}`);add('K1',prob.length?'auffaellig':'ok',prob.join('; '))}
 return out;
}

/** Zusammenfassung je Prüfung (für Runner und Tab). */
export function qaSummary(befunde:QaBefund[][]):Record<string,Record<QaStatus,number>>{
 const out:Record<string,Record<QaStatus,number>>={};for(const liste of befunde)for(const b of liste){out[b.id]??={ok:0,offen:0,auffaellig:0,fehler:0};out[b.id][b.status]++}return out;
}
