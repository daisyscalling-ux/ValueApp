"""Indexzugehoerigkeit des Export-Universums (S&P 500, NASDAQ-100, STOXX Europe 600, Nikkei 225, DAX).

Befund 10.11.2026: Wikipedia lehnt Abrufe ohne erkennbaren User-Agent ab (HTTP 403). regime.sp500_tickers()
fiel dann still auf den Yahoo-Screener zurueck ("groesste US-gehandelte Titel"). Dadurch fehlten 274 von 503
S&P-500-Mitgliedern, dafuer standen 215 OTC-Linien und rund 70 auslaendische ADRs im Universum.

Regeln:
- S&P 500 aus der Wikipedia-Tabelle "constituents" mit beschreibendem User-Agent (Wikipedia-Richtlinie;
  kein Browser vorgetaeuscht, keine persoenlichen Daten). Nur gueltig bei 480-520 plausiblen Symbolen.
- Sonst die feste Liste sp500_liste.txt (Stand im Kopf, hoechstens MAX_LIST_AGE_DAYS alt).
- Nie ein Screener: ohne gueltige Mitgliederliste bleibt der S&P 500 leer, und der Veroeffentlichungsschutz
  (export_continuity.guard) verhindert dann, dass bestehende Zeilen verschwinden.
- scope() beschreibt Quellen und Mitglieder; guard() erlaubt damit nur das Entfernen von Nicht-Mitgliedern.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import re
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

METHOD = 'index-members-v1'
SP500_URL = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
USER_AGENT = 'value-radar/1.0 (index membership list)'
SP500_RANGE = (480, 520)
# Mindestgroesse je Index, damit eine Liste als vollstaendig gilt (Schutz gegen abgeschnittene Quellen).
MIN_MEMBERS = {'SP500': 480, 'NDX': 95, 'STOXX600': 590, 'NIKKEI225': 220, 'DAX': 40}
MAX_LIST_AGE_DAYS = 120
SYMBOL = re.compile(r'^[A-Z][A-Z0-9]{0,5}(-[A-Z])?$')
HERE = Path(__file__).resolve().parent


def normalize_us(symbol) -> str:
    """Wikipedia schreibt BRK.B, Yahoo/Export BRK-B."""
    return str(symbol or '').strip().upper().replace('.', '-')


class _ConstituentsTable(HTMLParser):
    """Erste Spalte (Symbol) der Tabelle id="constituents"; nur Standardbibliothek."""

    def __init__(self):
        super().__init__()
        self.depth = 0          # Tabellentiefe innerhalb der Zieltabelle
        self.header = []
        self.rows = []
        self.cell = None
        self.row = None

    def handle_starttag(self, tag, attrs):
        if tag == 'table':
            if self.depth or dict(attrs).get('id') == 'constituents':
                self.depth += 1
        elif self.depth == 1 and tag == 'tr':
            self.row = []
        elif self.depth == 1 and tag in ('td', 'th') and self.row is not None:
            self.cell = []

    def handle_endtag(self, tag):
        if tag == 'table' and self.depth:
            self.depth -= 1
        elif self.depth == 1 and tag in ('td', 'th') and self.cell is not None:
            self.row.append(''.join(self.cell).strip())
            self.cell = None
        elif self.depth == 1 and tag == 'tr' and self.row is not None:
            if not self.header:
                self.header = self.row
            elif self.row:
                self.rows.append(self.row)
            self.row = None

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)


def parse_sp500(html: str) -> list:
    """Symbole aus der Tabelle id="constituents"; leer, wenn die Tabelle fehlt oder unplausibel ist."""
    p = _ConstituentsTable()
    p.feed(html)
    if not p.header or p.header[0] != 'Symbol':
        return []
    out = list(dict.fromkeys(normalize_us(r[0]) for r in p.rows if r))
    return out if valid_sp500(out) else []


def valid_sp500(symbols) -> bool:
    return SP500_RANGE[0] <= len(symbols) <= SP500_RANGE[1] and all(SYMBOL.match(s) for s in symbols)


def read_fixed_list(path: Path, today: dt.date):
    """Feste Liste: '# Stand: JJJJ-MM-TT' im Kopf, ein Symbol je Zeile. (Liste, Stand) oder ([], Grund)."""
    try:
        text = path.read_text(encoding='utf-8')
    except OSError:
        return [], 'fixed_list_missing'
    m = re.search(r'^#\s*Stand:\s*(\d{4}-\d{2}-\d{2})', text, re.M)
    if not m:
        return [], 'fixed_list_undated'
    stand = dt.date.fromisoformat(m.group(1))
    if not 0 <= (today - stand).days <= MAX_LIST_AGE_DAYS:
        return [], 'fixed_list_stale'
    symbols = list(dict.fromkeys(normalize_us(z.split('#')[0]) for z in text.splitlines() if z.split('#')[0].strip()))
    return (symbols, stand.isoformat()) if valid_sp500(symbols) else ([], 'fixed_list_invalid')


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def sp500_members(fetcher=fetch, fixed_path: Path = HERE / 'sp500_liste.txt', now=None):
    """(Symbole, Quelle). Wikipedia zuerst, dann die feste Liste; nie ein Screener."""
    now = now or dt.datetime.now(dt.timezone.utc)
    reason = ''
    try:
        raw = fetcher(SP500_URL)
        symbols = parse_sp500(raw.decode('utf-8', 'replace'))
        if symbols:
            return symbols, {'kind': 'wikipedia', 'url': SP500_URL, 'retrievedAt': now.isoformat(),
                             'sha256': hashlib.sha256(raw).hexdigest(), 'count': len(symbols)}
        reason = 'wikipedia_table_invalid'
    except Exception as e:  # Netz- oder HTTP-Fehler: Grund festhalten, feste Liste versuchen
        reason = 'wikipedia_' + (str(getattr(e, 'code', '')) or type(e).__name__)
    symbols, stand = read_fixed_list(fixed_path, now.date())
    if symbols:
        return symbols, {'kind': 'fixed_list', 'file': fixed_path.name, 'stand': stand, 'count': len(symbols), 'wikipediaFailure': reason}
    return [], {'kind': 'unavailable', 'count': 0, 'wikipediaFailure': reason, 'fixedListProblem': stand}


def scope(members: dict, sources: dict, now=None) -> dict:
    """Mitgliedschaft je Ticker und Quellen; members: Index -> Tickerliste (Export-Schreibweise)."""
    now = now or dt.datetime.now(dt.timezone.utc)
    by_ticker = {}
    for index, tickers in members.items():
        for t in tickers:
            by_ticker.setdefault(t, [])
            if index not in by_ticker[t]:
                by_ticker[t].append(index)
    counts = {k: len(set(v)) for k, v in members.items()}
    return {'method': METHOD, 'generatedAt': now.isoformat(), 'counts': counts, 'sources': sources,
            'complete': all(counts.get(k, 0) >= n for k, n in MIN_MEMBERS.items()), 'members': by_ticker}


def scope_complete(doc) -> bool:
    """Gueltige, vollstaendige Indexbeschreibung eines Exports (fuer den Veroeffentlichungsschutz)."""
    s = (doc or {}).get('index_scope') or {}
    counts = s.get('counts') or {}
    return (s.get('method') == METHOD and s.get('complete') is True and isinstance(s.get('members'), dict)
            and all(isinstance(counts.get(k), int) and counts[k] >= n for k, n in MIN_MEMBERS.items()))


# Boersensuffix -> Land. Ein Ticker ohne Suffix ist eine US-Notierung.
SUFFIX_COUNTRY = {'': 'US', 'DE': 'DE', 'F': 'DE', 'MU': 'DE', 'BE': 'DE', 'SG': 'DE', 'DU': 'DE', 'HM': 'DE', 'HA': 'DE', 'STU': 'DE',
                  'L': 'GB', 'IL': 'GB', 'XC': 'GB', 'PA': 'FR', 'AS': 'NL', 'BR': 'BE', 'MI': 'IT', 'MC': 'ES', 'SW': 'CH', 'VX': 'CH',
                  'ST': 'SE', 'HE': 'FI', 'OL': 'NO', 'CO': 'DK', 'VI': 'AT', 'LS': 'PT', 'IR': 'IE', 'WA': 'PL', 'AT': 'GR', 'T': 'JP'}


def collapse_same_market(tickers, priority):
    """Doppelnotierungen nur innerhalb desselben Landes zusammenfassen (AMZ.DE/AMZ.F, BHP.L/BHPL.XC).

    Ersetzt im Export precompute.collapse_listings, das nach Basissymbol ueber alle Boersen hinweg
    zusammenfasste: Ein US-Ticker ohne Suffix verdraengte dadurch gleichnamige Indexwerte anderer Firmen
    (DTE vs. DTE.DE, MRK vs. MRK.DE, AIR vs. AIR.PA). priority: Suffix -> Rang (kleiner = bevorzugt)."""
    out, pos = [], {}
    def key(t):
        base, _, suf = t.partition('.')
        suf = suf.upper()
        if suf in ('XC', 'IL') and len(base) > 2 and base.endswith('L'):
            base = base[:-1]
        return (base.upper(), SUFFIX_COUNTRY.get(suf, suf)), priority.get(suf, 0 if not suf else 50)
    for t in tickers:
        k, pri = key(t)
        if k not in pos:
            pos[k] = len(out)
            out.append(t)
        elif pri < key(out[pos[k]])[1]:
            out[pos[k]] = t
    return out
