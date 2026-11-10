"""Kurshistorie der Heimatnotierung als gekennzeichneter Ersatz.

Fehlt einer Notierung eine verwertbare eigene Kurshistorie (kein Eintrag, Fehler oder weniger als
505 Handelstage), hat aber dieselbe Aktie (gleiche ISIN) eine Heimatnotierung an einer Boerse
(keine OTC-Notierung) mit vollstaendiger, frischer Historie, wird deren Risikozusammenfassung unter
dem Symbol der Notierung abgelegt. Der Eintrag traegt historySource und einen Hinweistext; die App
zeigt ihn unter "Berechnung und Datenqualitaet". Wechselkursschwankungen zur Handelswaehrung der
Notierung sind nicht enthalten. Echte eigene Historien werden nie ueberschrieben; export-risk.ts
versucht die eigene Historie trotzdem jedes Mal neu.
"""
import copy
import datetime as dt
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

DATA = Path(os.environ.get('RISK_DATA_DIR') or Path(__file__).resolve().parents[1] / 'daten')
MIN_OBSERVATIONS = 505
MAX_AGE_HOURS = 36


def complete(rec, now):
    s = (rec or {}).get('statistics') or {}
    try:
        age = (now - dt.datetime.fromisoformat(str(rec.get('retrievedAt')).replace('Z', '+00:00'))).total_seconds() / 3600
    except (ValueError, AttributeError):
        return False
    return (rec.get('format') == 'risk-summary' and not rec.get('historySource') and not s.get('error')
            and isinstance(s.get('observations'), int) and s['observations'] >= MIN_OBSERVATIONS and s.get('es') is not None and 0 <= age <= MAX_AGE_HOURS)


def build(risk, universe, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    stocks = risk.setdefault('stocks', {})
    rows = [r for r in universe.get('kandidaten', []) if r.get('listing_symbol') and r.get('isin')]
    by_isin = defaultdict(list)
    for r in rows:
        by_isin[r['isin']].append(r)
    report = defaultdict(int)
    for r in rows:
        sym = r['listing_symbol']
        own = stocks.get(sym)
        if own and not own.get('historySource') and complete(own, now):
            continue
        homes = [h for h in by_isin[r['isin']] if h['listing_symbol'] != sym and not h['listing_symbol'].startswith('OTC:') and complete(stocks.get(h['listing_symbol']), now)]
        if not homes:
            if own and own.get('historySource'):
                del stocks[sym]   # Heimathistorie nicht mehr verwertbar: Ersatz entfernen
                report['withdrawn'] += 1
            continue
        if own and not own.get('historySource') and own.get('statistics', {}).get('observations', 0) >= MIN_OBSERVATIONS and not own['statistics'].get('error'):
            continue   # eigene vollstaendige, nur nicht frische Historie bleibt Sache des Exports
        # Stammaktie vor Depositary Receipt, dann die laengere Historie.
        home = max(homes, key=lambda h: (h.get('security_type') == 'stock', stocks[h['listing_symbol']]['statistics']['observations']))
        src = stocks[home['listing_symbol']]
        rec = copy.deepcopy(src)
        rec['symbol'] = sym
        rec['historySource'] = {'kind': 'same_isin_home_listing', 'symbol': home['listing_symbol'], 'isin': r['isin'], 'currency': src.get('currency'),
                                'reason': 'own_history_missing' if not own else ('own_history_error' if own.get('statistics', {}).get('error') else 'own_history_short'),
                                'ownError': (own or {}).get('statistics', {}).get('error') or None}
        rec['historyNote'] = (f"Eigene Kurshistorie dieser Notierung fehlt oder ist unvollständig. Kursrisiko aus der Heimatnotierung {home['listing_symbol']} "
                              f"(gleiche ISIN {r['isin']}, in {src.get('currency')}); Wechselkursschwankungen zur Handelswährung sind nicht enthalten.")
        stocks[sym] = rec
        report['proxied'] += 1
    risk.setdefault('report', {})['historyProxies'] = dict(report)
    return dict(report)


def main(folder=DATA):
    folder = Path(folder)
    path = folder / 'cf_risk.json'
    risk = json.loads(path.read_text(encoding='utf-8'))
    universe = json.loads((folder / 'cf_universum.json').read_text(encoding='utf-8'))
    report = build(risk, universe)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(risk, ensure_ascii=False), encoding='utf-8')
    tmp.replace(path)
    print(json.dumps(report))


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else DATA)
