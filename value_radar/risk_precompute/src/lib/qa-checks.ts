// QA-Prüfregeln der Einzelanalyse (QA-EINZELANALYSE.md, Phase 1, seit 20.11.2026). Laufen im Rechenweg der App auf dem Ergebnis
// von evaluateStock und melden je Prüfung ok / offen / auffaellig / fehler. Nur Meldung (Entscheidung des Nutzers), keine
// Änderung an Werten. Der Runner (Phase 2) ruft qaChecks je Titel auf und fasst über das Universum zusammen.
import {szenarioMatrix,FAIR_VALUE_MAX_MULT,FAIR_VALUE_MIN_MULT,fairesKgvTeile,investitionsanteil,epsBasis,type Fund,type FairValueResult} from './valuation';
import {BLOCK_WEIGHTS} from './risk-construct';
export const QA_METHOD='qa_einzelanalyse_v1';
export type QaStatus='ok'|'offen'|'auffaellig'|'fehler';
export type QaBefund={id:string;status:QaStatus;titel:string;detail:string;wert?:number|string|null;erwartet?:number|string|null};
type Rec=Record<string,any>;
export type QaInput={raw?:Rec|null;ev:{fund:Rec;fv:FairValueResult;scores:Rec;kz:Rec|null;q:Rec;playbook:string};universeRow?:Rec|null;now?:number};
/** Schwellen (Vorschläge, nach dem ersten Lauf zu schärfen). */
export const QA_LIMITS={formelToleranz:0.005,mcapToleranz:0.02,evToleranz:0.10,bandToleranz:0.05,quellenFaktor:1.5,ergaenzungMaxTage:7,kzFvAnteil:1/3,kzClip:[0.6,1.6] as [number,number]};
export const QA_TITEL:Record<string,string>={E1:'Identität',E2:'Frische',E3:'Einheit und Währung',E4:'52-Wochen-Band und Splits',E5:'Jahresreihe',E6:'Wertebereiche',E7:'Marktkapitalisierung = Kurs × Aktien',
 F1:'KGV = Kurs ÷ EPS',F2:'EV/EBITDA = (Marktkapitalisierung + Nettoverschuldung) ÷ EBITDA',F3:'Margen',F4:'KBV = Kurs ÷ Buchwert je Aktie',F5:'Fair Value aus Kernmethoden',F6:'DCF-Annahmen',F8:'Szenarien Bear ≤ Base ≤ Bull',
 F9:'12M-Ziel aus Teilzielen',F10:'Composite aus Kategorien',F12:'Risikoscore-Gewichte',D1:'Offene Werte mit Grund',D3:'Währung',D5:'Keine Platzhalter im Text',D6:'Keine widersprüchlichen Ergebnisse',K1:'App gegen Scanner'};
const fin=(v:unknown):v is number=>typeof v==='number'&&Number.isFinite(v);
const rel=(a:number,b:number)=>Math.abs(a-b)/Math.max(Math.abs(b),1e-12);
const r2=(v:number)=>Math.round(v*100)/100;
const ISIN=/^[A-Z]{2}[A-Z0-9]{9}[0-9]$/;
/** Pence-Codes vereinheitlichen (GBX = GBp); GBp gegen GBP ist eine Einheit, keine andere Notierung. */
export const waehrungsCode=(c:unknown)=>{const x=String(c??'');return x==='GBX'?'GBp':x};
const pence=(c:unknown)=>waehrungsCode(c)==='GBp';
/** Faktor, um einen Betrag in Währung b auf Währung a zu bringen (nur Pence/Pfund), sonst 1 bzw. null. */
const einheit=(a:unknown,b:unknown)=>{const x=waehrungsCode(a),y=waehrungsCode(b);if(x===y||!x||!y)return 1;if(x==='GBp'&&y==='GBP')return 100;if(x==='GBP'&&y==='GBp')return 0.01;return null};
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
  if(universeRow){for(const [k,a,b] of [['Notierung',universeRow.listing_symbol,sym],['ISIN',universeRow.isin,f.isin],['Währung',universeRow.currency,nativ]] as const){
   if(k==='Währung'&&a&&b&&einheit(a,b)!==null)continue;   // GBP/GBX/GBp: Einheit, keine andere Notierung
   if(a&&b&&String(a)!==String(b))prob.push(`${k} Universum ${a} ≠ ${b}`);else if(a&&!b)offen.push(`${k} in der App fehlt`)}}
  add('E1',prob.length?'fehler':offen.length?'offen':'ok',[...prob,...offen].join('; '))}
 // E2 Frische der Ergänzungsdatei und des Zinses
 {const t=Date.parse(String(sup?.retrieved_at??''));const tage=Number.isFinite(t)?(now-t)/86400000:null;
  if(!sup)add('E2','offen','Keine Ergänzungsdatei');else if(tage===null||tage<0||tage>L.ergaenzungMaxTage)add('E2','offen',`Ergänzungsdatei ${tage===null?'ohne Datum':Math.round(tage)+' Tage alt'}`,tage===null?null:Math.round(tage),L.ergaenzungMaxTage);
  else if(fv.risk_free&&String((fv.risk_free as Rec).source??'').startsWith('fallback'))add('E2','offen',`Zins ${nativ}: Rückfallwert, keine Tagesquelle`);else add('E2','ok')}
 // E3 Kurs der Quellen
 {const sp=sup?.market?.fields?.price,sc=sup?.market?.currency;
  if(f.price_source_conflict)add('E3','offen','Kurskonflikt erkannt, Bewertung gesperrt');
  else if(!fin(sp)||!fin(price)||!sc)add('E3','offen','Kein zweiter Kurs zum Abgleich');
  else{const faktor=einheit(nativ,sc);const p0=fin(f._fx)&&cur==='EUR'&&nativ!=='EUR'?price/f._fx:price;
   if(faktor===null)add('E3','offen',`Ergänzung in ${sc}, Notierung in ${nativ}`);else{const r=sp*faktor/p0;add('E3',r>L.quellenFaktor||r<1/L.quellenFaktor?'fehler':'ok',`Yahoo ÷ App-Kurs = ${r.toFixed(3)}`,r2(r),'0,67–1,5')}}}
 // E4 52-Wochen-Band
 {const hi=f['52w_high'],lo=f['52w_low'];
  if(!fin(hi)||!fin(lo)||!fin(price))add('E4','offen','Band oder Kurs fehlt');else if(hi<lo)add('E4','fehler',`Hoch ${hi} < Tief ${lo}`);
  else if(price>hi*(1+L.bandToleranz)||price<lo*(1-L.bandToleranz))add('E4','auffaellig',`Kurs ${price} außerhalb ${lo}–${hi} (möglicher Split oder Einheit)`,price,`${lo}–${hi}`);else add('E4','ok')}
 // E5 Jahresreihe
 {const jr=f.jahresreihe;if(!Array.isArray(jr))add('E5','offen',String(f.jahresreihe_status??'Keine Jahresreihe'));
  else{const j=jr.map((z:Rec)=>z.jahr),e=jr.map((z:Rec)=>String(z.ende??''));const steigt=j.every((x:number,i:number)=>!i||x>j[i-1])&&e.every((x:string,i:number)=>!i||x>e[i-1]);
   // Negativer Umsatz kommt bei Versicherern und Beteiligungsgesellschaften vor (Anlageergebnis im Umsatz): auffällig, kein Fehler.
   const neg=jr.some((z:Rec)=>fin(z.umsatz)&&z.umsatz<0);add('E5',!steigt?'fehler':neg?'auffaellig':'ok',!steigt?'Jahre oder Stichtage nicht aufsteigend':neg?'negativer Umsatz in der Jahresreihe (bei Versicherern und Holdings möglich)':'')}}
 // E6 Wertebereiche
 {const prob:string[]=[];const chk=(n:string,v:unknown,ok:(x:number)=>boolean)=>{if(fin(v)&&!ok(v))prob.push(`${n} ${v}`)};
  chk('Kurs',price,x=>x>0);chk('Aktien',f.shares_out,x=>x>0);chk('Bilanzsumme',f.total_assets,x=>x>0);
  chk('Beta',f.beta,x=>x>=-1&&x<=4);if(fv.risk_free)chk('Zins',(fv.risk_free as Rec).value,x=>x>=-0.01&&x<=0.15);
  // Margen über 100 % oder unter −200 % sind möglich (Bewertungsgewinne bei Immobilien, Beteiligungserträge, Anlaufverluste): auffällig.
  const marge:string[]=[];for(const k of ['gross_margin','operating_margin','profit_margin'])if(fin(f[k])&&!(f[k]>-2&&f[k]<=1.0001))marge.push(`${k} ${(f[k]*100).toFixed(0)} %`);
  if(fin(f.revenue)&&f.revenue<0)marge.push(`Umsatz negativ`);
  add('E6',prob.length?'fehler':marge.length?'auffaellig':'ok',[...prob,...marge].join('; '))}
 // E7 Marktkapitalisierung
 if(fin(f.market_cap)&&fin(price)&&fin(f.shares_out)&&f.shares_out>0){const r=rel(price*f.shares_out,f.market_cap);add('E7',r>L.mcapToleranz?'auffaellig':'ok',`Abweichung ${(r*100).toFixed(1)} %`,r2(price*f.shares_out),r2(f.market_cap))}else add('E7','offen','Marktkapitalisierung oder Aktienzahl fehlt');
 // F1 KGV
 if(fin(f.pe_trailing)&&fin(price)&&fin(f.eps_trailing)&&f.eps_trailing>0){const e=price/f.eps_trailing;add('F1',rel(f.pe_trailing,e)>L.formelToleranz?'fehler':'ok','',r2(f.pe_trailing),r2(e))}else add('F1','offen','KGV oder positives EPS fehlt');
 // F2 EV
 // Seit 21.11.2026: EV/EBITDA zum aktuellen Kurs (aktuelleMultiples) nachrechnen; vorher Vergleich mit dem ROIC-EV zum Jahresende (830 auffällig).
 if(fin(f.ev_ebitda)&&fin(f.market_cap)&&fin(f.net_debt)&&fin(f.ebitda)&&f.ebitda>0&&f.market_cap+f.net_debt>0){const e=(f.market_cap+f.net_debt)/f.ebitda;add('F2',rel(f.ev_ebitda,e)>L.formelToleranz?'fehler':'ok','',r2(f.ev_ebitda),r2(e))}
 else add('F2','offen',fin(f.ev_ebitda)?String(f.ev_ebitda_basis??'Marktkapitalisierung, Nettoverschuldung oder positives EBITDA fehlt'):'EV/EBITDA fehlt');
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
  if(fv.fair_value!==null&&fin(price)&&fin(fv.upside_pct)&&Math.abs((fv.fair_value/price-1)*100-fv.upside_pct)>0.3)prob.push(`Upside ${fv.upside_pct} ≠ FV ${fv.fair_value} / Kurs ${r2(price)} − 1 = ${r2((fv.fair_value/price-1)*100)}`);
  if(fv.reliable&&fv.confidence==='niedrig')prob.push('verlässlich bei Konfidenz niedrig');add('D6',prob.length?'fehler':'ok',prob.join('; '))}
 // K1 App gegen Scanner-Zeile (nur Kennzeichnung, Abweichungen sind auffällig)
 if(universeRow){const prob:string[]=[];const cmp=(n:string,a:unknown,b:unknown,tol:number)=>{if(fin(a)&&fin(b)&&rel(a,b)>tol)prob.push(`${n} App ${r2(a)} / Scanner ${r2(b)}`);else if((a===null)!==(b===null)&&(fin(a)||fin(b)))prob.push(`${n} nur ${fin(a)?'App':'Scanner'}`)};
  const k=cur===nativ?einheit(nativ,universeRow.currency):null;   // Pence/Pfund-Einheit des Universums angleichen
  if(k!==null){const sk=(v:unknown)=>fin(v)?v*k:v;cmp('Fair Value',fv.fair_value,sk(universeRow.fair_value),0.02);cmp('12M-Ziel',kz?.ziel??null,sk(universeRow.target_12m),0.02);
   // Seit 21.11.2026: welche Methode abweicht (Universum score_diagnostics.fv_methods)
   const um=universeRow.score_diagnostics?.fv_methods?.values??null;if(um&&prob.length){const diff:string[]=[];for(const [m,v] of Object.entries(fv.method_values??{})){const w=sk(um[m]);if(fin(v)&&fin(w)&&rel(v,w)>0.02)diff.push(`${m} ${r2(v)}/${r2(w)}`);else if(fin(v)!==fin(w))diff.push(`${m} nur ${fin(v)?'App':'Scanner'}`)}
    for(const m of Object.keys(um))if(!(m in (fv.method_values??{}))&&fin(sk(um[m])))diff.push(`${m} nur Scanner`);if(diff.length)prob.push('Methoden App/Scanner: '+diff.join(', '))}
   // Seit 22.11.2026 (Entscheidung des Nutzers: erst messen): weicht das begründete KGV ab, welche Stufe des fairen KGV kippt
   // und welcher Eingang dahintersteht (Scanner-Eingänge aus score_diagnostics.kgv_inputs, gleiche Rechnung fairesKgvTeile).
   const ki=universeRow.score_diagnostics?.kgv_inputs;const jv=(fv.method_values??{} as Rec).justified_pe,jw=um?sk(um.justified_pe):null;
   if(ki&&fin(jv)&&fin(jw)&&rel(jv,jw)>0.02){const t=kgvVergleich(f as Fund,fv.playbook??ev.playbook,ki);if(t)prob.push('Faires KGV '+t)}
   const ur=universeRow.score_diagnostics?.fv_check?.reliable;if(typeof ur==='boolean'&&ur!==fv.reliable)prob.push(`verlässlich App ${fv.reliable} / Scanner ${ur}`)}
  if(universeRow.playbook&&universeRow.playbook!==ev.playbook)prob.push(`Playbook ${ev.playbook} / ${universeRow.playbook}`);add('K1',prob.length?'auffaellig':'ok',prob.join('; '))}
 return out;
}

/** K1-Ursache beim begründeten KGV: Stufen des fairen KGV aus App-Eingängen und Scanner-Eingängen (kgv_inputs) gegenüberstellen.
 *  Liefert z. B. „14 / 10,5: Profitabilität 1/0 (bereinigte EKR 5,2 % / 4,75 %)“ oder null, wenn Stufen und EPS gleich sind. */
const KGV_TEIL_NAME:Record<string,string>={stab:'Stabilität',prof:'Profitabilität',pos:'Marge',gp:'Wachstum'};
export function kgvVergleich(app:Fund,preset:unknown,ki:Rec):string|null{
 const p=(preset as any)??ki.preset??'quality';
 const scan={free_cashflow:ki.free_cashflow,net_debt_ebitda:ki.net_debt_ebitda,current_ratio:ki.current_ratio,roe:ki.roe,gross_margin:ki.gross_margin,
  revenue_growth:ki.revenue_growth,earnings_growth:ki.earnings_growth,net_income:ki.net_income,total_assets:ki.total_assets,
  ...(typeof ki.capex_share==='number'&&ki.capex_share_source==='abschluss'?{investitionsanteil:{method:'capex_share_annual_v1',wert:ki.capex_share,periode:ki.capex_share_period??null}}:{})} as unknown as Fund;
 const a=fairesKgvTeile(app,p),b=fairesKgvTeile(scan,ki.preset??p);
 const zahl0=(v:unknown)=>typeof v==='number'&&Number.isFinite(v)?String(Math.round(v*100)/100):'—';
 // Nur zuordnen, wenn sich das Scanner-KGV aus den gespeicherten Eingängen nachrechnen lässt (21.11.2026: 1.337 von 1.342).
 if(typeof ki.faires_kgv==='number'&&Math.abs(b.faires_kgv-ki.faires_kgv)>0.01)return `${zahl0(a.faires_kgv)}/${zahl0(ki.faires_kgv)}: Ursache offen, Scanner-Eingänge unvollständig`;
 const pct=(v:unknown)=>typeof v==='number'&&Number.isFinite(v)?(Math.round(v*1000)/10).toLocaleString('de-DE')+' %':'—';
 const zahl=(v:unknown)=>typeof v==='number'&&Number.isFinite(v)?String(Math.round(v*100)/100):'—';
 const ein:Record<string,string>={
  stab:`FCF ${(app.free_cashflow??0)>0?'+':'≤0'}/${(ki.free_cashflow??0)>0?'+':'≤0'}, Nettoschulden/EBITDA ${zahl(app.net_debt_ebitda)}/${zahl(ki.net_debt_ebitda)}, Current Ratio ${zahl(app.current_ratio)}/${zahl(ki.current_ratio)}`,
  prof:`bereinigte EKR ${pct(a.uroe)}/${pct(b.uroe)}, EKR ${pct(app.roe)}/${pct(ki.roe)}, Investitionsanteil ${pct(investitionsanteil(app).wert)} ${investitionsanteil(app).quelle}/${pct(ki.capex_share)} ${ki.capex_share_source??'?'}`,
  pos:`Bruttomarge ${pct(app.gross_margin)}/${pct(ki.gross_margin)}`,
  gp:`Umsatzwachstum ${pct(app.revenue_growth)}/${pct(ki.revenue_growth)}`};
 const teile=(['stab','prof','pos','gp'] as const).filter(k=>a[k]!==b[k]).map(k=>`${KGV_TEIL_NAME[k]} ${a[k]}/${b[k]} (${ein[k]})`);
 const ea=epsBasis(app).eps,eb=ki.eps;const epsDiff=typeof ea==='number'&&typeof eb==='number'&&eb!==0&&Math.abs(ea/eb-1)>0.02;
 if(!teile.length&&!epsDiff&&a.faires_kgv===b.faires_kgv)return null;
 return `${zahl(a.faires_kgv)}/${zahl(b.faires_kgv)}`+(teile.length?': '+teile.join('; '):'')+(epsDiff?`; EPS ${zahl(ea)}/${zahl(eb)}`:'');
}

/** Zusammenfassung je Prüfung (für Runner und Tab). */
export function qaSummary(befunde:QaBefund[][]):Record<string,Record<QaStatus,number>>{
 const out:Record<string,Record<QaStatus,number>>={};for(const liste of befunde)for(const b of liste){out[b.id]??={ok:0,offen:0,auffaellig:0,fehler:0};out[b.id][b.status]++}return out;
}
