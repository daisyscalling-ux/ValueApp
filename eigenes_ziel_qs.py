#!/usr/bin/env python3
"""
eigenes_ziel_qs.py - Qualitaetssicherung fuer das eigene 12-Monats-Ziel.

Zeigt fuer echte Aktien nebeneinander:
  - Kurs, Fair Value, eigenes Ziel, Analystenziel
  - Upside des eigenen Ziels
  - Abweichung eigenes Ziel vs. Analystenkonsens
  - die komplette Herleitung (Wachstum, Bewertungshistorie, Regime)

So pruefst du, ob das eigene Ziel plausibel ist und ob die Abweichung vom
Analystenkonsens nachvollziehbar begruendet wird.

AUFRUF (PowerShell im value_radar-Ordner):
    $env:ROIC_API_KEY="dein_key"; python eigenes_ziel_qs.py
    python eigenes_ziel_qs.py OHB.DE SAP.DE AAPL
"""
import sys

STANDARD = ["AAPL", "MSFT", "GOOGL", "META", "NVDA", "SAP.DE", "OHB.DE",
            "KO", "JPM", "XOM"]


def main():
    ticker = sys.argv[1:] or STANDARD
    try:
        import providers
        import valuation as val
        import regime as reg
    except Exception as e:
        print(f"Import fehlgeschlagen: {e}")
        return

    # Marktregime einmal
    try:
        mr = reg.markt_regime()
        ampel = mr.get("ampel") if mr else None
        print(f"Marktregime: {ampel} ({(mr or {}).get('text','')})\n")
    except Exception:
        ampel = None

    for t in ticker:
        try:
            f = providers.get_fundamentals(t, deep=True)
            if not f or not f.get("price"):
                print(f"{t}: keine Daten\n")
                continue
            pb = val.classify_playbook(f)
            r = val.fair_value(f, None, pb)
            fv = r.get("fair_value")
            bk = reg.bewertungs_kontext(f, fair_value=fv)
            ez = val.eigenes_ziel(
                f, fair_value=fv, preset=pb, regime_ampel=ampel,
                pe_perzentil=bk.get("pe_perzentil"),
                analyst_target=r.get("analyst_target"))

            print("=" * 62)
            print(f"{t}  ({pb})")
            print(f"  Kurs:          {f.get('price')}")
            print(f"  Fair Value:    {fv}")
            if ez:
                print(f"  EIGENES ZIEL:  {ez['ziel']}  "
                      f"(Upside {ez['upside_pct']}%)")
            print(f"  Analystenziel: {r.get('analyst_target')} "
                  f"({r.get('analyst_count')} Analysten)")
            if ez and ez.get("vs_analyst") is not None:
                print(f"  -> eigenes Ziel {ez['vs_analyst']:+.1f}% ggue. Analyst")
            if ez:
                print("  Herleitung:")
                for s in ez.get("herleitung", []):
                    print(f"    - {s}")
            print()
        except Exception as e:
            print(f"{t}: FEHLER {str(e)[:50]}\n")

    print("=" * 62)
    print("PRUEFPUNKTE:")
    print("  - Eigenes Ziel sollte plausibel zwischen Fair Value und (meist)")
    print("    Analystenziel liegen - bei teuren Titeln darunter.")
    print("  - Die Herleitung muss die Abweichung erklaeren.")
    print("  - Kein Ziel sollte absurd weit vom Kurs entfernt sein.")


if __name__ == "__main__":
    main()
