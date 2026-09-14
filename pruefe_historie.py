"""
pruefe_historie.py - Wie viele Jahre Umsatzhistorie liefert roic wirklich?

    python3 pruefe_historie.py DVN USB CF LLY COST UNH

Der Reverse-DCF-Korridor braucht mindestens drei Anker (3J, 5J, 10J, Konsens).
Im letzten Lauf war er bei KEINEM der 30 Titel belastbar - das Gate war damit
wirkungslos. Die Frage ist, woran es liegt:

  a) roic liefert generell nur wenige Jahre  -> Quelle klaeren oder Anker
     anders schneiden
  b) umsatz_reihe() fuehrt die Quellen nicht richtig zusammen -> mein Fehler
  c) income_annual antwortet, aber mit anderen Feldnamen -> mein Fehler

Dieses Skript zeigt beide Quellen einzeln und das Ergebnis der Zusammenfuehrung.
"""

import sys

import roic
import valuation


def main(t: str) -> None:
    print(f"\n{'=' * 66}\n{t}\n{'=' * 66}")
    if not roic.enabled():
        print("  roic inaktiv.")
        return

    try:
        kh = roic.kennzahl_historie(t, 15) or []
    except Exception as e:
        kh = []
        print(f"  kennzahl_historie: Fehler {e}")
    jahre_kh = sorted(str(z.get("jahr"))[:4] for z in kh if z.get("revenue"))
    print(f"  kennzahl_historie : {len(jahre_kh):2d} Jahre mit Umsatz"
          + (f"  {jahre_kh[0]}-{jahre_kh[-1]}" if jahre_kh else ""))

    try:
        ia = roic.income_annual(t, limit=15) or []
    except Exception as e:
        ia = []
        print(f"  income_annual: Fehler {e}")
    print(f"  income_annual     : {len(ia):2d} Datensaetze")
    if ia and isinstance(ia[0], dict):
        felder = [k for k in ia[0] if "rev" in k.lower() or "sales" in k.lower()]
        print(f"     Umsatzfelder im ersten Satz: {felder or 'KEINE gefunden'}")
        jahrfelder = [k for k in ia[0]
                      if any(x in k.lower() for x in
                             ("year", "date", "period", "fiscal"))]
        print(f"     Jahresfelder: {jahrfelder or 'KEINE gefunden'}")

    # FMP GETRENNT abfragen. Die zusammengefuehrte Reihe zeigt nicht, ob FMP
    # fuenf Jahre lieferte oder gar nichts und der roic-Rueckfall eingesprungen
    # ist - beide Faelle sehen identisch aus.
    try:
        import providers
        roh = providers._fmp_get(f"income-statement/{t}", {"limit": 20})
        if roh is None:
            print("  FMP v3            : kein Ergebnis")
            roh = providers._fmp_stable("income-statement",
                                        {"symbol": t, "limit": 20})
            if roh is None:
                print("  FMP stable        : ebenfalls kein Ergebnis")
                print("     -> Beide FMP-Pfade tot. Die Umsatzhistorie bleibt "
                      "bei roics fuenf Jahren.")
            else:
                _j = sorted(str(z.get("calendarYear") or z.get("fiscalYear")
                                or z.get("date"))[:4]
                            for z in roh if isinstance(z, dict) and z.get("revenue"))
                print(f"  FMP stable        : {len(_j):2d} Jahre"
                      + (f"  {_j[0]}-{_j[-1]}" if _j else ""))
            roh = None
        elif isinstance(roh, dict):
            print(f"  FMP (roh)         : Fehlermeldung {str(roh)[:80]}")
        else:
            jahre = sorted(str(z.get("calendarYear") or z.get("date"))[:4]
                           for z in roh if z.get("revenue"))
            print(f"  FMP (roh)         : {len(jahre):2d} Jahre"
                  + (f"  {jahre[0]}-{jahre[-1]}" if jahre else ""))
        fmp = providers.umsatz_historie(t, 20)
    except Exception as e:
        fmp = []
        print(f"  providers.umsatz_historie: Fehler {e}")
    print(f"  zusammengefuehrt  : {len(fmp):2d} Jahre")
    if fmp:
        print("     " + "  ".join(f"{z['jahr'][-2:]}:{z['revenue'] / 1e9:.1f}"
                                  for z in fmp))
    reihe = fmp or roic.umsatz_reihe(t, 15)
    print(f"  verwendete Reihe  : {len(reihe):2d} Jahre")
    if reihe:
        print("     " + "  ".join(f"{z['jahr'][-2:]}:{z['revenue'] / 1e9:.1f}"
                                  for z in reihe))

    # Ankernamen NICHT fest verdrahten. Genau daran ist diese Anzeige schon
    # einmal gescheitert: Sie zaehlte nach den alten Namen (3J/5J/10J) weiter,
    # nachdem valuation.py auf 1J/2J/3J/4J umgestellt war - und meldete
    # "2 Anker, zu wenige", waehrend der Korridor tatsaechlich auf fuenf stand.
    # Massgeblich ist, was rd_korridor sieht, nicht was hier aufgelistet ist.
    letzte = reihe[-1]["revenue"] / reihe[-2]["revenue"] - 1 if len(reihe) > 1 else 0.05
    anker = valuation.anker_aus_fund({"revenue_growth": letzte}, historie=reihe)
    gesetzt = {k: v for k, v in anker.items()
               if not k.startswith("_") and v is not None}
    print(f"  -> Anker ({len(gesetzt)}): "
          + ", ".join(f"{k}={v * 100:.1f}%" for k, v in sorted(gesetzt.items())))

    for pb in ("quality", "cyclical", "inflection"):
        kor = valuation.rd_korridor(anker, pb)
        if not kor:
            print(f"     {pb:11s} kein Korridor")
            continue
        n = len(kor.anker)
        print(f"     {pb:11s} {kor.tief * 100:6.1f} % bis {kor.hoch * 100:6.1f} %  "
              f"({n} Anker, "
              + ("BELASTBAR - Gate darf ausschliessen"
                 if n >= 3 else "zu wenige - Gate nur daempfend") + ")")


if __name__ == "__main__":
    for t in (sys.argv[1:] or ["DVN"]):
        main(t.upper())
