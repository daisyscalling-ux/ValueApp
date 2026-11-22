"""Export public general RSS feeds for Cloudflare. No keys or full article bodies."""
import concurrent.futures, datetime as dt, email.utils, html, json, os, re, time
import urllib.request, urllib.parse, xml.etree.ElementTree as ET
from pathlib import Path
SOURCES = {
 'marketwatch': ('MarketWatch', 'https://feeds.content.dowjones.io/public/rss/mw_topstories', 'Publisher-RSS'),
 'fool': ('The Motley Fool', 'https://www.fool.com/feeds/index.aspx', 'Publisher-RSS'),
 'investing': ('Investing.com', 'https://www.investing.com/rss/news_25.rss', 'Publisher-RSS · Stock Market News'),
 # Financial Times: oeffentliche Rubriken-Feeds; nur Titel, Datum, Originallink zu ft.com (kein Text, keine Umleitung).
 'ft': ('Financial Times', ['https://www.ft.com/markets?format=rss','https://www.ft.com/companies?format=rss','https://www.ft.com/technology?format=rss'], 'Publisher-RSS · Märkte, Unternehmen, Technologie'),
 # Bloomberg und Wall Street Journal (seit 16.11.2026): oeffentliche Rubriken-Feeds der Verlage; nur Titel, Datum, Originallink.
 'bloomberg': ('Bloomberg', ['https://www.bloomberg.com/feeds/markets/news.rss','https://www.bloomberg.com/feeds/business/news.rss','https://www.bloomberg.com/feeds/economics/news.rss','https://www.bloomberg.com/feeds/technology/news.rss'], 'Publisher-RSS · Märkte, Wirtschaft, Konjunktur, Technologie'),
 'wsj': ('The Wall Street Journal', ['https://feeds.content.dowjones.io/public/rss/RSSMarketsMain','https://feeds.content.dowjones.io/public/rss/WSJcomUSBusiness','https://feeds.content.dowjones.io/public/rss/socialeconomyfeed','https://feeds.content.dowjones.io/public/rss/RSSWSJD'], 'Publisher-RSS · Märkte, US-Wirtschaft, Konjunktur, Technologie'),
 'yahoo': ('Yahoo Finance', 'https://news.google.com/rss/search?' + urllib.parse.urlencode({'q':'site:finance.yahoo.com (markets OR stocks OR earnings OR economy) when:3d','hl':'en-US','gl':'US','ceid':'US:en'}), 'Google-News-Index · Link über Google')
}
# Welt-Rubriken (seit 22.11.2026, Entscheidung des Nutzers für „Themen des Tages · Welt“): eigene Datei cf_world_news.json,
# damit News-Tab und Trend-Zählung unverändert bleiben. Nur Titel, Datum, Originallink; am 22.11. alle vier öffentlich erreichbar.
WORLD_SOURCES = {
 'bbc_world': ('BBC News', 'https://feeds.bbci.co.uk/news/world/rss.xml', 'Publisher-RSS · World'),
 'ft_world': ('Financial Times', 'https://www.ft.com/world?format=rss', 'Publisher-RSS · World'),
 'wsj_world': ('The Wall Street Journal', 'https://feeds.content.dowjones.io/public/rss/RSSWorldNews', 'Publisher-RSS · World News'),
 'bloomberg_politics': ('Bloomberg', 'https://www.bloomberg.com/feeds/politics/news.rss', 'Publisher-RSS · Politics'),
}
# Regionale Wirtschaftsquellen (seit 22.11.2026, Entscheidung des Nutzers für das News-Briefing): eigene Datei
# cf_regional_news.json; je Quelle die Region im Feld via. Am 22.11. alle acht öffentlich erreichbar.
REGIONAL_SOURCES = {
 'ft_europe': ('Financial Times', 'https://www.ft.com/europe?format=rss', 'Europa · Publisher-RSS'),
 'dw_business': ('Deutsche Welle', 'https://rss.dw.com/rdf/rss-en-bus', 'Europa · Publisher-RSS'),
 'euronews_business': ('Euronews', 'https://www.euronews.com/rss?level=vertical&name=business', 'Europa · Publisher-RSS'),
 'faz_finanzen': ('FAZ', 'https://www.faz.net/rss/aktuell/finanzen/', 'Europa · Publisher-RSS'),
 'tagesschau_wirtschaft': ('tagesschau', 'https://www.tagesschau.de/wirtschaft/index~rss2.xml', 'Europa · Publisher-RSS'),
 'nikkei_asia': ('Nikkei Asia', 'https://asia.nikkei.com/rss/feed/nar', 'Asien · Publisher-RSS'),
 'ft_asia': ('Financial Times', 'https://www.ft.com/asia-pacific?format=rss', 'Asien · Publisher-RSS'),
 'et_markets': ('The Economic Times', 'https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms', 'Asien · Publisher-RSS'),
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
RDF='{http://www.w3.org/1999/02/22-rdf-syntax-ns#}RDF';RSS1='{http://purl.org/rss/1.0/}';DC='{http://purl.org/dc/elements/1.1/}'
def parse_rdf(root, name, via, now):
 """RSS 1.0 (RDF, seit 22.11.2026: Deutsche Welle, Nikkei Asia). Datum aus dc:date; ohne Datum (Nikkei) publishedAt None,
 die Erfassungszeit setzt retrieve() als gekennzeichneten Ersatz (datumErsatz „erfasst“)."""
 articles=[]
 for item in root.findall(RSS1+'item'):
  title=clean(item.findtext(RSS1+'title')); url=clean(item.findtext(RSS1+'link'))
  if not title or urllib.parse.urlsplit(url).scheme not in ('http','https'): continue
  d=item.findtext(DC+'date')
  if d:
   try: stamp=parse_date(d)
   except (ValueError,TypeError,OverflowError): continue
   if stamp>now+300 or now-stamp>7*86400: continue
   articles.append({'title':title,'url':url,'publishedAt':dt.datetime.fromtimestamp(stamp,dt.timezone.utc).isoformat(),'publisher':name,'via':via})
  else:
   articles.append({'title':title,'url':url,'publishedAt':None,'publisher':name,'via':via})
 return articles[:80]
def parse_rss(raw, name, via, now):
 if len(raw)>2000000 or b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():
  raise ValueError('Ungültiger RSS-Feed')
 root=ET.fromstring(raw)
 if root.tag==RDF: return parse_rdf(root, name, via, now)
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
def retrieve(key, old, now, quellen=None):
 name,url,via=(quellen or SOURCES)[key]
 try:
  # Mehrere Feeds einer Quelle (FT-Rubriken): zusammenfuehren, jeden Link nur einmal; Fehler nur, wenn keiner liefert.
  articles=[];seen=set();errors=[]
  for one in (url if isinstance(url,list) else [url]):
   try:
    request=urllib.request.Request(one,headers={'Accept':'application/rss+xml, application/xml','User-Agent':'ValueRadar-News/1.0 (public RSS reader)'})
    with urllib.request.urlopen(request,timeout=20) as response: raw=response.read(2000001)
    frueher={x['url']:x for x in old.get('items',[]) if isinstance(x,dict)}
    for a in parse_rss(raw,name,via,now):
     if a['publishedAt'] is None:
      # Quelle ohne Datum: Erfassungszeit des ersten Abrufs als gekennzeichneter Ersatz; nach 7 Tagen fällt der Artikel weg.
      erst=frueher.get(a['url'],{}).get('publishedAt') if frueher.get(a['url'],{}).get('datumErsatz')=='erfasst' else None
      a['publishedAt']=erst or dt.datetime.fromtimestamp(now,dt.timezone.utc).isoformat();a['datumErsatz']='erfasst'
      if now-dt.datetime.fromisoformat(a['publishedAt']).timestamp()>7*86400: continue
     if a['url'] not in seen: seen.add(a['url']);articles.append(a)
   except Exception as exc:
    errors.append(exc)
  articles=sorted(articles,key=lambda a:a['publishedAt'],reverse=True)[:80]
  if not articles:
   if errors: raise errors[0]
   raise ValueError('Keine aktuellen Artikel')
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
def main(satz='markt'):
 quellen={'welt':WORLD_SOURCES,'regional':REGIONAL_SOURCES}.get(satz,SOURCES)
 path=Path(os.environ.get('NEWS_OUTPUT','value_radar/daten/'+{'welt':'cf_world_news.json','regional':'cf_regional_news.json'}.get(satz,'cf_news.json')))
 try: old=json.loads(path.read_text(encoding='utf-8')).get('sources',{})
 except (OSError,ValueError): old={}
 now=time.time()
 with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
  jobs=[pool.submit(retrieve,k,old.get(k,{}),now,quellen) for k in quellen]
  sources=dict(job.result() for job in jobs)
 snapshot={'version':1,'checkedAt':int(now*1000),'sources':sources}
 path.parent.mkdir(parents=True,exist_ok=True)
 tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(snapshot,ensure_ascii=False),encoding='utf-8');tmp.replace(path)
 for key,status in sources.items():
  print(key+': '+str(len(status['items']))+' Artikel; '+(status['error'] or 'OK'))
  if status['error']: print('::warning::'+key+' nicht aktualisiert: '+status['error'])
 if all(s['error'] for s in sources.values()): raise SystemExit(1)
if __name__=='__main__':
 import sys
 main(sys.argv[1] if len(sys.argv)>1 else 'markt')
