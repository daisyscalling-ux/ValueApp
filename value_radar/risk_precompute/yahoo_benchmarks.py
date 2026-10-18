"""Shared reviewed market ETF histories; raw data only in the runner temp directory."""
import contextlib
import datetime as dt
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time

REGISTRY = json.loads(Path(__file__).with_name('market-proxies.json').read_text(encoding='utf8'))
PROXIES = {r['proxy']: r['country'] for r in REGISTRY}
EXCHANGES = {'PCX','NYQ','NMS','NGM','NCM','ASE','BATS','BTS'}

def normalize(symbol, metadata, prices, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    if symbol not in PROXIES or metadata.get('symbol') != symbol or metadata.get('instrumentType') != 'ETF' or metadata.get('currency') != 'USD' or metadata.get('exchangeName') not in EXCHANGES:
        raise ValueError('ETF identity, US venue or USD currency not confirmed')
    bars = []
    seen = set()
    for date, price in prices:
        stamp = dt.date.fromisoformat(date)
        if stamp >= now.date():
            continue
        if date in seen or not math.isfinite(price) or price <= 0:
            raise ValueError('Invalid adjusted close')
        seen.add(date)
        bars.append({'date':date,'close':price})
    bars.sort(key=lambda b:b['date'])
    if len(bars) < 200 or (now.date()-dt.date.fromisoformat(bars[-1]['date'])).days > 7:
        raise ValueError('Missing or stale market history')
    return {'symbol':'YAHOO:'+symbol,'proxy':symbol,'region':PROXIES[symbol],
            'provider':'Yahoo Finance / yfinance','exchange':metadata['exchangeName'],
            'instrumentType':'ETF','currency':'USD','adjustment':'total_return',
            'bars':bars,'retrievedAt':now.isoformat(),'requestedFrom':bars[0]['date'],
            'note':'Yahoo Finance / yfinance · Adjusted Close (Dividenden/Splits). US-gehandelter Markt-/Länder-ETF in USD; ausländische Märkte einschließlich Wechselkurseinfluss. Kein reiner lokaler Index.'}

def fetch_one(symbol):
    import yfinance as yf
    now = dt.datetime.now(dt.timezone.utc)
    start = (now-dt.timedelta(days=5*365)).date().isoformat()
    ticker = yf.Ticker(symbol)
    with contextlib.redirect_stdout(sys.stderr):
        frame = ticker.history(start=start,end=now.date().isoformat(),interval='1d',auto_adjust=False,back_adjust=False,repair=False,actions=True,timeout=10,raise_errors=True)
        metadata = ticker.get_history_metadata()
    if 'Adj Close' not in frame.columns:
        raise ValueError('Adjusted Close missing; raw close is not an alternative')
    return normalize(symbol,metadata,[(i.date().isoformat(),float(v)) for i,v in frame['Adj Close'].items()],now)

def main():
    output = Path(os.getenv('RISK_YAHOO_PATH','/tmp/risk-yahoo.json'))
    output.parent.mkdir(parents=True,exist_ok=True)
    result = {'benchmarks':{},'errors':[]}
    deadline = time.monotonic()+900
    def save():
        temporary = output.with_suffix('.tmp')
        temporary.write_text(json.dumps(result,allow_nan=False),encoding='utf-8')
        temporary.replace(output)
    save()
    try:
        old = json.loads(Path(os.getenv('RISK_OUTPUT_PATH','value_radar/daten/cf_risk.json')).read_text(encoding='utf8')).get('benchmarks',{})
    except (OSError,ValueError):
        old = {}
    # Missing and oldest observations first; do not starve additions after a timeout.
    symbols = sorted(PROXIES,key=lambda s:old.get(s,{}).get('retrievedAt',''))
    for symbol in symbols:
        if time.monotonic() > deadline:
            result['errors'].append({'symbol':symbol,'reason':'Time budget exhausted'})
            break
        ok = False
        for attempt in range(2):
            if time.monotonic() > deadline:
                break
            try:
                run = subprocess.run([sys.executable,__file__,'--one',symbol],capture_output=True,text=True,timeout=max(1,min(40,deadline-time.monotonic())),check=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                result['benchmarks'][symbol] = json.loads(run.stdout)
                ok = True
                break
            except (subprocess.SubprocessError,ValueError):
                if attempt == 0:
                    time.sleep(5)
        if not ok:
            result['errors'].append({'symbol':symbol,'reason':'Yahoo history unavailable, invalid or time limit'})
        save()
    save()
    print('Yahoo market ETFs: '+str(len(result['benchmarks']))+'/'+str(len(PROXIES))+' available')
    if len(result['benchmarks']) < len(PROXIES):
        print('::warning::Some Yahoo market histories remain unavailable; missing values are not scored.')

if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--one':
        print(json.dumps(fetch_one(sys.argv[2]),allow_nan=False))
    else:
        main()
