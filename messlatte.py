"""
messlatte.py - Etappe 0: Ausgangswert der Entdeckungsschicht festhalten.

    python3 messlatte.py               # Bilanz anzeigen
    python3 messlatte.py --diagnose    # warum ist die Bilanz leer?
    python3 messlatte.py --einfrieren  # Stand als Vergleichsbasis speichern
    python3 messlatte.py --vergleich   # aktueller Stand gegen den eingefrorenen
    python3 messlatte.py --backtest AAPL MSFT ...   # Ersatzbasis aus Historie

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
BT_DATEI = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "messlatte_backtest.json")
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


# ---------------------------------------------------------------------------
# Diagnose: warum ist die Bilanz leer?
# ---------------------------------------------------------------------------

def diagnose() -> None:
    """Leere Bilanz hat drei moegliche Ursachen - sie sehen gleich aus.

      1. Es wurde nie aufgezeichnet (precompute.py lief nicht)
      2. Aufgezeichnet wurde woanders (Backend Sheet vs. Datei)
      3. Alle Signale sind juenger als 14 Tage

    Ohne diese Unterscheidung sucht man am falschen Ende.
    """
    import store
    print(f"\n{'=' * 72}\nDIAGNOSE\n{'=' * 72}")
    print(f"  Speicher-Backend: {store.backend()}")
    if store.backend() != "sheet":
        print("     Achtung: precompute.py schreibt in dasselbe Backend. Laeuft")
        print("     precompute in der Cloud (Sheet) und dieses Skript lokal")
        print("     (Datei), sieht jedes eine andere Ablage.")

    try:
        roh = store.get_signals() or []
    except Exception as e:
        print(f"  Signale nicht lesbar: {e}")
        return
    print(f"  Signale im Speicher: {len(roh)}")
    if not roh:
        print("\n  -> Es wurde noch nie aufgezeichnet.")
        print("     trackrecord.record() wird AUSSCHLIESSLICH von precompute.py")
        print("     aufgerufen (Zeile ~1537). Ohne precompute-Lauf entsteht")
        print("     kein Tagebuch - die Einzelanalyse und der Screener im")
        print("     Dashboard schreiben nichts mit.")
        print("\n     Zwei Wege:")
        print("       a) precompute.py laufen lassen und ab jetzt aufzeichnen")
        print("          (Ergebnis erst in ~4 Wochen auswertbar)")
        print("       b) Ersatzbasis aus der Historie:")
        print("          python3 messlatte.py --backtest AAPL MSFT NVDA ...")
        return

    from datetime import datetime as _dt
    alter = []
    for e in roh:
        d = e.get("datum") or e.get("date")
        try:
            alter.append((_dt.now() - _dt.fromisoformat(str(d)[:19])).days)
        except Exception:
            continue
    if alter:
        alter.sort()
        reif = sum(1 for a in alter if a >= 14)
        print(f"  Aeltestes {max(alter)} Tage, juengstes {min(alter)} Tage")
        print(f"  Davon mindestens 14 Tage alt: {reif}")
        if reif == 0:
            print("\n  -> Alle Signale sind zu frisch. In "
                  f"{14 - max(alter)} Tagen ist die erste Auswertung moeglich.")
    quellen = {}
    for e in roh:
        quellen[e.get("quelle") or "?"] = quellen.get(e.get("quelle") or "?", 0) + 1
    print(f"  Nach Quelle: {quellen}")


# ---------------------------------------------------------------------------
# Ersatzbasis aus dem Backtest
# ---------------------------------------------------------------------------

def backtest_basis(ticker_liste, von_jahr=2019, bis_jahr=2024,
                   pro_jahr=2) -> dict:
    """Baseline aus der Historie statt aus dem Tagebuch.

    backtest.py spielt die ECHTE fair_value-Logik auf historischen Daten nach,
    mit Schutz gegen Look-ahead (Jahreszahlen gelten erst vier Monate nach
    Geschaeftsjahresende als bekannt). Das ist kein Ersatz fuer echte Signale,
    aber es beantwortet dieselbe Frage - "trifft unsere Bewertung?" - und zwar
    heute statt in vier Wochen.

    Wichtige Einschraenkung: Der Backtest misst die BEWERTUNG, nicht die
    Auswahl. Er sagt nichts darueber, ob Screener oder Radar die richtigen
    Titel vorgeschlagen haetten - nur, ob der Fair Value fuer die
    uebergebenen Titel getragen hat.
    """
    import backtest as bt
    import roic
    import valuation

    if not roic.enabled():
        return {"fehler": "roic inaktiv - Backtest braucht Kurs- und "
                          "Jahreshistorie"}

    stichtage = bt.jahres_stichtage(von_jahr, bis_jahr, pro_jahr)
    alle = []
    for i, t in enumerate(ticker_liste, 1):
        try:
            zeilen = bt.einzeltest(roic, valuation, t, stichtage)
        except Exception as e:
            print(f"  [{i}/{len(ticker_liste)}] {t}: Fehler {e}")
            continue
        alle.extend(zeilen)
        print(f"  [{i}/{len(ticker_liste)}] {t}: {len(zeilen)} Stichtage")

    if not alle:
        return {"fehler": "keine auswertbaren Stichtage"}

    erg = bt.auswertung(alle)
    return {"zeitpunkt": datetime.now().isoformat(timespec="seconds"),
            "titel": list(ticker_liste), "stichtage": len(stichtage),
            "zeilen": len(alle), "auswertung": erg}


def zeige_backtest(b: dict) -> None:
    print(f"\n{'=' * 72}\nERSATZBASIS AUS DER HISTORIE\n{'=' * 72}")
    if b.get("fehler"):
        print(f"  {b['fehler']}")
        return
    a = b.get("auswertung") or {}
    print(f"  {len(b['titel'])} Titel \u00b7 {b['stichtage']} Stichtage \u00b7 "
          f"{b['zeilen']} auswertbare Zeilen")
    for k, v in a.items():
        if isinstance(v, (int, float, str)) or v is None:
            print(f"    {k:28s} {v}")
    print("\n  Das misst die BEWERTUNG, nicht die Auswahl - ob Screener und")
    print("  Radar die richtigen Titel vorgeschlagen haetten, sagt es nicht.")


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
    if "--diagnose" in sys.argv:
        diagnose()
        sys.exit(0)

    if "--backtest" in sys.argv:
        i = sys.argv.index("--backtest")
        titel = [a.upper() for a in sys.argv[i + 1:] if not a.startswith("--")]
        if not titel:
            print("  Titel angeben: python3 messlatte.py --backtest AAPL MSFT ...")
            sys.exit(1)
        b = backtest_basis(titel)
        zeige_backtest(b)
        if not b.get("fehler"):
            with open(BT_DATEI, "w", encoding="utf-8") as fh:
                json.dump(b, fh, indent=2, ensure_ascii=False)
            print(f"\n  Gespeichert: {BT_DATEI}")
        sys.exit(0)

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
            if not (jetzt.get("gesamt") or {}).get("n"):
                print("\n  Bilanz ist leer. Ursache finden:")
                print("     python3 messlatte.py --diagnose")
