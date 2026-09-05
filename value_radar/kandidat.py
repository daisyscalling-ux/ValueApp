"""
kandidat.py - Etappe 1: der gemeinsame Datenvertrag der Entdeckungsschicht.

Bis hierher hatte jedes Modul seine eigene Vorstellung davon, was ein guter
Kandidat ist:

    Screener   boolesche Pflicht-/Bonus-Kriterien auf flachen yfinance-Feldern
    Momentum   additiver 0-100-Score aus sechs Bausteinen
    Radar      fuenf Ebenen mit Maximum-Formel und Koinzidenz-Multiplikator
    scoring    Perzentilrang gegen Peers ueber sechs Kategorien

Vier Ranglisten, vier Definitionen von "gut", keine gemeinsame Grundlage - ein
Titel konnte im Screener durchfallen und im Radar oben stehen, ohne dass sich
sagen liess, welche Aussage stimmt.

Dieses Modul rechnet NICHTS NEU. Es buendelt, was valuation, relval, scores,
momentum und providers ohnehin liefern, zu einem Objekt. Danach beantwortet
genau eine Stelle die Frage "was wissen wir ueber diesen Titel", und die
Suchprofile unterscheiden sich nur noch in Gewichten und Ausschluessen - so
wie die vier Playbooks sich nur in Gewichten unterscheiden, nicht in den
Methoden.

Wichtig: pruefe() ist teuer (deep=True). Es gehoert in Stufe 3 der Pipeline,
NICHT in den Vorfilter. Fuer die breite Vorauswahl gibt es vorfilter().
"""

from __future__ import annotations

__version__ = "2026.09.23"

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Vorfilter (Stufe 2): billig, nur Ausschluesse
# ---------------------------------------------------------------------------

#: Grundsatz: Der Vorfilter darf NIE auf Bewertungskennzahlen filtern.
#: Ein KGV aus dem flachen Pfad ist keine belastbare Groesse - daran zu filtern
#: verwirft gute Titel aus Datengruenden und behaelt schlechte aus demselben.
#: Hier stehen deshalb nur Merkmale, die auch flach verlaesslich sind.

MIN_MARKTKAP_EUR = 3e8          # darunter Liquiditaet und Datenlage zu duenn
MIN_TAGESVOLUMEN_EUR = 5e5      # Handelbarkeit


#: Vorzugsaktien, Bezugsrechte, Optionsscheine, Fondsanteile. Sie tragen den
#: Firmennamen und rutschen deshalb durch jede namensbasierte Zusammenfuehrung.
#: Im 354-Titel-Lauf landete "BAC-PB" - eine Vorzugsaktie von Bank of America -
#: mit +43 % auf Platz eins. Ein Papier mit festem Anspruch hat keinen Fair
#: Value im Sinne eines Eigenkapitalmodells; die Zahl war bedeutungslos.
_NICHT_STAMMAKTIE = (
    "-P", "-PA", "-PB", "-PC", "-PD", "-PE", "-PF", "-PG", "-PH",
    "-PL", "-PK", "-PJ", "-PN", "-PO", "-PQ", "-PR", "-PS", "-PT",
    ".PR", "-WT", "-W", "-U", "-R", "-RT",
)

_FONDS_WOERTER = ("etf", "fund", "trust", "index", "ishares", "spdr",
                  "vanguard", "invesco", "proshares", "preferred",
                  "warrant", "right")


def _ist_stammaktie(ticker: str, name: str = "") -> bool:
    t = (ticker or "").upper()
    if any(t.endswith(x) for x in _NICHT_STAMMAKTIE):
        return False
    n = (name or "").lower()
    if any(w in n for w in _FONDS_WOERTER):
        return False
    return True


def vorfilter(fd: dict, min_mcap_eur: float = MIN_MARKTKAP_EUR,
              max_mcap_eur: Optional[float] = None) -> Optional[str]:
    """Grund fuer den Ausschluss - oder None, wenn der Titel weiterkommt.

    Bewusst als Grund statt als bool: In der Vorauswahl gehen die meisten
    Titel verloren, und ohne Grund laesst sich hinterher nicht sagen, ob das
    Universum oder der Filter das Problem war.
    """
    if not fd or not fd.get("price"):
        return "kein Kurs"
    if not _ist_stammaktie(fd.get("ticker") or "", fd.get("name") or ""):
        return "keine Stammaktie (Vorzug, Bezugsrecht, Fonds)"
    fx = fd.get("_fx") or 1.0
    mcap = (fd.get("market_cap") or 0) * fx
    if mcap < min_mcap_eur:
        return f"Marktkap. zu klein ({mcap / 1e6:.0f} Mio)"
    if max_mcap_eur and mcap > max_mcap_eur:
        return f"Marktkap. zu gross ({mcap / 1e9:.0f} Mrd)"
    if not fd.get("sector"):
        return "kein Sektor - Peer-Vergleich unmoeglich"
    return None


# ---------------------------------------------------------------------------
# Das Kandidat-Objekt
# ---------------------------------------------------------------------------

@dataclass
class Kandidat:
    ticker: str
    name: str = ""
    sektor: Optional[str] = None
    branche: Optional[str] = None
    playbook: Optional[str] = None
    kurs: Optional[float] = None
    waehrung: str = "USD"
    fx: float = 1.0

    fund: Dict[str, Any] = field(default_factory=dict)
    bewertung: Dict[str, Any] = field(default_factory=dict)
    kurserwartung: Dict[str, Any] = field(default_factory=dict)   # Reverse DCF
    forensik: Dict[str, Any] = field(default_factory=dict)
    historie: Dict[str, Any] = field(default_factory=dict)
    momentum: Dict[str, Any] = field(default_factory=dict)
    qualitaet: Dict[str, Any] = field(default_factory=dict)

    fehler: List[str] = field(default_factory=list)

    # -- abgeleitete Bequemlichkeiten -------------------------------------
    @property
    def upside(self) -> Optional[float]:
        return self.bewertung.get("upside_pct")

    @property
    def fair_value(self) -> Optional[float]:
        return self.bewertung.get("fair_value")

    @property
    def datenstufe(self) -> str:
        return (self.qualitaet.get("stufe") or "unbekannt")

    @property
    def multiple_anteil(self) -> Optional[float]:
        return (self.bewertung.get("herkunft") or {}).get("multiple_anteil")

    @property
    def kurs_urteil(self) -> Optional[str]:
        return self.kurserwartung.get("urteil")

    def as_dict(self) -> dict:
        return {
            "ticker": self.ticker, "name": self.name, "sektor": self.sektor,
            "branche": self.branche, "playbook": self.playbook,
            "kurs": self.kurs, "waehrung": self.waehrung, "fx": self.fx,
            "upside": self.upside, "fair_value": self.fair_value,
            "datenstufe": self.datenstufe,
            "multiple_anteil": self.multiple_anteil,
            "kurs_urteil": self.kurs_urteil,
            "momentum_score": self.momentum.get("score"),
            "piotroski": (self.forensik.get("piotroski") or {}).get("score"),
            "altman": (self.forensik.get("altman") or {}).get("z"),
            "beneish": (self.forensik.get("beneish") or {}).get("m"),
            "perzentil": ((self.historie.get("urteil") or {}).get("teuer_pct")),
            "fehler": self.fehler,
        }


# ---------------------------------------------------------------------------
# Tiefe Pruefung (Stufe 3)
# ---------------------------------------------------------------------------

def pruefe(ticker: str, fund: Optional[dict] = None,
           peer_funds=None, mit_momentum: bool = True,
           mit_forensik: bool = True, mit_historie: bool = True) -> Kandidat:
    """Alles, was ueber einen Titel bekannt ist, in einem Objekt.

    fund   bereits geladene Fundamentaldaten (deep!). Fehlt es, wird geladen.
    Jeder Baustein faellt einzeln aus, ohne den Rest mitzureissen - was fehlt,
    steht in .fehler und fuehrt spaeter zum Ausschluss, nicht zu einem stillen
    Naeherungswert.
    """
    import time as _t

    import providers
    import valuation

    k = Kandidat(ticker=ticker)
    _zeit = {}

    def _messe(name, fn):
        """Dauer je Stufe festhalten. Die Screener-Laufzeit lag bei 19 s je
        Titel, und zweimal habe ich die Ursache falsch geraten. Gemessen wird
        nur, wenn jemand danach fragt - der Aufwand ist vernachlaessigbar."""
        _a = _t.perf_counter()
        try:
            return fn()
        finally:
            _zeit[name] = round(_t.perf_counter() - _a, 2)

    if fund is None:
        try:
            fund = _messe("fundamentaldaten",
                          lambda: providers.get_fundamentals(ticker, deep=True) or {})
        except Exception as e:
            k.fehler.append(f"Fundamentaldaten: {e}")
            return k
    k.fund = fund
    if not fund.get("price"):
        k.fehler.append("kein Kurs")
        return k

    k.name = (fund.get("name") or "")[:60]
    k.sektor = fund.get("sector")
    k.branche = fund.get("industry")
    k.kurs = fund.get("price")
    k.waehrung = fund.get("currency") or "USD"
    k.fx = fund.get("_fx") or 1.0

    # --- Bewertung -------------------------------------------------------
    try:
        k.playbook = valuation.classify_playbook(fund)
        v = valuation.fair_value(dict(fund), peer_funds, k.playbook) or {}
        k.bewertung = v
        k.qualitaet = dict(v.get("datenqualitaet") or {})
        k.qualitaet["offene_luecken"] = fund.get("_offene_luecken") or []
        k.qualitaet["vollstaendig"] = bool(fund.get("_vollstaendig"))
        k.qualitaet["roic"] = bool(fund.get("_roic"))
        z = fund.get("_zyklus_diagnose") or {}
        if z:
            k.qualitaet["zyklus"] = z
            if z.get("gipfelverdacht"):
                k.qualitaet.setdefault("hinweise", []).append(
                    f"Gipfelverdacht: aktuelle Marge {z['aktuelle_marge']:.1%} "
                    f"liegt ueber dem Zyklusschnitt {z['schnitt_marge']:.1%} - "
                    f"Gewinnmultiplikatoren sind hier am truegerischsten.")
    except Exception as e:
        k.fehler.append(f"Bewertung: {e}")

    # --- Was der Kurs verlangt (Reverse DCF) ------------------------------
    # WICHTIG: anker_aus_fund() braucht die Umsatzhistorie. Ohne sie bleibt
    # hoechstens der Konsens uebrig, das sind weniger als zwei Anker, und der
    # Reverse DCF faellt aus. Im ersten 30-Titel-Lauf traf das ALLE sechs
    # Treffer - der Baustein mit 25 % Gewicht im Value-Profil, also
    # ausgerechnet die falsifizierbare Fassung von "guenstig", war nie belegt.
    # Erkennbar war das nur an "Basis 75 %" in jeder einzelnen Zeile.
    try:
        historie = fund.get("umsatz_historie")
        if historie is None:
            try:
                # providers.umsatz_historie holt zuerst bei FMP (lange Reihe)
                # und faellt erst dann auf roic zurueck. roic liefert nur fuenf
                # Jahre - damit gibt es weder 5J- noch 10J-Anker, und das
                # Reverse-DCF-Gate ist wirkungslos.
                historie = _messe(
                    "umsatzhistorie",
                    lambda: providers.umsatz_historie(ticker, 15) or [])
            except Exception:
                historie = None
        anker = valuation.anker_aus_fund(fund, historie=historie)
        vorhanden = sum(1 for x in ("cagr_3j", "cagr_5j", "cagr_10j", "konsens")
                        if anker.get(x) is not None)
        if vorhanden >= 2:
            rd = _messe("reverse_dcf", lambda: valuation.reverse_dcf_analyse(
                fund, anker, k.playbook or "quality", mit_gitter=False))
            k.kurserwartung = rd or {}
        else:
            k.fehler.append("Reverse DCF: zu wenig Umsatzhistorie")
    except Exception as e:
        k.fehler.append(f"Reverse DCF: {e}")

    # --- Forensik ---------------------------------------------------------
    if mit_forensik:
        try:
            k.forensik = _messe("forensik", lambda: _forensik(ticker, fund))
        except Exception as e:
            k.fehler.append(f"Forensik: {e}")

    # --- Bewertungshistorie ----------------------------------------------
    if mit_historie:
        try:
            import relval
            k.historie = _messe("historie", lambda: relval.bericht(fund) or {})
        except Exception as e:
            k.fehler.append(f"Historie: {e}")

    # --- Momentum ---------------------------------------------------------
    if mit_momentum:
        try:
            import momentum as mom
            k.momentum = _messe("momentum",
                                lambda: mom.bausteine(ticker, fund) or {})
        except Exception as e:
            k.fehler.append(f"Momentum: {e}")

    k.qualitaet["zeiten"] = _zeit
    return k


def _forensik(ticker: str, fund: dict) -> dict:
    """Piotroski F, Altman Z, Beneish M - bisher nur in der Einzelanalyse.

    Genau die Werkzeuge, die eine Value-Trap erkennen, liefen im Screener nie.
    Der dortige Filter waren drei Zeilen in scoring._value_trap().
    """
    import roic
    import scores

    out: Dict[str, Any] = {}
    if not roic.enabled():
        out["hinweis"] = "roic inaktiv - keine Jahresabschluesse verfuegbar"
        return out
    try:
        inc = roic.income_annual(ticker, limit=3) or []
        bal = roic.balance_annual(ticker, limit=3) or []
        cf = roic.cashflow_annual(ticker, limit=3) or []
        akt, vorjahr = scores.jahres_paar(inc, bal, cf)
    except Exception as e:
        out["hinweis"] = f"Jahresabschluesse nicht ladbar: {e}"
        return out
    if not akt or not vorjahr:
        out["hinweis"] = "kein vollstaendiges Jahrespaar"
        return out
    sektor = fund.get("sector")
    # Signaturen laut scores.py:
    #   piotroski_f(akt, vorjahr, sektor=, fund=)  -> {"score", "details", ...}
    #   altman_z(akt, sektor=, fund=)              -> {"z", "zone", "gefahr"}
    #   beneish_m(akt, vorjahr, sektor=, fund=)    -> {"m", "verdaechtig", ...}
    # Alle drei geben bei Finanzwerten None zurueck - das ist kein Fehler,
    # sondern die richtige Antwort (Piotroski und Altman sind fuer Banken
    # nicht definiert).
    try:
        out["piotroski"] = scores.piotroski_f(akt, vorjahr, sektor=sektor,
                                              fund=fund) or {}
    except Exception as e:
        out["piotroski"] = {"fehler": str(e)}
    try:
        out["altman"] = scores.altman_z(akt, sektor=sektor, fund=fund) or {}
    except Exception as e:
        out["altman"] = {"fehler": str(e)}
    try:
        out["beneish"] = scores.beneish_m(akt, vorjahr, sektor=sektor,
                                          fund=fund) or {}
    except Exception as e:
        out["beneish"] = {"fehler": str(e)}
    out["finanzwert"] = scores._ist_finanzwert(sektor, fund)
    return out


# ---------------------------------------------------------------------------
# Gates (Stufe 4, vor der Rangbildung)
# ---------------------------------------------------------------------------

#: Ausschluesse statt Punktabzuege. Bisher kostete eine Value-Trap 20 Punkte
#: und der Titel stand trotzdem oben. Ein Kandidat, dessen Fair Value auf
#: halber Datenbasis steht, gehoert in keine Rangliste - egal wie gut die Zahl
#: aussieht. Das ist die Lehre aus dem NVDA-Fall: nicht der Wert war falsch,
#: sondern seine Grundlage unvollstaendig, und niemand hat es gesehen.

GATES = {
    "value": {
        "datenstufe_max": "eingeschraenkt",
        "piotroski_min": 5,
        "beneish_unauffaellig": True,
        "altman_kein_distress": True,
        "kurs_urteil_verboten": ("zu_optimistisch",),
        # Erster echter Lauf: AAPL 79 %, MSFT 79 %, MU 79 %, NVDA 84 %,
        # AZN 81 %, BHP 76 %. Bei 0,75 faellt damit praktisch jeder Standardwert
        # durch - nicht weil die Titel schlecht waeren, sondern weil der DCF bei
        # ihnen regelmaessig als unplausibel verworfen wird und der Fair Value
        # dann fast nur noch aus Multiples besteht.
        #
        # Der Befund bleibt richtig, taugt aber nicht als absolutes Ausschluss-
        # kriterium: Ein Gate, das die halbe Welt aussortiert, trennt nicht mehr.
        # Harte Grenze deshalb bei 0,90 ("gar kein Cashflow-Gehalt"), der Bereich
        # dazwischen kostet Punkte im Rang (screener2._b_cashflow_anteil).
        "multiple_anteil_max": 0.90,
        # Ein Value-Treffer ohne Abschlag zum Fair Value ist keiner. Ohne diese
        # Grenze trugen im Test die uebrigen Bausteine (Perzentil, Reverse DCF)
        # Titel mit -10 % Upside in die Liste - fachlich vertretbar, aber unter
        # der Ueberschrift "Value" irrefuehrend.
        "upside_min": 0.0,
    },
    "momentum": {
        "datenstufe_max": "eingeschraenkt",
        "beneish_unauffaellig": True,
        "rsi_max": 85.0,
        "operativer_cashflow_positiv": True,
    },
    "fruehphase": {
        "datenstufe_max": "kritisch",      # hier ist Unschaerfe systembedingt
        "beneish_unauffaellig": True,
    },
}

_STUFEN_RANG = {"vollstaendig": 0, "eingeschraenkt": 1, "kritisch": 2,
                "nicht belastbar": 3, "unbekannt": 2}


def gate_pruefen(k: Kandidat, profil: str = "value") -> List[str]:
    """Gruende, warum dieser Kandidat NICHT in die Rangliste gehoert.

    Leere Liste = besteht. Die Gruende werden zurueckgegeben statt nur
    True/False, damit eine schrumpfende Trefferliste erklaerbar bleibt.
    """
    g = GATES.get(profil, GATES["value"])
    raus: List[str] = []

    grenze = _STUFEN_RANG.get(g.get("datenstufe_max", "kritisch"), 2)
    if _STUFEN_RANG.get(k.datenstufe, 2) > grenze:
        raus.append(f"Datenbasis {k.datenstufe}")

    # "nicht belastbar" schliesst in JEDEM Profil aus, auch in der Fruehphase.
    # Dort ist Unschaerfe systembedingt - aber ein Fair Value auf weniger als
    # der Haelfte der Verfahren ist keine Unschaerfe, sondern eine Luecke.
    if (k.qualitaet or {}).get("nicht_belastbar"):
        anteil = (k.qualitaet or {}).get("gewicht_weg")
        raus.append(f"Bewertungsmodell traegt den Titel nicht"
                    + (f" ({anteil:.0%} der Verfahren ohne Ergebnis)" if anteil else ""))

    # Bei Finanzwerten geben Piotroski und Altman bewusst nichts zurueck -
    # die Kennzahlen sind fuer Banken nicht definiert. Das darf kein Ausschluss
    # sein, sonst faellt der gesamte Sektor durch ein Gate, das ihn gar nicht
    # bewerten kann.
    _finanz = bool(k.forensik.get("finanzwert"))
    # Ist die Forensik SYSTEMWEIT nicht verfuegbar (roic aus, Kontingent leer),
    # ist das kein Mangel des Titels. Vorher fielen dadurch ALLE Kandidaten
    # durch - im ersten echten Lauf 24 von 24 mit "Piotroski nicht berechenbar".
    # Ein Gate, das bei einem Konfigurationsproblem die ganze Welt aussortiert,
    # misst nichts. Es wird deshalb ausgesetzt und der Titel markiert.
    _forensik_aus = bool(k.forensik.get("hinweis"))
    if _forensik_aus:
        k.qualitaet.setdefault("ohne_forensik", True)

    if g.get("piotroski_min") is not None and not _finanz and not _forensik_aus:
        p = (k.forensik.get("piotroski") or {}).get("score")
        if p is None:
            raus.append("Piotroski nicht berechenbar")
        elif p < g["piotroski_min"]:
            raus.append(f"Piotroski F {p} < {g['piotroski_min']}")

    if g.get("beneish_unauffaellig") and not _forensik_aus:
        b = k.forensik.get("beneish") or {}
        # AUSSCHLUSS nur, wenn zwei unabhaengige Bedingungen zusammenkommen:
        # Beneishs eigene Standardgrenze (-1,78, nicht die empfindliche -2,22)
        # UND erhoehte Abgrenzungen. TATA misst, ob der Gewinn durch operativen
        # Cashflow gedeckt ist - das ist der Kern des Manipulationsverdachts.
        # Der Gesamtscore allein reicht nicht: Er wird bei wachsenden Firmen
        # mechanisch vom Umsatzindex hochgezogen.
        #
        # Alles darunter kostet Punkte im Rang (screener2._b_bilanz), schliesst
        # aber nicht aus. Beneish ist ein Screening-Werkzeug mit bekannt hoher
        # Fehlalarmquote - als alleiniges Ausschlusskriterium ueberfordert.
        _m = b.get("m")
        _tata = (b.get("teile") or {}).get("TATA")
        if b.get("verdaechtig_streng") and _tata is not None and _tata > 0.06:
            raus.append(f"Beneish M {_m} und Abgrenzungen {_tata:.3f} - "
                        f"Gewinn nicht cashgedeckt")
        elif b.get("verdaechtig"):
            k.qualitaet.setdefault("hinweise", []).append(
                f"Beneish M {_m} ueber der empfindlichen Warnschwelle "
                f"(-2,22), aber "
                + ("unter Beneishs Standardgrenze (-1,78)"
                   if not b.get("verdaechtig_streng")
                   else f"Abgrenzungen unauffaellig (TATA {_tata})")
                + " - Abzug im Rang statt Ausschluss.")

    if g.get("altman_kein_distress") and not _finanz and not _forensik_aus:
        a = k.forensik.get("altman") or {}
        if a.get("gefahr") is True:
            # Dieselbe Vorsicht wie bei Beneish: Altman Z ist an Industrie-
            # unternehmen der 1960er kalibriert und schlaegt bei allem an, was
            # viel Firmenwert und Akquisitionsschulden traegt. Im Kontrolllauf
            # traf es Smucker (Z 1,37) und Occidental (Z 1,27) - beide
            # verschuldet, aber nicht in Not.
            #
            # Ausschluss deshalb nur mit einem zweiten, unabhaengigen Beleg
            # fuer tatsaechliche Enge: Zinsdeckung unter 3 oder eine
            # Nettoverschuldung ueber dem Vierfachen des EBITDA. Ohne diesen
            # Beleg bleibt es ein Abzug im Rang.
            _f = k.fund or {}
            _deckung = _f.get("interest_coverage")
            _nd = _f.get("net_debt_ebitda")
            _eng = ((_deckung is not None and _deckung < 3.0)
                    or (_nd is not None and _nd > 4.0))
            if _eng:
                raus.append(f"Altman Z {a.get('z')} und angespannte Finanzlage "
                            f"(Zinsdeckung {_deckung}, Nettoschulden/EBITDA {_nd})")
            else:
                k.qualitaet.setdefault("hinweise", []).append(
                    f"Altman Z {a.get('z')} unter der Schwelle, aber Zinsdeckung "
                    f"und Verschuldung unauffaellig - Abzug im Rang statt "
                    f"Ausschluss.")

    # "basis_unklar" ist KEIN Ausschluss wegen Ueberbewertung. Der Reverse DCF
    # traegt den Titel nur nicht - das gehoert als Hinweis vermerkt, damit der
    # Baustein nicht stillschweigend mit 0 Punkten in den Rang eingeht.
    if k.kurs_urteil == "basis_unklar":
        k.qualitaet.setdefault("hinweise", []).append(
            "Reverse DCF ohne Aussage: heutiger Cashflow als Ausgangspunkt zu "
            "niedrig. Bewertung stuetzt sich auf die uebrigen Bausteine.")

    verboten = g.get("kurs_urteil_verboten") or ()
    if k.kurs_urteil in verboten:
        # Nur ausschliessen, wenn der Korridor auf mindestens drei Ankern
        # steht. Mit zwei Ankern ist er der Abstand zwischen zwei Zahlen -
        # bei UnitedHealth ergab das -15,7 % bis 11,4 %, bei Eli Lilly
        # 36,5 % bis 95,0 %. Beides bewertet nichts.
        #
        # Der Grund ist Datenmangel, nicht Methodik: roic lieferte nur fuenf
        # Jahre Umsatzhistorie, damit gibt es weder 5J- noch 10J-Anker.
        if (k.kurserwartung or {}).get("belastbar"):
            # Abstand zum Korridor mitgeben. "Zu viel verlangt" ist bei +2 Pp.
            # etwas anderes als bei +20 Pp. - ohne die Zahl laesst sich ein
            # knapper Ausschluss nicht von einem klaren unterscheiden, und bei
            # 22 von 30 Ausschluessen ist genau das die Frage.
            _ke = k.kurserwartung
            _g = _ke.get("impliziertes_wachstum")
            _hoch = (_ke.get("korridor") or {}).get("hoch")
            if _g is not None and _hoch is not None:
                raus.append(
                    f"Kurs verlangt {_g * 100:.1f} %, Korridor bis "
                    f"{_hoch * 100:.1f} % (+{(_g - _hoch) * 100:.1f} Pp.)")
            else:
                raus.append("Kurs verlangt mehr als das realistisch Lieferbare")
        else:
            n = (k.kurserwartung or {}).get("anker_anzahl", 0)
            k.qualitaet.setdefault("hinweise", []).append(
                f"Kurs verlangt mehr als der Korridor hergibt - aber der "
                f"Korridor steht nur auf {n} Ankern. Als Hinweis gewertet, "
                f"nicht als Ausschluss.")

    if g.get("multiple_anteil_max") is not None and k.multiple_anteil is not None:
        if k.multiple_anteil > g["multiple_anteil_max"]:
            raus.append(f"Fair Value zu {k.multiple_anteil:.0%} aus "
                        f"Multiple-Annahmen")

    if g.get("upside_min") is not None:
        u = k.upside
        if u is None:
            raus.append("kein Upside berechenbar")
        elif u <= g["upside_min"]:
            raus.append(f"kein Abschlag zum Fair Value (Upside {u:+.0f} %)")

    if g.get("rsi_max") is not None:
        # momentum.bausteine setzt "ueberhitzt" selbst; der Rohwert bleibt als
        # Rueckfall, falls das Momentum-Modul aelter ist.
        if k.momentum.get("ueberhitzt"):
            raus.append(f"RSI {k.momentum.get('rsi', 0):.0f} - ueberhitzt, "
                        f"Einstieg jetzt ungeeignet")
        else:
            rsi = k.momentum.get("rsi")
            if rsi is not None and rsi > g["rsi_max"]:
                raus.append(f"RSI {rsi:.0f} - ueberhitzt")

    if g.get("operativer_cashflow_positiv"):
        ocf = k.fund.get("operating_cashflow")
        if ocf is not None and ocf <= 0:
            raus.append("operativer Cashflow negativ")

    return raus
