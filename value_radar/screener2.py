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

__version__ = "2026.09.19"

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
    """Abstand zum Fair Value - gewichtet mit der Verlaesslichkeit des Werts.

    Ein Upside ist nur so gut wie der Fair Value dahinter. Im Kontrolllauf
    landete NVIDIA mit +89 % auf Platz zwei eines VALUE-Profils: volle 100
    Punkte fuer einen Abschlag, der aus einem Fair Value stammt, welcher zu
    83 % aus Multiple-Annahmen besteht und bei dem der DCF als unplausibel
    verworfen wurde. Die uebrigen Bausteine straften das zwar ab, aber das
    Abschlagskriterium mit 30 % Gewicht zog es wieder hoch.

    Deshalb wird der Rohwert gedaempft, wenn die Grundlage duenn ist:
      - Datenbasis eingeschraenkt oder schlechter
      - Fair Value ueberwiegend aus Multiple-Annahmen
    Beides zusammen halbiert den Baustein.
    """
    u = k.upside
    if u is None:
        return None
    wert = _klemm(u / 60.0 * 100.0)

    faktor = 1.0
    if k.datenstufe not in ("vollstaendig", "unbekannt"):
        faktor *= 0.75
    m = k.multiple_anteil
    if m is not None and m > 0.60:
        # linear von 1,0 bei 60 % auf 0,65 bei 90 % Multiple-Anteil
        faktor *= max(0.65, 1.0 - (m - 0.60) * 1.2)
    return _klemm(wert * faktor)


def _b_kurserwartung(k: kd.Kandidat) -> Optional[float]:
    """(Doku am Funktionsende - siehe unten.)"""
    """Wo liegt das eingepreiste Wachstum im realistischen Korridor?

    Unterhalb der Korridormitte = voll, am oberen Rand = 0. Das ist die
    falsifizierbare Fassung von "guenstig": nicht "Kurs unter Fair Value",
    sondern "was der Kurs verlangt, hat die Firma schon geliefert".
    """
    ke = k.kurserwartung or {}
    if ke.get("urteil") == "basis_unklar":
        # Kein Wert statt null Punkte: Ein Baustein ohne Aussage darf den
        # Score nicht nach unten ziehen. Der Anteil fehlenden Gewichts wird
        # ohnehin als "Basis" ausgewiesen.
        return None
    g = ke.get("impliziertes_wachstum")
    kor = ke.get("korridor") or {}
    tief, mitte, hoch = kor.get("tief"), kor.get("mitte"), kor.get("hoch")
    if g is None or mitte is None or hoch is None or tief is None:
        return None
    def _daempfen(w):
        # Steht der Korridor auf zwei Ankern, ist er kaum belastbar. Das darf
        # den Score weder voll nach oben noch voll nach unten treiben.
        return w if ke.get("belastbar") else 50.0 + (w - 50.0) * 0.5

    if g <= tief:
        return _daempfen(100.0)
    if g >= hoch:
        return _daempfen(0.0)
    if g <= mitte:
        anteil = (mitte - g) / (mitte - tief) if mitte > tief else 0.0
        wert = _klemm(60.0 + 40.0 * anteil)
    else:
        anteil = (hoch - g) / (hoch - mitte) if hoch > mitte else 0.0
        wert = _klemm(60.0 * anteil)

    return _daempfen(wert)


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
    """Piotroski, gemindert um einen Beneish-Abzug.

    Beneish schliesst nur noch im Extremfall aus (Standardgrenze plus erhoehte
    Abgrenzungen). Alles darunter gehoert trotzdem ins Ergebnis - aber als
    Abzug, nicht als Todesurteil. So bleibt ein Titel mit auffaelligem M-Wert
    sichtbar und faellt im Rang zurueck, statt kommentarlos zu verschwinden.
    """
    p = (k.forensik.get("piotroski") or {}).get("score")
    if p is None:
        # Finanzwerte: Piotroski nicht definiert. Neutral statt Nullpunkte,
        # sonst faellt der ganze Sektor im Rang zurueck.
        basis = 50.0 if k.forensik.get("finanzwert") else None
    else:
        basis = _klemm(p / 9.0 * 100.0)
    if basis is None:
        return None

    b = k.forensik.get("beneish") or {}
    if b.get("verdaechtig_streng"):
        basis -= 25.0
    elif b.get("verdaechtig"):
        basis -= 10.0
    tata = (b.get("teile") or {}).get("TATA")
    if tata is not None and tata > 0.06:
        basis -= 15.0
    # Altman schliesst nur noch mit zweitem Beleg aus - der Befund selbst
    # gehoert trotzdem in den Rang, sonst verschwindet er ganz.
    a = k.forensik.get("altman") or {}
    if a.get("gefahr") is True:
        basis -= 20.0
    return _klemm(basis)


def _b_cashflow_anteil(k: kd.Kandidat) -> Optional[float]:
    """Je weniger des Fair Value aus Multiple-Annahmen stammt, desto besser."""
    m = k.multiple_anteil
    return None if m is None else _klemm((1.0 - m) * 100.0 / 0.7)


def _b_trend(k: kd.Kandidat) -> Optional[float]:
    """Trendstaerke aus dem Momentum-Modul.

    Der Score dort ist bereits risikoadjustiert und - sofern Sektormediane
    vorliegen - gegen die Branche bereinigt. Hier wird er nur uebernommen.
    """
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
    ("Korridor bis", "Kurs verlangt zu viel"),
    ("Cashflow-Basis", "Reverse DCF ohne Aussage"),
    ("Multiple-Annahmen", "Wert zu stark aus Multiples"),
    ("RSI", "ueberhitzt (RSI)"),
    ("Cashflow", "operativer Cashflow negativ"),
    ("Upside", "kein Abschlag zum Fair Value"),
    ("Score", "kein Score berechenbar"),
    ("traegt den Titel nicht", "Modell traegt den Titel nicht"),
)


#: Zieht den Abstand aus "... (+3.4 Pp.)" heraus.
_KNAPP = __import__("re").compile(r"\(\+([\d.]+) Pp\.\)")


def _grundart(grund: str) -> str:
    for muster, name in _GRUNDARTEN:
        if muster.lower() in grund.lower():
            return name
    return grund.split("(")[0].split("<")[0].strip()


def _entdopple(paare):
    """Mehrfachnotierungen derselben Firma auf eine reduzieren.

    Nach dem flachen Laden liegt der Firmenname vor - darueber laesst sich
    zusammenfuehren, was ueber das Ticker-Symbol nicht geht. Behalten wird die
    Heimatnotierung (Ticker ohne Boersensuffix), sonst die mit der groessten
    Marktkapitalisierung; die Zweitnotierung hat oft duenne Kursdaten.
    """
    def _norm(name):
        n = str(name or "").lower()
        # Reihenfolge zaehlt: laengere Formen zuerst, sonst bleibt aus
        # "corporation" ein "oration" stehen.
        n = n.replace(",", " ").replace(".", " ")
        # Wortweise entfernen statt per Teilstring: "Limited" und "Ltd" sind
        # dieselbe Rechtsform, aber Teilstring-Ersetzung macht aus
        # "BHP Group Limited" ein "bhp limited" und aus "BHP Group Ltd" ein
        # "bhp" - zwei verschiedene Schluessel fuer dieselbe Firma.
        weg = {"corporation", "corp", "incorporated", "inc", "company", "co",
               "holdings", "holding", "group", "plc", "ag", "nv", "sa", "se",
               "ltd", "limited", "the", "class", "a", "b"}
        return " ".join(w for w in n.split() if w not in weg)

    best = {}
    for tk, fd in paare:
        name = _norm(fd.get("name"))
        if not name:
            best[f"__{tk}"] = (tk, fd)          # ohne Namen nicht zusammenfuehren
            continue
        heim = "." not in tk
        mcap = (fd.get("market_cap") or 0) * (fd.get("_fx") or 1.0)
        alt = best.get(name)
        if alt is None:
            best[name] = (tk, fd)
            continue
        a_tk, a_fd = alt
        a_heim = "." not in a_tk
        a_mcap = (a_fd.get("market_cap") or 0) * (a_fd.get("_fx") or 1.0)
        # Reihenfolge der Entscheidung: Stammaktie vor Vorzug, dann
        # Heimatnotierung vor Zweitnotierung, dann Marktkapitalisierung.
        # Ohne die erste Stufe gewinnt bei gleicher Marktkapitalisierung der
        # zufaellig erste Eintrag - so kam BAC-PB statt BAC in die Liste.
        stamm = kd._ist_stammaktie(tk, fd.get("name") or "")
        a_stamm = kd._ist_stammaktie(a_tk, a_fd.get("name") or "")
        if (stamm and not a_stamm) or (
                stamm == a_stamm and ((heim and not a_heim)
                                      or (heim == a_heim and mcap > a_mcap))):
            best[name] = (tk, fd)
    return list(best.values())


@dataclass
class Trichter:
    universum: int = 0
    nach_vorfilter: int = 0
    tief_geprueft: int = 0
    gate_bestanden: int = 0
    # Wie oft trug der Reverse-DCF-Korridor genug Anker, um ueberhaupt
    # ausschliessen zu duerfen? Ohne diese Zahl sieht ein stummes Gate genauso
    # aus wie ein Gate, das nichts zu beanstanden hat.
    korridor_belastbar: int = 0
    korridor_anker: Dict[int, int] = field(default_factory=dict)
    #: (Ticker, Abstand in Prozentpunkten) fuer alle am Korridor Gescheiterten
    korridor_abstand: List[tuple] = field(default_factory=list)
    #: Summierte Dauer je Stufe ueber alle tief geprueften Titel
    zeiten: Dict[str, float] = field(default_factory=dict)
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


#: Welche teuren Zusatzabrufe braucht ein Profil ueberhaupt?
#: Der erste echte Lauf brauchte 20,8 s je Titel - ein Grossteil davon fuer
#: Bausteine, die im jeweiligen Profil gar nicht ins Gewicht gehen.
PROFIL_BEDARF = {
    "value":      {"momentum": False, "historie": True,  "forensik": True},
    "momentum":   {"momentum": True,  "historie": False, "forensik": True},
    "fruehphase": {"momentum": True,  "historie": False, "forensik": True},
}


def lauf(universum: Sequence[str],
         flach_laden: Callable[[str], dict],
         profil: str = "value",
         max_tief: int = 80,
         min_mcap_eur: float = kd.MIN_MARKTKAP_EUR,
         max_mcap_eur: Optional[float] = None,
         fortschritt: Optional[Callable[[float, str], None]] = None,
         parallel: int = 4, gates_aus: bool = False) -> Ergebnis:
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
    # Doppelnotierungen raus, BEVOR das teure Budget verbraucht wird.
    # Im ersten echten Lauf standen HSBA.L neben HSBAL.XC, AZN.L neben AZNL.XC,
    # NVDA neben NVD.DE - collapse_listings() kann das nicht fangen, weil es
    # nach Basissymbol gruppiert und "HSBA" != "HSBAL" ist. Nach dem flachen
    # Laden liegt aber der Firmenname vor, und damit geht es.
    vorher = len(ueberlebende)
    ueberlebende = _entdopple(ueberlebende)
    if vorher > len(ueberlebende):
        t.vorfilter_gruende["Zweitnotierung"] = vorher - len(ueberlebende)
    t.nach_vorfilter = len(ueberlebende)

    # Grosse zuerst: bei begrenztem Budget sind ihre Daten verlaesslicher.
    ueberlebende.sort(key=lambda p: -((p[1].get("market_cap") or 0)
                                      * (p[1].get("_fx") or 1.0)))
    ueberlebende = ueberlebende[:max_tief]

    # --- Stufe 3+4: tiefe Pruefung und Gates ---------------------------
    #
    # Die Zeitmessung ergab: 87 % der Laufzeit stecken im Abruf der
    # Fundamentaldaten (230 von 265 Sekunden bei 30 Titeln). Das ist reine
    # Wartezeit auf Netzwerkantworten, kein Rechnen - dafuer lohnt
    # Parallelisierung.
    #
    # Bewusst niedrig angesetzt: roic hat ein Minutenlimit, und ein Screener,
    # der die Quelle ausbremst, hat nichts gewonnen. Vier gleichzeitige Abrufe
    # sind ein Kompromiss; parallel=1 schaltet zurueck auf nacheinander.
    bedarf = PROFIL_BEDARF.get(profil, PROFIL_BEDARF["value"])

    def _pruefe_einen(tk):
        try:
            return tk, kd.pruefe(tk, mit_momentum=bedarf["momentum"],
                                 mit_historie=bedarf["historie"],
                                 mit_forensik=bedarf["forensik"]), None
        except Exception as e:
            return tk, None, str(e)

    if parallel > 1 and len(ueberlebende) > 1:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=parallel) as pool:
            roh = list(pool.map(lambda p: _pruefe_einen(p[0]), ueberlebende))
    else:
        roh = [_pruefe_einen(tk) for tk, _ in ueberlebende]

    for i, (tk, k, fehler) in enumerate(roh, 1):
        if fortschritt:
            fortschritt(i / max(len(roh), 1),
                        f"Auswertung {tk} ({t.gate_bestanden} Treffer)")
        if fehler or k is None:
            t.fehler.append(f"{tk}: {fehler}")
            continue
        t.tief_geprueft += 1
        for _n, _d in ((k.qualitaet or {}).get("zeiten") or {}).items():
            t.zeiten[_n] = round(t.zeiten.get(_n, 0.0) + _d, 2)
        _ke = k.kurserwartung or {}
        if _ke:
            _n = _ke.get("anker_anzahl", 0)
            t.korridor_anker[_n] = t.korridor_anker.get(_n, 0) + 1
            if _ke.get("belastbar"):
                t.korridor_belastbar += 1

        raus = kd.gate_pruefen(k, profil)

        # KONTROLLLAUF: Gates protokollieren, aber nicht anwenden.
        #
        # Die Trefferliste besteht ueber fuenf Laeufe nur aus Banken und
        # Rohstofftiteln. Zwei Erklaerungen sind moeglich und von aussen nicht
        # zu unterscheiden: Entweder findet ein Value-Filter in einem teuren
        # Markt genau das - oder das Profil hat eine strukturelle Neigung zu
        # niedrigen Multiples, und Qualitaetstitel scheitern systematisch.
        #
        # Mit ausgeschalteten Gates rangieren alle Titel nach Score. Fuehren
        # dann dieselben Zykliker, liegt es am Markt. Tauchen Qualitaetstitel
        # oben auf, liegt es am Profil.
        if gates_aus:
            if raus:
                for g in raus:
                    t.gate_gruende[_grundart(g)] = t.gate_gruende.get(_grundart(g), 0) + 1
            r = rang(k, profil)
            if r["score"] is not None:
                t.gate_bestanden += 1
                erg.treffer.append({**k.as_dict(), "score": r["score"],
                                    "teile": r["teile"], "score_basis": r["basis"],
                                    "score_fehlend": r["fehlend"],
                                    "waere_raus": raus})
            continue

        if raus:
            for g in raus:
                t.gate_gruende[_grundart(g)] = t.gate_gruende.get(_grundart(g), 0) + 1
                _m = _KNAPP.search(g)
                if _m:
                    t.korridor_abstand.append((k.ticker, float(_m.group(1))))
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
    if t.tief_geprueft:
        z.append(f"  Reverse-DCF-Korridor belastbar bei "
                 f"{t.korridor_belastbar} von {t.tief_geprueft} Titeln"
                 + (f" (Ankerverteilung: "
                    + ", ".join(f"{n} Anker: {k}x" for n, k in
                                sorted(t.korridor_anker.items())) + ")"
                    if t.korridor_anker else ""))
        if t.korridor_belastbar == 0 and t.tief_geprueft:
            z.append("  -> Das Gate 'Kurs verlangt zu viel' konnte bei KEINEM "
                     "Titel greifen. Es fehlt Umsatzhistorie, nicht Strenge.")
        elif t.korridor_belastbar < t.tief_geprueft * 0.5:
            z.append("  -> Bei ueber der Haelfte der Titel steht der Korridor "
                     "auf zu wenig Ankern; dort wirkt das Gate nur daempfend.")
    if t.korridor_abstand:
        knapp = sorted(t.korridor_abstand, key=lambda x: x[1])
        nah = [f"{tk} +{d:.1f}" for tk, d in knapp[:5]]
        weit = [f"{tk} +{d:.1f}" for tk, d in knapp[-3:]]
        z.append(f"  Am Korridor gescheitert, knappste: {', '.join(nah)} Pp.")
        z.append(f"  ... deutlichste: {', '.join(weit)} Pp.")
        z.append("  Knappe Faelle sind Grenzfaelle der Annahmen, keine klaren "
                 "Ueberbewertungen - dort lohnt der Einzelblick.")
    if t.zeiten:
        gesamt = sum(t.zeiten.values()) or 1.0
        teile = sorted(t.zeiten.items(), key=lambda x: -x[1])
        z.append("  Zeit je Stufe: " + ", ".join(
            f"{n} {d:.0f}s ({d / gesamt * 100:.0f} %)" for n, d in teile))
    duenn = [x for x in erg.treffer if (x.get("score_basis") or 1) < 0.6]
    if duenn:
        z.append(f"  {len(duenn)} Treffer mit duenner Score-Grundlage "
                 f"(<60 % des Gewichts belegt) - als Schaetzung lesen")
    return z
