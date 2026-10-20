"""Official institution-level regulatory evidence, never a holding-company score."""
import datetime as dt, json, math, os, pathlib, re, time, urllib.parse, urllib.request
UTC=dt.timezone.utc
BASE='https://api.fdic.gov/banks/financials'
FIELDS='CERT,NAME,NAMEFULL,NAMEHCR,RSSDHCR,RSSDID,REPDTE,RBCT1CER,RBC1RWAJ,RBCRWAJ,NCLNLSR'
DEFINITIONS='https://api.fdic.gov/banks/docs/risview_properties.yaml'
METRICS={'RBCT1CER':'cet1_ratio','RBC1RWAJ':'tier1_ratio','RBCRWAJ':'total_capital_ratio','NCLNLSR':'noncurrent_loans_ratio'}
def numeric(v):
 return isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v)
def identifier(v):
 s=str(v or '')
 return s if re.fullmatch(r'[1-9][0-9]*',s) else None
def normalize_record(row,period,today):
 if str(row.get('REPDTE'))!=period: raise ValueError('Mixed reporting periods')
 end=dt.datetime.strptime(period,'%Y%m%d').date()
 if end>today: raise ValueError('Future report')
 cert=identifier(row.get('CERT'));rssd=identifier(row.get('RSSDID'))
 if not cert or not rssd or not row.get('NAME'): raise ValueError('Missing institution identity')
 metrics={}
 for field,key in METRICS.items():
  value=row.get(field)
  # Negative capital is possible. Invalid values remain missing, never zero.
  valid=numeric(value) and (-100<=value<=1000 if key!='noncurrent_loans_ratio' else 0<=value<=100)
  metrics[key]={'value':value/100 if valid else None,'state':'reported' if valid else 'missing','raw_value':value if numeric(value) else None,'source_field':field,'source_unit':'percent','unit':'fraction'}
 return {'cert':cert,'rssd_id':rssd,'name':row.get('NAMEFULL') or row['NAME'],'holding_name':row.get('NAMEHCR') or None,'holding_rssd_id':identifier(row.get('RSSDHCR')),'period':end.isoformat(),'scope':'fdic_insured_institution','jurisdiction':'US','regime':'US_call_report','metrics':metrics,'lcr':{'state':'not_collected','value':None},'source_url':BASE+'?'+urllib.parse.urlencode({'filters':f'CERT:{cert} AND REPDTE:{period}','fields':FIELDS,'limit':1,'format':'json'}),'definitions_url':DEFINITIONS,'published_at':None,'historical_point_in_time_usable':False}
def request(params):
 url=BASE+'?'+urllib.parse.urlencode({**params,'format':'json'})
 for attempt in range(2):
  try:
   req=urllib.request.Request(url,headers={'User-Agent':'ValueApp/1.0','Accept':'application/json'})
   with urllib.request.urlopen(req,timeout=20) as r:
    body=r.read(15000001)
    if len(body)>15000000: raise ValueError('Response too large')
    return json.loads(body)
  except Exception:
   if attempt: raise
   time.sleep(2)
def collect(fetch=request,today=None):
 today=today or dt.datetime.now(UTC).date()
 head=fetch({'fields':'REPDTE','sort_by':'REPDTE','sort_order':'DESC','limit':1})
 period=str(head['data'][0]['data']['REPDTE'])
 dt.datetime.strptime(period,'%Y%m%d')
 records={};expected=None;offset=0
 while True:
  data=fetch({'filters':'REPDTE:'+period,'fields':FIELDS,'sort_by':'CERT','sort_order':'ASC','limit':1000,'offset':offset})
  total=data['meta']['total']
  if not isinstance(total,int) or not 1<=total<=20000: raise ValueError('Unexpected record count')
  if expected is not None and total!=expected: raise ValueError('Source changed during pagination')
  expected=total;rows=data.get('data',[])
  if not rows: raise ValueError('Incomplete pagination')
  for item in rows:
   record=normalize_record(item['data'],period,today)
   if record['cert'] in records: raise ValueError('Duplicate institution')
   records[record['cert']]=record
  offset+=len(rows)
  if offset>=total: break
  time.sleep(.2)
 if len(records)!=expected: raise ValueError('Incomplete archive')
 return {'schema':1,'retrieved_at':dt.datetime.now(UTC).isoformat(),'reporting_period':dt.datetime.strptime(period,'%Y%m%d').date().isoformat(),'institution_count':len(records),'source':'FDIC BankFind financials','institutions':records,'limitations':['Institution data is not consolidated holding-company data.','No LCR or insurance solvency data supplied by this collector.','Retrieval time is not original publication time.','Noncurrent loans ratio is the FDIC definition, not a harmonized IFRS NPL ratio.']}
def name_key(name):
 return re.sub(r'[^A-Z0-9]','',str(name or '').upper())
def coverage(universe,data):
 # Names produce REVIEW CANDIDATES only; never authorize a financial transfer.
 by_name={}
 for cert,row in data['institutions'].items():
  if row.get('holding_name'): by_name.setdefault(name_key(row['holding_name']),[]).append(cert)
 rows=[]
 for r in universe.get('kandidaten',[]):
  industry=str(r.get('industry','')).lower()
  if not any(x in industry for x in ['bank','insurance','financial conglomerate']): continue
  candidates=by_name.get(name_key(r.get('name')),[])
  rows.append({'symbol':r.get('listing_symbol') or r.get('ticker'),'name':r.get('name'),'country':r.get('country'),'industry':r.get('industry'),'state':'identity_review' if candidates else 'source_mapping_required','fdic_name_candidates':candidates,'group_metrics':None,'score':None})
 return {'schema':1,'generated_at':data['retrieved_at'],'universe_asof':universe.get('stand'),'stocks':rows,'summary':{'financial_listings':len(rows),'name_candidates_for_review':sum(bool(r['fdic_name_candidates']) for r in rows),'verified_group_metrics':0},'other_sources':{'EEA_banks':'https://www.eba.europa.eu/risk-and-data-analysis/pillar-3-data-hub','insurance':'Issuer SFCR / jurisdiction-specific regulatory disclosures; no individual ratios imported from aggregate EIOPA statistics'}}
def save(path,value):
 path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix('.tmp')
 tmp.write_text(json.dumps(value,ensure_ascii=False,allow_nan=False),encoding='utf8');tmp.replace(path)
def main():
 folder=pathlib.Path(os.getenv('REGULATORY_OUTPUT','value_radar/daten/regulatory'))
 universe=pathlib.Path(os.getenv('REGULATORY_UNIVERSE','value_radar/daten/cf_universum.json'))
 try:
  data=collect();report=coverage(json.loads(universe.read_text(encoding='utf8')),data)
  holding_path=folder/'bhcf-import.json'
  if holding_path.exists():
   from import_bhcf import link_fdic
   holding_links=link_fdic(json.loads(holding_path.read_text(encoding='utf8')),data)
  else:
   holding_links={'schema':1,'state':'not_imported','score':None}
 except Exception as e:
  save(folder/'status.json',{'attempted_at':dt.datetime.now(UTC).isoformat(),'state':'failed','reason':type(e).__name__,'previous_observations_retained':True})
  raise
 save(folder/('fdic-'+data['reporting_period']+'.json'),data)
 save(folder/'fdic-latest.json',data);save(folder/'coverage.json',report)
 save(folder/'holding-links.json',holding_links)
 save(folder/'status.json',{'attempted_at':data['retrieved_at'],'state':'success','institution_count':data['institution_count'],'reporting_period':data['reporting_period']})
 print(json.dumps({'institutions':data['institution_count'],'period':data['reporting_period'],**report['summary']}))
if __name__=='__main__':main()
