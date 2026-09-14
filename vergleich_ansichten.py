"""
vergleich_ansichten.py - Warum zeigen zwei Ansichten verschiedene Upsides?

    python3 vergleich_ansichten.py NVDA

Ruft denselben Titel auf BEIDEN Wegen ab, die das Dashboard nutzt:
  * deep=True   (Einzelanalyse, Portfolio, Watchlist)
  * deep=False  (Vergleichstabellen, precompute-Scan)
und stellt Felder, Playbook und Fair Value gegenueber.

Zusaetzlich wird der deep-Abruf ZWEIMAL gemacht. Weicht er von sich selbst ab,
ist eine Quelle unzuverlaessig (meist yfinance) - und dann haengt es nur vom
Aufrufzeitpunkt ab, welchen Wert eine Oberflaeche sieht.
"""

import sys

import providers
import valuation

WICHTIG = ["price", "currency", "eps_forward", "eps_trailing", "target_mean",
           "analyst_count", "revenue_growth", "earnings_growth", "beta",
           "free_cashflow", "ebitda", "book_value_ps", "hist_pe_median",
           "ev_ebitda", "pb", "_roic", "_vollstaendig", "data_sources"]


def hole(t, deep):
    f = providers.get_fundamentals(t, deep=deep) or {}
    if not f.get("price"):
        return f, None, None
    p = valuation.classify_playbook(f)
    v = valuation.fair_value(dict(f), None, p)
    return f, p, v


def zeile(name, a, b, c=None):
    sp = f"{str(a):>18s} {str(b):>18s}"
    if c is not None:
        sp += f" {str(c):>18s}"
    print(f"   {name:20s} {sp}")


def main(t):
    print(f"{'=' * 84}\n{t}: deep=True gegen deep=False\n{'=' * 84}")
    f1, p1, v1 = hole(t, True)
    f2, p2, v2 = hole(t, False)
    f3, p3, v3 = hole(t, True)          # zweiter deep-Abruf: stabil?

    print(f"\n{'':23s}{'deep=True':>18s} {'deep=False':>18s} {'deep=True (2.)':>18s}")
    for k in WICHTIG:
        a, b, c = f1.get(k), f2.get(k), f3.get(k)
        fmt = lambda x: ("--" if x in (None, "") else
                         (f"{x:,.2f}".replace(",", " ") if isinstance(x, float) else x))
        zeile(k, fmt(a), fmt(b), fmt(c))

    print()
    zeile("Playbook", p1 or "--", p2 or "--", p3 or "--")
    zeile("Fair Value", (v1 or {}).get("fair_value", "--"),
          (v2 or {}).get("fair_value", "--"), (v3 or {}).get("fair_value", "--"))
    zeile("Upside %", (v1 or {}).get("upside_pct", "--"),
          (v2 or {}).get("upside_pct", "--"), (v3 or {}).get("upside_pct", "--"))
    zeile("Methoden", len((v1 or {}).get("methods") or {}),
          len((v2 or {}).get("methods") or {}), len((v3 or {}).get("methods") or {}))

    print("\nBefund:")
    if v1 and v3 and v1.get("fair_value") != v3.get("fair_value"):
        print("   INSTABIL: zwei Abrufe desselben Pfades liefern verschiedene Werte.")
        for k in WICHTIG:
            if f1.get(k) != f3.get(k):
                print(f"     abweichend: {k}  {f1.get(k)}  ->  {f3.get(k)}")
        print("   Welche Zahl eine Oberflaeche zeigt, haengt damit nur vom "
              "Aufrufzeitpunkt ab.")
    elif v1 and v2 and v1.get("fair_value") != v2.get("fair_value"):
        print("   Die beiden Pfade sehen verschiedene Daten - erwartbar, aber die "
              "Differenz sollte klein sein:")
        for k in WICHTIG:
            if f1.get(k) != f2.get(k):
                print(f"     {k}:  deep={f1.get(k)}   flach={f2.get(k)}")
    else:
        print("   Beide Pfade stimmen ueberein.")

    for label, f in (("deep=True", f1), ("deep=False", f2)):
        if f.get("_luecke_prognose"):
            print(f"   {label}: Prognosefelder fehlen -> "
                  f"{', '.join(f['_luecke_prognose'])}  "
                  f"(im inflection-Playbook 70 % Methodengewicht)")


if __name__ == "__main__":
    for t in (sys.argv[1:] or ["NVDA"]):
        main(t.upper())
