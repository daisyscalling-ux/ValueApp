"""Taegliches Archiv der Rohdaten aller Risikoblocke je Notierung (Point-in-Time-Grundlage).

Speichert, was an diesem Tag bekannt war: Kursstatistik, Markt- und Branchenumfeld,
letzter Jahresabschluss mit Veroeffentlichungsdatum, Bewertungsangaben aus dem Universum,
Bank- und Versichererkapital sowie gepruefte Ereignisse. Keine Scores: Jede spaetere
Formelversion soll aus denselben Rohdaten nachrechenbar sein.

Regeln: erste Beobachtung je UTC-Tag wird geschrieben und nie ueberschrieben; Werte werden
nie rueckdatiert; fehlende oder nicht endliche Werte bleiben null.
"""
import datetime as dt
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys

METHOD = 'risk-feature-snapshot-v1'
DAY = 86400
UNIVERSE_FIELDS = ('price', 'fair_value', 'upside', 'revenue_growth', 'gross_margin', 'ebitda_margin', 'net_debt_ebitda',
                   'ev_ebitda', 'pe', 'pb', 'beta', 'market_cap', 'target_mean', 'analyst_count')
FUNDAMENTAL_FIELDS = ('revenue', 'gross_profit', 'ebit', 'ebitda', 'net_income', 'operating_cashflow', 'capex', 'cash',
                      'total_debt', 'total_assets', 'total_liabilities', 'equity', 'interest_expense', 'revenue_growth',
                      'eps_trailing', 'weighted_shares')
MARKET_FIELDS = ('price', 'shares_out', 'beta', '52w_high', '52w_low', 'target_mean', 'analyst_count')
PRICE_FIELDS = ('observations', 'first', 'last', 'error', 'es', 'vol', 'dd', 'worst', 'drawdown')


def finite(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) else None


def pick(row, keys, numeric=True):
    row = row if isinstance(row, dict) else {}
    return {k: (finite(row.get(k)) if numeric else row.get(k)) for k in keys}


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def stamp(value):
    try:
        t = dt.datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return t if t.tzinfo else None
    except ValueError:
        return None


def fundamentals_name(symbol):
    return re.sub('[^A-Za-z0-9._-]', '_', symbol) + '.json'


def price_block(summary):
    if not isinstance(summary, dict):
        return None
    s = summary.get('statistics') or {}
    out = {k: (s.get(k) if k in ('first', 'last', 'error') else finite(s.get(k))) for k in PRICE_FIELDS}
    out.update(retrievedAt=summary.get('retrievedAt'), adjustment=summary.get('adjustment'), currency=summary.get('currency'))
    # Ersatzhistorie aus der Heimatnotierung bleibt im Archiv erkennbar.
    if isinstance(summary.get('historySource'), dict):
        out['historySource'] = summary['historySource'].get('symbol')
    return out


def sector_block(sector):
    if not isinstance(sector, dict):
        return None
    out = {k: sector.get(k) for k in ('state', 'reason', 'group', 'groupLevel', 'currency', 'peerIssuers', 'observationDate')}
    out.update(drawdown=finite(sector.get('drawdown')), medianDrawdown=finite(sector.get('medianDrawdown')))
    broad = sector.get('broaderContext')
    if isinstance(broad, dict):
        out['broader'] = {**{k: broad.get(k) for k in ('state', 'group', 'peerIssuers', 'observationDate')},
                          'drawdown': finite(broad.get('drawdown')), 'medianDrawdown': finite(broad.get('medianDrawdown'))}
    return out


def bank_block(balance, reviewed):
    c = (balance or {}).get('bankCapital')
    if not isinstance(c, dict) or c.get('state') != 'available':
        return None
    req, liq = c.get('capitalRequirement') or {}, c.get('liquidity') or {}
    # US: Kreditqualitaet aus reviewedRisk.bankCredit; EU (EBA): direkt am Kapitaleintrag (creditQuality, eba-npl-v1).
    eu_credit = c.get('creditQuality') or {}
    credit = eu_credit if c.get('scope') == 'eu_prudential_group' else (reviewed or {}).get('bankCredit') or {}
    return {'period': c.get('period'), 'rssdId': c.get('rssdId'), 'lei': c.get('lei'), 'scope': c.get('scope'),
            'ratios': {k: finite((c.get('metrics') or {}).get(k, {}).get('value')) for k in ('cet1_ratio', 'tier1_ratio', 'total_capital_ratio', 'tier1_leverage_ratio', 'leverage_ratio')},
            'cet1Requirement': finite(req.get('value')) if req.get('state') == 'available' else None,
            'cet1RequirementMethod': req.get('method') if req.get('state') == 'available' else None,
            'requirementReviewExpires': req.get('reviewExpires'),
            'lcr': finite(liq.get('reportedRatio')) if liq.get('state') == 'available' else None,
            'lcrPeriod': liq.get('period'), 'lcrReviewExpires': liq.get('reviewExpires'),
            'problemLoanRatio': finite(credit.get('ratio')) if credit.get('state') == 'available' else None,
            'problemLoanPeriod': credit.get('period'), 'problemLoanPeerMedian': finite(credit.get('peerMedian')),
            'problemLoanMethod': credit.get('method') if credit.get('state') == 'available' else None}


def insurer_block(balance):
    s = (balance or {}).get('insurerSolvency')
    if not isinstance(s, dict):
        return None
    obs = [o for o in s.get('observations') or [] if isinstance(o, dict) and finite(o.get('ratio')) is not None]
    obs.sort(key=lambda o: str(o.get('period')), reverse=True)
    return {'framework': s.get('framework'), 'reviewExpires': s.get('reviewExpires'),
            'observations': [{k: o.get(k) for k in ('period', 'reportKind', 'basis', 'ratio')} for o in obs[:4]]}


def listing_record(row, universe_row, risk, benchmarks, fundamentals):
    d = row.get('domains') or {}
    balance, reviewed = d.get('balance') or {}, d.get('reviewedRisk') or {}
    proxy = (d.get('market') or {}).get('proxy')
    bench = benchmarks.get(proxy) if proxy else None
    f = fundamentals or {}
    annual = f.get('annual') or {}
    events = [{k: e.get(k) for k in ('candidateId', 'state', 'eventDate', 'reviewedAt', 'expiresAt', 'sourceType')}
              for e in reviewed.get('events') or [] if isinstance(e, dict) and e.get('state') == 'confirmed_event']
    return {
        'symbol': row.get('symbol'), 'name': row.get('name'), 'country': row.get('country'),
        'profile': balance.get('profile'), 'sectorName': (universe_row or {}).get('sector'), 'industry': (universe_row or {}).get('industry'),
        'price': price_block(risk.get(row.get('symbol'))),
        'market': {'proxy': proxy, 'drawdown': finite(((bench or {}).get('statistics') or {}).get('drawdown')),
                   'last': ((bench or {}).get('statistics') or {}).get('last')} if proxy else None,
        'sectorContext': sector_block(d.get('sector')),
        'universe': {**pick(universe_row, UNIVERSE_FIELDS), 'currency': (universe_row or {}).get('currency')} if universe_row else None,
        'fundamentals': {'retrievedAt': f.get('retrieved_at'), 'end': annual.get('end'), 'publishedAt': annual.get('published_at'),
                         'currency': annual.get('currency'), 'source': annual.get('source'),
                         'fields': pick(annual.get('fields'), FUNDAMENTAL_FIELDS),
                         'market': {**pick((f.get('market') or {}).get('fields'), MARKET_FIELDS),
                                    'currency': (f.get('market') or {}).get('currency'), 'quoteAt': (f.get('market') or {}).get('quote_at')}}
                        if annual else None,
        'balanceRatios': {k: finite(v) for k, v in (balance.get('ratios') or {}).items()} or None,
        'bank': bank_block(balance, reviewed), 'insurer': insurer_block(balance), 'confirmedEvents': events,
    }


def build(folder, now, code_version=''):
    folder = Path(folder)
    files = {name: (folder / name).read_bytes() for name in ('cf_universum.json', 'cf_risk.json', 'cf_risk_app_manifest.json')}
    universe, risk, manifest = (json.loads(files[n]) for n in ('cf_universum.json', 'cf_risk.json', 'cf_risk_app_manifest.json'))
    generated = stamp(manifest.get('generatedAt'))
    if not generated or not 0 <= (now - generated).total_seconds() <= 1.5 * DAY:
        raise ValueError('stale_or_missing_app_manifest')
    rows = []
    shard_hashes = {}
    for key, name in sorted((manifest.get('shards') or {}).items()):
        raw = (folder / 'risk_app' / f'{name}.json').read_bytes()
        if digest(raw) != name:
            raise ValueError('shard_hash_mismatch')
        shard_hashes[key] = name
        rows.extend(json.loads(raw).get('stocks') or [])
    symbols = [r.get('symbol') for r in rows]
    if not rows or len(symbols) != len(set(symbols)):
        raise ValueError('missing_or_duplicate_listings')
    by_symbol = {(u.get('listing_symbol') or u.get('ticker')): u for u in universe.get('kandidaten') or []}
    fund_dir, fund_hashes, records = folder / 'fundamentals', {}, []
    for row in sorted(rows, key=lambda r: r['symbol']):
        path = fund_dir / fundamentals_name(row['symbol'])
        fund = None
        if path.exists():
            raw = path.read_bytes()
            fund_hashes[path.name] = digest(raw)
            fund = json.loads(raw)
        records.append(listing_record(row, by_symbol.get(row['symbol']), risk.get('stocks') or {}, risk.get('benchmarks') or {}, fund))
    return {
        'schema': 1, 'method': METHOD, 'observedAt': now.isoformat(), 'codeVersion': code_version,
        'sources': {**{n: {'sha256': digest(b), 'generatedAt': json.loads(b).get('generatedAt') or json.loads(b).get('stand')} for n, b in files.items()},
                    'risk_app_shards': shard_hashes,
                    'fundamentals': {'files': len(fund_hashes), 'sha256': digest(json.dumps(fund_hashes, sort_keys=True).encode())}},
        'listings': len(records), 'records': records,
        'limitations': ['Beobachtet am observedAt; Abschluesse tragen ihr eigenes Periodenende und Veroeffentlichungsdatum.',
                        'Anbieter koennen Werte spaeter revidieren; dieses Archiv haelt den damals gelieferten Stand fest.',
                        'Keine Scores und keine Ergebnislabels; spaetere Kursverlaeufe kommen aus eigenen datierten Beobachtungen.'],
    }


def compact(value):
    """Leere Werte weglassen (fehlender Schluessel = nicht vorhanden), Zahlen auf 6 signifikante Stellen."""
    if isinstance(value, dict):
        out = {k: compact(v) for k, v in value.items()}
        return {k: v for k, v in out.items() if v not in (None, {}, [], '')}
    if isinstance(value, list):
        return [compact(v) for v in value]
    if isinstance(value, float):
        return float(f'{value:.6g}')
    return value


def write_once(snapshot, target, now):
    target.mkdir(parents=True, exist_ok=True)
    path = target / f'{now.date().isoformat()}.json.gz'
    if path.exists():
        saved = json.loads(gzip.decompress(path.read_bytes()))
        if saved.get('method') != METHOD or stamp(saved.get('observedAt')).date() != now.date():
            raise ValueError('existing_snapshot_invalid')
        return {'state': 'retained_first_daily_snapshot', 'file': path.name, 'observedAt': saved['observedAt']}
    raw = gzip.compress(json.dumps(compact(snapshot), sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode(), mtime=0)
    tmp = path.with_suffix('.tmp')
    tmp.write_bytes(raw)
    tmp.replace(path)
    return {'state': 'recorded', 'file': path.name, 'observedAt': snapshot['observedAt'], 'bytes': len(raw), 'sha256': digest(raw)}


def load_snapshots(target):
    """Alle Tagesarchive in Datumsreihenfolge; Grundlage fuer spaetere Kalibrierungsstudien."""
    for path in sorted(Path(target).glob('*.json.gz')):
        yield json.loads(gzip.decompress(path.read_bytes()))


def main():
    folder = Path(sys.argv[1] if len(sys.argv) > 1 else 'value_radar/daten')
    now = dt.datetime.now(dt.timezone.utc)
    snapshot = build(folder, now, os.environ.get('GITHUB_SHA', ''))
    result = write_once(snapshot, folder / 'risk_observations' / 'features', now)
    filled = {k: sum(1 for r in snapshot['records'] if r.get(k)) for k in ('price', 'market', 'sectorContext', 'universe', 'fundamentals', 'bank', 'insurer')}
    print(json.dumps({**result, 'listings': snapshot['listings'], 'filled': filled}, indent=1))


if __name__ == '__main__':
    main()
