import {buildSectorComparisons,seriesCheck,currencyUnit} from './sector-comparison';
type Row=Record<string,any>;
const DAY=86400000,finite=(v:any)=>typeof v==='number'&&Number.isFinite(v);
const fresh=(v:any,now:number,days:number)=>typeof v==='string'&&Number.isFinite(Date.parse(v))&&Date.parse(v)<=now&&now-Date.parse(v)<=days*DAY;
const keys=['isin','currency','industry','sub_industry','name_full','security_type'];
const identity=(r:Row)=>Object.fromEntries(keys.map(k=>[k,r[k]??null]));
export function fxCheck(fx:Row|null|undefined,now:number){
 if(fx?.schema!==1||fx.source!=='ECB euro foreign exchange reference rates'||fx.base!=='EUR'||fx.quoteConvention!=='currency_units_per_EUR'||!fresh(fx.retrievedAt,now,1.5)||!fresh(fx.lastObservation,now,7)||!fx.rates||Array.isArray(fx.rates))return 'fx_missing_or_stale';
 const entries=Object.entries(fx.rates);if(entries.length<250||entries.length>740)return 'fx_history_incomplete';
 const midnight=new Date(now).setUTCHours(0,0,0,0);
 for(const [d,rates] of entries){if(!/^\d{4}-\d{2}-\d{2}$/.test(d)||!Number.isFinite(Date.parse(d))||new Date(Date.parse(d)).toISOString().slice(0,10)!==d||Date.parse(d)>=midnight||!rates||typeof rates!=='object'||Array.isArray(rates))return 'fx_invalid';
  for(const [currency,value] of Object.entries(rates))if(!/^[A-Z]{3}$/.test(currency)||!finite(value)||Number(value)<=0||currency==='EUR'&&value!==1)return 'fx_invalid';
 }
 if(entries.map(([d])=>d).sort().at(-1)!==fx.lastObservation)return 'fx_last_date_mismatch';
 return null;
}
export function convertToEuro(h:Row,fx:Row,now:number){
 const error=seriesCheck(h,now);if(error)return {error};
 const currency=currencyUnit(h.currency),scale=['GBp','GBX'].includes(h.currency)?100:1;
 const points:[string,number][]=[];
 for(const [d,p] of h.points){const rate=currency==='EUR'?(fx.rates[d]?1:null):fx.rates[d]?.[currency];
  if(!finite(rate)||rate<=0)continue;const value=p/scale/rate;if(!finite(value)||value<=0)return {error:'converted_price_invalid'};points.push([d,value]);}
 const series={...h,currency:'EUR',points};const invalid=seriesCheck(series,now);
 return invalid?{error:'fx_overlap_'+invalid}:{series,originalCurrency:h.currency,excludedDates:h.points.length-points.length};
}
/** Supplement only: same business groups, actual dated FX, no widening of peers. */
export function addFxPeerContext(strict:Row,universe:Row,groups:Row,cache:Row,fx:Row|null,now=Date.now()){
 const summary:Row={available:0,missing:0,reasons:{},basis:'EUR investor perspective',scoreContribution:0};
 const error=fxCheck(fx,now),rows=universe.kandidaten||[],counts=new Map<string,number>();
 for(const r of rows)counts.set(r.listing_symbol,(counts.get(r.listing_symbol)||0)+1);
 const transformed:Row[]=[],listings:Row={},series:Row={},originals:Row={},diagnostics:Row={};
 if(!error)for(const r of rows){const s=r.listing_symbol,g=groups?.listings?.[s],h=cache?.schema===1?cache.series?.[s]:null;
  if(counts.get(s)!==1||!g?.inputIdentity||keys.some(k=>(r[k]??null)!==(g.inputIdentity[k]??null))){diagnostics[s]='membership_identity_mismatch';continue;}
  if(!h||h.symbol!==s||!r.currency||currencyUnit(h.currency)!==currencyUnit(r.currency)){diagnostics[s]='series_currency_or_identity_mismatch';continue;}
  if(h.inputIdentity&&['listing_symbol','ticker','isin','currency','name_full','name','security_type','share_class'].some(k=>(h.inputIdentity[k]??null)!==(r[k]??null))){diagnostics[s]='history_input_identity_mismatch';continue;}
  const converted=convertToEuro(h,fx!,now);if(converted.error){diagnostics[s]=converted.error;continue;}
  const row={...r,currency:'EUR'};transformed.push(row);series[s]=converted.series;originals[s]=r;
  listings[s]={...g,inputIdentity:identity(row)};
 }
 const context=error?null:buildSectorComparisons({kandidaten:transformed},{...groups,listings},{schema:1,series},now,5);
 for(const [s,value] of Object.entries(strict.stocks) as [string,Row][]){
  // Other failure types need their own repair; do not mask identity/history errors.
  if(value.state!=='missing'||value.reason!=='fewer_than_five_same_currency_issuers')continue;
  const c=context?.stocks[s];let reason=error||diagnostics[s]||c?.reason||'fx_context_unavailable';
  const currencies=c?.state==='available'?[...new Set([s,...c.peerSymbols].map((p:string)=>currencyUnit(originals[p]?.currency)))].sort():[];
  if(c?.state==='available'&&currencies.length<2)reason='no_cross_currency_extension';
  if(c?.state==='available'&&currencies.length>=2){
   value.currencyAdjustedContext={...c,method:'eur-investor-cohort-v1',quality:'currency_adjusted_business_context',reason:'same_business_group_actual_fx',inputIdentity:identity(originals[s]),
    originalCurrency:originals[s].currency,fxCurrencies:currencies,fxSource:fx!.source,fxSourceUrl:fx!.sourceUrl,fxRetrievedAt:fx!.retrievedAt,fxLastObservation:fx!.lastObservation,
    fxDatePolicy:'exact_same_date_no_fill',minimumPeers:5,directCompetitorsVerified:false,score:null,
    interpretation:'Geschaeftsgruppenvergleich aus Euro-Anlegersicht mit historischen EZB-Referenzkursen. Wechselkurse sind enthalten, nicht abgesichert. Kein Ersatz fuer direkte Wettbewerber, kein Einfluss auf Risikoscore oder Fair Value.',
    warnings:[...c.warnings.filter((x:string)=>!x.startsWith('Same trading currency')),'Boersenschluss und EZB-Fixing liegen nicht zur selben Uhrzeit; rein beschreibender Vergleich, kein Handelssignal.','Nur gemeinsame Tage mit vorhandenen Wechselkursen; keine Fortschreibung. Laender- und Geschaeftsrisiken bleiben unterschiedlich.']};summary.available++;
  }else{value.currencyAdjustedContextStatus={state:'missing',reason};summary.missing++;summary.reasons[reason]=(summary.reasons[reason]||0)+1;}
 }
 strict.summary.currencyAdjustedContext=summary;return strict;
}
