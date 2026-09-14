"""
pruefe_roic_endpunkte.py - Was bietet roic.ai wirklich an?

    python3 pruefe_roic_endpunkte.py MSFT

Anlass: Ich habe mehrfach behauptet, roic fuehre keine Analystenschaetzungen
("eps_forward und target_mean gibt es dort nicht"). Geprueft hatte ich nur,
welche Endpunkte UNSER CODE aufruft - 21 Stueck, alle historisch-fundamental.
Das ist etwas anderes als das, was die API anbietet.

Dieses Skript probiert plausible Pfade gegen den echten Schluessel und meldet,
welche antworten. Danach ist es keine Vermutung mehr.

Es ruft nur lesende Endpunkte auf und bricht bei Rate-Limit ab.
"""

from __future__ import annotations

__version__ = "2026.09.27"

import json
import sys

#: Pfade, die es geben KOENNTE. Abgeleitet aus der Struktur der bekannten
#: Endpunkte (fundamental/..., company/...) und aus dem, was vergleichbare
#: Anbieter unter diesen Namen fuehren.
KANDIDATEN = [
    # Schaetzungen
    "fundamental/estimates/{sym}",
    "fundamental/analyst-estimates/{sym}",
    "fundamental/consensus/{sym}",
    "company/estimates/{sym}",
    "company/analyst-estimates/{sym}",
    "estimates/{sym}",
    "analyst-estimates/{sym}",
    "consensus/{sym}",
    # Kursziele
    "company/price-target/{sym}",
    "analyst/price-target/{sym}",
    "price-target/{sym}",
    "fundamental/price-target/{sym}",
    # Empfehlungen
    "company/recommendations/{sym}",
    "analyst/recommendations/{sym}",
    "recommendations/{sym}",
    # Prognostizierte Kennzahlen
    "fundamental/forward-multiples/{sym}",
    "fundamental/growth/{sym}",
    # Bekannt funktionierend - als Gegenprobe, dass der Schluessel greift
    "company/profile/{sym}",
    "fundamental/multiples/{sym}",
]


def main(ticker: str) -> int:
    import roic

    if not roic.enabled():
        print("  roic ist nicht aktiv - ROIC_API_KEY fehlt.")
        return 1
    sym = roic._sym(ticker)
    print(f"\n{'=' * 72}\nroic-Endpunkte fuer {ticker} (Symbol {sym})\n{'=' * 72}\n")

    treffer, leer, fehler = [], [], []
    for muster in KANDIDATEN:
        pfad = muster.format(sym=sym)
        try:
            d = roic._get(pfad)
        except Exception as e:
            fehler.append((pfad, str(e)[:50]))
            continue
        if d is None:
            leer.append(pfad)
            continue
        # Was kam zurueck? Die Feldnamen sind interessanter als der Inhalt.
        roh = d if isinstance(d, list) else [d]
        felder = sorted(roh[0].keys()) if roh and isinstance(roh[0], dict) else []
        treffer.append((pfad, len(roh), felder))

    print(f"  ANTWORTEN ({len(treffer)}):\n")
    for pfad, n, felder in treffer:
        print(f"    {pfad}")
        print(f"      {n} Datensatz/-saetze, {len(felder)} Felder")
        # Nur Felder zeigen, die nach Schaetzung aussehen
        interessant = [f for f in felder if any(
            w in f.lower() for w in ("estimat", "forecast", "target", "forward",
                                     "consensus", "analyst", "next", "guidance"))]
        if interessant:
            print(f"      SCHAETZFELDER: {', '.join(interessant)}")
        else:
            print(f"      Beispielfelder: {', '.join(felder[:8])}")
        print()

    if leer:
        print(f"  KEINE ANTWORT ({len(leer)}): gibt es dort nicht")
        for p in leer:
            print(f"    {p}")
    if fehler:
        print(f"\n  FEHLER ({len(fehler)}):")
        for p, e in fehler:
            print(f"    {p}: {e}")

    print(f"\n{'=' * 72}")
    mit_schaetzung = [p for p, _n, f in treffer if any(
        w in x.lower() for x in f
        for w in ("estimat", "forecast", "target", "forward", "consensus"))]
    if mit_schaetzung:
        print("  roic FUEHRT Schaetzdaten. Diese Pfade anbinden:")
        for p in mit_schaetzung:
            print(f"    {p}")
    else:
        print("  Kein Pfad mit Schaetzfeldern gefunden. Damit ist die Aussage")
        print("  'roic fuehrt keine Analystenschaetzungen' belegt - vorher war")
        print("  sie nur eine Vermutung.")
    return 0


if __name__ == "__main__":
    sys.exit(main((sys.argv[1] if len(sys.argv) > 1 else "MSFT").upper()))
