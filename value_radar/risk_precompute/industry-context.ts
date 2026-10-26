import {buildSectorComparisons} from './sector-comparison';
type Row=Record<string,any>;
const DAY=86400000;
const norm=(x:any)=>typeof x==='string'?x.trim().toLowerCase().replace(/\s+/g,' '):'';
const fresh=(x:any,now:number)=>typeof x==='string'&&Number.isFinite(Date.parse(x))&&Date.parse(x)<=now&&now-Date.parse(x)<=90*DAY;
/** Intermediate provider-industry context: never silently replace strict peers. */
export function addIndustryContext(strict:Row,universe:Row,groups:Row,cache:Row,now=Date.now()){
 const rows=new Map<string,Row>(),duplicates=new Set<string>();
 for(const r of universe.kandidaten||[]){const key=String(r.listing_symbol||r.ticker||'').toUpperCase();if(rows.has(key))duplicates.add(key);rows.set(key,r);}
 const issuers:Row[]=[],listings:Row={};
 for(const issuer of groups?.issuers||[]){
  const members=(issuer.listings||[]).map((s:string)=>rows.get(s)).filter(Boolean) as Row[];
  // Every listing contributing to the issuer classification must agree. No
  // majority voting, hand-picked companies, stale classification or new alias.
  if(!members.length||members.some(r=>duplicates.has(r.listing_symbol)||!fresh(r.metadata_asof,now)||!norm(r.industry)))continue;
  const industries=new Set(members.map(r=>norm(r.industry)));
  if(industries.size!==1)continue;
  const industry=norm(members[0].industry);if(['unknown','n/a','none'].includes(industry))continue;
  const group='provider-industry:'+industry;
  const selected=(issuer.listings||[]).filter((s:string)=>rows.has(s)&&groups.listings?.[s]?.issuerId===issuer.id);
  if(!selected.length)continue;
  issuers.push({...issuer,listings:selected,classification:{group,label:members[0].industry+' · Branchenkontext',level:'industry_context',source:members[0].metadata_source||'Provider industry classification',observedAt:members.map(r=>r.metadata_asof).sort()[0]}});
  for(const s of selected)listings[s]={...groups.listings[s],group,level:'industry_context'};
 }
 const context=buildSectorComparisons(universe,{...groups,issuers,listings},cache,now,5);
 const summary:Row={available:0,missing:0,reasons:{}};
 for(const [symbol,value] of Object.entries(strict.stocks) as [string,Row][]){
  if(value.state!=='missing'||value.reason!=='fewer_than_five_same_currency_issuers'||value.groupLevel==='reviewed_business_model')continue;
  const c=context.stocks[symbol];
  if(c?.state==='available'){
   value.industryContext={...c,quality:'provider_industry_context',reason:'same_currency_provider_industry',minimumPeers:5,directCompetitorsVerified:false,
    interpretation:'Anbieter-Branche als Vergleichskontext. Breiter als die engere Unterbranche; keine bestaetigten direkten Wettbewerber. Kein Einfluss auf Fair Value oder Risikoscore.'};summary.available++;
  }else{const reason=c?.reason||'industry_context_unavailable';value.industryContextStatus={state:'missing',reason,minimumPeers:5};summary.missing++;summary.reasons[reason]=(summary.reasons[reason]||0)+1;}
 }
 strict.summary.industryContext=summary;return strict;
}
