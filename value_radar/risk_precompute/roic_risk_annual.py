"""Bounded ROIC v3 annual risk statements, independent of valuation inputs."""
import datetime as dt
import json
import math
import os
from pathlib import Path
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from news_identity import valid_isin
from financial_supply_policy import decision
from market_priority import fetch_priority,market_tier
from yahoo_sector import load,save,recent

UTC=dt.timezone.utc
IDENTITY=('listing_symbol','ticker','isin','currency','security_type','share_class')
def identity(row):return {k:row.get(k) for k in IDENTITY}
def number(v):return v if isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) else None

def records(payload,symbol,now):
 data=payload.get('data') if isinstance(payload,dict) else None
 if not isinstance(data,list):raise ValueError('invalid_schema')
 result={}
 for r in data:
  if not isinstance(r,dict) or r.get('symbol')!=symbol or r.get('period_type')!='annual':continue
  try:
   date=r['period_end_date'];age=(now.date()-dt.date.fromisoformat(date)).days
  except (ValueError,TypeError,KeyError):continue
  if not 0<=age<=550 or not re.fullmatch('[A-Z]{3}',str(r.get('currency',''))) or r.get('fx_applied') is not False:continue
  if date in result and result[date]!=r:raise ValueError('conflicting_statement_period')
  result[date]=r
 return result

def normalize(row,payloads,now=None):
 now=now or dt.datetime.now(UTC);symbol=row['listing_symbol']
 tables={k:records(payloads[k],symbol,now) for k in ('balance','cashflow','income')}
 if not tables['balance']:raise ValueError('eligible_balance_missing')
 end=max(tables['balance']);balance=tables['balance'][end];currency=balance['currency']
 # Never take a cash-flow row by list position, year label or another currency.
 matching=lambda k:tables[k].get(end,{}) if tables[k].get(end,{}).get('currency')==currency else {}
 cashflow=matching('cashflow');income=matching('income');fields={};sources={}
 urls={k:'https://www.roic.ai/api/docs/financial-statements/'+v for k,v in [('balance','balance-sheet'),('cashflow','cash-flow'),('income','income-statement')]}
 def assign(key,kind,table,provider):
  fields[key]=number(table.get(provider))
  if fields[key] is not None:sources[key]={'source':'ROIC v3 annual statements','source_url':urls[kind],'end':end,'currency':currency,'provider_field':provider}
 for key,provider in [('total_assets','bs_tot_asset'),('cash','bs_cash_near_cash_item'),('equity','bs_eqty_bef_minority_int_detailed')]:assign(key,'balance',balance,provider)
 assign('net_income','income',income,'is_net_income')
 assign('operating_cashflow','cashflow',cashflow,'cf_cash_from_oper')
 debt=[number(balance.get(k)) for k in ('bs_st_borrow','bs_lt_borrow')]
 fields['total_debt']=sum(debt) if all(v is not None and v>=0 for v in debt) else None
 if fields['total_debt'] is not None:sources['total_debt']={'source':'ROIC v3 annual statements','source_url':urls['balance'],'end':end,'currency':currency,'derivation':'sum_of_reported_maturities','components':dict(zip(('bs_st_borrow','bs_lt_borrow'),debt))}
 capex=number(cashflow.get('cf_cap_expenditures'));parts={}
 if capex is None:
  # Reported gross fixed/intangible acquisition aggregate, or both components.
  capex=number(cashflow.get('cf_acquis_fxd_and_intang_detailed'))
  if capex is not None:parts={'cf_acquis_fxd_and_intang_detailed':capex}
  else:
   names=('cf_purchase_of_fixed_prod_assets','cf_acquisition_of_intang_assets');values=[number(cashflow.get(k)) for k in names]
   if all(v is not None and v<=0 for v in values):capex=sum(values);parts=dict(zip(names,values))
 else:parts={'cf_cap_expenditures':capex}
 fields['capex']=-capex if capex is not None and capex<=0 else None
 if fields['capex'] is not None:sources['capex']={'source':'ROIC v3 annual statements','source_url':urls['cashflow'],'end':end,'currency':currency,'derivation':'negative_cash_outflow_to_positive_spend','components':parts}
 # Providers may expose next fiscal-year headers before populating any
 # financial values. Never overwrite useful archived observations with these.
 if all(v is None for v in fields.values()):
  remaining=[r for r in payloads['balance']['data'] if not isinstance(r,dict) or r.get('period_end_date')!=end]
  if not any(date<end for date in tables['balance']):raise ValueError('empty_statement_values')
  older=normalize(row,{**payloads,'balance':{**payloads['balance'],'data':remaining}},now)
  older['skippedEmptyPeriods']=[end]+older.get('skippedEmptyPeriods',[])
  return older
 return {'symbol':symbol,'purpose':'standalone_balance_risk_context','period_type':'annual','end':end,'currency':currency,
  'source':'ROIC v3 annual statements','source_url':urls['balance'],'published_at':None,'fields':fields,'field_sources':sources,
  'limitations':['Consolidated standardized annual fields, not historical point-in-time data.','Debt is the provider-defined sum of reported short and long maturities; lease scope is not separately reconciled.']}

def safe_error(exc):
 if isinstance(exc,urllib.error.HTTPError):return 'http_'+str(exc.code)
 allowed={'invalid_schema','conflicting_statement_period','eligible_balance_missing','budget_exhausted','response_too_large','empty_statement_values'}
 return str(exc) if isinstance(exc,ValueError) and str(exc) in allowed else 'provider_unavailable'

def run(universe,coverage,state,fetch,now=None,budget=720,checkpoint=None):
 now=now or dt.datetime.now(UTC);start=time.monotonic();state=state if state.get('schema')==1 else {'schema':1,'stocks':{},'attempts':{}}
 state.setdefault('stocks',{});state.setdefault('attempts',{});counts=Counter()
 active={};conflicts=set()
 for r in universe.get('kandidaten',[]):
  s=r.get('listing_symbol')
  if not s:continue
  if s in active and identity(active[s])!=identity(r):conflicts.add(s)
  active[s]=r
 for s in conflicts:del active[s]
 counts['conflicting_listings']=len(conflicts)
 for store in (state['stocks'],state['attempts']):
  for s in list(store):
   if s not in active or store[s].get('inputIdentity')!=identity(active[s]):del store[s]
 # Without a recent audit, do not guess which stocks need this fallback.
 if not recent(coverage.get('generatedAt'),now,2):
  state['report']={'stopped':'coverage_missing_or_stale'};return state
 balances={r['symbol']:r.get('domains',{}).get('balance',{}) for r in coverage.get('stocks',[])}
 targets={s for s,b in balances.items() if b.get('state') in ('partial','missing') or b.get('refreshDue') is True}
 targets.update(s for s in active if s not in balances)
 # Refresh already used records too, or successful recovery would expire.
 targets.update(s for s,v in state['stocks'].items() if not recent(v.get('retrievedAt'),now,1))
 rows=[active[s] for s in targets if s in active]
 rows.sort(key=lambda r:fetch_priority(r['listing_symbol'],state['attempts'].get(r['listing_symbol'],{}).get('at'),now))
 for row in rows:
  s=row['listing_symbol'];old=state['attempts'].get(s,{})
  if market_tier(s)>1:counts['deferred_other_market']+=1;continue
  if not valid_isin(row.get('isin')) or row.get('listing_reference_status') in ('expired','input_mismatch') or not re.fullmatch('[A-Z0-9._-]+:[A-Z0-9._-]+',s):counts['identity_blocked']+=1;continue
  balance=balances.get(s,{})
  # Legacy archives may contain successful records before the audit selected
  # their source. Do not discard their first refresh during migration.
  if old.get('coverageSignature') is None and s in state['stocks'] and not balance:balance={'state':'missing'}
  policy=decision(row,balance,state['stocks'].get(s,{}),old,now)
  if not policy['due']:counts['cooldown']+=1;continue
  if time.monotonic()-start>=budget:counts['budget_reached']+=1;break
  record={'at':now.isoformat(),'inputIdentity':identity(row),'coverageSignature':policy['coverageSignature'],'expectedPeriod':balance.get('period')};counts['attempted']+=1
  try:
   payloads={}
   for kind,endpoint in [('balance','balance-sheet'),('cashflow','cash-flow'),('income','income-statement')]:
    remaining=budget-(time.monotonic()-start)
    if remaining<1:raise ValueError('budget_exhausted')
    payloads[kind]=fetch(s,endpoint,min(12,remaining))
   annual=normalize(row,payloads,now)
   state['stocks'][s]={'inputIdentity':identity(row),'retrievedAt':now.isoformat(),'annual':annual};counts['updated']+=1
   counts['skipped_empty_periods']+=len(annual.get('skippedEmptyPeriods',[]))
   counts['empty_statements' if all(v is None for v in annual['fields'].values()) else 'partial_statements' if any(v is None for v in annual['fields'].values()) else 'complete_statements']+=1
  except Exception as e:
   record['error']=safe_error(e);counts[record['error']]+=1
   record['consecutiveFailures']=min(7,old.get('consecutiveFailures',0)+1)
  state['attempts'][s]=record;state['generatedAt']=now.isoformat();state['report']=dict(counts)
  if checkpoint:checkpoint(state)
  if record.get('error') in ('http_401','http_402','http_403','http_429','budget_exhausted'):break
 state['generatedAt']=now.isoformat();state['report']=dict(counts);return state

def main():
 folder=Path(os.getenv('RISK_DATA_DIR',str(Path(__file__).resolve().parents[1]/'daten')));dest=folder/'cf_roic_risk_annual.json'
 state=load(dest,{});key=os.getenv('ROIC_API_KEY')
 if not key:
  state.update(schema=1,report={'stopped':'roic_key_missing'});save(dest,state);print(json.dumps(state['report']));return
 last=[0.0]
 def fetch(s,endpoint,timeout):
  # <=120 calls/minute, leaving headroom under the user's 300/min allowance.
  time.sleep(max(0,.5-(time.monotonic()-last[0])));last[0]=time.monotonic()
  url='https://api.roic.ai/v3.0.0/fundamental/'+endpoint+'/'+urllib.parse.quote(s,safe=':')+'?'+urllib.parse.urlencode({'period_type':'annual','limit':2,'apikey':key})
  request=urllib.request.Request(url,headers={'User-Agent':'value-radar','Accept':'application/json'})
  with urllib.request.urlopen(request,timeout=timeout) as response:raw=response.read(2000001)
  if len(raw)>2000000:raise ValueError('response_too_large')
  return json.loads(raw)
 state=run(load(folder/'cf_universum.json',{}),load(folder/'cf_risk_coverage.json',{}),state,fetch,checkpoint=lambda s:save(dest,s))
 save(dest,state);print(json.dumps(state['report']))
if __name__=='__main__':main()
