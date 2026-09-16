"""
kennzahl_kacheln.py - Kennzahlen und Nachrichten als sichtbarer Kopfbereich.

Baut aus roic-Jahresreihen die Kachelreihe (Grosszahl, Vorjahresdelta,
Verlauf, 3J/5J/10J) und aus roic.news() die Nachrichtenkarte. Beides gehoert
oben auf die Seite: Das Faktische zuerst, die Modellrechnung danach.

Die bestehenden Aufklapper "FINANZKENNZAHLEN" und "PROFIL, NACHRICHTEN, PEERS"
bleiben unangetastet - sie sind der Tiefgang, das hier ist die Uebersicht.
"""


from __future__ import annotations

__version__ = "2026.09.27"

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


def _einordnung(xs, label: str, negativ_ist_gut: bool = False) -> tuple:
    """Was sagt der Verlauf - jenseits der letzten Prozentzahl?

    Drei Wachstumsraten nebeneinander (3J/5J/10J) sind Zahlen, keine Aussage.
    Interessant ist die zweite Ableitung: Beschleunigt sich das Wachstum oder
    laeuft es aus? Bei Eaton war genau das der Punkt - Umsatz weiter steigend,
    Nettoergebnis bereits drehend.

    Rueckgabe: (ampel, zusatztext)
    """
    xs = [float(v) for v in xs if isinstance(v, (int, float))]
    if len(xs) < 4:
        return None, None

    def rate(a, b):
        return (b / a - 1.0) if a and a > 0 else None

    letzte = rate(xs[-2], xs[-1])
    vorletzte = rate(xs[-3], xs[-2])
    if letzte is None or vorletzte is None:
        return None, None

    # Dreijahresschnitt als Referenz fuer "normal"
    frueher = [r for r in (rate(xs[i - 1], xs[i]) for i in range(1, len(xs) - 1))
               if r is not None]
    schnitt = sum(frueher) / len(frueher) if frueher else 0.0

    delta = letzte - vorletzte
    if letzte < 0 and vorletzte < 0:
        return "rot", f"zweites Jahr rueckl\u00e4ufig ({letzte * 100:+.0f} %)"
    if letzte < 0:
        return "rot", f"gedreht: von {vorletzte * 100:+.0f} % auf {letzte * 100:+.0f} %"
    if delta < -0.05:
        return "gelb", (f"Wachstum verlangsamt sich "
                        f"({vorletzte * 100:+.0f} % \u2192 {letzte * 100:+.0f} %)")
    if delta > 0.05:
        return "gruen", (f"Wachstum zieht an "
                         f"({vorletzte * 100:+.0f} % \u2192 {letzte * 100:+.0f} %)")
    if letzte > schnitt * 1.1:
        return "gruen", f"stetig, ueber dem Schnitt ({schnitt * 100:+.0f} %)"
    return None, f"stetig um {letzte * 100:+.0f} % pro Jahr"


def _marge_einordnung(xs) -> tuple:
    """Margen: Niveau UND Richtung. Eine fallende hohe Marge ist etwas anderes
    als eine steigende niedrige."""
    xs = [float(v) for v in xs if isinstance(v, (int, float))]
    if len(xs) < 4:
        return None, None
    jetzt = xs[-1]
    schnitt = sum(xs[:-1]) / len(xs[:-1])
    if schnitt == 0:
        return None, None
    ab = jetzt - schnitt
    if ab < -0.02:
        return "rot", (f"{abs(ab) * 100:.1f} Pp. unter dem Mehrjahresschnitt "
                       f"({schnitt * 100:.1f} %)")
    if ab > 0.02:
        return "gruen", (f"{ab * 100:.1f} Pp. ueber dem Schnitt "
                         f"({schnitt * 100:.1f} %) \u2013 Gipfelverdacht pruefen")
    return None, f"stabil um {schnitt * 100:.1f} %"


def kacheln_aus_historie(historie: Sequence[dict], fx: float = 1.0,
                         waehrung: str = "EUR") -> List[Dict]:
    """historie: roic.kennzahl_historie(t) - Reihenfolge egal, wird sortiert."""
    rows = sorted([z for z in (historie or []) if z.get("jahr")],
                  key=lambda z: str(z["jahr"]))
    if len(rows) < 2:
        return []
    # Welche Geschaeftsjahre werden verglichen? Ohne diese Angabe steht auf
    # der Kachel "+18 %" und niemand weiss, ob das laufende oder das letzte
    # abgeschlossene Jahr gemeint ist.
    _jahr = str(rows[-1].get("jahr"))[:4]
    _vorjahr = str(rows[-2].get("jahr"))[:4]
    _bezug = f"Geschaeftsjahr {_jahr} gegenueber {_vorjahr}"
    _alle_jahre = [str(z.get("jahr"))[:4] for z in rows]

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
        ampel, zusatz = _einordnung(xs, label, negativ)
        # BEFUND: Die Grosszahl lief durch _zahl(..., fx), die Balkenreihe
        # nicht. Auf dem Screenshot stand "58,3 Mrd" (EUR) ueber Balken mit
        # "53/57/67" (USD) - dieselbe Groesse in zwei Waehrungen. Die Reihe
        # wird jetzt mitgerechnet, damit Balken und Grosszahl uebereinstimmen.
        xs_anzeige = [v * fx for v in xs]
        items.append({
            "label": label,
            "value": _zahl(xs[-1], waehrung, fx),
            "delta": delta,
            "chips": chips,
            "reihe": xs_anzeige,
            "jahre": _alle_jahre[-len(xs):] if xs else [],
            "negative": negativ,
            "ampel": ampel,
            "zusatz": zusatz,
            "jahr": f"GJ {_jahr}",
            "bezug": _bezug,
        })

    # Margen als eigene Kachel: Prozentwerte, keine Waehrung
    for key, label in (("profit_margin", "Nettomarge"),
                       ("oper_margin", "Operative Marge")):
        xs = [z.get(key) for z in rows]
        xs = [float(v) for v in xs if isinstance(v, (int, float))]
        if len(xs) < 3:
            continue
        ampel, zusatz = _marge_einordnung(xs)
        items.append({
            "label": label,
            "value": ui.pct(xs[-1], 1),
            "delta": None,
            "chips": [],
            "reihe": xs,
            "jahre": _alle_jahre[-len(xs):] if xs else [],
            "negative": False,
            "ampel": ampel,
            "zusatz": zusatz,
            "jahr": f"GJ {_jahr}",
            "bezug": _bezug,
        })
    return items


def rendern(historie: Sequence[dict], news: Optional[Sequence[dict]] = None,
            fx: float = 1.0, waehrung: str = "EUR",
            nummer_start: int = 1, bilanz=None, bilanz_zusammenfassung=None) -> int:
    """Rendert Kacheln, Finanzlage und Nachrichten.

    bilanz  Rueckgabe von kennzahlen.bewerte() - die Bilanzkennzahlen standen
            bisher ganz unten in einem Aufklapper mit mehreren Tabellen. Hier
            stehen sie als Kachelstreifen oben; die Tabellen bleiben unten
            fuer den, der die Schwellen sehen will.
    """
    n = nummer_start
    items = kacheln_aus_historie(historie, fx, waehrung)
    if items:
        ui.abschnitt(n, "Kennzahlen", "Jahresabschluesse")
        n += 1
        ui.kennzahl_kacheln(items)

    if bilanz:
        ui.bilanz_streifen(bilanz, bilanz_zusammenfassung)

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
