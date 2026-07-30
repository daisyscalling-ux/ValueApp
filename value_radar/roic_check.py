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

# --- Stufe 4: ROHER Abruf mit HTTP-Status (zeigt 401/429/403 im Klartext)
print(f"\n4) Roher HTTP-Abruf (fundamental/profile/AAPL)")
import json as _json
import urllib.parse as _up
import urllib.request as _ur
import urllib.error as _ue
_url = f"{roic.BASE}/fundamental/profile/AAPL?" + _up.urlencode({"apikey": k})
t0 = time.time()
try:
    _req = _ur.Request(_url, headers={"User-Agent": "roic-check"})
    with _ur.urlopen(_req, timeout=20) as _r:
        _status = _r.status
        _roh = _r.read().decode("utf-8", "replace")
    print(f"   HTTP {_status} nach {time.time()-t0:.1f}s")
    if _status == 200:
        print("   OK: Schluessel akzeptiert.")
except _ue.HTTPError as _e:
    _status = _e.code
    print(f"   HTTP {_status} - {_e.reason}")
    if _status == 401:
        print("   -> Schluessel UNGUELTIG oder abgelaufen. Bitte pruefen.")
    elif _status == 429:
        print("   -> Rate-Limit. Kurz warten, erneut testen.")
    elif _status == 403:
        print("   -> Zugriff gesperrt (Plan deckt Endpunkt nicht?).")
    raise SystemExit(1)
except Exception as _e:
    print(f"   Netzwerk/anderer Fehler: {_e}")
    raise SystemExit(1)

# Ueber den App-Code (nutzt den aktuell konfigurierten Endpunkt)
d = roic._get("fundamental/profile/AAPL")
erste = roic._first(d) if d else None
if isinstance(erste, dict):
    print(f"   Felder: {sorted(erste.keys())[:12]}")
    print(f"   Name:   {erste.get('company_name') or erste.get('name')}")
    print(f"   ISIN:   {erste.get('isin')}")

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

# --- Stufe 6: europaeische Deckung
print(f"\n6) Deckung europaeischer Titel (covers)")
for _t in ("SAP.DE", "HSBC", "RR.L", "0R2V.L"):
    print(f"   {_t:8} covers={roic.covers(_t)}")

# --- Stufe 7: HSBC im Detail - der Kaufkandidat aus dem Screenshot
print(f"\n7) HSBC im Detail (dein Kaufkandidat)")
try:
    import providers
    f = providers.get_fundamentals("HSBC", deep=True)
    if f and f.get("price"):
        print(f"   Name:      {f.get('name')}")
        print(f"   ISIN:      {f.get('isin')}")
        print(f"   Kurs:      {f.get('price')} {f.get('currency')}")
        print(f"   Composite: {f.get('composite')}")
        # Insider/Analyst - die entscheidenden Bonusdaten fuer den Nachtlauf
        try:
            _ins = providers.get_insider_activity("HSBC")
            print(f"   Insider:   {_ins}")
        except Exception as _e:
            print(f"   Insider:   Fehler {_e}")
        try:
            _ana = providers.get_analyst_ratings("HSBC")
            print(f"   Analysten: {_ana}")
        except Exception as _e:
            print(f"   Analysten: Fehler {_e}")
        print("   -> Wenn hier Kurs + Insider + Analysten ankommen, hat der")
        print("      Nachtlauf alles fuer die Kaufkandidat-Wertung.")
    else:
        print("   Keine/kein Kurs - roic liefert fuer HSBC nichts.")
except Exception as _e:
    print(f"   Fehler: {_e}")

# --- Stufe 8: BRITISCHE AKTIEN - unsere drei bekannten Fallen
print(f"\n8) Britische Aktien - die drei UK-Probleme im Detail")
try:
    import providers
    import precompute as pc

    # (a) PENCE-NORMALISIERUNG: UK-Kurse kommen in Pence (BP.L 517 GBp),
    #     muessen auf Pfund (5,17) - sonst Bewertungen x100 daneben.
    print("   (a) Pence-Normalisierung (Kurs muss in Pfund landen):")
    for _t in ("BP.L", "SHEL.L", "HSBA.L"):
        try:
            f = providers.get_fundamentals(_t)
            _px = f.get("price") if f else None
            _cur = f.get("currency") if f else None
            _pence = providers.is_pence(_t)
            _hinweis = ""
            if _px is not None and _px > 200 and _cur == "GBP":
                _hinweis = "  <- VERDACHT: evtl. noch Pence (Wert > 200)"
            print(f"       {_t:8} Kurs {_px} {_cur} (is_pence={_pence}){_hinweis}")
        except Exception as _e:
            print(f"       {_t:8} Fehler {_e}")

    # (b) ZWEITNOTIERUNGEN: London-IOB (Ziffer + .L) muessen als
    #     Zweitnotierung erkannt und rausgefiltert werden.
    print("   (b) London-IOB als Zweitnotierung erkennen (soll True):")
    for _t in ("0R2V.L", "0QZ8.L"):
        print(f"       {_t:8} ist_zweitnotierung={pc.ist_zweitnotierung(_t)}")

    # (c) ECHTE UK-TITEL duerfen NICHT rausfliegen (soll False).
    print("   (c) Echte UK-Titel behalten (soll False):")
    for _t in ("RR.L", "BARC.L", "BHP.L", "BP.L"):
        print(f"       {_t:8} ist_zweitnotierung={pc.ist_zweitnotierung(_t)}")

    # (d) Deckt roic UK-Titel mit ISIN? (fuer die Entdopplung)
    print("   (d) roic-Daten fuer einen echten UK-Titel (RR.L):")
    try:
        f = providers.get_fundamentals("RR.L", deep=True)
        if f and f.get("price"):
            print(f"       Name {f.get('name')} · ISIN {f.get('isin')} · "
                  f"{f.get('price')} {f.get('currency')}")
            if not f.get("isin"):
                print("       -> keine ISIN: Entdopplung greift nur ueber Namen")
        else:
            print("       roic/yfinance liefert nichts fuer RR.L")
    except Exception as _e:
        print(f"       Fehler {_e}")
    print("   Merke: (a) Kurse muessen in Pfund sein, (b) True, (c) False.")
    print("   Weicht etwas ab, schick mir genau diese Zeilen.")
except Exception as _e:
    print(f"   Fehler in Stufe 8: {_e}")

print("\n" + "=" * 60)
print("ERGEBNIS: Es gehen Abrufe raus. Wenn dein Zaehler trotzdem bei")
print("300/300 steht, ist es das rollierende Minutenfenster - der Wert")
print("fuellt sich jede Minute wieder auf.")
print("\nSchick mir die Ausgabe ab Stufe 4 - dann sehen wir, ob der neue")
print("Schluessel voll traegt und HSBC seine Kaufkandidat-Daten bekommt.")
