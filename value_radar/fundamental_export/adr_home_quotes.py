"""Heimatnotierung fuer Depositary Receipts, deren Stammaktie nicht im Universum steht.

adr_basis.py braucht fuer ein Umtauschverhaeltnis Kurs und Aktienzahl der Heimatnotierung. Fehlt sie im
Universum (z. B. ASML Amsterdam, Sanofi Paris, HDFC Bank Mumbai), sucht dieses Programm ueber die
ROIC-Ticker-Suche genau eine Hauptnotierung mit exakt derselben ISIN (keine OTC-Linie, Aktie, nicht delistet),
uebersetzt sie in ein Yahoo-Symbol und laedt dort nur Kurs, Aktienzahl, Waehrung und Namen. Der Name muss zum
Emittenten passen. Ob daraus ein Verhaeltnis wird, entscheidet weiter adr_basis.py mit derselben doppelten
Pruefung (Aktienzahl 2 %, Kurs 10 %, nur Standardverhaeltnisse).

Ausgabe: daten/fundamentals/adr_homes.json (Aufloesung 30 Tage gueltig, Kurs bei jedem Lauf neu).
"""
import datetime as dt
import json
import math
import os
import pathlib
import re
import sys
import time
import urllib.parse
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'risk_precompute'))
from news_identity import valid_isin, canonical_names  # noqa: E402

METHOD = 'roic_isin_primary_yahoo_quote_v1'
RESOLVE_DAYS = 30
SUFFIX = {'XETR': '.DE', 'LSE': '.L', 'TSE': '.T', 'HKEX': '.HK', 'SIX': '.SW', 'STO': '.ST', 'CPH': '.CO', 'HEL': '.HE', 'OSL': '.OL',
          'MIL': '.MI', 'BME': '.MC', 'VIE': '.VI', 'ATHEX': '.AT', 'GPW': '.WA', 'ASX': '.AX', 'SGX': '.SI', 'TWSE': '.TW', 'TPEX': '.TWO',
          'KRX': '.KS', 'KOSDAQ': '.KQ', 'NSE': '.NS', 'BSE': '.BO', 'SSE': '.SS', 'SZSE': '.SZ', 'B3': '.SA', 'JSE': '.JO', 'TSX': '.TO'}
EURONEXT = {'NL': '.AS', 'FR': '.PA', 'BE': '.BR', 'PT': '.LS', 'IE': '.IR'}


def finite(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) and x > 0


def yahoo_home_symbol(symbol, country=None):
    """ROIC-Notierung -> Yahoo-Symbol; None, wenn die Schreibweise nicht eindeutig ist."""
    if not isinstance(symbol, str) or ':' not in symbol:
        return None
    ex, t = symbol.split(':', 1)
    if not re.fullmatch(r'[A-Z0-9._-]+', t):
        return None
    if ex == 'EURONEXT':
        suffix = EURONEXT.get(str(country or '').upper())
        return t + suffix if suffix else None
    if ex not in SUFFIX:
        return None
    if ex == 'LSE':
        t = t.rstrip('.')
    if ex in ('STO', 'CPH', 'HEL'):
        t = re.sub(r'[_ ]([A-Z])$', r'-\1', t)
    if ex == 'HKEX':
        if not t.isdigit():
            return None
        t = t.lstrip('0').zfill(4)
    return t + SUFFIX[ex]


def choose_home(isin, candidates):
    """Genau eine Hauptnotierung mit derselben ISIN (keine OTC-Linie, Aktie, nicht delistet)."""
    ok = {c['symbol']: c for c in candidates if isinstance(c, dict) and c.get('isin') == isin and isinstance(c.get('symbol'), str)
          and not c['symbol'].upper().startswith('OTC:') and c.get('type') == 'stock' and c.get('status') != 'delisted' and c.get('is_primary') is True}
    return next(iter(ok.values())) if len(ok) == 1 else None


def targets(universe, folder):
    """DR-Zeilen mit Waehrungskonflikt, ohne Heimatnotierung derselben ISIN im Universum."""
    rows = universe.get('kandidaten', [])
    homes = {r.get('isin') for r in rows if r.get('security_type') == 'stock' and r.get('listing_symbol') and not r['listing_symbol'].startswith('OTC:')}
    out = {}
    for r in rows:
        s, isin = r.get('listing_symbol'), r.get('isin')
        if r.get('security_type') != 'dr' or not s or not valid_isin(isin) or isin in homes or isin.startswith('US'):
            continue
        path = folder / (re.sub('[^A-Za-z0-9._-]', '_', s) + '.json')
        try:
            d = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            continue
        annual, market = d.get('annual') or {}, d.get('market') or {}
        if annual.get('currency') and market.get('currency') and annual['currency'] != market['currency']:
            out.setdefault(isin, {'isin': isin, 'name': r.get('name_full') or r.get('name'), 'drs': []})['drs'].append(s)
    return list(out.values())


LEGAL = r'\b(plc|p l c|sa|s a|nv|n v|se|ag|asa|ab|oyj|spa|s p a|inc|ltd|limited|corp|corporation|co|company|holdings?|group|class [a-z])\b'


def compact(name):
    return re.sub(r'[^a-z0-9]', '', re.sub(LEGAL, ' ', str(name or '').lower().replace('&', ' and ')))


def name_matches(issuer, quoted):
    """Gemeinsamer kanonischer Name; bei sehr kurzen Namen (z. B. GSK) exakte Gleichheit ohne Rechtsform."""
    a, b = canonical_names(issuer), canonical_names(quoted)
    if a and b:
        return bool(a & b)
    return bool(compact(issuer)) and compact(issuer) == compact(quoted)


def run(universe, folder, state, search, quote, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    state = state if state.get('method') == METHOD else {'schema': 1, 'method': METHOD, 'homes': {}}
    report = {'targets': 0, 'resolved': 0, 'unresolved': {}, 'quoted': 0, 'quoteFailed': {}}
    wanted = set()
    for t in targets(universe, folder):
        report['targets'] += 1
        isin = t['isin']
        wanted.add(isin)
        old = state['homes'].get(isin) or {}
        try:
            fresh = dt.timedelta(0) <= now - dt.datetime.fromisoformat(old['resolvedAt']) < dt.timedelta(days=RESOLVE_DAYS)
        except (KeyError, ValueError, TypeError):
            fresh = False
        if not fresh:
            try:
                home = choose_home(isin, search(isin))
            except Exception:
                report['unresolved']['search_failed'] = report['unresolved'].get('search_failed', 0) + 1
                continue
            ysym = yahoo_home_symbol(home['symbol'], home.get('listing_country_code')) if home else None
            old = {'isin': isin, 'resolvedAt': now.isoformat(), 'roicSymbol': home['symbol'] if home else None, 'yahooSymbol': ysym,
                   'reason': '' if ysym else ('no_unique_primary_listing' if not home else 'yahoo_mapping_unclear'), 'source': 'ROIC v3 tickers/search · exact ISIN'}
        old['drs'] = t['drs']
        old.pop('market', None)
        state['homes'][isin] = old
        if not old.get('yahooSymbol'):
            report['unresolved'][old['reason']] = report['unresolved'].get(old['reason'], 0) + 1
            continue
        report['resolved'] += 1
        try:
            q = quote(old['yahooSymbol'])
        except Exception:
            q = None
        why = ('quote_missing' if not q else 'price_or_shares_missing' if not (finite(q.get('price')) and finite(q.get('shares_out')) and q.get('currency'))
               else 'issuer_name_mismatch' if not name_matches(t['name'], q.get('name')) else '')
        if why:
            report['quoteFailed'][why] = report['quoteFailed'].get(why, 0) + 1
            old['quoteProblem'] = why
            continue
        old.pop('quoteProblem', None)
        old['market'] = {'currency': q['currency'], 'quote_at': q.get('quote_at'), 'source': 'Yahoo Finance',
                         'source_url': 'https://finance.yahoo.com/quote/' + urllib.parse.quote(old['yahooSymbol']) + '/',
                         'name': q.get('name'), 'fields': {'price': q['price'], 'shares_out': q['shares_out']}}
        report['quoted'] += 1
    for isin in [k for k in state['homes'] if k not in wanted]:
        del state['homes'][isin]
    state['generatedAt'] = now.isoformat()
    state['report'] = report
    return state


def roic_search(key):
    last = [0.0]

    def search(q):
        time.sleep(max(0, 0.5 - (time.monotonic() - last[0])))
        last[0] = time.monotonic()
        url = 'https://api.roic.ai/v3.0.0/tickers/search?' + urllib.parse.urlencode({'query': q, 'apikey': key})
        req = urllib.request.Request(url, headers={'User-Agent': 'value-radar', 'Accept': 'application/json'})
        with urllib.request.urlopen(req, timeout=12) as response:
            data = json.load(response)
        if isinstance(data, list):
            return data
        for k in ('data', 'results', 'tickers'):
            if isinstance(data, dict) and isinstance(data.get(k), list):
                return data[k]
        raise ValueError('unexpected schema')
    return search


def yahoo_quote(symbol):
    import yfinance as yf
    info = yf.Ticker(symbol).info or {}
    price, currency = info.get('regularMarketPrice'), info.get('currency')
    if currency == 'GBp' and finite(price):
        price, currency = price / 100, 'GBP'
    stamp = info.get('regularMarketTime')
    return {'price': price, 'shares_out': info.get('sharesOutstanding'), 'currency': currency, 'name': info.get('longName') or info.get('shortName'),
            'quote_at': dt.datetime.fromtimestamp(stamp, dt.timezone.utc).isoformat() if isinstance(stamp, (int, float)) else None}


def main(base='.'):
    base = pathlib.Path(base)
    key = os.environ.get('ROIC_API_KEY')
    if not key:
        raise RuntimeError('ROIC_API_KEY missing')
    folder = base / 'daten' / 'fundamentals'
    universe = json.loads((base / 'daten' / 'cf_universum.json').read_text(encoding='utf-8'))
    path = folder / 'adr_homes.json'
    try:
        state = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        state = {}
    def paced_quote(symbol):
        time.sleep(1.5)   # Yahoo bremst schnelle Folgeanfragen; ein Fehlschlag bleibt offen und wird am naechsten Tag wiederholt
        return yahoo_quote(symbol)
    state = run(universe, folder, state, roic_search(key), paced_quote)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    tmp.replace(path)
    print(json.dumps(state['report'], ensure_ascii=False))


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else '.')
