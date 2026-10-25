"""Incremental EDINET discovery and bounded original-filing download for Japan."""
import datetime as dt
import json
import os
from pathlib import Path
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from edinet_cashflow import parse_zip,PARSER_VERSION
from news_identity import valid_isin
from roic_risk_annual import identity
from yahoo_sector import load,save,recent
UTC=dt.timezone.utc
JST=dt.timezone(dt.timedelta(hours=9))

def sec_code(row):
 symbol=str(row.get('listing_symbol',''));m=re.fullmatch(r'(TSE|TYO|JPX):([0-9A-Z]{4})',symbol)
 if not m or not str(row.get('isin','')).startswith('JP') or not valid_isin(row.get('isin')) or row.get('currency')!='JPY' or row.get('listing_reference_status') in ('expired','input_mismatch'):return None
 return m[2]+'0'

def published(doc):
 try:return dt.datetime.strptime(doc['submitDateTime'],'%Y-%m-%d %H:%M').replace(tzinfo=JST).astimezone(UTC)
 except (ValueError,TypeError,KeyError):return None

def eligible(doc,code,now):
 try:
  start=dt.date.fromisoformat(doc['periodStart']);end=dt.date.fromisoformat(doc['periodEnd'])
 except (ValueError,TypeError,KeyError):return False
 return (doc.get('secCode')==code and doc.get('docTypeCode') in ('120','130') and doc.get('xbrlFlag')=='1'
  and not doc.get('fundCode') and doc.get('withdrawalStatus')=='0' and doc.get('disclosureStatus')=='0' and doc.get('docInfoEditStatus')=='0'
  and re.fullmatch(r'E\d{5}',str(doc.get('edinetCode',''))) is not None
  and re.fullmatch(r'S[0-9A-Z]{7}',str(doc.get('docID',''))) is not None
  and 330<=(end-start).days<=380 and 0<=(now.date()-end).days<=550
  and published(doc) is not None and published(doc)<=now and published(doc).date()>=end)

def select_doc(docs,code,now):
 # Select the newest fiscal year's original first. Corrections inherit ONLY
 # missing metadata from a verified parent chain, never financial values.
 roots=[d for d in docs if d.get('docTypeCode')=='120' and eligible(d,code,now)]
 if not roots:return None
 if len({d['edinetCode'] for d in roots})!=1:raise ValueError('ambiguous_filer')
 roots.sort(key=lambda d:(d['periodEnd'],d['submitDateTime']),reverse=True)
 root=roots[0]
 if any(d['periodEnd']==root['periodEnd'] and d['submitDateTime']==root['submitDateTime'] and d['docID']!=root['docID'] for d in roots[1:]):raise ValueError('ambiguous_revision')
 nodes={root['docID']:{**root,'revisionChain':[root['docID']],'revisionIndexDates':[root['indexDate']],'periodOriginDocID':root['docID']}}
 seen={}
 for d in docs:
  if d.get('docTypeCode')!='130':continue
  key=d.get('docID')
  if key in seen:
   keys=('parentDocID','edinetCode','secCode','periodStart','periodEnd','xbrlFlag','submitDateTime','withdrawalStatus','disclosureStatus','docInfoEditStatus')
   if any(seen[key].get(k)!=d.get(k) for k in keys):
    if d.get('secCode')==code or seen[key].get('secCode')==code:raise ValueError('ambiguous_revision')
  seen[key]=d
 for _ in range(16):
  progress=False
  for key,d in seen.items():
   if key in nodes or d.get('parentDocID') not in nodes:continue
   parent=nodes[d['parentDocID']]
   if d.get('withdrawalStatus')!='0':continue
   if d.get('edinetCode')!=parent['edinetCode'] or d.get('secCode') not in (None,'',code):raise ValueError('ambiguous_filer')
   if not published(d) or not published(parent) or not published(parent)<=published(d)<=now:raise ValueError('ambiguous_revision')
   resolved={**d,'secCode':code,'periodStart':d.get('periodStart') or parent['periodStart'],'periodEnd':d.get('periodEnd') or parent['periodEnd']}
   if resolved['periodStart']!=root['periodStart'] or resolved['periodEnd']!=root['periodEnd']:raise ValueError('ambiguous_revision')
   if not eligible({**resolved,'xbrlFlag':'1'},code,now):raise ValueError('unavailable_correction')
   nodes[key]={**resolved,'revisionChain':parent['revisionChain']+[key],
    'revisionIndexDates':list(dict.fromkeys(parent['revisionIndexDates']+[d['indexDate']])),
    'periodOriginDocID':root['docID'],'periodMetadataInherited':not d.get('periodStart') or not d.get('periodEnd')}
   progress=True
  if not progress:break
 # A newer same-year correction with an unresolved parent is a review case.
 for key,d in seen.items():
  if key not in nodes and d.get('secCode')==code and d.get('periodEnd') in (None,'',root['periodEnd']) and published(d) and published(d)>published(root) and d.get('withdrawalStatus')=='0':raise ValueError('unavailable_correction')
 choices=sorted(nodes.values(),key=lambda d:d['submitDateTime'],reverse=True);best=choices[0]
 if len(choices)>1 and choices[1]['submitDateTime']==best['submitDateTime']:raise ValueError('ambiguous_revision')
 if best.get('xbrlFlag')!='1':raise ValueError('unavailable_correction')
 return best

def safe_error(e):
 if isinstance(e,urllib.error.HTTPError):return 'http_'+str(e.code)
 allowed={'http_401','http_403','http_429','invalid_index','ambiguous_filer','ambiguous_revision','unavailable_correction','unsafe_xml','not_xbrl_instance','invalid_annual_period','duplicate_context','duplicate_unit','ambiguous_or_unsupported_taxonomy','ambiguous_public_instance','archive_too_large','budget_exhausted','response_too_large','consolidation_unconfirmed','issuer_unconfirmed','conflicting_namespace'}
 return str(e) if isinstance(e,ValueError) and str(e) in allowed else 'provider_or_parse_error'

def run(universe,coverage,state,get_day,get_zip,now=None,budget=1680,checkpoint=None):
 now=now or dt.datetime.now(UTC);started=time.monotonic();today=now.astimezone(JST).date()
 if state.get('schema')!=1:state={'schema':1,'days':{},'stocks':{},'attempts':{}}
 for k in ('days','stocks','attempts'):state.setdefault(k,{})
 report={'indexDaysFetched':0,'downloaded':0,'completeCashflows':0,'partialCashflows':0,'errors':{}}
 rows={};conflicts=set()
 for row in universe.get('kandidaten',[]):
  s=row.get('listing_symbol');code=sec_code(row)
  if not code:continue
  if s in rows and identity(rows[s])!=identity(row):conflicts.add(s)
  rows[s]=row
 for s in conflicts:rows.pop(s,None)
 for bucket in ('stocks','attempts'):
  for s in list(state[bucket]):
   if s not in rows or state[bucket][s].get('inputIdentity')!=identity(rows[s]):del state[bucket][s]
 def persist():
  state.update(generatedAt=now.isoformat(),report=report)
  if checkpoint:checkpoint(state)
 def error(e):
  code=safe_error(e);report['errors'][code]=report['errors'].get(code,0)+1
  return code in ('http_401','http_403','http_429','budget_exhausted')
 def day_fetch(date):
  data=get_day(date)
  status=str(data.get('metadata',{}).get('status')) if isinstance(data,dict) else ''
  if status in ('401','403','429'):raise ValueError('http_'+status)
  if not isinstance(data,dict) or str(data.get('metadata',{}).get('status'))!='200' or not isinstance(data.get('results'),list):raise ValueError('invalid_index')
  # Include unavailable records: a later refresh must be able to remove them.
  records=[{**d,'indexDate':date} for d in data['results'] if d.get('docTypeCode') in ('120','130') and (d.get('secCode') or d.get('parentDocID'))]
  state['days'][date]={'checkedAt':now.isoformat(),'documents':records};report['indexDaysFetched']+=1;persist()
 if not recent(coverage.get('generatedAt'),now,2):report['stopped']='coverage_missing_or_stale';persist();return state
 targets={s['symbol'] for s in coverage.get('stocks',[]) if s.get('domains',{}).get('balance',{}).get('state') in ('partial','missing')}
 targets.update(state['stocks']);targets &= rows.keys();report['targetListings']=len(targets)
 if not targets:report['stopped']='no_targets';persist();return state
 for date in list(state['days']):
  try:age=(today-dt.date.fromisoformat(date)).days
  except ValueError:age=999
  if not 0<=age<=550:del state['days'][date]
 # Cold start walks 460 filing days once, newest first, with persistent progress.
 # A rolling seven-day overlap captures new filings and correction announcements.
 for offset in range(461):
  date=str(today-dt.timedelta(days=offset));cached=state['days'].get(date)
  if cached and (offset>7 or recent(cached.get('checkedAt'),now,.5)):continue
  if time.monotonic()-started>min(1080,budget*.7):report['indexBudgetReached']=True;break
  try:day_fetch(date)
  except Exception as e:
   if error(e):report['stopped']='index_access_or_budget';persist();return state
 report['indexWindowComplete']=all(str(today-dt.timedelta(days=i)) in state['days'] for i in range(461))
 for s in sorted(targets,key=lambda s:state['attempts'].get(s,{}).get('at','')):
  if time.monotonic()-started>=budget:report['downloadBudgetReached']=True;break
  row=rows[s];old=state['attempts'].get(s,{})
  if old.get('parserVersion')==PARSER_VERSION and recent(old.get('at'),now,.9):continue
  attempt={'at':now.isoformat(),'inputIdentity':identity(row),'parserVersion':PARSER_VERSION}
  try:
   docs=[d for v in state['days'].values() for d in v['documents']]
   doc=select_doc(docs,sec_code(row),now)
   if not doc:
    # No cached value survives a known withdrawal or unavailable correction.
    previous=state['stocks'].get(s,{}).get('filing',{})
    if any(d.get('docID')==previous.get('docID') and not eligible(d,sec_code(row),now) for d in docs) or report['indexWindowComplete']:state['stocks'].pop(s,None)
    attempt['error']='annual_filing_not_found';state['attempts'][s]=attempt;persist();continue
   # Recheck the original filing day for withdrawals/corrections before reuse.
   for day in doc.get('revisionIndexDates',[doc['indexDate']]):
    if not recent(state['days'][day]['checkedAt'],now,.9):day_fetch(day)
   docs=[d for v in state['days'].values() for d in v['documents']]
   checked=select_doc(docs,sec_code(row),now)
   if not checked or checked['docID']!=doc['docID']:
    state['stocks'].pop(s,None);attempt['error']='filing_changed_retry_required';state['attempts'][s]=attempt;persist();continue
   if state['stocks'].get(s,{}).get('filing',{}).get('docID') not in (None,doc['docID']):
    state['stocks'].pop(s,None);persist()
   doc=checked
   # Only a newly downloaded file can renew the observation timestamp.
   annual=parse_zip(get_zip(doc['docID']),doc,now)
   annual.update(symbol=s,purpose='standalone_cashflow_risk_context',published_at=published(doc).isoformat(),
    source_url='https://disclosure2.edinet-fsa.go.jp/',docID=doc['docID'])
   state['stocks'][s]={'inputIdentity':identity(row),'retrievedAt':now.isoformat(),'filing':doc,'annual':annual}
   report['downloaded']+=1;report['completeCashflows' if annual['state']=='available' else 'partialCashflows']+=1
  except Exception as e:
   attempt['error']=safe_error(e)
   if attempt['error'] in ('unavailable_correction','ambiguous_filer','ambiguous_revision','unsafe_xml','issuer_unconfirmed','consolidation_unconfirmed','invalid_annual_period','duplicate_context','duplicate_unit','ambiguous_or_unsupported_taxonomy','ambiguous_public_instance'):state['stocks'].pop(s,None)
   if error(e):state['attempts'][s]=attempt;persist();return state
  state['attempts'][s]=attempt;persist()
 persist();return state

def main():
 folder=Path(os.getenv('RISK_DATA_DIR',str(Path(__file__).resolve().parents[1]/'daten')));dest=folder/'cf_edinet_cashflow.json';state=load(dest,{})
 key=os.getenv('EDINET_API_KEY')
 if not key:
  state.update(schema=1,report={'stopped':'edinet_key_missing'});save(dest,state);print(json.dumps(state['report']));return
 start=time.monotonic();last=[0.0]
 def request(path,params,limit):
  if time.monotonic()-start>1680:raise ValueError('budget_exhausted')
  time.sleep(max(0,2-(time.monotonic()-last[0])));last[0]=time.monotonic()
  params={**params,'Subscription-Key':key};url='https://api.edinet-fsa.go.jp/api/v2/'+path+'?'+urllib.parse.urlencode(params)
  with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'ValueApp financial research'}),timeout=20) as response:raw=response.read(limit+1)
  if len(raw)>limit:raise ValueError('response_too_large')
  if raw.lstrip().startswith(b'{'):
   try:status=str(json.loads(raw).get('metadata',{}).get('status'))
   except (ValueError,AttributeError):status=''
   if status in ('401','403','429'):raise ValueError('http_'+status)
  return raw
 state=run(load(folder/'cf_universum.json',{}),load(folder/'cf_risk_coverage.json',{}),state,
  lambda date:json.loads(request('documents.json',{'date':date,'type':2},5_000_000)),
  lambda doc:request('documents/'+doc,{'type':1},30_000_000),checkpoint=lambda s:save(dest,s))
 save(dest,state);print(json.dumps(state['report']))
 if state['report'].get('stopped'):print('::warning::EDINET supply incomplete: '+state['report']['stopped'])
if __name__=='__main__':main()
