"""
messlatte.py - Etappe 0: Ausgangswert der Entdeckungsschicht festhalten.

    python3 messlatte.py              # Bilanz anzeigen
    python3 messlatte.py --einfrieren # Stand als Vergleichsbasis speichern
    python3 messlatte.py --vergleich  # aktueller Stand gegen den eingefrorenen

Warum das VOR den Aenderungen kommt:
    Screener, Momentum und Radar werden in den naechsten Etappen strenger.
    Die Trefferlisten werden dadurch kuerzer - das fuehlt sich nach Rueckschritt
    an. Ob es einer ist, laesst sich nur sagen, wenn der Ausgangswert
    festgehalten wurde, BEVOR etwas geaendert wurde. Danach ist er nicht mehr
    rekonstruierbar.

Gemessen wird, was trackrecord.py ohnehin schon aufzeichnet. Kein neues
Verfahren, nur eine feste Momentaufnahme.

Wichtig zur Einordnung: Eine Trefferquote ueber wenige Dutzend Signale hat
eine grosse Zufallsspanne. Der Vergleich sagt "besser/schlechter/nicht
unterscheidbar" - das dritte ist das haeufigste Ergebnis und kein Makel.
"""

from __future__ import annotations

import json
import math
import os
import sys
from datetime import datetime

QUELLEN = ["Screener", "Momentum", "Radar"]
DATEI = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "messlatte_basis.json")

#: Unter so vielen ausgewerteten Signalen ist jede Quote Rauschen.
MIN_SIGNALE = 15


def _wilson(treffer: int, n: int, z: float = 1.96) -> tuple:
    """Konfidenzintervall fuer eine Trefferquote (Wilson).

    Ohne Intervall verleitet "62 % Trefferquote" bei 13 Signalen zu Schluessen,
    die die Datenlage nicht traegt. Das Intervall macht sichtbar, wie breit die
    Zufallsspanne wirklich ist.
    """
    if n <= 0:
        return (0.0, 100.0)
    p = treffer / n
    nenner = 1 + z * z / n
    mitte = (p + z * z / (2 * n)) / nenner
    rand = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / nenner
    return (round(max(0.0, mitte - rand) * 100, 1),
            round(min(1.0, mitte + rand) * 100, 1))


def aufnehmen() -> dict:
    """Aktuelle Bilanz je Quelle einsammeln."""
    import trackrecord as tr

    rows = tr.evaluate(limit=500)
    stand = {"zeitpunkt": datetime.now().isoformat(timespec="seconds"),
             "quellen": {}, "gesamt": tr.summary(rows)}

    for q in QUELLEN:
        s = tr.source_stats(q, rows=rows) or {}
        n = s.get("n", 0)
        if n:
            s["ci_win"] = _wilson(s.get("wins", 0), n)
            s["belastbar"] = n >= MIN_SIGNALE
        stand["quellen"][q] = s

    try:
        stand["nach_urteil"] = tr.by_verdict(rows)
    except Exception:
        stand["nach_urteil"] = None
    try:
        stand["trennschaerfe"] = tr.discrimination(rows)
    except Exception:
        stand["trennschaerfe"] = None
    return stand


def zeige(stand: dict, titel: str = "AKTUELLER STAND") -> None:
    print(f"\n{'=' * 72}\n{titel}   ({stand.get('zeitpunkt', '?')})\n{'=' * 72}")
    g = stand.get("gesamt") or {}
    if g.get("n"):
        print(f"  Gesamt: {g['n']} auswertbare Signale \u00b7 "
              f"Trefferquote {g.get('win_pct')} % \u00b7 "
              f"\u00d8 {g.get('avg_ret')} % \u00b7 "
              f"\u00d8 gegen Index {g.get('avg_excess')} %")
    else:
        print("  Noch keine auswertbaren Signale (mind. 14 Tage alt).")

    print(f"\n  {'Quelle':12s} {'n':>4s} {'Treffer':>8s} {'Spanne':>16s} "
          f"{'\u00d8 Rendite':>10s} {'\u00d8 vs. Index':>12s}")
    for q in QUELLEN:
        s = stand["quellen"].get(q) or {}
        if not s.get("n"):
            print(f"  {q:12s} {'-':>4s}   keine Signale")
            continue
        lo, hi = s.get("ci_win", (0, 100))
        marke = "" if s.get("belastbar") else "  (zu wenige)"
        print(f"  {q:12s} {s['n']:>4d} {s.get('win_pct', 0):>7.0f} % "
              f"{f'{lo:.0f}-{hi:.0f} %':>16s} "
              f"{s.get('avg_ret', 0):>9.1f} % "
              f"{(s.get('avg_excess') if s.get('avg_excess') is not None else 0):>11.1f} %"
              f"{marke}")

    t = stand.get("trennschaerfe")
    if t:
        print(f"\n  Trennschaerfe (hoher Score = bessere Rendite?): {t}")


def einfrieren(stand: dict) -> None:
    with open(DATEI, "w", encoding="utf-8") as fh:
        json.dump(stand, fh, indent=2, ensure_ascii=False)
    print(f"\n  Als Vergleichsbasis gespeichert: {DATEI}")
    print("  Diese Datei NICHT ueberschreiben, solange die Umbauten laufen -")
    print("  sonst gibt es nichts mehr, wogegen gemessen werden kann.")


def vergleiche(jetzt: dict) -> None:
    if not os.path.exists(DATEI):
        print("\n  Keine Vergleichsbasis vorhanden. Erst: "
              "python3 messlatte.py --einfrieren")
        return
    with open(DATEI, encoding="utf-8") as fh:
        basis = json.load(fh)

    zeige(basis, "EINGEFRORENE BASIS")
    zeige(jetzt, "JETZT")

    print(f"\n{'=' * 72}\nURTEIL\n{'=' * 72}")
    for q in QUELLEN:
        a = (basis["quellen"].get(q) or {})
        b = (jetzt["quellen"].get(q) or {})
        if not a.get("n") or not b.get("n"):
            print(f"  {q:12s} nicht vergleichbar (zu wenige Signale)")
            continue
        lo_a, hi_a = a.get("ci_win", (0, 100))
        lo_b, hi_b = b.get("ci_win", (0, 100))
        d = b["win_pct"] - a["win_pct"]
        # Ueberlappen die Intervalle, ist der Unterschied nicht belegt.
        ueberlappt = not (lo_b > hi_a or hi_b < lo_a)
        if ueberlappt:
            urteil = "nicht unterscheidbar (Intervalle ueberlappen)"
        elif d > 0:
            urteil = "besser"
        else:
            urteil = "SCHLECHTER"
        print(f"  {q:12s} {a['win_pct']:.0f} % -> {b['win_pct']:.0f} % "
              f"({d:+.0f} Pp.)   {urteil}")

    print("\n  'nicht unterscheidbar' ist bei wenigen Dutzend Signalen das")
    print("  haeufigste Ergebnis und kein Makel - es heisst nur, dass die")
    print("  Datenlage die Aussage noch nicht traegt.")


if __name__ == "__main__":
    try:
        jetzt = aufnehmen()
    except Exception as e:
        print(f"Bilanz konnte nicht erstellt werden: {e}")
        sys.exit(1)

    if "--vergleich" in sys.argv:
        vergleiche(jetzt)
    else:
        zeige(jetzt)
        if "--einfrieren" in sys.argv:
            einfrieren(jetzt)
        else:
            print("\n  Zum Festhalten als Vergleichsbasis:")
            print("     python3 messlatte.py --einfrieren")
