"""
test_stabilitaet.py - Liefert derselbe Titel zweimal denselben Fair Value?

    python3 test_stabilitaet.py META ADBE NVDA

Ruft jeden Titel MEHRFACH ab und vergleicht Fair Value und Rechengrundlage.
Weicht etwas ab, wird benannt WAS - nicht nur DASS.

Gedacht fuer genau den Fall "Meta zeigte +20 %, nach dem Neustart +4 %".
"""

import sys

import providers
import valuation


def einmal(t):
    f = providers.get_fundamentals(t, deep=True) or {}
    if not f.get("price"):
        return None, None
    p = valuation.classify_playbook(f)
    return f, valuation.fair_value(dict(f), None, p)


def main(t, laeufe=3):
    print(f"\n{'=' * 72}\n{t}\n{'=' * 72}")
    ergebnisse = []
    for i in range(laeufe):
        providers._DEEP_CACHE = {} if hasattr(providers, "_DEEP_CACHE") else None
        f, v = einmal(t)
        if not v:
            print(f"  Lauf {i + 1}: keine Daten")
            continue
        ergebnisse.append((f, v))
        luecken = f.get("_luecke_anreicherung") or []
        if i == 0:
            try:
                import store as _s
                print(f"     Berichtsmarker: {_s.anreicherung_marker(f)}"
                      f"  (aendert sich mit jedem Quartalsbericht und "
                      f"verwirft dann den Zwischenspeicher)")
            except Exception:
                pass
        print(f"  Lauf {i + 1}: FV {v['fair_value']:>9.2f}  "
              f"Upside {v['upside_pct']:+7.1f} %  "
              f"Playbook {v.get('playbook', '?'):11s} "
              f"Methoden {len(v.get('methods') or {})}"
              + (f"  Anreicherung fehlt: {', '.join(luecken)}" if luecken else ""))

    if len(ergebnisse) < 2:
        return
    werte = [v["fair_value"] for _, v in ergebnisse if v.get("fair_value")]
    spanne = (max(werte) - min(werte)) / min(werte) * 100 if werte else 0
    print(f"\n  Spanne ueber {len(werte)} Laeufe: {spanne:.2f} %")
    if spanne < 0.5:
        print("  STABIL.")
        return
    print("  INSTABIL - Ursache:")
    basis0 = ergebnisse[0][1].get("basis")
    for i, (_, v) in enumerate(ergebnisse[1:], start=2):
        d = valuation.basis_vergleich(v.get("basis"), basis0)
        if d:
            for txt in d["texte"]:
                print(f"     Lauf {i}: {txt}")
        else:
            print(f"     Lauf {i}: gleiche Grundlage - die Bewegung ist echt "
                  f"(Kurs oder Datenaktualisierung).")


if __name__ == "__main__":
    for t in (sys.argv[1:] or ["META", "ADBE", "NVDA"]):
        main(t.upper())
