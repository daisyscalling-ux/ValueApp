"""
pruefe_sektor.py - Warum steht in der Segment-Karte noch nichts?

    python3 pruefe_sektor.py

Die Kette hat fuenf Glieder, und jedes kann still reissen:

    1. sektor.py liegt im Repo          -> sonst Import-Fehler im Nachtlauf
    2. precompute ruft die Messung auf  -> sonst wird nie gemessen
    3. Titel haben Sektor + Multiples   -> sonst kein Median
    4. Der Schreibvorgang geht durch    -> Google Sheet kann ablehnen
    5. Die App liest denselben Speicher -> Datei gegen Sheet

Dieses Skript prueft alle fuenf und sagt, an welchem es haengt.
"""

from __future__ import annotations

__version__ = "2026.09.25"

import sys


def main() -> int:
    print(f"\n{'=' * 70}\nSEKTORMESSUNG - Kette pruefen\n{'=' * 70}")

    # --- 1) Modul vorhanden ------------------------------------------
    try:
        import sektor as S
        print(f"  1. sektor.py            vorhanden (Version {S.__version__})")
    except Exception as e:
        print(f"  1. sektor.py            FEHLT oder defekt: {e}")
        print("\n     -> Datei ins Repo legen und pushen. Ohne sie meldet der")
        print("        Nachtlauf '[sektor] Modul nicht ladbar' und macht weiter.")
        return 1

    # --- 2) precompute ruft auf --------------------------------------
    try:
        import precompute as P
        hat = hasattr(P, "sektormediane_schreiben")
        ruft = "sektormediane_schreiben()" in open(
            "precompute.py", encoding="utf-8").read()
        print(f"  2. precompute.py        Funktion {'ja' if hat else 'NEIN'}, "
              f"Aufruf in run() {'ja' if ruft else 'NEIN'}")
        if not (hat and ruft):
            print("\n     -> Die neue precompute.py ist nicht im Repo. Genau das")
            print("        erklaert erfolgreiche Laeufe ohne Ergebnis: Der Lauf")
            print("        macht alles wie bisher, nur eben ohne die Messung.")
            return 1
    except Exception as e:
        print(f"  2. precompute.py        nicht pruefbar: {e}")

    # --- 3) Speicher-Backend -----------------------------------------
    import store
    print(f"  3. Speicher-Backend     {store.backend()}")
    if store.backend() == "file":
        print("     Achtung: Der Nachtlauf in GitHub schreibt ins Google Sheet")
        print("     (GSHEET_ID gesetzt). Laeuft dieses Skript lokal gegen eine")
        print("     Datei, sieht es die Ergebnisse des Nachtlaufs NICHT.")

    # --- 4) Was liegt im Speicher? -----------------------------------
    try:
        aux = store._load_aux().get("anreicherung", {})
    except Exception as e:
        print(f"  4. Speicher            nicht lesbar: {e}")
        return 1
    mediane = {k: v for k, v in aux.items() if k.startswith("sektormedian:")}
    index = {k: v for k, v in aux.items() if k.startswith("sektorindex:")}
    print(f"  4. Gespeicherte Gruppen {len(mediane)}   Index-Eintraege {len(index)}")

    if not mediane:
        print("\n     -> Es wurde noch nie erfolgreich geschrieben.")
        print("        Moegliche Gruende, in dieser Reihenfolge:")
        print("          a) Der Nachtlauf lief mit der ALTEN precompute.py")
        print("          b) Kein Titel hatte Sektor UND Multiples (min. 6 je Gruppe)")
        print("          c) Das Schreiben ins Sheet schlug fehl - im Protokoll")
        print("             steht dann '[sektor] Schreiben fehlgeschlagen'")
        return 1

    # --- 5) Inhalt ----------------------------------------------------
    print(f"\n{'=' * 70}\nINHALT\n{'=' * 70}")
    for ebene in ("sector", "segment"):
        gruppen = S._index_lesen(ebene)
        if not gruppen:
            print(f"\n  {ebene}: kein Index")
            continue
        print(f"\n  {ebene}: {len(gruppen)} Gruppen")
        print(f"    {'Gruppe':26s} {'heute':>7s} {'Messungen':>10s}  Stand")
        for g in gruppen:
            reihe = S.lade_reihe(g, ebene)
            v = S.vergleich(g, "ev_ebitda", ebene)
            letzte = reihe[-1]["datum"] if reihe else "-"
            heute = v.get("heute")
            print(f"    {g[:26]:26s} "
                  f"{(f'{heute:6.1f}x' if heute else '     -'):>7s} "
                  f"{len(reihe):10d}  {letzte}")

    n_reif = sum(1 for eb in ("sector", "segment") for g in S._index_lesen(eb)
                 if len(S.lade_reihe(g, eb)) >= S.MIN_MESSUNGEN)
    print(f"\n  {n_reif} Gruppen haben {S.MIN_MESSUNGEN}+ Messungen und zeigen")
    print(f"  den Vergleich mit dem eigenen Schnitt. Der Rest zeigt nur den")
    print(f"  aktuellen Stand - das ist richtig so, nicht kaputt.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
