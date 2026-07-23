#!/usr/bin/env python3
"""
test_roic_live.py - Pruefung der roic.ai-Anbindung mit ECHTEM Schluessel.

VOR dem ersten produktiven Lauf ausfuehren, und NOCHMAL, bevor du
ROIC_EU_ENABLED=1 setzt.

AUFRUF (Windows PowerShell):
    $env:ROIC_API_KEY="dein_key"
    python test_roic_live.py               # US-Titel
    python test_roic_live.py eu            # zusaetzlich Europa-Pruefung

Was geprueft wird:
  1) Kommt ueberhaupt etwas zurueck (Schluessel gueltig)?
  2) Sind die US-Kennzahlen plausibel (Margen 0..1, KGV 1..200)?
  3) KGV-Historie fuer relval vorhanden?
  4) [eu] Sind die Europa-Werte ENDLICH korrekt? (BP.L-KGV muss ~10
     sein, nicht 168.091 - der v2-Fehler, den der Support bestaetigt hat)
"""
import sys

import roic


def _ok(t, wert, lo, hi):
    if wert is None:
        return f"  ?  {t}: fehlt"
    if lo <= wert <= hi:
        return f"  OK {t}: {wert}"
    return f"  !! {t}: {wert}  AUSSERHALB [{lo}, {hi}]"


def main():
    if not roic.enabled():
        print("Kein Schluessel. Setze die Umgebungsvariable ROIC_API_KEY.")
        return

    print("=" * 64)
    print("ROIC.AI LIVE-PRUEFUNG")
    print("=" * 64)

    print("\n--- 1) US-Titel ---")
    for t in ("AAPL", "NVDA", "GM", "F"):
        b = roic.bundle(t)
        if not b:
            print(f"  !! {t}: KEINE Daten")
            continue
        print(f"\n  {t} ({b.get('name')})")
        print(_ok("operating_margin", b.get("operating_margin"), 0.0, 1.0))
        print(_ok("roe", b.get("roe"), -2.0, 3.0))
        print(_ok("pe_trailing", b.get("pe_trailing"), 1, 200))
        print(_ok("revenue (Mrd)", (b.get("revenue") or 0) / 1e9, 1, 1000))

    print("\n--- 2) KGV-Historie (fuer relval) ---")
    for t in ("AAPL", "MSFT"):
        h = roic.pe_history(t)
        print(f"  {t}: {len(h)} Jahre -> {h}")
        if len(h) < 4:
            print(f"  !! {t}: zu wenig Historie")

    print("\n--- 3) Quartalshistorie (tiefer als yfinance) ---")
    q = roic.earnings_history_deep("AAPL", 20)
    print(f"  AAPL: {len(q)} Quartale (yfinance liefert max. 8)")

    if len(sys.argv) > 1 and sys.argv[1].lower() == "eu":
        print("\n--- 4) EUROPA-PRUEFUNG (v3-Freigabe) ---")
        print("  Referenz: BP.L-KGV sollte grob 8-15 sein. v2 lieferte 168.091.")
        alt = roic.covers
        roic.covers = lambda t: roic.enabled()      # Sperre nur fuer den Test
        try:
            for t in ("BP.L", "SAP.DE", "SHEL.L"):
                b = roic.bundle(t)
                m = roic.multiples(t)
                pe = None
                if m:
                    pe = roic._num(roic._g(m, "pe_ratio", "price_earnings"))
                print(f"\n  {t} ({(b or {}).get('name')})")
                print(_ok("pe (multiples)", pe, 1, 200))
                print(_ok("operating_margin", (b or {}).get("operating_margin"),
                          0.0, 1.0))
            print("\n  Wenn ALLE Werte OK sind: ROIC_EU_ENABLED=1 setzen.")
            print("  Wenn irgendwo '!!' steht: NICHT freischalten, v2-Fehler "
                  "besteht weiter.")
        finally:
            roic.covers = alt

    print("\n" + "=" * 64)
    print("Fertig. '!!'-Zeilen bitte an mich zurueckmelden.")


if __name__ == "__main__":
    main()
