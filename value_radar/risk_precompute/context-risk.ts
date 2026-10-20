import {historyStatistics} from './src/lib/risk-statistics';
type Row=Record<string,any>;
const DAY=86400000;
const fresh=(date:any,now:number,days:number)=>typeof date==='string'&&Number.isFinite(Date.parse(date))&&Date.parse(date)<=now&&now-Date.parse(date)<=days*DAY;
const key=(r:Row)=>String(r.listing_symbol||r.ticker||'').toUpperCase();
const issuer=(r:Row)=>r.cik?`cik:${r.cik}`:r.lei?`lei:${r.lei}`:String(r.name_full||r.name||'').toUpperCase().replace(/[^A-Z0-9]/g,'');
export function industryContexts(universe:Row,risk:Row,now:number){
 const inputs=universe.kandidaten||[],counts=new Map<string,number>();
 for(const r of inputs)counts.set(key(r),(counts.get(key(r))||0)+1);
 const valid:Row[]=[];
 for(const r of inputs){
  const k=key(r),canonical=k.includes(':')?k:risk.aliases?.[k],h=risk.stocks?.[canonical],s=historyStatistics(h,now);
  if(counts.get(k)!==1||!canonical||h?.symbol!==canonical||!r.currency||h.currency!==r.currency||!fresh(r.metadata_asof,now,90)||!fresh(h.retrievedAt,now,1.5)||s.drawdown===null||!r.industry||!issuer(r))continue;
  if(!['common_stock','common','stock','equity','dr','adr','ordinary','ordinary_share'].includes(String(r.security_type||'').toLowerCase()))continue;
  valid.push({r,k,issuer:issuer(r),s});
 }
 const result:Record<string,Row>={};
 for(const t of valid){
  const peers=new Map<string,Row>();
  // Same industry/currency, current observations; each issuer gets one vote.
  for(const p of valid){
   if(p.issuer===t.issuer||p.r.industry!==t.r.industry||p.r.currency!==t.r.currency||Math.abs(Date.parse(p.s.last)-Date.parse(t.s.last))>3*DAY)continue;
   const old=peers.get(p.issuer);
   if(!old||Number(p.r.is_primary===true)>Number(old.r.is_primary===true)||p.r.is_primary===old.r.is_primary&&p.k<old.k)peers.set(p.issuer,p);
  }
  const group=[...peers.values()],values=group.map(p=>p.s.drawdown).sort((a,b)=>a-b);
  if(values.length<5){result[t.k]={state:'missing',reason:'fewer_than_five_eligible_issuers',peerIssuers:values.length};continue;}
  const n=values.length,median=n%2?values[(n-1)/2]:(values[n/2-1]+values[n/2])/2;
  result[t.k]={state:'available',reason:'same_industry_currency_drawdown_comparison',industry:t.r.industry,currency:t.r.currency,
   peerIssuers:n,peerSymbols:group.map(p=>p.k).sort(),drawdown:t.s.drawdown,medianDrawdown:median,
   differencePercentagePoints:100*(t.s.drawdown-median),higherDrawdownPercentile:100*values.filter(x=>x<t.s.drawdown).length/n,
   observationDate:t.s.last,interpretation:'Current drawdown versus own recent high; industry cohort, not verified competitors or a sector index. No causal spillover or loss probability.'};
 }
 return result;
}
export function newsContext(symbol:string,archive:Row,now:number){
 const r=archive?.stocks?.[symbol];
 if(archive?.schema!==1||!r)return {state:'not_assessed',reason:'company_news_not_yet_fetched'};
 if(!fresh(r.successAt,now,1.5))return {state:'missing',reason:'company_news_missing_or_stale',lastAttemptAt:r.attemptedAt||null,error:r.error||null,fallbackAttemptAt:r.fallbackAttemptAt||null,fallbackError:r.fallbackError||null};
 const items=Array.isArray(r.items)?r.items.filter((i:Row)=>fresh(i.publishedAt,now,7)):[];
 return {state:items.length?'review_required':'observed_empty',reason:items.length?'headlines_are_unverified_event_candidates':'no_recent_articles_is_not_low_risk',
  checkedAt:r.successAt,lastAttemptError:r.error||null,articleCount:items.length,items:items.slice(0,6),queryIdentifier:r.identifier,rejectedArticles:r.rejectedArticles||0,
  provider:r.source||'ROIC',rawArticleCount:r.rawArticleCount??null,fallbackAttemptAt:r.fallbackAttemptAt||null,fallbackError:r.fallbackError||null,
  truncated:r.truncated===true,score:null,interpretation:'Provider company association; headline tags require verification. No negative headline does not imply safety.'};
}
