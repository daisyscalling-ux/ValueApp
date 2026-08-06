"""
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
def quantum_score(composite, valu, analyst=None, momentum=None, radar=None) -> dict:
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

    return {"score": round(max(0.0, min(100.0, score)), 1),
            "parts": parts, "n": len(comps)}
