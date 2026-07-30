#!/usr/bin/env python3
"""
roic_v3_transcript.py - Findet den richtigen v3-Endpunkt fuers Earnings-Call-
PROTOKOLL. Die LISTE der Calls kommt an (company/earnings-calls/list/...),
aber das Wortprotokoll (transcript/latest) liefert nichts.

Die Sonde probiert mehrere Pfad- und Parameter-Varianten fuer AAPL durch und
zeigt HTTP-Status + ob Text drinsteht.

AUFRUF (PowerShell):  $env:ROIC_API_KEY="dein_key"; python roic_v3_transcript.py
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


def ruf(path, params=None):
    params = dict(params or {})
    params["apikey"] = KEY
    url = f"{BASE}/{path.lstrip('/')}?{urllib.parse.urlencode(params)}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "roic-tx"})
        with urllib.request.urlopen(req, timeout=25) as r:
            status = r.status
            roh = r.read().decode("utf-8", "replace")
        try:
            daten = json.loads(roh)
        except Exception:
            daten = roh[:120]
        # Text/Content vorhanden?
        txt_len = 0
        obj = daten[0] if isinstance(daten, list) and daten else daten
        if isinstance(obj, dict):
            for k in ("content", "transcript", "text", "body"):
                v = obj.get(k)
                if isinstance(v, str):
                    txt_len = len(v)
                    break
            felder = sorted(obj.keys())[:10]
        else:
            felder = []
        print(f"  [{status}] {path:52}")
        if felder:
            print(f"         Felder: {felder}")
        if txt_len:
            print(f"         >>> TEXT gefunden: {txt_len} Zeichen <<<")
        return status, daten
    except urllib.error.HTTPError as e:
        print(f"  [{e.code}] {path:52} {e.reason}")
        return e.code, None
    except Exception as e:
        print(f"  [ERR] {path:52} {e}")
        return None, None


if not KEY:
    print("Kein ROIC_API_KEY. Setzen und erneut starten.")
    raise SystemExit(1)

print("=" * 64)
print(f"Earnings-Transcript-Sonde   {EX}")
print("=" * 64)

print("\n[1] Die LISTE (die funktioniert) - welche Felder/IDs liefert sie?")
s, d = ruf(f"company/earnings-calls/list/{EX}", {"limit": 5})
# Aus der Liste ein konkretes Jahr/Quartal ziehen
jahr = quartal = call_id = None
reihen = d if isinstance(d, list) else (d or {}).get("data") if isinstance(d, dict) else None
if isinstance(reihen, list) and reihen and isinstance(reihen[0], dict):
    z = reihen[0]
    print(f"      Beispiel-Eintrag: {json.dumps(z)[:300]}")
    jahr = z.get("year")
    quartal = z.get("quarter")
    call_id = z.get("id") or z.get("call_id") or z.get("transcript_id")
    print(f"      -> jahr={jahr} quartal={quartal} id={call_id}")

print("\n[2] transcript/latest (aktuell im Code - liefert nichts?)")
ruf(f"company/earnings-calls/latest/{EX}")

print("\n[3] transcript mit year+quarter (verschiedene Param-Namen)")
if jahr and quartal:
    try:
        q = int(str(quartal).replace("Q", ""))
    except Exception:
        q = quartal
    ruf(f"company/earnings-calls/transcript/{EX}", {"year": int(jahr), "quarter": q})
    ruf(f"company/earnings-calls/transcript/{EX}", {"fiscal_year": int(jahr), "fiscal_quarter": q})
    ruf(f"company/earnings-calls/{EX}", {"year": int(jahr), "quarter": q})

print("\n[4] Alternative Pfad-Schreibweisen")
ruf(f"company/earnings-calls/transcripts/{EX}")
ruf(f"company/earnings-call/transcript/{EX}")
ruf(f"earnings-calls/transcript/{EX}")
if call_id:
    ruf(f"company/earnings-calls/transcript/{call_id}")
    ruf(f"company/earnings-calls/{call_id}")

print("\n[5] Vielleicht enthaelt die LISTE schon den Text? (limit=1, voll)")
s, d = ruf(f"company/earnings-calls/list/{EX}", {"limit": 1})
obj = None
if isinstance(d, list) and d:
    obj = d[0]
elif isinstance(d, dict):
    inner = d.get("data")
    obj = inner[0] if isinstance(inner, list) and inner else d
if isinstance(obj, dict):
    print(f"      volle Felder: {sorted(obj.keys())}")

print("\n" + "=" * 64)
print("Schick mir die Ausgabe. Die [200]-Zeile mit '>>> TEXT gefunden'")
print("zeigt den richtigen Endpunkt - darauf stelle ich transcript() um.")
