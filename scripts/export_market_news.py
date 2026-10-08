"""Export public general RSS feeds for Cloudflare. No keys or full article bodies."""
import concurrent.futures, datetime as dt, email.utils, html, json, os, re, time
import urllib.request, urllib.parse, xml.etree.ElementTree as ET
from pathlib import Path
SOURCES = {
 'marketwatch': ('MarketWatch', 'https://feeds.content.dowjones.io/public/rss/mw_topstories', 'Publisher-RSS'),
 'fool': ('The Motley Fool', 'https://www.fool.com/feeds/index.aspx', 'Publisher-RSS'),
 'investing': ('Investing.com', 'https://www.investing.com/rss/news_25.rss', 'Publisher-RSS · Stock Market News'),
 'yahoo': ('Yahoo Finance', 'https://news.google.com/rss/search?' + urllib.parse.urlencode({'q':'site:finance.yahoo.com (markets OR stocks OR earnings OR economy) when:3d','hl':'en-US','gl':'US','ceid':'US:en'}), 'Google-News-Index · Link über Google')
}
def clean(value):
 return html.unescape(re.sub(r'<[^>]*>', '', value or '')).strip()
def parse_date(value):
 # Investing RSS omits the zone. Interpret its ISO-like timestamps as UTC,
 # consistently with the Worker; never use the runner's local timezone.
 try: parsed=email.utils.parsedate_to_datetime(value)
 except (ValueError,TypeError): parsed=dt.datetime.fromisoformat(value.replace('Z','+00:00'))
 if parsed.tzinfo is None: parsed=parsed.replace(tzinfo=dt.timezone.utc)
 return parsed.timestamp()
def parse_rss(raw, name, via, now):
 if len(raw)>2000000 or b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():
  raise ValueError('Ungültiger RSS-Feed')
 root=ET.fromstring(raw)
 if root.tag!='rss' or root.find('channel') is None: raise ValueError('Kein RSS-Feed')
 articles=[]
 for item in root.findall('./channel/item'):
  title=clean(item.findtext('title')); url=clean(item.findtext('link'))
  if not title or urllib.parse.urlsplit(url).scheme not in ('http','https'): continue
  try:
   stamp=parse_date(item.findtext('pubDate') or '')
  except (ValueError,TypeError,OverflowError): continue
  if stamp>now+300 or now-stamp>7*86400: continue
  articles.append({'title':title,'url':url,'publishedAt':dt.datetime.fromtimestamp(stamp,dt.timezone.utc).isoformat(),'publisher':clean(item.findtext('source')) or name,'via':via})
 return articles[:80]
def retrieve(key, old, now):
 name,url,via=SOURCES[key]
 try:
  request=urllib.request.Request(url,headers={'Accept':'application/rss+xml, application/xml','User-Agent':'ValueRadar-News/1.0 (public RSS reader)'})
  with urllib.request.urlopen(request,timeout=20) as response: raw=response.read(2000001)
  articles=parse_rss(raw,name,via,now)
  if not articles: raise ValueError('Keine aktuellen Artikel')
  return key,dict(name=name,via=via,checkedAt=int(now*1000),successAt=int(now*1000),error=None,items=articles)
 except Exception as exc:
  # Only status/type, never arbitrary response text.
  reason=('HTTP '+str(exc.code)) if hasattr(exc,'code') else type(exc).__name__
  retained=[]
  for a in old.get('items',[]):
   try:
    age=now-dt.datetime.fromisoformat(a['publishedAt'].replace('Z','+00:00')).timestamp()
    if 0<=age<=7*86400: retained.append(a)
   except (ValueError,KeyError,TypeError): pass
  return key,dict(name=name,via=via,checkedAt=int(now*1000),successAt=old.get('successAt',0),error=reason,items=retained)
def main():
 path=Path(os.environ.get('NEWS_OUTPUT','value_radar/daten/cf_news.json'))
 try: old=json.loads(path.read_text(encoding='utf-8')).get('sources',{})
 except (OSError,ValueError): old={}
 now=time.time()
 with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
  jobs=[pool.submit(retrieve,k,old.get(k,{}),now) for k in SOURCES]
  sources=dict(job.result() for job in jobs)
 snapshot={'version':1,'checkedAt':int(now*1000),'sources':sources}
 path.parent.mkdir(parents=True,exist_ok=True)
 tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(snapshot,ensure_ascii=False),encoding='utf-8');tmp.replace(path)
 for key,status in sources.items():
  print(key+': '+str(len(status['items']))+' Artikel; '+(status['error'] or 'OK'))
  if status['error']: print('::warning::'+key+' nicht aktualisiert: '+status['error'])
 if all(s['error'] for s in sources.values()): raise SystemExit(1)
if __name__=='__main__': main()
