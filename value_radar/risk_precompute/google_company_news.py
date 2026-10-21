"""Conservative Google News RSS fallback: headline candidates, not verified events."""
import datetime as dt
from email.utils import parsedate_to_datetime
import re
import unicodedata
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

FILTER_VERSION=2

def headline_rejection(title,name,publisher=''):
    if ' '+' '.join(words(name))+' ' not in ' '+' '.join(words(title))+' ':return 'company_name_missing'
    # Navigation, quote/profile pages and discussions are not dated news stories.
    patterns=(r'options? chain|stock price|stock forecast|stock quote|bond price|market cap|'
      r'research\s*&\s*ratings|analyst insights|analyst ratings, estimates|price targets.*recommendations|'
      r'forum (?:&|and)|discussion|profile (?:&|and) facts|performance\s*&\s*quotes|'
      r'technical analysis:|support, resistance|regulatory news\. live|news\s*\||'
      r'analyst predictions|stock grades|common equity to total deposits|market is going to boom|'
      r'tokenized|cryptocurrency|price today|latest stock news|news and headlines|institutional ownership 20\d\d')
    if re.search(patterns,title,re.I) or 'tradingview' in publisher.casefold():return 'non_article_page'
    # Company-only titles, optionally a ticker in parentheses, contain no event.
    stripped=re.sub(r'\([^)]*\)',' ',title).replace('$','')
    if words(stripped)==words(name):return 'company_only_title'
    return None

def clean_cached(archive,symbol_rows):
    removed=0
    for symbol,entry in archive.get('stocks',{}).items():
        rows=symbol_rows.get(symbol,[])
        if entry.get('source')!='Google News · Suchindex' or len(rows)!=1:continue
        name=rows[0].get('name_full') or rows[0].get('name') or ''
        items=entry.get('items',[])
        kept=[i for i in items if not headline_rejection(i.get('title',''),name,i.get('publisher',''))]
        removed+=len(items)-len(kept)
        entry.update(items=kept,googleFilterVersion=FILTER_VERSION)
        entry['googleRemovedNonArticles']=entry.get('googleRemovedNonArticles',0)+len(items)-len(kept)
    return removed

def words(value):
    value=unicodedata.normalize('NFKD',str(value or '')).casefold()
    value=''.join(c for c in value if not unicodedata.combining(c))
    return re.findall(r'[^\W_]+',value,flags=re.UNICODE)

def query_name(row):
    name=str(row.get('name_full') or row.get('name') or '').strip()
    tokens=words(name)
    if len(tokens)<2 or len(name)>180 or name.lower()=='unknown':
        raise ValueError('google_identity_name_insufficient')
    return name

def parse_feed(raw,name,now):
    if len(raw)>2_000_000:raise ValueError('google_response_too_large')
    root=ET.fromstring(raw)
    if root.tag!='rss' or root.find('channel') is None:raise ValueError('google_response_schema')
    rows=[];rejected=0;items=root.findall('./channel/item')
    needle=' '+' '.join(words(name))+' '
    for item in items[:100]:
        title=item.findtext('title') or ''
        publisher=item.findtext('source') or ''
        headline=title.removesuffix(' - '+publisher) if publisher else title
        link=item.findtext('link') or '';parts=urllib.parse.urlsplit(link)
        try:date=parsedate_to_datetime(item.findtext('pubDate') or '')
        except (ValueError,TypeError):date=None
        # Full supplied company name, word boundaries; no fuzzy ticker matching.
        if headline_rejection(headline,name,publisher) or not date or not date.tzinfo or not dt.timedelta(0)<=now-date<=dt.timedelta(days=7) or parts.scheme!='https' or parts.hostname!='news.google.com' or parts.username or not parts.path.startswith('/rss/articles/'):
            rejected+=1;continue
        rows.append({'title':headline,'article_url':link,'published_date':date.isoformat(),'site':publisher or 'Google News index'})
    return {'rows':rows,'rawArticleCount':len(items),'rejectedCandidates':rejected}

def collect(row,now,timeout=10):
    name=query_name(row)
    query='"'+name.replace('"','')+'" when:7d'
    url='https://news.google.com/rss/search?'+urllib.parse.urlencode({'q':query,'hl':'en-US','gl':'US','ceid':'US:en'})
    request=urllib.request.Request(url,headers={'User-Agent':'ValueApp company news RSS reader'})
    with urllib.request.urlopen(request,timeout=timeout) as response:raw=response.read(2_000_001)
    return parse_feed(raw,name,now)

