"""Kursblock des Risikoscores gegen spaetere Verluste im historischen S&P 500 pruefen.

Liest ein free-source-research-Archiv (Ordner oder ZIP). Vorab festgelegte Regeln:
- Stichtage: letzter Handelstag jedes Quartals; Universum = damalige Indexmitglieder.
- Merkmale nur aus Kursen bis zum Stichtag, hoechstens fuenf Kalenderjahre, mindestens 505 Kurse,
  keine Luecke ueber 14 Tage, letzter Kurs hoechstens sieben Tage alt (wie historyStatistics der App).
- Einstieg Schlusskurs der naechsten Sitzung; groesster Verlust ab Einstieg in 21/63/126 Sitzungen.
- Entwicklung: Stichtage vor 2022-01-01. Test: ab 2022-01-01; Fenster duerfen nicht in den Test hineinreichen.
Keine Aenderung produktiver Gewichte; Ergebnis ist eine Forschungsauswertung.
"""
import argparse
import csv
import datetime as dt
import io
import json
import math
from pathlib import Path
import zipfile

import numpy as np

HORIZONS = (21, 63, 126)
SPLIT = '2022-01-01'
LOOKBACK_YEARS = 5
EVENT = 0.20


def lin(v, zero, full):
    return max(0.0, min(100.0, 100.0 * (v - zero) / (full - zero)))


def features(dates, prices, end):
    """Merkmale bis einschliesslich Index end; None bei unzureichender Historie."""
    start_date = dt.date.fromisoformat(dates[end]) - dt.timedelta(days=round(365.25 * LOOKBACK_YEARS))
    start = int(np.searchsorted(np.array(dates[:end + 1]), start_date.isoformat()))
    p = prices[start:end + 1]
    d = dates[start:end + 1]
    if len(p) < 505:
        return None
    stamps = np.array([dt.date.fromisoformat(x).toordinal() for x in d])
    if np.any(np.diff(stamps) > 14):
        return None
    r = p[1:] / p[:-1] - 1
    tail = np.sort(r)[:max(1, int(len(r) * 0.05))]
    es = max(0.0, -tail.mean())
    peak = np.maximum.accumulate(p)
    dd = float(np.max(1 - p / peak))
    worst = float(np.max(1 - p[20:] / p[:-20])) if len(p) > 20 else 0.0
    vol = float(np.std(r[-252:], ddof=1) * math.sqrt(252))
    recent = p[-252:]
    cur_dd = float(1 - recent[-1] / recent.max())
    score = (15 * lin(es, .01, .07) + 10 * lin(dd, .15, .70) + 5 * lin(worst, .05, .35)) / 30
    return dict(es=es, dd=dd, worst=worst, vol=vol, cur_dd=cur_dd, score=score)


def outcome(prices, entry, n):
    if entry + n >= len(prices):
        return None
    path = prices[entry + 1:entry + n + 1] / prices[entry] - 1
    return float(max(0.0, -path.min()))


def spearman(a, b):
    ra = np.argsort(np.argsort(a)).astype(float)
    rb = np.argsort(np.argsort(b)).astype(float)
    return float(np.corrcoef(ra, rb)[0, 1])


def auc(score, event):
    score, event = np.asarray(score), np.asarray(event, bool)
    pos, neg = score[event], score[~event]
    if not len(pos) or not len(neg):
        return None
    ranks = np.argsort(np.argsort(np.concatenate([pos, neg]))) + 1.0
    # Bindungen mitteln
    allv = np.concatenate([pos, neg])
    for v in np.unique(allv):
        m = allv == v
        if m.sum() > 1:
            ranks[m] = ranks[m].mean()
    return float((ranks[:len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def load(source):
    source = Path(source)
    archive = zipfile.ZipFile(source) if source.is_file() else None
    def read(name):
        return archive.read(name).decode('utf-8-sig') if archive else (source / name).read_text(encoding='utf-8-sig')
    table = lambda name: list(csv.DictReader(io.StringIO(read(name))))
    identities = table('identity-review/identitaetspruefung.csv')
    members = table('identity-review/mitglieder_korrigiert_vorlaeufig.csv')
    sessions = [r['date'] for r in table('session-review/handelskalender.csv')]
    series = {}
    for row in identities:
        if not row['price_file']:
            continue
        rows = [r for r in table(row['price_file']) if r['Adjusted_Close']]
        dates = [r['Datum'] for r in rows]
        prices = np.array([float(r['Adjusted_Close']) for r in rows])
        if len(prices) and np.all(np.isfinite(prices)) and np.all(prices > 0):
            series[row['identity']] = (dates, prices)
    spans = {}
    for m in members:
        spans.setdefault(m['symbol'], []).append((m['start'], m['end']))
    status = {r['identity']: r['status'] for r in identities}
    return series, spans, sessions, status


def quarter_ends(sessions, first='2016-01-01'):
    out = []
    for a, b in zip(sessions, sessions[1:]):
        if a >= first and (a[:4], (int(a[5:7]) - 1) // 3) != (b[:4], (int(b[5:7]) - 1) // 3):
            out.append(a)
    return out


def build(series, spans, sessions, status):
    rows, missing = [], {'no_prices': 0, 'short_or_gappy_history': 0, 'stale_last_price': 0}
    for day in quarter_ends(sessions):
        nxt = sessions[sessions.index(day) + 1] if sessions.index(day) + 1 < len(sessions) else None
        for sid, iv in spans.items():
            if not any(a <= day < b for a, b in iv):
                continue
            if sid not in series:
                missing['no_prices'] += 1
                continue
            dates, prices = series[sid]
            end = int(np.searchsorted(np.array(dates), day, side='right')) - 1
            if end < 0 or (dt.date.fromisoformat(day) - dt.date.fromisoformat(dates[end])).days > 7:
                missing['stale_last_price'] += 1
                continue
            f = features(dates, prices, end)
            if f is None:
                missing['short_or_gappy_history'] += 1
                continue
            if nxt is None or end + 1 >= len(dates) or dates[end + 1] != nxt:
                continue
            outs = {n: outcome(prices, end + 1, n) for n in HORIZONS}
            rows.append(dict(identity=sid, decision=day, status=status.get(sid, ''), **f,
                             **{f'loss{n}': outs[n] for n in HORIZONS},
                             **{f'end{n}': dates[end + 1 + n] if end + 1 + n < len(dates) else None for n in HORIZONS}))
    return rows, missing


PRICE_BLOCK_VARIANTS = {
    # Vorab festgelegt am 09.11.2026; Auswahl ausschliesslich nach Entwicklungszeitraum, 63 Sitzungen.
    'A_production_es15_dd10_w20_5': lambda r: r['score'],
    'B_es15_dd10': lambda r: (15 * lin(r['es'], .01, .07) + 10 * lin(r['dd'], .15, .70)) / 25,
    'C_volatility': lambda r: lin(r['vol'], .15, .60),
    'D_es15_vol10_dd5': lambda r: (15 * lin(r['es'], .01, .07) + 10 * lin(r['vol'], .15, .60) + 5 * lin(r['dd'], .15, .70)) / 30,
    'E_es15_vol15': lambda r: (15 * lin(r['es'], .01, .07) + 15 * lin(r['vol'], .15, .60)) / 30,
    'F_production_w20_scale_10_60': lambda r: (15 * lin(r['es'], .01, .07) + 10 * lin(r['dd'], .15, .70) + 5 * lin(r['worst'], .10, .60)) / 30,
}
SELECTION_RULE = 'Hoechste mittlere Stichtags-Rangkorrelation im Entwicklungszeitraum, 63 Sitzungen'

CANDIDATES = {
    **PRICE_BLOCK_VARIANTS,
    'production_score': lambda r: r['score'],
    'volatility_252d': lambda r: r['vol'],
    'expected_shortfall_5pct': lambda r: r['es'],
    'max_drawdown': lambda r: r['dd'],
    'worst_20d': lambda r: r['worst'],
    'current_drawdown_252d': lambda r: r['cur_dd'],
}


def evaluate(rows, n):
    report = {}
    for period in ('development', 'test'):
        sel = [r for r in rows if r[f'loss{n}'] is not None and r[f'end{n}'] is not None and
               ((r['decision'] < SPLIT and r[f'end{n}'] < SPLIT) if period == 'development' else r['decision'] >= SPLIT)]
        if not sel:
            continue
        losses = np.array([r[f'loss{n}'] for r in sel])
        events = losses >= EVENT
        by_date = {}
        for i, r in enumerate(sel):
            by_date.setdefault(r['decision'], []).append(i)
        res = dict(windows=len(sel), securities=len({r['identity'] for r in sel}), dates=len(by_date),
                   event_rate=float(events.mean()), candidates={})
        for name, fn in CANDIDATES.items():
            vals = np.array([fn(r) for r in sel])
            rhos = [spearman(vals[idx], losses[idx]) for idx in by_date.values() if len(idx) >= 20]
            # Ereignisquote je Quintil des Merkmals innerhalb jedes Stichtags (keine Zeitvermischung)
            quint = np.zeros(len(sel), int)
            for idx in by_date.values():
                ranks = np.argsort(np.argsort(vals[idx]))
                quint[idx] = np.minimum(4, ranks * 5 // len(idx))
            res['candidates'][name] = dict(
                mean_rank_correlation=float(np.mean(rhos)), dates_with_correlation=len(rhos),
                auc_event=auc(vals, events),
                event_rate_by_quintile=[float(events[quint == q].mean()) for q in range(5)])
        report[period] = res
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('archive')
    parser.add_argument('output')
    args = parser.parse_args()
    series, spans, sessions, status = load(args.archive)
    rows, missing = build(series, spans, sessions, status)
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    with (out / 'beobachtungen.csv').open('w', newline='', encoding='utf-8') as stream:
        w = csv.DictWriter(stream, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    report = dict(method='price-block-study-v1', split=SPLIT, lookback_years=LOOKBACK_YEARS, event_threshold=EVENT,
                  observations=len(rows), excluded_member_quarters=missing,
                  horizons={str(n): evaluate(rows, n) for n in HORIZONS},
                  limitations=['Kostenlose Anbieterreihen ohne archivierte Point-in-Time-Version; Identitaeten nur vorlaeufig.',
                               'Fehlende Reihen ausgeschiedener Firmen bleiben ausgeschlossen und sind in excluded_member_quarters gezaehlt.',
                               'Ueberlappende Fenster und gemeinsame Marktereignisse: Beobachtungen nicht unabhaengig, keine Signifikanztests.',
                               'Nur Kursblock; Finanz-, Bewertungs- und Wettbewerbsbloecke sind ohne Point-in-Time-Daten nicht pruefbar.'])
    dev = report['horizons']['63']['development']['candidates']
    report['selection'] = dict(rule=SELECTION_RULE, selected=max(PRICE_BLOCK_VARIANTS, key=lambda k: dev[k]['mean_rank_correlation']))
    (out / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf8')
    print(json.dumps(report, indent=1))


if __name__ == '__main__':
    main()
