import fs from 'node:fs';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {buildSectorComparisons,seriesCheck} from './sector-comparison';
import {addBroadSectorContext} from './broad-sector-context';
const read=(p:string)=>{try{return JSON.parse(fs.readFileSync(p,'utf8'))}catch{return null}};
export function exportSector(folder='value_radar/daten',cachePath='.risk-sector-series.json',now=Date.now()){
 const universe=read(path.join(folder,'cf_universum.json'));if(!Array.isArray(universe?.kandidaten)||!universe.kandidaten.length)throw Error('Universum fehlt');
 const groups=read(path.join(folder,'cf_peer_groups.json'));
 const metadata=read(path.join(folder,'cf_peer_metadata.json'));
 const cache=read(cachePath),result=addBroadSectorContext(buildSectorComparisons(universe,groups,cache,now),universe,groups,metadata,cache,now);
 const out=path.join(folder,'cf_sector_context.json');fs.writeFileSync(out+'.tmp',JSON.stringify(result));fs.renameSync(out+'.tmp',out);
 const rows=Object.entries(result.stocks).map(([symbol,value]:any)=>({symbol,state:value.state,reason:value.reason,
  group:value.group||null,quality:value.quality||null,peerIssuers:value.peerIssuers??null,
  broaderContext:value.broaderContext?{state:'available',peerIssuers:value.broaderContext.peerIssuers,group:value.broaderContext.group}:value.broaderContextStatus||null,
  membershipOnly: {reason:groups?.listings?.[symbol]?.groupSizeReason||null,
   sameCurrencyPeerIssuers:groups?.listings?.[symbol]?.sameCurrencyPeerIssuerCount??null},
  historyIssue:seriesCheck(cache?.series?.[symbol],now),
  calendarDiagnostic:value.calendarDiagnostic||null,
  nextAction:value.state==='available'?'observe':value.reason==='fewer_than_five_same_currency_issuers'?'group_membership_or_currency_review':
   ['insufficient_common_history','target_calendar_insufficient','no_fresh_common_trading_date'].includes(value.reason)?'calendar_review':
   value.reason==='issuer_or_business_group_unconfirmed'?'identity_review':'history_refresh',
  lastSupplementAttempt:metadata?.attempts?.[symbol]?.at||null,supplementError:metadata?.attempts?.[symbol]?.error||null}));
 const plan={schema:1,generatedAt:result.generatedAt,summary:result.summary,supplementReport:metadata?.report||null,rows};
 const planPath=path.join(folder,'cf_sector_supply_plan.json');fs.writeFileSync(planPath+'.tmp',JSON.stringify(plan));fs.renameSync(planPath+'.tmp',planPath);
 console.log(JSON.stringify(result.summary));return result;
}
if(process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href)exportSector(process.argv[2]||'value_radar/daten',process.env.RISK_SECTOR_STATE||'.risk-sector-series.json');


