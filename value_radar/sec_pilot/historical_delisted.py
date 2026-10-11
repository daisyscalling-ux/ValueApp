"""Bounded delisting registry for coverage audits, not security identifiers/returns."""
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import time
import urllib.error
import urllib.parse
import urllib.request
from historical_sources import NoRedirect

FIELDS=('symbol','companyName','exchange','ipoDate','delistedDate')

def normalize(row):
    if not isinstance(row,dict):raise ValueError('row is not an object')
    result={k:row.get(k) for k in FIELDS}
    for k in ('symbol','companyName','exchange'):
        if not isinstance(result[k],str) or not result[k].strip():raise ValueError('missing identity hint')
        result[k]=result[k].strip()
    for k in ('ipoDate','delistedDate'):
        value=result[k]
        if k=='ipoDate' and value in (None,''):result[k]=None;continue
        if not isinstance(value,str) or dt.date.fromisoformat(value).isoformat()!=value:raise ValueError('invalid date')
    if result['ipoDate'] and result['ipoDate']>result['delistedDate']:raise ValueError('inverted listing dates')
    result['source']='https://financialmodelingprep.com/stable/delisted-companies'
    result['identity_status']='unresolved_security_id'
    return result

def collect(fetch_page,max_pages=10):
    rows=[];seen=set();page_hashes=set();pages=[];invalid=0;duplicates=0;status='page_limit'
    for page in range(max_pages):
        data=fetch_page(page)
        if not isinstance(data,list):status='unrecognized_response';break
        if not data:status='provider_end_reached';break
        digest=hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()
        if digest in page_hashes:status='repeated_page';break
        page_hashes.add(digest);pages.append({'page':page,'rows':len(data),'sha256':digest})
        for raw in data:
            try:r=normalize(raw)
            except (ValueError,TypeError):invalid+=1;continue
            # Never deduplicate by ticker alone: it may have been reused.
            identity=tuple(r[k] for k in FIELDS)
            if identity in seen:duplicates+=1;continue
            seen.add(identity);rows.append(r)
    return {'schema':1,'retrieved_at':dt.datetime.now(dt.timezone.utc).isoformat(),
            'status':status,'pages':pages,'invalid_rows':invalid,'duplicates':duplicates,
            'records':rows,'complete_historical_universe_verified':False,
            'limitations':['Provider delisting list only, not historical index membership.',
              'Company and ticker hints are not permanent security IDs.',
              'No terminal proceeds or total returns. End of pagination does not certify historical completeness.']}

def run():
    key=os.environ.get('FMP_API_KEY','').strip();out=Path('historical-universe-output');out.mkdir(exist_ok=True)
    if not key:
        report={'status':'missing_secret','records':[],'complete_historical_universe_verified':False}
    else:
        errors=[]
        def fetch(page):
            time.sleep(.3)
            url='https://financialmodelingprep.com/stable/delisted-companies?'+urllib.parse.urlencode({'page':page,'limit':100,'apikey':key})
            try:
                req=urllib.request.Request(url,headers={'User-Agent':'ValueApp delisting coverage audit'})
                with urllib.request.build_opener(NoRedirect).open(req,timeout=20) as response:
                    raw=response.read(2_000_001)
                    if len(raw)>2_000_000:raise ValueError('too large')
                    return json.loads(raw)
            except urllib.error.HTTPError as exc:
                errors.append({'page':page,'http':exc.code});return None
            except Exception:
                errors.append({'page':page,'status':'network_or_parse_error'});return None
        report=collect(fetch);report['errors']=errors
    encoded=json.dumps(report,indent=2,allow_nan=False)
    if key:encoded=encoded.replace(key,'[redacted]')
    (out/'delisted-registry.json').write_text(encoded,encoding='utf8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('records','pages')}))
    print('Registry rows:',len(report['records']))

if __name__=='__main__':run()
