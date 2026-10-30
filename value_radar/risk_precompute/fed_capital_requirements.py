"""Verify reviewed Fed requirements against their original document, without guessing new rules."""
import datetime as dt,hashlib,json,os,urllib.request
from pathlib import Path
from yahoo_sector import load,save
URL='https://www.federalreserve.gov/publications/files/large-bank-capital-requirements-20260624.pdf'

def valid_registry(r):
 try:
  if r['schema']!=1 or r['method']!='fed-cet1-requirement-v1' or r['sourceUrl']!=URL:return False
  if not dt.date.fromisoformat(r['publicationDate'])<=dt.date.fromisoformat(r['applicableFrom'])<=dt.date.fromisoformat(r['reviewExpires']):return False
  ids=[e['rssdId'] for e in r['entries']]
  return bool(ids) and len(ids)==len(set(ids)) and all(e['holdingName'] and all(type(e[k]) is int and 0<=e[k]<=10000 for k in ('minimumBps','stressBufferBps','gsibBps','totalBps')) and e['minimumBps']==450 and e['stressBufferBps']>=250 and sum(e[k] for k in ('minimumBps','stressBufferBps','gsibBps'))==e['totalBps'] for e in r['entries'])
 except (KeyError,TypeError,ValueError):return False

def fetch():
 req=urllib.request.Request(URL,headers={'User-Agent':'ValueApp regulatory source verification'})
 with urllib.request.urlopen(req,timeout=20) as response:
  if response.geturl()!=URL:raise ValueError('source_redirected')
  data=response.read(2_000_001)
 if len(data)>2_000_000 or not data.startswith(b'%PDF-'):raise ValueError('source_not_expected_pdf')
 return data

def collect(registry,previous,now=None,fetcher=fetch):
 now=now or dt.datetime.now(dt.timezone.utc);today=now.date().isoformat()
 out={'schema':1,'generatedAt':now.isoformat(),'state':'missing','reason':'invalid_or_expired_registry'}
 if not valid_registry(registry) or not registry['applicableFrom']<=today<=registry['reviewExpires']:return out
 digest=hashlib.sha256(json.dumps(registry,sort_keys=True).encode()).hexdigest()
 try:actual=hashlib.sha256(fetcher()).hexdigest()
 except Exception:
  try:
   verified=dt.datetime.fromisoformat(previous['sourceVerifiedAt'].replace('Z','+00:00'))
   if previous['state']=='available' and previous['registryDigest']==digest and previous['sourceSha256']==registry['sourceSha256'] and verified.tzinfo and 0<=(now-verified).total_seconds()<=7*86400:
    return {**previous,'generatedAt':now.isoformat(),'refreshState':'fetch_failed_using_dated_verification'}
  except (KeyError,TypeError,ValueError):pass
  return {**out,'reason':'source_unreachable_no_recent_verification'}
 if actual!=registry['sourceSha256']:return {**out,'reason':'source_changed_review_required'}
 return {**registry,'generatedAt':now.isoformat(),'state':'available','sourceVerifiedAt':now.isoformat(),'registryDigest':digest,'refreshState':'verified','scoreContribution':0}

def requirement_for(capital,archive,now):
 try:
  verified=dt.datetime.fromisoformat(archive['sourceVerifiedAt'].replace('Z','+00:00'))
  if archive['state']!='available' or not valid_registry(archive) or not verified.tzinfo or not 0<=(now-verified).total_seconds()<=7*86400:return None
  if not archive['applicableFrom']<=capital['period']<=archive['reviewExpires'] or now.date().isoformat()>archive['reviewExpires']:return None
  entries=[e for e in archive['entries'] if e['rssdId']==capital['rssdId'] and e['holdingName']==capital['holdingName']]
  if len(entries)!=1:return None
  return {**entries[0],**{k:archive[k] for k in ('method','sourceUrl','sourceSha256','sourcePage','sourceVerifiedAt','publicationDate','applicableFrom','reviewExpires')},'state':'available','unit':'fraction','value':entries[0]['totalBps']/10000,'comparisonPeriod':capital['period']}
 except (KeyError,ValueError,TypeError):return None

def main():
 folder=Path(os.getenv('RISK_DATA_DIR',str(Path(__file__).resolve().parents[1]/'daten')))
 registry=load(Path(__file__).resolve().parents[1]/'regulatory_export/fed-capital-requirements.json',{})
 path=folder/'cf_capital_requirements.json';result=collect(registry,load(path,{}));save(path,result)
 print({'state':result['state'],'reason':result.get('reason'),'refresh':result.get('refreshState')})
if __name__=='__main__':main()

