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

ERWARTET = "2026.08.29"

MODULE = {
    "ui_bewertung": ["sparkline", "kennzahl_kacheln", "news_karte",
                     "wert_kopf", "szenario_tabelle", "abschnitt"],
    "bewertung_seite": ["rendern"],
    "kennzahl_kacheln": ["rendern", "kacheln_aus_historie"],
}

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

        ver = getattr(m, "__version__", None)
        stand = "aktuell" if ver == ERWARTET else f"VERALTET ({ver or 'ohne Marker'})"
        fehlend = [f for f in funktionen if not hasattr(m, f)]
        print(f"  {name + '.py':24s} {stand}")
        if fehlend:
            print(f"      fehlende Funktionen: {', '.join(fehlend)}")
        if ver != ERWARTET or fehlend:
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

    print()
    if fehler:
        print(f"  {fehler} Modul(e) nicht auf Stand {ERWARTET}.")
        print("  -> Diese Dateien erneut hochladen und die App neu starten.")
    else:
        print(f"  Alle Module auf Stand {ERWARTET}.")
    return 1 if fehler else 0


if __name__ == "__main__":
    sys.exit(main())
