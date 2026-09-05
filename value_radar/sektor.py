"""
sektor.py - Was zahlt der Markt gerade fuer diesen Sektor, und was frueher?

WARUM DIESES MODUL

    Die Bewertung kannte den Sektor bisher nur als feste Zahl im Code:
    SECTOR_EV_EBITDA["Technology"] = 16. Ob Software gerade bei 25 oder bei 11
    handelt, aenderte am Fair Value nichts. Der einzige dynamische Pfad -
    peer_funds in multiple_ev_ebitda() - wurde an keiner Stelle im Projekt
    befuellt und war damit toter Code.

    Die Folge: Ein Titel aus einem abgestraften Sektor sieht guenstig aus,
    weil das Modell mit dem Multiple von vorgestern rechnet. Genau die Falle,
    in die man tappt, wenn man das Segment nicht kennt.

DIE ZIRKULARITAETSFALLE - und warum hier NICHTS ersetzt wird

    Naheliegend waere, den Fair Value am heutigen Sektormultiple zu verankern.
    Dann sagt das Modell aber bei jedem Sektor genau das, was der Markt ohnehin
    sagt: fair bewertet. Es koennte nie mehr feststellen, dass ein Sektor zu
    billig ist - und dafuer ist es da.

    Deshalb ersetzt dieses Modul keinen einzigen Wert. Es liefert einen
    ZWEITEN Anker daneben und benennt die Luecke. Welche der beiden Lesarten
    stimmt, entscheidet der Mensch: Ist die Abwertung zyklisch (Chance) oder
    strukturell (Falle)? Kein Modell im Bestand kann das beantworten.

WAS ES NICHT KANN

    Die Sektorhistorie laesst sich nicht beschaffen. roic liefert fuenf Jahre
    je Titel, kein Anbieter im Bestand gibt Sektormediane ueber die Zeit.
    Gemessen werden kann nur ab heute - die Zeitreihe entsteht mit jedem
    Screener-Lauf. Bis genug Messpunkte da sind, sagt das Modul das
    ausdruecklich, statt eine Abweichung zu behaupten.
"""

from __future__ import annotations

__version__ = "2026.09.23"

from datetime import datetime
from typing import Dict, List, Optional, Sequence

#: Kennzahlen, fuer die ein Sektormedian gebildet wird. Je Kennzahl ein
#: plausibler Wertebereich - Ausreisser (negatives EBITDA, KGV 900) wuerden den
#: Median sonst nicht verzerren, aber die Zaehlung aufblaehen.
KENNZAHLEN = {
    "ev_ebitda": (0.5, 60.0),
    "pe": (1.0, 120.0),
    "pb": (0.1, 30.0),
    "ps": (0.1, 40.0),
}

#: Unter so vielen Titeln je Sektor ist der Median Rauschen. Bei einem
#: Universum von 150 Titeln sind kleine Sektoren schnell darunter - dann gibt
#: es lieber keinen Anker als einen aus drei Firmen.
MIN_TITEL = 6

#: Unter so vielen Messzeitpunkten gibt es keinen Vergleich mit der eigenen
#: Historie. Die Reihe entsteht erst ab heute.
MIN_MESSUNGEN = 4

#: Ab dieser Abweichung vom eigenen Schnitt wird es zur Aussage.
AUFFAELLIG_PCT = 20.0


# ---------------------------------------------------------------------------
# Namensvereinheitlichung
# ---------------------------------------------------------------------------

#: AUDIT-BEFUND SK1: Der Sektorname haengt an der LADETIEFE, nicht am Titel.
#:
#: roic liefert Sektor und Branche im Profil, und die Uebernahmeschleife in
#: providers kopiert jedes Bundle-Feld - also auch diese beiden. Damit gilt:
#:
#:   deep=True   -> roic      "Electronic technology", "Energy minerals"
#:   deep=False  -> yfinance  "Technology", "Energy"
#:
#: Derselbe Titel bekommt je nach Ladeweg einen anderen Sektornamen. Der
#: Vorfilter im Screener arbeitet flach, die tiefe Pruefung tief - beide sehen
#: verschiedene Namen fuer dieselbe Firma.
#:
#: Folge: Acht von zwoelf beobachteten Namen treffen SECTOR_EV_EBITDA gar
#: nicht und fallen still auf _default = 11. Ein Energiewert bekommt dann 11
#: statt 6, ein Techwert 11 statt 16 - und der Fehler ist unsichtbar, weil ein
#: Anker ja geliefert wird.
#:
#: Fuer die Sektormediane waere die Folge schlimmer: Dieselbe Branche laege
#: unter zwei Namen, und keiner erreichte die Mindestzahl an Titeln.
_SEKTOR_ALIAS = {
    # Finnhub/FactSet -> yfinance-Schreibweise (die die Tabellen benutzen)
    "electronic technology": "Technology",
    "technology services": "Technology",
    "producer manufacturing": "Industrials",
    "electronic technology services": "Technology",
    "health technology": "Healthcare",
    "health services": "Healthcare",
    "energy minerals": "Energy",
    "industrial services": "Energy",
    "non-energy minerals": "Basic Materials",
    "process industries": "Basic Materials",
    "finance": "Financial Services",
    "consumer non-durables": "Consumer Defensive",
    "consumer services": "Consumer Cyclical",
    "consumer durables": "Consumer Cyclical",
    "retail trade": "Consumer Cyclical",
    "distribution services": "Industrials",
    "transportation": "Industrials",
    "commercial services": "Industrials",
    "communications": "Communication Services",
    "utilities": "Utilities",
    "miscellaneous": "Unknown",
}


def normalisieren(name: Optional[str]) -> Optional[str]:
    """Sektorname auf EIN System bringen.

    Ohne diesen Schritt wird derselbe Sektor unter zwei Namen gefuehrt: Die
    Mediane teilen sich auf, keiner erreicht die Mindestzahl an Titeln, und
    die feste Ankertabelle greift nur bei der Haelfte der Titel.
    """
    if not name:
        return None
    return _SEKTOR_ALIAS.get(str(name).strip().lower(), str(name).strip())


#: SEGMENTE: die Ebene zwischen Sektor (11 Stueck, zu grob) und Branche
#: (ueber 140, zu fein).
#:
#: Warum es sie braucht: "Technology" mischt Software und Halbleiter - zwei
#: Geschaefte mit voellig verschiedener Bewertung und verschiedenen Zyklen.
#: Die Branchenebene trennt sie zwar, aber bei 150 geladenen Titeln und ueber
#: 140 Branchen kommen nirgends genug Firmen fuer einen Median zusammen. Die
#: Segmente fassen Branchen zu rund 25 Gruppen zusammen, die gross genug sind
#: und trotzdem etwas trennen.
_SEGMENT_MUSTER = [
    ("Software", ("software", "internet content", "internet software",
                  "packaged software", "information technology serv")),
    ("Halbleiter", ("semiconductor", "electronic production equipment")),
    ("Hardware & Geraete", ("computer hardware", "consumer electronics",
                            "electronic components", "communication equipment",
                            "electronics & computer distribution",
                            "computer processing hardware",
                            "computer peripherals", "office equipment")),
    ("IT-Dienstleistungen", ("information technology", "technology services",
                             "data processing")),
    ("Banken", ("bank", "credit services", "capital markets", "mortgage",
                "savings institutions", "finance/rental/leasing")),
    ("Versicherungen", ("insurance",)),
    ("Vermoegensverwaltung", ("asset management", "financial data",
                              "financial conglomerates")),
    ("Immobilien", ("reit", "real estate")),
    ("Pharma & Biotech", ("drug manufacturers", "biotechnology",
                          "pharmaceutical")),
    ("Medizintechnik", ("medical devices", "medical instruments",
                        "medical specialties", "diagnostics",
                        "health information")),
    ("Gesundheitsdienste", ("healthcare plans", "medical care", "health care",
                            "medical distribution")),
    ("Oel & Gas", ("oil", "gas", "drilling", "refin")),
    ("Bergbau & Metalle", ("mining", "metals", "steel", "copper", "gold",
                           "silver", "aluminum", "coking")),
    ("Chemie", ("chemical", "agricultural inputs", "specialty chemicals")),
    ("Baustoffe & Bau", ("building", "construction", "homebuild", "cement",
                         "lumber", "paper")),
    ("Maschinenbau", ("machinery", "industrial", "tools", "conglomerates",
                      "electrical equipment", "electrical products",
                      "trucks/construction/farm")),
    ("Luft- & Raumfahrt, Ruestung", ("aerospace", "defense")),
    ("Transport & Logistik", ("airlines", "railroad", "trucking", "shipping",
                              "marine", "logistics", "integrated freight",
                              "air freight", "courier", "transportation")),
    ("Autos & Zulieferer", ("auto", "recreational vehicles", "motor vehicles",
                            "automotive aftermarket")),
    ("Handel", ("retail", "department stores", "grocery", "discount",
                "wholesale distributors", "specialty stores",
                "catalog/specialty distribution")),
    ("Konsumgueter", ("beverages", "food", "tobacco", "household",
                      "confection", "personal", "consumer sundries",
                      "household/personal care")),
    ("Freizeit & Gastgewerbe", ("restaurant", "lodging", "resorts", "gambling",
                                "travel", "leisure", "entertainment")),
    ("Medien & Telekom", ("telecom", "broadcasting", "publishing", "advertis",
                          "media", "cable/satellite", "movies/entertainment",
                          "wireless")),
    ("Versorger", ("utilities", "utility", "power", "water")),
    ("Luxus & Bekleidung", ("apparel", "luxury", "footwear", "textile")),
]


def segment(fund: dict) -> Optional[str]:
    """Das Segment eines Titels - grob genug fuer einen Median, fein genug,
    um Software von Halbleitern zu trennen.

    Faellt auf den normalisierten Sektor zurueck, wenn die Branche zu keinem
    Muster passt. Lieber eine grobe Gruppe als gar keine.
    """
    ind = str(fund.get("industry") or "").lower()
    if ind:
        for name, muster in _SEGMENT_MUSTER:
            if any(m in ind for m in muster):
                return name
    return normalisieren(fund.get("sector"))


def unbekannte_branchen(funds: Sequence[dict], limit: int = 30) -> list:
    """Welche Branchennamen trifft kein Segmentmuster?

    Die Musterliste ist handgepflegt - genau die Sorte, die ich beim Radar
    kritisiert habe. Der Unterschied: Diese hier laesst sich gegen die echten
    Daten pruefen. Was hier auftaucht, gehoert entweder ins Raster oder ist
    zu selten, um zu zaehlen.

    Rueckgabe: [(branche, anzahl, ersatzweise_zugeordnet), ...]
    """
    zaehler: Dict[str, int] = {}
    for f in funds:
        if not isinstance(f, dict):
            continue
        ind = str(f.get("industry") or "").lower()
        if not ind:
            continue
        if any(any(m in ind for m in muster) for _n, muster in _SEGMENT_MUSTER):
            continue
        roh = str(f.get("industry"))
        zaehler[roh] = zaehler.get(roh, 0) + 1
    out = [(b, n, normalisieren(
        next((f.get("sector") for f in funds
              if str(f.get("industry")) == b), None)))
        for b, n in zaehler.items()]
    return sorted(out, key=lambda x: -x[1])[:limit]


def _median(xs: Sequence[float]) -> Optional[float]:
    xs = sorted(float(x) for x in xs if x is not None)
    if not xs:
        return None
    n = len(xs)
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2.0


def _kennzahlen_aus_fund(f: dict) -> dict:
    """Die vier Multiples aus einem fund-Dict - nur wo sie sinnvoll sind."""
    out = {}
    ev = f.get("ev_ebitda")
    if ev is not None:
        out["ev_ebitda"] = ev
    preis, eps = f.get("price"), f.get("eps_trailing")
    if preis and eps and eps > 0:
        out["pe"] = preis / eps
    if f.get("pb") is not None:
        out["pb"] = f["pb"]
    mcap, rev = f.get("market_cap"), f.get("revenue")
    if mcap and rev and rev > 0:
        out["ps"] = mcap / rev
    return out


def messen(funds: Sequence[dict], ebene: str = "sector") -> dict:
    """Sektormediane aus einer Menge geladener Titel.

    funds: fund-Dicts, wie sie der Screener ohnehin hat.
    ebene: "sector"   - 11 Gruppen, vereinheitlicht ueber beide Datenquellen
           "segment"  - rund 25 Gruppen, EMPFOHLEN: trennt Software von
                        Halbleitern und erreicht trotzdem genug Titel
           "industry" - ueber 140 Gruppen, meist zu duenn besetzt
    """
    eimer: Dict[str, Dict[str, List[float]]] = {}
    for f in funds:
        if not isinstance(f, dict):
            continue
        if ebene == "segment":
            gruppe = segment(f)
        elif ebene == "sector":
            gruppe = normalisieren(f.get("sector"))
        else:
            gruppe = f.get(ebene)
        if not gruppe or gruppe == "Unknown":
            continue
        werte = _kennzahlen_aus_fund(f)
        for k, v in werte.items():
            lo, hi = KENNZAHLEN[k]
            if lo <= v <= hi:
                eimer.setdefault(gruppe, {}).setdefault(k, []).append(v)

    out = {}
    for gruppe, kz in eimer.items():
        eintrag = {}
        for k, xs in kz.items():
            if len(xs) >= MIN_TITEL:
                eintrag[k] = {"median": round(_median(xs), 2), "n": len(xs)}
        if eintrag:
            out[gruppe] = eintrag
    return out


# ---------------------------------------------------------------------------
# Speichern: die Zeitreihe entsteht ab heute
# ---------------------------------------------------------------------------

def speichern(mediane: dict, ebene: str = "sector") -> int:
    """Eine Messung ablegen. Eine je Tag reicht - mehr waere Scheingenauigkeit.

    Rueckgabe: Anzahl gespeicherter Gruppen.
    """
    import store

    heute = datetime.now().strftime("%Y-%m-%d")
    n = 0
    for gruppe, kz in (mediane or {}).items():
        schluessel = f"{ebene}:{gruppe}"
        try:
            reihe = store.get_anreicherung(schluessel, "sektormedian",
                                           max_alter_tage=3650) or []
        except Exception:
            reihe = []
        if not isinstance(reihe, list):
            reihe = []
        # Messung desselben Tages ersetzen, nicht anhaengen
        reihe = [e for e in reihe if e.get("datum") != heute]
        reihe.append({"datum": heute,
                      **{k: v["median"] for k, v in kz.items()},
                      "n": max(v["n"] for v in kz.values())})
        reihe = sorted(reihe, key=lambda e: e["datum"])[-400:]
        try:
            if store.set_anreicherung(schluessel, "sektormedian", reihe):
                n += 1
        except Exception:
            pass
    _index_ergaenzen(list((mediane or {}).keys()), ebene)
    return n


def lade_reihe(gruppe: str, ebene: str = "sector") -> list:
    import store
    try:
        r = store.get_anreicherung(f"{ebene}:{gruppe}", "sektormedian",
                                   max_alter_tage=3650)
        return r if isinstance(r, list) else []
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Vergleich: heute gegen die eigene Historie
# ---------------------------------------------------------------------------

def vergleich(gruppe: str, kennzahl: str = "ev_ebitda",
              ebene: str = "sector") -> dict:
    """Wie steht der Sektor heute gegenueber seinem eigenen Schnitt?

    Das ist eine TATSACHE ("Software handelt 45 % unter seinem Schnitt"),
    keine Deutung. Ob die Abwertung zyklisch oder strukturell ist, steht
    hier bewusst nicht - das ist die Frage, die der Mensch beantwortet.
    """
    reihe = lade_reihe(gruppe, ebene)
    werte = [(e.get("datum"), e.get(kennzahl)) for e in reihe
             if e.get(kennzahl) is not None]
    if not werte:
        return {"gruppe": gruppe, "kennzahl": kennzahl, "heute": None,
                "hinweis": "noch keine Messung fuer diesen Sektor"}

    heute = werte[-1][1]
    if len(werte) < MIN_MESSUNGEN:
        return {"gruppe": gruppe, "kennzahl": kennzahl, "heute": heute,
                "messungen": len(werte),
                "hinweis": (f"erst {len(werte)} von {MIN_MESSUNGEN} noetigen "
                            f"Messungen \u2013 die Reihe entsteht ab jetzt")}

    frueher = [v for _d, v in werte[:-1]]
    schnitt = _median(frueher)
    ab = (heute / schnitt - 1.0) * 100 if schnitt else None

    if ab is None:
        urteil, ton = "nicht vergleichbar", "grau"
    elif ab <= -AUFFAELLIG_PCT:
        urteil, ton = "deutlich unter dem eigenen Schnitt", "gelb"
    elif ab >= AUFFAELLIG_PCT:
        urteil, ton = "deutlich ueber dem eigenen Schnitt", "gelb"
    else:
        urteil, ton = "im ueblichen Bereich", "gruen"

    return {"gruppe": gruppe, "kennzahl": kennzahl, "heute": heute,
            "schnitt": round(schnitt, 2) if schnitt else None,
            "abweichung_pct": round(ab, 1) if ab is not None else None,
            "messungen": len(werte),
            "von": werte[0][0], "bis": werte[-1][0],
            "urteil": urteil, "ton": ton}


def anker(gruppe: str, kennzahl: str = "ev_ebitda",
          ebene: str = "sector") -> Optional[float]:
    """Der zuletzt gemessene Median - oder None, wenn keiner vorliegt.

    KEIN Rueckfall auf die feste Tabelle in config: Wer diesen Anker benutzt,
    will ausdruecklich den gemessenen Marktstand. Ein stiller Rueckfall auf
    eine Zahl von 2023 waere genau die Verwechslung, die dieses Modul
    verhindern soll.
    """
    reihe = lade_reihe(gruppe, ebene)
    for e in reversed(reihe):
        if e.get(kennzahl) is not None:
            return float(e[kennzahl])
    return None


def _index_lesen(ebene: str) -> list:
    """Welche Gruppen wurden je gemessen - in Originalschreibweise.

    store legt seine Schluessel in Grossbuchstaben ab. Wer die Ablage direkt
    durchsucht, bekommt "TECHNOLOGY" statt "Technology" und findet mit einem
    kleingeschriebenen Praefix gar nichts. Deshalb ein eigener Index: Er haelt
    die Namen so, wie sie in den Daten stehen.
    """
    import store
    try:
        r = store.get_anreicherung(f"index-{ebene}", "sektorindex",
                                   max_alter_tage=3650)
        return sorted(set(r)) if isinstance(r, list) else []
    except Exception:
        return []


def _index_ergaenzen(gruppen, ebene: str) -> None:
    import store
    vorhanden = set(_index_lesen(ebene))
    neu = vorhanden | {g for g in gruppen if g}
    if neu != vorhanden:
        try:
            store.set_anreicherung(f"index-{ebene}", "sektorindex", sorted(neu))
        except Exception:
            pass


def alle_vergleiche(kennzahl: str = "ev_ebitda", ebene: str = "sector") -> list:
    """Alle gemessenen Sektoren nebeneinander.

    Der Punkt der Uebersicht: Ein einzelner Sektor sagt wenig. Erst
    nebeneinander sieht man, ob EIN Segment abgestraft wird oder der ganze
    Markt nachgibt. Das ist der Unterschied zwischen "Software ist unter
    Druck" und "alles ist billiger geworden".
    """
    out = []
    for gruppe in _index_lesen(ebene):
        v = vergleich(gruppe, kennzahl, ebene)
        if v.get("heute") is not None:
            out.append(v)
    return sorted(out, key=lambda x: (x.get("abweichung_pct") is None,
                                      x.get("abweichung_pct") or 0))
