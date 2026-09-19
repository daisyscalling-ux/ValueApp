"""
__version__ = "2026.10.01"
scoring.py — Scoring-Matrix.

Wandelt Rohkennzahlen in branchenrelative Perzentil-Scores (0-100), mittelt
pro Kategorie, gewichtet zum Composite. Value-Trap-Strafe inklusive.

Branchenrelativ: Scores werden gegen das übergebene Peer-Universum gerankt.
Bei nur einem Titel wird ein absoluter Fallback-Score verwendet.
"""
from __future__ import annotations
from typing import Any
import config

# Kennzahl -> (Kategorie, höher_ist_besser)
METRIC_MAP = {
    # valuation (kleiner ist besser -> invertiert)
    "ev_ebitda":      ("valuation", False),
    "pb":             ("valuation", False),
    "pe_forward":     ("valuation", False),
    "peg":            ("valuation", False),
    "fcf_yield":      ("valuation", True),
    # quality
    "roe":            ("quality", True),
    "roa":            ("quality", True),
    "gross_margin":   ("quality", True),
    "operating_margin": ("quality", True),
    # growth
    "revenue_growth": ("growth", True),
    "earnings_growth": ("growth", True),
    # health (net_debt_ebitda kleiner besser)
    "current_ratio":  ("health", True),
    "net_debt_ebitda": ("health", False),
}


# Kennzahlen, bei denen ein negativer Wert pathologisch ist (Verluste, negativer
# Buchwert, negatives EBITDA): NICHT invertiert-bestnoten, sondern schlechteste Note.
_PATHOLOGICAL_IF_NEGATIVE = {"pe_forward", "peg", "ev_ebitda", "pb"}


def _percentile_rank(value, peers_values, higher_is_better) -> float:
    """0-100 Perzentil von value innerhalb peers_values."""
    vals = [v for v in peers_values if v is not None]
    if value is None or not vals:
        return 50.0  # neutral, wenn keine Vergleichsbasis
    below = sum(1 for v in vals if v < value)
    equal = sum(1 for v in vals if v == value)
    pct = (below + 0.5 * equal) / len(vals) * 100
    return pct if higher_is_better else (100 - pct)


def _absolute_fallback(metric, value, higher_is_better) -> float:
    """Wenn keine Peers da sind: grobe absolute Heuristik auf 0-100."""
    if value is None:
        return 50.0
    # einfache, robuste Skala je Kennzahlentyp
    scales = {
        "ev_ebitda": (5, 25), "pb": (0.5, 6), "pe_forward": (8, 40),
        "peg": (0.5, 3), "fcf_yield": (0.0, 0.12),
        "roe": (0.0, 0.30), "roa": (0.0, 0.15),
        "gross_margin": (0.1, 0.7), "operating_margin": (0.0, 0.35),
        "revenue_growth": (-0.1, 0.4), "earnings_growth": (-0.1, 0.5),
        "current_ratio": (0.5, 3.0), "net_debt_ebitda": (0.0, 5.0),
    }
    lo, hi = scales.get(metric, (0, 1))
    x = max(lo, min(hi, value))
    pct = (x - lo) / (hi - lo) * 100
    return pct if higher_is_better else (100 - pct)


def score_stock(fund: dict[str, Any], peer_funds: list[dict] | None,
                preset: str = "quality") -> dict[str, Any]:
    """
    Gibt {category_scores, composite, value_trap, breakdown} zurück.
    peer_funds: Liste von Fundamental-Dicts der Branche (für relatives Ranking).
    """
    weights = config.SCORE_PRESETS.get(preset, config.SCORE_PRESETS["quality"])
    cat_values: dict[str, list[float]] = {k: [] for k in weights}
    breakdown: dict[str, float] = {}

    for metric, (cat, hib) in METRIC_MAP.items():
        val = fund.get(metric)
        if metric in _PATHOLOGICAL_IF_NEGATIVE and val is not None and val <= 0:
            s = 0.0                    # negatives KGV/PEG/EV-EBITDA/KBV = Verlust/negatives
        elif peer_funds:               # Eigenkapital -> schlechteste, nicht beste Note
            peer_vals = [p.get(metric) for p in peer_funds]
            s = _percentile_rank(val, peer_vals, hib)
        else:
            s = _absolute_fallback(metric, val, hib)
        breakdown[metric] = round(s, 1)
        cat_values[cat].append(s)

    # Kategorie-Scores (Mittel); 'momentum' & 'catalyst' separat (s.u.)
    cat_scores = {}
    cat_neutral = {}       # welche Kategorie fiel mangels Daten auf 50 zurueck?
    for cat in weights:
        vals = cat_values.get(cat, [])
        cat_scores[cat] = sum(vals) / len(vals) if vals else 50.0
        cat_neutral[cat] = (not vals)     # True = kein echter Wert, nur Neutral

    # Momentum: relativer Abstand zu 52W-Hoch/-Tief als grobe Proxy
    price = fund.get("price")
    hi, lo = fund.get("52w_high"), fund.get("52w_low")
    if price and hi and lo and hi > lo:
        pos = (price - lo) / (hi - lo) * 100
        # Deckel 0..100: bei fehlerhaften Kursen (z.B. OTC-Titel wie SSNLF, wo
        # der aktuelle Kurs ueber dem 52W-Hoch liegt) wuerde pos sonst weit
        # ueber 100 schiessen (404 gesehen) und den Composite faelschlich
        # hochziehen. Der Deckel gilt generell fuer alle Titel.
        pos = max(0.0, min(100.0, pos))
        cat_scores["momentum"] = pos
        breakdown["price_position_52w"] = round(pos, 1)
    else:
        cat_scores["momentum"] = 50.0

    # Catalyst-Score: extern setzbar (Intel-Layer), default neutral
    cat_scores.setdefault("catalyst", float(fund.get("_catalyst_score", 50.0)))

    composite = sum(cat_scores[c] * w for c, w in weights.items())

    # Value-Trap-Filter
    vt = _value_trap(fund)
    if vt:
        composite -= config.VALUE_TRAP_PENALTY
    composite = max(0.0, min(100.0, composite))   # Score bleibt in [0, 100]

    return {
        "ticker": fund.get("ticker"),
        "name": fund.get("name"),
        "sector": fund.get("sector"),
        "category_scores": {k: round(v, 1) for k, v in cat_scores.items()},
        "cat_neutral": cat_neutral,     # welche Kategorien sind nur Neutral (50)?
        "composite": round(composite, 1),
        "value_trap": vt,
        "breakdown": breakdown,
    }


#: Sprechende Namen und Einheiten je Kennzahl - fuer die Score-Erklaerung.
_METRIC_LABEL = {
    "ev_ebitda":       ("EV/EBITDA", "x", False),
    "pb":              ("Kurs-Buchwert", "x", False),
    "pe_forward":      ("erwartetes KGV", "x", False),
    "peg":             ("PEG", "", False),
    "fcf_yield":       ("Free-Cashflow-Rendite", "%", True),
    "roe":             ("Eigenkapitalrendite", "%", True),
    "roa":             ("Gesamtkapitalrendite", "%", True),
    "gross_margin":    ("Bruttomarge", "%", True),
    "operating_margin":("operative Marge", "%", True),
    "revenue_growth":  ("Umsatzwachstum", "%", True),
    "earnings_growth": ("Gewinnwachstum", "%", True),
    "current_ratio":   ("Liquiditaet 3. Grades", "x", True),
    "net_debt_ebitda": ("Nettoverschuldung/EBITDA", "x", False),
    "price_position_52w": ("Kursposition im 52-Wochen-Band", "%", True),
}

_KAT_BESCHREIBUNG = {
    "valuation": "Wie teuer ist die Aktie gemessen an Gewinn, Cashflow und Substanz?",
    "quality":   "Wie profitabel wirtschaftet die Firma mit ihrem Kapital?",
    "growth":    "Wie stark wachsen Umsatz und Gewinn?",
    "health":    "Wie solide ist die Bilanz - Schulden gegen Liquiditaet?",
    "momentum":  "Wo steht der Kurs zwischen 52-Wochen-Tief und -Hoch?",
    "catalyst":  "Gibt es Ausloeser (News, Termine), die Bewegung bringen koennten?",
}


def score_erklaerung(scores: dict, fund: dict) -> dict:
    """Warum ist jeder Kategorie-Score so, wie er ist?

    Nutzt breakdown (die Einzelnoten je Kennzahl) und die Rohwerte aus fund.
    Fuer jede Kategorie: die Kennzahlen, die sie am staerksten nach oben oder
    unten ziehen - mit dem tatsaechlichen Wert, nicht nur der Note.

    Rueckgabe je Kategorie: {frage, treiber:[...], hinweis}
    """
    breakdown = scores.get("breakdown") or {}
    cat_neutral = scores.get("cat_neutral") or {}
    # Kennzahl -> Kategorie
    kat_von = {m: cat for m, (cat, _hib) in METRIC_MAP.items()}
    kat_von["price_position_52w"] = "momentum"

    # Kennzahlen je Kategorie sammeln, mit Note und Rohwert
    je_kat: dict[str, list] = {}
    for metric, note in breakdown.items():
        cat = kat_von.get(metric)
        if not cat:
            continue
        label, einheit, hib = _METRIC_LABEL.get(metric, (metric, "", True))
        roh = fund.get(metric)
        je_kat.setdefault(cat, []).append(
            {"label": label, "note": note, "roh": roh, "einheit": einheit})

    out = {}
    for cat, frage in _KAT_BESCHREIBUNG.items():
        eintraege = je_kat.get(cat, [])
        if cat_neutral.get(cat) or (not eintraege and cat not in ("momentum", "catalyst")):
            out[cat] = {"frage": frage, "treiber": [],
                        "hinweis": "Keine belastbaren Daten - Wert auf neutral (50) gesetzt."}
            continue
        # nach Note sortieren: staerkste Treiber oben und unten
        eintraege.sort(key=lambda e: e["note"], reverse=True)
        treiber = []
        for e in eintraege:
            roh = e["roh"]
            if roh is None:
                wert = "n/a"
            elif e["einheit"] == "%":
                wert = f"{roh * 100:.1f} %" if abs(roh) < 3 else f"{roh:.1f} %"
            elif e["einheit"] == "x":
                wert = f"{roh:.1f}x"
            else:
                wert = f"{roh:.2f}"
            richtung = ("stark" if e["note"] >= 66 else
                        "schwach" if e["note"] <= 33 else "mittel")
            treiber.append({"label": e["label"], "wert": wert,
                            "note": e["note"], "richtung": richtung})
        out[cat] = {"frage": frage, "treiber": treiber, "hinweis": ""}
    return out


def _value_trap(fund: dict) -> bool:
    """Billig aus gutem Grund: fallender Umsatz UND fallende Marge UND viel Schulden."""
    rev_g = fund.get("revenue_growth")
    op_m = fund.get("operating_margin")
    nde = fund.get("net_debt_ebitda")
    shrinking = rev_g is not None and rev_g < 0
    weak_margin = op_m is not None and op_m < 0.05
    levered = nde is not None and nde > 4
    return bool(shrinking and weak_margin and levered)


# ---------------------------------------------------------------------------
# QUANTUM SCORE — Meta-Score ueber vier Dimensionen ("Quanten")
# ---------------------------------------------------------------------------
def analyst_trend_update(hist: dict, ticker: str, target_mean, eps_forward,
                         count, now_ts=None, max_punkte=12):
    """Schreibt die Analysten-Schaetzungen eines Titels fort und gibt den Trend
    zurueck. hist wird in-place ergaenzt (der Aufrufer speichert es via
    store.set_analyst_hist). Nur ~alle 3 Tage ein neuer Punkt, damit sich ueber
    Wochen ein echter Verlauf bildet statt vieler fast-gleicher Werte.

    Rueckgabe: dict mit
      richtung   : "steigend" | "fallend" | "stabil" | None (zu wenig Daten)
      target_delta_pct : Veraenderung des Kursziels seit dem aeltesten Punkt (%)
      punkte     : Anzahl gespeicherter Messpunkte
    So laesst sich erkennen, ob die Analysten ihre Ziele SENKEN - das staerkste
    Value-Trap-Signal."""
    import time as _t
    now_ts = now_ts or _t.time()
    if target_mean is None or target_mean <= 0:
        return {"richtung": None, "target_delta_pct": None, "punkte": 0}
    reihe = hist.get(ticker) or []
    # neuen Punkt nur, wenn der letzte >= ~2,5 Tage her ist (oder noch keiner
    # da). Etwas unter 3 Tagen, damit ein Lauf am 3-Tage-Raster nicht knapp
    # verpasst wird und trotzdem ~2 Punkte pro Woche entstehen.
    if not reihe or (now_ts - reihe[-1].get("ts", 0)) >= 2.5 * 86400:
        reihe.append({"ts": round(now_ts), "target_mean": round(float(target_mean), 2),
                      "eps_forward": (round(float(eps_forward), 3)
                                      if eps_forward is not None else None),
                      "count": count})
        reihe = reihe[-max_punkte:]      # nur die letzten N behalten
        hist[ticker] = reihe
    if len(reihe) < 2:
        return {"richtung": None, "target_delta_pct": None, "punkte": len(reihe)}
    alt = reihe[0]["target_mean"]
    neu = reihe[-1]["target_mean"]
    if not alt or alt <= 0:
        return {"richtung": None, "target_delta_pct": None, "punkte": len(reihe)}
    delta = (neu / alt - 1) * 100
    if delta <= -5:
        richtung = "fallend"
    elif delta >= 5:
        richtung = "steigend"
    else:
        richtung = "stabil"
    return {"richtung": richtung, "target_delta_pct": round(delta, 1),
            "punkte": len(reihe)}


def quantum_score(composite, valu, analyst=None, momentum=None, radar=None,
                  analyst_skepsis=None, analyst_trend=None) -> dict:
    """Buendelt alle Sichten des Tools in EINEN erklaerbaren Score (0-100):

      Q-Qualitaet  (30%): Composite (fundamentale Qualitaet + rel. Bewertung)
      Q-Bewertung  (40%): Fair-Value-Upside inkl. Analysten-Anker; je geringer
                          die Konfidenz des Fair Value, desto staerker zieht
                          die Komponente Richtung neutral (50)
      Q-Analysten  (15%): Konviktion aus Buy/Hold/Sell-Verteilung
      Q-Momentum   (15%): Radar-Score, falls gescannt; sonst 52W-Positionsscore

    Zusaetzlich: ein Ueberbewertungs-Malus zieht den Score gezielt nach unten,
    wenn ein Titel deutlich UEBER seinem Fair Value notiert (typisch bei
    teuren Qualitaetstiteln wie NVIDIA/Google, die sonst allein durch
    Qualitaet + Momentum + Analysten hoch scoren, obwohl sie teuer sind).

    Fehlende Dimensionen werden nicht neutral gefuellt, sondern die Gewichte
    werden auf die vorhandenen renormalisiert (kein kuenstlicher 50er-Ballast).
    """
    comps, wts, parts = [], [], {}

    if composite is not None:
        comps.append(float(composite)); wts.append(0.30)
        parts["Qualit\u00e4t"] = round(float(composite))

    up = (valu or {}).get("upside_pct")
    if up is not None:
        conf = (valu or {}).get("confidence")
        pull = {"hoch": 1.0, "mittel": 0.75, "niedrig": 0.45}.get(conf, 0.6)
        q_val = 50.0 + max(min(up, 40.0), -40.0) * 0.8 * pull
        comps.append(q_val); wts.append(0.40)
        parts["Bewertung"] = round(q_val)

    a = analyst or {}
    b, h, se = a.get("buy") or 0, a.get("hold") or 0, a.get("sell") or 0
    tot = b + h + se
    if tot >= 3:                                   # erst ab 3 Ratings aussagekraeftig
        net = (b - se) / tot
        q_anl = 50.0 + net * 45.0
        comps.append(q_anl); wts.append(0.15)
        parts["Analysten"] = round(q_anl)

    q_mom = radar if radar is not None else momentum
    if q_mom is not None:
        # Generell 0..100 deckeln - schuetzt gegen fehlerhafte Roh-Scores
        # (z.B. ein Momentum-Wert von 404 durch verzerrte OTC-Kurse), die den
        # Quantum/Composite sonst faelschlich nach oben ziehen.
        q_mom = max(0.0, min(100.0, float(q_mom)))
        comps.append(q_mom); wts.append(0.15)
        parts["Momentum" + ("/Radar" if radar is not None else "")] = round(q_mom)

    if not comps:
        return {"score": None, "parts": {}, "n": 0}
    wsum = sum(wts)
    score = sum(c * w for c, w in zip(comps, wts)) / wsum

    # UEBERBEWERTUNGS-MALUS: Ein Titel, der deutlich UEBER seinem Fair Value
    # notiert (negativer Upside), wird gezielt gedaempft - zusaetzlich zur
    # ohnehin schwachen Bewertungskomponente. Das trifft teure Qualitaetstitel
    # (NVIDIA/Google), die sonst allein durch Qualitaet + Momentum + Analysten
    # hoch scoren. Ein fair oder guenstig bewerteter Titel bleibt unberuehrt.
    #   Upside  -10 %  -> -2 Punkte
    #   Upside  -20 %  -> -5 Punkte
    #   Upside  -30 %  -> -8 Punkte
    #   Upside <=-40 % -> -11 Punkte (Deckel)
    up = (valu or {}).get("upside_pct")
    malus = 0.0
    if up is not None and up < -5:
        # linear ab -5 %, ca. 0,3 Punkte je Prozentpunkt Ueberbewertung
        malus = min((abs(up) - 5) * 0.3, 11.0)
        score -= malus
        if malus >= 1:
            parts["\u00dcberbewertungs-Malus"] = -round(malus)

    # VALUE-TRAP-MALUS (mild): "zu guenstig" ist oft eine Falle, kein Geschenk.
    # Drei Signale, die zusammen das Risiko eines Value Traps anzeigen:
    #   1) Extrem hoher Upside (>80 %): meist ein Datenfehler oder eine Falle,
    #      keine echte Gelegenheit (z.B. HSBC mit 134 % - der Fair Value ist
    #      wahrscheinlich falsch, nicht die Aktie 134 % zu billig).
    #   2) Fallendes Messer: hoher Upside UND schwaches Momentum (<40) - der
    #      Kurs faellt weiter, obwohl der Titel schon guenstig aussieht
    #      (Adobe/Accenture/Salesforce-Fall).
    #   3) Unsichere Bewertung: die Methoden streuen stark (spread_pct hoch) -
    #      ein hoher Upside auf wackliger Basis ist besonders riskant.
    # BEWUSST MILD: Der Titel bleibt im Screener (Ideenquelle), wird nur im
    # Score gedaempft und mit einer Warnung markiert. Keine Ausfilterung.
    vt_signale = []
    vt_malus = 0.0
    _spread = (valu or {}).get("spread_pct")
    if up is not None and up > 80:
        vt_malus += min((up - 80) * 0.15, 8.0)
        vt_signale.append(f"extrem hoher Upside ({up:.0f} %) - Fair Value pr\u00fcfen")
    if up is not None and up > 25 and momentum is not None and momentum < 40:
        vt_malus += 5.0
        vt_signale.append("g\u00fcnstig, aber fallender Kurs (m\u00f6gliches fallendes Messer)")
    if up is not None and up > 40 and _spread is not None and _spread > 60:
        vt_malus += 4.0
        vt_signale.append(
            f"hoher Upside auf unsicherer Bewertungsbasis: die einzelnen "
            f"Bewertungsmethoden (DCF, KGV, KBV \u2026) weichen um {_spread:.0f} % "
            f"voneinander ab \u2013 je gr\u00f6\u00dfer die Streuung, desto unsicherer der "
            f"Fair Value, weil viel Wert in unsicheren Zukunftsannahmen steckt")
    # NEU: Analysten-Skepsis - unser Fair Value verspricht viel Upside, aber die
    # Analysten trauen dem nicht (ihr Kursziel liegt deutlich darunter). Wenn die
    # Profis skeptischer sind als unsere Rechnung, ist Vorsicht geboten.
    if analyst_skepsis is not None and up is not None and up > 25:
        # analyst_skepsis = (analyst_target/fair_value - 1)*100, also negativ,
        # wenn die Analysten unter unserem Fair Value liegen
        if analyst_skepsis < -20:
            vt_malus += 4.0
            vt_signale.append("Analysten deutlich vorsichtiger als unser Fair Value")
    # NEU: fallende Analysten-Schaetzungen ueber die Zeit - das staerkste
    # Value-Trap-Signal. "Billig" ist eine Illusion, wenn die erwarteten Gewinne
    # gerade nach unten revidiert werden.
    if analyst_trend and analyst_trend.get("richtung") == "fallend":
        _d = analyst_trend.get("target_delta_pct")
        vt_malus += 6.0
        _txt = "Analysten SENKEN ihre Kursziele"
        if _d is not None:
            _txt += f" ({_d:.0f} % seit Beobachtungsbeginn)"
        vt_signale.append(_txt)
    if vt_malus > 0:
        vt_malus = min(vt_malus, 12.0)     # Deckel: mild bleiben
        score -= vt_malus
        parts["Value-Trap-Malus"] = -round(vt_malus)

    return {"score": round(max(0.0, min(100.0, score)), 1),
            "parts": parts, "n": len(comps),
            "value_trap_warnung": vt_signale}
