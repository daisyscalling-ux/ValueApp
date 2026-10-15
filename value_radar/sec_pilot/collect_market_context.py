"""Bounded, resumable public market-context archive. No score calibration."""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import subprocess
import sys

SERIES = {s: ('ETF','adjusted_price_proxy') for s in
          ['SPY','QQQ','IWM','XLK','XLF','XLV','XLE','XLI','XLP','XLY','XLU','XLB','XLRE','XLC']}
SERIES.update({'^VIX':('INDEX','volatility_index_level'),'^TNX':('INDEX','ten_year_yield_indicator_percent')})

def one(symbol, start, end, output):
    import yfinance as yf
    folder=Path(output);folder.mkdir(parents=True,exist_ok=True)
    stem=symbol.replace('^','INDEX_')
    result=dict(symbol=symbol,start=start,end_exclusive=end,
                retrieved_at=dt.datetime.now(dt.timezone.utc).isoformat(),
                source='Yahoo Finance via yfinance',interpretation=SERIES[symbol][1],
                production_eligible=False)
    try:
        ticker=yf.Ticker(symbol)
        frame=ticker.history(start=start,end=end,auto_adjust=False,repair=False,
                             actions=True,timeout=12,raise_errors=True)
        metadata=ticker.history_metadata
        if frame.empty:raise ValueError('empty_history')
        if metadata.get('symbol')!=symbol or metadata.get('instrumentType')!=SERIES[symbol][0]:
            raise ValueError('identity_or_instrument_mismatch')
        if SERIES[symbol][0]=='ETF' and metadata.get('currency')!='USD':
            raise ValueError('currency_mismatch')
        if SERIES[symbol][0]=='ETF' and 'Adj Close' not in frame:raise ValueError('adjustment_missing')
        dates=[d.date().isoformat() for d in frame.index]
        if dates!=sorted(set(dates)) or any(not start<=d<end for d in dates):
            raise ValueError('invalid_date_range_or_duplicates')
        frame.to_csv(folder/(stem+'.csv'))
        result.update(status='captured_not_verified',rows=len(frame),first=dates[0],last=dates[-1],
                      data_sha256=hashlib.sha256((folder/(stem+'.csv')).read_bytes()).hexdigest(),
                      metadata={k:metadata.get(k) for k in ('symbol','currency','instrumentType','exchangeName','longName')})
    except Exception as exc:
        result.update(status='unavailable',error_type=type(exc).__name__)
    (folder/(stem+'.json')).write_text(json.dumps(result,indent=2),encoding='utf8')
    return result

def collect(start,end,output):
    if dt.date.fromisoformat(start)>=dt.date.fromisoformat(end):raise ValueError('Invalid range')
    folder=Path(output);folder.mkdir(parents=True,exist_ok=True)
    records=[]
    for symbol in SERIES:
        path=folder/(symbol.replace('^','INDEX_')+'.json')
        previous=json.loads(path.read_text()) if path.exists() else {}
        data=path.with_suffix('.csv')
        cached=(previous.get('status')=='captured_not_verified' and previous.get('start')==start
                and previous.get('end_exclusive')==end and data.exists()
                and hashlib.sha256(data.read_bytes()).hexdigest()==previous.get('data_sha256'))
        if not cached:
            try:
                subprocess.run([sys.executable,__file__,'--one',symbol,'--start',start,'--end',end,
                                '--output',str(folder)],timeout=45,check=True,capture_output=True)
            except (subprocess.TimeoutExpired,subprocess.CalledProcessError) as exc:
                previous=dict(symbol=symbol,start=start,end_exclusive=end,status='unavailable',
                              error_type=type(exc).__name__,production_eligible=False)
                path.write_text(json.dumps(previous,indent=2),encoding='utf8')
        current=json.loads(path.read_text());records.append(current)
        print(symbol,current['status'],current.get('rows',0),flush=True)
        (folder/'manifest.json').write_text(json.dumps(dict(series=records,
            complete=len(records)==len(SERIES),production_eligible=False,
            limitations=['Sector ETFs are investable proxies, not historical sector membership.',
                         'VIX and TNX are indicator levels, not total-return investments.',
                         'Missing observations and short fund histories remain missing.',
                         'Provider adjustments have not been independently verified.']),indent=2),encoding='utf8')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--one',choices=list(SERIES));p.add_argument('--start',required=True)
    p.add_argument('--end',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    if a.one:one(a.one,a.start,a.end,a.output)
    else:collect(a.start,a.end,a.output)
