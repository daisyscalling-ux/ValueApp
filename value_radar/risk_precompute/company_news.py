"""Bounded company-news collection. Store links/headlines, never article bodies."""
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import time
import urllib.error
import urllib.parse
import urllib.request

UTC=dt.timezone.utc
BASE='https://api.roic.ai/v2/company/news/'
PATTERNS={
 'earnings_warning':r'profit warning|cuts? (?:its )?(?:outlook|forecast|guidance)|gewinnwarnung|prognose gesenkt',
 'credit_distress':r'bankruptcy|insolvency|debt default|insolvenz|zahlungsausfall',
 'legal_regulatory':r'antitrust|lawsuit|regulatory investigation|kartell|klage|ermittlung',
 'operations':r'product recall|data breach|cyberattack|production halt|rückruf|datenleck|produktionsstopp',
 'competition':r'price war|new competitor|market share loss|preiskampf|marktanteilsverlust',
}
def stamp(value):
 try:
  d=dt.datetime.fromisoformat(str(value).replace('Z','+00:00'))
  return d.astimezone(UTC) if d.tzinfo else None
 except (ValueError,TypeError):return None

def identifier(row):
 # Avoid naked ticker collisions: prefer a globally scoped instrument/company ID.
 isin=str(row.get('isin') or '').upper()
 if re.fullmatch('[A-Z]{2}[A-Z0-9]{9}[0-9]',isin):return isin
 cik=str(row.get('cik') or '').strip()
 if re.fullmatch('[0-9]{1,10}',cik) and int(cik)>0:return cik.zfill(10)
 return None

def normalize(payload,now):
 rows=payload if isinstance(payload,list) else payload.get('data') if isinstance(payload,dict) else None
 if not isinstance(rows,list):raise ValueError('unexpected_response_schema')
 items={};rejected=0
 for r in rows:
  if not isinstance(r,dict):rejected+=1;continue
  title=r.get('title');url=r.get('article_url');date=stamp(r.get('published_date'))
  parts=urllib.parse.urlsplit(url) if isinstance(url,str) else None
  if not isinstance(title,str) or not title.strip() or not parts or parts.scheme not in ['https','http'] or not parts.netloc or parts.username or not date or not dt.timedelta(0)<=now-date<=dt.timedelta(days=7):
   rejected+=1;continue
  # Tracking parameters do not produce independent evidence.
  clean=urllib.parse.urlunsplit((parts.scheme,parts.netloc.lower(),parts.path,urllib.parse.urlencode([(k,v) for k,v in urllib.parse.parse_qsl(parts.query) if not k.lower().startswith('utm_') and k not in ['mod','ref']]),''))
  title=' '.join(title.split())[:500]
  dedup=hashlib.sha256((parts.netloc.lower()+'|'+title.casefold()).encode()).hexdigest()
  items.setdefault(dedup,{'title':title,'url':clean,'publishedAt':date.isoformat(),'publisher':str(r.get('site') or parts.netloc)[:150],
    'eventCandidates':[k for k,p in PATTERNS.items() if re.search(p,title,re.I)],'verified':False})
 return {'items':sorted(items.values(),key=lambda x:x['publishedAt'],reverse=True),'rejectedArticles':rejected,'rawArticleCount':len(rows),'truncated':len(rows)>=30}

def save(path,data):
 path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix('.tmp')
 tmp.write_text(json.dumps(data,ensure_ascii=False,allow_nan=False),encoding='utf8');tmp.replace(path)

def fetch(ident,key,now):
 query=urllib.parse.urlencode({'apikey':key,'limit':30,'date_start':(now-dt.timedelta(days=7)).date().isoformat()})
 req=urllib.request.Request(BASE+urllib.parse.quote(ident,safe='')+'?'+query,headers={'Accept':'application/json','User-Agent':'ValueApp/1.0'})
 with urllib.request.urlopen(req,timeout=12) as response:
  body=response.read(4_000_001)
  if len(body)>4_000_000:raise ValueError('response_too_large')
  return json.loads(body)

def main():
 folder=Path(os.getenv('RISK_DATA_DIR','value_radar/daten'));path=folder/'cf_company_news.json'
 universe=json.loads((folder/'cf_universum.json').read_text(encoding='utf8'))
 archive=json.loads(path.read_text(encoding='utf8')) if path.exists() else {'schema':1,'stocks':{}}
 if archive.get('schema')!=1:raise ValueError('unsupported_archive')
 key=os.getenv('ROIC_API_KEY','');now=dt.datetime.now(UTC);deadline=time.monotonic()+min(25,max(1,float(os.getenv('NEWS_BUDGET_MIN','20'))))*60
 groups={};symbol_rows={}
 for row in universe['kandidaten']:
  symbol=str(row.get('listing_symbol') or row.get('ticker') or '').upper()
  if symbol:symbol_rows.setdefault(symbol,[]).append(row)
 for symbol,rows in symbol_rows.items():
  ident=identifier(rows[0]) if len(rows)==1 else None
  if not ident:
   old=archive['stocks'].get(symbol,{})
   archive['stocks'][symbol]=old if len(rows)==1 and old and not old.get('identifier') else {'identifier':None,'items':[],'successAt':None,'error':'unique_company_identifier_missing'}
   continue
  old=archive['stocks'].get(symbol,{})
  if old.get('identifier')!=ident:old={};archive['stocks'][symbol]=old
  groups.setdefault(ident,[]).append(symbol)
 def last_attempt(pair):
  return min((stamp(archive['stocks'].get(s,{}).get('attemptedAt')) or dt.datetime.min.replace(tzinfo=UTC)) for s in pair[1])
 attempted=0;stop='complete';next_request=0
 for ident,symbols in sorted(groups.items(),key=last_attempt):
  if time.monotonic()>deadline:stop='budget';break
  if not key:stop='missing_api_key';break
  old_rows=[archive['stocks'].get(s,{}) for s in symbols]
  if all(stamp(o.get('successAt')) and dt.timedelta(0)<=now-stamp(o['successAt'])<dt.timedelta(hours=20) for o in old_rows):continue
  if all(stamp(o.get('attemptedAt')) and dt.timedelta(0)<=now-stamp(o['attemptedAt'])<dt.timedelta(hours=6) for o in old_rows):continue
  time.sleep(max(0,next_request-time.monotonic()));next_request=time.monotonic()+.7
  at=dt.datetime.now(UTC).isoformat();error=None;data=None;code=None
  try:data=normalize(fetch(ident,key,now),now)
  except urllib.error.HTTPError as e:code=e.code;error='http_'+str(code)
  except Exception as e:error=type(e).__name__ # never publish URLs containing keys
  for symbol in symbols:
   old=archive['stocks'].get(symbol,{})
   archive['stocks'][symbol]={**old,'identifier':ident,'attemptedAt':at,'error':error}
   if data is not None:
    archive['stocks'][symbol]['roicResult']={'checkedAt':at,'rawArticleCount':data['rawArticleCount'],'acceptedArticles':len(data['items'])}
    # Do not erase a recent successful alternative with an empty primary response.
    if data['items'] or old.get('source') not in ['Yahoo Finance','Google News · Suchindex'] or not stamp(old.get('successAt')) or now-stamp(old['successAt'])>dt.timedelta(hours=36):
     archive['stocks'][symbol].update(data,successAt=at,source='ROIC')
  attempted+=1
  if attempted%20==0:save(path,archive)
  if code in [401,402,403,429]:stop='provider_'+str(code);break
 fallback_attempted=0;fallback_recovered=0
 from yahoo_company_news import collect as yahoo_collect,error_code
 def needs_fallback(symbol):
  old=archive['stocks'].get(symbol,{})
  success=stamp(old.get('successAt'))
  recent_items=[i for i in old.get('items',[]) if stamp(i.get('publishedAt')) and dt.timedelta(0)<=now-stamp(i['publishedAt'])<=dt.timedelta(days=7)]
  return not recent_items or not success or not dt.timedelta(0)<=now-success<=dt.timedelta(hours=36)
 candidates=[s for s in symbol_rows if len(symbol_rows[s])==1 and needs_fallback(s)]
 candidates.sort(key=lambda s:stamp(archive['stocks'].get(s,{}).get('fallbackAttemptAt')) or dt.datetime.min.replace(tzinfo=UTC))
 for symbol in candidates:
  if time.monotonic()+19>deadline or fallback_attempted>=100:break
  old=archive['stocks'].get(symbol,{})
  last=stamp(old.get('fallbackAttemptAt'))
  if last and dt.timedelta(0)<=now-last<dt.timedelta(hours=20):continue
  at=dt.datetime.now(UTC).isoformat();old['fallbackAttemptAt']=at;fallback_attempted+=1
  try:
   result=yahoo_collect(symbol_rows[symbol][0]);data=normalize(result['rows'],dt.datetime.now(UTC))
   old.update(data,successAt=at,source='Yahoo Finance',identityEvidence=result['evidence'],error=None,fallbackError=None)
   fallback_recovered+=bool(data['items'])
  except Exception as e:old['fallbackError']=error_code(e)
  archive['stocks'][symbol]=old
  if fallback_attempted%10==0:save(path,archive)
 # RSS is a search index: conservative full-name headline matching, no ticker guesses.
 from google_company_news import collect as google_collect
 google_attempted=0;google_recovered=0
 candidates=[s for s in symbol_rows if len(symbol_rows[s])==1 and needs_fallback(s)]
 candidates.sort(key=lambda s:stamp(archive['stocks'].get(s,{}).get('googleAttemptAt')) or dt.datetime.min.replace(tzinfo=UTC))
 for symbol in candidates:
  if time.monotonic()+12>deadline or google_attempted>=50:break
  old=archive['stocks'].get(symbol,{})
  last=stamp(old.get('googleAttemptAt'))
  if last and dt.timedelta(0)<=now-last<dt.timedelta(hours=20):continue
  at=dt.datetime.now(UTC).isoformat();old['googleAttemptAt']=at;google_attempted+=1
  try:
   result=google_collect(symbol_rows[symbol][0],dt.datetime.now(UTC));data=normalize(result['rows'],dt.datetime.now(UTC))
   old['googleResult']={'checkedAt':at,'rawArticleCount':result['rawArticleCount'],'acceptedArticles':len(data['items']),'rejectedCandidates':result['rejectedCandidates']}
   old['googleError']=None
   if data['items']:
    old.update(data,successAt=at,source='Google News · Suchindex',error=None)
    google_recovered+=1
  except urllib.error.HTTPError as e:old['googleError']='http_'+str(e.code)
  except Exception as e:old['googleError']=type(e).__name__
  archive['stocks'][symbol]=old
  if google_attempted%10==0:save(path,archive)
 archive['stocks']={s:v for s,v in archive['stocks'].items() if s in symbol_rows}
 archive.update(generatedAt=dt.datetime.now(UTC).isoformat(),report={'attemptedCompanies':attempted,'uniqueIdentifiers':len(groups),'stop':stop,'fallbackAttempted':fallback_attempted,'fallbackRecoveredListings':fallback_recovered},
   limitations=['Latest 30 ROIC/Yahoo articles per query; Google RSS at most 100 candidates; seven-day lookback, not exhaustive.','Google is a search index; publication dates and company mentions are not independently confirmed.','Headline tags are unverified review candidates, not adverse-event findings.','Empty results, unsupported languages and fetch failures do not establish low risk.'])
 archive['report'].update(googleAttempted=google_attempted,googleRecoveredListings=google_recovered)
 save(path,archive);print(json.dumps(archive['report']))
 if stop in ['missing_api_key','provider_401','provider_402','provider_403']:raise SystemExit(1)

if __name__=='__main__':main()

