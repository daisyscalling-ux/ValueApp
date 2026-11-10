"""Umtauschverhaeltnis von Depositary Receipts aus zwei unabhaengigen Wegen.

1. Aktienzahl: Stammaktien der Heimatnotierung / ADR-Einheiten (beide aus dem Kursabruf).
2. Kurs: ADR-Kurs / (Heimatkurs umgerechnet zum EZB-Referenzkurs).
Uebernommen wird ein Standardverhaeltnis nur, wenn die Aktienzahl es auf 2 % und der Kurs auf 10 %
trifft (OTC-Kurse sind manchmal einige Tage alt). Die Heimatnotierung ist die Stammaktie mit derselben
ISIN im Universum (keine OTC-Notierung). Manuelle Eintraege in share_basis.json haben Vorrang.
Laeuft nach dem Abschluss-Export und schreibt share_basis in die DR-Dateien.
"""
import datetime as dt
import json
import math
import pathlib
import sys
from collections import defaultdict

METHOD = 'share_count_and_price_ratio_v1'


def save(path, data):
    """Gleiches Format wie export_fundamentals.save (kompakt, atomar)."""
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, allow_nan=False), encoding='utf-8')
    tmp.replace(path)
STANDARD = [0.01, 0.02, 0.04, 0.05, 0.1, 0.2, 0.25, 1 / 3, 0.5, 1, 2, 3, 4, 5, 6, 8, 10, 12, 15, 16, 20, 25, 30, 40, 50, 100]
SHARE_TOLERANCE, PRICE_TOLERANCE, REFRESH_DAYS = .02, .10, 90


def positive(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) and x > 0


def market(d):
    m = (d or {}).get('market') or {}
    f = m.get('fields') or {}
    price, currency = f.get('price'), m.get('currency')
    if currency == 'GBp' and positive(price):
        price, currency = price / 100, 'GBP'
    return price, currency, f.get('shares_out'), m.get('quote_at')


def adr_basis(dr_row, dr_file, home_row, home_file, today):
    """Liefert einen share_basis-Eintrag oder (None, Grund)."""
    annual = (dr_file or {}).get('annual') or {}
    rates = ((dr_file or {}).get('fx') or {}).get('rates') or {}
    pa, ca, sa, qa = market(dr_file)
    ph, ch, sh, qh = market(home_file)
    if not annual.get('currency'):
        return None, 'annual_currency_missing'
    if not all(positive(x) for x in (pa, ph, sa, sh)) or not positive(rates.get(ca)) or not positive(rates.get(ch)):
        return None, 'price_shares_or_fx_missing'
    by_shares, by_price = sh / sa, pa / (ph * rates[ca] / rates[ch])
    ratio = min(STANDARD, key=lambda r: abs(math.log(by_shares / r)))
    if abs(by_shares / ratio - 1) > SHARE_TOLERANCE:
        return None, 'share_count_not_standard_ratio'
    if abs(by_price / ratio - 1) > PRICE_TOLERANCE:
        return None, 'price_disagrees_with_share_count'
    ratio = round(ratio, 6)
    entry = {'symbol': dr_row['listing_symbol'], 'kind': 'ADR', 'ordinary_shares_per_unit': ratio, 'report_currency': annual['currency'],
             'quote_currency': ((dr_file.get('market') or {}).get('currency')), 'annual_eps_basis': 'ordinary', 'reviewed_at': today.isoformat(),
             'source_url': (dr_file.get('market') or {}).get('source_url'), 'method': METHOD,
             'evidence': {'homeListing': home_row['listing_symbol'], 'byShareCount': round(by_shares, 4), 'byPrice': round(by_price, 4),
                          'drQuoteAt': qa, 'homeQuoteAt': qh, 'fxObservedAt': (dr_file.get('fx') or {}).get('observed_at')}}
    if not str(entry['source_url'] or '').startswith('https://'):
        return None, 'source_url_missing'
    return entry, ''


def outside_home(outside, isin, today):
    """Heimatnotierung ausserhalb des Universums (adr_home_quotes.py): nur mit frischem Kurs (hoechstens 7 Tage)."""
    h = ((outside or {}).get('homes') or {}).get(isin) or {}
    m = h.get('market') or {}
    try:
        age = (today - dt.date.fromisoformat(str(m.get('quote_at'))[:10])).days
    except ValueError:
        return None, None
    if (outside or {}).get('method') != 'roic_isin_primary_yahoo_quote_v1' or not h.get('roicSymbol') or not 0 <= age <= 7:
        return None, None
    return {'listing_symbol': h['roicSymbol'], 'yahoo_symbol': h.get('yahooSymbol'), 'outside_universe': True}, {'market': m}


def apply(folder, universe, manual, today=None, outside=None):
    today = today or dt.datetime.now(dt.timezone.utc).date()
    folder = pathlib.Path(folder)
    rows = universe.get('kandidaten', [])
    homes = defaultdict(list)
    for r in rows:
        if r.get('security_type') == 'stock' and r.get('listing_symbol') and not r['listing_symbol'].startswith('OTC:'):
            homes[r.get('isin')].append(r)
    load = lambda s: json.loads((folder / (s.replace(':', '_') + '.json')).read_text(encoding='utf-8')) if (folder / (s.replace(':', '_') + '.json')).exists() else None
    report = defaultdict(int)
    for r in rows:
        s = r.get('listing_symbol')
        if r.get('security_type') != 'dr' or not s or s in manual:
            continue
        d = load(s)
        home = sorted(homes.get(r.get('isin'), []), key=lambda h: h['listing_symbol'])
        if not d:
            report['dr_file_missing'] += 1
            continue
        if home:
            home_row, home_file = home[0], load(home[0]['listing_symbol'])
        else:
            home_row, home_file = outside_home(outside, r.get('isin'), today)
            if not home_row:
                report['home_listing_missing'] += 1
                if (d.get('share_basis') or {}).get('method') == METHOD:
                    d.pop('share_basis')   # Heimatkurs nicht mehr verfuegbar: abgeleiteten Wert nicht weiterfuehren
                    save(folder / (s.replace(':', '_') + '.json'), d)
                continue
        entry, reason = adr_basis(r, d, home_row, home_file, today)
        if entry and home_row.get('outside_universe'):
            entry['evidence'].update(homeOutsideUniverse=True, homeYahooSymbol=home_row.get('yahoo_symbol'), homeSource='adr_home_quotes.py (ROIC ISIN, Yahoo Kurs)')
        old = d.get('share_basis')
        if not entry:
            report[reason] += 1
            if old and old.get('method') == METHOD:
                d.pop('share_basis')   # nicht mehr bestaetigt: nie einen alten Wert weiterfuehren
                save(folder / (s.replace(':', '_') + '.json'), d)
            continue
        report['ratio_set'] += 1
        same = old and old.get('method') == METHOD and old.get('ordinary_shares_per_unit') == entry['ordinary_shares_per_unit'] and old.get('report_currency') == entry['report_currency']
        if same and (today - dt.date.fromisoformat(old['reviewed_at'])).days < REFRESH_DAYS:
            continue   # unveraendert bestaetigt; Datum erst nach 90 Tagen erneuern (weniger Commits)
        d['share_basis'] = entry
        save(folder / (s.replace(':', '_') + '.json'), d)
    return dict(report)


def main(base='.'):
    base = pathlib.Path(base)
    universe = json.loads((base / 'daten' / 'cf_universum.json').read_text(encoding='utf-8'))
    manual_path = base / 'fundamental_export' / 'share_basis.json'
    manual = json.loads(manual_path.read_text(encoding='utf-8')) if manual_path.exists() else {}
    homes_path = base / 'daten' / 'fundamentals' / 'adr_homes.json'
    outside = json.loads(homes_path.read_text(encoding='utf-8')) if homes_path.exists() else None
    print(json.dumps(apply(base / 'daten' / 'fundamentals', universe, manual, outside=outside)))


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else '.')
