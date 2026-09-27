"""Bounded by the parent process. Yahoo supplements never replace ROIC prices.

Uses ValueApp providers.py's targetMeanPrice/targetMedianPrice approach, with
listing identity checks and period-matched cashflow reconciliation in the TS adapter.
"""
import json
import math
import re
import sys
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


def run(stock):
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
    return output


if __name__ == '__main__':
    try:
        print(json.dumps(run(json.load(sys.stdin)), allow_nan=False))
    except Exception as error:
        # Provider responses can contain cookies; only our validation messages may cross the boundary.
        message = str(error) if isinstance(error, ValueError) and str(error).startswith(('Yahoo:', 'Keine bestaetigte')) else 'Yahoo-Daten momentan nicht abrufbar; bisherige Daten bleiben erhalten.'
        print(json.dumps({'error': message}))
