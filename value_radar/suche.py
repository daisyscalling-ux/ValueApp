"""
suche.py - Aktiensuche ueber die vorberechneten Kandidaten.

Ersetzt die getrennten Tabs Screener / Radar / Momentum durch EINE Suche mit
zwei Modi:

  Schnellfilter  - die bewaehrten Profile als ein Klick (Value & Qualitaet,
                   Turnaround, Momentum, Radar).
  Eigene Suche   - frei kombinierbare Filter (Composite, Upside, Quantum,
                   Kauf-Urteil, Momentum, Sektor ...).

WARUM DAS SCHNELL IST

    Es wird NICHT live gerechnet. Ein Scan ueber 600 Titel dauert Minuten
    (siehe Nachtlauf). Stattdessen filtert die Suche die Liste, die der
    Nachtlauf (precompute.score_ticker) ohnehin schon berechnet und im Sheet
    abgelegt hat - 30 Felder je Titel. Filtern einer fertigen Tabelle ist in
    Millisekunden durch, egal wie viele Filter kombiniert werden.

    Der Preis: Die Suche findet nur, was der Nachtlauf gescannt hat. Ein Titel
    ausserhalb des Universums taucht nie auf.
"""

from __future__ import annotations

__version__ = "2026.10.06"

from typing import Any, Callable, Dict, List, Optional

# ---------------------------------------------------------------------------
# Schnellfilter: voreingestellte Filtersaetze + Sortierung.
# Sie rechnen nichts Neues - sie setzen nur Filterwerte und die Sortierung,
# die dem jeweiligen Profil entspricht.
# ---------------------------------------------------------------------------
SCHNELLFILTER: Dict[str, dict] = {
    "value": {
        "label": "\U0001f48e Value & Qualit\u00e4t",
        "beschreibung": "Unterbewertet mit solider Bilanz",
        "filter": {"upside_min": 10, "quality_min": 55, "kauf_urteil": "kauf"},
        "sortier": "composite",
    },
    "turnaround": {
        "label": "\U0001f504 Turnaround",
        "beschreibung": "Beschleunigung aus tiefer Bewertung",
        "filter": {"upside_min": 15, "growth_min": 40},
        "sortier": "upside",
    },
    "momentum": {
        "label": "\U0001f680 Momentum",
        "beschreibung": "Starke relative St\u00e4rke",
        "filter": {"momentum_min": 70},
        "sortier": "momentum",
    },
    "radar": {
        "label": "\U0001f4e1 Radar",
        "beschreibung": "Frischer Katalysator",
        "filter": {"catalyst_min": 55},
        "sortier": "catalyst",
    },
}

#: Sortierbare Felder mit sprechendem Namen. Richtung: True = absteigend.
SORTIERFELDER: Dict[str, tuple] = {
    "composite": ("Composite Score", True),
    "upside": ("Upside %", True),
    "quantum": ("Quantum Score", True),
    "momentum": ("Momentum", True),
    "quality": ("Qualit\u00e4t", True),
    "growth": ("Wachstum", True),
    "catalyst": ("Katalysator", True),
    "pe": ("KGV (niedrig zuerst)", False),
}

#: Freie Filter: Feldname im Kandidaten -> (Vergleich, Beschriftung).
#: "min"/"max" heisst >= bzw. <=. "eq" exakter Wert.
FILTER_DEF: Dict[str, dict] = {
    "composite_min": {"feld": "composite", "op": "min", "label": "Composite \u2265"},
    "upside_min":    {"feld": "upside", "op": "min", "label": "Upside % \u2265"},
    "quantum_min":   {"feld": "quantum", "op": "min", "label": "Quantum \u2265"},
    "momentum_min":  {"feld": "momentum", "op": "min", "label": "Momentum \u2265"},
    "quality_min":   {"feld": "quality", "op": "min", "label": "Qualit\u00e4t \u2265"},
    "growth_min":    {"feld": "growth", "op": "min", "label": "Wachstum \u2265"},
    "catalyst_min":  {"feld": "catalyst", "op": "min", "label": "Katalysator \u2265"},
    "pe_max":        {"feld": "pe", "op": "max", "label": "KGV \u2264"},
    "kauf_urteil":   {"feld": "kauf_urteil", "op": "eq", "label": "Kauf-Urteil"},
    "sektor":        {"feld": "sector", "op": "eq", "label": "Sektor"},
}


def _wert(k: dict, feld: str) -> Any:
    v = k.get(feld)
    return v


def _passt(k: dict, filter_satz: dict) -> bool:
    """True, wenn der Kandidat ALLE aktiven Filter erfuellt (UND-Verknuepfung).

    Ein Filter mit Wert None ist inaktiv. Ein Kandidat, dem ein gefiltertes
    Feld fehlt (None), faellt raus - man kann nicht nach etwas filtern, das
    nicht gemessen wurde.
    """
    for schluessel, wert in filter_satz.items():
        if wert is None or wert == "" or wert == "alle":
            continue
        spec = FILTER_DEF.get(schluessel)
        if not spec:
            continue
        haben = _wert(k, spec["feld"])
        if haben is None:
            return False
        op = spec["op"]
        try:
            if op == "min" and float(haben) < float(wert):
                return False
            if op == "max" and float(haben) > float(wert):
                return False
            if op == "eq" and str(haben) != str(wert):
                return False
        except (TypeError, ValueError):
            return False
    return True


def suchen(kandidaten: List[dict], filter_satz: dict,
           sortier: str = "composite", max_treffer: int = 60) -> dict:
    """Filtert und sortiert die vorberechnete Kandidatenliste.

    Rueckgabe: {treffer, anzahl, geprueft, aktive_filter, leer_grund}
    """
    if not kandidaten:
        return {"treffer": [], "anzahl": 0, "geprueft": 0,
                "aktive_filter": [], "leer_grund":
                "Keine vorberechneten Kandidaten vorhanden. L\u00e4uft der "
                "n\u00e4chtliche Job?"}

    aktive = [FILTER_DEF[k]["label"] + f" {v}"
              for k, v in filter_satz.items()
              if v not in (None, "", "alle") and k in FILTER_DEF]

    treffer = [k for k in kandidaten if _passt(k, filter_satz)]

    # Sortierung
    name, absteigend = SORTIERFELDER.get(sortier, ("composite", True))
    feld = sortier if sortier in {v[0] for v in []} else sortier
    treffer.sort(key=lambda k: (k.get(feld) is None, k.get(feld) or 0),
                 reverse=absteigend)

    leer_grund = ""
    if not treffer:
        if aktive:
            leer_grund = ("Kein Titel erf\u00fcllt alle Filter gleichzeitig. "
                          "Einzelne Filter lockern - besonders die kombinierten "
                          "Mindestwerte.")
        else:
            leer_grund = "Keine Treffer."

    return {
        "treffer": treffer[:max_treffer],
        "anzahl": len(treffer),
        "geprueft": len(kandidaten),
        "aktive_filter": aktive,
        "sortiert_nach": name,
        "leer_grund": leer_grund,
    }


def schnellfilter_ausfuehren(kandidaten: List[dict], name: str,
                             max_treffer: int = 60) -> dict:
    """Einen der vordefinierten Schnellfilter anwenden."""
    sf = SCHNELLFILTER.get(name)
    if not sf:
        return suchen(kandidaten, {}, max_treffer=max_treffer)
    erg = suchen(kandidaten, dict(sf["filter"]), sf.get("sortier", "composite"),
                 max_treffer)
    erg["schnellfilter"] = sf["label"]
    erg["beschreibung"] = sf["beschreibung"]
    return erg


def sektoren_in(kandidaten: List[dict]) -> List[str]:
    """Welche Sektoren kommen in den Kandidaten vor? Fuer das Dropdown."""
    s = sorted({k.get("sector") for k in (kandidaten or []) if k.get("sector")})
    return s
