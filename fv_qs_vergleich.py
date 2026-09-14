#!/usr/bin/env python3
"""
fv_qs_vergleich.py - Qualitaetssicherung fuer die ausgeduennten Bewertungs-
modelle. Vergleicht den Fair Value der NEUEN Gewichtung (3 Kernmethoden +
Analyst 15%) gegen die ALTE fuer eine Liste echter Aktien.

Zeigt je Aktie: alter FV, neuer FV, Differenz, und wie viele Methoden jeweils
genutzt wurden. So siehst du schwarz auf weiss, ob der neue Fair Value
plausibler ist oder ob einzelne Titel auffaellig abweichen.

AUFRUF (PowerShell im value_radar-Ordner):
    $env:ROIC_API_KEY="dein_key"; python fv_qs_vergleich.py

Optional eigene Ticker:
    python fv_qs_vergleich.py AAPL MSFT SAP.DE JPM XOM
"""
import sys
import copy

# Standard-Testkorb: verschiedene Typen (Quality, Wachstum, Zykliker, Bank)
STANDARD = ["AAPL", "MSFT", "GOOGL", "META", "NVDA",      # Quality/Growth
            "JPM", "BAC", "ALV.DE",                        # Financial
            "XOM", "CVX", "BAS.DE",                        # Cyclical/Energy
            "SAP.DE", "ASML", "V", "MA"]                   # Quality


# --- ALTE Gewichte (vor der Ausduennung) - zum Vergleich fest hinterlegt ----
ALTE_WEIGHTS = {
    "quality":    {"justified_pe": .15, "fwd_composite": .20, "dcf": .15, "epv": .05,
                   "ev_ebitda": .10, "hist_pe": .10, "analyst": .25},
    "inflection": {"fwd_pe": .15, "fwd_composite": .20, "dcf": .15, "justified_pe": .10,
                   "analyst": .40},
    "cyclical":   {"ev_ebitda": .25, "pb": .20, "epv": .15, "justified_pe": .15,
                   "analyst": .25},
    "financial":  {"justified_pe": .30, "pb": .30, "fwd_pe": .10, "hist_pe": .05,
                   "analyst": .25},
}


def main():
    ticker = sys.argv[1:] or STANDARD
    try:
        import providers
        import valuation as val
    except Exception as e:
        print(f"Import fehlgeschlagen: {e}")
        return

    neu_weights = copy.deepcopy(val._WEIGHTS)   # aktuelle (neue) Gewichte

    print(f"{'Ticker':<9} {'Typ':<11} {'Kurs':>8} {'FV alt':>8} "
          f"{'FV neu':>8} {'Diff%':>7} {'n_alt':>5} {'n_neu':>5}")
    print("-" * 72)

    _summe_abw = 0.0
    _n = 0
    for t in ticker:
        try:
            f = providers.get_fundamentals(t, deep=True)
            if not f or not f.get("price"):
                print(f"{t:<9} (keine Daten)")
                continue
            pb = val.classify_playbook(f)
            price = f.get("price")

            # NEU (aktuelle Gewichte)
            r_neu = val.fair_value(f, None, pb)
            fv_neu = r_neu.get("fair_value")
            n_neu = r_neu.get("n_methods")

            # ALT: kurz die alten Gewichte einsetzen, dann zuruecksetzen
            val._WEIGHTS = ALTE_WEIGHTS
            r_alt = val.fair_value(f, None, pb)
            fv_alt = r_alt.get("fair_value")
            n_alt = r_alt.get("n_methods")
            val._WEIGHTS = neu_weights          # zuruecksetzen

            if fv_alt and fv_neu:
                diff = (fv_neu / fv_alt - 1) * 100
                _summe_abw += abs(diff)
                _n += 1
                print(f"{t:<9} {pb:<11} {price:>8.2f} {fv_alt:>8.2f} "
                      f"{fv_neu:>8.2f} {diff:>+6.1f}% {n_alt:>5} {n_neu:>5}")
            else:
                print(f"{t:<9} {pb:<11} {price:>8.2f} "
                      f"{'n/a' if not fv_alt else fv_alt:>8} "
                      f"{'n/a' if not fv_neu else fv_neu:>8}")
        except Exception as e:
            print(f"{t:<9} FEHLER: {str(e)[:40]}")

    print("-" * 72)
    if _n:
        print(f"Durchschnittliche Abweichung alt->neu: "
              f"{_summe_abw / _n:.1f}% ueber {_n} Titel")
        print()
        print("Interpretation:")
        print("  < 3%  : Ausduennung aendert kaum etwas - Fair Value war robust,")
        print("          Gewinn liegt in Einfachheit/Nachvollziehbarkeit.")
        print("  3-8%  : spuerbare Verschiebung, meist weil Analyst-Gewicht sank")
        print("          (Fair Value naeher an den Fundamentaldaten).")
        print("  > 8%  : bei einzelnen Titeln pruefen, welche Methode wegfiel.")


if __name__ == "__main__":
    main()
