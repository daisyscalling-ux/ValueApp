"""
pruefe_beneish.py - Warum meldet Beneish bei diesem Titel Verdacht?

    python3 pruefe_beneish.py NVDA LLY WDC

Zeigt alle acht Indizes, ihren Beitrag zum M-Wert und die Entscheidung, ob es
sich um ein Wachstumsartefakt oder einen echten Verdacht handelt.

Hintergrund: Der Umsatzwachstumsindex SGI geht mit 0,892 in die Formel ein.
Eine Firma mit verdoppeltem Umsatz bekommt daraus fast einen ganzen Punkt -
ohne dass an der Bilanz irgendetwas auffaellig waere. Der eigentliche
Manipulationstest ist TATA: Gewinn, der nicht durch operativen Cashflow
gedeckt ist.
"""

import sys

import roic
import scores

GEWICHTE = {"DSRI": 0.92, "GMI": 0.528, "AQI": 0.404, "SGI": 0.892,
            "DEPI": 0.115, "SGAI": -0.172, "TATA": 4.679, "LVGI": -0.327}


def main(t: str) -> None:
    print(f"\n{'=' * 68}\n{t}\n{'=' * 68}")
    if not roic.enabled():
        print("  roic inaktiv - ohne Jahresabschluesse kein Beneish.")
        return
    try:
        inc = roic.income_annual(t, limit=3) or []
        bal = roic.balance_annual(t, limit=3) or []
        cf = roic.cashflow_annual(t, limit=3) or []
        akt, vor = scores.jahres_paar(inc, bal, cf)
    except Exception as e:
        print(f"  Jahresabschluesse nicht ladbar: {e}")
        return
    if not akt or not vor:
        print("  Kein vollstaendiges Jahrespaar.")
        return

    b = scores.beneish_m(akt, vor)
    if not b:
        print("  Beneish nicht berechenbar (Finanzwert oder Daten fehlen).")
        return

    print(f"  M = {b['m']}   Warnschwelle -2,22 · Standardgrenze -1,78   verdaechtig: {b['verdaechtig']}")
    print(f"  wachstumsgetrieben: {b.get('wachstumsgetrieben')}   "
          f"Gewinn cashgedeckt: {b.get('tata_unauffaellig')}")
    print(f"\n  {'Index':6s} {'Wert':>8s} {'Gewicht':>8s} {'Beitrag':>9s}")
    teile = b.get("teile") or {}
    for k, w in GEWICHTE.items():
        v = teile.get(k)
        if v is None:
            continue
        print(f"  {k:6s} {v:8.3f} {w:8.3f} {v * w:9.3f}"
              + ("   <- Treiber" if k in (b.get("treiber") or []) else ""))
    print(f"\n  Urteil: ", end="")
    if not b["verdaechtig"]:
        print("unauffaellig")
    elif b.get("wachstumsgetrieben"):
        print("Verdacht durch Wachstum/Investitionen erklaert - kein Ausschluss")
    else:
        print(f"echter Bilanzverdacht (Treiber: {', '.join(b.get('treiber') or [])})")


if __name__ == "__main__":
    for t in (sys.argv[1:] or ["NVDA"]):
        main(t.upper())
