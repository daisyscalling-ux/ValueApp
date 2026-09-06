"""
audit_harness.py - Prueffundament: ein eingefrorener Datensatz.

    python3 audit_harness.py --einfrieren     # einmal, holt aus dem Netz
    python3 audit_harness.py --zeigen         # was steckt drin?
    python3 audit_harness.py --pruefen        # Vollstaendigkeit je Titel

Warum das der erste Schritt ist:

    Jede Pruefung, die live gegen die APIs laeuft, liefert bei jedem Aufruf
    andere Zahlen - Kurse aendern sich, Anbieter fallen aus, Kontingente
    laufen leer. Ein Befund waere dann nicht wiederholbar, und genau das ist
    in dieser Sitzung mehrfach passiert: Ein Fehler war da, beim naechsten
    Lauf weg, und niemand wusste, ob die Korrektur gewirkt hat oder die
    Datenlage sich geaendert hatte.

    Deshalb wird EINMAL geholt und als Datei abgelegt. Danach laeuft jede
    Pruefung offline, reproduzierbar, ohne API-Verbrauch.

Die Titelauswahl ist bewusst breit - sie soll die Raender treffen, nicht den
Durchschnitt. Jede Gruppe steht fuer eine Fehlerklasse, die uns schon einmal
getroffen hat.
"""

from __future__ import annotations

__version__ = "2026.09.25"

import json
import os
import sys
from datetime import datetime

DATEI = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "audit_datensatz.json")

#: Warum genau diese Titel? Jede Gruppe deckt einen Fall ab, an dem das
#: Werkzeug schon einmal gescheitert ist oder scheitern koennte.
TITEL = {
    "qualitaet_stabil": ["MSFT", "JNJ", "PG", "COST", "SAP.DE"],
    "zykliker": ["MU", "STLD", "DOW", "NUE", "BAS.DE"],
    "finanzwerte": ["USB", "C", "ALLY", "ALV.DE"],
    "hyperwachstum": ["NVDA", "CRWD", "LLY"],
    "gedrueckt_verlust": ["EL", "WBA", "INTC"],
    "adr_ausland": ["TSM", "MUFG", "TCTZF"],
    "nebenwerte": ["STLD", "MOS", "CF"],
    "energie_rohstoff": ["DVN", "OXY", "BHP"],
    "sonderfaelle": ["BRK-B", "GOOG", "GOOGL"],
}

#: Felder, ohne die eine Bewertung nicht sinnvoll ist. Fehlen sie, wird der
#: Titel im Datensatz markiert - nicht entfernt: Auch ein Titel mit Luecken
#: ist ein Pruefgegenstand, naemlich fuer die Fehlerbehandlung.
KERNFELDER = ["price", "market_cap", "shares_out", "revenue", "net_income",
              "free_cashflow", "ebitda", "eps_trailing", "eps_forward",
              "book_value_ps", "sector", "currency"]


def alle_titel() -> list:
    gesehen, out = set(), []
    for gruppe in TITEL.values():
        for t in gruppe:
            if t not in gesehen:
                gesehen.add(t)
                out.append(t)
    return out


def einfrieren() -> int:
    """Holt alles einmal und legt es ab. Dauert; laeuft nur wenn gewollt."""
    import providers
    import roic

    titel = alle_titel()
    print(f"  {len(titel)} Titel, das dauert etwa "
          f"{len(titel) * 9 // 60 + 1} Minuten.\n")

    daten = {"erstellt": datetime.now().isoformat(timespec="seconds"),
             "roic_aktiv": bool(roic.enabled()), "titel": {}}

    for i, t in enumerate(titel, 1):
        eintrag = {}
        try:
            eintrag["fund_deep"] = providers.get_fundamentals(t, deep=True) or {}
        except Exception as e:
            eintrag["fehler_deep"] = str(e)
        try:
            eintrag["fund_flach"] = providers.get_fundamentals(t, deep=False) or {}
        except Exception as e:
            eintrag["fehler_flach"] = str(e)
        # Rohdaten der Quellen mitschreiben: Nur so laesst sich spaeter
        # pruefen, ob die Feldabbildung stimmt - und nicht bloss, ob das
        # Ergebnis plausibel aussieht.
        if roic.enabled():
            for name, fn in (("roic_bundle", lambda: roic.bundle(t)),
                             ("roic_historie", lambda: roic.kennzahl_historie(t, 15)),
                             ("roic_income", lambda: roic.income_annual(t, 6)),
                             ("roic_balance", lambda: roic.balance_annual(t, 3)),
                             ("roic_cashflow", lambda: roic.cashflow_annual(t, 6)),
                             ("roic_multiples", lambda: roic.multiples(t))):
                try:
                    eintrag[name] = fn()
                except Exception as e:
                    eintrag[name + "_fehler"] = str(e)

        fehlend = [k for k in KERNFELDER
                   if not (eintrag.get("fund_deep") or {}).get(k)]
        eintrag["_fehlende_kernfelder"] = fehlend
        daten["titel"][t] = eintrag
        print(f"  [{i:2d}/{len(titel)}] {t:8s} "
              + ("vollstaendig" if not fehlend
                 else f"ohne {', '.join(fehlend[:4])}"))

    with open(DATEI, "w", encoding="utf-8") as fh:
        json.dump(daten, fh, ensure_ascii=False, default=str)
    mb = os.path.getsize(DATEI) / 1e6
    print(f"\n  Abgelegt: {DATEI} ({mb:.1f} MB)")
    print("  Diese Datei NICHT ueberschreiben, solange das Audit laeuft -")
    print("  sonst verschieben sich die Befunde mit den Daten.")
    return 0


def laden() -> dict:
    """Datensatz einlesen. Wirft, wenn er fehlt - das ist Absicht:
    Eine Pruefung ohne festen Datensatz waere nicht wiederholbar."""
    if not os.path.exists(DATEI):
        raise FileNotFoundError(
            "Kein Datensatz. Zuerst: python3 audit_harness.py --einfrieren")
    with open(DATEI, encoding="utf-8") as fh:
        return json.load(fh)


def fund(ticker: str, tief: bool = True) -> dict:
    """Ein fund-Dict aus dem eingefrorenen Satz."""
    d = laden()["titel"].get(ticker.upper()) or {}
    return d.get("fund_deep" if tief else "fund_flach") or {}


def alle_funds(tief: bool = True) -> dict:
    return {t: (d.get("fund_deep" if tief else "fund_flach") or {})
            for t, d in laden()["titel"].items()}


def zeigen() -> int:
    d = laden()
    print(f"\n  Erstellt: {d['erstellt']}   roic aktiv: {d['roic_aktiv']}")
    print(f"  {len(d['titel'])} Titel\n")
    print(f"  {'Ticker':9s} {'Sektor':22s} {'Kurs':>10s} {'Waehr':>6s}  fehlende Kernfelder")
    for t, e in sorted(d["titel"].items()):
        f = e.get("fund_deep") or {}
        fehlt = e.get("_fehlende_kernfelder") or []
        print(f"  {t:9s} {str(f.get('sector'))[:22]:22s} "
              f"{(f.get('price') or 0):10.2f} {str(f.get('currency')):>6s}  "
              + (", ".join(fehlt[:5]) if fehlt else "-"))
    return 0


def pruefen() -> int:
    """Wie vollstaendig ist der Datensatz? Das ist selbst schon ein Befund."""
    d = laden()
    n = len(d["titel"])
    zaehler = {}
    for e in d["titel"].values():
        for k in e.get("_fehlende_kernfelder") or []:
            zaehler[k] = zaehler.get(k, 0) + 1
    print(f"\n  Fehlende Kernfelder ueber {n} Titel:\n")
    for k, c in sorted(zaehler.items(), key=lambda x: -x[1]):
        print(f"    {k:18s} fehlt bei {c:2d} von {n} ({c / n:.0%})")
    if not zaehler:
        print("    keine")

    ohne_roic = [t for t, e in d["titel"].items() if not e.get("roic_bundle")]
    if ohne_roic:
        print(f"\n  Ohne roic-Daten ({len(ohne_roic)}): {', '.join(sorted(ohne_roic))}")
        print("  Diese Titel pruefen die Rueckfallpfade - sie gehoeren dazu.")
    return 0


if __name__ == "__main__":
    if "--einfrieren" in sys.argv:
        sys.exit(einfrieren())
    if "--pruefen" in sys.argv:
        sys.exit(pruefen())
    if "--zeigen" in sys.argv:
        sys.exit(zeigen())
    print(__doc__)
