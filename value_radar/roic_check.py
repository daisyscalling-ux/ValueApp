#!/usr/bin/env python3
"""
roic_check.py - Kommt der Schluessel an, und geht wirklich ein Abruf raus?

Beantwortet genau die Frage "warum sinkt mein Request-Zaehler nicht".
Laeuft lokal UND im GitHub-Runner.

AUFRUF lokal (PowerShell):
    $env:ROIC_API_KEY="dein_key"
    python roic_check.py

Im Workflow: als zusaetzlichen Schritt VOR precompute.py einhaengen:
    - name: roic pruefen
      working-directory: value_radar
      env:
        ROIC_API_KEY: ${{ secrets.ROIC_API_KEY }}
      run: python roic_check.py
"""
import os
import time

print("=" * 60)
print("ROIC-DIAGNOSE")
print("=" * 60)

# --- Stufe 1: Umgebungsvariable ueberhaupt gesetzt?
roh = os.getenv("ROIC_API_KEY", "")
print(f"\n1) Umgebungsvariable ROIC_API_KEY")
if not roh:
    print("   FEHLER: nicht gesetzt.")
    print("   -> Lokal:  $env:ROIC_API_KEY=\"...\"")
    print("   -> Action: env-Block im Workflow + Repo-Secret pruefen")
    raise SystemExit(1)
print(f"   OK: gesetzt, Laenge {len(roh)}, "
      f"beginnt mit '{roh[:4]}...', endet auf '...{roh[-3:]}'")
if roh != roh.strip():
    print("   WARNUNG: Leerzeichen/Zeilenumbruch am Rand! Secret neu anlegen.")
if roh.startswith(("'", '"')) or roh.endswith(("'", '"')):
    print("   WARNUNG: Anfuehrungszeichen im Wert! Secret ohne \" anlegen.")

# --- Stufe 2: sieht config ihn?
import config
print(f"\n2) config.ROIC_API_KEY")
k = getattr(config, "ROIC_API_KEY", "")
print(f"   {'OK: gefunden' if k else 'FEHLER: leer'} (Laenge {len(k)})")
if not k:
    raise SystemExit(1)

# --- Stufe 3: haelt roic sich fuer aktiv?
import roic
print(f"\n3) roic-Modul")
print(f"   enabled():        {roic.enabled()}")
print(f"   covers('AAPL'):   {roic.covers('AAPL')}   <- muss True sein")
print(f"   covers('BP.L'):   {roic.covers('BP.L')}   <- False ist RICHTIG (EU-Sperre)")
print(f"   eu_enabled():     {roic.eu_enabled()}")
if not roic.covers("AAPL"):
    print("   FEHLER: roic wuerde keinen einzigen Abruf machen.")
    raise SystemExit(1)

# --- Stufe 4: geht ein echter Abruf raus?
print(f"\n4) Echter Abruf (company/profile/AAPL)")
t0 = time.time()
d = roic._get("company/profile/AAPL")
dauer = time.time() - t0
if d is None:
    print(f"   FEHLER: keine Antwort ({dauer:.1f}s).")
    print("   Moegliche Ursachen: Schluessel ungueltig, Plan nicht aktiv,")
    print("   Endpunktpfad geaendert, Netzsperre.")
    print(f"   Test im Browser: {roic.BASE}/company/profile/AAPL?apikey=DEIN_KEY")
    raise SystemExit(1)
print(f"   OK: Antwort nach {dauer:.1f}s")
print(f"   Typ: {type(d).__name__}")
erste = roic._first(d)
if isinstance(erste, dict):
    print(f"   Felder: {sorted(erste.keys())[:12]}")
    print(f"   Name:   {erste.get('company_name') or erste.get('name')}")

# --- Stufe 5: kommt ein vollstaendiges Buendel zusammen?
print(f"\n5) bundle('AAPL') - 6 Abrufe")
t0 = time.time()
b = roic.bundle("AAPL")
print(f"   Dauer: {time.time()-t0:.1f}s, Felder: {len(b)}")
wichtig = ["name", "sector", "revenue", "operating_margin", "eps_trailing",
           "market_cap", "pe_trailing"]
for f in wichtig:
    v = b.get(f)
    print(f"   {'OK ' if v is not None else '-- '} {f:18} {v}")
fehlt = [f for f in wichtig if b.get(f) is None]
if fehlt:
    print(f"\n   HINWEIS: {len(fehlt)} Feld(er) leer: {', '.join(fehlt)}")
    print("   Wahrscheinlich heissen die Felder bei roic anders als erwartet.")
    print("   Bitte die 'Felder:'-Zeile aus Stufe 4 an mich schicken.")

print("\n" + "=" * 60)
print("ERGEBNIS: Es gehen Abrufe raus. Wenn dein Zaehler trotzdem bei")
print("300/300 steht, ist es das rollierende Minutenfenster - der Wert")
print("fuellt sich jede Minute wieder auf.")
