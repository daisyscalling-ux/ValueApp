"""Repair missing listing metadata only; never copy prices or valuation fields."""
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time
import urllib.request
import urllib.parse
from collections import Counter
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from listing_identity import listing_matches
from news_identity import valid_isin,canonical_names

UTC=dt.timezone.utc
ALLOWED={'stock','equity','common','common_stock','ordinary','ordinary_share','adr','dr'}
IDENTITY_FIELDS=('ticker','listing_symbol','isin','currency','name','name_full','security_type','share_class')
def fingerprint(row):
 return hashlib.sha256(json.dumps({k:row.get(k) for k in IDENTITY_FIELDS},sort_keys=True).encode()).hexdigest()
def queries(ticker):
 base=ticker.rsplit('.',1)[0] if '.' in ticker else ticker
 return list(dict.fromkeys([base,re.sub(r'-([A-Z])$',r'.\1',base),re.sub(r'[-.]([A-Z])$','',base)]))[:3]
def names(value,share_class=None):
 value=re.sub(r'\s*\(publ\)\s*$','',str(value or ''),flags=re.I)
 if share_class:value=re.sub(r'\s+class\s+'+re.escape(share_class)+r'\s*$','',value,flags=re.I)
 return canonical_names(value)
def currency(value):return 'GBP' if value in ('GBp','GBX') else value
def validate(row,hits):
 ticker=str(row.get('ticker') or '')
 # Preferred instruments cannot inherit a common-share valuation or cohort.
 if re.fullmatch(r'[A-Z]+-P[A-Z]+',ticker):return None,'preferred_instrument_review'
 exact=[h for h in hits if listing_matches(ticker,h.get('symbol'))]
 if not exact:return None,'exact_listing_not_found'
 identifiers={(h.get('symbol'),h.get('isin')) for h in exact}
 if len(identifiers)!=1:return None,'conflicting_listing_candidates'
 h=exact[0]
 if not valid_isin(h.get('isin')):return None,'valid_isin_missing'
 if str(h.get('type') or h.get('security_type') or '').lower() not in ALLOWED:return None,'unsupported_security_type'
 if row.get('isin') and row['isin']!=h['isin']:return None,'isin_conflict'
 if h.get('currency') and currency(h['currency'])!=currency(row.get('currency')):return None,'currency_conflict'
 share=re.search(r'-([A-Z])\.(?:ST|CO|HE)$',ticker)
 share=share.group(1) if share else None
 candidate_name=h.get('name') or h.get('company_name')
 if not names(row.get('name_full') or row.get('name'),share)&names(candidate_name,share):return None,'issuer_name_mismatch'
 return h,None

def recover(row,search,now=None):
 now=now or dt.datetime.now(UTC)
 if row.get('listing_symbol') and valid_isin(row.get('isin')):return row,{'state':'already_present'}
 if re.fullmatch(r'[A-Z]+-P[A-Z]+',str(row.get('ticker') or '')):return row,{'state':'review','reason':'preferred_instrument_review'}
 hits=[];used=[]
 for q in queries(str(row.get('ticker') or '')):
  used.append(q);hits.extend(search(q))
  if any(listing_matches(row.get('ticker'),h.get('symbol')) for h in hits):break
 h,error=validate(row,hits)
 evidence=[{k:h.get(k) for k in ('symbol','isin','name','company_name','type','currency')} for h in hits if listing_matches(row.get('ticker'),h.get('symbol'))]
 record={'queries':used,'candidates':evidence,'observedAt':now.isoformat(),'source':'ROIC v3 tickers/search'}
 if error:return row,{**record,'state':'review','reason':error}
 # Preserve existing currency, financials, name, industry and their provenance.
 changes={'listing_symbol':h['symbol'],'exchange':h['symbol'].split(':')[0],'isin':h['isin'],
  'security_type':h.get('type') or h.get('security_type'),'is_primary':h.get('is_primary') if isinstance(h.get('is_primary'),bool) else None,
  'listing_metadata_source':'ROIC v3 tickers/search · exact listing and issuer name',
  'listing_metadata_asof':now.isoformat()}
 if not row.get('country') and h.get('listing_country_code'):changes['country']=h['listing_country_code']
 return {**row,**changes},{**record,'state':'repaired','changes':changes}

def load(path,default):
 try:return json.loads(path.read_text(encoding='utf8'))
 except (OSError,ValueError):return default
def save(path,value):
 temp=path.with_suffix('.tmp');temp.write_text(json.dumps(value,ensure_ascii=False,allow_nan=False),encoding='utf8');temp.replace(path)
def run(universe,state,search,now=None,budget=480,checkpoint=None):
 now=now or dt.datetime.now(UTC);start=time.monotonic();counts=Counter();state=state if state.get('schema')==1 else {'schema':1,'stocks':{}}
 targets={r['listing_symbol']:r.get('ticker') for r in universe['kandidaten'] if r.get('listing_symbol')}
 for i,row in enumerate(universe['kandidaten']):
  if row.get('listing_symbol') and valid_isin(row.get('isin')):continue
  symbol=row.get('ticker');fp=fingerprint(row);old=state['stocks'].get(symbol,{})
  if old.get('inputFingerprint')==fp:
   try:
    age=now-dt.datetime.fromisoformat(old['attemptedAt']);cooldown=dt.timedelta(days=1)
    if old.get('state')=='repaired' and dt.timedelta(0)<=age<dt.timedelta(days=30) and targets.get(old['changes']['listing_symbol'],symbol)==symbol:
     universe['kandidaten'][i]={**row,**old['changes']};targets[old['changes']['listing_symbol']]=symbol;counts['reused']+=1;continue
    if dt.timedelta(0)<=age<cooldown:counts['cooldown']+=1;continue
   except (ValueError,KeyError,TypeError):pass
  if time.monotonic()-start>=budget:counts['budgetReached']+=1;break
  try:updated,record=recover(row,search,now)
  except Exception:updated,record=row,{'state':'retry','reason':'provider_unavailable'}
  if record['state']=='repaired':
   target=updated['listing_symbol']
   if targets.get(target,symbol)!=symbol:updated,record=row,{'state':'review','reason':'duplicate_listing_target'}
   else:targets[target]=symbol
  universe['kandidaten'][i]=updated
  state['stocks'][symbol]={**record,'inputFingerprint':fp,'attemptedAt':now.isoformat()}
  counts[record['state']]+=1
  state['summary']=dict(counts);state['generatedAt']=now.isoformat()
  if checkpoint:checkpoint(universe,state)
 state['summary']=dict(counts);state['generatedAt']=now.isoformat()
 return universe,state
def main():
 folder=Path(os.getenv('RISK_DATA_DIR',str(Path(__file__).resolve().parents[1]/'daten')))
 up=folder/'cf_universum.json';sp=folder/'cf_listing_recovery.json';key=os.getenv('ROIC_API_KEY')
 if not key:raise RuntimeError('ROIC_API_KEY missing')
 last=[0.0]
 def search(q):
  time.sleep(max(0,0.5-(time.monotonic()-last[0])));last[0]=time.monotonic()
  url='https://api.roic.ai/v3.0.0/tickers/search?'+urllib.parse.urlencode({'query':q,'apikey':key})
  request=urllib.request.Request(url,headers={'User-Agent':'value-radar','Accept':'application/json'})
  with urllib.request.urlopen(request,timeout=10) as response:data=json.load(response)
  if isinstance(data,list):return data
  if isinstance(data,dict):
   for k in ('data','results','tickers'):
    if isinstance(data.get(k),list):return data[k]
  raise ValueError('unexpected schema')
 u,s=run(load(up,{}),load(sp,{}),search,checkpoint=lambda u,s:(save(up,u),save(sp,s)))
 save(up,u);save(sp,s);print(json.dumps(s['summary']))
if __name__=='__main__':main()

