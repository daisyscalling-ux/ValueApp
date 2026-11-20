"""Messung (20.11.2026): Wie viele Geschaeftsjahre liefert ROIC je Titel?

Die App fragt Gewinn- und Cashflow-Rechnung mit limit=3 ab und zeigt aus dem EV-Block (ohne Parameter, 5 Zeilen) nur die
letzten 3 Jahre. Diese Messung fragt fuer eine Stichprobe des Universums (je Region gleich viele Titel) die Bloecke mit
limit=LIMIT ab und zaehlt: Zeilen, aelteste und juengste Periode, Luecken in der Jahresfolge, Jahre mit Umsatz, EBITDA
und Free Cashflow. Schreibt nur die Messung (Artefakt), nichts ins Repo, keine Schluessel.
"""
import json, os, sys, collections, datetime as dt
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import roic

LIMIT = 30
BLOECKE = {
    'enterprise_value': ('fundamental/enterprise-value/{s}', {'period_type': 'annual', 'limit': LIMIT}),
    'enterprise_value_ohne': ('fundamental/enterprise-value/{s}', None),
    'income': ('fundamental/income-statement/{s}', {'period_type': 'annual', 'limit': LIMIT}),
    'cashflow': ('fundamental/cash-flow/{s}', {'period_type': 'annual', 'limit': LIMIT}),
}
FELDER = {'enterprise_value': ('ttm_net_sales', 'ttm_ebitda', 'ttm_free_cashflow_firm'), 'income': ('is_sales_revenue_turnover', 'revenue', 'net_income'),
          'cashflow': ('cf_free_cash_flow', 'free_cash_flow')}


def zeilen(d):
    return d if isinstance(d, list) else (d.get('data') if isinstance(d, dict) and isinstance(d.get('data'), list) else ([d] if isinstance(d, dict) and d else []))


def jahr(z):
    for k in ('fiscal_year',):
        if isinstance(z.get(k), int):
            return z[k]
    e = str(z.get('period_end_date') or z.get('date') or '')
    return int(e[:4]) if e[:4].isdigit() else None


def form(rows, felder=()):
    jahre = sorted({j for j in (jahr(z) for z in rows) if j})
    luecken = [j for j in range(jahre[0], jahre[-1] + 1) if j not in jahre] if jahre else []
    return {'zeilen': len(rows), 'jahre': len(jahre), 'von': jahre[0] if jahre else None, 'bis': jahre[-1] if jahre else None, 'luecken': luecken,
            'perioden': sorted({str(z.get('period_type') or z.get('period_label') or '') for z in rows}),
            'felder_mit_wert': {f: sum(1 for z in rows if isinstance(z.get(f), (int, float))) for f in felder if any(f in z for z in rows)},
            'schluessel': sorted(k for k in (rows[0].keys() if rows else []) if any(x in k for x in ('year', 'period', 'date', 'fiscal')))}


def stichprobe(uni, n):
    reg = collections.defaultdict(list)
    for r in uni['kandidaten']:
        if r.get('listing_symbol'):
            reg[r.get('country') if r.get('country') in ('US', 'JP', 'GB') else 'EU'].append(r)
    je = max(1, n // len(reg))
    out = []
    for k in sorted(reg):
        rows = sorted(reg[k], key=lambda r: r['listing_symbol'])
        schritt = max(1, len(rows) // je)
        out += rows[::schritt][:je]
    return out


def main():
    uni_pfad, aus, n = sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 40
    if not roic._key():
        print('ROIC_API_KEY fehlt'); return 1
    uni = json.loads(Path(uni_pfad).read_text(encoding='utf-8'))
    ergebnis = []
    for r in stichprobe(uni, n):
        s = r['listing_symbol']
        z = {'symbol': s, 'land': r.get('country')}
        for name, (pfad, params) in BLOECKE.items():
            d = roic._get(pfad.format(s=s), params)
            z[name] = form(zeilen(d), FELDER.get(name.replace('_ohne', ''), ())) if d is not None else {'fehler': 'keine Antwort'}
        ergebnis.append(z)
    zus = {}
    for name in BLOECKE:
        werte = [z[name] for z in ergebnis if 'jahre' in z[name]]
        zus[name] = {'titel': len(werte), 'jahre_verteilung': dict(sorted(collections.Counter(w['jahre'] for w in werte).items())),
                     'aeltestes_jahr_median': sorted(w['von'] for w in werte if w['von'])[len(werte) // 2] if werte else None,
                     'mit_luecken': sum(1 for w in werte if w['luecken']), 'perioden': dict(collections.Counter(p for w in werte for p in w['perioden']))}
    bericht = {'schema': 1, 'method': 'roic_years_probe_v1', 'erstellt': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
               'limit': LIMIT, 'stichprobe': len(ergebnis), 'zusammenfassung': zus, 'titel': ergebnis}
    Path(aus).write_text(json.dumps(bericht, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps({'stichprobe': len(ergebnis), 'zusammenfassung': zus}, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    sys.exit(main())
