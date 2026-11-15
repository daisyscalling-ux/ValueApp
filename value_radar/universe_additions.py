"""Zusatztitel des Universums (seit 15.11.2026): vom Nutzer benannte Titel ausserhalb der Indizes.

Gepflegt in daten/universum_zusatz.json. Jeder Eintrag bindet einen Export-Ticker an eine Notierung
(listing_symbol, isin, currency, security_type) und traegt Grund, Aufnahme- und Pruefdatum mit Ablauf.
- Abgelaufene oder fehlerhafte Eintraege werden nicht aufgenommen (Grund in problems).
- Im Export wird die Identitaet gegen die ROIC-Aufloesung geprueft (check_row): weicht Notierung, ISIN oder
  Waehrung ab, wird die Zeile verworfen (identity_rejected), nicht angepasst.
- Zusatztitel zaehlen wie Indexwerte als Peers und in den Raengen (Entscheidung des Nutzers); sie tragen
  index_membership ["ZUSATZ"] und universe_addition mit Grund und Pruefdatum.
"""
import datetime as dt
import json
import re
from pathlib import Path

METHOD = 'curated-additions-v1'
INDEX = 'ZUSATZ'
PATH = Path(__file__).resolve().parent / 'daten' / 'universum_zusatz.json'
TICKER = re.compile(r'^[A-Z0-9][A-Z0-9.\-]{0,13}$')
LISTING = re.compile(r'^[A-Z]+:[A-Z0-9._\-]+$')
ISIN = re.compile(r'^[A-Z]{2}[A-Z0-9]{9}[0-9]$')
REQUIRED = ('ticker', 'listing_symbol', 'isin', 'currency', 'security_type', 'name', 'reason',
            'added_on', 'reviewed_on', 'review_expires')


def isin_valid(isin: str) -> bool:
    """ISIN mit Pruefziffer (Luhn ueber die Ziffernfolge, Buchstaben als 10-35)."""
    if not isinstance(isin, str) or not ISIN.match(isin):
        return False
    digits = ''.join(str(int(c, 36)) for c in isin[:-1])
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2 == 0:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return (10 - total % 10) % 10 == int(isin[-1])


def load(path: Path = PATH, today: dt.date = None):
    """({ticker: eintrag}, [probleme]). Fehlt die Datei, ist die Liste leer (kein Fehler)."""
    today = today or dt.datetime.now(dt.timezone.utc).date()
    try:
        doc = json.loads(Path(path).read_text(encoding='utf-8'))
    except FileNotFoundError:
        return {}, []
    except (OSError, ValueError) as e:
        return {}, [f'datei_unlesbar: {type(e).__name__}']
    if doc.get('schema') != 1 or doc.get('method') != METHOD:
        return {}, ['schema_oder_methode_falsch']
    out, problems = {}, []
    for e in doc.get('titles') or []:
        t = (e or {}).get('ticker')
        fehlt = [k for k in REQUIRED if not (e or {}).get(k)]
        if fehlt:
            problems.append(f'{t}: felder_fehlen {",".join(fehlt)}'); continue
        if not TICKER.match(t) or not LISTING.match(e['listing_symbol']):
            problems.append(f'{t}: symbol_ungueltig'); continue
        if not isin_valid(e['isin']):
            problems.append(f'{t}: isin_pruefziffer'); continue
        try:
            reviewed, expires = dt.date.fromisoformat(e['reviewed_on']), dt.date.fromisoformat(e['review_expires'])
        except ValueError:
            problems.append(f'{t}: datum_ungueltig'); continue
        if reviewed > today:
            problems.append(f'{t}: pruefung_in_zukunft'); continue
        if today >= expires:
            problems.append(f'{t}: pruefung_abgelaufen {e["review_expires"]}'); continue
        if t in out:
            problems.append(f'{t}: doppelt'); continue
        out[t] = e
    return out, problems


def check_row(row: dict, entry: dict):
    """None bei passender Identitaet, sonst Grund. Verglichen werden Notierung, ISIN und Waehrung der Exportzeile."""
    for key in ('listing_symbol', 'isin', 'currency'):
        if row.get(key) != entry.get(key):
            return f'curated_addition_mismatch:{key}'
    return None


def mark(row: dict, entry: dict) -> dict:
    row['universe_addition'] = {'method': METHOD, 'reason': entry['reason'], 'added_on': entry['added_on'],
                                'reviewed_on': entry['reviewed_on'], 'review_expires': entry['review_expires']}
    return row
