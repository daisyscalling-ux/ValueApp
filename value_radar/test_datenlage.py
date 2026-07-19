#!/usr/bin/env python3
"""
test_datenlage.py - Was liefert DEIN AKTUELLER Datenstack wirklich?

Beantwortet vor jeder Kaufentscheidung die Frage:
Fehlen die Fundamentaldaten tatsaechlich - oder liegt das Problem woanders?

AUFRUF (im value_radar-Ordner, wo providers.py liegt):
    python test_datenlage.py
    python test_datenlage.py BP.L SHEL.L      # eigene Ticker

Kostet nichts, aendert nichts - fragt nur deine bestehenden Quellen ab
(yfinance + Finnhub + FMP + Tiingo, je nach konfigurierten Schluesseln).
"""
import sys

import providers
import valuation

# Deine Problemticker aus den Cron-Logs
DEFAULT = ["AAPL", "BP.L", "SHEL.L", "GSK.L", "BHP.L", "SAP.DE", "4GLD.DE"]

# Welche Felder braucht WELCHE Bewertungsmethode? (aus valuation.py ausgelesen)
METHODS = {
    "justified_pe (Faires KGV)": ["eps_trailing", "net_debt_ebitda",
                                  "current_ratio", "free_cashflow"],
    "fwd_pe (Forward-KGV)":      ["eps_forward"],
    "hist_pe (hist. Median-KGV)": ["hist_pe_median", "eps_trailing"],
    "ev_ebitda (Multiple)":      ["ebitda", "shares_out", "revenue_growth"],
    "dcf_two_stage (DCF)":       ["free_cashflow", "shares_out", "market_cap",
                                  "beta", "total_debt", "earnings_growth"],
    "epv (Ertragswert)":         ["market_cap", "shares_out", "beta",
                                  "total_debt", "net_debt"],
    "analyst (Kursziel)":        ["analyst_target"],
}


def show(tk):
    print("\n" + "=" * 62)
    print(f"TICKER: {tk}")
    print("=" * 62)
    try:
        f = providers.get_fundamentals(tk, deep=True)
    except Exception as e:
        print(f"  Abruf fehlgeschlagen: {e}")
        return None
    if not f:
        print("  KEINE Daten erhalten.")
        return None

    print(f"  Name:   {f.get('name') or '(fehlt)'}")
    print(f"  Sektor: {f.get('sector') or '(fehlt)'}")
    print(f"  Kurs:   {f.get('price') or '(fehlt)'}  {f.get('currency') or ''}")
    src = f.get("sources") or f.get("_sources")
    if src:
        print(f"  Quellen: {src}")

    # Welche Methode kann rechnen, welche nicht - und woran scheitert sie?
    print("\n  BEWERTUNGSMETHODEN:")
    ok_count = 0
    for name, fields in METHODS.items():
        missing = [x for x in fields if f.get(x) in (None, "", 0)]
        if not missing:
            ok_count += 1
            print(f"    OK    {name}")
        else:
            print(f"    fehlt {name}")
            print(f"          -> es fehlt: {', '.join(missing)}")

    print(f"\n  {ok_count} von {len(METHODS)} Methoden koennen rechnen.")
    if ok_count <= 1:
        print("  => Genau das ist die Meldung 'Fair Value aus nur einer Methode'.")

    # Gegenprobe: was sagt valuation.fair_value selbst?
    try:
        ep = valuation.classify_playbook(f)
        v = valuation.fair_value(f, None, ep)
        print(f"\n  valuation.fair_value: {v.get('fair_value')} "
              f"(n_methods={v.get('n_methods')}, reliable={v.get('reliable')})")
    except Exception as e:
        print(f"\n  valuation.fair_value fehlgeschlagen: {e}")
    return ok_count


def main():
    tickers = sys.argv[1:] or DEFAULT
    print("DATENLAGE-TEST - was liefert dein aktueller Stack?")
    print("(yfinance + Finnhub + FMP + Tiingo, je nach Schluessel)")
    results = {}
    for tk in tickers:
        results[tk] = show(tk)

    print("\n" + "=" * 62)
    print("ZUSAMMENFASSUNG")
    print("=" * 62)
    for tk, n in results.items():
        if n is None:
            print(f"  {tk:10} kein Abruf moeglich")
        else:
            print(f"  {tk:10} {n}/{len(METHODS)} Bewertungsmethoden rechenbar")
    print()
    print("SO LIEST DU DAS:")
    print("- 4+ Methoden bei den .L-Tickern -> deine Daten sind in Ordnung,")
    print("  das Problem liegt NICHT an fehlenden Fundamentaldaten.")
    print("- 0-1 Methoden -> die oben genannten Felder fehlen wirklich.")
    print("  Dann gezielt pruefen, ob ein Anbieter GENAU diese Felder liefert.")
    print("- Achte darauf, WELCHE Felder fehlen: sind es immer dieselben")
    print("  (z.B. free_cashflow, shares_out), reicht evtl. eine kleine Quelle.")


if __name__ == "__main__":
    main()
