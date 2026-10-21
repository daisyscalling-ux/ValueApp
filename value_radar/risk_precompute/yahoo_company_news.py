"""Isolated, time-bounded Yahoo news fallback with exact issuer checks."""
import datetime as dt
import json
import hashlib
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

ERROR_CODES={'yahoo_issuer_name_mismatch','yahoo_currency_mismatch',
 'yahoo_security_type_mismatch','yahoo_symbol_mismatch','unsupported_yahoo_symbol',
 'yahoo_news_schema','yahoo_timeout','yahoo_dependency_missing','yahoo_rate_limited',
 'yahoo_provider_failure','yahoo_child_failure'}

def error_code(exc):
    # Only fixed codes may leave the isolated process, never provider messages.
    if isinstance(exc,subprocess.TimeoutExpired):return 'yahoo_timeout'
    if isinstance(exc,ImportError):return 'yahoo_dependency_missing'
    if type(exc).__name__=='YFRateLimitError':return 'yahoo_rate_limited'
    if isinstance(exc,ValueError) and str(exc) in ERROR_CODES:return str(exc)
    return 'yahoo_provider_failure'

def name_key(value):
    value=unicodedata.normalize('NFKD',str(value or '')).casefold()
    return ''.join(c for c in value if c.isalnum())

def currency(value):
    return 'GBP' if value in ['GBp','GBX'] else value

def alias_entries():
    return json.loads(Path(__file__).with_name('yahoo-news-name-aliases.json').read_text(encoding='utf-8-sig'))

def alias_revision(row):
    entries=[a for a in alias_entries() if a['symbol']==row.get('listing_symbol') and a['isin']==row.get('isin') and name_key(a['expected'])==name_key(row.get('name_full') or row.get('name'))]
    return hashlib.sha256(json.dumps(entries,sort_keys=True).encode()).hexdigest() if entries else None

def corrected_alias_retry(row,old):
    revision=alias_revision(row)
    return bool(revision and old.get('fallbackError') in ['ValueError','yahoo_issuer_name_mismatch'] and old.get('fallbackAliasRevision')!=revision)

def verify_profile(row,info):
    expected=name_key(row.get('name_full') or row.get('name'))
    names={name_key(info.get('longName')),name_key(info.get('shortName'))}-{''}
    alias=False
    if expected and expected not in names:
        # Explicit observed provider-name pairs, bound to listing and ROIC ISIN.
        # No general suffix stripping or fuzzy matching of unrelated companies.
        aliases=alias_entries()
        alias=any(a['symbol']==row.get('listing_symbol') and a['isin']==row.get('isin')
                  and name_key(a['expected'])==expected and name_key(a['yahooLong']) in names for a in aliases)
    if not expected or (expected not in names and not alias):raise ValueError('yahoo_issuer_name_mismatch')
    if not row.get('currency') or currency(info.get('currency'))!=currency(row['currency']):raise ValueError('yahoo_currency_mismatch')
    if info.get('quoteType')!='EQUITY':raise ValueError('yahoo_security_type_mismatch')
    symbol=str(row.get('ticker') or '')
    if not symbol or str(info.get('symbol') or '').upper()!=symbol.upper():raise ValueError('yahoo_symbol_mismatch')
    return {'symbol':symbol,'name':info.get('longName') or info.get('shortName'),'currency':info.get('currency'),'quoteType':'EQUITY','nameMatch':'reviewed_provider_alias' if alias else 'exact'}

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
    try:data=json.loads(result.stdout)
    except (ValueError,TypeError):raise ValueError('yahoo_child_failure') from None
    if result.returncode:
        code=data.get('error') if isinstance(data,dict) else None
        raise ValueError(code if code in ERROR_CODES else 'yahoo_child_failure')
    if not isinstance(data,dict) or not isinstance(data.get('rows'),list):raise ValueError('yahoo_news_schema')
    return data

if __name__=='__main__':
    try:
        row=json.loads(sys.stdin.read())
        print(json.dumps(collect_child(row),ensure_ascii=True))
    except Exception as exc:
        # Do not copy provider output, URLs or credentials into the public archive.
        print(json.dumps({'error':error_code(exc)}))
        sys.exit(1)

