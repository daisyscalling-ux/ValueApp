"""Resumable universe-wide ROIC annual history. Never modifies current valuations."""
import datetime as dt,json,os,re,time,urllib.parse,urllib.request
from pathlib import Path
from collections import Counter
from roic_risk_annual import identity,normalize,records,safe_error
from news_identity import valid_isin
from market_priority import fetch_priority
from yahoo_sector import recent,save
AGE=8*366

def normalize_years(row,payloads,now):
 tables={k:records(payloads[k],row['listing_symbol'],now,AGE) for k in ('balance','income','cashflow')};periods=tables['balance'];out=[]
 for end in sorted(periods,reverse=True)[:8]:
  parts={k:{'data':[tables[k][end]] if end in tables[k] else []} for k in ('balance','income','cashflow')}
  try:a=normalize(row,parts,now,AGE)
  except ValueError as e:
   if str(e)=='empty_statement_values':continue
   raise
  if a['fields'].get('total_assets') is not None and a['fields']['total_assets']>0:out.append(a)
 return sorted(out,key=lambda a:a['end'])

def run(universe,coverage,state,fetch,now=None,budget=1800,max_companies=500,checkpoint=None):
 now=now or dt.datetime.now(dt.timezone.utc);started=time.monotonic()
 if state and (state.get('schema')!=1 or state.get('method')!='roic-annual-history-v1'):raise ValueError('unsupported_history_cache')
 state=state or {'schema':1,'method':'roic-annual-history-v1','stocks':{},'attempts':{}}
 counts=Counter();rows={};duplicates=set()
 for row in universe.get('kandidaten',[]):
  s=row.get('listing_symbol')
  if s in rows:duplicates.add(s)
  rows[s]=row
 qualified={r['symbol'] for r in coverage.get('stocks',[]) if r.get('domains',{}).get('identity',{}).get('state')=='available'}
 if not recent(coverage.get('generatedAt'),now,2):state['report']={'stopped':'coverage_missing_or_stale'};return state
 candidates=[]
 for s,row in rows.items():
  if s in duplicates or s not in qualified or not valid_isin(row.get('isin')) or row.get('listing_reference_status') in ('expired','input_mismatch') or not re.fullmatch('[A-Z0-9._-]+:[A-Z0-9._-]+',str(s)):counts['identityBlocked']+=1;continue
  old=state['stocks'].get(s,{});attempt=state['attempts'].get(s,{})
  if old.get('inputIdentity')!=identity(row):old={}
  if attempt.get('inputIdentity')!=identity(row):attempt={}
  # Monthly refresh for seven years; shorter history rechecked weekly, not each day.
  days=30 if len(old.get('annuals',[]))>=7 else 7
  if old and recent(old.get('retrievedAt'),now,days):counts['cached']+=1;continue
  if attempt.get('error') and recent(attempt.get('at'),now,7 if attempt['error'] in ('http_401','http_402','http_403') else min(7,2**min(attempt.get('failures',0),3))):counts['cooldown']+=1;continue
  candidates.append(row)
 candidates.sort(key=lambda row:fetch_priority(row['listing_symbol'],state['attempts'].get(row['listing_symbol'],{}).get('at'),now))
 for row in candidates:
  if counts['attempted']>=max_companies or time.monotonic()-started>=budget:counts['budgetReached']+=1;break
  s=row['listing_symbol'];old=state['attempts'].get(s,{});attempt={'at':now.isoformat(),'inputIdentity':identity(row)};counts['attempted']+=1
  try:
   payloads={}
   for kind,endpoint in [('balance','balance-sheet'),('cashflow','cash-flow'),('income','income-statement')]:
    remaining=budget-(time.monotonic()-started)
    if remaining<1:raise ValueError('budget_exhausted')
    payloads[kind]=fetch(s,endpoint,min(12,remaining))
   annuals=normalize_years(row,payloads,now)
   if not annuals:raise ValueError('eligible_balance_missing')
   state['stocks'][s]={'inputIdentity':identity(row),'retrievedAt':now.isoformat(),'annuals':annuals,'pointInTimeUsable':False};counts['updated']+=1;counts['annualStatements']+=len(annuals)
   if len(annuals)<7:counts['shortHistory']+=1
  except Exception as e:attempt.update(error=safe_error(e),failures=min(7,old.get('failures',0)+1));counts[attempt['error']]+=1
  state['attempts'][s]=attempt;state['generatedAt']=now.isoformat();state['report']=dict(counts)
  if checkpoint:checkpoint(state)
  if attempt.get('error') in ('http_401','http_402','http_403','http_429','budget_exhausted'):break
 counts['remainingCandidates']=len(candidates)-counts['attempted'];state.update(generatedAt=now.isoformat(),report=dict(counts));return state

def main():
 folder=Path(os.getenv('RISK_DATA_DIR',str(Path(__file__).resolve().parents[1]/'daten')));path=folder/'cf_roic_history.json'
 def read(p):return json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}
 state=read(path);key=os.getenv('ROIC_API_KEY')
 if not key:print('History backfill: ROIC key unavailable; existing archive retained.');return
 last=[0.0]
 def fetch(s,endpoint,timeout):
  time.sleep(max(0,.5-(time.monotonic()-last[0])));last[0]=time.monotonic()
  query=urllib.parse.urlencode({'period_type':'annual','order':'desc','limit':8,'apikey':key})
  url='https://api.roic.ai/v3.0.0/fundamental/'+endpoint+'/'+urllib.parse.quote(s,safe=':')+'?'+query
  req=urllib.request.Request(url,headers={'User-Agent':'value-radar','Accept':'application/json'})
  with urllib.request.urlopen(req,timeout=timeout) as r:raw=r.read(4000001)
  if len(raw)>4000000:raise ValueError('response_too_large')
  return json.loads(raw)
 result=run(read(folder/'cf_universum.json'),read(folder/'cf_risk_coverage.json'),state,fetch,budget=min(1800,max(0,int(os.getenv('HISTORY_BACKFILL_BUDGET_S','1800')))),checkpoint=lambda s:save(path,s))
 save(path,result);print(json.dumps(result['report']))
 if os.getenv('GITHUB_STEP_SUMMARY'):
  with open(os.environ['GITHUB_STEP_SUMMARY'],'a',encoding='utf-8') as f:f.write('\n## Mehrjahresabschluesse nachladen\n\n```json\n'+json.dumps(result['report'])+'\n```\nWeniger gelieferte Jahre bleiben sichtbar; keine Garantie eines vollstaendigen Siebenjahresbestands.\n')
if __name__=='__main__':main()
