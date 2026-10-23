import {buildSectorComparisons} from './sector-comparison';
type Row=Record<string,any>;
const DAY=86400000;
const fields=['listing_symbol','ticker','isin','currency','name_full','name','security_type','share_class'];
const labels:Record<string,string>={'technology':'Technologie','financial-services':'Finanzdienstleistungen','healthcare':'Gesundheit',
 'industrials':'Industrie','consumer-cyclical':'Zyklischer Konsum','consumer-defensive':'Basiskonsum','energy':'Energie',
 'basic-materials':'Grundstoffe','communication-services':'Kommunikationsdienste','utilities':'Versorger','real-estate':'Immobilien'};
const key=(r:Row)=>String(r.listing_symbol||r.ticker||'').toUpperCase();
/** Separate broad sector context. Never replaces or upgrades strict peer coverage. */
export function addBroadSectorContext(strict:Row,universe:Row,groups:Row,metadata:Row,cache:Row,now=Date.now()){
 const rows=new Map<string,Row>((universe.kandidaten||[]).map((r:Row)=>[key(r),r]));
 const listings:Row={},issuers:Row[]=[];
 for(const issuer of groups?.issuers||[]){
  const profiles:Row[]=[];
  for(const symbol of issuer.listings||[]){
   const row=rows.get(symbol),p=metadata?.profiles?.[symbol];
   if(!row||!p||p.source!=='Yahoo Finance'||!labels[p.sectorKey]||p.evidence?.symbol!==row.ticker)continue;
   const at=Date.parse(p.retrievedAt);
   if(!Number.isFinite(at)||at>now||now-at>30*DAY||!fields.every(f=>(row[f]??null)===(p.inputIdentity?.[f]??null)))continue;
   profiles.push(p);
  }
  const sectors=new Set(profiles.map(p=>p.sectorKey));
  // Conflicting or missing provider sector classifications are not guessed.
  if(sectors.size!==1)continue;
  const sector=profiles[0].sectorKey,group='broad-yahoo:'+sector;
  const classification={group,label:labels[sector]+' · breiter Sektor',level:'broad_sector_context',
   source:'Yahoo Finance · verifizierte Unternehmensprofile',observedAt:profiles.map(p=>p.retrievedAt).sort()[0]};
  const members=(issuer.listings||[]).filter((s:string)=>rows.has(s)&&groups.listings?.[s]?.issuerId===issuer.id);
  if(!members.length)continue;
  issuers.push({...issuer,listings:members,classification});
  for(const s of members)listings[s]={...groups.listings[s],group,level:'broad_sector_context'};
 }
 const broadGroups={...groups,listings,issuers};
 const broad=buildSectorComparisons(universe,broadGroups,cache,now,10);
 const summary:Row={available:0,missing:0,reasons:{}};
 for(const [symbol,value] of Object.entries(strict.stocks) as [string,Row][]){
  if(value.state!=='missing'||value.reason!=='fewer_than_five_same_currency_issuers')continue;
  const context=broad.stocks[symbol];
  if(context?.state==='available'){
   value.broaderContext={...context,quality:'broad_sector_context',reason:'same_currency_broad_sector',minimumPeers:10,
    interpretation:'Breiter Sektorkontext, kein Vergleich direkter Wettbewerber. Ohne Einfluss auf Fair Value oder Risikoscore.',
    warnings:['Unterschiedliche Geschäftsmodelle innerhalb desselben Anbietersektors; keine bestätigten Konkurrenten.',
     'Gleiche Handelswährung beseitigt keine Länder- oder wirtschaftlichen Währungsrisiken.',
     'Historische Beschreibung; weder Verlustprognose noch investierbarer Sektorindex.']};
   summary.available++;
  }else{
   const reason=context?.reason||'broad_sector_unavailable';
   value.broaderContextStatus={state:'missing',reason,minimumPeers:10};
   summary.missing++;summary.reasons[reason]=(summary.reasons[reason]||0)+1;
  }
 }
 strict.summary.broaderContext=summary;
 return strict;
}

