"""
audit_zweige.py - Welche Verzweigung wurde je genommen?

    python3 audit_zweige.py valuation --titel 40
    python3 audit_zweige.py kandidat screener2 --titel 40

Findet Muster M5 aus dem Audit-Plan: stille Wirkungslosigkeit.

    Das Reverse-DCF-Gate durfte bei 30 von 30 Titeln nicht greifen. Von aussen
    sah das genauso aus wie ein Gate, das nichts zu beanstanden hatte - erst
    ein Zaehler hat es sichtbar gemacht. Dasselbe gilt fuer jede Bedingung im
    Code: Ein Zweig, der bei 40 verschiedenen Titeln NIE genommen wird, ist
    entweder toter Code oder eine Regel, die nicht greift. Beides muss man
    wissen.

    Umgekehrt genauso: Ein Zweig, der IMMER genommen wird, ist keine
    Fallunterscheidung, sondern eine verkleidete Konstante.

Arbeitet mit sys.settrace ueber den eingefrorenen Datensatz aus
audit_harness.py - also ohne Netz und wiederholbar.
"""

from __future__ import annotations

__version__ = "2026.09.23"

import ast
import os
import sys
from collections import defaultdict


def _zweigzeilen(modul: str) -> dict:
    """Alle Zeilen, die eine Verzweigung eroeffnen, mit Quelltext."""
    pfad = modul if modul.endswith(".py") else modul + ".py"
    src = open(pfad, encoding="utf-8").read()
    zeilen = src.split("\n")
    out = {}
    for n in ast.walk(ast.parse(src)):
        if isinstance(n, (ast.If, ast.While, ast.For, ast.Try)):
            nr = n.lineno
            out[nr] = zeilen[nr - 1].strip()[:88]
        elif isinstance(n, ast.ExceptHandler):
            out[n.lineno] = zeilen[n.lineno - 1].strip()[:88]
    return out


def messen(module: list, arbeit) -> dict:
    """Fuehrt `arbeit` aus und zaehlt ausgefuehrte Zeilen je Modul."""
    pfade = {}
    for m in module:
        p = os.path.abspath(m if m.endswith(".py") else m + ".py")
        pfade[p] = m.replace(".py", "")
    getroffen = defaultdict(set)

    def tracer(frame, event, arg):
        if event == "line":
            p = frame.f_code.co_filename
            if p in pfade:
                getroffen[pfade[p]].add(frame.f_lineno)
        return tracer

    sys.settrace(tracer)
    try:
        arbeit()
    finally:
        sys.settrace(None)
    return {m: getroffen[m] for m in pfade.values()}


def bericht(module: list, getroffen: dict, n_titel: int) -> int:
    gesamt_tot = 0
    for m in module:
        name = m.replace(".py", "")
        zweige = _zweigzeilen(name)
        traf = getroffen.get(name, set())
        nie = {nr: txt for nr, txt in zweige.items() if nr not in traf}
        print(f"\n{'=' * 74}\n{name}.py \u00b7 {len(zweige)} Verzweigungen, "
              f"{len(zweige) - len(nie)} genommen, {len(nie)} nie\n{'=' * 74}")
        if not nie:
            print("  Alle Verzweigungen wurden mindestens einmal genommen.")
            continue
        gesamt_tot += len(nie)
        # Nach Zeilennummer, damit man sie im Editor abarbeiten kann
        for nr, txt in sorted(nie.items()):
            print(f"  Zeile {nr:5d}  {txt}")
        print(f"\n  Diese {len(nie)} Zweige wurden bei {n_titel} verschiedenen "
              f"Titeln nie genommen.")
        print("  Moegliche Gruende, in dieser Reihenfolge zu pruefen:")
        print("    1. Die Bedingung kann nie zutreffen (Denkfehler)")
        print("    2. Der Datensatz deckt den Fall nicht ab (Datensatz erweitern)")
        print("    3. Toter Code aus einer frueheren Fassung (loeschen)")
    return gesamt_tot


def _standardarbeit(n_titel: int):
    """Bewertet die Titel des eingefrorenen Datensatzes."""
    import audit_harness as h
    import kandidat as kd
    import valuation as V

    funds = h.alle_funds(tief=True)
    ticker = list(funds)[:n_titel]

    def arbeit():
        for t in ticker:
            f = funds[t]
            if not f.get("price"):
                continue
            try:
                p = V.classify_playbook(f)
                v = V.fair_value(dict(f), None, p)
                anker = V.anker_aus_fund(f, historie=None)
                if sum(1 for k in anker if not k.startswith("_")
                       and anker.get(k) is not None) >= 2:
                    V.reverse_dcf_analyse(f, anker, p, mit_gitter=False)
                k = kd.Kandidat(ticker=t)
                k.fund, k.bewertung = f, v
                k.qualitaet = dict(v.get("datenqualitaet") or {})
                for profil in ("value", "momentum", "fruehphase"):
                    kd.gate_pruefen(k, profil)
            except Exception:
                pass
    return arbeit, len(ticker)


if __name__ == "__main__":
    module = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not module:
        print(__doc__)
        sys.exit(0)
    n = 40
    if "--titel" in sys.argv:
        n = int(sys.argv[sys.argv.index("--titel") + 1])
    try:
        arbeit, n_titel = _standardarbeit(n)
    except FileNotFoundError as e:
        print(f"  {e}")
        sys.exit(1)
    getroffen = messen(module, arbeit)
    tot = bericht(module, getroffen, n_titel)
    print(f"\n{'=' * 74}\n  {tot} nie genommene Verzweigungen insgesamt.")
