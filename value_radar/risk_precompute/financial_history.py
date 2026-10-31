"""Retain observed annual and regulatory quarters; never invent historical availability."""
import copy,datetime as dt,hashlib,json,math,os
from pathlib import Path
from collections import Counter
from news_identity import valid_isin
from yahoo_sector import recent,save
IDENTITY=('listing_symbol','ticker','isin','currency','security_type','share_class')
ANNUAL=('netDebtAssets','fcfAssets','bookEquityAssets','netIncomeEndingAssets','operatingCashflowAssets','cashAssets')
def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def finite(v):return isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v)
def date(v):return dt.date.fromisoformat(v)
def period_recent(v,now,days):
 try:return isinstance(v,str) and len(v)==10 and 0<=(now.date()-date(v)).days<=days
 except (ValueError,TypeError):return False
def stamp(v):
 d=dt.datetime.fromisoformat(v.replace('Z','+00:00'))
 if d.tzinfo is None:raise ValueError('timezone_required')
 return d

def observations(balance,now):
 result=[]
 for metric in ANNUAL:
  m=balance.get('metrics',{}).get(metric) or balance.get('supplementalMetrics',{}).get(metric) or {}
  basis=m.get('basis') or {};fields=basis.get('fields') or {}
  if m.get('state')!='available' or not finite(m.get('value')) or not fields or not period_recent(basis.get('period'),now,550):continue
  currency=basis.get('currency');retrieved=basis.get('retrievedAt')
  if not currency or not recent(retrieved,now,7):continue
  if not all(f.get('source') and f.get('end')==basis['period'] and f.get('currency')==currency and recent(f.get('retrievedAt'),now,7) for f in fields.values()):continue
  source={k:f['source'] for k,f in sorted(fields.items())}
  result.append({'metric':metric,'frequency':'annual','period':basis['period'],'currency':currency,'value':m['value'],'method':{'profile':balance.get('profile'),'sources':source,'version':'annual-assets-ratios-v1'},'sourceRetrievedAt':min([retrieved,*[f['retrievedAt'] for f in fields.values()]],key=stamp),'evidence':{'fields':source,'sourceUrl':balance.get('sourceUrl')}})
 c=balance.get('bankCapital') or {}
 if c.get('state')=='available' and period_recent(c.get('period'),now,180):
  for key,m in c.get('metrics',{}).items():
   if m.get('state')=='available' and m.get('unit')=='fraction' and finite(m.get('value')):
    result.append({'metric':key,'frequency':'quarterly','period':c['period'],'currency':'RATIO','value':m['value'],'method':{'rssdId':c['rssdId'],'sourceField':m['sourceField'],'version':'FRY9C-capital-v1'},'sourceRetrievedAt':c['sourceImportedAt'],'evidence':{'sourceUrl':c['sourceUrl'],'sourceFileSha256':c['sourceFileSha256']}})
  q=c.get('creditQuality') or {}
  if q.get('state')=='available' and q.get('period')==c['period']:
   for key,value in q.get('ratios',{}).items():
    if finite(value):result.append({'metric':key,'frequency':'quarterly','period':q['period'],'currency':'RATIO','value':value,'method':{'rssdId':c['rssdId'],'version':q['method']},'sourceRetrievedAt':q['sourceImportedAt'],'evidence':{'sourceUrl':q['sourceUrl'],'sourceFileSha256':q['sourceFileSha256']}})
 return result

def build(coverage,universe,previous,now=None):
 now=now or dt.datetime.now(dt.timezone.utc)
 if coverage.get('schema')!=1 or not recent(coverage.get('generatedAt'),now,1.5):raise ValueError('coverage_missing_or_stale')
 if previous and (previous.get('schema')!=1 or previous.get('method')!='observed-financial-history-v1' or not isinstance(previous.get('series'),dict)):raise ValueError('unsupported_history_archive')
 if previous and stamp(previous['lastCoverageAt'])>stamp(coverage['generatedAt']):raise ValueError('out_of_order_coverage')
 archive=copy.deepcopy(previous) if previous else {'schema':1,'method':'observed-financial-history-v1','series':{}}
 for key,series in archive['series'].items():
  expected=digest({'identity':digest(series['identity']),'metric':series['metric'],'frequency':series['frequency'],'currency':series['currency'],'method':series['method']})
  if key!=expected:raise ValueError('history_identity_key_mismatch')
  for period,entry in series['periods'].items():
   if date(period)>now.date() or not entry['revisions']:raise ValueError('invalid_history_period')
   if any(not finite(v['value']) or stamp(v['observedAt'])>now or stamp(v['sourceRetrievedAt'])>stamp(v['observedAt']) for v in entry['revisions']):raise ValueError('invalid_history_revision')
 report=copy.deepcopy(coverage);counts=Counter();inputs={};duplicates=set()
 for r in universe.get('kandidaten',[]):
  s=r.get('listing_symbol')
  if s in inputs:duplicates.add(s)
  inputs[s]=r
 seen=set()
 for row in report.get('stocks',[]):
  s=row.get('symbol')
  if s in seen:raise ValueError('duplicate_coverage_listing')
  seen.add(s);r=inputs.get(s,{});b=row.get('domains',{}).get('balance',{})
  summary={'state':'missing','reason':'qualified_identity_or_observations_missing','metrics':[],'pointInTimeUsable':False}
  b['history']=summary
  if s in duplicates or row.get('domains',{}).get('identity',{}).get('state')!='available' or not valid_isin(r.get('isin')):continue
  identity={k:r.get(k) for k in IDENTITY};identity_hash=digest(identity)
  for observation in observations(b,now):
   if stamp(observation['sourceRetrievedAt'])>now or date(observation['period'])>now.date():continue
   key=digest({'identity':identity_hash,'metric':observation['metric'],'frequency':observation['frequency'],'currency':observation['currency'],'method':observation['method']})
   series=archive['series'].setdefault(key,{'identity':identity,'metric':observation['metric'],'frequency':observation['frequency'],'currency':observation['currency'],'method':observation['method'],'periods':{}})
   periods=series['periods'];period=observation['period'];entry=periods.get(period)
   revision={k:observation[k] for k in ('value','sourceRetrievedAt','evidence')};revision['observedAt']=now.isoformat()
   if entry is None:periods[period]={'firstObservedAt':now.isoformat(),'lastVerifiedSourceAt':revision['sourceRetrievedAt'],'revisions':[revision]};counts['newPeriods']+=1
   else:
    latest=entry['revisions'][-1]
    if revision['value']!=latest['value']:
     if stamp(revision['sourceRetrievedAt'])<=stamp(entry.get('lastVerifiedSourceAt',latest['sourceRetrievedAt'])):counts['conflictingOrOlderRevisions']+=1;continue
     entry['revisions'].append(revision);counts['revisions']+=1
    if stamp(revision['sourceRetrievedAt'])>stamp(entry.get('lastVerifiedSourceAt',latest['sourceRetrievedAt'])):entry['lastVerifiedSourceAt']=revision['sourceRetrievedAt']
   retention=32 if observation['frequency']=='quarterly' else 12
   for expired in sorted(periods)[:-retention]:del periods[expired];counts['retentionPruned']+=1
   prior=[p for p in sorted(periods) if p<period]
   current=periods[period]['revisions'][-1]
   view={'metric':observation['metric'],'frequency':observation['frequency'],'currency':observation['currency'],'period':period,'value':current['value'],'periodCount':len(periods),'firstObservedAt':periods[period]['firstObservedAt'],'revisionCount':len(periods[period]['revisions'])-1,'state':'one_period','changePercentagePoints':None,'previousPeriod':None,'previousValue':None}
   if prior:
    p=prior[-1];days=(date(period)-date(p)).days;lo,hi=(70,110) if observation['frequency']=='quarterly' else (300,430)
    if lo<=days<=hi:
     value=periods[p]['revisions'][-1]['value'];view.update(state='comparable',previousPeriod=p,previousValue=value,changePercentagePoints=(current['value']-value)*100);counts['comparableMetrics']+=1
    else:view['state']='period_gap'
   summary['metrics'].append(view)
  if summary['metrics']:
   summary.update(state='available',reason='observed_periods_only');counts['listingsWithHistory']+=1
 archive.update(lastCoverageAt=coverage['generatedAt'],summary=dict(counts),pointInTimeUsable=False)
 return archive,report

def main():
 folder=Path(os.getenv('RISK_DATA_DIR',str(Path(__file__).resolve().parents[1]/'daten')))
 def read(path,default=None):return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default
 path=folder/'cf_financial_history.json'
 archive,report=build(read(folder/'cf_risk_coverage.json',{}),read(folder/'cf_universum.json',{}),read(path,{}))
 save(path,archive);save(folder/'cf_risk_coverage.json',report);print(json.dumps(archive['summary']))
 if os.getenv('GITHUB_STEP_SUMMARY'):
  with open(os.environ['GITHUB_STEP_SUMMARY'],'a',encoding='utf-8') as f:f.write('\n## Finanzverlauf\n'+str(archive['summary'].get('listingsWithHistory',0))+' Notierungen mit gespeicherten Beobachtungen; '+str(archive['summary'].get('comparableMetrics',0))+' vergleichbare Kennzahlenpaare. Einzelne Perioden sind noch kein Verlauf. Ursprünglicher Veröffentlichungstag nicht unterstellt.\n')
if __name__=='__main__':main()


