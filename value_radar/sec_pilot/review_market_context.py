"""Align public market context to the study calendar without forward fills."""
import argparse
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import zipfile
from free_sources import write_csv
from collect_market_context import SERIES

def normalize_market(rows,sessions,kind):
    previous_day=dict(zip(sessions[1:],sessions));calendar=set(sessions)
    normalized=[];outside=[];invalid=[];seen=set();previous=None
    for r in sorted(rows,key=lambda r:r['Date']):
        day=r['Date'][:10]
        if day in seen:raise ValueError('Duplicate market date')
        seen.add(day)
        if day not in calendar:outside.append(day);continue
        try:
            column='Adj Close' if kind=='adjusted_price_proxy' else 'Close'
            level=float(r[column])
            if not math.isfinite(level) or level<0 or (kind!='ten_year_yield_indicator_percent' and level==0):
                raise ValueError('Invalid level')
            if kind=='adjusted_price_proxy':
                volume=float(r['Volume'])
                if not math.isfinite(volume) or volume<=0:raise ValueError('Nontrading row')
        except (ValueError,KeyError,TypeError):invalid.append(day);previous=None;continue
        value=''
        if kind=='adjusted_price_proxy' and previous and previous[0]==previous_day.get(day):
            value=str(level/previous[1]-1)
        normalized.append(dict(date=day,level=str(level),daily_return=value,interpretation=kind))
        previous=(day,level)
    present={r['date'] for r in normalized}
    return normalized,dict(outside_reference_sessions=outside,invalid_observations=invalid,
                           missing_reference_sessions=[d for d in sessions if d not in present])

def run(folder,archive_path,output):
    folder=Path(folder);output=Path(output);output.mkdir(parents=True,exist_ok=True)
    manifest=json.loads((folder/'manifest.json').read_text())
    with zipfile.ZipFile(archive_path) as z:
        sessions=[r['date'] for r in csv.DictReader(io.StringIO(z.read('session-review/handelskalender.csv').decode('utf-8-sig')))]
    reports=[]
    for entry in manifest['series']:
        symbol=entry['symbol'];stem=symbol.replace('^','INDEX_')
        if entry['status']!='captured_not_verified':
            reports.append(dict(symbol=symbol,status='unavailable'));continue
        data=(folder/(stem+'.csv')).read_bytes()
        if hashlib.sha256(data).hexdigest()!=entry['data_sha256']:raise ValueError('Raw data hash mismatch')
        if symbol not in SERIES or entry['interpretation']!=SERIES[symbol][1]:raise ValueError('Unknown series')
        requested=[d for d in sessions if entry['start']<=d<entry['end_exclusive']]
        rows,checks=normalize_market(list(csv.DictReader(io.StringIO(data.decode()))),requested,entry['interpretation'])
        write_csv(output/(stem+'.csv'),rows,['date','level','daily_return','interpretation'])
        reports.append(dict(symbol=symbol,status='aligned_research_only',rows=len(rows),
            first=rows[0]['date'] if rows else None,last=rows[-1]['date'] if rows else None,
            requested_start=entry['start'],requested_end_exclusive=entry['end_exclusive'],
            raw_sha256=entry['data_sha256'],**checks,production_eligible=False))
    report=dict(series=reports,production_eligible=False,forward_fill=False,
                reference_calendar_sha256=hashlib.sha256('\n'.join(sessions).encode()).hexdigest())
    (output/'market_review.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('folder');p.add_argument('archive');p.add_argument('output')
    a=p.parse_args();r=run(a.folder,a.archive,a.output)
    for s in r['series']:print(s['symbol'],s['status'],s.get('rows'),len(s.get('missing_reference_sessions',[])))
