"""
relval.py - Relative Bewertung.

"Micron ist billig" sagt wenig. "Micron ist billiger als 80 % der letzten zehn
Jahre UND guenstiger als der Halbleiter-Sektor" ist eine Aussage. Dieses Modul
liefert genau diese beiden Einordnungen:

  1. Historisches Band: Wo steht die AKTUELLE Bewertung im Vergleich zur eigenen
     Vergangenheit? (Perzentil, grob aus verfuegbaren Datenpunkten geschaetzt.)
  2. Peer/Sektor-Vergleich: Ist der Titel teuer oder guenstig gegenueber typischen
     Sektor-Multiples?

Ehrliche Grenzen: Mit Gratis-Daten haben wir nur wenige historische Stuetzpunkte
(FMP liefert ~8 Jahres-Ratios) und Sektor-Durchschnitte statt echter Peer-Listen.
Das ist Orientierung, kein Present-Value-Beweis - und wird als solche gekennzeichnet.
"""
from __future__ import annotations

__version__ = "2026.09.25"   # gemessenes Perzentil aus Multiple-Historie

import math
from typing import Dict, Optional, Sequence

import config


def _pctile_from_median(current, median, spread=0.35):
    """Grobe Perzentil-Schaetzung ohne volle Zeitreihe: Wo liegt 'current' relativ
    zum historischen Median? Nimmt eine typische Streuung an (Standard 35 %).
    Rueckgabe 0-100 (niedrig = guenstig gegenueber der eigenen Historie)."""
    if not current or not median or median <= 0:
        return None
    ratio = current / median
    # ratio 1.0 -> ~50. Innerhalb +/- spread linear auf 15..85 abbilden, dann kappen.
    pct = 50 + (ratio - 1) / spread * 35
    return max(2, min(98, round(pct)))


def historical_band(f, pe_hist_werte=None):
    """Wo steht das aktuelle KGV/EV-EBITDA im Vergleich zur eigenen Historie?

    Liegen die JAHRESWERTE vor (roic.pe_history()['werte'] oder
    f['hist_pe_werte']), wird das Perzentil direkt aus der Verteilung berechnet.
    Nur wenn ausschliesslich der Median bekannt ist, greift die alte Schaetzung
    mit angenommener Streuung - dann wird das im Feld 'pctile_quelle' vermerkt,
    damit eine geschaetzte Zahl nicht wie eine gemessene aussieht.
    """
    price = f.get("price")
    eps = f.get("eps_trailing") or f.get("eps_forward")
    pe_now = None
    if price and eps and eps > 0:
        pe_now = price / eps
    pe_hist = f.get("hist_pe_median")
    werte = pe_hist_werte or f.get("hist_pe_werte") or f.get("hist_pe_values")

    out = {"pe_now": round(pe_now, 1) if pe_now else None,
           "pe_hist_median": round(pe_hist, 1) if pe_hist else None,
           "pe_pctile": None, "pctile_quelle": None, "text": None, "verdict": None}

    if pe_now and werte:
        p = perzentil(werte, pe_now, hoch_ist_teuer=True)
        if p:
            out["pe_pctile"] = round(p["teuer_pct"])
            out["pctile_quelle"] = f"gemessen ({p['n']} Jahre)"
            out["pe_hist_median"] = p["median"]
            pe_hist = p["median"]

    if pe_now and pe_hist and out["pe_pctile"] is None:
        out["pe_pctile"] = _pctile_from_median(pe_now, pe_hist)
        out["pctile_quelle"] = "geschaetzt (nur Median bekannt)"

    if pe_now and pe_hist and out["pe_pctile"] is not None:
        pct = out["pe_pctile"]
        if pct is not None:
            if pct <= 30:
                out["verdict"] = "guenstig"
                out["text"] = (f"KGV {pe_now:.1f} liegt unter dem eigenen Schnitt "
                               f"({pe_hist:.1f}) - guenstiger als ~{100 - pct} % der "
                               "Historie.")
            elif pct >= 70:
                out["verdict"] = "teuer"
                out["text"] = (f"KGV {pe_now:.1f} liegt ueber dem eigenen Schnitt "
                               f"({pe_hist:.1f}) - teurer als ~{pct} % der Historie.")
            else:
                out["verdict"] = "neutral"
                out["text"] = (f"KGV {pe_now:.1f} nahe am eigenen Schnitt "
                               f"({pe_hist:.1f}) - durchschnittlich bewertet.")
    return out


def peer_compare(f):
    """Vergleich gegen typische Sektor-Multiples (KGV + EV/EBITDA).
    Kein echter Einzel-Peer-Vergleich (dafuer braeuchte es eine Peer-Liste aus
    Premium-Daten), sondern gegen Sektor-Referenzwerte - klar so benannt."""
    sector = f.get("sector") or "_default"
    ref_pe = config.SECTOR_PE.get(sector, config.SECTOR_PE["_default"])
    ref_ev = config.SECTOR_EV_EBITDA.get(sector, config.SECTOR_EV_EBITDA["_default"])

    price = f.get("price")
    eps = f.get("eps_trailing") or f.get("eps_forward")
    pe_now = (price / eps) if (price and eps and eps > 0) else None
    ev_now = f.get("ev_ebitda")

    signals = []
    pe_disc = ev_disc = None
    if pe_now:
        pe_disc = (pe_now / ref_pe - 1) * 100
        signals.append(("KGV", pe_now, ref_pe, pe_disc))
    if ev_now and ev_now > 0:
        ev_disc = (ev_now / ref_ev - 1) * 100
        signals.append(("EV/EBITDA", ev_now, ref_ev, ev_disc))

    discs = [d for _, _, _, d in signals]
    avg = sum(discs) / len(discs) if discs else None
    verdict = None
    if avg is not None:
        verdict = ("guenstig" if avg <= -15 else
                   "teuer" if avg >= 15 else "fair")
    return {"sector": sector, "signals": signals, "avg_disc": avg,
            "verdict": verdict}


def summarize(f):
    """Kompakte Gesamtaussage zur relativen Bewertung fuer die Anzeige."""
    hist = historical_band(f)
    peer = peer_compare(f)
    bits = []
    if hist.get("verdict"):
        bits.append(f"historisch {hist['verdict']}")
    if peer.get("verdict"):
        bits.append(f"vs. Sektor {peer['verdict']}")
    headline = " \u00b7 ".join(bits) if bits else "keine Vergleichsdaten"
    return {"hist": hist, "peer": peer, "headline": headline}

# ==========================================================================
# ECHTES BEWERTUNGS-PERZENTIL (loest die Schaetzung oben ab)
# ==========================================================================

URTEIL_BAENDER = [(30.0, "Attraktiv", "gruen"),
                  (70.0, "Neutral", "gelb"),
                  (101.0, "Unattraktiv", "rot")]

MIN_PUNKTE = 4          # unter vier Jahreswerten ist ein Perzentil Zahlenkosmetik


# ---------------------------------------------------------------------------
# Statistik
# ---------------------------------------------------------------------------

def _quantil(sortiert: Sequence[float], q: float) -> float:
    if not sortiert:
        return float("nan")
    if len(sortiert) == 1:
        return sortiert[0]
    pos = q * (len(sortiert) - 1)
    lo = int(math.floor(pos))
    hi = min(lo + 1, len(sortiert) - 1)
    return sortiert[lo] + (sortiert[hi] - sortiert[lo]) * (pos - lo)


def perzentil(werte: Sequence[float], aktuell: Optional[float],
              hoch_ist_teuer: bool = True) -> Optional[dict]:
    """Echtes Perzentil aus der Verteilung.

    Rueckgabe teuer_pct: 0 = so guenstig wie nie, 100 = so teuer wie nie.
    Zwischen den Stuetzpunkten wird linear interpoliert, damit ein einzelner
    Jahreswert nicht zu Spruengen von 100/n Punkten fuehrt.
    """
    xs = sorted(float(v) for v in (werte or [])
                if v is not None and math.isfinite(float(v)) and float(v) > 0)
    if len(xs) < MIN_PUNKTE or not aktuell or aktuell <= 0:
        return None

    aktuell = float(aktuell)
    if aktuell <= xs[0]:
        roh = 0.0
    elif aktuell >= xs[-1]:
        roh = 100.0
    else:
        i = 0
        while i < len(xs) - 1 and xs[i + 1] < aktuell:
            i += 1
        spanne = xs[i + 1] - xs[i]
        anteil = (aktuell - xs[i]) / spanne if spanne else 0.0
        roh = (i + anteil) / (len(xs) - 1) * 100.0

    teuer = roh if hoch_ist_teuer else 100.0 - roh
    med = _quantil(xs, 0.5)

    return {
        "aktuell": round(aktuell, 2),
        "teuer_pct": round(teuer, 1),
        "median": round(med, 2),
        "p25": round(_quantil(xs, 0.25), 2),
        "p75": round(_quantil(xs, 0.75), 2),
        "min": round(xs[0], 2),
        "max": round(xs[-1], 2),
        "n": len(xs),
        "vs_median_pct": round((aktuell / med - 1) * 100, 1) if med else None,
        "hoch_ist_teuer": hoch_ist_teuer,
    }


# ---------------------------------------------------------------------------
# KGV-Historie
# ---------------------------------------------------------------------------

def kgv_historie(fund, pe_hist: Optional[dict] = None) -> Optional[dict]:
    """Perzentil des aktuellen KGV in der eigenen Historie.

    pe_hist: Rueckgabe von roic.pe_history(ticker, jahre=10), also
             {"median":.., "werte":[...], "jahre":[...], "n":..}.
             Fehlt sie, wird auf fund['hist_pe_werte'] bzw. den Median
             zurueckgegriffen.
    """
    price = fund.get("price")
    eps = fund.get("eps_trailing") or fund.get("eps_forward")
    if not price or not eps or eps <= 0:
        return None
    kgv_jetzt = price / eps

    werte = None
    jahre = None
    if pe_hist and pe_hist.get("werte"):
        werte, jahre = pe_hist["werte"], pe_hist.get("jahre")
    elif fund.get("hist_pe_werte"):
        werte = fund["hist_pe_werte"]

    if not werte:
        # Kein Rueckfall auf eine geschaetzte Streuung: lieber keine Zahl als
        # eine erfundene. Der Median bleibt als Rueckkehrwert nutzbar.
        med = fund.get("hist_pe_median")
        if not med:
            return None
        return {"kgv_jetzt": round(kgv_jetzt, 1), "perzentil": None,
                "median": round(med, 1), "jahre": None,
                "rueckkehrwert": round(min(med, 60.0) * eps, 2),
                "hinweis": "Nur der historische Median liegt vor - kein Perzentil."}

    p = perzentil(werte, kgv_jetzt, hoch_ist_teuer=True)
    if not p:
        return None

    return {"kgv_jetzt": round(kgv_jetzt, 1), "perzentil": p,
            "median": p["median"], "jahre": jahre, "werte": list(werte),
            "rueckkehrwert": round(min(p["median"], 60.0) * eps, 2),
            "hinweis": None}


def ev_ebitda_historie(fund, multiples_hist: Optional[Sequence[float]] = None) -> Optional[dict]:
    """Analog fuer EV/EBITDA. Die Jahresreihe kommt aus roic (bundle liefert
    hist_ev_ebitda_werte) oder wird uebergeben."""
    jetzt = fund.get("ev_ebitda")
    multiples_hist = multiples_hist or fund.get("hist_ev_ebitda_werte")
    if not jetzt or jetzt <= 0 or not multiples_hist:
        return None
    p = perzentil(multiples_hist, jetzt, hoch_ist_teuer=True)
    if not p:
        return None
    ebitda, shares = fund.get("ebitda"), fund.get("shares_out")
    rueck = None
    if ebitda and shares and ebitda > 0:
        eq = p["median"] * ebitda - (fund.get("net_debt") or 0.0)
        rueck = round(eq / shares, 2) if eq > 0 else None
    return {"jetzt": round(jetzt, 1), "perzentil": p, "rueckkehrwert": rueck}


# ---------------------------------------------------------------------------
# Gesamturteil
# ---------------------------------------------------------------------------

def urteil(bloecke: Sequence[Optional[dict]]) -> dict:
    """Gesamturteil ueber alle vorhandenen Perzentile."""
    pcts = []
    for b in bloecke:
        if b and b.get("perzentil") and b["perzentil"].get("teuer_pct") is not None:
            pcts.append(b["perzentil"]["teuer_pct"])
    if not pcts:
        return {"label": "Keine Historie", "ton": "grau", "teuer_pct": None,
                "text": "Zu wenige historische Bewertungspunkte fuer eine Einordnung."}

    schnitt = sum(pcts) / len(pcts)
    label, ton = "Unattraktiv", "rot"
    for grenze, lab, t in URTEIL_BAENDER:
        if schnitt < grenze:
            label, ton = lab, t
            break

    if schnitt >= 70:
        text = (f"Der Titel notiert teurer als in {schnitt:.0f} % seiner eigenen "
                f"Historie. Eine Rueckkehr zum Median-Multiple waere allein schon "
                f"ein Gegenwind.")
    elif schnitt <= 30:
        text = (f"Der Titel notiert guenstiger als in {100 - schnitt:.0f} % seiner "
                f"eigenen Historie. Zu pruefen ist, ob sich die Qualitaet strukturell "
                f"verschlechtert hat - guenstig ist nicht automatisch billig.")
    else:
        text = (f"Die Bewertung liegt im mittleren Bereich der eigenen Historie "
                f"({schnitt:.0f}. Perzentil).")

    return {"label": label, "ton": ton, "teuer_pct": round(schnitt, 1), "text": text}


def multiple_band(pe_hist: Optional[dict]) -> Optional[Dict[str, float]]:
    """Quartile der eigenen KGV-Historie als Band fuer die Szenarien.

    Damit wird das Bewertungsniveau im Bear/Bull-Fall aus der eigenen
    Vergangenheit abgeleitet statt pauschal gesetzt.
    """
    if not pe_hist or not pe_hist.get("werte"):
        return None
    xs = sorted(float(v) for v in pe_hist["werte"] if v and v > 0)
    if len(xs) < MIN_PUNKTE:
        return None
    return {"tief": round(_quantil(xs, 0.25), 1),
            "basis": round(_quantil(xs, 0.50), 1),
            "hoch": round(_quantil(xs, 0.75), 1),
            "n": len(xs)}


def bericht(fund, pe_hist: Optional[dict] = None,
            ev_hist: Optional[Sequence[float]] = None) -> dict:
    """Komplettpaket fuer die Anzeige.

    Reihen kommen bevorzugt aus dem fund-Dict (roic liefert sie in bundle()),
    koennen aber uebergeben werden.
    """
    if pe_hist is None and fund.get("hist_pe_werte"):
        pe_hist = {"werte": fund["hist_pe_werte"],
                   "jahre": fund.get("hist_pe_jahre"),
                   "median": fund.get("hist_pe_median")}
    kgv = kgv_historie(fund, pe_hist)
    ev = ev_ebitda_historie(fund, ev_hist)
    return {"kgv": kgv, "ev_ebitda": ev,
            "urteil": urteil([kgv, ev]),
            "band": multiple_band(pe_hist)}
