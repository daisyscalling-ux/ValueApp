"""
kennzahl_kacheln.py - Kennzahlen und Nachrichten als sichtbarer Kopfbereich.

Baut aus roic-Jahresreihen die Kachelreihe (Grosszahl, Vorjahresdelta,
Verlauf, 3J/5J/10J) und aus roic.news() die Nachrichtenkarte. Beides gehoert
oben auf die Seite: Das Faktische zuerst, die Modellrechnung danach.

Die bestehenden Aufklapper "FINANZKENNZAHLEN" und "PROFIL, NACHRICHTEN, PEERS"
bleiben unangetastet - sie sind der Tiefgang, das hier ist die Uebersicht.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence

import ui_bewertung as ui

#: (Schluessel in kennzahl_historie, Anzeigename, ist_negativ)
REIHEN = [
    ("revenue", "Umsatz", False),
    ("ebitda", "EBITDA", False),
    ("net_income", "Nettoergebnis", False),
    ("eps", "Ergebnis je Aktie", False),
]


def _zahl(x: Optional[float], waehrung: str = "", fx: float = 1.0) -> str:
    if x is None:
        return "n/a"
    x = x * fx
    a = abs(x)
    for teiler, suffix in ((1e12, " Bio."), (1e9, " Mrd."), (1e6, " Mio.")):
        if a >= teiler:
            return ui.de(x / teiler, 1) + suffix
    return ui.de(x, 2)


def _rate(xs: Sequence[float], jahre: int) -> Optional[float]:
    """Gesamtveraenderung ueber `jahre` - nicht annualisiert, wie im Vorbild."""
    xs = [v for v in xs if v is not None]
    if len(xs) < jahre + 1:
        return None
    alt, neu = xs[-(jahre + 1)], xs[-1]
    if not alt or alt <= 0:
        return None
    return neu / alt - 1.0


def kacheln_aus_historie(historie: Sequence[dict], fx: float = 1.0,
                         waehrung: str = "EUR") -> List[Dict]:
    """historie: roic.kennzahl_historie(t) - Reihenfolge egal, wird sortiert."""
    rows = sorted([z for z in (historie or []) if z.get("jahr")],
                  key=lambda z: str(z["jahr"]))
    if len(rows) < 2:
        return []

    items: List[Dict] = []
    for key, label, negativ in REIHEN:
        xs = [z.get(key) for z in rows]
        xs = [float(v) for v in xs if isinstance(v, (int, float))]
        if len(xs) < 2:
            continue
        # EPS ist ein Je-Aktie-Wert und wird ebenfalls umgerechnet; Margen
        # waeren es nicht - die stehen hier bewusst nicht drin.
        delta = (xs[-1] / xs[-2] - 1.0) if xs[-2] else None
        chips = []
        for j, name in ((3, "3J"), (5, "5J"), (10, "10J")):
            r = _rate(xs, j)
            if r is not None:
                chips.append((name, r))
        items.append({
            "label": label,
            "value": _zahl(xs[-1], waehrung, fx),
            "delta": delta,
            "chips": chips,
            "reihe": xs,
            "negative": negativ,
        })

    # Margen als eigene Kachel: Prozentwerte, keine Waehrung
    for key, label in (("profit_margin", "Nettomarge"),
                       ("oper_margin", "Operative Marge")):
        xs = [z.get(key) for z in rows]
        xs = [float(v) for v in xs if isinstance(v, (int, float))]
        if len(xs) < 3:
            continue
        items.append({
            "label": label,
            "value": ui.pct(xs[-1], 1),
            "delta": None,
            "chips": [("Spanne", 0)] if False else [],
            "reihe": xs,
            "negative": False,
        })
    return items


def rendern(historie: Sequence[dict], news: Optional[Sequence[dict]] = None,
            fx: float = 1.0, waehrung: str = "EUR",
            nummer_start: int = 1) -> int:
    """Rendert Kacheln und Nachrichten. Gibt die naechste Abschnittsnummer zurueck."""
    n = nummer_start
    items = kacheln_aus_historie(historie, fx, waehrung)
    if items:
        ui.abschnitt(n, "Kennzahlen", "Jahresabschluesse")
        n += 1
        ui.kennzahl_kacheln(items)

    eintraege = [x for x in (news or []) if x.get("titel")]
    if eintraege:
        ui.abschnitt(n, "Nachrichten")
        n += 1
        mit_link = sum(1 for x in eintraege if x.get("url"))
        kopf = f"{len(eintraege)} Meldungen"
        if mit_link < len(eintraege):
            kopf += f" \u00b7 {mit_link} mit Quelle"
        ui.news_karte(eintraege, kopf, sichtbar=5)
    return n
