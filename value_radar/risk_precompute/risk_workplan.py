"""Group outstanding risk work across the universe without inventing coverage."""
from collections import Counter
import datetime as dt
import json
import os
from pathlib import Path
from market_priority import market_tier
from risk_progress import progress,markdown
from yahoo_sector import load,save,recent

def build(coverage,now=None):
 now=now or dt.datetime.now(dt.timezone.utc)
 result={'schema':1,'generatedAt':now.isoformat(),'coverageAsOf':coverage.get('generatedAt'),'state':'blocked','summary':{},'batches':[],
         'interpretation':'Workload and data coverage only. Sector-framework work is not closed by complete book ratios. Smaller markets retained after main markets.'}
 if not recent(coverage.get('generatedAt'),now,2):result['reason']='coverage_missing_or_stale';return result
 rows=coverage.get('stocks',[])
 if not rows:result['reason']='coverage_empty';return result
 keys=[r.get('symbol') for r in rows]
 if any(not isinstance(s,str) or not s for s in keys) or len(set(keys))!=len(keys):result['reason']='duplicate_or_invalid_listing';return result
 groups={};supplemental=Counter();profiles=Counter();peer_context=Counter();open_symbols=set()
 def add(row,kind,reason,owner):
  symbol=row['symbol'];tier=market_tier(symbol);key=(tier,kind,reason)
  group=groups.setdefault(key,{'marketTier':tier,'kind':kind,'reason':reason,'owner':owner,'symbols':set()})
  group['symbols'].add(symbol);open_symbols.add(symbol)
 for row in rows:
  domains=row.get('domains',{});sector=domains.get('sector',{});
  levels=[key for key in ['industryContext','broaderContext','currencyAdjustedContext'] if sector.get(key,{}).get('state')=='available']
  if sector.get('state')=='available':levels.append('strict')
  for level in levels:peer_context[level]+=1
  peer_context['any_context' if levels else 'no_context']+=1
  b=domains.get('balance',{});profiles[b.get('profile','unknown')]+=1
  if b.get('state') in ('missing','partial'):
   for reason in sorted(set(str(b.get('reason') or 'balance_unavailable').split(','))):add(row,'financial_fields',reason,'fundamentals-daily / annual source review')
  for reason in sorted(set(b.get('sectorRequirements',[]))):add(row,'sector_framework',reason,'sector-specific original disclosures')
  rec=b.get('edinetReconciliation') or {}
  if rec.get('state')=='not_aligned':
   for reason in rec.get('reasons',[]):add(row,'source_reconciliation',reason,'compare statement definitions and source periods')
  for name,m in (b.get('supplementalMetrics') or {}).items():
   if m.get('state')=='available':supplemental[name]+=1
  for name,m in (b.get('edinetObservations') or {}).items():
   if m.get('state')=='available':supplemental['EDINET:'+name]+=1
  for domain,owner in [('identity','listing resolution'),('quote','fundamentals-daily quote refresh'),('price','daily-risk price context'),('historical','daily-risk history'),('market','market proxy coverage'),('sector','peer classification and aligned history')]:
   d=domains.get(domain,{})
   if d.get('state')!='available':add(row,domain,d.get('reason') or 'not_assessed',owner)
 for key,g in sorted(groups.items()):result['batches'].append({**g,'symbols':sorted(g['symbols']),'listings':len(g['symbols'])})
 result.update(state='ready',summary={'listings':len(rows),'listingsWithOpenWork':len(open_symbols),'batches':len(groups),
  'mainMarketBatches':sum(x['marketTier']<=1 for x in result['batches']),
  'profiles':dict(profiles),'peerContextCoverage':dict(peer_context),'supplementalObservations':dict(supplemental),
  'byKind':dict(Counter(g['kind'] for g in result['batches']))})
 result['progress']=progress(rows,result['batches'])
 return result

def main():
 folder=Path(os.getenv('RISK_DATA_DIR',str(Path(__file__).resolve().parents[1]/'daten')))
 result=build(load(folder/'cf_risk_coverage.json',{}));save(folder/'cf_risk_workplan.json',result)
 print(json.dumps({'state':result['state'],'summary':result['summary']}))
 if os.getenv('GITHUB_STEP_SUMMARY'):
  with open(os.environ['GITHUB_STEP_SUMMARY'],'a',encoding='utf8') as f:
   f.write('\n## Naechste Arbeitsbloecke fuer das Universum\n\n')
   if result['state']!='ready':f.write('Nicht auswertbar: '+result['reason']+'\n');return
   f.write(markdown(result['progress']))
   f.write('Gruppen koennen dieselben Unternehmen enthalten. Vollstaendige Buchkennzahlen ersetzen keine Branchenpruefung.\n\n| Markt | Aufgabe | Ursache | Notierungen |\n|---|---|---|---:|\n')
   main=[g for g in result['batches'] if g['marketTier']<=1]
   for g in sorted(main,key=lambda x:(x['marketTier'],-x['listings'],x['kind'],x['reason']))[:25]:
    reason=str(g['reason']).replace('|','/').replace('\n',' ')
    f.write('| '+('Primaer' if g['marketTier']==0 else 'Europa')+' | '+g['kind']+' | '+reason+' | '+str(g['listings'])+' |\n')
   f.write('\nVollstaendige Gruppen und zurueckgestellte Maerkte: cf_risk_workplan.json.\n')
if __name__=='__main__':main()
