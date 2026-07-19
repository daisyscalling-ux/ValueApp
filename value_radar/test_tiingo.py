#!/usr/bin/env python3
"""
test_tiingo.py - Deckt Tiingo deine Problemticker ab? (VOR dem Kauf pruefen)

Tiingo Power kostet 30 $/Monat. Der Vorteil waere: providers.py hat den
Adapter schon - ein Upgrade waere reine Schluesselsache, KEIN Code-Umbau.
Die offene Frage ist die Abdeckung: Quellen widersprechen sich, ob
europaeische Titel (BP.L, VWRL, 4GLD) enthalten sind.

Der GRATIS-Zugang erlaubt 1.000 Abrufe/Tag - fuer diesen Test mehr als genug.

AUFRUF:
    python test_tiingo.py DEIN_TIINGO_TOKEN

Token gratis unter tiingo.com/account/api/token (Registrierung noetig).
Kostet nichts, aendert nichts.
"""
import json
import sys
import urllib.error
import urllib.request

BASE = "https://api.tiingo.com"

# Tiingo nutzt fuer internationale Titel teils andere Schreibweisen als Yahoo.
# Darum je Titel mehrere Varianten testen und melden, welche greift.
TICKERS = [
    ("AAPL",    ["AAPL"],                      "Kontrolle - muss klappen"),
    ("VWRL",    ["VWRL", "VWRL-AS", "VWRL.AS"], "DEIN DEPOT"),
    ("4GLD.DE", ["4GLD", "4GLD-DE", "4GLD.DE"], "DEIN DEPOT"),
    ("BP.L",    ["BP-L", "BP.L", "BPL", "BP"],  "Hedgefonds-Ablehnung"),
    ("SHEL.L",  ["SHEL-L", "SHEL.L", "SHEL"],   "Hedgefonds-Ablehnung"),
    ("GSK.L",   ["GSK-L", "GSK.L", "GSK"],      "Hedgefonds-Ablehnung"),
    ("SAP.DE",  ["SAP-DE", "SAP.DE", "SAP"],    "Europa-Gegenprobe"),
]


def _get(path, token, params=None):
    p = dict(params or {})
    p["token"] = token
    q = "&".join(f"{k}={v}" for k, v in p.items())
    url = f"{BASE}/{path}?{q}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "vr-test"})
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode()), None
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code}"
    except Exception as e:
        return None, str(e)


def try_ticker(sym, token):
    """Existiert der Ticker bei Tiingo und gibt es einen Kurs?"""
    meta, err = _get(f"tiingo/daily/{sym}", token)
    if err or not isinstance(meta, dict) or not meta.get("ticker"):
        return None, err or "unbekannt"
    px, err2 = _get(f"tiingo/daily/{sym}/prices", token)
    close = None
    if isinstance(px, list) and px:
        close = px[0].get("adjClose") or px[0].get("close")
    return {"name": meta.get("name"), "start": meta.get("startDate"),
            "end": meta.get("endDate"), "currency": meta.get("priceCurrency"),
            "close": close}, err2


def check_fundamentals(sym, token):
    """Fundamentaldaten sind bei Tiingo ein separates, kostenpflichtiges
    Add-on. HTTP 403/404 heisst hier 'nicht freigeschaltet', nicht
    'keine Daten vorhanden'."""
    d, err = _get(f"tiingo/fundamentals/{sym}/daily", token)
    if err:
        return None, err
    if isinstance(d, list) and d:
        row = d[0]
        return {k: row.get(k) for k in
                ("peRatio", "pbRatio", "marketCap", "enterpriseVal")}, None
    return None, "leer"


def main():
    if len(sys.argv) < 2:
        print("Bitte Token angeben:  python test_tiingo.py DEIN_TOKEN")
        print("Gratis-Token: https://www.tiingo.com/account/api/token")
        return
    token = sys.argv[1]
    print("=" * 64)
    print("TIINGO-ABDECKUNGSTEST")
    print("=" * 64)

    found, missing = [], []
    for ytk, variants, why in TICKERS:
        print(f"\n--- {ytk}   ({why})")
        hit = None
        for v in variants:
            info, err = try_ticker(v, token)
            if info:
                hit = (v, info)
                break
            print(f"      '{v}': {err}")
        if not hit:
            print("    ERGEBNIS: NICHT gefunden")
            missing.append(ytk)
            continue
        v, info = hit
        print(f"    GEFUNDEN als '{v}'")
        print(f"      Name:    {info['name']}")
        print(f"      Waehrung:{info['currency']}")
        print(f"      Kurs:    {info['close']}")
        print(f"      Historie:{info['start']} bis {info['end']}")
        found.append(ytk)

        fu, ferr = check_fundamentals(v, token)
        if fu:
            print(f"      Fundamentals: {fu}")
        else:
            print(f"      Fundamentals: nicht verfuegbar ({ferr})")

    print("\n" + "=" * 64)
    print("ERGEBNIS")
    print("=" * 64)
    print(f"  gefunden:      {len(found)}/{len(TICKERS)}  {found}")
    print(f"  nicht gefunden:{len(missing)}/{len(TICKERS)}  {missing}")
    print()
    print("SO ENTSCHEIDEST DU:")
    print("- Sind VWRL, 4GLD und die .L-Titel dabei? Dann waere Tiingo Power")
    print("  (30 $/Mon.) die bequemste Loesung - providers.py kann Tiingo schon,")
    print("  es waere NUR ein Schluessel-Eintrag noetig.")
    print("- Fehlen sie? Dann ist EODHD EOD All World (16,58 $/Mon.) besser:")
    print("  dort sind sie nachweislich vorhanden (dein frueherer Test: 8/9).")
    print("- 'Fundamentals nicht verfuegbar' ist ERWARTBAR: das ist bei Tiingo")
    print("  ein separates Zusatzprodukt, nicht Teil von Power.")


if __name__ == "__main__":
    main()
