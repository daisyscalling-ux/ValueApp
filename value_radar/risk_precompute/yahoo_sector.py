"""Bounded, resumable sector metadata and adjusted-price fallback. No price forecasts."""
import datetime as dt
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from collections import Counter
from yahoo_company_news import verify_profile, error_code, currency
from news_identity import prepare_universe, valid_isin
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from listing_reference import apply_reference
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'fundamental_export'))
from listing_identity import listing_matches

UTC=dt.timezone.utc
FIELDS=('listing_symbol','ticker','isin','currency','name_full','name','security_type','share_class')
VENUES={'NASDAQ':{'NMS','NGM','NCM'},'NYSE':{'NYQ'},'AMEX':{'ASE'},'NYSEAMERICAN':{'ASE'},
 'OTC':{'PNK','OQX','OQB','OEM'},'XETR':{'GER'},'FRA':{'FRA'},'LSE':{'LSE'},
 'TSE':{'JPX','TYO'},'TYO':{'JPX','TYO'},'JPX':{'JPX','TYO'},'HKEX':{'HKG'},
 'EPA':{'PAR'},'AMS':{'AMS'},'EURONEXT':{'PAR','AMS','BRU','LIS','ISE'},'MIL':{'MIL'},
 'SIX':{'EBS','SWX'},'STO':{'STO'},'BME':{'MCE'},'OSL':{'OSL'},'HEL':{'HEL'},
 'CPH':{'CPH'},'TSX':{'TOR'},'ASX':{'ASX'},'VIE':{'VIE'},
 # Yahoo profile.exchange and chart.exchangeName, verified 2026-10-24.
 'GPW':{'WSE'},'ATHEX':{'ATH'}}

def identity(row): return {k:row.get(k) for k in FIELDS}
def recent(value,now,days):
    try:
        date=dt.datetime.fromisoformat(str(value).replace('Z','+00:00'))
        return date.tzinfo is not None and dt.timedelta(0)<=now-date<=dt.timedelta(days=days)
    except (TypeError,ValueError): return False

def profile(row,info,original=None,now=None):
    now=now or dt.datetime.now(UTC)
    if not valid_isin(row.get('isin')) or not listing_matches(row.get('ticker'),row.get('listing_symbol')):
        raise ValueError('yahoo_ambiguous_listing')
    evidence=verify_profile(row,info)
    venue=str(row.get('listing_symbol','')).split(':')[0]
    if info.get('exchange') not in VENUES.get(venue,set()): raise ValueError('yahoo_ambiguous_listing')
    sector=info.get('sectorKey');industry=info.get('industryKey')
    if not all(isinstance(v,str) and re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*',v) for v in (sector,industry)):
        sector=industry=None
    return {'inputIdentity':identity(original or row),'retrievedAt':now.isoformat(),
      'evidence':evidence,'source':'Yahoo Finance','sourceUrl':'https://finance.yahoo.com/quote/'+row['ticker']+'/profile/',
      'sectorKey':sector,'industryKey':industry,'industryLabel':info.get('industry') if industry else None}

def normalize_prices(row,meta,prices,now=None):
    now=now or dt.datetime.now(UTC)
    venue=str(row['listing_symbol']).split(':')[0]
    if (str(meta.get('symbol','')).upper()!=row['ticker'].upper() or meta.get('instrumentType')!='EQUITY'
        or currency(meta.get('currency'))!=currency(row['currency'])
        or meta.get('exchangeName') not in VENUES.get(venue,set())):
        raise ValueError('yahoo_ambiguous_listing')
    values={}
    for date,value in prices:
        day=dt.date.fromisoformat(date)
        if day>=now.date():continue
        if not isinstance(value,(int,float)) or not math.isfinite(value) or value<=0:
            raise ValueError('invalid_adjusted_prices')
        if date in values and values[date]!=value:raise ValueError('conflicting_prices')
        values[date]=value
    points=sorted(values.items())[-400:]
    if len(points)<200 or (dt.date.fromisoformat(points[-1][0])-dt.date.fromisoformat(points[0][0])).days<365:
        raise ValueError('insufficient_history')
    if (now.date()-dt.date.fromisoformat(points[-1][0])).days>7:raise ValueError('stale_history')
    if any((dt.date.fromisoformat(b[0])-dt.date.fromisoformat(a[0])).days>14 for a,b in zip(points,points[1:])):
        raise ValueError('history_gap')
    return {'schema':1,'format':'sector-series','symbol':row['listing_symbol'],'currency':row['currency'],
      'adjustment':'total_return','provider':'Yahoo Finance / yfinance · Adj Close',
      'retrievedAt':now.isoformat(),'points':points}

def collect_child(request):
    import yfinance as yf
    row=request['row'];ticker=yf.Ticker(row['ticker']);now=dt.datetime.now(UTC)
    result={'profile':profile(row,ticker.get_info(),request['original'],now)}
    if request['history']:
        try:
            frame=ticker.history(period='2y',auto_adjust=False,back_adjust=False,repair=False,actions=False,timeout=10,raise_errors=True)
            if 'Adj Close' not in frame:raise ValueError('adjusted_close_missing')
            result['series']=normalize_prices(row,ticker.get_history_metadata(),
                [(i.date().isoformat(),float(v)) for i,v in frame['Adj Close'].items()],now)
            result['series']['inputIdentity']=identity(request['original'])
        except Exception as exc: result['historyError']=safe_error(exc)
    return result

def safe_error(exc):
    allowed={'invalid_adjusted_prices','conflicting_prices','insufficient_history','stale_history','history_gap','adjusted_close_missing'}
    return str(exc) if isinstance(exc,ValueError) and str(exc) in allowed else error_code(exc)

def collect(request,timeout):
    p=subprocess.run([sys.executable,__file__,'--child'],input=json.dumps(request),text=True,
        capture_output=True,encoding='utf8',timeout=timeout,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    result=json.loads(p.stdout)
    if p.returncode:raise ValueError(result.get('error','yahoo_child_failure'))
    return result

def load(path,default):
    try:return json.loads(Path(path).read_text(encoding='utf8'))
    except (ValueError,OSError):return default
def save(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(json.dumps(value,ensure_ascii=False,allow_nan=False),encoding='utf8');tmp.replace(path)

def merge_recovered_series(universe,cache,recovered,now=None):
    """Import recent identity-checked recovery observations without refreshing dates."""
    now=now or dt.datetime.now(UTC)
    cache=cache if cache.get('schema')==1 else {'schema':1,'series':{}}
    cache.setdefault('series',{})
    if recovered.get('schema')!=1:return cache
    for row in universe.get('kandidaten',[]):
        s=row.get('listing_symbol');h=recovered.get('series',{}).get(s,{})
        if (not s or h.get('inputIdentity')!=identity(row) or h.get('symbol')!=s
            or h.get('currency')!=row.get('currency') or h.get('adjustment')!='total_return'
            or not recent(h.get('retrievedAt'),now,1.5)):continue
        old=cache['series'].get(s,{})
        try:
            if old.get('inputIdentity')==identity(row) and dt.datetime.fromisoformat(str(old.get('retrievedAt')).replace('Z','+00:00'))>=dt.datetime.fromisoformat(h['retrievedAt'].replace('Z','+00:00')):continue
        except (ValueError,TypeError):pass
        try:
            venue=s.split(':')[0]
            # Revalidate dates and price values; venue/issuer evidence was collected
            # independently and is tied to the exact original input fingerprint.
            normalize_prices(row,{'symbol':row['ticker'],'instrumentType':'EQUITY','currency':row['currency'],
                'exchangeName':next(iter(VENUES.get(venue,set())))},h['points'],now)
        except (ValueError,TypeError,KeyError,StopIteration):continue
        cache['series'][s]=h
    return cache

def run(universe,archive,cache,now=None,fetcher=collect,budget=1200,limit=400,checkpoint=None,calendar_retry=None,metadata_only=False):
    now=now or dt.datetime.now(UTC);started=time.monotonic()
    originals=universe.get('kandidaten',[])
    if not isinstance(originals,list) or not originals:raise ValueError('Universe missing or empty')
    rows=[apply_reference(dict(r),now.date()) for r in originals]
    prepare_universe(rows)
    archive=archive if archive.get('schema')==1 else {'schema':1,'profiles':{},'attempts':{}}
    archive.setdefault('profiles',{});archive.setdefault('attempts',{})
    cache=cache if cache.get('schema')==1 else {'schema':1,'series':{}}
    cache.setdefault('series',{})
    active={r.get('listing_symbol') for r in rows}
    for store in (archive['profiles'],archive['attempts'],cache['series']):
        for key in list(store):
            if key not in active:del store[key]
    requests=[];report=Counter();errors=Counter()
    for original,row in zip(originals,rows):
        s=row.get('listing_symbol');old=archive['profiles'].get(s,{});attempt=archive['attempts'].get(s,{})
        if not s or row.get('_newsIdentityBlocked') or not valid_isin(row.get('isin')) or not listing_matches(row.get('ticker'),s):
            report['identityBlocked']+=1;continue
        h=cache['series'].get(s,{})
        need_history=not (h.get('symbol')==s and recent(h.get('retrievedAt'),now,1.5) and h.get('points') and recent(h['points'][-1][0]+'T00:00:00+00:00',now,7)
                         and (h.get('inputIdentity') is None or h.get('inputIdentity')==identity(original)))
        if s in (calendar_retry or set()):need_history=True
        if metadata_only:need_history=False
        need_profile=not(old.get('inputIdentity')==identity(original) and recent(old.get('retrievedAt'),now,30) and old.get('industryKey'))
        if not need_history and not need_profile:report['freshSkipped']+=1;continue
        if attempt.get('inputIdentity')==identity(original) and recent(attempt.get('at'),now,1):report['cooldownSkipped']+=1;continue
        requests.append((attempt.get('at',''),not need_history,s,{'row':row,'original':original,'history':need_history}))
    # Oldest attempts first prevents repeated failures from starving new listings.
    requests.sort(key=lambda x:x[:3])
    for _,_,s,request in requests[:limit]:
        remaining=budget-(time.monotonic()-started)
        if remaining<2:break
        report['attempted']+=1
        attempt={'at':now.isoformat(),'inputIdentity':identity(request['original'])}
        try:
            data=fetcher(request,min(25,remaining))
            p=data['profile']
            if p.get('inputIdentity')!=identity(request['original']):raise ValueError('yahoo_ambiguous_listing')
            archive['profiles'][s]=p;report['profilesUpdated']+=1
            if data.get('series'):
                cache['series'][s]=data['series'];report['historiesUpdated']+=1
            if data.get('historyError'):attempt['error']=data['historyError'];errors[data['historyError']]+=1
        except Exception as exc:
            attempt['error']=safe_error(exc);errors[attempt['error']]+=1
        archive['attempts'][s]=attempt
        archive['generatedAt']=now.isoformat()
        archive['report']={**report,'pending':len(requests)-report['attempted'],'errors':dict(errors)}
        if checkpoint:checkpoint(archive,cache)
        if attempt.get('error')=='yahoo_rate_limited':report['rateLimitedStop']+=1;break
    archive['generatedAt']=now.isoformat();cache['generatedAt']=now.isoformat()
    archive['report']={**report,'pending':len(requests)-report['attempted'],'errors':dict(errors)}
    return archive,cache

def main():
    folder=Path(os.getenv('RISK_DATA_DIR',str(Path(__file__).resolve().parents[1]/'daten')))
    ap=folder/'cf_peer_metadata.json';cp=Path(os.getenv('RISK_SECTOR_STATE','.risk-sector-series.json'))
    budget=float(os.getenv('SECTOR_YAHOO_BUDGET_MIN','20'))*60
    if not 1<=budget<=1800:raise ValueError('Invalid budget')
    previous=load(folder/'cf_sector_context.json',{})
    retry={s for s,r in previous.get('stocks',{}).items() if r.get('reason')=='target_calendar_insufficient'} if recent(previous.get('generatedAt'),dt.datetime.now(UTC),1.5) else set()
    universe=load(folder/'cf_universum.json',{})
    cache=merge_recovered_series(universe,load(cp,{}),load(folder/'cf_sector_recovered_series.json',{}))
    archive,cache=run(universe,load(ap,{}),cache,budget=budget,
        checkpoint=lambda a,c:(save(ap,a),None if os.getenv('SECTOR_METADATA_ONLY')=='1' else save(cp,c)),calendar_retry=retry,
        metadata_only=os.getenv('SECTOR_METADATA_ONLY')=='1')
    save(ap,archive)
    if os.getenv('SECTOR_METADATA_ONLY')!='1':save(cp,cache)
    print(json.dumps(archive['report']))

if __name__=='__main__':
    if '--child' in sys.argv:
        try:print(json.dumps(collect_child(json.loads(sys.stdin.read())),allow_nan=False))
        except Exception as exc:print(json.dumps({'error':safe_error(exc)}));sys.exit(1)
    else:main()


