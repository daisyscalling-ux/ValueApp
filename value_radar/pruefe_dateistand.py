"""
pruefe_dateistand.py - Sind alle Dateien auf dem aktuellen Stand?

    python3 pruefe_dateistand.py

Prueft die Module mit Versionsmarker und die Funktionen, die dashboard.py
von ihnen erwartet. Gedacht fuer genau den Fall, in dem die App
"nicht verfuegbar (module hat kein Attribut ...)" meldet - dann fehlt keine
Funktion, sondern eine Datei wurde beim Hochladen vergessen.
"""

import importlib
import sys

ERWARTET = "2026.09.22"          # Bewertungs-/Anzeigeschicht
ERWARTET_ENTDECKUNG = "2026.09.22"   # Screener, Kandidat, Forensik

#: Module der Entdeckungsschicht - eigener Zyklus, eigener Stand.
ENTDECKUNG = {"kandidat", "screener2", "scores",
              "valuation", "providers", "relval", "roic", "momentum", "radar", "pruefung", "kennzahlen"}

MODULE = {
    "valuation": ["zyklisch_aus_margen", "fcf_basis", "reverse_dcf_analyse",
                  "datenqualitaet", "basis_signatur", "wachstums_anker"],
    "providers": ["get_eps_history", "get_fundamentals", "umsatz_historie"],
    "relval": ["perzentil", "bericht", "multiple_band"],
    "roic": ["umsatz_reihe", "cashflow_reihe", "wachstum"],
    "momentum": ["bausteine", "branchen_mediane", "branchen_mediane_12_1"],
    "radar": ["compute", "_frische"],
    "pruefung": ["pruefe", "fundamentales_momentum"],
    "kennzahlen": ["bewerte", "zusammenfassung", "transkript_kennzahlen",
                   "zusammenfassung_call", "kernstellen"],
    "ui_bewertung": ["sparkline", "kennzahl_kacheln", "news_karte",
                     "wert_kopf", "szenario_tabelle", "abschnitt"],
    "bewertung_seite": ["rendern"],
    "kennzahl_kacheln": ["rendern", "kacheln_aus_historie"],
    # Entdeckungsschicht
    "kandidat": ["pruefe", "vorfilter", "gate_pruefen"],
    "screener2": ["lauf", "rang", "vergleich", "_entdopple"],
    "scores": ["piotroski_f", "altman_z", "beneish_m"],
}

#: Frueher wurde hier nur geprueft, OB bestimmte Funktionen existieren. Das
#: uebersieht jede Aenderung INNERHALB einer Funktion: valuation.py galt als
#: aktuell, obwohl die Vorversion lief - der Screener rechnete deshalb mit
#: zwei statt fuenf Ankern, ohne dass die Pruefung anschlug. Jetzt tragen alle
#: Module einen Marker.
OHNE_MARKER = {}

SIGNATUREN = {
    ("bewertung_seite", "rendern"): ["fx", "waehrung", "start_abschnitt"],
}


def main() -> int:
    fehler = 0
    for name, funktionen in MODULE.items():
        try:
            m = importlib.import_module(name)
        except Exception as e:
            print(f"  {name + '.py':24s} FEHLT oder defekt ({e})")
            fehler += 1
            continue

        soll = ERWARTET_ENTDECKUNG if name in ENTDECKUNG else ERWARTET
        ver = getattr(m, "__version__", None)
        stand = ("aktuell" if ver == soll
                 else f"VERALTET ({ver or 'ohne Marker'}, erwartet {soll})")
        fehlend = [f for f in funktionen if not hasattr(m, f)]
        print(f"  {name + '.py':24s} {stand}")
        if fehlend:
            print(f"      fehlende Funktionen: {', '.join(fehlend)}")
        if ver != soll or fehlend:
            fehler += 1

        import inspect
        for (mod, fn), params in SIGNATUREN.items():
            if mod != name or not hasattr(m, fn):
                continue
            vorhanden = inspect.signature(getattr(m, fn)).parameters
            fehlt_p = [p for p in params if p not in vorhanden]
            if fehlt_p:
                print(f"      {fn}() ohne Parameter: {', '.join(fehlt_p)}")
                fehler += 1

    for name, funktionen in OHNE_MARKER.items():
        try:
            m = importlib.import_module(name)
        except Exception as e:
            print(f"  {name + '.py':24s} FEHLT oder defekt ({e})")
            fehler += 1
            continue
        fehlend = [f for f in funktionen if not hasattr(m, f)]
        print(f"  {name + '.py':24s} "
              + ("aktuell" if not fehlend else "VERALTET"))
        if fehlend:
            print(f"      fehlende Funktionen: {', '.join(fehlend)}")
            fehler += 1

    print()
    if fehler:
        print(f"  {fehler} Modul(e) nicht auf Stand "
              f"({ERWARTET} bzw. {ERWARTET_ENTDECKUNG}).")
        print("  -> Diese Dateien erneut hochladen und die App neu starten.")
    else:
        print(f"  Alle Module aktuell ({ERWARTET} / {ERWARTET_ENTDECKUNG}).")
    return 1 if fehler else 0


if __name__ == "__main__":
    sys.exit(main())
