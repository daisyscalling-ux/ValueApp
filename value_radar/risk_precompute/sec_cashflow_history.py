"""Independent annual SEC cashflow context; never a substitute for full capex."""
import copy,datetime as dt,json,math,os,re,sys,time,urllib.error,urllib.request
from collections import Counter
from pathlib import Path
from news_identity import valid_isin,canonical_names
from roic_risk_annual import identity,safe_error
from yahoo_sector import recent,save
from market_priority import fetch_priority
from sec_issuer_names import same_issuer,POLICY
SOURCE='SEC companyfacts / annual cash PPE context v1'
METHOD='sec-cashflow-history-v1'
COLLECTION_POLICY=POLICY+'/cash-context-v5-filing-selection'
# Numerical concordance only, not proof of functional currency or an FX quote.
CURRENCY_RATIO_RTOL=1e-4
CURRENCY_RATIO_ATOL=1e-6
TAGS={'assets':'Assets','ocf':'NetCashProvidedByUsedInOperatingActivities','ppe':'PaymentsToAcquirePropertyPlantAndEquipment'}

def diagnostics(data,audit=None):
 facts=data.get('facts',{});us=facts.get('us-gaap',{})
 forms=sorted({f.get('form','') for tag in TAGS.values() for f in us.get(tag,{}).get('units',{}).get('USD',[])})
 counts={k:len(us.get(t,{}).get('units',{}).get('USD',[])) for k,t in TAGS.items()}
 alternatives=sorted(k for k in us if k.startswith('PaymentsToAcquire') and ('Property' in k or 'Productive' in k or 'Intangible' in k))
 variants=[]
 for namespace,tags,metric in VARIANTS:
  f=facts.get(namespace,{})
  units=[{c for c,rows in f.get(t,{}).get('units',{}).items() if rows} for t in tags.values()]
  common=sorted(c for c in set.intersection(*units) if re.fullmatch('[A-Z]{3}',c))
  variant_forms=sorted({str(x.get('form','')) for t in tags.values() for c in common for x in f.get(t,{}).get('units',{}).get(c,[])})
  currencies_by_field={key:sorted(c for c,rows in f.get(tag,{}).get('units',{}).items() if rows and re.fullmatch('[A-Z]{3}',c)) for key,tag in tags.items()}
  variants.append({'namespace':namespace,'concept':tags['ppe'],'metric':metric,'commonCurrencies':common,'forms':variant_forms,'currenciesByField':currencies_by_field})
 reason='matching_annual_filing_missing'
 if not any(facts.get(ns) for ns in ('us-gaap','ifrs-full')):reason='supported_accounting_namespace_missing'
 elif not any(v['currenciesByField']['ppe'] for v in variants):reason='cash_ppe_concept_missing'
 elif not any(v['commonCurrencies'] for v in variants):reason='same_currency_fields_missing'
 elif not any(any(f in ANNUAL_FORMS for f in v['forms']) for v in variants):reason='supported_annual_form_missing'
 if audit:
  if audit.get('currency_conflict_periods'):reason='multiple_currency_conflict'
  elif audit.get('group_conflicting_facts'):reason='conflicting_annual_facts'
  elif audit.get('group_negative_investment'):reason='negative_cash_ppe_requires_review'
 return {'reason':reason,'namespaces':sorted(facts),'forms':forms,'conceptCounts':counts,'alternativeConcepts':alternatives,'variants':variants,'stageCounts':dict(audit or {})}

def currency_concordant(items):
 # Do not accept ratios from different filings, periods or accounting definitions.
 if len({tuple(p[k] for k in ('end','start','filed','accession','namespace','concept','metric')) for p in items})!=1:return False
 for key in ('operatingCashflow','cashPpe'):
  values=[p[key]/p['assets'] for p in items]
  if not all(math.isfinite(v) for v in values):return False
  # Compare each component, not merely their difference (cancellation can hide errors).
  if not math.isclose(min(values),max(values),rel_tol=CURRENCY_RATIO_RTOL,abs_tol=CURRENCY_RATIO_ATOL):return False
 return True

ANNUAL_FORMS=('10-K','10-K/A','20-F','20-F/A','40-F','40-F/A')
IFRS_TAGS={'assets':'Assets','ocf':'CashFlowsFromUsedInOperatingActivities','ppe':'PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities'}
VARIANTS=[('us-gaap',TAGS,'cashAfterPpeAssets'),('us-gaap',{**TAGS,'ppe':'PaymentsToAcquireProductiveAssets'},'cashAfterProductiveAssets'),('ifrs-full',IFRS_TAGS,'cashAfterPpeAssets')]

def normalize_series(data,cik,now,namespace,tags,currency,metric,audit=None,all_filings=False):
 audit=audit if audit is not None else Counter()
 if str(data.get('cik','')).lstrip('0')!=str(cik).lstrip('0'):raise ValueError('cik_mismatch')
 groups={};conflicts=set()
 for key,tag in tags.items():
  for f in data.get('facts',{}).get(namespace,{}).get(tag,{}).get('units',{}).get(currency,[]):
   try:
    end=dt.date.fromisoformat(f['end']);filed=dt.date.fromisoformat(f['filed']);value=f['val'];acc=f['accn']
    if f.get('form') not in ANNUAL_FORMS:audit['fact_nonannual_form']+=1;continue
    if not re.fullmatch(r'\d{10}-\d{2}-\d{6}',acc):audit['fact_invalid_accession']+=1;continue
    if not 0<=(now.date()-end).days<=8*366 or not end<=filed<=now.date():audit['fact_outside_date_window']+=1;continue
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):audit['fact_invalid_value']+=1;continue
    if key!='assets' and not 330<=(end-dt.date.fromisoformat(f['start'])).days<=400:audit['fact_nonannual_duration']+=1;continue
    if key=='assets' and f.get('start'):audit['fact_assets_not_instant']+=1;continue
    group=(str(end),str(filed),acc);item=(value,f.get('start') if key!='assets' else None)
    g=groups.setdefault(group,{})
    if key in g and g[key]!=item:conflicts.add(group)
    g[key]=item
   except (KeyError,ValueError,TypeError):audit['fact_malformed']+=1;continue
 candidates={}
 for (end,filed,acc),g in groups.items():
  if (end,filed,acc) in conflicts:audit['group_conflicting_facts']+=1;continue
  if not all(k in g for k in TAGS):audit['group_missing_same_filing_fields']+=1;continue
  if g['assets'][0]<=0:audit['group_nonpositive_assets']+=1;continue
  if g['ppe'][0]<0:audit['group_negative_investment']+=1;continue
  if g['ocf'][1]!=g['ppe'][1]:audit['group_duration_mismatch']+=1;continue
  value=(g['ocf'][0]-g['ppe'][0])/g['assets'][0]
  if not math.isfinite(value):continue
  v={'end':end,'start':g['ocf'][1],'filed':filed,'accession':acc,'assets':g['assets'][0],'operatingCashflow':g['ocf'][0],'cashPpe':g['ppe'][0],'value':value,'currency':currency,'namespace':namespace,'concept':tags['ppe'],'metric':metric,'sourceUrl':f'https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc.replace("-","")}/'}
  candidates.setdefault(end,[]).append(v)
 if all_filings:return [p for items in candidates.values() for p in items]
 out=[]
 for end,items in sorted(candidates.items()):
  latest=max(v['filed'] for v in items);same=[v for v in items if v['filed']==latest]
  if len({(v['assets'],v['operatingCashflow'],v['cashPpe'],v['start']) for v in same})!=1:audit['period_conflicting_latest_filings']+=1;continue
  out.append(max(same,key=lambda v:v['accession']))
 return out[-8:]

def normalize(data,cik,now,audit=None):
 audit=audit if audit is not None else Counter()
 if str(data.get('cik','')).lstrip('0')!=str(cik).lstrip('0'):raise ValueError('cik_mismatch')
 out=[]
 for namespace,tags,metric in VARIANTS:
  facts=data.get('facts',{}).get(namespace,{})
  units=[set(facts.get(tag,{}).get('units',{})) for tag in tags.values()]
  currencies=set.intersection(*units)
  series=[]
  for currency in sorted(currencies):
   if re.fullmatch('[A-Z]{3}',currency):series.extend(normalize_series(data,cik,now,namespace,tags,currency,metric,audit,all_filings=True))
  by_end={}
  for p in series:by_end.setdefault(p['end'],[]).append(p)
  for end in sorted(by_end)[-8:]:
   versions=by_end[end]
   latest=max(p['filed'] for p in versions)
   items=[p for p in versions if p['filed']==latest]
   audit['older_filing_observations_superseded']+=len(versions)-len(items)
   # A currency printed only in an older report must not veto a newer complete report.
   # Same-day different accessions remain ambiguous unless every currency's values match.
   selected=[]
   for currency in sorted({p['currency'] for p in items}):
    same=[p for p in items if p['currency']==currency]
    if len({tuple(p[k] for k in ('assets','operatingCashflow','cashPpe','start')) for p in same})!=1:
     audit['period_conflicting_latest_filings']+=1;selected=[];break
    selected.append(max(same,key=lambda p:p['accession']))
   items=selected
   if not items:continue
   if len(items)>1:
    if not currency_concordant(items):audit['currency_conflict_periods']+=1;continue
    audit['currency_concordant_periods']+=1
    for p in items:p['currencyCheck']={'method':'component-ratios-v1','currencies':sorted(x['currency'] for x in items)}
   # Preserve separate reported series. Never pick a native currency or convert amounts.
   out.extend(items)
 return out

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
  att=state['attempts'].get(s,{})
  retry_partial=att.get('policy')!=COLLECTION_POLICY and att.get('normalization',{}).get('currency_conflict_periods',0)>0
  if old.get('inputIdentity')==identity(r) and old.get('cik')==str(cik) and recent(old.get('retrievedAt'),now,7) and not retry_partial:counts['cached']+=1;continue
  cooldown=28 if att.get('error') in ('us_gaap_missing','supported_accounting_namespace_missing','supported_annual_form_missing') else 2
  if att.get('policy')==COLLECTION_POLICY and att.get('inputIdentity')==identity(r) and att.get('error') and recent(att.get('at'),now,cooldown):counts['cooldown']+=1;continue
  candidates.append(r)
 candidates.sort(key=lambda r:fetch_priority(r['listing_symbol'],state['attempts'].get(r['listing_symbol'],{}).get('at'),now))
 for r in candidates:
  remaining=budget-(time.monotonic()-started)
  if counts['attempted']>=max_companies or remaining<1:break
  s=r['listing_symbol'];cik=str(listing_map[s]);att={'at':now.isoformat(),'inputIdentity':identity(r),'policy':COLLECTION_POLICY};counts['attempted']+=1
  try:
   data=fetch(cik,min(12,remaining))
   att['issuerNames']={'expected':r.get('name_full') or r.get('name'),'sec':data.get('entityName'),'cik':cik}
   if not same_issuer(data.get('entityName'),r.get('name_full') or r.get('name')):raise ValueError('issuer_name_mismatch')
   audit=Counter();periods=normalize(data,cik,now,audit)
   att['normalization']=dict(audit)
   counts['currencyConcordantPeriods']+=audit['currency_concordant_periods']
   counts['currencyConflictPeriods']+=audit['currency_conflict_periods']
   if not periods:
    att['diagnostics']=diagnostics(data,audit)
    raise ValueError(att['diagnostics']['reason'])
   state['stocks'][s]={'inputIdentity':identity(r),'cik':cik,'retrievedAt':now.isoformat(),'periods':periods,'pointInTimeUsable':False};counts['updated']+=1;counts['periods']+=len(periods)
   counts['fiscalYears']+=len({p['end'] for p in periods})
  except Exception as e:
   reason=str(e) if isinstance(e,ValueError) and str(e) in ('cik_mismatch','issuer_name_mismatch','matching_cashflow_periods_missing','matching_annual_filing_missing','us_gaap_missing','cash_ppe_concept_missing','supported_annual_form_missing','negative_cash_ppe_requires_review','multiple_currency_conflict','conflicting_annual_facts','supported_accounting_namespace_missing','same_currency_fields_missing') else safe_error(e)
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
    if p['assets']<=0 or p['cashPpe']<0 or not re.fullmatch('[A-Z]{3}',p['currency']):continue
    value=(p['operatingCashflow']-p['cashPpe'])/p['assets']
    if not math.isfinite(value) or abs(value-p['value'])>1e-12:continue
   except (KeyError,ValueError,TypeError):continue
   if 'namespace' not in p and p['currency']!='USD':continue
   variant=next((v for v in VARIANTS if v[0]==p.get('namespace','us-gaap') and v[1]['ppe']==p.get('concept',TAGS['ppe']) and v[2]==p.get('metric','cashAfterPpeAssets')),None)
   if variant is None:continue
   source=SOURCE if variant[0]=='us-gaap' and variant[2]=='cashAfterPpeAssets' else 'SEC companyfacts / '+variant[0]+' / '+variant[1]['ppe']
   basis={'period':p['end'],'currency':p['currency'],'retrievedAt':c['retrievedAt'],'fields':{k:{'source':source,'end':p['end'],'currency':p['currency'],'retrievedAt':c['retrievedAt']} for k in TAGS}}
   items.append({'profile':'corporate','sourceUrl':p['sourceUrl'],'metrics':{variant[2]:{'state':'available','value':value,'basis':basis}}})
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
