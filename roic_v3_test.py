#!/usr/bin/env python3
"""
roic_v3_test.py - Prueft den fertigen v3-Umbau END-TO-END mit deinem Key.

Der Umbau in roic.py ist gemacht:
  - BASE = https://api.roic.ai/v3.0.0
  - Ticker werden ueber die Suche zu EXCHANGE:TICKER aufgeloest (+ ISIN)
  - alle Endpunkte laufen ueber das aufgeloeste Symbol

Dieses Skript ruft den ECHTEN App-Code (roic.py, providers.py) auf und
zeigt, ob fuer verschiedene Titel Kurs, ISIN, Composite ankommen. Wenn das
hier klappt, funktioniert das Tool wieder.

AUFRUF (PowerShell):  $env:ROIC_API_KEY="dein_key"; python roic_v3_test.py
"""
import os


def _key():
    if os.getenv("ROIC_API_KEY"):
        return
    for p in (".streamlit/secrets.toml", "../.streamlit/secrets.toml"):
        if os.path.isfile(p):
            for z in open(p, encoding="utf-8"):
                if z.strip().startswith("ROIC_API_KEY"):
                    os.environ["ROIC_API_KEY"] = \
                        z.split("=", 1)[1].strip().strip('"').strip("'")
                    return


_key()

import roic          # noqa: E402
import providers     # noqa: E402

print("=" * 66)
print("v3-Umbau - End-to-End-Test")
print(f"BASE = {roic.BASE}")
print("=" * 66)

# 1) Aufloesung: nackter Ticker -> EXCHANGE:TICKER + ISIN
print("\n[1] Ticker-Aufloesung (Suche -> v3-Symbol + ISIN)")
for t in ("AAPL", "MSFT", "KO", "HSBC", "SAP.DE", "RR.L", "BP.L"):
    r = roic.aufloesen(t)
    if r:
        print(f"   {t:8} -> {str(r.get('symbol')):16} ISIN {r.get('isin')} "
              f"[{r.get('exchange')}, {r.get('country')}, "
              f"primary={r.get('is_primary')}]")
    else:
        print(f"   {t:8} -> nicht aufloesbar (faellt auf yfinance zurueck)")

# 2) Voller Fundamentaldaten-Abruf ueber den App-Code
print("\n[2] get_fundamentals + score_stock (echte Bewertung)")
import scoring     # noqa: E402
import valuation   # noqa: E402
for t in ("AAPL", "HSBC", "SAP.DE"):
    try:
        f = providers.get_fundamentals(t, deep=True)
        if f and f.get("price"):
            ep = valuation.classify_playbook(f)
            comp = scoring.score_stock(f, None, preset=ep).get("composite")
            print(f"   {t:8} {(f.get('name') or '')[:26]:26} "
                  f"{f.get('price')} {f.get('currency')} "
                  f"ISIN {f.get('isin')} -> Composite {comp}")
            # Rohdaten-Check: kommen die Score-Bausteine an?
            fehlt = [k for k in ("revenue", "operating_margin", "roe",
                                 "eps_trailing", "pe_trailing")
                     if f.get(k) is None]
            if fehlt:
                print(f"            fehlende Rohfelder: {fehlt}")
        else:
            print(f"   {t:8} kein Kurs / keine Daten")
    except Exception as e:
        print(f"   {t:8} Fehler: {e}")

# 3) HSBC im Detail - der Kaufkandidat
print("\n[3] HSBC + Insider/Analyst (fuer die Kaufkandidat-Wertung)")
try:
    f = providers.get_fundamentals("HSBC", deep=True)
    ep = valuation.classify_playbook(f)
    comp = scoring.score_stock(f, None, preset=ep).get("composite")
    print(f"   Kurs {f.get('price')} {f.get('currency')}, ISIN {f.get('isin')}, "
          f"Composite {comp}")
    try:
        print(f"   Insider:   {providers.get_insider_activity('HSBC')}")
    except Exception as e:
        print(f"   Insider:   Fehler {e}")
    try:
        print(f"   Analysten: {providers.get_analyst_ratings('HSBC')}")
    except Exception as e:
        print(f"   Analysten: Fehler {e}")
except Exception as e:
    print(f"   Fehler: {e}")

# 4) UK-Pence-Check: kommt der Kurs in Pfund oder Pence?
print("\n[4] UK-Pence-Check (Kurs muss vernuenftig sein, nicht x100)")
for t in ("BP.L", "SHEL.L", "HSBA.L"):
    try:
        f = providers.get_fundamentals(t)
        px = f.get("price") if f else None
        cur = f.get("currency") if f else None
        warn = "  <- VERDACHT Pence" if (px and px > 200 and cur == "GBP") else ""
        print(f"   {t:8} {px} {cur}{warn}")
    except Exception as e:
        print(f"   {t:8} Fehler: {e}")

print("\n" + "=" * 66)
print("Wenn [1] Symbole+ISIN zeigt und [2]/[3] Kurse+Composite liefern,")
print("laeuft der v3-Umbau. Schick mir die Ausgabe - dann sehen wir, ob")
print("noch irgendwo ein Feldname klemmt.")
