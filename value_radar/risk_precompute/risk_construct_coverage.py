"""Taegliche Abdeckungsmessung des Risiko-Konstrukts (Version 0.8) fuer das ganze Universum.

Prueft je Notierung und Kennzahl, ob die Eingangsdaten offline vorliegen. Das ist eine
Datenverfuegbarkeit, kein nachgerechneter Score: Die App rechnet mit Live-Daten (ROIC-Abruf,
Peer-Kurse, Fair Value). Kennzahlen, die nur dort pruefbar sind, zaehlen als "app_only",
bewusst offene Kennzahlen (z. B. Bruttomarge bei Banken) als "by_design".

Ergebnis: daten/cf_risk_construct_coverage.json mit Befuellung je Profil und Block und einer
Rangliste der groessten Luecken (Gewicht x fehlende Notierungen).
"""
import datetime as dt
import json
import math
import os
import sys
from collections import defaultdict
from pathlib import Path

DATA = Path(os.environ.get('RISK_DATA_DIR') or Path(__file__).resolve().parents[1] / 'daten')
BLOCKS = {'Kursrisiko': 30, 'Finanzielle Verwundbarkeit': 25, 'Umfeldstress': 15, 'Bewertungsrisiko': 15, 'Wettbewerbsanfälligkeit': 15}
CONSTRUCT_VERSION = '0.8'
MIN_OBSERVATIONS = 505


def finite(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def load(path, default):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return default


def available(d):
    return isinstance(d, dict) and d.get('state') == 'available'


class Listing:
    """Offline verfuegbare Eingangsdaten einer Notierung."""

    def __init__(self, symbol, domains, universe_row, stats, annual, market_currency, peers):
        self.symbol, self.domains, self.u, self.stats = symbol, domains or {}, universe_row or {}, stats or {}
        self.balance = self.domains.get('balance') or {}
        self.f = (annual or {}).get('fields') or {}
        ac, mc = (annual or {}).get('currency'), market_currency
        # Waehrungskonflikt wie in der App-Datenpruefung: Bericht und Handel verschieden (GBP/Pence gilt als gleich).
        self.currency_conflict = bool(annual) and ac != mc and not (ac == 'GBP' and mc == 'GBp')
        self.peers = peers
        bc = self.balance.get('bankCapital') or {}
        profile = self.balance.get('profile') or 'unclassified'
        self.bank_like = profile == 'specialist_financial' and available(bc)
        self.profile = 'bank' if self.bank_like else profile

    def stat(self, key):
        s = self.stats
        return not s.get('error') and finite(s.get('observations')) and s['observations'] >= MIN_OBSERVATIONS and finite(s.get(key))


def m(block, name, weight, status, reason=''):
    return {'block': block, 'name': name, 'weight': weight, 'status': status, 'reason': reason}


def yes(ok, reason):
    return 'filled' if ok else 'missing', ('' if ok else reason)


def first(*checks):
    """Erste zutreffende Ursache als Grund; ohne Ursache gilt die Kennzahl als befuellt."""
    for failed, reason in checks:
        if failed:
            return 'missing', reason
    return 'filled', ''


def metrics(x):
    """Kennzahlen des Konstrukts mit Status filled / missing / app_only / by_design."""
    out = []
    K, F, U, V, W = BLOCKS.keys()
    s = x.stats
    for name, key, w in (('Expected Shortfall', 'es', 15), ('Volatilität', 'vol', 10), ('Größter Rückgang', 'dd', 5)):
        out.append(m(K, name, w, *first((not s, 'Keine Kurshistorie'), (bool(s.get('error')), 'Kurshistorie fehlerhaft'),
                                        (not (finite(s.get('observations')) and s['observations'] >= MIN_OBSERVATIONS), 'Kurshistorie kürzer als 505 Handelstage'),
                                        (not finite(s.get(key)), 'Kennzahl in der Vorberechnung noch nicht vorhanden'))))
    f, u, b = x.f, x.u, x.balance
    p = x.profile
    if p == 'bank':
        c = b.get('bankCapital') or {}
        credit = available(c.get('creditQuality')) or available((x.domains.get('reviewedRisk') or {}).get('bankCredit'))
        out += [m(F, 'Kernkapital-Puffer (CET1)', 10, *yes(available(c) and available(c.get('capitalRequirement')), 'Geprüfte Kapitalquote mit Anforderung fehlt')),
                m(F, 'Liquiditätsdeckung (LCR)', 7.5, *yes(available(c) and available(c.get('liquidity')), 'Geprüfte LCR fehlt')),
                m(F, 'Kreditqualität', 7.5, *yes(available(c) and credit, 'Geprüfte Kreditqualität fehlt'))]
    elif p == 'insurer':
        out += [m(F, 'Solvenzquote', 15, *yes(available(b.get('insurerSolvency')), 'Geprüfte Solvenzquote fehlt')),
                m(F, 'Reserve- und Kapitalanlagerisiko', 10, 'by_design', 'Für Versicherer noch nicht umgesetzt')]
    elif p == 'specialist_financial':
        eq, ta = f.get('equity'), f.get('total_assets')
        ratio = eq / ta if finite(eq) and finite(ta) and ta > 0 else None
        nd_ok = not x.currency_conflict and finite(eq) and eq > 0 and finite(f.get('total_debt')) and finite(f.get('cash')) and ratio is not None
        if nd_ok and ratio < .10:
            out.append(m(F, 'Nettofinanzschulden / Eigenkapital', 15, 'by_design', 'Bilanz mit Kunden-, Clearing- oder Bankvermögen'))
        else:
            out.append(m(F, 'Nettofinanzschulden / Eigenkapital', 15, *yes(nd_ok, 'Eigenkapital, Schulden, Kasse oder Bilanzsumme fehlen oder Währungskonflikt')))
        out.append(m(F, 'Eigenkapitalrendite', 10, *yes(finite(f.get('net_income')) and finite(eq) and eq > 0, 'Jahresergebnis oder Eigenkapital fehlt')))
    else:
        ebitda = f.get('ebitda')
        out += [m(F, 'Nettoschulden / EBITDA', 15, *yes((finite(ebitda) and ebitda > 0 and finite(f.get('total_debt')) and finite(f.get('cash'))) or finite(u.get('net_debt_ebitda')), 'EBITDA, Schulden oder Kasse fehlen')),
                m(F, 'FCFF-Marge', 10, *yes(finite(f.get('operating_cashflow')) and finite(f.get('capex')) and finite(f.get('revenue')) and f['revenue'] > 0, 'Cashflow, Investitionen oder Umsatz fehlen'))]
    out += [m(U, 'Markt-ETF', 10, *yes(available(x.domains.get('market')), 'Kein Markt-ETF zugeordnet')),
            m(U, 'Peer-Stress', 5, *yes(available(x.domains.get('sector')), 'Vergleichsgruppe zu klein oder nicht geprüft'))]
    growth = f.get('revenue_growth') if finite(f.get('revenue_growth')) else (u['revenue_growth'] / 100 if finite(u.get('revenue_growth')) else None)
    if p in ('bank', 'insurer'):
        out.append(m(V, 'Erwartungslücke Eigenkapitalrendite', 10, *first((x.currency_conflict, 'Währungskonflikt (Bericht und Handel verschieden)'),
                                                                        (not (finite(u.get('pb')) and .05 < u['pb'] < 15), 'KBV fehlt oder unplausibel'),
                                                                        (not finite(u.get('roe')), 'Eigenkapitalrendite fehlt'))))
    elif p == 'specialist_financial':
        ni = f.get('net_income')
        out.append(m(V, 'Erwartungslücke Gewinnwachstum', 10, *first((x.currency_conflict, 'Währungskonflikt (Bericht und Handel verschieden)'),
                                                                   (not (finite(ni) and ni > 0), 'Verlust oder Jahresergebnis fehlt'),
                                                                   (growth is None, 'Umsatzwachstum fehlt'),
                                                                   (growth is not None and abs(growth) > .5, 'Umsatzsprung über ±50 %'))))
    else:
        fcf = f['operating_cashflow'] - abs(f['capex']) if finite(f.get('operating_cashflow')) and finite(f.get('capex')) else None
        out.append(m(V, 'Erwartungslücke Reverse DCF', 10, *first((x.currency_conflict, 'Währungskonflikt (Bericht und Handel verschieden)'),
                                                                (fcf is None, 'Cashflow oder Investitionen fehlen'),
                                                                (fcf is not None and fcf <= 0, 'Freier Cashflow negativ oder null'),
                                                                (growth is None, 'Umsatzwachstum fehlt'))))
    out.append(m(V, 'Abstand zum Bear-Szenario', 5, 'app_only', 'Benötigt die Szenariorechnung der App'))
    if p in ('bank', 'insurer', 'specialist_financial'):
        out += [m(W, 'Bruttomargen-Trend', 5, 'by_design', 'Für Finanzunternehmen nicht definiert'),
                m(W, 'EBITDA-Marge gegenüber Peers', 5, 'by_design', 'Für Finanzunternehmen nicht aussagekräftig')]
    else:
        out += [m(W, 'Bruttomargen-Trend', 5, 'app_only', 'Benötigt drei Geschäftsjahre aus dem ROIC-Abruf der App'),
                m(W, 'EBITDA-Marge gegenüber Peers', 5, *yes(finite(u.get('ebitda_margin')) and x.peers >= 3, 'Eigene EBITDA-Marge oder mindestens drei Peers mit Marge fehlen'))]
    out.append(m(W, 'Umsatzentwicklung', 5, 'app_only', 'Benötigt drei Geschäftsjahre aus dem ROIC-Abruf der App'))
    return out


def build(universe, shards, risk, annuals, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    rows = {r.get('listing_symbol'): r for r in universe.get('kandidaten', []) if r.get('listing_symbol')}
    margins = defaultdict(int)
    for r in rows.values():
        if finite(r.get('ebitda_margin')) and r.get('industry'):
            margins[r['industry']] += 1
    per_profile = defaultdict(lambda: {'listings': 0, 'blocks': defaultdict(lambda: defaultdict(float))})
    per_metric = defaultdict(lambda: {'filled': 0, 'missing': 0, 'app_only': 0, 'by_design': 0, 'weight': 0, 'reasons': defaultdict(int)})
    for symbol, domains in shards.items():
        u = rows.get(symbol, {})
        annual, currency = annuals.get(symbol, (None, None))
        own = 1 if finite(u.get('ebitda_margin')) else 0
        x = Listing(symbol, domains, u, (risk.get(symbol) or {}).get('statistics'), annual, currency, margins.get(u.get('industry'), 0) - own)
        prof = per_profile[x.profile]
        prof['listings'] += 1
        for k in metrics(x):
            blk = prof['blocks'][k['block']]
            blk[k['status']] += k['weight']
            pm = per_metric[(x.profile, k['block'], k['name'])]
            pm[k['status']] += 1
            pm['weight'] = k['weight']
            if k['status'] == 'missing':
                pm['reasons'][k['reason']] += 1
    profiles = {}
    for name, prof in sorted(per_profile.items()):
        n = prof['listings']
        blocks = {}
        for b, w in BLOCKS.items():
            s = prof['blocks'][b]
            blocks[b] = {'weight': w, **{k: round(s[k] / n, 2) for k in ('filled', 'missing', 'app_only', 'by_design')},
                         'filledShareOfMeasurable': round(s['filled'] / (s['filled'] + s['missing']), 3) if s['filled'] + s['missing'] else None}
        tot = {k: round(sum(prof['blocks'][b][k] for b in BLOCKS) / n, 1) for k in ('filled', 'missing', 'app_only', 'by_design')}
        profiles[name] = {'listings': n, 'averageWeight': tot, 'blocks': blocks}
    gaps = [{'profile': p, 'block': b, 'metric': n, 'weight': v['weight'], 'missingListings': v['missing'], 'filledListings': v['filled'],
             'weightedGap': round(v['weight'] * v['missing'], 1), 'reasons': dict(sorted(v['reasons'].items(), key=lambda kv: -kv[1]))}
            for (p, b, n), v in per_metric.items() if v['missing']]
    gaps.sort(key=lambda g: -g['weightedGap'])
    app_only = sorted({(b, n) for (p, b, n), v in per_metric.items() if v['app_only']})
    listings = sum(p['listings'] for p in profiles.values())
    overall = {k: round(sum(p['averageWeight'][k] * p['listings'] for p in profiles.values()) / listings, 1) for k in ('filled', 'missing', 'app_only', 'by_design')} if listings else {}
    return {'schema': 1, 'method': 'offline-input-availability-v1', 'constructVersion': CONSTRUCT_VERSION, 'generatedAt': now.isoformat(),
            'listings': listings, 'overallAverageWeight': overall, 'profiles': profiles, 'largestGaps': gaps[:25],
            'appOnlyMetrics': [{'block': b, 'metric': n} for b, n in app_only],
            'limitations': ['Measures whether offline inputs exist, not the score the app computes with live data.',
                            'Peer stress uses the precomputed sector domain as a proxy for the peer histories loaded by the app.',
                            'Corporate FCF uses operating cash flow minus capex from the dated annual record, not the FCFF of the app.']}


def annual_records(folder):
    out = {}
    for f in (folder / 'fundamentals').glob('*.json'):
        d = load(f, {})
        a = d.get('annual') if isinstance(d.get('annual'), dict) else None
        out[f.stem] = (a, (d.get('market') or {}).get('currency'))
    return out


def main(folder=DATA):
    folder = Path(folder)
    manifest = load(folder / 'cf_risk_app_manifest.json', {})
    shards = {}
    for h in (manifest.get('shards') or {}).values():
        for s in load(folder / 'risk_app' / f'{h}.json', {}).get('stocks', []):
            shards[s['symbol']] = s.get('domains', {})
    files = annual_records(folder)
    annuals = {sym: files.get(sym.replace(':', '_'), (None, None)) for sym in shards}
    result = build(load(folder / 'cf_universum.json', {}), shards, (load(folder / 'cf_risk.json', {}).get('stocks') or {}), annuals)
    (folder / 'cf_risk_construct_coverage.json').write_text(json.dumps(result, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print(json.dumps({'listings': result['listings'], 'overallAverageWeight': result['overallAverageWeight'],
                      'topGaps': [(g['profile'], g['metric'], g['missingListings']) for g in result['largestGaps'][:5]]}, ensure_ascii=False))


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else DATA)
