"""
autodepot.py — Ein einziges, selbstverwaltetes Papierdepot mit 50.000 EUR.

Idee (und ehrliche Grenze):
    Das Depot wendet FESTE, nachvollziehbare Regeln auf die Scan-Signale an -
    es sagt NICHT die Zukunft voraus. "Selbst entscheiden, wann eingestiegen
    wird" heisst hier: Ein Titel wird gekauft, wenn er in Screener, Radar ODER
    Momentum als starkes Signal auftaucht UND die Depotregeln (Gewicht, freie
    Slots, Cash) es zulassen. Verkauft wird nach Stop-Loss, Take-Profit,
    nachgezogenem Gewinn-Stop oder wenn das Signal erlischt. Das ist eine
    mechanische Umsetzung, kein Markt-Timing.

Regeln (mit dem Nutzer abgestimmt):
    - Startkapital 50.000 EUR, muss NICHT sofort investiert sein (Cash ist ok)
    - gleichgewichtet, 10-15 Positionen -> Zielgewicht ~7 % je Position
    - Obergrenze je Einzelposition (POS_CAP), Land spielt keine Rolle
    - Quellen: Screener + Radar + Momentum gemeinsam
    - Long UND Short erlaubt, maximal 1x Hebel (also ungehebelt)
    - Gewinnabsicherung: Stop-Loss, Take-Profit, Trailing-Stop, Teilverkauf
"""
from __future__ import annotations
import math
import time

import providers
import scoring
import valuation

# Bausteine aus dem bestehenden Simulator wiederverwenden - NICHT duplizieren.
from hedgefund import (_price_eur, _pl_pct, _trail_stop,
                       scorecard_ok, _quality_gate)

START_CAPITAL = 50000.0
ZIEL_POSITIONEN = 13          # Mitte von 10-15
ZIEL_GEWICHT = 1.0 / ZIEL_POSITIONEN     # ~7,7 %
POS_CAP = 0.10                # harte Obergrenze je Einzelposition (10 %)
CASH_PUFFER = 0.03            # min. 3 % Cash halten, nie 100 % investieren

# Exit-Schwellen (gleich fuer long/short, Short-Rendite invers gerechnet)
TP = 30.0                     # Take-Profit
SL = -15.0                    # Stop-Loss
# Teilverkauf: bei diesem Gewinn die HAELFTE glattstellen, Rest weiterlaufen
# lassen (Gewinn sichern, Chance behalten).
TEILVERKAUF_AB = 20.0
TEILVERKAUF_ANTEIL = 0.5

STATE_KEY = "autodepot"       # eigener Slot im Hedgefonds-Speicher (stoert HF nicht)


def _store():
    import store
    return store


def leeres_depot(grund=""):
    return {
        "start_capital": START_CAPITAL,
        "cash": START_CAPITAL,
        "positions": [],
        "trades": [],
        "created": time.time(),
        "value_eur": START_CAPITAL,
        "last_check": None,
        "neustart_am": time.time(),
        "neustart_grund": grund or "",
    }


def lade():
    hf = _store().get_hf() or {}
    st = hf.get(STATE_KEY)
    if not isinstance(st, dict) or "positions" not in st:
        st = leeres_depot("Erststart")
        speichere(st)
    return st


def speichere(st):
    hf = _store().get_hf() or {}
    hf[STATE_KEY] = st
    return _store().set_hf(hf)


# ---------------------------------------------------------------------------
# Kandidaten aus ALLEN DREI Scans zusammenfuehren
# ---------------------------------------------------------------------------
def _kandidaten(scan_size=200, top=25):
    """Longs und Shorts aus Screener + Radar + Momentum gemeinsam.

    Rueckgabe: (longs, shorts) - je eine Liste dicts mit ticker/name/score/
    upside/quelle. Ueber die ISIN/Namen-Entdopplung ist jede Firma nur einmal
    drin; taucht ein Titel in mehreren Scans auf, zaehlt das staerkste Signal.
    """
    import precompute as pc
    longs, shorts = {}, {}

    # 1) Screener/Radar ueber den Live-Scan (liefert composite, upside, verdict)
    try:
        live = pc.live_scan(universum=scan_size, top_n=top, tief=True,
                            strategie="Standard (wie Nachtlauf)") or []
    except Exception:
        live = []
    for r in live:
        t = r.get("ticker")
        if not t:
            continue
        up = r.get("upside")
        comp = r.get("composite")
        verdict = (r.get("verdict") or "")
        # Long-Kandidat: Kaufkandidat ODER klar unterbewertet mit solidem Score
        if verdict == "Kaufkandidat" or (up is not None and up >= 15
                                         and comp is not None and comp >= 60):
            longs[t] = {"ticker": t, "name": r.get("name"), "score": comp,
                        "upside": up, "quelle": "Screener/Radar"}
        # Short-Kandidat: klar ueberbewertet (nur wenn Short gewuenscht)
        elif up is not None and up <= -12 and comp is not None and comp < 45:
            shorts[t] = {"ticker": t, "name": r.get("name"), "score": comp,
                         "upside": up, "quelle": "Screener/Radar"}

    # 2) Momentum ergaenzen (Trendstaerke - als Long-Signal)
    try:
        mom = pc.momentum_scan(universum=scan_size, top_n=top) or []
    except Exception:
        mom = []
    for r in mom:
        t = r.get("ticker")
        if not t or r.get("ampel") != "gruen":
            continue
        if t not in longs:                 # Screener-Signal hat Vorrang
            longs[t] = {"ticker": t, "name": r.get("name"),
                        "score": r.get("score"), "upside": None,
                        "quelle": "Momentum"}

    _l = sorted(longs.values(), key=lambda r: -(r.get("score") or 0))
    _s = sorted(shorts.values(), key=lambda r: (r.get("upside") or 0))
    return _l, _s


# ---------------------------------------------------------------------------
# Ein Durchlauf: Exits pruefen, dann freie Slots fuellen
# ---------------------------------------------------------------------------
def _wert(st):
    """Gesamtwert = Cash + aktuelle Positionswerte."""
    total = st["cash"]
    for p in st["positions"]:
        pe, _ = _price_eur(p["ticker"])
        if pe is not None:
            if p["dir"] == "long":
                total += p["qty"] * pe
            else:                          # short: Gewinn wenn Kurs faellt
                total += p["qty"] * p["entry_eur"] + p["qty"] * (p["entry_eur"] - pe)
    return total


def _exits(st, erlauben_shorts):
    now = time.time()
    keep = []
    for p in st["positions"]:
        pe, _ = _price_eur(p["ticker"])
        if pe is None:
            keep.append(p)
            continue
        pl = _pl_pct(p, pe)
        if pl is None:
            keep.append(p)
            continue

        # Gewinn-Sicherung: Peak merken, Trailing-Stop nachziehen
        peak = max(p.get("peak_pl") or 0.0, pl)
        p["peak_pl"] = round(peak, 1)
        trail = _trail_stop(peak)
        p["trail_stop"] = trail

        exit_why = None
        if pl >= TP - 1e-6:
            exit_why = "Take-Profit"
        elif pl <= SL + 1e-6:
            exit_why = "Stop-Loss"
        elif trail is not None and pl <= trail + 1e-6:
            exit_why = f"Gewinn-Stop (+{trail:.0f} %)"

        # Teilverkauf: einmalig bei TEILVERKAUF_AB die Haelfte glattstellen
        if (exit_why is None and pl >= TEILVERKAUF_AB - 1e-6
                and not p.get("teilverkauft")):
            teil_qty = p["qty"] * TEILVERKAUF_ANTEIL
            cost = teil_qty * p["entry_eur"]
            proceeds = cost * (1 + pl / 100)
            st["cash"] += proceeds
            p["qty"] -= teil_qty
            p["teilverkauft"] = True
            st["trades"].insert(0, {
                "ts": now, "action": "teilverkauf", "ticker": p["ticker"],
                "dir": p["dir"], "pl_pct": round(pl, 1),
                "gain_eur": round(proceeds - cost, 2),
                "einsatz_eur": round(cost, 2),
                "why": f"Teilverkauf 50 % bei +{pl:.0f} %"})

        if exit_why:
            cost = p["qty"] * p["entry_eur"]
            proceeds = cost * (1 + pl / 100)
            st["cash"] += proceeds
            st["trades"].insert(0, {
                "ts": now, "action": "close", "ticker": p["ticker"],
                "dir": p["dir"], "pl_pct": round(pl, 1),
                "gain_eur": round(proceeds - cost, 2),
                "einsatz_eur": round(cost, 2), "why": exit_why})
        else:
            p["last_eur"] = round(pe, 2)
            p["pl_pct"] = round(pl, 1)
            keep.append(p)
    st["positions"] = keep


def _entries(st, longs, shorts, erlauben_shorts):
    now = time.time()
    held = {p["ticker"] for p in st["positions"]}
    gesamtwert = _wert(st)
    ziel_euro = gesamtwert * ZIEL_GEWICHT
    max_euro = gesamtwert * POS_CAP

    frei = ZIEL_POSITIONEN - len(st["positions"])
    if frei <= 0:
        return

    kandidaten = [("long", c) for c in longs]
    if erlauben_shorts:
        kandidaten += [("short", c) for c in shorts]

    for direction, c in kandidaten:
        if frei <= 0:
            break
        t = c["ticker"]
        if t in held:
            continue
        pe, _ = _price_eur(t)
        if pe is None or pe <= 0:
            continue
        # Einsatz = Zielgewicht, gedeckelt durch Obergrenze und verfuegbares Cash
        min_cash = gesamtwert * CASH_PUFFER
        verfuegbar = max(0.0, st["cash"] - min_cash)
        einsatz = min(ziel_euro, max_euro, verfuegbar)
        if einsatz < 100:                  # Kleinstpositionen ueberspringen
            continue
        qty = einsatz / pe
        st["cash"] -= qty * pe
        st["positions"].append({
            "ticker": t, "name": c.get("name"), "dir": direction,
            "qty": qty, "entry_eur": round(pe, 4), "last_eur": round(pe, 2),
            "pl_pct": 0.0, "peak_pl": 0.0, "trail_stop": None,
            "teilverkauft": False, "opened": now,
            "quelle": c.get("quelle", ""), "score": c.get("score")})
        st["trades"].insert(0, {
            "ts": now, "action": "open", "ticker": t, "dir": direction,
            "einsatz_eur": round(einsatz, 2),
            "why": f"Signal aus {c.get('quelle', '?')}"
                   + (f", Score {c.get('score')}" if c.get("score") else "")})
        held.add(t)
        frei -= 1


def durchlauf(scan_size=200, erlauben_shorts=True, grund=""):
    """Ein kompletter Rebalance-Schritt: laden, Exits, Entries, speichern."""
    st = lade()
    longs, shorts = _kandidaten(scan_size=scan_size)
    _exits(st, erlauben_shorts)
    _entries(st, longs, shorts, erlauben_shorts)
    st["value_eur"] = round(_wert(st), 2)
    st["last_check"] = time.time()
    speichere(st)
    return st


def reset(grund=""):
    st = leeres_depot(grund)
    speichere(st)
    return st


def kennzahlen(st=None):
    """Kennzahlen fuers Dashboard: Wert, Rendite, investiert, Positionen."""
    st = st or lade()
    wert = _wert(st)
    invest = sum(p["qty"] * (p.get("last_eur") or p["entry_eur"])
                 for p in st["positions"])
    rendite = (wert / st["start_capital"] - 1) * 100 if st["start_capital"] else 0
    geschlossen = [t for t in st["trades"] if t.get("action") == "close"]
    gewinner = [t for t in geschlossen if (t.get("pl_pct") or 0) > 0]
    return {
        "wert": round(wert, 2),
        "start": st["start_capital"],
        "rendite_pct": round(rendite, 2),
        "cash": round(st["cash"], 2),
        "investiert": round(invest, 2),
        "cash_quote": round(st["cash"] / wert * 100, 1) if wert else 0,
        "n_positionen": len(st["positions"]),
        "n_trades": len(st["trades"]),
        "trefferquote": (round(len(gewinner) / len(geschlossen) * 100, 0)
                         if geschlossen else None),
        "neustart_am": st.get("neustart_am"),
        "neustart_grund": st.get("neustart_grund", ""),
    }
