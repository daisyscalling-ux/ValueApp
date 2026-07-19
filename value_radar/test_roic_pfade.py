#!/usr/bin/env python3
"""
test_roic_pfade.py - Findet die richtigen Endpunkt-Pfade fuer Bewertung.

Die Kennzahlen-Pfade sind bestaetigt:
    fundamental/ratios/profitability/{ticker}   -> funktioniert
    fundamental/ratios/credit/{ticker}          -> funktioniert
Die Bewertungs-Pfade liefern 404. Statt weiter zu raten probiert dieses
Skript die plausiblen Varianten durch und meldet, welche 200 zurueckgibt.

WICHTIG: Gratistarif = 5 Anfragen/Min. Bei ~14 Kandidaten dauert das
etwa 3 Minuten. Das Skript drosselt selbst.

AUFRUF:
    python test_roic_pfade.py DEIN_API_KEY
"""
import json
import sys
import time
import urllib.error
import urllib.request

BASE = "https://api.roic.ai/v2"
PAUSE = 13.0
TICKER = "BP.L"

# Kandidaten, abgeleitet aus dem bestaetigten Muster fundamental/ratios/...
KANDIDATEN = [
    "fundamental/valuation/multiples/{t}",
    "fundamental/multiples/{t}",
    "fundamental/ratios/valuation/{t}",
    "fundamental/ratios/multiples/{t}",
    "fundamental/valuation-multiples/{t}",
    "valuation/multiples/{t}",
    "fundamental/valuation/per-share/{t}",
    "fundamental/per-share/{t}",
    "fundamental/ratios/per-share/{t}",
    "fundamental/valuation/per_share/{t}",
    "fundamental/ratios/yield/{t}",
    "fundamental/valuation/enterprise-value/{t}",
    "fundamental/enterprise-value/{t}",
    "fundamental/ratios/liquidity/{t}",
]

_last = [0.0]


def _get(path, key):
    wait = PAUSE - (time.time() - _last[0])
    if wait > 0:
        time.sleep(wait)
    _last[0] = time.time()
    url = f"{BASE}/{path}?apikey={key}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "vr-test"})
        with urllib.request.urlopen(req, timeout=25) as r:
            return json.loads(r.read().decode()), None
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code}"
    except Exception as e:
        return None, str(e)


def main():
    if len(sys.argv) < 2:
        print("Aufruf:  python test_roic_pfade.py DEIN_KEY")
        return
    key = sys.argv[1]
    print("=" * 64)
    print(f"PFAD-SUCHE an {TICKER}  ({len(KANDIDATEN)} Kandidaten, ~3 Min)")
    print("=" * 64)

    treffer = []
    for i, muster in enumerate(KANDIDATEN, 1):
        path = muster.format(t=TICKER)
        d, err = _get(path, key)
        if d:
            row = d[0] if isinstance(d, list) and d else d
            felder = list(row)[:12] if isinstance(row, dict) else []
            n = len(row) if isinstance(row, dict) else "?"
            print(f"\n[{i}/{len(KANDIDATEN)}] OK  {path}")
            print(f"        {n} Felder: {', '.join(map(str, felder))}")
            treffer.append((path, row))
        else:
            print(f"[{i}/{len(KANDIDATEN)}] --  {path}  ({err})")

    print("\n" + "=" * 64)
    print(f"GEFUNDEN: {len(treffer)} funktionierende Pfade")
    for p, row in treffer:
        print(f"\n  {p}")
        if isinstance(row, dict):
            # Alles zeigen, was nach Bewertung aussieht
            interessant = {k: v for k, v in row.items()
                           if any(s in k.lower() for s in
                                  ("pe_", "_pe", "px_", "eps", "book",
                                   "ev_", "ebitda", "yield", "ratio",
                                   "sales", "cash_flow", "currency"))}
            for k, v in list(interessant.items())[:18]:
                print(f"      {k}: {v}")
    if not treffer:
        print("  Keiner der Kandidaten passt - dann hilft nur die Doku-Seite")
        print("  im Browser (Abschnitt 'GET https://api.roic.ai/v2/...')")
        print("  oder eine kurze Frage im roic.ai-Discord.")


if __name__ == "__main__":
    main()
