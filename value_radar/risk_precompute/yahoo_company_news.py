"""Isolated, time-bounded Yahoo news fallback with exact issuer checks."""
import datetime as dt
import json
import re
import subprocess
import sys
import unicodedata

def name_key(value):
    value=unicodedata.normalize('NFKD',str(value or '')).casefold()
    return ''.join(c for c in value if c.isalnum())

def currency(value):
    return 'GBP' if value in ['GBp','GBX'] else value

def verify_profile(row,info):
    expected=name_key(row.get('name_full') or row.get('name'))
    names={name_key(info.get('longName')),name_key(info.get('shortName'))}-{''}
    if not expected or expected not in names:raise ValueError('yahoo_issuer_name_mismatch')
    if not row.get('currency') or currency(info.get('currency'))!=currency(row['currency']):raise ValueError('yahoo_currency_mismatch')
    if info.get('quoteType')!='EQUITY':raise ValueError('yahoo_security_type_mismatch')
    symbol=str(row.get('ticker') or '')
    if not symbol or str(info.get('symbol') or '').upper()!=symbol.upper():raise ValueError('yahoo_symbol_mismatch')
    return {'symbol':symbol,'name':info.get('longName') or info.get('shortName'),'currency':info.get('currency'),'quoteType':'EQUITY'}

def convert_news(items):
    if not isinstance(items,list):raise ValueError('yahoo_news_schema')
    rows=[]
    for item in items:
        c=item.get('content',{}) if isinstance(item,dict) else {}
        if not isinstance(c,dict):continue
        url=c.get('canonicalUrl') or c.get('clickThroughUrl') or {}
        provider=c.get('provider') or {}
        if not isinstance(url,dict) or not isinstance(provider,dict):continue
        rows.append({'title':c.get('title'),'article_url':url.get('url'),'published_date':c.get('pubDate'),'site':provider.get('displayName')})
    return rows

def collect_child(row):
    import yfinance as yf
    symbol=str(row.get('ticker') or '')
    if not re.fullmatch(r'[A-Za-z0-9.^=_-]{1,40}',symbol):raise ValueError('unsupported_yahoo_symbol')
    ticker=yf.Ticker(symbol)
    evidence=verify_profile(row,ticker.get_info())
    news=convert_news(ticker.get_news(count=30,tab='news'))
    return {'evidence':evidence,'rows':news}

def collect(row,timeout=18):
    # yfinance may hang beyond its own timeouts. Kill the isolated child on expiry.
    result=subprocess.run([sys.executable,__file__,'--child'],input=json.dumps(row),text=True,
                          capture_output=True,timeout=timeout,encoding='utf8')
    if result.returncode:raise ValueError('yahoo_unavailable_or_identity_rejected')
    data=json.loads(result.stdout)
    if not isinstance(data,dict) or not isinstance(data.get('rows'),list):raise ValueError('yahoo_news_schema')
    return data

if __name__=='__main__':
    try:
        row=json.loads(sys.stdin.read())
        print(json.dumps(collect_child(row),ensure_ascii=True))
    except Exception:
        # Do not copy provider output, URLs or credentials into the public archive.
        sys.exit(1)
