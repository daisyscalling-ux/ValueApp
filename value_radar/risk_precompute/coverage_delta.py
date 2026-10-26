"""Compare published coverage snapshots, not investment risk or score changes."""
import datetime as dt
import json
import os
from pathlib import Path
from collections import Counter
from market_priority import market_tier
from yahoo_sector import load, save
UTC=dt.timezone.utc

def timestamp(value):
 try:
  result=dt.datetime.fromisoformat(str(value).replace('Z','+00:00'))
  return result if result.tzinfo else None
 except (ValueError,TypeError):return None

def index(snapshot):
 rows={}
 for row in snapshot.get('stocks',[]):
  symbol=row.get('symbol')
  if not isinstance(symbol,str) or not symbol or symbol in rows:raise ValueError('duplicate_or_invalid_listing')
  rows[symbol]=row
 return rows

def compare(before,after,now=None):
 now=now or dt.datetime.now(UTC)
 result={'schema':1,'generatedAt':now.isoformat(),'previousAsOf':before.get('generatedAt'),'currentAsOf':after.get('generatedAt'),
         'state':'not_comparable','reason':None,'changes':[], 'summary':{},
         'interpretation':'Data availability transitions only. Context-only observations are not complete coverage; no risk score or probability.'}
 old_date=timestamp(before.get('generatedAt'));new_date=timestamp(after.get('generatedAt'))
 if not new_date or not dt.timedelta(0)<=now-new_date<=dt.timedelta(days=2):result['reason']='current_missing_stale_or_future';return result
 if not old_date or not dt.timedelta(0)<new_date-old_date<=dt.timedelta(days=14):result['reason']='baseline_missing_stale_or_not_older';return result
 try:old=index(before);new=index(after)
 except ValueError as e:result['reason']=str(e);return result
 if not old or not new:result['reason']='empty_snapshot';return result
 counts=Counter();markets={}
 for symbol in sorted(old.keys() & new.keys()):
  a=old[symbol].get('domains',{});b=new[symbol].get('domains',{});market=('primary','europe','rotation')[market_tier(symbol)]
  for domain in sorted(a.keys()|b.keys()):
   source=a.get(domain,{}).get('state','missing');target=b.get(domain,{}).get('state','missing')
   framework_changed=domain=='balance' and a.get(domain,{}).get('profile')!=b.get(domain,{}).get('profile')
   if source==target and not framework_changed:continue
   transition='framework_changed' if framework_changed else 'became_available' if target=='available' else 'lost_available' if source=='available' else 'state_changed'
   counts[transition]+=1;markets.setdefault(market,Counter())[transition]+=1
   result['changes'].append({'symbol':symbol,'market':market,'domain':domain,'before':source,'after':target,'transition':transition,'previousProfile':a.get(domain,{}).get('profile') if domain=='balance' else None,'currentProfile':b.get(domain,{}).get('profile') if domain=='balance' else None,'reason':b.get(domain,{}).get('reason')})
 result.update(state='compared',reason=None,addedListings=sorted(new.keys()-old.keys()),removedListings=sorted(old.keys()-new.keys()),
               summary={'transitions':dict(counts),'markets':{k:dict(v) for k,v in markets.items()},'comparableListings':len(old.keys()&new.keys()),'addedListings':len(new.keys()-old.keys()),'removedListings':len(old.keys()-new.keys())})
 return result

def main():
 folder=Path(os.getenv('RISK_DATA_DIR',str(Path(__file__).resolve().parents[1]/'daten')))
 before=load(Path(os.getenv('RISK_COVERAGE_BASELINE','/tmp/risk-coverage-before.json')), {})
 report=compare(before,load(folder/'cf_risk_coverage.json',{}));save(folder/'cf_risk_coverage_changes.json',report)
 print(json.dumps({'state':report['state'],'reason':report['reason'],'summary':report['summary']}))
 if os.getenv('GITHUB_STEP_SUMMARY'):
  with open(os.environ['GITHUB_STEP_SUMMARY'],'a',encoding='utf8') as f:
   f.write('\n## Datenabdeckung: Veraenderung seit dem letzten Lauf\n\n')
   if report['state']!='compared':f.write('Kein belastbarer Vorher-nachher-Vergleich: '+report['reason']+'.\n')
   else:
    c=report['summary']['transitions'];f.write(str(c.get('became_available',0))+' Datenbereiche neu verfuegbar; '+str(c.get('lost_available',0))+' nicht mehr vollstaendig verfuegbar. Dies sind Datenbereiche, keine Anzahl Unternehmen.\n\n')
    f.write('| Markt | Neu verfuegbar | Verfuegbarkeit verloren | Andere Statuswechsel | Branchenpruefung geaendert |\n|---|---:|---:|---:|---:|\n')
    for market,counts in report['summary']['markets'].items():f.write('| '+market+' | '+str(counts.get('became_available',0))+' | '+str(counts.get('lost_available',0))+' | '+str(counts.get('state_changed',0))+' | '+str(counts.get('framework_changed',0))+' |\n')
    f.write('\nNeue und entfernte Notierungen werden separat ausgewiesen; Details in cf_risk_coverage_changes.json.\n')
if __name__=='__main__':main()
