#!/usr/bin/env python3
"""
marktkontext_qs.py - Qualitaetssicherung fuer die neue Marktkontext-Ebene.

Zeigt fuer eine Liste echter Aktien:
  - den Fair Value und den Kurs
  - den Fair-Value-Abstand (Markt vs. Fundamentaldaten)
  - das KGV-Perzentil in der eigenen Historie
  - die kombinierte Einordnung
und einmal das aktuelle Marktregime (Trend/VIX/Drawdown).

So pruefst du, ob die Einordnung plausibel ist - besonders der wichtige Fall:
Aktie ueber Fair Value, aber historisch normal bewertet (darf NICHT als
'teuer auf beiden Ebenen' erscheinen).

AUFRUF (PowerShell im value_radar-Ordner):
    $env:ROIC_API_KEY="dein_key"; python marktkontext_qs.py
    python marktkontext_qs.py AAPL MSFT KO JPM XOM
"""
import sys

STANDARD = ["AAPL", "MSFT", "GOOGL", "META", "NVDA", "KO", "JPM", "XOM",
            "SAP.DE", "V"]


def main():
    ticker = sys.argv[1:] or STANDARD
    try:
        import providers
        import valuation as val
        import regime as reg
    except Exception as e:
        print(f"Import fehlgeschlagen: {e}")
        return

    # --- Marktregime einmal global ---
    print("=" * 70)
    print("MARKTREGIME (Gesamtmarkt)")
    print("=" * 70)
    try:
        mr = reg.markt_regime()
        if mr:
            amp = {"gruen": "GRUEN", "gelb": "GELB", "rot": "ROT"}.get(
                mr["ampel"], "?")
            print(f"Ampel: {amp}  ({mr['text']}, Punkte {mr['punkte']})")
            for x in mr.get("faktoren", []):
                print(f"  - {x}")
        else:
            print("kein Marktregime abrufbar")
    except Exception as e:
        print(f"FEHLER Marktregime: {e}")

    # --- Je Aktie die Bewertungs-Einordnung ---
    print("\n" + "=" * 70)
    print("BEWERTUNGS-EINORDNUNG JE AKTIE")
    print("=" * 70)
    for t in ticker:
        try:
            f = providers.get_fundamentals(t, deep=True)
            if not f or not f.get("price"):
                print(f"\n{t}: keine Daten")
                continue
            pb = val.classify_playbook(f)
            r = val.fair_value(f, None, pb)
            fv = r.get("fair_value")
            bk = reg.bewertungs_kontext(f, fair_value=fv)
            print(f"\n{t}  ({pb})")
            print(f"  Kurs {f.get('price'):.2f}  |  Fair Value "
                  f"{fv:.2f}" if fv else f"  Kurs {f.get('price'):.2f}  |  FV n/a")
            print(f"  FV-Abstand:   {bk.get('fv_abstand')}%")
            print(f"  KGV-Perzentil: {bk.get('pe_perzentil')} "
                  f"({bk.get('pe_lage')})")
            print(f"  Einordnung:   {bk.get('gesamt')}")
        except Exception as e:
            print(f"\n{t}: FEHLER {str(e)[:50]}")

    print("\n" + "=" * 70)
    print("PRUEFPUNKTE:")
    print("  1. Aktien ueber Fair Value MIT hohem KGV-Perzentil (>=80) sollten")
    print("     'teuer auf beiden Ebenen' zeigen.")
    print("  2. Aktien ueber Fair Value ABER normalem KGV-Perzentil (40-60)")
    print("     duerfen das NICHT zeigen - nur die neutrale Einordnung.")
    print("  3. Das Marktregime sollte zur allgemeinen Marktlage passen.")


if __name__ == "__main__":
    main()
