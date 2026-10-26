import {withEdinetCashflow} from './edinet-context';
import {assessBalanceSnapshot} from './balance-profile';
import {industryContexts,newsContext} from './context-risk';
import {selectSectorComparison} from './sector-comparison';
import {historyStatistics} from './src/lib/risk-statistics';
import {marketProxy} from './worker/risk-benchmark';
import {marketTier,rotationDue} from './market-priority';
type Row=Record<string,any>;
const DAY=86400000;
const number=(v:any)=>typeof v==='number'&&Number.isFinite(v);
const currency=(v:any)=>['GBp','GBX'].includes(v)?'GBP':v;
const recent=(v:any,now:number,days:number)=>typeof v==='string'&&Number.isFinite(Date.parse(v))&&Date.parse(v)<=now&&now-Date.parse(v)<=days*DAY;
const status=(state:string,reason:string,extra:Row={})=>({state,reason,...extra});
export const listingKey=(r:Row)=>String(r.listing_symbol||r.ticker||'').trim().toUpperCase();
export function failureState(message:string,old:Row|undefined,now:number){
 const category=/401|403/.test(message)?'access':/402/.test(message)?'subscription':/429/.test(message)?'rate_limit':/Notierung|Währung|eindeutig/.test(message)?'identity':/200|zwei Handelsjahre|Lücken|nicht aktuell|Zukunft/.test(message)?'history_quality':'provider';
 const count=Math.min(20,(old?.category===category&&Number.isInteger(old.count)&&old.count>=0?old.count:0)+1);
 const hours=category==='identity'?168:category==='subscription'?168:category==='access'?24:category==='history_quality'?24:Math.min(24,2**count);
 return {category,count,at:new Date(now).toISOString(),nextAttemptAt:new Date(now+hours*3600000).toISOString()};
}
export function retryDue(state:Row|undefined,now:number){
 // Invalid or implausibly remote dates must not permanently suppress a listing.
 const t=Date.parse(state?.nextAttemptAt);return !Number.isFinite(t)||t<=now||t>now+8*DAY;
}
export function auditUniverse(universe:Row,risk:Row,fundamentals:Record<string,Row>,now=Date.now(),fundamentalIndex:Row={},news:Row={},sectorReport?:Row|null,roicArchive?:Row|null,edinetArchive?:Row|null){
 if(!Array.isArray(universe?.kandidaten)||!universe.kandidaten.length)throw Error('Universum fehlt');
 const grouped=new Map<string,Row[]>();let invalidRows=0;
 for(const r of universe.kandidaten){const key=listingKey(r);if(!/^[A-Z0-9._:-]{1,100}$/.test(key)){invalidRows++;continue}grouped.set(key,[...(grouped.get(key)||[]),r]);}
 const industries=new Map<string,Set<string>>();
 for(const [key,rows] of grouped){const r=rows[0];if(r.industry&&recent(r.metadata_asof,now,90))industries.set(r.industry,new Set([...(industries.get(r.industry)||[]),key]));}
 const sectorContexts=sectorReport===undefined?industryContexts(universe,risk,now):{};
 const stocks:Row[]=[];const jobs:Row[]=[];const markets:Row={};
 for(const [key,rows] of grouped){
  const r=rows[0],currencies=new Set(rows.map(x=>x.currency).filter(Boolean));
  const conflict=currencies.size>1;
  const canonical=key.includes(':')?key:risk.aliases?.[key];
  const h=risk.stocks?.[canonical||key];
  const identityOK=!conflict&&!!canonical&&(!h||h.symbol===canonical)&&(!h?.currency||!r.currency||currency(h.currency)===currency(r.currency));
  const s=identityOK?historyStatistics(h,now):historyStatistics(null,now);
  const retrieved=recent(h?.retrievedAt,now,1.5);
  const context=identityOK&&retrieved&&s.drawdown!==null;
  const history=identityOK&&retrieved&&s.es!==null;
  const input=fundamentals[key]||fundamentals[canonical||''];
  // The collector stores the requested exact listing (e.g. RR.L), while
  // history resolution stores its verified exchange symbol (LSE:RR.).
  const f=identityOK&&[key,canonical].includes(input?.symbol)?input:null;
  const rawRoic=roicArchive?.schema===1?roicArchive.stocks?.[key]:null;
  const identityFields=['listing_symbol','ticker','isin','currency','security_type','share_class'];
  const roic=rawRoic&&rows.every(x=>identityFields.every(k=>(rawRoic.inputIdentity?.[k]??null)===(x[k]??null)))
    &&!['expired','input_mismatch'].includes(r.listing_reference_status)?rawRoic:undefined;
  const baseBalance=assessBalanceSnapshot(r,f,identityOK,now,roic);
  const sameIdentity=rows.every(x=>identityFields.every(k=>(x[k]??null)===(r[k]??null)));
  const balance=withEdinetCashflow(baseBalance,r,edinetArchive,identityOK&&sameIdentity,now);
  const quote=f?.market,quoteOK=recent(quote?.quote_at,now,7)&&number(quote?.fields?.price)&&quote.fields.price>0&&currency(quote.currency)===currency(r.currency);
  const proxy=marketProxy(String(r.country||'')),benchmark=proxy?risk.benchmarks?.[proxy]:null;
  const market=benchmark&&recent(benchmark.retrievedAt,now,1.5)&&historyStatistics(benchmark,now).drawdown!==null;
  const peers=r.industry&&recent(r.metadata_asof,now,90)?(industries.get(r.industry)?.size||0)-1:0;
  const domains={
   identity:status(identityOK?'available':'blocked',conflict?'conflicting_listing_currency':identityOK?'qualified_listing':'unresolved_or_mismatched_listing'),
   quote:status(identityOK&&quoteOK?'available':'missing','dated_same_currency_quote_required'),
   price:status(context?'available':h?'stale_or_invalid':'missing',s.error||(!retrieved?'retrieval_missing_or_stale':'current_drawdown'),{observations:s.observations,last:s.last}),
   historical:status(history?'available':'missing',s.error||(!retrieved?'retrieval_missing_or_stale':'historical_loss_statistics')),
   balance,
   market:status(market?'available':proxy?'missing':'unsupported',proxy||'country_proxy_not_mapped',{proxy,interpretation:'Country ETF; may include FX exposure, not an issuer beta or local index return.'}),
   sector:!identityOK?status('missing','listing_identity_unverified'):sectorReport!==undefined?
    selectSectorComparison(sectorReport as Row,key,r,now)||status('missing','aligned_sector_report_missing_or_stale'):
    sectorContexts[key]||status(peers>=5?'context_only':'missing','industry_classification_only_not_verified_competitors',{industry:r.industry||null,peerListings:Math.max(0,peers)}),
   news:identityOK?newsContext(key,news,now):status('not_assessed','listing_identity_unverified')
  };
  stocks.push({symbol:key,name:r.name||key,country:r.country||null,domains,score:null,scoreStatus:'coverage_audit_not_calibrated_score'});
  const tier=marketTier(key),marketGroup=tier===0?'primary':tier===1?'europe':'rotation';
  const bucket=markets[marketGroup]??={listings:0,domains:{}};bucket.listings++;
  for(const [domain,d] of Object.entries(domains) as any){bucket.domains[domain]??={};bucket.domains[domain][d.state]=(bucket.domains[domain][d.state]||0)+1;}
  const add=(kind:string,owner:string,reason:string,severity:number,automatic:boolean)=>{
   const prior=kind==='history'?risk.retryState?.[key]:kind==='fundamentals'?{nextAttemptAt:fundamentalIndex.failures?.[key]?.next_attempt_at}:null;
   jobs.push({id:kind+':'+key,symbol:key,kind,owner,reason,severity,marketTier:marketTier(key),
    state:!identityOK&&(!!canonical||conflict)?'identity_review':!automatic?'review_required':retryDue(prior,now)?'queued':'cooldown',
    lastAttemptAt:kind==='history'?risk.attempts?.[key]||null:fundamentalIndex.attempts?.[key]||f?.retrieved_at||null,nextAttemptAt:prior?.nextAttemptAt||null});
  };
  if(!identityOK)add('identity',!canonical&&!conflict?'daily-risk':'review','listing_identity',100,!canonical&&!conflict);
  if(!context||!history)add('history','daily-risk',!context?'current_history_missing':'long_history_missing',!context?90:60,true);
  if(balance.needsFinancialRefresh||balance.refreshDue||!quoteOK)add('fundamentals','fundamentals-daily',balance.needsFinancialRefresh?balance.reason:balance.refreshDue?'annual_refresh_before_expiry':'quote_missing_or_stale',balance.refreshDue?85:80,true);
  if(balance.sectorRequirements.length)add('sector_financials','review',balance.sectorRequirements.join(','),70,false);
  if(!market)add('market','daily-risk',proxy?'benchmark_missing':'unsupported_market',70,!!proxy);
  if(domains.sector.state!=='available')add('sector','review','eligible_industry_history_missing',30,false);
  if(domains.sector.quality==='provisional_industry')add('peer_classification','review','business_model_not_individually_verified',25,false);
  if(['not_assessed','missing'].includes(domains.news.state))add('news','daily-risk','company_news_missing_or_stale',20,identityOK);
 }
 jobs.sort((a,b)=>{
  return Number(rotationDue(b.lastAttemptAt,now))-Number(rotationDue(a.lastAttemptAt,now))||a.marketTier-b.marketTier||b.severity-a.severity||(Date.parse(a.lastAttemptAt)||0)-(Date.parse(b.lastAttemptAt)||0)||a.id.localeCompare(b.id);
 });
 const domains:Row={};for(const r of stocks)for(const [key,d] of Object.entries(r.domains) as any){domains[key]??={};domains[key][d.state]=(domains[key][d.state]||0)+1;}
 return {schema:1,generatedAt:new Date(now).toISOString(),universeAsOf:universe.stand||null,
  summary:{inputRows:universe.kandidaten.length,uniqueListings:stocks.length,duplicateRows:universe.kandidaten.length-invalidRows-stocks.length,invalidRows,domains,markets,
   queue:jobs.reduce((a:Row,j:Row)=>(a[j.state]=(a[j.state]||0)+1,a),{})},stocks,jobs,
  limitations:['Data coverage is not a risk probability or a new score.','Current annual data is not a historical point-in-time backtest.',
   'Listing duplicates are removed; ADRs and ordinary shares remain separate listings.','Available annual ratios do not reconcile all leases, capital claims or issuer-specific definitions.']};
}

