"""
portfolio.py — Portfolio-Check.

Reine Analyse-Logik (ohne Streamlit). Bekommt je Position bereits die aus unseren
Modulen berechneten Kennzahlen (Composite, Fair-Value-Upside, optional Radar) und
errechnet:
  - Gewichte, Klumpenrisiken (Einzelposition, Sektor, Land), effektive Positionszahl
  - Ueberschneidungen (doppelte Firmen / Cross-Listings)
  - gewichtete Portfolio-Scores + einen Gesamtscore 0-100
  - Flags und Diversifikations-Luecken
"""
from __future__ import annotations

STANDARD_SECTORS = [
    "Technology", "Communication Services", "Consumer Cyclical", "Consumer Defensive",
    "Healthcare", "Financial Services", "Industrials", "Energy", "Basic Materials",
    "Utilities", "Real Estate",
]


def _alloc(rows, key):
    d = {}
    for r in rows:
        k = r.get(key) or "Unbekannt"
        d[k] = d.get(k, 0.0) + r["weight"]
    return dict(sorted(d.items(), key=lambda x: -x[1]))


def _wavg(rows, field):
    num = sum(r["weight"] * r[field] for r in rows if r.get(field) is not None)
    wt = sum(r["weight"] for r in rows if r.get(field) is not None)
    return (num / wt) if wt > 0 else None


def classify_total(score):
    if score >= 70:
        return "Robust", "buy"
    if score >= 55:
        return "Solide", "watch"
    if score >= 40:
        return "Ausbauf\u00e4hig", "watch"
    return "Schwach", "drop"


def _position_status(r):
    """Bewertet eine Position aus Rendite-seit-Kauf + Bewertung + Qualitaet.
    Rueckgabe: (label, farbe, hinweis). Nennt bei ueberbewerteten Gewinnern
    konkrete Kurse fuer (Teil-)Gewinnmitnahme (kein Rat - Orientierung)."""
    ret = r.get("ret_pct")
    up = r.get("upside")
    comp = r.get("composite")
    price = r.get("price_eur")
    fair = r.get("fair_value_eur")

    def _tp_note():
        if price and fair and fair > 0:
            if fair < price:            # bereits ueber fairem Wert
                return (f" \u00b7 bereits \u00fcber Fair Value (\u2248{_eur(fair)}): Teilverkauf "
                        "sichert die Pr\u00e4mie, Rest ggf. mit Stop sch\u00fctzen")
            half = price + (fair - price) * 0.5
            return (f" \u00b7 Teilgewinn \u2248{_eur(half)}, Gewinnmitnahme Richtung "
                    f"Fair Value \u2248{_eur(fair)}")
        if price:
            return (f" \u00b7 grobe Marken: Teilgewinn \u2248{_eur(price*1.08)}, "
                    f"Gewinnmitnahme \u2248{_eur(price*1.15)}")
        return ""

    if ret is None:
        return ("\u2014", "neutral", "")
    if ret >= 15 and up is not None and up < 0:
        return ("Gewinnmitnahme?", "gelb",
                "l\u00e4uft gut, ist jetzt aber \u00fcberbewertet \u2013 Teilverkauf erw\u00e4gen"
                + _tp_note())
    if ret >= 25 and (up is None or up < 5):
        return ("Teilgewinn sichern?", "gelb",
                "deutlicher Gewinn, kaum noch Bewertungsluft" + _tp_note())
    if ret > 0 and (up is None or up >= 0):
        note = ("Gewinn und noch Bewertungsluft \u2013 halten" if up is not None
                else "Gewinn; Bewertung unklar \u2013 halten")
        return ("Im Plus \u2013 halten", "gr\u00fcn", note)
    if ret <= -15 and (comp if comp is not None else 100) < 50 and (up or 0) < 0:
        return ("Verlust \u2013 schwach", "rot",
                "Verlust + schwache Kennzahlen \u2013 Ausstieg/Steuerverlust pr\u00fcfen")
    if ret < 0 and (up or 0) > 10 and (comp or 0) >= 55:
        return ("Verlust \u2013 Qualit\u00e4t ok", "gelb",
                "im Minus, aber g\u00fcnstig & solide \u2013 nachkaufen pr\u00fcfen")
    return ("Beobachten", "neutral", "")


def _eur(x):
    try:
        return f"{x:,.2f}\u20ac".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "\u2014"


def analyze(rows: list) -> dict:
    """rows: je Position dict mit ticker, name, value_eur, sector, country,
    composite, upside, price_eur, fair_value_eur, radar (optional), playbook,
    optional ret_pct/gain_eur/cost_eur (Gewinn/Verlust seit Kauf)."""
    total = sum(r["value_eur"] for r in rows) or 1.0
    for r in rows:
        r["weight"] = r["value_eur"] / total
        r["status"] = _position_status(r)

    weights = sorted((r["weight"] for r in rows), reverse=True)
    n = len(rows)
    max_pos = weights[0] if weights else 0.0
    top3 = sum(weights[:3])
    hhi = sum(w * w for w in weights)
    eff_positions = (1 / hhi) if hhi > 0 else 0.0

    sector_alloc = _alloc(rows, "sector")
    country_alloc = _alloc(rows, "country")
    max_sector_name, max_sector = (next(iter(sector_alloc.items())) if sector_alloc else ("", 0.0))

    # Ueberschneidungen: gleiche Firma (z.B. Cross-Listings) anhand Name
    namemap = {}
    for r in rows:
        nm = (r.get("name") or r.get("ticker") or "").strip().lower()
        namemap.setdefault(nm, []).append(r["ticker"])
    duplicates = [v for v in namemap.values() if len(v) > 1]

    w_comp = _wavg(rows, "composite")
    w_ups = _wavg(rows, "upside")
    w_radar = _wavg(rows, "radar")

    # Gewinn/Verlust seit Kauf (nur Positionen mit Kaufdatum)
    pl_rows = [r for r in rows if r.get("ret_pct") is not None]
    have_pl = len(pl_rows) > 0
    pl_cost = sum((r.get("cost_eur") or 0) for r in pl_rows)
    pl_value = sum(r["value_eur"] for r in pl_rows)
    pl_gain = pl_value - pl_cost
    pl_return = (pl_gain / pl_cost * 100) if pl_cost > 0 else None

    # Portfolio-Fair-Value (gewichtet ueber Upside je Position)
    pf_fair = sum(r["value_eur"] * (1 + (r.get("upside") or 0) / 100.0) for r in rows)
    pf_upside = (pf_fair / total - 1) * 100 if total else None

    # Gesamtscore
    score = w_comp if w_comp is not None else 50.0
    if w_ups is not None:
        score += max(min(w_ups * 0.2, 8), -10)         # Bewertungs-Tilt
    if have_pl:                                          # These-Bestaetigung / gebrochene Thesen
        working = sum(r["weight"] for r in rows if r["status"][0] == "Im Plus \u2013 halten")
        broken = sum(r["weight"] for r in rows if r["status"][0] == "Verlust \u2013 schwach")
        score += working * 4 - broken * 10
    if max_pos > 0.25:
        score -= (max_pos - 0.25) * 60                 # Einzelklumpen
    if max_sector > 0.40:
        score -= (max_sector - 0.40) * 50              # Sektorklumpen
    if n < 5:
        score -= (5 - n) * 3                           # zu wenige Positionen
    if duplicates:
        score -= 4 * len(duplicates)
    score = max(0.0, min(100.0, score))
    label, vkey = classify_total(score)

    # Flags
    flags = []
    if max_pos > 0.30:
        flags.append(("rot", f"Gr\u00f6\u00dfte Position {max_pos*100:.0f} % \u2013 starkes Klumpenrisiko."))
    elif max_pos > 0.20:
        flags.append(("gelb", f"Gr\u00f6\u00dfte Position {max_pos*100:.0f} % \u2013 leicht \u00fcbergewichtet."))
    if max_sector > 0.50:
        flags.append(("rot", f"Sektor {max_sector_name} {max_sector*100:.0f} % \u2013 Klumpenrisiko."))
    elif max_sector > 0.35:
        flags.append(("gelb", f"Sektor {max_sector_name} {max_sector*100:.0f} % \u2013 erh\u00f6ht."))
    if n < 5:
        flags.append(("gelb", f"Nur {n} Positionen \u2013 wenig diversifiziert."))
    if n > 25:
        flags.append(("gelb", f"{n} Positionen \u2013 evtl. \u00fcberdiversifiziert."))
    for d in duplicates:
        flags.append(("gelb", f"Doppelte Firma: {', '.join(d)} \u2013 Cross-Listing?"))
    if not flags:
        flags.append(("gr\u00fcn", "Keine groben Klumpen- oder \u00dcberschneidungsprobleme erkannt."))

    # Schwaechste Positionen (Reduzieren/Ersetzen pruefen)
    weak = []
    for r in rows:
        reasons = []
        if (r.get("composite") if r.get("composite") is not None else 100) < 45:
            reasons.append(f"Score {r['composite']:.0f}")
        if (r.get("upside") or 0) < -10:
            reasons.append(f"\u00fcberbewertet {r['upside']:.0f} %")
        if r["weight"] > 0.20:
            reasons.append(f"Gewicht {r['weight']*100:.0f} %")
        if reasons:
            weak.append({"ticker": r["ticker"], "name": r.get("name"),
                         "reasons": reasons, "weight": r["weight"]})
    weak.sort(key=lambda x: -x["weight"])

    held_sectors = {r.get("sector") for r in rows if r.get("sector")}
    gaps = [s for s in STANDARD_SECTORS if s not in held_sectors]

    # Handlungsempfehlungen aus dem Kauf-Status (Gewinne sichern / Ausstieg / Nachkaufen)
    actions = []
    for r in rows:
        lab, col, note = r["status"]
        if lab in ("Gewinnmitnahme?", "Teilgewinn sichern?", "Verlust \u2013 schwach",
                   "Verlust \u2013 Qualit\u00e4t ok"):
            actions.append({"ticker": r["ticker"], "name": r.get("name"),
                            "label": lab, "color": col, "note": note,
                            "ret_pct": r.get("ret_pct")})

    return {
        "n": n, "total_eur": total,
        "max_pos": max_pos, "top3": top3, "hhi": hhi, "eff_positions": eff_positions,
        "sector_alloc": sector_alloc, "country_alloc": country_alloc,
        "max_sector_name": max_sector_name, "max_sector": max_sector,
        "duplicates": duplicates,
        "w_composite": w_comp, "w_upside": w_ups, "w_radar": w_radar,
        "pf_fair_eur": pf_fair, "pf_upside": pf_upside,
        "have_pl": have_pl, "pl_cost": pl_cost, "pl_value": pl_value,
        "pl_gain": pl_gain, "pl_return": pl_return, "pl_count": len(pl_rows),
        "actions": actions,
        "score": round(score, 1), "label": label, "vkey": vkey,
        "flags": flags, "weak": weak, "gaps": gaps,
    }
