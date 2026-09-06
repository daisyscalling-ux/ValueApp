"""
audit_konstanten.py - Jede Zahl im Rechenweg sichtbar machen.

    python3 audit_konstanten.py valuation.py
    python3 audit_konstanten.py valuation.py roic.py --csv befund.csv
    python3 audit_konstanten.py --alle          # alle Kernmodule

Warum das der erste Schritt ist:

    Der Plausibilitaetsfilter stand bei "0.25 * price" - eine Zahl, die die
    Annahme enthaelt, der Markt habe ungefaehr recht. Bei einem Zykliker am
    Gewinngipfel ist das genau verkehrt, und es hat 80 % des Methodengewichts
    verworfen. Die Zahl stand seit jeher im Code, unbegruendet und unbemerkt.

    Beneish prueft gegen -2.22, waehrend die Standardgrenze der Originalarbeit
    -1.78 ist. Eine Ziffer Unterschied, und Eli Lilly fiel durch.

    Solche Zahlen sind die dichteste Fehlerquelle ueberhaupt, weil sie
    Annahmen sind, die wie Code aussehen. Dieses Werkzeug listet sie auf,
    damit jede einzelne eine Begruendung bekommt.

Was NICHT gemeldet wird: 0, 1, -1, 2 und 100 in offensichtlicher Verwendung
(Indizes, Prozentumrechnung, Schleifen). Sonst ertrinkt der Befund im
Rauschen.
"""

from __future__ import annotations

__version__ = "2026.09.25"

import ast
import os
import sys
from collections import defaultdict

#: Zahlen, die fast nie eine Annahme tragen.
HARMLOS = {0, 1, -1, 2, 100, 0.0, 1.0, 100.0, 1000.0, 1e3, 1e6, 1e9, 1e12}

#: In diesen Zusammenhaengen ist eine Zahl besonders verdaechtig - dort
#: entscheidet sie ueber ein Ergebnis, statt nur zu formatieren.
ROLLEN = {
    "vergleich": "Schwelle - entscheidet ueber ja/nein",
    "faktor": "Multiplikator - skaliert ein Ergebnis",
    "divisor": "Teiler - normiert ein Ergebnis",
    "grenze": "Kappung - begrenzt ein Ergebnis",
    "vorgabe": "Standardwert - greift, wenn Daten fehlen",
    "sonstige": "sonstige Verwendung",
}


class Sammler(ast.NodeVisitor):
    def __init__(self, quelle: str):
        self.quelle = quelle.split("\n")
        self.funde = []
        self._fn = "<Modulebene>"

    # -- Kontext ---------------------------------------------------------
    def visit_FunctionDef(self, node):
        alt, self._fn = self._fn, node.name
        self.generic_visit(node)
        self._fn = alt

    visit_AsyncFunctionDef = visit_FunctionDef

    def _merke(self, node, rolle, hinweis=""):
        wert = node.value
        if isinstance(wert, bool) or not isinstance(wert, (int, float)):
            return
        if wert in HARMLOS:
            return
        zeile = node.lineno
        text = (self.quelle[zeile - 1].strip()
                if 0 < zeile <= len(self.quelle) else "")
        # Formatangaben und Prozentumrechnungen sind Anzeige, keine Annahme.
        if any(x in text for x in (':.1f', ':.2f', ':.0f', 'round(', 'f"', "f'")) \
                and rolle == "sonstige":
            return
        self.funde.append({"zeile": zeile, "funktion": self._fn, "wert": wert,
                           "rolle": rolle, "hinweis": hinweis,
                           "code": text[:110]})

    # -- Rollen erkennen -------------------------------------------------
    def visit_Compare(self, node):
        for c in node.comparators:
            if isinstance(c, ast.Constant):
                self._merke(c, "vergleich")
        if isinstance(node.left, ast.Constant):
            self._merke(node.left, "vergleich")
        self.generic_visit(node)

    def visit_BinOp(self, node):
        if isinstance(node.op, ast.Mult):
            for s in (node.left, node.right):
                if isinstance(s, ast.Constant):
                    self._merke(s, "faktor")
        elif isinstance(node.op, ast.Div):
            if isinstance(node.right, ast.Constant):
                self._merke(node.right, "divisor")
        self.generic_visit(node)

    def visit_Call(self, node):
        name = getattr(node.func, "id", "") or getattr(node.func, "attr", "")
        if name in ("min", "max"):
            for a in node.args:
                if isinstance(a, ast.Constant):
                    self._merke(a, "grenze")
        elif name == "get" and len(node.args) == 2:
            if isinstance(node.args[1], ast.Constant):
                self._merke(node.args[1], "vorgabe")
        for kw in node.keywords:
            if isinstance(kw.value, ast.Constant):
                self._merke(kw.value, "vorgabe", f"Parameter {kw.arg}")
        self.generic_visit(node)

    def visit_arguments(self, node):
        for d in list(node.defaults) + [x for x in node.kw_defaults if x]:
            if isinstance(d, ast.Constant):
                self._merke(d, "vorgabe", "Standardargument")
        self.generic_visit(node)


def pruefe(pfad: str) -> list:
    src = open(pfad, encoding="utf-8").read()
    s = Sammler(src)
    s.visit(ast.parse(src))
    # Doppelte Meldungen derselben Stelle zusammenfassen
    gesehen, out = set(), []
    for f in s.funde:
        k = (f["zeile"], f["wert"], f["rolle"])
        if k in gesehen:
            continue
        gesehen.add(k)
        out.append(f)
    return sorted(out, key=lambda x: x["zeile"])


def bericht(pfad: str, funde: list, ausfuehrlich: bool = True) -> None:
    nach_rolle = defaultdict(int)
    for f in funde:
        nach_rolle[f["rolle"]] += 1
    print(f"\n{'=' * 78}\n{pfad}: {len(funde)} begruendungspflichtige Zahlen\n{'=' * 78}")
    print("  " + " · ".join(f"{ROLLEN[r].split(' -')[0]} {n}"
                            for r, n in sorted(nach_rolle.items(),
                                               key=lambda x: -x[1])))
    if not ausfuehrlich:
        return
    aktuelle_fn = None
    for f in funde:
        if f["funktion"] != aktuelle_fn:
            aktuelle_fn = f["funktion"]
            print(f"\n  {aktuelle_fn}")
        marke = {"vergleich": "SCHWELLE", "grenze": "KAPPUNG",
                 "faktor": "FAKTOR", "divisor": "TEILER",
                 "vorgabe": "VORGABE"}.get(f["rolle"], "")
        print(f"    {f['zeile']:5d}  {str(f['wert']):>10s}  {marke:9s} {f['code']}")


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    kurz = "--kurz" in sys.argv
    if "--alle" in sys.argv:
        args = [f for f in ("valuation.py", "roic.py", "providers.py", "scores.py",
                            "relval.py", "kennzahlen.py", "scoring.py", "matrices.py",
                            "momentum.py", "radar.py", "kandidat.py", "screener2.py",
                            "regime.py", "backtest.py") if os.path.exists(f)]
    if not args:
        print(__doc__)
        return 1

    gesamt = 0
    csv_zeilen = ["datei;zeile;funktion;wert;rolle;code"]
    for pfad in args:
        if not os.path.exists(pfad):
            print(f"  {pfad}: nicht gefunden")
            continue
        funde = pruefe(pfad)
        gesamt += len(funde)
        bericht(pfad, funde, ausfuehrlich=not kurz)
        for f in funde:
            csv_zeilen.append(f"{pfad};{f['zeile']};{f['funktion']};{f['wert']};"
                              f"{f['rolle']};\"{f['code']}\"")

    print(f"\n{'=' * 78}\nInsgesamt {gesamt} Zahlen, die eine Begruendung brauchen.")
    print("Jede davon ist eine Annahme ueber die Welt, die wie Code aussieht.")

    if "--csv" in sys.argv:
        i = sys.argv.index("--csv")
        ziel = sys.argv[i + 1] if len(sys.argv) > i + 1 else "konstanten.csv"
        with open(ziel, "w", encoding="utf-8") as fh:
            fh.write("\n".join(csv_zeilen))
        print(f"-> {ziel} geschrieben ({len(csv_zeilen) - 1} Zeilen)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
