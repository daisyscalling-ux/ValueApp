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


def historical_band(f):
    """Wo steht das aktuelle KGV/EV-EBITDA im Vergleich zur eigenen Historie?
    Nutzt hist_pe_median (aus mehreren Jahren). Rueckgabe u.a. Perzentil + Klartext."""
    price = f.get("price")
    eps = f.get("eps_trailing") or f.get("eps_forward")
    pe_now = None
    if price and eps and eps > 0:
        pe_now = price / eps
    pe_hist = f.get("hist_pe_median")

    out = {"pe_now": round(pe_now, 1) if pe_now else None,
           "pe_hist_median": round(pe_hist, 1) if pe_hist else None,
           "pe_pctile": None, "text": None, "verdict": None}
    if pe_now and pe_hist:
        pct = _pctile_from_median(pe_now, pe_hist)
        out["pe_pctile"] = pct
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
