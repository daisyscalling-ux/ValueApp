"""Dauerhaftes Archiv der ROIC-Jahreswerte (seit 21.11.2026, Wunsch des Nutzers).

ROIC liefert je Titel hoechstens 5 Geschaeftsjahre (Messung roic-jahre, 20.11.2026). Mit jedem neuen Geschaeftsjahr faellt das
aelteste aus dem Fenster. Dieses Archiv haelt jedes einmal gelieferte Jahr fest, damit die Kennzahlen-Tabelle der App es weiter
zeigen kann. Quelle sind die Rohbloecke, die precompute ohnehin je Titel holt (roic.rohbloecke, enterprise_value).

Regeln:
- Datei je Notierung daten/roic_archiv/<listing_symbol, bereinigt>.json mit inputIdentity (Notierung, ISIN, Waehrung).
- Nur Jahreszeilen (period_type annual) mit Stichtag; je Stichtag ein Eintrag.
- Es wird nie geloescht. Liefert ROIC fuer einen Stichtag spaeter andere Werte (Anpassung), gilt der neue Wert; der alte bleibt
  mit Datum unter "frueher" erhalten.
- Passt die Identitaet nicht (andere ISIN oder Waehrung), wird nichts eingetragen und gezaehlt.
- Waehrung je Zeile wie von ROIC geliefert (Berichtswaehrung); keine Umrechnung.
"""
import datetime as dt
import json
import re
from pathlib import Path

METHODE = 'roic_annual_archive_v1'
ROH_METHODE = 'roic_raw_blocks_v1'
FELDER = ('ttm_net_sales', 'ttm_ebitda', 'ttm_free_cash_flow_firm', 'ttm_net_income', 'ttm_ebit')
ORDNER = Path(__file__).resolve().parent / 'daten' / 'roic_archiv'


def dateiname(sym):
    return re.sub(r'[^A-Za-z0-9._-]', '_', sym) + '.json'


def _zahl(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v == v and abs(v) != float('inf')


def _zeilen(d):
    if isinstance(d, list):
        return d
    if isinstance(d, dict):
        return d.get('data') if isinstance(d.get('data'), list) else [d]
    return []


def jahre_aus_roh(roh):
    """Rohbloecke -> {stichtag: eintrag} aus enterprise_value (nur Jahreszeilen mit Stichtag)."""
    out = {}
    for z in _zeilen((roh or {}).get('enterprise_value')):
        if not isinstance(z, dict):
            continue
        ende = str(z.get('period_end_date') or '')[:10]
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', ende) or str(z.get('period_type') or 'annual') != 'annual':
            continue
        werte = {k: z[k] for k in FELDER if _zahl(z.get(k))}
        if not werte:
            continue
        out[ende] = {'fiscal_year': z.get('fiscal_year') if isinstance(z.get('fiscal_year'), int) else None,
                     'waehrung': z.get('currency') if isinstance(z.get('currency'), str) else None, 'werte': werte}
    return out


def einarbeiten(rows, ordner=ORDNER, heute=None):
    """Frisch gescannte Zeilen (mit _ts_input._roic_raw) ins Archiv uebernehmen. Rueckgabe: Zaehler."""
    heute = heute or dt.datetime.now(dt.timezone.utc).date().isoformat()
    z = {'titel': 0, 'neue_jahre': 0, 'angepasst': 0, 'identitaet_abweichend': 0, 'ohne_bloecke': 0}
    ordner.mkdir(parents=True, exist_ok=True)
    for r in rows:
        sym = r.get('listing_symbol')
        roh = ((r.get('_ts_input') or {}).get('_roic_raw')) if isinstance(r.get('_ts_input'), dict) else None
        if not isinstance(sym, str) or not isinstance(roh, dict):
            continue
        if roh.get('method') != ROH_METHODE or roh.get('symbol') != sym:
            z['ohne_bloecke'] += 1
            continue
        neu = jahre_aus_roh(roh)
        if not neu:
            z['ohne_bloecke'] += 1
            continue
        pfad = ordner / dateiname(sym)
        ident = {'listing_symbol': sym, 'isin': r.get('isin'), 'currency': r.get('currency')}
        doc = json.loads(pfad.read_text(encoding='utf-8')) if pfad.exists() else {
            'schema': 1, 'method': METHODE, 'inputIdentity': ident, 'quelle': 'ROIC enterprise-value (Jahreszeilen)', 'jahre': {}}
        alt = doc.get('inputIdentity') or {}
        if alt.get('isin') and ident['isin'] and alt['isin'] != ident['isin'] or alt.get('currency') and ident['currency'] and alt['currency'] != ident['currency']:
            z['identitaet_abweichend'] += 1
            continue
        z['titel'] += 1
        for ende, e in neu.items():
            vorher = doc['jahre'].get(ende)
            if vorher is None:
                doc['jahre'][ende] = {**e, 'erstmals': heute, 'zuletzt': heute}
                z['neue_jahre'] += 1
            elif vorher.get('werte') != e['werte'] or vorher.get('waehrung') != e['waehrung']:
                frueher = vorher.get('frueher', []) + [{'werte': vorher.get('werte'), 'waehrung': vorher.get('waehrung'), 'bis': heute}]
                doc['jahre'][ende] = {**e, 'erstmals': vorher.get('erstmals', heute), 'zuletzt': heute, 'frueher': frueher}
                z['angepasst'] += 1
            else:
                vorher['zuletzt'] = heute
        doc['jahre'] = dict(sorted(doc['jahre'].items()))
        doc['aktualisiert'] = heute
        pfad.write_text(json.dumps(doc, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
    return z
