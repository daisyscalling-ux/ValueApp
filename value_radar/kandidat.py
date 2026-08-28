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

__version__ = "2026.08.31"

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


def vorfilter(fd: dict, min_mcap_eur: float = MIN_MARKTKAP_EUR,
              max_mcap_eur: Optional[float] = None) -> Optional[str]:
    """Grund fuer den Ausschluss - oder None, wenn der Titel weiterkommt.

    Bewusst als Grund statt als bool: In der Vorauswahl gehen die meisten
    Titel verloren, und ohne Grund laesst sich hinterher nicht sagen, ob das
    Universum oder der Filter das Problem war.
    """
    if not fd or not fd.get("price"):
        return "kein Kurs"
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
    import providers
    import valuation

    k = Kandidat(ticker=ticker)

    if fund is None:
        try:
            fund = providers.get_fundamentals(ticker, deep=True) or {}
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
    except Exception as e:
        k.fehler.append(f"Bewertung: {e}")

    # --- Was der Kurs verlangt (Reverse DCF) ------------------------------
    try:
        anker = valuation.anker_aus_fund(fund)
        vorhanden = sum(1 for x in ("cagr_3j", "cagr_5j", "cagr_10j", "konsens")
                        if anker.get(x) is not None)
        if vorhanden >= 2:
            rd = valuation.reverse_dcf_analyse(fund, anker, k.playbook or "quality",
                                               mit_gitter=False)
            k.kurserwartung = rd or {}
        else:
            k.fehler.append("Reverse DCF: zu wenig Umsatzhistorie")
    except Exception as e:
        k.fehler.append(f"Reverse DCF: {e}")

    # --- Forensik ---------------------------------------------------------
    if mit_forensik:
        try:
            k.forensik = _forensik(ticker, fund)
        except Exception as e:
            k.fehler.append(f"Forensik: {e}")

    # --- Bewertungshistorie ----------------------------------------------
    if mit_historie:
        try:
            import relval
            k.historie = relval.bericht(fund) or {}
        except Exception as e:
            k.fehler.append(f"Historie: {e}")

    # --- Momentum ---------------------------------------------------------
    if mit_momentum:
        try:
            import momentum as mom
            k.momentum = mom.bausteine(ticker, fund) or {}
        except Exception as e:
            k.fehler.append(f"Momentum: {e}")

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
        "multiple_anteil_max": 0.75,
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
                "unbekannt": 2}


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

    # Bei Finanzwerten geben Piotroski und Altman bewusst nichts zurueck -
    # die Kennzahlen sind fuer Banken nicht definiert. Das darf kein Ausschluss
    # sein, sonst faellt der gesamte Sektor durch ein Gate, das ihn gar nicht
    # bewerten kann.
    _finanz = bool(k.forensik.get("finanzwert"))
    if g.get("piotroski_min") is not None and not _finanz:
        p = (k.forensik.get("piotroski") or {}).get("score")
        if p is None:
            raus.append("Piotroski nicht berechenbar")
        elif p < g["piotroski_min"]:
            raus.append(f"Piotroski F {p} < {g['piotroski_min']}")

    if g.get("beneish_unauffaellig"):
        b = k.forensik.get("beneish") or {}
        if b.get("verdaechtig") is True:
            raus.append(f"Beneish M {b.get('m')} - Bilanzverdacht")

    if g.get("altman_kein_distress") and not _finanz:
        a = k.forensik.get("altman") or {}
        if a.get("gefahr") is True:
            raus.append(f"Altman Z {a.get('z')} - Insolvenzgefahr")

    verboten = g.get("kurs_urteil_verboten") or ()
    if k.kurs_urteil in verboten:
        raus.append("Kurs verlangt mehr als das realistisch Lieferbare")

    if g.get("multiple_anteil_max") is not None and k.multiple_anteil is not None:
        if k.multiple_anteil > g["multiple_anteil_max"]:
            raus.append(f"Fair Value zu {k.multiple_anteil:.0%} aus "
                        f"Multiple-Annahmen")

    if g.get("rsi_max") is not None:
        rsi = k.momentum.get("rsi")
        if rsi is not None and rsi > g["rsi_max"]:
            raus.append(f"RSI {rsi:.0f} - ueberhitzt")

    if g.get("operativer_cashflow_positiv"):
        ocf = k.fund.get("operating_cashflow")
        if ocf is not None and ocf <= 0:
            raus.append("operativer Cashflow negativ")

    return raus
