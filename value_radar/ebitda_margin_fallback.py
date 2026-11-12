"""EBITDA-Marge aus dem eigenen Jahresabschluss, wenn ROIC keine TTM-Marge liefert (12.11.2026, Entscheidung des Nutzers).

Befund: Nach dem Geschaeftsjahreswechsel (z. B. 30.09.) liefert ROIC das TTM-EBITDA voruebergehend nicht; die
Universumsmarge fehlte dadurch bei rund 19 Indexwerten (Emerson, Kraft Heinz, Skyworks, FactSet ...) und mittelbar
bei deren Peers (Nestle, ABF). Ersatz nur gekennzeichnet:
- nur wenn die ROIC-Marge fehlt; eine vorhandene ROIC-Marge wird nie ueberschrieben,
- Zeile mit listing_symbol; Jahresabschluss derselben Notierung (Datei-Symbol = listing_symbol oder ticker), Periodentyp annual,
  Stichtag hoechstens 460 Tage alt, Umsatz > 0, EBITDA endlich, |Marge| <= 100 %,
- EBITDA und Umsatz aus demselben Abschluss (gleiche Periode und Waehrung; die Waehrung kuerzt sich),
- Feld ebitda_margin_source mit Methode, Stichtag, Quelle; App und Messung zeigen den Hinweis.
"""
from __future__ import annotations

import datetime as dt
import json
import math
from pathlib import Path

METHOD = 'annual_statement_ebitda_over_revenue_v1'
MAX_AGE_DAYS = 460


def _num(v):
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) else None


def _load(folder: Path, row: dict):
    # Ohne eindeutige Notierung kein Ersatz (Identitaet vor Inhalt).
    if not row.get('listing_symbol'):
        return None
    for key in (row.get('listing_symbol'), row.get('ticker')):
        if not key:
            continue
        path = folder / (str(key).replace(':', '_') + '.json')
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            continue
        if data.get('symbol') in (row.get('listing_symbol'), row.get('ticker')):
            return data
    return None


def annual_margin(row: dict, folder: Path, today: dt.date):
    """(Marge in Prozent, Herkunft) oder (None, Grund)."""
    data = _load(folder, row)
    a = (data or {}).get('annual') or {}
    if not a:
        return None, 'no_annual_statement'
    try:
        end = dt.date.fromisoformat(str(a.get('end'))[:10])
    except ValueError:
        return None, 'annual_end_invalid'
    if a.get('period_type') != 'annual' or not 0 <= (today - end).days <= MAX_AGE_DAYS:
        return None, 'annual_stale_or_not_annual'
    f = a.get('fields') or {}
    ebitda, revenue = _num(f.get('ebitda')), _num(f.get('revenue'))
    if ebitda is None or revenue is None or revenue <= 0:
        return None, 'ebitda_or_revenue_missing'
    margin = ebitda / revenue
    if abs(margin) > 1:
        return None, 'margin_out_of_range'
    return round(margin * 100, 1), {'method': METHOD, 'end': str(end), 'source': a.get('source'), 'currency': a.get('currency')}


def apply(rows, folder: Path, today: dt.date | None = None):
    """Fuellt fehlende ebitda_margin gekennzeichnet; gibt die Anzahl gefuellter Zeilen zurueck."""
    today = today or dt.datetime.now(dt.timezone.utc).date()
    filled = 0
    for row in rows:
        if _num(row.get('ebitda_margin')) is not None:
            row.pop('ebitda_margin_source', None)
            continue
        margin, origin = annual_margin(row, folder, today)
        if margin is not None:
            row['ebitda_margin'] = margin
            row['ebitda_margin_source'] = origin
            filled += 1
    return filled
