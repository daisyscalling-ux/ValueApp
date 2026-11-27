"""SEC-Jahresreihen je Titel fuer die Kennzahlen-Tabelle der App (seit 20.11.2026, Entscheidung des Nutzers).

Aus cf_sec_cashflow_history.json: Jahresumsatz (revenueStocks, sec_revenue_history) und operativer Cashflow minus
Sachinvestitionen (stocks, Konzept PaymentsToAcquirePropertyPlantAndEquipment, us-gaap). Nur Titel des Universums mit
gleicher inputIdentity und CIK, Abruf hoechstens MAX_AGE_DAYS alt. Datei je Notierung unter daten/sec_jahre/, Aeltere Jahre
bleiben erhalten (behalten). Die App verlaengert damit die Umsatzzeile nur bei Uebereinstimmung mit ROIC und zeigt
"Operativer CF - Capex (SEC)" als eigene, gekennzeichnete Zeile. Kein Score nutzt diese Dateien.
"""
import datetime as dt, json, math, os, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

METHOD = 'sec_annual_series_v1'
MAX_AGE_DAYS = 14
PPE = 'PaymentsToAcquirePropertyPlantAndEquipment'


def _zahl(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _datei(sym):
    return re.sub(r'[^A-Za-z0-9._-]', '_', sym) + '.json'


def build(state, universe, now):
    from roic_risk_annual import identity
    from sec_cashflow_history import METHOD as STATE_METHOD
    if state.get('schema') != 1 or state.get('method') != STATE_METHOD:
        return {}
    rows = {}
    for r in universe.get('kandidaten', []):
        if r.get('listing_symbol'):
            rows.setdefault(r['listing_symbol'], []).append(r)
    out = {}
    for s, lst in rows.items():
        if len(lst) != 1:
            continue
        r = lst[0]
        ident = identity(r)
        def gueltig(c):
            try:
                alt = (now - dt.datetime.fromisoformat(c['retrievedAt'])).days
            except (KeyError, TypeError, ValueError):
                return False
            if c.get('inputIdentity') != ident or not 0 <= alt <= MAX_AGE_DAYS:
                return False
            return not r.get('cik') or str(r['cik']).lstrip('0') == str(c.get('cik', '')).lstrip('0')
        rev, cf = state.get('revenueStocks', {}).get(s), state.get('stocks', {}).get(s)
        eb = state.get('ebitdaStocks', {}).get(s)
        umsatz = [{'ende': p['end'], 'start': p['start'], 'wert': p['value'], 'waehrung': p['currency'], 'konzept': p['concept'],
                   'accession': p['accession'], 'sourceUrl': p['sourceUrl']}
                  for p in (rev or {}).get('periods', []) if rev and gueltig(rev) and _zahl(p.get('value')) and p['value'] >= 0]
        ocf = [{'ende': p['end'], 'start': p['start'], 'ocf': p['operatingCashflow'], 'capex': p['cashPpe'],
                'wert': p['operatingCashflow'] - p['cashPpe'], 'waehrung': p['currency'], 'konzept': p['concept'],
                'accession': p['accession'], 'sourceUrl': p['sourceUrl']}
               for p in (cf or {}).get('periods', [])
               if cf and gueltig(cf) and p.get('namespace', 'us-gaap') == 'us-gaap' and p.get('concept') == PPE
               and _zahl(p.get('operatingCashflow')) and _zahl(p.get('cashPpe')) and p['cashPpe'] >= 0]
        # EBITDA = operativer Gewinn + Abschreibungen (seit 27.11.2026, sec_ebitda_history); die App übernimmt nur bei Übereinstimmung mit ROIC.
        ebitda = [{'ende': p['end'], 'start': p['start'], 'wert': p['value'], 'operativ': p['operatingIncome'], 'abschreibungen': p['da'],
                   'waehrung': p['currency'], 'konzept': p['daConcept'], 'accession': p['accession'], 'sourceUrl': p['sourceUrl']}
                  for p in (eb or {}).get('periods', []) if eb and gueltig(eb) and _zahl(p.get('value')) and _zahl(p.get('operatingIncome'))
                  and _zahl(p.get('da')) and p['da'] >= 0]
        if len(umsatz) < 2 and len(ocf) < 2 and len(ebitda) < 2:
            continue
        out[s] = {'schema': 1, 'method': METHOD, 'inputIdentity': ident, 'cik': str((rev or cf or eb)['cik']),
                  'retrievedAt': max(c['retrievedAt'] for c in (rev, cf, eb) if c and gueltig(c)),
                  'umsatz': sorted(umsatz, key=lambda x: x['ende']), 'ocf_capex': sorted(ocf, key=lambda x: x['ende']),
                  'ebitda': sorted(ebitda, key=lambda x: x['ende'])}
    return out


def behalten(neu, alt):
    """Aeltere Jahre aus der bisherigen Datei behalten (seit 21.11.2026): Die SEC-Reihe umfasst nur 8 Jahre, aeltere fielen
    sonst mit jedem neuen Geschaeftsjahr weg. Nur bei gleicher Identitaet und CIK; Umsatz nur bei gleichem Konzept. Behaltene
    Jahre tragen archiviert: true. Dateien von Titeln ohne neue Reihe bleiben unveraendert liegen (nie loeschen)."""
    if not alt or alt.get('method') != METHOD or alt.get('inputIdentity') != neu['inputIdentity'] or str(alt.get('cik')) != str(neu['cik']):
        return neu, 0
    neu, n = dict(neu), 0
    for key in ('umsatz', 'ocf_capex', 'ebitda'):
        if not neu.get(key):
            continue
        erstes = neu[key][0]['ende']
        konzepte = {r.get('konzept') for r in neu[key]}
        vorher = [{**r, 'archiviert': True} for r in alt.get(key, []) if r.get('ende', '') < erstes and r.get('konzept') in konzepte]
        n += len(vorher)
        neu[key] = vorher + neu[key]
    return neu, n


def main():
    folder = Path(os.getenv('RISK_DATA_DIR', str(Path(__file__).resolve().parents[1] / 'daten')))
    try:
        state = json.loads((folder / 'cf_sec_cashflow_history.json').read_text(encoding='utf-8'))
        universe = json.loads((folder / 'cf_universum.json').read_text(encoding='utf-8'))
    except (OSError, ValueError) as e:
        print(f'SEC-Jahresreihen: Eingabe fehlt ({type(e).__name__}), Ordner unveraendert'); return
    out = build(state, universe, dt.datetime.now(dt.timezone.utc))
    ziel = folder / 'sec_jahre'
    ziel.mkdir(parents=True, exist_ok=True)
    gehalten = 0
    for s, d in out.items():
        pfad = ziel / _datei(s)
        try:
            alt = json.loads(pfad.read_text(encoding='utf-8')) if pfad.exists() else None
        except (OSError, ValueError):
            alt = None
        d, n = behalten(d, alt)
        gehalten += n
        pfad.write_text(json.dumps(d, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
    mit_umsatz = sum(1 for d in out.values() if len(d['umsatz']) >= 2)
    print(json.dumps({'titel': len(out), 'aeltere_jahre_behalten': gehalten, 'mit_umsatz': mit_umsatz, 'mit_ocf_capex': sum(1 for d in out.values() if len(d['ocf_capex']) >= 2), 'mit_ebitda': sum(1 for d in out.values() if len(d['ebitda']) >= 2)}))


if __name__ == '__main__':
    main()
