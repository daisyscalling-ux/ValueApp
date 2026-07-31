#!/usr/bin/env python3
"""
roic_v3_liste.py - Findet den richtigen v3-Endpunkt fuer die LISTE der
Earnings Calls. Aktuell laedt der Earnings-Calls-Tab nichts mehr; die
Vermutung ist, dass der alte Pfad 'company/earnings-calls/list/{sym}' unter
v3 nicht mehr antwortet.

Die Sonde probiert mehrere Pfad-Varianten fuer AAPL durch und zeigt je
Variante: HTTP-Status, wie viele Eintraege zurueckkommen und welche Felder
der erste Eintrag hat. Der Pfad mit Status 200 UND Eintraegen ist der
richtige.

AUFRUF (PowerShell im value_radar-Ordner):
    $env:ROIC_API_KEY="dein_key"; python roic_v3_liste.py
"""
import json
import os
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://api.roic.ai/v3.0.0"


def _key():
    if os.getenv("ROIC_API_KEY"):
        return os.environ["ROIC_API_KEY"]
    for p in (".streamlit/secrets.toml", "../.streamlit/secrets.toml"):
        if os.path.isfile(p):
            for z in open(p, encoding="utf-8"):
                if z.strip().startswith("ROIC_API_KEY"):
                    return z.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


KEY = _key()
EX = "NASDAQ:AAPL"

# Kandidaten-Pfade fuer die LISTE der Earnings Calls (v3)
PFADE = [
    ("company/earnings-calls/list/{s}",      {"limit": 5}),      # alter v2-Pfad
    ("earnings-calls/list/{s}",              {"limit": 5}),      # v3 ohne 'company'
    ("earnings-calls/{s}/list",              {"limit": 5}),      # v3 Suffix-Variante
    ("earnings-calls",                       {"symbol": EX, "limit": 5}),  # v3 Query
    ("earnings-calls/list",                  {"symbol": EX, "limit": 5}),
    ("company/earnings-calls/{s}",           {"limit": 5}),
]


def ruf(path, params=None):
    params = dict(params or {})
    params["apikey"] = KEY
    url = f"{BASE}/{path.lstrip('/')}?{urllib.parse.urlencode(params)}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "roic-liste"})
        with urllib.request.urlopen(req, timeout=25) as r:
            status = r.status
            roh = r.read().decode("utf-8", "replace")
        try:
            daten = json.loads(roh)
        except Exception:
            return status, roh[:100], 0, []
        # Wie viele Eintraege?
        if isinstance(daten, list):
            reihen = daten
        elif isinstance(daten, dict):
            reihen = daten.get("data") or daten.get("earnings_calls") or []
            if not isinstance(reihen, list):
                reihen = [daten]
        else:
            reihen = []
        felder = sorted(reihen[0].keys())[:12] if (reihen and isinstance(reihen[0], dict)) else []
        return status, None, len(reihen), felder
    except urllib.error.HTTPError as e:
        return e.code, f"HTTP {e.code}", 0, []
    except Exception as e:
        return "ERR", str(e)[:80], 0, []


def main():
    if not KEY:
        print("KEIN ROIC_API_KEY gefunden. Erst setzen:")
        print('  $env:ROIC_API_KEY="dein_key"')
        return
    print(f"Teste Listen-Endpunkte fuer {EX}\n" + "=" * 60)
    treffer = []
    for pfad, params in PFADE:
        p = pfad.format(s=EX)
        status, fehler, anzahl, felder = ruf(p, params)
        marke = "  <-- FUNKTIONIERT" if (status == 200 and anzahl > 0) else ""
        print(f"\n{p}")
        print(f"   Params: {params}")
        print(f"   Status: {status}   Eintraege: {anzahl}{marke}")
        if fehler:
            print(f"   Hinweis: {fehler}")
        if felder:
            print(f"   Felder im 1. Eintrag: {felder}")
        if status == 200 and anzahl > 0:
            treffer.append((p, params, felder))
    print("\n" + "=" * 60)
    if treffer:
        print("RICHTIGER LISTEN-PFAD gefunden:")
        for p, params, felder in treffer:
            print(f"  {p}  mit {params}")
            print(f"  Felder: {felder}")
        print("\nSchick mir diese Ausgabe, dann passe ich transcript_liste an.")
    else:
        print("KEIN Pfad lieferte Eintraege. Moeglich: der Key hat kein")
        print("Earnings-Call-Paket, oder der Endpunkt heisst anders.")
        print("Schick mir die komplette Ausgabe oben.")


if __name__ == "__main__":
    main()
