"""Independent annual SEC cashflow context; never a substitute for full capex."""
import copy,datetime as dt,json,math,os,re,sys,time,urllib.error,urllib.request
from collections import Counter
from pathlib import Path
from news_identity import valid_isin,canonical_names
from roic_risk_annual import identity,safe_error
from yahoo_sector import recent,save
from market_priority import fetch_priority
SOURCE='SEC companyfacts / annual cash PPE context v1'
METHOD='sec-cashflow-history-v1'
TAGS={'assets':'Assets','ocf':'NetCashProvidedByUsedInOperatingActivities','ppe':'PaymentsToAcquirePropertyPlantAndEquipment'}

def normalize(data,cik,now):
 if str(data.get('cik','')).lstrip('0')!=str(cik).lstrip('0'):raise ValueError('cik_mismatch')
 groups={};conflicts=set()
 for key,tag in TAGS.items():
  for f in data.get('facts',{}).get('us-gaap',{}).get(tag,{}).get('units',{}).get('USD',[]):
   try:
    end=dt.date.fromisoformat(f['end']);filed=dt.date.fromisoformat(f['filed']);value=f['val'];acc=f['accn']
    if f.get('form') not in ('10-K','10-K/A') or not re.fullmatch(r'\d{10}-\d{2}-\d{6}',acc) or not 0<=(now.date()-end).days<=8*366 or not end<=filed<=now.date():continue
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):continue
    if key!='assets' and not 330<=(end-dt.date.fromisoformat(f['start'])).days<=400:continue
    group=(str(end),str(filed),acc);item=(value,f.get('start') if key!='assets' else None)
    g=groups.setdefault(group,{})
    if key in g and g[key]!=item:conflicts.add(group)
    g[key]=item
   except (KeyError,ValueError,TypeError):continue
 candidates={}
 for (end,filed,acc),g in groups.items():
  if (end,filed,acc) in conflicts or not all(k in g for k in TAGS):continue
  if g['assets'][0]<=0 or g['ppe'][0]<0 or g['ocf'][1]!=g['ppe'][1]:continue
  value=(g['ocf'][0]-g['ppe'][0])/g['assets'][0]
  if not math.isfinite(value):continue
  v={'end':end,'start':g['ocf'][1],'filed':filed,'accession':acc,'assets':g['assets'][0],'operatingCashflow':g['ocf'][0],'cashPpe':g['ppe'][0],'value':value,'currency':'USD','sourceUrl':f'https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc.replace("-","")}/'}
  candidates.setdefault(end,[]).append(v)
 out=[]
 for end,items in sorted(candidates.items()):
  latest=max(v['filed'] for v in items);same=[v for v in items if v['filed']==latest]
  if len({(v['assets'],v['operatingCashflow'],v['cashPpe'],v['start']) for v in same})!=1:continue
  out.append(max(same,key=lambda v:v['accession']))
 return out[-8:]

def run(universe,coverage,state,listing_map,fetch,now=None,budget=900,max_companies=300,checkpoint=None):
 now=now or dt.datetime.now(dt.timezone.utc);started=time.monotonic()
 if state and (state.get('schema')!=1 or state.get('method')!=METHOD):raise ValueError('unsupported_sec_history')
 state=state or {'schema':1,'method':METHOD,'stocks':{},'attempts':{}}
 if not recent(coverage.get('generatedAt'),now,2):state['report']={'stopped':'coverage_missing_or_stale'};return state
 allowed={r['symbol'] for r in coverage.get('stocks',[]) if r.get('domains',{}).get('identity',{}).get('state')=='available' and r.get('domains',{}).get('balance',{}).get('profile')=='corporate'}
 rows={};duplicates=set();counts=Counter();candidates=[]
 for r in universe.get('kandidaten',[]):
  s=r.get('listing_symbol')
  if s in rows:duplicates.add(s)
  rows[s]=r
 for s,r in rows.items():
  cik=listing_map.get(s)
  if s in duplicates or s not in allowed or not valid_isin(r.get('isin')) or r.get('listing_reference_status') in ('expired','input_mismatch') or not str(cik or '').isdigit():continue
  if r.get('cik') and str(r['cik']).lstrip('0')!=str(cik).lstrip('0'):counts['cikConflict']+=1;continue
  old=state['stocks'].get(s,{})
  if old.get('inputIdentity')==identity(r) and old.get('cik')==str(cik) and recent(old.get('retrievedAt'),now,7):counts['cached']+=1;continue
  att=state['attempts'].get(s,{})
  if att.get('inputIdentity')==identity(r) and att.get('error') and recent(att.get('at'),now,2):counts['cooldown']+=1;continue
  candidates.append(r)
 candidates.sort(key=lambda r:fetch_priority(r['listing_symbol'],state['attempts'].get(r['listing_symbol'],{}).get('at'),now))
 for r in candidates:
  remaining=budget-(time.monotonic()-started)
  if counts['attempted']>=max_companies or remaining<1:break
  s=r['listing_symbol'];cik=str(listing_map[s]);att={'at':now.isoformat(),'inputIdentity':identity(r)};counts['attempted']+=1
  try:
   data=fetch(cik,min(12,remaining))
   if not canonical_names(data.get('entityName')) & canonical_names(r.get('name_full') or r.get('name')):raise ValueError('issuer_name_mismatch')
   periods=normalize(data,cik,now)
   if not periods:raise ValueError('matching_cashflow_periods_missing')
   state['stocks'][s]={'inputIdentity':identity(r),'cik':cik,'retrievedAt':now.isoformat(),'periods':periods,'pointInTimeUsable':False};counts['updated']+=1;counts['periods']+=len(periods)
  except Exception as e:
   reason=str(e) if isinstance(e,ValueError) and str(e) in ('cik_mismatch','issuer_name_mismatch','matching_cashflow_periods_missing') else safe_error(e)
   att['error']=reason;counts[reason]+=1
  state['attempts'][s]=att;state.update(generatedAt=now.isoformat(),report=dict(counts))
  if checkpoint:checkpoint(state)
  if att.get('error') in ('http_403','http_429'):break
 counts['remainingCandidates']=len(candidates)-counts['attempted'];state.update(generatedAt=now.isoformat(),report=dict(counts));return state

def balances(cache,universe,now):
 out={};rows={r.get('listing_symbol'):r for r in universe.get('kandidaten',[])}
 if cache.get('schema')!=1 or cache.get('method')!=METHOD:return out
 for s,c in cache.get('stocks',{}).items():
  if c.get('inputIdentity')!=identity(rows.get(s,{})) or not recent(c.get('retrievedAt'),now,14):continue
  items=[]
  for p in c.get('periods',[]):
   try:
    if not all(isinstance(p[k],(int,float)) and not isinstance(p[k],bool) and math.isfinite(p[k]) for k in ('assets','cashPpe','operatingCashflow','value')):continue
    end=dt.date.fromisoformat(p['end']);filed=dt.date.fromisoformat(p['filed'])
    if not 0<=(now.date()-end).days<=8*366 or not end<=filed<=now.date() or not 330<=(end-dt.date.fromisoformat(p['start'])).days<=400:continue
    if not re.fullmatch(r'\d{10}-\d{2}-\d{6}',p['accession']) or p['sourceUrl']!=f'https://www.sec.gov/Archives/edgar/data/{int(c["cik"])}/{p["accession"].replace("-","")}/':continue
    if p['assets']<=0 or p['cashPpe']<0 or p['currency']!='USD':continue
    value=(p['operatingCashflow']-p['cashPpe'])/p['assets']
    if not math.isfinite(value) or abs(value-p['value'])>1e-12:continue
   except (KeyError,ValueError,TypeError):continue
   basis={'period':p['end'],'currency':'USD','retrievedAt':c['retrievedAt'],'fields':{k:{'source':SOURCE,'end':p['end'],'currency':'USD','retrievedAt':c['retrievedAt']} for k in TAGS}}
   items.append({'profile':'corporate','sourceUrl':p['sourceUrl'],'metrics':{'cashAfterPpeAssets':{'state':'available','value':value,'basis':basis}}})
  if items:out[s]={'inputIdentity':c['inputIdentity'],'balances':items}
 return out

def main():
 folder=Path(os.getenv('RISK_DATA_DIR',str(Path(__file__).resolve().parents[1]/'daten')));target=folder/'cf_sec_cashflow_history.json'
 def read(p):return json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}
 ua=os.getenv('SEC_USER_AGENT','')
 if not ua:print('SEC history: operator contact unavailable; archive retained');return
 sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'fundamental_export'))
 from reference_data import fetch_sec_listings
 listings=fetch_sec_listings(ua);last=[0.]
 def fetch(cik,timeout):
  time.sleep(max(0,.6-(time.monotonic()-last[0])));last[0]=time.monotonic()
  req=urllib.request.Request(f'https://data.sec.gov/api/xbrl/companyfacts/CIK{int(cik):010d}.json',headers={'User-Agent':ua,'Accept':'application/json'})
  with urllib.request.urlopen(req,timeout=timeout) as r:raw=r.read(25000001)
  if len(raw)>25000000:raise ValueError('response_too_large')
  return json.loads(raw)
 result=run(read(folder/'cf_universum.json'),read(folder/'cf_risk_coverage.json'),read(target),listings,fetch,checkpoint=lambda s:save(target,s))
 save(target,result);print(json.dumps(result['report']))
 if os.getenv('GITHUB_STEP_SUMMARY'):
  with open(os.environ['GITHUB_STEP_SUMMARY'],'a',encoding='utf-8') as f:f.write('\n## SEC cashflow history\n'+json.dumps(result['report'])+'\nPPE-only cashflow context; not comprehensive free cashflow.\n')
if __name__=='__main__':main()
