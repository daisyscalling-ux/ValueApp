/** Descriptive, point-in-time cohort comparison. Never a probability or calibrated score. */
type Row=Record<string,any>;
export const SECTOR_VERSION=1;
const DAY=86400000;
const num=(v:any)=>typeof v==='number'&&Number.isFinite(v);
export const currencyUnit=(v:any)=>['GBp','GBX'].includes(v)?'GBP':v;
const date=(v:any)=>typeof v==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(v)&&Number.isFinite(Date.parse(v))&&new Date(Date.parse(v)).toISOString().slice(0,10)===v;
const fresh=(v:any,now:number,days:number)=>typeof v==='string'&&Number.isFinite(Date.parse(v))&&Date.parse(v)<=now&&now-Date.parse(v)<=days*DAY;
const median=(v:number[])=>{const a=[...v].sort((x,y)=>x-y),i=Math.floor(a.length/2);return a.length%2?a[i]:(a[i-1]+a[i])/2};
const quantile=(v:number[],p:number)=>{const a=[...v].sort((x,y)=>x-y),i=(a.length-1)*p,lo=Math.floor(i);return a[lo]+(a[Math.ceil(i)]-a[lo])*(i-lo)};
export function seriesCheck(h:Row|undefined,now:number){
 if(!h||h.schema!==1||h.format!=='sector-series'||h.adjustment!=='total_return'||typeof h.symbol!=='string'||!h.currency||!Array.isArray(h.points))return 'series_missing_or_invalid';
 if(!fresh(h.retrievedAt,now,1.5))return 'series_stale';
 const midnight=new Date(now).setUTCHours(0,0,0,0);let previous='';
 for(const p of h.points){if(!Array.isArray(p)||p.length!==2||!date(p[0])||p[0]<=previous||Date.parse(p[0])>=midnight||!num(p[1])||p[1]<=0)return 'invalid_or_duplicate_prices';previous=p[0]}
 if(h.points.length<200||h.points.length>400)return 'insufficient_observations';
 if(!fresh(previous,now,7))return 'last_price_stale';
 if(Date.parse(previous)-Date.parse(h.points[0][0])<365*DAY)return 'less_than_one_year';
 if(h.points.some((p:any,i:number)=>i>0&&Date.parse(p[0])-Date.parse(h.points[i-1][0])>14*DAY))return 'history_gap';
 return null;
}
export function compactSectorSeries(h:Row,now=Date.now()):Row{
 if(h.adjustment!=='total_return'||!Array.isArray(h.bars))throw Error('Sektorvergleich: bereinigte Kursreihe fehlt.');
 const points=new Map<string,number>();
 for(const b of h.bars){if(!date(b.date)||!num(b.close)||b.close<=0||points.has(b.date)&&points.get(b.date)!==b.close)throw Error('Sektorvergleich: widersprüchliche Kursdaten.');points.set(b.date,b.close)}
 const out={schema:1,format:'sector-series',symbol:h.symbol,currency:h.currency,adjustment:h.adjustment,
  retrievedAt:h.retrievedAt,provider:h.provider||'ROIC',points:[...points].sort((a,b)=>a[0].localeCompare(b[0])).slice(-400)};
 const error=seriesCheck(out,now);if(error)throw Error('Sektorvergleich: '+error);return out;
}
export function sectorSeriesFresh(h:Row|undefined,now=Date.now()){return !seriesCheck(h,now)}
const key=(r:Row)=>String(r.listing_symbol||r.ticker||'').toUpperCase();
const identity=(r:Row)=>Object.fromEntries(['isin','currency','industry','sub_industry','name_full','security_type'].map(k=>[k,r[k]??null]));
const matches=(a:Row,b:Row)=>Object.keys(identity(a)).every(k=>(a[k]??null)===(b?.[k]??null));
const iso=(n:number)=>new Date(n).toISOString().slice(0,10);
function anchor(dates:string[],wanted:number,tolerance=7){return [...dates].reverse().find(d=>Date.parse(d)<=wanted&&wanted-Date.parse(d)<=tolerance*DAY)}
function metrics(points:Map<string,number>,dates:string[],end:string){
 const finish=Date.parse(end),start=anchor(dates,finish-365*DAY);
 if(!start)return null;
 const common=dates.filter(d=>d>=start&&d<=end);if(common.length<200)return null;
 if(common.some((d,i)=>i>0&&Date.parse(d)-Date.parse(common[i-1])>14*DAY))return null;
 const returns:Row={};for(const [label,days] of [['oneMonth',30],['threeMonths',90],['sixMonths',180]] as const){
  const a=anchor(common,finish-days*DAY);if(!a)return null;returns[label]={value:points.get(end)!/points.get(a)!-1,from:a,to:end};
 }
 const weekly:string[]=[];for(let i=52;i>=0;i--){const d=anchor(common,finish-i*7*DAY,4);if(!d||weekly.includes(d))return null;weekly.push(d)}
 const log=weekly.slice(1).map((d,i)=>Math.log(points.get(d)!/points.get(weekly[i])!)),mean=log.reduce((a,b)=>a+b,0)/log.length;
 const volatility=Math.sqrt(log.reduce((a,b)=>a+(b-mean)**2,0)/(log.length-1))*Math.sqrt(52);
 let peak=points.get(start)!,maxDrawdown=0;
 for(const d of common){const v=points.get(d)!;peak=Math.max(peak,v);maxDrawdown=Math.max(maxDrawdown,1-v/peak)}
 return {returns,volatility,maxDrawdown,drawdown:1-points.get(end)!/peak,from:start,to:end,observations:common.length,weeklyObservations:weekly.length};
}
export function buildSectorComparisons(universe:Row,groups:Row,cache:Row,now=Date.now()):Row{
 const stocks:Record<string,Row>={},excluded= (reason:string,extra:Row={})=>({method:'aligned-cohort-v1',state:'missing',reason,score:null,...extra});
 const rows=Array.isArray(universe?.kandidaten)?universe.kandidaten:[],counts=new Map<string,number>();for(const r of rows)counts.set(key(r),(counts.get(key(r))||0)+1);
 const sources=new Map<string,Row>(rows.map((r:Row)=>[key(r),r])),all=cache?.schema===1?cache.series||{}:{};
 const groupOK=groups?.schema===1&&groups.method==='issuer-business-groups-v1'&&fresh(groups.generatedAt,now,1.5)&&Array.isArray(groups.issuers);
 const members=new Map<string,Row[]>();
 if(groupOK)for(const issuer of groups.issuers){const g=issuer.classification?.group;if(g)members.set(g,[...(members.get(g)||[]),issuer])}
 function eligible(s:string){
  const r=sources.get(s),g=groups?.listings?.[s],h=all[s];
  if(!r||counts.get(s)!==1||!g||!g.inputIdentity||!matches(r,g.inputIdentity))return 'membership_identity_mismatch';
  if(!h||h.symbol!==s)return 'series_missing_or_wrong_listing';
  if(!r.currency||currencyUnit(h.currency)!==currencyUnit(r.currency))return 'series_currency_mismatch';
  return seriesCheck(h,now);
 }
 for(const r of rows){
  const symbol=key(r),membership=groups?.listings?.[symbol];
  if(!groupOK){stocks[symbol]=excluded('group_snapshot_missing_or_stale');continue}
  if(!membership){stocks[symbol]=excluded('issuer_or_business_group_unconfirmed');continue}
  const base={group:membership.group,groupLevel:membership.level,currency:currencyUnit(r.currency),
   directCompetitorsVerified:false,quality:membership.level==='reviewed_business_model'?'reviewed_business_model':membership.level==='provider_subindustry'?'provider_subindustry':'provisional_industry',
   classificationConfidence:membership.level==='reviewed_business_model'?'medium':'low'};
  const error=eligible(symbol);if(error){stocks[symbol]=excluded(error,base);continue}
  const candidates=members.get(membership.group)||[],chosen:Row[]=[],excludedPeers:Record<string,number>={},issuerIds=new Set<string>();
  for(const issuer of candidates){
   if(issuer.id===membership.issuerId)continue;
   if(issuerIds.has(issuer.id)){excludedPeers.duplicate_issuer=(excludedPeers.duplicate_issuer||0)+1;continue}issuerIds.add(issuer.id);
   const listings=Array.isArray(issuer.listings)?issuer.listings:[];
   const sameCurrency=listings.filter((s:string)=>currencyUnit(sources.get(s)?.currency)===base.currency);
   const valid=sameCurrency.filter((s:string)=>!eligible(s)&&groups.listings[s].issuerId===issuer.id&&groups.listings[s].group===membership.group);
   valid.sort((a:string,b:string)=>Number(b===issuer.representative)-Number(a===issuer.representative)||a.localeCompare(b));
   if(!valid.length){const reason=sameCurrency.length?'history_or_identity_unavailable':'different_currency';excludedPeers[reason]=(excludedPeers[reason]||0)+1;continue}
   chosen.push({symbol:valid[0],id:issuer.id,history:all[valid[0]],country:sources.get(valid[0])?.country||null});
  }
  const detail={...base,peerIssuers:chosen.length,eligibleGroupIssuers:issuerIds.size,excludedPeers,
    peerSymbols:chosen.map(p=>p.symbol).sort(),peerCountries:[...new Set(chosen.map(p=>p.country).filter(Boolean))].sort()};
  if(chosen.length<5){stocks[symbol]=excluded('fewer_than_five_same_currency_issuers',detail);continue}
  const series=[all[symbol],...chosen.map(p=>p.history)],maps=series.map(h=>new Map<string,number>(h.points));
  const dates=[...maps[0].keys()].filter(d=>maps.every(m=>m.has(d))).sort(),end=dates.at(-1);
  if(!end||!fresh(end,now,7)){stocks[symbol]=excluded('no_fresh_common_trading_date',detail);continue}
  const stats=maps.map(m=>metrics(m,dates,end));
  if(stats.some(s=>s===null)){stocks[symbol]=excluded('insufficient_common_history',detail);continue}
  const target=stats[0]!,peers=stats.slice(1) as NonNullable<ReturnType<typeof metrics>>[];
  const comparisons:Row={};
  for(const label of ['oneMonth','threeMonths','sixMonths']){
   const values=peers.map(p=>p.returns[label].value),value=target.returns[label].value;
   comparisons[label]={...target.returns[label],peerMedian:median(values),peerQ25:quantile(values,.25),peerQ75:quantile(values,.75),
    differencePercentagePoints:100*(value-median(values)),belowZeroShare:values.filter(v=>v<0).length/values.length,
    strengthPercentile:100*(values.filter(v=>v<value).length+.5*values.filter(v=>v===value).length)/values.length};
  }
  const measure=(field:'volatility'|'drawdown'|'maxDrawdown')=>{const values=peers.map(p=>p[field]),value=target[field];return {value,peerMedian:median(values),differencePercentagePoints:100*(value-median(values)),higherRiskPercentile:100*(values.filter(v=>v<value).length+.5*values.filter(v=>v===value).length)/values.length}};
  const drawdown=measure('drawdown');
  stocks[symbol]={method:'aligned-cohort-v1',state:'available',reason:'same_currency_common_dates',...detail,inputIdentity:identity(r),
   groupLabel:candidates.find(i=>i.id===membership.issuerId)?.classification?.label||membership.group,
   observationDate:end,window:{from:target.from,to:end,commonObservations:target.observations,weeklyObservations:target.weeklyObservations},
   returns:comparisons,volatility:measure('volatility'),maxDrawdown:measure('maxDrawdown'),currentDrawdown:drawdown,
   drawdown:drawdown.value,medianDrawdown:drawdown.peerMedian,differencePercentagePoints:drawdown.differencePercentagePoints,
   sourceDates:{oldestRetrieval:series.map(h=>h.retrievedAt).sort()[0],groupGeneratedAt:groups.generatedAt},score:null,
   interpretation:'Descriptive peer medians, not a sector index, causal effect or loss probability. Current membership is not a historical investable universe.',
   warnings:[...(membership.level==='reviewed_business_model'?[]:['Business models not individually verified; provisional context.']),
    'Same trading currency does not remove underlying business FX or country exposure.',
    'Weekly historical volatility is not a forecast; sparse common dates can understate intraperiod drawdowns.']};
 }
 const summary:Row={inputListings:rows.length,states:{},reasons:{},quality:{}};
 for(const r of Object.values(stocks)){summary.states[r.state]=(summary.states[r.state]||0)+1;summary.reasons[r.reason]=(summary.reasons[r.reason]||0)+1;if(r.state==='available')summary.quality[r.quality]=(summary.quality[r.quality]||0)+1}
 return {schema:SECTOR_VERSION,method:'aligned-cohort-v1',generatedAt:new Date(now).toISOString(),summary,stocks};
}
export function selectSectorComparison(report:Row,symbol:string,row:Row,now=Date.now()){
 if(report?.schema!==SECTOR_VERSION||report.method!=='aligned-cohort-v1'||!fresh(report.generatedAt,now,1.5))return null;
 const r=report.stocks?.[symbol];if(!r||r.method!=='aligned-cohort-v1')return null;
 if(r.state==='available'&&(!fresh(r.observationDate,now,7)||currencyUnit(row.currency)!==r.currency||!matches(row,r.inputIdentity)))return null;
 return r;
}
