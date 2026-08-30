"""
screener2.py - Etappe 2+3: zweistufige Kandidatensuche.

Was sich gegenueber dem bisherigen Screener aendert:

  ALT   Universum -> alle Titel FLACH laden (deep=False) -> auf pe/pb/peg
        filtern -> fair_value auf denselben flachen Daten -> Liste.

        Problem: Gefiltert wurde auf genau den Feldern, deren Unzuverlaessigkeit
        uns Tage gekostet hat. Der Fair Value stand auf halber Datenbasis - und
        niemand hat es gesehen, weil im Screener keine Warnung erscheint.

  NEU   Universum -> Vorfilter (flach, NUR Ausschluesse: Kurs, Marktkap,
        Sektor) -> tiefe Pruefung nur fuer die Ueberlebenden (roic, Forensik,
        Reverse DCF, Datenqualitaet) -> Gates -> Rangbildung.

Der Bruch zwischen Stufe 2 und 3 ist die eigentliche Entscheidung: Der
Vorfilter darf NIE auf Bewertungskennzahlen filtern. Ein KGV aus dem flachen
Pfad verwirft gute Titel aus Datengruenden und behaelt schlechte aus demselben.

Jeder Lauf liefert einen TRICHTER: wie viele Titel an welcher Stufe
ausgeschieden sind und warum. Eine kurze Trefferliste ist damit erklaerbar
statt verdaechtig.
"""

from __future__ import annotations

__version__ = "2026.09.02"

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence

import kandidat as kd

# ---------------------------------------------------------------------------
# Rangbildung
# ---------------------------------------------------------------------------

#: Bausteine je Suchprofil. Jeder liefert 0-100. Die Gewichte sind bewusst
#: sichtbar und einzeln nachvollziehbar - ein Gesamtscore ohne Aufschluesselung
#: ist eine Meinung mit Nachkommastellen.
PROFILE: Dict[str, Dict[str, float]] = {
    "value": {
        "abschlag": 0.30,        # wie weit unter dem Fair Value
        "kurserwartung": 0.25,   # wie viel der Kurs verlangt (Reverse DCF)
        "historie": 0.20,        # Perzentil in der eigenen Bewertungshistorie
        "bilanz": 0.15,          # Piotroski
        "cashflow_anteil": 0.10, # wie wenig der Wert aus Multiples stammt
    },
    "momentum": {
        "trend": 0.45,
        "relative_staerke": 0.25,
        "bilanz": 0.15,
        "abschlag": 0.15,
    },
    "fruehphase": {
        "beschleunigung": 0.40,
        "trend": 0.25,
        "bilanz": 0.20,
        "abschlag": 0.15,
    },
}


def _klemm(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def _b_abschlag(k: kd.Kandidat) -> Optional[float]:
    """Abstand zum Fair Value. 0 % Upside = 0 Punkte, +60 % = 100."""
    u = k.upside
    return None if u is None else _klemm(u / 60.0 * 100.0)


def _b_kurserwartung(k: kd.Kandidat) -> Optional[float]:
    """Wo liegt das eingepreiste Wachstum im realistischen Korridor?

    Unterhalb der Korridormitte = voll, am oberen Rand = 0. Das ist die
    falsifizierbare Fassung von "guenstig": nicht "Kurs unter Fair Value",
    sondern "was der Kurs verlangt, hat die Firma schon geliefert".
    """
    ke = k.kurserwartung or {}
    g = ke.get("impliziertes_wachstum")
    kor = ke.get("korridor") or {}
    tief, mitte, hoch = kor.get("tief"), kor.get("mitte"), kor.get("hoch")
    if g is None or mitte is None or hoch is None or tief is None:
        return None
    if g <= tief:
        return 100.0
    if g >= hoch:
        return 0.0
    if g <= mitte:
        anteil = (mitte - g) / (mitte - tief) if mitte > tief else 0.0
        return _klemm(60.0 + 40.0 * anteil)
    anteil = (hoch - g) / (hoch - mitte) if hoch > mitte else 0.0
    return _klemm(60.0 * anteil)


def _b_historie(k: kd.Kandidat) -> Optional[float]:
    """Perzentil in der eigenen Bewertungshistorie. Guenstig = viele Punkte.

    Annahmefrei: kein Wachstumsmodell, keine Kapitalkosten, keine
    Terminalannahme - nur die Frage, wo der Titel in seiner eigenen
    Verteilung steht.
    """
    u = (k.historie or {}).get("urteil") or {}
    p = u.get("teuer_pct")
    return None if p is None else _klemm(100.0 - p)


def _b_bilanz(k: kd.Kandidat) -> Optional[float]:
    p = (k.forensik.get("piotroski") or {}).get("score")
    if p is None:
        # Finanzwerte: Piotroski nicht definiert. Neutral statt Nullpunkte,
        # sonst faellt der ganze Sektor im Rang zurueck.
        return 50.0 if k.forensik.get("finanzwert") else None
    return _klemm(p / 9.0 * 100.0)


def _b_cashflow_anteil(k: kd.Kandidat) -> Optional[float]:
    """Je weniger des Fair Value aus Multiple-Annahmen stammt, desto besser."""
    m = k.multiple_anteil
    return None if m is None else _klemm((1.0 - m) * 100.0 / 0.7)


def _b_trend(k: kd.Kandidat) -> Optional[float]:
    s = (k.momentum or {}).get("score")
    return None if s is None else _klemm(float(s))


def _b_relative_staerke(k: kd.Kandidat) -> Optional[float]:
    rs = (k.momentum or {}).get("rel_staerke")
    return None if rs is None else _klemm(50.0 + rs * 2.0)


def _b_beschleunigung(k: kd.Kandidat) -> Optional[float]:
    """Nimmt das Umsatzwachstum zu? Fuer die Fruehphase das Kernsignal."""
    f = k.fund or {}
    g_neu, g_alt = f.get("revenue_growth"), f.get("revenue_growth_vorjahr")
    if g_neu is None:
        return None
    if g_alt is None:
        return _klemm(g_neu / 0.40 * 100.0)
    return _klemm(50.0 + (g_neu - g_alt) / 0.20 * 50.0)


BAUSTEINE: Dict[str, Callable[[kd.Kandidat], Optional[float]]] = {
    "abschlag": _b_abschlag,
    "kurserwartung": _b_kurserwartung,
    "historie": _b_historie,
    "bilanz": _b_bilanz,
    "cashflow_anteil": _b_cashflow_anteil,
    "trend": _b_trend,
    "relative_staerke": _b_relative_staerke,
    "beschleunigung": _b_beschleunigung,
}


def rang(k: kd.Kandidat, profil: str = "value") -> dict:
    """Score plus Aufschluesselung.

    Fehlende Bausteine werden herausgerechnet - ABER der Anteil des
    fehlenden Gewichts wird ausgewiesen. Im Radar hatte genau diese
    Normalisierung dazu gefuehrt, dass ein einzelnes Signal so viel wog wie
    vier: wer nur einen Baustein hat, bekam die volle Punktzahl. Hier steht
    daneben, auf wie viel Grundlage der Score steht.
    """
    gew = PROFILE.get(profil, PROFILE["value"])
    teile, fehlend = {}, []
    summe = w_summe = 0.0
    for name, w in gew.items():
        fn = BAUSTEINE.get(name)
        wert = fn(k) if fn else None
        if wert is None:
            fehlend.append(name)
            continue
        teile[name] = round(wert, 1)
        summe += wert * w
        w_summe += w

    if w_summe <= 0:
        return {"score": None, "teile": {}, "fehlend": fehlend, "basis": 0.0}

    return {
        "score": round(summe / w_summe, 1),
        "teile": teile,
        "fehlend": fehlend,
        # Anteil des Gewichts, der tatsaechlich belegt ist. Unter 0,6 ist der
        # Score eine Schaetzung, keine Messung.
        "basis": round(w_summe / sum(gew.values()), 2),
    }


# ---------------------------------------------------------------------------
# Lauf
# ---------------------------------------------------------------------------

#: Ausschlussgruende enthalten konkrete Zahlen ("Piotroski F 3 < 5", "zu 83 %
#: aus Multiple-Annahmen"). Fuer die Trichter-Statistik zaehlt die ART, nicht
#: der Wert - sonst steht dieselbe Ursache dreimal mit verschiedenen Prozenten
#: in der Liste.
_GRUNDARTEN = (
    ("Datenbasis", "Datenbasis unzureichend"),
    ("Piotroski", "Piotroski zu niedrig"),
    ("Beneish", "Bilanzverdacht (Beneish)"),
    ("Altman", "Insolvenzgefahr (Altman)"),
    ("Kurs verlangt", "Kurs verlangt zu viel"),
    ("Multiple-Annahmen", "Wert zu stark aus Multiples"),
    ("RSI", "ueberhitzt (RSI)"),
    ("Cashflow", "operativer Cashflow negativ"),
    ("Upside", "kein Abschlag zum Fair Value"),
    ("Score", "kein Score berechenbar"),
)


def _grundart(grund: str) -> str:
    for muster, name in _GRUNDARTEN:
        if muster.lower() in grund.lower():
            return name
    return grund.split("(")[0].split("<")[0].strip()


@dataclass
class Trichter:
    universum: int = 0
    nach_vorfilter: int = 0
    tief_geprueft: int = 0
    gate_bestanden: int = 0
    vorfilter_gruende: Dict[str, int] = field(default_factory=dict)
    gate_gruende: Dict[str, int] = field(default_factory=dict)
    fehler: List[str] = field(default_factory=list)

    def text(self) -> List[str]:
        z = [f"Universum {self.universum}",
             f"nach Vorfilter {self.nach_vorfilter}",
             f"tief geprueft {self.tief_geprueft}",
             f"Gates bestanden {self.gate_bestanden}"]
        return z


@dataclass
class Ergebnis:
    treffer: List[dict] = field(default_factory=list)
    ausgeschlossen: List[dict] = field(default_factory=list)
    trichter: Trichter = field(default_factory=Trichter)
    profil: str = "value"


def lauf(universum: Sequence[str],
         flach_laden: Callable[[str], dict],
         profil: str = "value",
         max_tief: int = 80,
         min_mcap_eur: float = kd.MIN_MARKTKAP_EUR,
         max_mcap_eur: Optional[float] = None,
         fortschritt: Optional[Callable[[float, str], None]] = None) -> Ergebnis:
    """Vier Stufen. `flach_laden` ist der billige Loader (deep=False).

    max_tief begrenzt die teure Stufe. Die Auswahl trifft dabei NICHT der
    Zufall, sondern die Marktkapitalisierung - das ist willkuerlich, aber
    wenigstens nachvollziehbar willkuerlich. Wer mehr will, erhoeht max_tief.
    """
    erg = Ergebnis(profil=profil)
    t = erg.trichter
    t.universum = len(universum)

    # --- Stufe 2: Vorfilter -------------------------------------------
    ueberlebende = []
    for i, tk in enumerate(universum, 1):
        try:
            fd = flach_laden(tk) or {}
        except Exception as e:
            t.fehler.append(f"{tk}: {e}")
            continue
        grund = kd.vorfilter(fd, min_mcap_eur, max_mcap_eur)
        if grund:
            schluessel = grund.split("(")[0].strip()
            t.vorfilter_gruende[schluessel] = t.vorfilter_gruende.get(schluessel, 0) + 1
            continue
        ueberlebende.append((tk, fd))
        if fortschritt:
            fortschritt(i / max(len(universum), 1), f"Vorfilter {tk}")
    t.nach_vorfilter = len(ueberlebende)

    # Grosse zuerst: bei begrenztem Budget sind ihre Daten verlaesslicher.
    ueberlebende.sort(key=lambda p: -((p[1].get("market_cap") or 0)
                                      * (p[1].get("_fx") or 1.0)))
    ueberlebende = ueberlebende[:max_tief]

    # --- Stufe 3+4: tiefe Pruefung und Gates ---------------------------
    for i, (tk, _fd) in enumerate(ueberlebende, 1):
        if fortschritt:
            fortschritt(i / max(len(ueberlebende), 1),
                        f"Tiefe Pruefung {tk} ({t.gate_bestanden} Treffer)")
        try:
            k = kd.pruefe(tk)
        except Exception as e:
            t.fehler.append(f"{tk}: {e}")
            continue
        t.tief_geprueft += 1

        raus = kd.gate_pruefen(k, profil)
        if raus:
            for g in raus:
                t.gate_gruende[_grundart(g)] = t.gate_gruende.get(_grundart(g), 0) + 1
            erg.ausgeschlossen.append({**k.as_dict(), "gruende": raus})
            continue

        r = rang(k, profil)
        if r["score"] is None:
            t.gate_gruende["kein Score berechenbar"] = \
                t.gate_gruende.get("kein Score berechenbar", 0) + 1
            erg.ausgeschlossen.append({**k.as_dict(),
                                       "gruende": ["kein Score berechenbar"]})
            continue

        t.gate_bestanden += 1
        erg.treffer.append({**k.as_dict(), "score": r["score"],
                            "teile": r["teile"], "score_basis": r["basis"],
                            "score_fehlend": r["fehlend"]})

    erg.treffer.sort(key=lambda z: -(z.get("score") or 0))
    return erg


# ---------------------------------------------------------------------------
# Gegenprobe gegen den alten Weg
# ---------------------------------------------------------------------------

def vergleich(erg: Ergebnis, alt_treffer: Sequence[str]) -> dict:
    """Was haette der alte Filter geliefert, was liefert der neue?

    Ersetzt die fehlende Messlatte: Statt vier Wochen auf Trackrecord-Daten
    zu warten, wird im selben Lauf sichtbar, welche Titel neu dazukommen,
    welche wegfallen - und aus welchem Grund sie wegfallen. Ein Titel, der
    nur wegen "Datenbasis kritisch" verschwindet, ist ein anderer Fall als
    einer mit Bilanzverdacht.
    """
    neu = {z["ticker"] for z in erg.treffer}
    alt = set(alt_treffer)
    raus_gruende = {z["ticker"]: z.get("gruende", [])
                    for z in erg.ausgeschlossen}
    return {
        "in_beiden": sorted(neu & alt),
        "nur_neu": sorted(neu - alt),
        "nur_alt": sorted(alt - neu),
        "warum_weg": {t: raus_gruende.get(t, ["im Vorfilter oder nicht geprueft"])
                      for t in sorted(alt - neu)},
        "alt_n": len(alt), "neu_n": len(neu),
    }


def bericht(erg: Ergebnis) -> List[str]:
    """Der Trichter als lesbare Zeilen - fuer Konsole und Dashboard."""
    t = erg.trichter
    z = [f"Trichter: {' -> '.join(t.text())}"]
    if t.vorfilter_gruende:
        z.append("  Im Vorfilter ausgeschieden: " + ", ".join(
            f"{k} ({n})" for k, n in
            sorted(t.vorfilter_gruende.items(), key=lambda x: -x[1])))
    if t.gate_gruende:
        z.append("  An den Gates ausgeschieden: " + ", ".join(
            f"{k} ({n})" for k, n in
            sorted(t.gate_gruende.items(), key=lambda x: -x[1])))
    if t.fehler:
        z.append(f"  Fehler bei {len(t.fehler)} Titeln")
    duenn = [x for x in erg.treffer if (x.get("score_basis") or 1) < 0.6]
    if duenn:
        z.append(f"  {len(duenn)} Treffer mit duenner Score-Grundlage "
                 f"(<60 % des Gewichts belegt) - als Schaetzung lesen")
    return z
