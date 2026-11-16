"""Pruefristen auf einen Blick (seit 16.11.2026): wann gepruefte Zuordnungen und datierte Aufsichtskennzahlen ablaufen.

Liest nur Dateien, ruft nichts ab. Zwei Arten von Fristen:
- ausdrueckliche Pruefdaten in kuratierten Dateien (reviewExpires, review_expires, mappingReviewExpires);
- abgeleitete Fristen aus dem Stichtag: internationale Bankkennzahlen und Kreditqualitaet (CR1) gelten
  INTL_CREDIT_MAX_AGE_DAYS = 270 Tage nach Stichtag (regulatory_context.py).
Aufruf: python review_deadlines.py [Tage, Standard 60] -> Markdown-Tabelle der Fristen innerhalb dieses Fensters.
"""
import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAX_AGE_DAYS = 270   # wie INTL_CREDIT_MAX_AGE_DAYS / KM1_MAX_AGE_DAYS in regulatory_context.py
KEYS = ('reviewExpires', 'review_expires', 'mappingReviewExpires')
CURATED = ['regulatory_export/*.json', 'daten/regulatory/*.json', 'risk_precompute/reviewed-*.json', 'daten/universum_zusatz.json']


def _date(v):
    try:
        return dt.date.fromisoformat(str(v)[:10])
    except ValueError:
        return None


def explicit(doc, source):
    """Alle ausdruecklichen Pruefdaten mit Pfad und naechstem Namen (Emittent, Symbol)."""
    out = []

    def walk(x, path, label):
        if isinstance(x, dict):
            label = x.get('issuer') or x.get('holdingName') or x.get('symbol') or x.get('listing_symbol') or x.get('name') or label
            for k in KEYS:
                d = _date(x.get(k)) if x.get(k) else None
                if d:
                    out.append({'expires': d, 'source': source, 'what': f'{label or path or source} ({k})', 'kind': 'Prüfdatum'})
            for k, v in x.items():
                walk(v, f'{path}/{k}', label)
        elif isinstance(x, list):
            for i, v in enumerate(x):
                walk(v, f'{path}[{i}]', label)
    walk(doc, '', None)
    return out


def derived(intl, source='daten/regulatory/intl-bank-metrics.json'):
    """Stichtag + 270 Tage fuer Kennzahlen (period) und Kreditqualitaet (creditPeriod) internationaler Banken."""
    out = []
    for isin, v in (intl.get('issuers') or {}).items():
        name = v.get('issuer') or isin
        for key, what in (('period', 'Kapital/LCR'), ('creditPeriod', 'Kreditqualität (CR1)')):
            d = _date(v.get(key)) if v.get(key) else None
            if d:
                out.append({'expires': d + dt.timedelta(days=MAX_AGE_DAYS), 'source': source, 'what': f'{name}: {what}, Stichtag {d}', 'kind': 'Stichtag + 270 Tage'})
    return out


def collect(root=ROOT):
    items = []
    for pattern in CURATED:
        for f in sorted(root.glob(pattern)):
            try:
                doc = json.loads(f.read_text(encoding='utf-8'))
            except (OSError, ValueError):
                continue
            rel = str(f.relative_to(root))
            items += explicit(doc, rel)
            if f.name == 'intl-bank-metrics.json':
                items += derived(doc, rel)
    return sorted(items, key=lambda x: (x['expires'], x['what']))


def due(items, today, days):
    return [x for x in items if x['expires'] <= today + dt.timedelta(days=days)]


def markdown(items, today):
    rows = ['| Ablauf | in Tagen | Was | Art | Datei |', '|---|---:|---|---|---|']
    for x in items:
        rows.append(f"| {x['expires']} | {(x['expires'] - today).days} | {x['what']} | {x['kind']} | `{x['source']}` |")
    return '\n'.join(rows)


if __name__ == '__main__':
    today = dt.datetime.now(dt.timezone.utc).date()
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    print(markdown(due(collect(), today, days), today))
