#!/usr/bin/env python3
"""
test_roic.py - Liefert roic.ai die Ticker und Kennzahlen, die Value Radar braucht?

Besonderheit gegenueber den frueheren Tests: Bei roic.ai kann JEDER Tarif -
auch der kostenlose - alle Endpunkte fuer alle Ticker aufrufen. Unterschied
sind nur Rate-Limit und Historientiefe. Wir koennen also VOLLSTAENDIG gratis
pruefen, statt wie bei EODHD in ein HTTP 403 zu laufen.

WICHTIG: Der Gratistarif erlaubt nur 5 Anfragen/Minute. Das Skript drosselt
deshalb selbst (ca. 13 s Pause). Der komplette Lauf dauert rund 3 Minuten -
das ist normal, nicht haengengeblieben.

AUFRUF:
    python test_roic.py DEIN_API_KEY

Gratis-Key (ohne Kreditkarte): https://roic.ai/login
"""
import json
import sys
import time
import urllib.error
import urllib.request

BASE = "https://api.roic.ai/v2"
PAUSE = 13.0            # 5 Anfragen/Min im Gratistarif -> 12 s Mindestabstand

# Deine echten Problemticker. Schreibweise bei roic.ai unbekannt ->
# mehrere Varianten testen, damit nichts faelschlich als fehlend gilt.
TICKERS = [
    ("AAPL",    ["AAPL"],                       "Kontrolle"),
    ("BP.L",    ["BP.L", "BP.LON", "BPl", "BP"], "Hedgefonds-Ablehnung"),
    ("SHEL.L",  ["SHEL.L", "SHEL.LON", "SHEL"],  "Hedgefonds-Ablehnung"),
    ("VWRL",    ["VWRL.AS", "VWRL", "VWRL.EU"],  "DEIN DEPOT"),
    ("4GLD.DE", ["4GLD.DE", "4GLD.XETRA", "4GLD"], "DEIN DEPOT"),
    ("SAP.DE",  ["SAP.DE", "SAP.XETRA", "SAP"],  "Europa-Gegenprobe"),
]

_last = [0.0]


def _get(path, key, params=None, quiet=False):
    """Ein API-Aufruf mit Drosselung."""
    wait = PAUSE - (time.time() - _last[0])
    if wait > 0:
        if not quiet:
            print(f"      (warte {wait:.0f}s wegen Limit 5/Min)", flush=True)
        time.sleep(wait)
    _last[0] = time.time()
    extra = "".join(f"&{k}={v}" for k, v in (params or {}).items())
    url = f"{BASE}/{path}?apikey={key}{extra}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "vr-test"})
        with urllib.request.urlopen(req, timeout=25) as r:
            return json.loads(r.read().decode()), None
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code}"
    except Exception as e:
        return None, str(e)


def _first(d):
    """roic.ai liefert je nach Endpunkt Liste oder Objekt."""
    if isinstance(d, list) and d:
        return d[0] if isinstance(d[0], dict) else {}
    if isinstance(d, dict):
        for k in ("data", "results", "items"):
            v = d.get(k)
            if isinstance(v, list) and v and isinstance(v[0], dict):
                return v[0]
        return d
    return {}


def find_ticker(variants, key):
    """Welche Schreibweise kennt roic.ai?"""
    for v in variants:
        d, err = _get(f"company/profile/{v}", key)
        if d:
            p = _first(d)
            if p:
                return v, p
        print(f"      '{v}': {err or 'leer'}")
    return None, None


def main():
    if len(sys.argv) < 2:
        print("Bitte API-Key angeben:  python test_roic.py DEIN_KEY")
        print("Gratis-Key: https://roic.ai/login")
        return
    key = sys.argv[1]
    print("=" * 66)
    print("ROIC.AI-TEST fuer Value Radar")
    print("Gratistarif: 5 Anfragen/Min -> das Skript drosselt, ~3 Min Laufzeit")
    print("=" * 66)

    found = {}
    for ytk, variants, why in TICKERS:
        print(f"\n--- {ytk}   ({why})")
        sym, prof = find_ticker(variants, key)
        if not sym:
            print("    NICHT gefunden")
            continue
        print(f"    GEFUNDEN als '{sym}'")
        for lbl, k in [("Name", "name"), ("Sektor", "sector"),
                       ("Land", "country"), ("Waehrung", "currency"),
                       ("Boerse", "exchange")]:
            v = prof.get(k) or prof.get(k.capitalize())
            if v:
                print(f"      {lbl}: {v}")
        # Warnung: Wenn nur der NACKTE Ticker traf (ohne Boersenkuerzel),
        # ist es womoeglich ein US-ADR statt des Originals. Beim Tiingo-Test
        # lieferte 'BPL' die laengst delistete Buckeye Partners LP.
        if "." not in sym and "." in ytk:
            print("      !! ACHTUNG: nur der nackte Ticker traf - das ist evtl.")
            print("         ein US-ADR, NICHT die Londoner/Xetra-Notierung.")
            print("         Name, Boerse und Waehrung oben pruefen!")
        found[ytk] = sym

    print("\n" + "=" * 66)
    print(f"TICKER-ABDECKUNG: {len(found)}/{len(TICKERS)}")
    for y, s in found.items():
        print(f"   {y:9} -> '{s}'")
    fehlt = [y for y, _, _ in TICKERS if y not in found]
    if fehlt:
        print(f"   fehlt: {fehlt}")

    # Tiefentest an EINEM europaeischen Titel - spart Anfragen
    ziel = found.get("BP.L") or found.get("SHEL.L") or found.get("SAP.DE")
    if not ziel:
        print("\nKein europaeischer Titel gefunden - Tiefentest entfaellt.")
        return

    print("\n" + "=" * 66)
    print(f"TIEFENTEST an '{ziel}' - liefert roic.ai die Felder der Scorecard?")
    print("=" * 66)

    # Pfade laut Doku: v2/fundamental/ratios/... (NICHT financial-ratios).
    # Je Eintrag mehrere Kandidaten - falls einer 404 gibt, wird der naechste
    # probiert. Ausgegeben werden ALLE gelieferten Felder, damit wir nicht
    # wieder von geratenen Feldnamen abhaengen.
    checks = [
        ("Profitabilitaet (ROE/ROIC/Margen)",
         [f"fundamental/ratios/profitability/{ziel}",
          f"financial-ratios/profitability/{ziel}"]),
        ("Verschuldung (Net Debt/EBITDA)",
         [f"fundamental/ratios/credit/{ziel}",
          f"financial-ratios/credit/{ziel}"]),
        ("Bewertungs-Multiplikatoren (KGV/KBV/EV-EBITDA)",
         [f"fundamental/valuation/multiples/{ziel}",
          f"valuation/multiples/{ziel}"]),
        ("Je-Aktie-Daten (EPS/Buchwert/FCF)",
         [f"fundamental/valuation/per-share/{ziel}",
          f"valuation/per-share/{ziel}"]),
    ]
    for label, pfade in checks:
        row, used, err = None, None, None
        for p in pfade:
            d, err = _get(p, key)
            if d:
                row, used = _first(d), p
                break
        if not row:
            print(f"\n  {label}: FEHLER ({err})")
            continue
        print(f"\n  {label}")
        print(f"    Pfad: {used}")
        print(f"    {len(row)} Felder geliefert:")
        for k, v in list(row.items())[:22]:
            print(f"      {k}: {v}")
        if len(row) > 22:
            print(f"      ... und {len(row)-22} weitere")

    # KERNFRAGE: wie tief reicht die KGV-Historie? (fuer hist_pe_median)
    print("\n" + "-" * 66)
    print("HISTORISCHES KGV - reicht es fuer den fehlenden hist_pe_median?")
    d, err = _get(f"fundamental/valuation/multiples/{ziel}", key,
                  {"period": "quarterly", "limit": "40"})
    if isinstance(d, list):
        print(f"  {len(d)} Perioden erhalten (Gratistarif: 2 Jahre, "
              f"Individual: 5 Jahre, Professional: 40+)")
        for row in d[:6]:
            if isinstance(row, dict):
                datum = (row.get("date") or row.get("fiscal_year")
                         or row.get("period") or "?")
                pe = next((row[k] for k in row
                           if "pe" in k.lower() and "ratio" in k.lower()), None)
                print(f"    {datum}: KGV = {pe}")
    elif d:
        print(f"  Antwort ist kein Zeitreihen-Array: {type(d).__name__}")
    else:
        print(f"  nicht abrufbar ({err})")

    print("\n" + "=" * 66)
    print("SO LIEST DU DAS:")
    print("- Kommen bei 'Bewertungs-Multiplikatoren' mehrere Perioden mit KGV?")
    print("  Dann liesse sich hist_pe_median daraus bauen - die relative")
    print("  Bewertung im Tool waere endlich nicht mehr leer.")
    print("- Waehrung war GBp: die Pence-Normalisierung bleibt also noetig,")
    print("  roic.ai rechnet Londoner Kurse NICHT auf Pfund um.")
    print("- Achte auf die Feldnamen oben - danach richtet sich der Adapter,")
    print("  falls wir roic.ai einbauen.")


if __name__ == "__main__":
    main()
