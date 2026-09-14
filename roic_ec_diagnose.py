#!/usr/bin/env python3
"""
roic_ec_diagnose.py - Testet die KOMPLETTE Earnings-Call-Kette und zeigt an
jeder Station, was ankommt. So sehen wir genau, wo es hakt.

AUFRUF (PowerShell im value_radar-Ordner):
    $env:ROIC_API_KEY="dein_key"; python roic_ec_diagnose.py

Es werden nacheinander geprueft:
  1) Roher API-Aufruf GET /earnings-calls?identifier=NASDAQ:AAPL
  2) roic.transcript_liste("AAPL")        -> Liste der Calls
  3) roic.neue_transkripte([...], tage=90) -> was der Nachtlauf finden wuerde
  4) roic.transcript(...) fuer den neuesten -> das Volltext-Protokoll
"""
import json
import os
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


def roh(path, params):
    params = dict(params)
    params["apikey"] = KEY
    url = f"{BASE}/{path.lstrip('/')}?{urllib.parse.urlencode(params)}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ec-diag"})
        with urllib.request.urlopen(req, timeout=25) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8", "replace")[:300]
        except Exception:
            body = ""
        return e.code, body
    except Exception as e:
        return "ERR", str(e)[:200]


def schritt(nr, titel):
    print(f"\n{'='*62}\n[{nr}] {titel}\n{'='*62}")


def main():
    if not KEY:
        print('KEIN ROIC_API_KEY. Erst: $env:ROIC_API_KEY="dein_key"')
        return

    # -- 1) Roher Endpunkt-Test ------------------------------------------
    schritt(1, "Roher Aufruf  GET /earnings-calls?identifier=NASDAQ:AAPL")
    status, body = roh("earnings-calls", {"identifier": "NASDAQ:AAPL", "limit": 5})
    print(f"HTTP-Status: {status}")
    print(f"Antwort (Anfang): {body[:400]}")
    if status == 200:
        try:
            d = json.loads(body)
            data = d.get("data") if isinstance(d, dict) else d
            print(f"-> 'data' enthaelt {len(data or [])} Eintraege")
            if data:
                print(f"-> Felder im 1. Eintrag: {sorted(data[0].keys())}")
        except Exception as e:
            print(f"-> JSON-Parse-Fehler: {e}")

    # -- 2) transcript_liste ---------------------------------------------
    schritt(2, "roic.transcript_liste('AAPL')")
    try:
        import roic
        liste = roic.transcript_liste("AAPL", limit=5)
        print(f"Ergebnis: {len(liste)} Eintraege")
        for z in liste[:3]:
            print(f"   {z}")
        if not liste:
            print("-> LEER. Hier bricht es. Der Endpunkt/Parse stimmt nicht.")
    except Exception as e:
        import traceback
        print(f"FEHLER: {e}")
        traceback.print_exc()

    # -- 3) neue_transkripte (wie der Nachtlauf, aber nur 5 Titel) --------
    schritt(3, "roic.neue_transkripte(5 Titel, tage=90)")
    try:
        import roic
        # bewusst grosszuegige 90 Tage, damit auch aeltere Calls zaehlen
        testtitel = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL"]
        neu = roic.neue_transkripte(testtitel, tage=90, deckel=5)
        print(f"Gefundene 'neue' Calls (90 Tage): {len(neu)}")
        for z in neu[:5]:
            print(f"   {z}")
        if not neu:
            print("-> LEER. Entweder liefert transcript_liste nichts (siehe 2),")
            print("   oder alle Calls sind aelter als 90 Tage.")
    except Exception as e:
        import traceback
        print(f"FEHLER: {e}")
        traceback.print_exc()

    # -- 4) transcript (Volltext des neuesten AAPL-Calls) ----------------
    schritt(4, "roic.transcript('AAPL') - Volltext des neuesten Calls")
    try:
        import roic
        tx = roic.transcript("AAPL")
        if tx and tx.get("text"):
            print(f"Datum {tx.get('datum')}, {tx.get('quartal')} {tx.get('jahr')}")
            print(f"Textlaenge: {len(tx['text'])} Zeichen")
            print(f"Anfang: {tx['text'][:200]}")
        else:
            print(f"-> Kein Text. Rueckgabe: {tx}")
    except Exception as e:
        import traceback
        print(f"FEHLER: {e}")
        traceback.print_exc()

    print(f"\n{'='*62}\nFERTIG. Schick mir die komplette Ausgabe.\n{'='*62}")


if __name__ == "__main__":
    main()
