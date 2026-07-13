"""
trackrecord.py — Signal-Tagebuch (VORWAERTS-Test, kein Backtest).

WARUM KEIN BACKTEST:
Unsere Datenquellen liefern nur die HEUTIGEN Kennzahlen. Wuerde man damit eine
Entscheidung von vor zwei Jahren nachspielen, kaeme das Modell mit Wissen aus der
Zukunft daher (Look-ahead-Bias) - das Ergebnis waere schoengerechnet und wertlos.
Ehrlich messbar ist nur: Signal HEUTE festhalten, spaeter nachsehen, was daraus
wurde - und immer gegen den Index (sonst haelt man einen Bullenmarkt fuer Koennen).

Erfasst wird JEDES Signal, auch die Fehlschlaege. Genau das ist der Punkt.
"""
from __future__ import annotations
import time

import providers
import store

BENCHMARK = "^GSPC"          # S&P 500 als Vergleichsmassstab
HORIZONS = (30, 90, 180)     # Tage, nach denen bewertet wird


def _price(t):
    try:
        f = providers.get_fundamentals(t)
        return f.get("price")
    except Exception:
        return None


def _bench_price():
    try:
        h = providers.get_price_history(BENCHMARK, period="5d", interval="1d")
        if h is not None and not h.empty:
            return float(h["Close"].dropna().iloc[-1])
    except Exception:
        pass
    return None


def record(signals):
    """Neue Signale festhalten. signals = [{ticker, quelle, score, upside, verdict}].
    Ein Ticker wird je Quelle nur EINMAL erfasst (kein Nachtragen von Gewinnern)."""
    log = store.get_signals() or []
    known = {(e["ticker"], e.get("quelle")) for e in log}
    bp = _bench_price()
    now = time.time()
    added = 0
    for s in signals or []:
        key = (s.get("ticker"), s.get("quelle"))
        if not key[0] or key in known:
            continue
        px = s.get("price") or _price(s["ticker"])
        if not px:
            continue
        log.insert(0, {
            "ts": now, "ticker": s["ticker"], "quelle": s.get("quelle", ""),
            "score": s.get("score"), "upside": s.get("upside"),
            "verdict": s.get("verdict", ""),
            "entry_px": round(float(px), 4),
            "bench_entry": round(bp, 2) if bp else None,
        })
        known.add(key)
        added += 1
    store.set_signals(log[:250])
    print(f"[trackrecord] {added} neue Signale erfasst ({len(log)} gesamt).")
    return added


def evaluate(limit=120):
    """Aktuelle Entwicklung je Signal + Vergleich zum Index (Ueberrendite)."""
    log = store.get_signals() or []
    bp_now = _bench_price()
    out = []
    for e in log[:limit]:
        px_now = _price(e["ticker"])
        if not px_now or not e.get("entry_px"):
            continue
        ret = (px_now / e["entry_px"] - 1) * 100
        bret = None
        if bp_now and e.get("bench_entry"):
            bret = (bp_now / e["bench_entry"] - 1) * 100
        days = int((time.time() - (e.get("ts") or time.time())) / 86400)
        out.append({**e, "ret_pct": round(ret, 1),
                    "bench_pct": round(bret, 1) if bret is not None else None,
                    "excess_pct": round(ret - bret, 1) if bret is not None else None,
                    "days": days})
    return out


def summary(rows=None):
    """Ehrliche Bilanz: Trefferquote, Durchschnitt, und - entscheidend - ob wir den
    Index geschlagen haben. Ohne diesen Vergleich haelt man einen Bullenmarkt fuer
    eigenes Koennen."""
    rows = rows if rows is not None else evaluate()
    ready = [r for r in rows if r["days"] >= 14]      # frische Signale sagen nichts
    if not ready:
        return {"n": 0, "n_all": len(rows)}
    wins = [r for r in ready if r["ret_pct"] > 0]
    exc = [r["excess_pct"] for r in ready if r.get("excess_pct") is not None]
    beat = [x for x in exc if x > 0]
    return {
        "n": len(ready), "n_all": len(rows),
        "win_pct": round(len(wins) / len(ready) * 100),
        "avg_ret": round(sum(r["ret_pct"] for r in ready) / len(ready), 1),
        "avg_excess": round(sum(exc) / len(exc), 1) if exc else None,
        "beat_pct": round(len(beat) / len(exc) * 100) if exc else None,
    }
