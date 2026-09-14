#!/usr/bin/env python3
"""
roic_felder.py - Zeigt die ECHTEN Feldnamen aller roic-Endpunkte.

Ich habe die Namen bisher geraten. 'revenue' und 'operating_margin' kamen
leer zurueck, also heissen sie dort anders. Dieses Skript listet, was
tatsaechlich geliefert wird - danach ist die Zuordnung exakt statt geraten.

AUFRUF:
    $env:ROIC_API_KEY="dein_key"
    python roic_felder.py            > felder.txt
    python roic_felder.py NVDA       # anderer Titel

Bitte die Ausgabe (oder felder.txt) an mich schicken.
"""
import json
import sys

import roic

TICKER = (sys.argv[1] if len(sys.argv) > 1 else "AAPL").upper()

# Endpunkte laut deinem Screenshot der API-Uebersicht
ENDPUNKTE = [
    ("Company Profile",        f"company/profile/{TICKER}", None),
    # prices/latest gibt es im Individual-Plan nicht - der Kurs steht
    # im Company Profile ("price"). Deshalb hier entfernt.
    ("Income Statement (a)",   f"fundamental/income-statement/{TICKER}",
     {"period": "annual", "limit": 2}),
    ("Income Statement (q)",   f"fundamental/income-statement/{TICKER}",
     {"period": "quarter", "limit": 2}),
    ("Balance Sheet",          f"fundamental/balance-sheet/{TICKER}",
     {"period": "annual", "limit": 1}),
    ("Cash Flow",              f"fundamental/cash-flow/{TICKER}",
     {"period": "annual", "limit": 1}),
    ("Ratios Profitability",   f"fundamental/ratios/profitability/{TICKER}", None),
    ("Ratios Credit & Debt",   f"fundamental/ratios/credit/{TICKER}", None),
    ("Ratios Liquidity",       f"fundamental/ratios/liquidity/{TICKER}", None),
    ("Ratios Working Capital", f"fundamental/ratios/working-capital/{TICKER}", None),
    # ratios/yield antwortet nicht - Dividendenrendite kommt aus dem Profil.
    ("Enterprise Value",       f"fundamental/enterprise-value/{TICKER}", None),
    ("Multiples",              f"fundamental/multiples/{TICKER}", None),
    ("Per-Share Data",         f"fundamental/per-share/{TICKER}", None),
]

# Diese Werte suchen wir - damit du gleich siehst, wo sie stecken
GESUCHT = {
    "revenue": ("umsatz", "revenue", "sales"),
    "operating_margin": ("operating", "ebit"),
    "ebitda": ("ebitda",),
    "net_income": ("net_income", "netincome", "profit"),
    "free_cashflow": ("free_cash", "freecash", "fcf"),
    "book_value": ("book", "equity"),
    "total_debt": ("debt",),
}

if not roic.enabled():
    print("Kein Schluessel gesetzt.")
    raise SystemExit(1)

print("=" * 72)
print(f"ROIC-FELDNAMEN  ({TICKER})")
print("=" * 72)

alle_felder = {}

for name, pfad, params in ENDPUNKTE:
    print(f"\n{'='*72}\n{name}\n   {pfad}" + (f"  {params}" if params else ""))
    print("-" * 72)
    d = roic._get(pfad, params)
    if d is None:
        print("   KEINE ANTWORT (Pfad falsch oder nicht im Plan enthalten)")
        continue
    erste = roic._first(d)
    if not isinstance(erste, dict):
        print(f"   Unerwartetes Format: {type(d).__name__}")
        print(f"   {str(d)[:200]}")
        continue
    for k in sorted(erste.keys()):
        v = erste[k]
        if isinstance(v, (dict, list)):
            v = f"<{type(v).__name__}>"
        elif isinstance(v, str) and len(v) > 40:
            v = v[:40] + "..."
        print(f"   {k:42} {v}")
        alle_felder.setdefault(k, []).append(name)

# --- Zusammenfassung: wo stecken die gesuchten Werte?
print(f"\n{'='*72}")
print("WO STECKEN DIE GESUCHTEN WERTE?")
print("=" * 72)
for ziel, mustern in GESUCHT.items():
    treffer = [(k, q) for k, q in alle_felder.items()
               if any(m in k.lower() for m in mustern)]
    print(f"\n{ziel}:")
    if not treffer:
        print("   nichts gefunden")
    for k, quellen in treffer[:8]:
        print(f"   {k:42} in: {quellen[0]}")

print(f"\n{'='*72}")
print("Bitte diese Ausgabe komplett an mich schicken.")
