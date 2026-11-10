"""Taegliche Pruefung der Notierungs-ISIN von OTC-Stammaktien gegen die exakte Notierung beim Anbieter.

Das Universum uebernimmt die Unternehmens-ISIN. Bei Konzernen mit mehreren Aktiengattungen (z. B. A- und H-Aktien)
handelt eine OTC-Linie aber oft eine andere Gattung. Diese Pruefung vergleicht die ISIN im Universum mit der ISIN der
exakten Notierung laut ROIC-Ticker-Suche und meldet Abweichungen. Sie aendert nichts: Korrekturen werden geprueft in
reviewed_listing_reference.json abgelegt (mit Quelle und Ablauf) und dort beim Export angewendet.

Ergebnis je Notierung: confirmed, conflict (ungeprueft), reference_confirmed, reference_contradicted, not_found, ambiguous.
"""
import datetime as dt
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from listing_identity import listing_matches
from news_identity import valid_isin

UTC = dt.timezone.utc
CACHE_DAYS = 14
METHOD = 'otc-listing-isin-audit-v1'


def in_scope(row):
    return str(row.get('listing_symbol') or '').startswith('OTC:') and row.get('security_type') in ('stock', 'common', 'common_stock', 'equity') and valid_isin(row.get('isin'))


def queries(ticker):
    base = str(ticker or '').rsplit('.', 1)[0]
    return [q for q in dict.fromkeys([base]) if q]


def check(row, search):
    """Vergleicht die ISIN der Zeile mit der ISIN der exakten Notierung beim Anbieter."""
    exact = []
    for q in queries(row.get('ticker')):
        exact = [h for h in search(q) if listing_matches(row.get('ticker'), h.get('symbol')) and h.get('symbol') == row.get('listing_symbol')]
        if exact:
            break
    isins = {h.get('isin') for h in exact if valid_isin(h.get('isin'))}
    if not exact or not isins:
        return {'state': 'not_found'}
    if len(isins) != 1:
        return {'state': 'ambiguous', 'providerIsins': sorted(isins)}
    provider = isins.pop()
    applied = row.get('listing_reference_status') == 'applied'
    if provider == row.get('isin'):
        return {'state': 'reference_confirmed' if applied else 'confirmed', 'providerIsin': provider}
    return {'state': 'reference_contradicted' if applied else 'conflict', 'providerIsin': provider, 'universeIsin': row.get('isin'),
            'name': row.get('name_full') or row.get('name'), 'sameCountryPrefix': provider[:2] == str(row.get('isin'))[:2]}


def run(universe, state, search, now=None, budget=240):
    now = now or dt.datetime.now(UTC)
    start = time.monotonic()
    state = state if state.get('method') == METHOD else {'schema': 1, 'method': METHOD, 'listings': {}}
    rows = [r for r in universe.get('kandidaten', []) if in_scope(r)]
    seen = set()
    counts = Counter()
    for r in rows:
        s = r['listing_symbol']
        seen.add(s)
        old = state['listings'].get(s) or {}
        try:
            fresh = bool(old.get('state')) and old.get('inputIsin') == r['isin'] and \
                dt.timedelta(0) <= now - dt.datetime.fromisoformat(old['checkedAt']) < dt.timedelta(days=CACHE_DAYS)
        except (KeyError, ValueError, TypeError):
            fresh = False
        if fresh:
            counts[old['state']] += 1
            continue
        if time.monotonic() - start >= budget:
            counts['budgetReached'] += 1
            break
        try:
            res = check(r, search)
        except Exception:
            counts['provider_unavailable'] += 1
            continue
        state['listings'][s] = {**res, 'inputIsin': r['isin'], 'checkedAt': now.isoformat(), 'source': 'ROIC v3 tickers/search · exact listing'}
        counts[res['state']] += 1
    for s in [k for k in state['listings'] if k not in seen]:
        del state['listings'][s]
    state['generatedAt'] = now.isoformat()
    state['summary'] = dict(counts)
    state['openConflicts'] = sorted(s for s, v in state['listings'].items() if v.get('state') in ('conflict', 'reference_contradicted'))
    return state


def main(folder=None):
    folder = Path(folder or os.getenv('RISK_DATA_DIR') or Path(__file__).resolve().parents[1] / 'daten')
    key = os.getenv('ROIC_API_KEY')
    if not key:
        raise RuntimeError('ROIC_API_KEY missing')
    universe = json.loads((folder / 'cf_universum.json').read_text(encoding='utf-8'))
    path = folder / 'cf_listing_isin_audit.json'
    try:
        state = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        state = {}
    last = [0.0]

    def search(q):
        time.sleep(max(0, 0.5 - (time.monotonic() - last[0])))
        last[0] = time.monotonic()
        url = 'https://api.roic.ai/v3.0.0/tickers/search?' + urllib.parse.urlencode({'query': q, 'apikey': key})
        req = urllib.request.Request(url, headers={'User-Agent': 'value-radar', 'Accept': 'application/json'})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.load(response)
        if isinstance(data, list):
            return data
        for k in ('data', 'results', 'tickers'):
            if isinstance(data, dict) and isinstance(data.get(k), list):
                return data[k]
        raise ValueError('unexpected schema')

    state = run(universe, state, search)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    tmp.replace(path)
    print(json.dumps({'summary': state['summary'], 'openConflicts': state['openConflicts']}, ensure_ascii=False))


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else None)
