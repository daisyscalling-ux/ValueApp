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
    """Aktueller Kurs - moeglichst leichtgewichtig und robust. Erst der schnelle
    Intraday-Quote (falls vorhanden), dann die Kurshistorie (zuverlaessiger als ein
    voller Fundamentaldaten-Abruf), zuletzt Fundamentaldaten. So scheitert der Kurs
    nicht schon an einem einzelnen ausgelasteten Endpoint."""
    # 1) schneller Quote, falls der Provider ihn hat
    for fn in ("get_quote", "get_intraday_quote"):
        f = getattr(providers, fn, None)
        if f:
            try:
                q = f(t)
                if isinstance(q, dict):
                    px = q.get("price")
                elif isinstance(q, (tuple, list)) and q:
                    px = q[0]                      # (preis, waehrung)
                else:
                    px = q
                if px:
                    # auf dieselbe Einheit bringen wie der Einstiegskurs
                    n = getattr(providers, "normalise_price", None)
                    return float(n(t, px)) if n else float(px)
            except Exception:
                pass
    # 2) letzter Schlusskurs aus der Historie
    try:
        h = providers.get_price_history(t, period="5d", interval="1d")
        if h is not None and not h.empty:
            return float(h["Close"].dropna().iloc[-1])
    except Exception:
        pass
    # 3) Fundamentaldaten als letzte Option
    try:
        return providers.get_fundamentals(t).get("price")
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
        # Einstiegskurs auf dieselbe Einheit bringen wie spaeter der Vergleichskurs.
        # s["price"] stammt aus den Scan-Daten und kann bei Londoner Titeln in
        # PENCE vorliegen - ohne diese Zeile entstehen Renditen von -99 %.
        _n = getattr(providers, "normalise_price", None)
        if _n:
            try:
                px = _n(s["ticker"], px) or px
            except Exception:
                pass
        try:
            _ccy = "GBP" if providers.is_pence(s["ticker"]) else ""
        except Exception:
            _ccy = ""
        log.insert(0, {
            "ts": now, "ticker": s["ticker"], "quelle": s.get("quelle", ""),
            "score": s.get("score"), "upside": s.get("upside"),
            "verdict": s.get("verdict", ""),
            "entry_px": round(float(px), 4),
            "entry_norm": True,          # Kennzeichen: bereits normalisiert
            "entry_ccy": _ccy,
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
        entry = e.get("entry_px")
        if not px_now or not entry:
            continue

        # ALT-DATENSAETZE reparieren: Signale, die VOR der Pence-Korrektur
        # erfasst wurden, haben ihren Einstiegskurs noch in Pence gespeichert.
        # Der Vergleichskurs ist jetzt in Pfund -> Verhaeltnis ~100 -> -99 %.
        # Erkennung ueber das Verhaeltnis, nicht ueber die Datumsgrenze, weil
        # nur so auch gemischte Bestaende sauber werden.
        repariert = False
        if not e.get("entry_norm"):
            try:
                if providers.is_pence(e["ticker"]) and px_now > 0:
                    verhaeltnis = entry / px_now
                    if 20 < verhaeltnis < 500:        # ~Faktor 100 = Pence-Einstieg
                        entry = entry / 100.0
                        repariert = True
            except Exception:
                pass

        ret = (px_now / entry - 1) * 100
        # SICHERHEITSNETZ gegen verbleibenden Einheiten-Mischmasch. Greift in
        # BEIDE Richtungen: +9900 % (Pence/Pfund) genauso wie -99 % (Pfund/Pence).
        # Solche Werte sind keine Rendite, sondern ein Datenfehler - sie werden
        # markiert und aus allen Statistiken herausgehalten, statt sie still zu
        # "korrigieren" (eine stille Korrektur wuerde echte Ausreisser verschleiern).
        suspekt = abs(ret) > 500 or ret < -85
        bret = None
        if bp_now and e.get("bench_entry"):
            bret = (bp_now / e["bench_entry"] - 1) * 100
        days = int((time.time() - (e.get("ts") or time.time())) / 86400)
        out.append({**e, "entry_px": round(entry, 4),
                    "ret_pct": round(ret, 1),
                    "bench_pct": round(bret, 1) if bret is not None else None,
                    "excess_pct": round(ret - bret, 1) if bret is not None else None,
                    "days": days, "suspekt": suspekt, "repariert": repariert})
    return out


def _clean(rows):
    """Nur auswertbare Zeilen - ohne offensichtliche Datenfehler."""
    return [r for r in rows if not r.get("suspekt")]


def summary(rows=None):
    """Ehrliche Bilanz: Trefferquote, Durchschnitt, und - entscheidend - ob wir den
    Index geschlagen haben. Ohne diesen Vergleich haelt man einen Bullenmarkt fuer
    eigenes Koennen."""
    rows = rows if rows is not None else evaluate()
    rows = _clean(rows)
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


def source_stats(quelle=None, invest_eur=None, rows=None):
    """Statistik gefiltert nach Quelle ('Screener', 'Radar' oder None = alle).

    Liefert gewonnene/verlorene Signale, Win %, Ø-Rendite %, Ø-Ueberrendite vs. Index.
    invest_eur (optional): MODELLRECHNUNG - haette man bei JEDEM Signal diesen festen
    Betrag investiert, was waere daraus geworden? Ausdruecklich KEIN echtes Geld -
    ein Screener-Signal ist kein Trade (kein Einsatz, keine Stueckzahl). Nur eine
    Was-waere-wenn-Zahl, damit sich die Trefferquote in Euro einordnen laesst."""
    rows = _clean(rows if rows is not None else evaluate())
    ready = [r for r in rows if r["days"] >= 14
             and (quelle is None or r.get("quelle") == quelle)]
    if not ready:
        return {"n": 0}
    wins = [r for r in ready if r["ret_pct"] > 0]
    losses = [r for r in ready if r["ret_pct"] <= 0]
    exc = [r["excess_pct"] for r in ready if r.get("excess_pct") is not None]
    out = {
        "n": len(ready),
        "wins": len(wins), "losses": len(losses),
        "win_pct": round(len(wins) / len(ready) * 100),
        "avg_ret": round(sum(r["ret_pct"] for r in ready) / len(ready), 1),
        "best": round(max(r["ret_pct"] for r in ready), 1),
        "worst": round(min(r["ret_pct"] for r in ready), 1),
        "avg_excess": round(sum(exc) / len(exc), 1) if exc else None,
    }
    if invest_eur and invest_eur > 0:
        # Modell: fester Betrag je Signal, Ergebnis = Summe der Einzelergebnisse.
        invested = invest_eur * len(ready)
        final = sum(invest_eur * (1 + r["ret_pct"] / 100) for r in ready)
        gain = final - invested
        out["model"] = {
            "per_signal": invest_eur,
            "invested": round(invested, 2),
            "final": round(final, 2),
            "gain_eur": round(gain, 2),
            "gain_pct": round(gain / invested * 100, 1) if invested else None,
        }
    return out


def discrimination(rows=None, min_days=14):
    """TRENNT die Scorecard? Vergleicht Treffer gegen Kontrollgruppe.

    Der wichtigste Test des ganzen Systems. Eine hohe Trefferquote allein
    sagt NICHTS - im steigenden Markt gewinnt fast alles. Aussagekraeftig
    ist nur der ABSTAND zwischen den als gut und den als schlecht
    bewerteten Titeln. Ist er nahe null oder negativ, trennt das Modell
    nicht, egal wie gut die absolute Rendite aussieht."""
    rows = _clean(rows if rows is not None else evaluate())
    ready = [r for r in rows if r["days"] >= min_days]
    gut = [r for r in ready if r.get("quelle") in ("Screener", "Radar")]
    schlecht = [r for r in ready if r.get("quelle") == "Negativ"]

    def _agg(rs):
        if not rs:
            return None
        exc = [r["excess_pct"] for r in rs if r.get("excess_pct") is not None]
        return {
            "n": len(rs),
            "avg_ret": round(sum(r["ret_pct"] for r in rs) / len(rs), 1),
            "avg_excess": round(sum(exc) / len(exc), 1) if exc else None,
            "win_pct": round(sum(1 for r in rs if r["ret_pct"] > 0) / len(rs) * 100),
        }

    g, s = _agg(gut), _agg(schlecht)
    out = {"gut": g, "schlecht": s, "spread": None, "urteil": None}
    if not g or not s:
        out["urteil"] = "noch keine Gegenprobe moeglich"
        return out

    out["spread"] = round(g["avg_ret"] - s["avg_ret"], 1)
    # Ehrliche Einordnung - bewusst zurueckhaltend formuliert
    n_min = min(g["n"], s["n"])
    if n_min < 10:
        out["urteil"] = ("zu wenige Faelle fuer eine Aussage "
                         f"(kleinste Gruppe: {n_min})")
    elif out["spread"] > 5:
        out["urteil"] = "Treffer laufen besser als die Kontrollgruppe"
    elif out["spread"] < -5:
        out["urteil"] = ("Kontrollgruppe laeuft BESSER - das Modell trennt "
                         "nicht wie gedacht")
    else:
        out["urteil"] = ("kein erkennbarer Unterschied - die Auswahl bringt "
                         "bisher keinen Mehrwert")
    return out


def _bucket_stats(rows):
    """Kennzahlen einer Gruppe: n, Win %, Durchschnittsrendite, Ø Ueberrendite."""
    if not rows:
        return None
    exc = [r["excess_pct"] for r in rows if r.get("excess_pct") is not None]
    return {
        "n": len(rows),
        "win_pct": round(sum(1 for r in rows if r["ret_pct"] > 0) / len(rows) * 100),
        "avg_ret": round(sum(r["ret_pct"] for r in rows) / len(rows), 1),
        "avg_excess": round(sum(exc) / len(exc), 1) if exc else None,
    }


# Reihenfolge der Scorecard-Urteile von stark nach schwach
VERDICT_ORDER = ["Kaufkandidat", "Solide \u2013 Watchlist", "Knapp \u2013 Watchlist",
                 "Verwerfen"]


def by_verdict(rows=None):
    """DIE Kernfrage: Schlagen 'Kaufkandidat'-Titel die 'Verwerfen'-Titel?
    Gruppiert die reifen Signale nach dem Scorecard-Urteil beim Signalzeitpunkt
    und vergleicht ihre spaetere Wertentwicklung. Erst wenn die besseren Urteile
    ueber viele Faelle auch besser abschneiden, hat die Scorecard bewiesen, dass
    sie etwas kann - vorher ist sie nur plausibel."""
    rows = rows if rows is not None else evaluate()
    ready = [r for r in rows if r["days"] >= 14 and r.get("verdict")]
    out = []
    for v in VERDICT_ORDER:
        grp = [r for r in ready if r.get("verdict") == v]
        st = _bucket_stats(grp)
        if st:
            out.append({"verdict": v, **st})
    # monotonie-Check: faellt die Ueberrendite von stark nach schwach?
    ranked = [g for g in out if g.get("avg_excess") is not None]
    monotonic = all(ranked[i]["avg_excess"] >= ranked[i + 1]["avg_excess"]
                    for i in range(len(ranked) - 1)) if len(ranked) >= 2 else None
    return {"groups": out, "monotonic": monotonic, "n_ready": len(ready)}


def calibration(rows=None):
    """Kalibrierung: Trifft ein HOHER Score haeufiger als ein niedriger?
    Teilt die Signale in Score-Baender und zeigt Win % + Ø Ueberrendite je Band.
    Ein gut kalibriertes System zeigt steigende Werte mit steigendem Score."""
    rows = rows if rows is not None else evaluate()
    ready = [r for r in rows if r["days"] >= 14 and r.get("score") is not None]
    bands = [("\u2265 80", 80, 201), ("70\u201379", 70, 80),
             ("60\u201369", 60, 70), ("< 60", -1, 60)]
    out = []
    for label, lo, hi in bands:
        grp = [r for r in ready if lo <= r["score"] < hi]
        st = _bucket_stats(grp)
        if st:
            out.append({"band": label, **st})
    return {"bands": out, "n_ready": len(ready)}
