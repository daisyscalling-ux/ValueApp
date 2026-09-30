"""Bounded by the parent process. Yahoo supplements never replace ROIC prices.

Uses ValueApp providers.py's targetMeanPrice/targetMedianPrice approach, with
listing identity checks and period-matched cashflow reconciliation in the TS adapter.
"""
import json
import math
import re
import sys
import urllib.request
import csv
import io
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone


def number(value):
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) else None


def yahoo_symbol(stock):
    exchange, _, code = stock['symbol'].partition(':')
    suffix = {'NASDAQ': '', 'NYSE': '', 'AMEX': '', 'XETR': '.DE', 'FWB': '.F', 'HKEX': '.HK', 'NSE': '.NS', 'BSE': '.BO'}
    if exchange not in suffix or not re.fullmatch(r'[A-Z0-9.-]{1,20}', code):
        raise ValueError('Keine bestaetigte Yahoo-Symbolzuordnung fuer diese Boerse.')
    if exchange == 'HKEX' and code.isdigit():
        code = code.zfill(4)
    return code.replace('.', '-') + suffix[exchange] if not suffix[exchange] else code + suffix[exchange]


def normalize(stock, info, isin, symbol, now=None):
    exchanges = {'NASDAQ': {'NMS', 'NGM', 'NCM'}, 'NYSE': {'NYQ'}, 'AMEX': {'ASE'}, 'XETR': {'GER'}, 'FWB': {'FRA'}, 'HKEX': {'HKG'}, 'NSE': {'NSI'}, 'BSE': {'BSE'}}
    if not stock.get('isPrimary') or stock.get('securityType') != 'stock' or info.get('quoteType') != 'EQUITY':
        raise ValueError('Yahoo: Aktiengattung nicht bestaetigt.')
    if info.get('symbol') != symbol or info.get('currency') != stock.get('currency') or info.get('exchange') not in exchanges.get(stock['exchange'], set()):
        raise ValueError('Yahoo: Notierung, Boerse oder Handelswaehrung weichen ab.')
    # Require the same security identifier; never map a German secondary listing to a US ADR.
    if not stock.get('isin') or isin != stock['isin']:
        raise ValueError('Yahoo: ISIN konnte nicht mit ROIC bestaetigt werden.')
    values = {key: number(info.get(field)) for key, field in [('mean', 'targetMeanPrice'), ('median', 'targetMedianPrice'), ('low', 'targetLowPrice'), ('high', 'targetHighPrice')]}
    values = {k: v if v is not None and v > 0 else None for k, v in values.items()}
    low, high = values['low'], values['high']
    if low is not None and high is not None and low > high:
        raise ValueError('Yahoo: widerspruechliche Zielspanne.')
    if any(v is not None and ((low is not None and v < low) or (high is not None and v > high)) for v in [values['mean'], values['median']]):
        raise ValueError('Yahoo: Ziel liegt ausserhalb der gemeldeten Spanne.')
    if values['mean'] is None:
        return None
    return dict(provider='Yahoo Finance', symbol=symbol, currency=stock['currency'], **values,
                updatedAt=None, retrievedAt=now or datetime.now(timezone.utc).isoformat(),
                sourceUrl='https://finance.yahoo.com/quote/'+symbol+'/analysis/')


def yahoo_run(stock):
    import yfinance as yf
    symbol = yahoo_symbol(stock)
    ticker = yf.Ticker(symbol)
    info = ticker.get_info()
    isin = ticker.get_isin()
    if not isin or isin == '-':
        # Yahoo's ticker ISIN is often absent. Resolve the known ROIC ISIN through
        # Yahoo Search, requiring the exact mapped listing and security type.
        matches = yf.Search(stock.get('isin', ''), max_results=10, news_count=0).quotes if stock.get('isin') else []
        if any(q.get('symbol') == symbol and q.get('quoteType') == 'EQUITY' and q.get('exchange') == info.get('exchange') for q in matches):
            isin = stock['isin']
    target = normalize(stock, info, isin, symbol)
    output = {'analystTarget': target}
    context=context_base(stock)
    beta=number(info.get('beta'))
    if beta is not None and 0<beta<=5:
        context['beta']=dict(value=beta,date=context['retrievedAt'][:10],source='Yahoo Finance · Anbieter-Beta',url='https://finance.yahoo.com/quote/'+symbol+'/key-statistics/',note='Abrufdatum; Berechnungsfenster und Beobachtungsstichtag vom Anbieter nicht separat ausgewiesen. Historische Näherung.')
    output['marketInputs']=context
    latest = stock.get('financials', [{}])[0]
    if latest.get('fcf') is None and info.get('financialCurrency') == latest.get('currency'):
        frame = ticker.ttm_cashflow if latest.get('periodType') == 'ttm' else ticker.cashflow
        for date in frame.columns:
            if date.strftime('%Y-%m-%d') != latest.get('date'):
                continue
            def cell(label):
                return number(frame.at[label, date]) if label in frame.index else None
            output['cashflow'] = dict(date=latest['date'], reportedCurrency=latest['currency'],
                                      operatingCashFlow=cell('Operating Cash Flow'),
                                      capitalExpenditure=cell('Capital Expenditure'), freeCashFlow=cell('Free Cash Flow'))
            break
    if latest.get('preferredEquity') is None and info.get('financialCurrency')==latest.get('currency'):
        try:
            for frame in (ticker.quarterly_balance_sheet,ticker.balance_sheet):
                for date in frame.columns:
                    if date.strftime('%Y-%m-%d')!=latest.get('date'): continue
                    def balance(label): return number(frame.at[label,date]) if label in frame.index else None
                    direct=balance('Preferred Stock Equity')
                    parent,common=balance('Stockholders Equity'),balance('Common Stock Equity')
                    reconciled=parent-common if parent is not None and common is not None and parent>=common else None
                    value=direct if direct is not None else reconciled
                    if value is not None and value>=0 and (direct is None or reconciled is None or abs(direct-reconciled)<1):
                        context['preferredEquity']=dict(value=value,date=latest['date'],source='Yahoo Finance · Bilanz',url='https://finance.yahoo.com/quote/'+symbol+'/balance-sheet/',note='Explizites Vorzugskapital oder Gesamteigenkapital der Anteilseigner minus Stammaktionärseigenkapital, gleicher Stichtag. Buchwert-Näherung.')
        except Exception: pass
    return output


def context_base(stock):
    return dict(id=stock['id'],currency=stock['currency'],financialDate=stock['financials'][0]['date'],retrievedAt=datetime.now(timezone.utc).isoformat(),warnings=[])

def download(url):
    req=urllib.request.Request(url,headers={'User-Agent':'QuantumEquityResearch/1.0'})
    with urllib.request.urlopen(req,timeout=10) as response:
        return response.read(2000000).decode('utf-8')

def market_inputs(stock):
    context=context_base(stock)
    def rate():
        if stock['currency']=='USD':
            from datetime import timedelta
            start=(datetime.now(timezone.utc)-timedelta(days=20)).date().isoformat()
            rows=list(csv.DictReader(io.StringIO(download('https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10&cosd='+start))))
            valid=[r for r in rows if r.get('DGS10','').replace('.','',1).isdigit()]
            if valid:
                r=valid[-1];return dict(value=float(r['DGS10']),date=r.get('observation_date') or r.get('DATE'),source='FRED / US Treasury · DGS10',url='https://fred.stlouisfed.org/series/DGS10')
        elif stock['currency']=='EUR':
            url='https://data-api.ecb.europa.eu/service/data/YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y?lastNObservations=1&format=csvdata'
            rows=list(csv.DictReader(io.StringIO(download(url))))
            if rows:return dict(value=100*math.expm1(float(rows[-1]['OBS_VALUE'])/100),date=rows[-1]['TIME_PERIOD'],source='EZB · AAA-Euro-Zins, effektiv',url='https://data.ecb.europa.eu/data/datasets/YC/YC.B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y')
    def erp():
        html=download('https://pages.stern.nyu.edu/adamodar/New_Home_Page/home.htm')
        plain=re.sub(r'\s+',' ',re.sub('<[^>]*>',' ',html).replace('&nbsp;',' '))
        m=re.search(r'Implied ERP on\s+([A-Za-z]+\s+\d{1,2},\s+\d{4})\s*=\s*([\d.\s]+)%\s*\(Trailing 12 month, with adjusted payout\)',plain)
        if not m:return
        value=float(re.sub(r'\s','',m[2]))
        if stock['currency']=='EUR':
            spread=re.search(r'default spread\s*\(([\d.\s]+)%\)',plain)
            if not spread:return
            value+=float(re.sub(r'\s','',spread[1]))
        elif stock['currency']!='USD':return
        return dict(value=value,date=datetime.strptime(m[1],'%B %d, %Y').date().isoformat(),source='Damodaran · implizite Risikoprämie',url='https://pages.stern.nyu.edu/adamodar/New_Home_Page/home.htm',note='Monatliche Schätzung; für EUR um US-Ausfallspread ergänzt, Näherung für reife Märkte.')
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs={key:pool.submit(fn) for key,fn in [('riskFree',rate),('erp',erp)]}
        for key,job in jobs.items():
            try:
                value=job.result()
                if value:context[key]=value
            except Exception:pass
    return context

def run(stock):
    # Independent partial success: Yahoo failure must not discard macro observations.
    with ThreadPoolExecutor(max_workers=2) as pool:
        macro=pool.submit(market_inputs,stock)
        try:output=yahoo_run(stock)
        except Exception:output={}
        try:context=macro.result()
        except Exception:context=context_base(stock)
        context.update(output.get('marketInputs',{}))
        output['marketInputs']=context
        return output

if __name__ == '__main__':
    try:
        print(json.dumps(run(json.load(sys.stdin)), allow_nan=False))
    except Exception as error:
        # Provider responses can contain cookies; only our validation messages may cross the boundary.
        message = str(error) if isinstance(error, ValueError) and str(error).startswith(('Yahoo:', 'Keine bestaetigte')) else 'Yahoo-Daten momentan nicht abrufbar; bisherige Daten bleiben erhalten.'
        print(json.dumps({'error': message}))
