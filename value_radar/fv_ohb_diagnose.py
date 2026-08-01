#!/usr/bin/env python3
"""
fv_ohb_diagnose.py - Schluesselt auf, WORAUF der Fair Value einer Aktie beruht.

Gedacht fuer den OHB.DE-Fall: Warum liegt der Fair Value bei 86 EUR, obwohl
gute Nachrichten (Joint Ventures, KKR-Programm, Auftragsbestand) vorliegen?

Zeigt: jede Bewertungsmethode mit ihrem Wert, Analystenzahl und -ziel,
Konfidenz, sowie die zugrundeliegenden Kennzahlen (Umsatz-/Gewinnwachstum,
KGV etc.). So siehst du, ob der Fair Value konservativ-korrekt, schlecht
informiert (duenne Daten) oder veraltet (Schaetzungen noch nicht angepasst)
ist.

AUFRUF (PowerShell im value_radar-Ordner):
    $env:ROIC_API_KEY="dein_key"; python fv_ohb_diagnose.py
    python fv_ohb_diagnose.py OHB.DE
"""
import sys


def main():
    ticker = sys.argv[1] if len(sys.argv) > 1 else "OHB.DE"
    try:
        import providers
        import valuation as val
    except Exception as e:
        print(f"Import fehlgeschlagen: {e}")
        return

    print(f"Fair-Value-Diagnose fuer {ticker}\n" + "=" * 60)
    f = providers.get_fundamentals(ticker, deep=True)
    if not f:
        print("Keine Fundamentaldaten erhalten.")
        return

    print(f"\nKurs:            {f.get('price')}")
    print(f"Name:            {f.get('name')}")
    print(f"Sektor:          {f.get('sector')}")
    print(f"Waehrung:        {f.get('currency')}")

    print("\n--- Kennzahlen, auf denen der Fair Value beruht ---")
    for k, label in [("revenue_growth", "Umsatzwachstum"),
                     ("earnings_growth", "Gewinnwachstum"),
                     ("pe_ttm", "KGV (ttm)"),
                     ("forward_pe", "KGV (forward)"),
                     ("hist_pe_median", "hist. KGV-Median"),
                     ("eps_ttm", "EPS (ttm)"),
                     ("eps_forward", "EPS (forward)"),
                     ("book_value", "Buchwert/Aktie"),
                     ("ebitda", "EBITDA"),
                     ("analyst_target", "Analysten-Kursziel"),
                     ("analyst_count", "Anzahl Analysten")]:
        v = f.get(k)
        print(f"  {label:<22}: {v}")

    print("\n--- Fair Value nach Methoden ---")
    pb = val.classify_playbook(f)
    print(f"  Playbook-Typ: {pb}")
    r = val.fair_value(f, None, pb)
    print(f"\n  METHODEN-EINZELWERTE:")
    methoden = r.get("methods") or r.get("all_methods") or {}
    if methoden:
        for name, wert in methoden.items():
            print(f"    {name:<18}: {wert}")
    else:
        print("    (Methoden-Einzelwerte nicht im Rueckgabeobjekt - "
              "zeige Kernfelder)")
        for k in ("model_fair_value", "analyst_target", "fair_value"):
            print(f"    {k:<18}: {r.get(k)}")

    print(f"\n  FAIR VALUE (gewichtet): {r.get('fair_value')}")
    print(f"  Modell-FV (ohne Analyst-Extra): {r.get('model_fair_value')}")
    print(f"  Konfidenz:      {r.get('confidence')}")
    print(f"  Verlaesslich:   {r.get('reliable')}")
    print(f"  Analystenzahl:  {r.get('analyst_count')}")
    print(f"  Methoden genutzt: {r.get('n_methods')}")
    dv = r.get("model_vs_analyst_pct")
    if dv is not None:
        print(f"  Modell vs. Analyst: {dv:+.0f}%")

    print("\n" + "=" * 60)
    print("SO LIEST DU DAS ERGEBNIS:")
    print("  - Wenige Analysten (< 4) + niedrige Konfidenz")
    print("      -> duenne Datenlage, Fair Value mit Vorsicht geniessen.")
    print("  - analyst_target noch auf altem Niveau trotz guter News")
    print("      -> Schaetzungen noch nicht angepasst (bei Nebenwerten normal).")
    print("  - Modell-FV deutlich unter Kurs, Analyst nah am Kurs")
    print("      -> Markt/Analysten preisen Zukunft ein, die harten Zahlen")
    print("         (noch) nicht. Der Fair Value ist dann bewusst konservativ.")
    print("  - Auftragsbestand/JV stehen NIE direkt im Fair Value - erst wenn")
    print("    sie als Umsatz/Gewinn in den Zahlen landen.")


if __name__ == "__main__":
    main()
