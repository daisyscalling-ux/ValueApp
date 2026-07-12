"""
hedgefund.py — fortlaufende Papier-Portfolios je Hedgefonds-Strategie.

Regeln (deterministisch, pro Pruefung):
  - LONG schliessen bei Gewinn >= +20 % oder Verlust <= -10 %
  - SHORT schliessen bei Gewinn >= +15 % (Kurs gefallen) oder Verlust <= -10 %
  - Freie Slots werden mit neuen Kandidaten aus dem Scan gefuellt
  - Positionsgroesse: gleichgewichtet je Slot, 15 %-Deckel, EUR-basiert
Strategien: marktneutral (8L/8S), 130/30 (8L/3S), quality_long (8L/0S).
Zustand liegt persistent in store-Aux (Google Sheet) -> App und Cron teilen ihn.
Laeuft standalone (Cron, 2x taeglich) UND on-demand aus der App.
"""
from __future__ import annotations
import time

import providers
import scoring
import valuation
import store

TP_LONG, SL_LONG = 20.0, -10.0
TP_SHORT, SL_SHORT = 15.0, -10.0
STRATS = {"marktneutral": (8, 8), "130/30": (8, 3), "quality_long": (8, 0),
          "core_ko": (6, 0)}       # Aktien-Kern (6) + KO-Beimischung auf ANDERE Titel
KO_LEV, KO_N, KO_EACH = 3.0, 3, 0.04    # 3 KOs x 4 % = ~12 % (Ziel 8-15 %)
TP_KO, SL_KO = 45.0, -30.0
START_CAPITAL = 10000.0
POS_CAP = 0.15


def _price_eur(t):
    f = providers.get_fundamentals(t)
    p = f.get("price")
    if not p:
        return None, None
    fx = providers.get_fx_to_eur(f.get("currency", "USD")) or 1.0
    return p * fx, f


def _pl_pct(pos, price_eur):
    e = pos["entry_eur"]
    if not e or not price_eur:
        return None
    r = (price_eur / e - 1) * 100
    if pos.get("type") == "ko":               # Zertifikat: Basiswert-Bewegung x Hebel
        r = r if pos["ko_dir"] == "call" else -r
        return max(r * KO_LEV, -100.0)
    return r if pos["dir"] == "long" else -r


def candidates(size=60):
    """Kompakter Long/Short-Scan (flach) fuer die Slot-Befuellung."""
    try:
        import market_screener as ms
        usd = providers.get_fx_to_eur("USD") or 0.92
        tks, _ = ms.get_universe(["us", "de", "fr", "gb", "nl"], 5e9 / usd, size)
    except Exception:
        return [], []
    longs, shorts = [], []
    for t in tks:
        f = providers.get_fundamentals(t)
        price = f.get("price")
        if not price:
            continue
        ep = valuation.classify_playbook(f)
        comp = scoring.score_stock(f, None, preset=ep)["composite"]
        v = valuation.fair_value(f, None, ep)
        up = v.get("upside_pct")
        if v.get("fair_value_capped") and v.get("analyst_target"):
            up = (v["analyst_target"] / price - 1) * 100
        if comp is None or up is None:
            continue
        h = providers.get_price_history(t, period="1y", interval="1d")
        above = mom20 = mom60 = None
        if h is not None and not h.empty:
            cl = [float(x) for x in h["Close"].dropna()]
            if len(cl) > 61:
                above = cl[-1] > sum(cl[-200:]) / min(len(cl), 200)
                mom20, mom60 = cl[-1] / cl[-21] - 1, cl[-1] / cl[-61] - 1
        if comp >= 58 and up >= 10 and (mom60 is None or mom60 > -0.20):
            longs.append((comp * 0.6 + min(up, 60) * 0.5, t))
        if up <= -20 and comp <= 52:
            if not (above and (mom60 or 0) > 0.15) and ((not above) or (mom20 or 0) < 0):
                shorts.append(((-up) * 0.5 + (60 - comp) * 0.4, t))
    longs.sort(reverse=True)
    shorts.sort(reverse=True)
    return [t for _, t in longs], [t for _, t in shorts]


def rebalance(state, longs_cand, shorts_cand):
    """Eine Pruefung: TP/SL anwenden, dann freie Slots fuellen. Mutiert state."""
    now = time.time()
    held = {p["ticker"] for p in state["positions"]}
    # 1) Exits
    keep = []
    for p in state["positions"]:
        pe, _ = _price_eur(p["ticker"])
        if pe is None:
            keep.append(p)
            continue
        pl = _pl_pct(p, pe)
        if p.get("type") == "ko":             # Knock-out: Barriere durchbrochen -> 0
            hit = (pe <= p["barrier_eur"]) if p["ko_dir"] == "call" else (pe >= p["barrier_eur"])
            if hit:
                state["trades"].insert(0, {"ts": now, "action": "close",
                    "ticker": p["ticker"], "dir": f'KO-{p["ko_dir"]}',
                    "pl_pct": -100.0, "why": "Knock-out"})
                held.discard(p["ticker"])
                continue
            tp, sl = TP_KO, SL_KO
        else:
            tp, sl = (TP_LONG, SL_LONG) if p["dir"] == "long" else (TP_SHORT, SL_SHORT)
        if pl is not None and (pl >= tp - 1e-6 or pl <= sl + 1e-6):
            proceeds = p["qty"] * p["entry_eur"] * (1 + pl / 100)
            state["cash"] += proceeds
            state["trades"].insert(0, {
                "ts": now, "action": "close", "ticker": p["ticker"],
                "dir": (f'KO-{p["ko_dir"]}' if p.get("type") == "ko" else p["dir"]),
                "pl_pct": round(pl, 1),
                "why": ("Take-Profit" if pl >= tp else "Stop-Loss")})
            held.discard(p["ticker"])
        else:
            p["last_eur"] = round(pe, 2)
            p["pl_pct"] = round(pl, 1) if pl is not None else None
            keep.append(p)
    state["positions"] = keep
    # 2) Entries (freie Slots)
    nl, ns = STRATS[state["strategy"]]
    for direction, n_max, cands in (("long", nl, longs_cand), ("short", ns, shorts_cand)):
        cur = [p for p in state["positions"] if p["dir"] == direction]
        for t in cands:
            if len(cur) >= n_max or t in held:
                continue
            pe, _ = _price_eur(t)
            if not pe:
                continue
            avail = state["cash"]
            if state["strategy"] == "core_ko":     # Cash fuer die KO-Beimischung reservieren
                n_open_ko = KO_N - len([p for p in state["positions"]
                                        if p.get("type") == "ko"])
                avail -= max(n_open_ko, 0) * KO_EACH * state["start_capital"]
            budget = min(max(avail, 0) * 0.5, POS_CAP * state["start_capital"])
            qty = int(budget / pe)
            if qty < 1 or budget < 50:
                break
            state["cash"] -= qty * pe
            pos = {"ticker": t, "dir": direction, "entry_eur": round(pe, 2),
                   "qty": qty, "opened": now, "last_eur": round(pe, 2), "pl_pct": 0.0}
            state["positions"].append(pos)
            cur.append(pos)
            held.add(t)
            state["trades"].insert(0, {"ts": now, "action": "open", "ticker": t,
                                       "dir": direction, "pl_pct": None, "why": "Signal"})
    if state["strategy"] == "core_ko":
        kos = [p for p in state["positions"] if p.get("type") == "ko"]
        core_t = {p["ticker"] for p in state["positions"] if not p.get("type")}
        ko_t = {p["ticker"] for p in kos}
        # KO-Basiswerte muessen ANDERE Unternehmen sein als der Aktien-Kern - sonst
        # traegt man dasselbe Firmenrisiko doppelt (Aktie + gehebelter Schein).
        calls = [t for t in longs_cand if t not in core_t and t not in ko_t]
        puts = [t for t in shorts_cand if t not in core_t and t not in ko_t]
        have_call = any(p["ko_dir"] == "call" for p in kos)
        have_put = any(p["ko_dir"] == "put" for p in kos)
        plan = []
        # Immer BEIDE Richtungen: zuerst je einen Put und einen Call sichern ...
        if not have_put and puts:
            plan.append(("put", puts.pop(0)))
        if not have_call and calls:
            plan.append(("call", calls.pop(0)))
        # ... dann restliche Slots abwechselnd auffuellen.
        while len(kos) + len(plan) < KO_N and (calls or puts):
            if calls and len(kos) + len(plan) < KO_N:
                plan.append(("call", calls.pop(0)))
            if puts and len(kos) + len(plan) < KO_N:
                plan.append(("put", puts.pop(0)))
        for kd, t in plan:
            pe, _ = _price_eur(t)
            budget = min(state["cash"], KO_EACH * state["start_capital"])
            if not pe or budget < 50:
                continue
            qty = budget / pe
            barrier = pe * (1 - 1 / KO_LEV) if kd == "call" else pe * (1 + 1 / KO_LEV)
            state["cash"] -= qty * pe
            pos = {"ticker": t, "dir": "long", "type": "ko", "ko_dir": kd,
                   "leverage": KO_LEV, "barrier_eur": round(barrier, 2),
                   "entry_eur": round(pe, 2), "qty": qty, "opened": now,
                   "last_eur": round(pe, 2), "pl_pct": 0.0}
            state["positions"].append(pos)
            kos.append(pos)
            ko_t.add(t)
            state["trades"].insert(0, {"ts": now, "action": "open", "ticker": t,
                                       "dir": f"KO-{kd}", "pl_pct": None, "why": "Signal"})
    state["trades"] = state["trades"][:40]
    # 3) Gesamtwert
    val = state["cash"]
    for p in state["positions"]:
        pl = p.get("pl_pct") or 0
        val += p["qty"] * p["entry_eur"] * (1 + pl / 100)
    state["value_eur"] = round(val, 2)
    state["last_check"] = now
    return state


def fresh_state(strategy):
    """Leeres Startdepot fuer eine Strategie (Papiergeld, keine Positionen)."""
    return {"strategy": strategy, "start_capital": START_CAPITAL,
            "cash": START_CAPITAL, "positions": [], "trades": [],
            "created": time.time(), "value_eur": START_CAPITAL,
            "last_check": None}


def reset(strategy, refill=True, scan_size=50):
    """Ein Strategie-Depot komplett neu aufsetzen (alle Positionen verwerfen).
    refill=True baut direkt nach den aktuellen Regeln neu auf."""
    hf = store.get_hf() or {}
    st_ = fresh_state(strategy)
    if refill:
        lc, sc = candidates(scan_size)
        st_ = rebalance(st_, lc, sc)
    hf[strategy] = st_
    store.set_hf(hf)
    return st_


def run_all(scan_size=60):
    """Alle Strategie-Portfolios pruefen/anpassen (Cron-Einstieg, 2x taeglich)."""
    hf = store.get_hf() or {}
    lc, sc = candidates(scan_size)
    for strat in STRATS:
        st_ = hf.get(strat) or fresh_state(strat)
        st_["strategy"] = strat
        hf[strat] = rebalance(st_, lc, sc)
        print(f"[hedgefund] {strat}: Wert {hf[strat]['value_eur']:.0f} EUR, "
              f"{len(hf[strat]['positions'])} Positionen")
    store.set_hf(hf)
    return hf
