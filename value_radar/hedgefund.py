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
import math
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


_CORE_FIELDS = (
    ("eps_trailing", "eps_forward"),
    ("revenue_growth",),
    ("operating_margin", "profit_margin", "gross_margin"),
    ("roe", "roa"),
    ("free_cashflow", "ebitda"),
    ("market_cap",),
    ("pb", "book_value_ps"),
    ("total_debt", "net_debt", "cash"),
    ("ev_ebitda", "pe_forward", "pe_trailing"),
)


def _data_ok(f, need=5):
    """Wieviele Kennzahlen-Gruppen sind WIRKLICH vorhanden? Das Scoring fuellt
    fehlende Werte mit 50 (neutral) auf - ohne diese Pruefung koennen datenarme
    Notierungen (z.B. BHPL.XC mit 3/9) einen scheinbar soliden Composite bekommen,
    obwohl kaum eine Zahl echt ist."""
    have = sum(1 for grp in _CORE_FIELDS
               if any(f.get(k) not in (None, "") for k in grp))
    return have >= need, have


def _quality_gate(f, s, v, direction, min_groups=5):
    """Mindestanforderungen fuers Depot.

    LONG folgt der SCORECARD-Logik (die verwirft einen Titel bei 2+ verfehlten
    Pflichtkriterien). Hart, weil sie den Kern eines Kaufkandidaten ausmachen:
      - Composite >= 55  (Qualitaet)
      - Upside >= +15 % UND belastbarer Fair Value
      - kein Value-Trap-Verdacht
    Weich (ein Verfehlen ist erlaubt, wie bei "Knapp - Watchlist"):
      - Bewertungs-Streuung <= 60 %
    BP fiel genau hier durch: Composite 50, unbelastbarer Fair Value, Streuung 116 %
    -> in der Scorecard "Verwerfen", also auch kein Long-Kandidat.

    SHORT/PUT: Datenlage muss stimmen, ein unsicherer Fair Value ist aber kein K.o.
    (die These lebt ja gerade von der Fehlbewertung)."""
    ok_data, n = _data_ok(f, need=min_groups)
    if not ok_data:                                  # Kernschutz gegen BHPL.XC & Co.
        return False, f"nur {n}/9 Kennzahlen-Gruppen vorhanden"
    if (v.get("n_methods") or 0) < 2:
        return False, "Fair Value aus nur einer Methode"

    if direction == "long":
        comp = s.get("composite")
        if comp is None or comp < 55:
            return False, f"Composite {comp:.0f} < 55 (Scorecard-Pflicht)" if comp \
                else "kein Composite"
        up = v.get("upside_pct")
        if up is None or up < 15 or not v.get("reliable"):
            return False, (f"Upside {up} / Fair Value nicht belastbar "
                           "(Scorecard-Pflicht)")
        if s.get("value_trap"):
            return False, "Value-Trap-Verdacht"
        spread = v.get("spread_pct")
        if spread is not None and spread > 90:       # weit jenseits der Scorecard
            return False, f"Bewertungs-Streuung {spread:.0f} % (unbrauchbar)"
        return True, "ok"

    # Short-/Put-Seite
    if not v.get("reliable") and n < min_groups + 1:
        return False, "Fair Value unsicher bei d\u00fcnner Datenlage"
    return True, "ok"


_SC_CACHE = {}          # Ticker -> (ok, verdict, missing, evaluated) je Lauf


def scorecard_ok(ticker, f, s, v):
    """Laesst die ECHTE Scorecard laufen (alle 6 Pflichtkriterien) statt einer
    Nachbildung. Frueher pruefte der Hedgefonds nur Composite/Upside/Value-Trap -
    Matrix 1 (Setup), Insider-Verkaeufe und der Trendfilter fehlten. Genau dadurch
    kam BP ins Long-Buch, obwohl die Scorecard es verwirft.

    Rueckgabe: (ok, urteil, offene_punkte, evaluated)
      evaluated=False heisst: Pruefung war NICHT moeglich (Modul/Daten fehlen).
      Der Aufrufer entscheidet dann bewusst - neue Titel werden abgelehnt,
      bestehende Positionen aber NICHT wegen eines Fehlers liquidiert."""
    if ticker in _SC_CACHE:
        return _SC_CACHE[ticker]
    try:
        import matrices as mx
        import scorecard as sc
        import intel as intel_mod
    except Exception as e:
        res = (False, "Scorecard nicht pruefbar", f"Modul fehlt: {e}", False)
        _SC_CACHE[ticker] = res
        return res
    try:
        hist = providers.get_price_history(ticker, period="1y", interval="1d")
        try:
            intel = intel_mod.gather(ticker, name=f.get("name"))
        except Exception:
            intel = {}
        try:
            extras = providers.get_signal_extras(ticker)     # Reihen/EPS-Rev/Short
        except Exception:
            extras = {}
        f = dict(f)
        f.setdefault("_catalyst_score", (intel or {}).get("catalyst_score", 50))
        sig = mx.build_signals(f, hist, intel.get("analyst"), extras)
        m1 = mx.auto_m1_total(sig)
        m2 = mx.auto_m2_total(sig)
        r = sc.evaluate(f, v, s.get("composite"), m1, m2, extras,
                        intel.get("insider"), intel.get("analyst"))
        mand = r.get("mandatory", [])
        # HART (muessen sitzen): Qualitaet + belastbarer Bewertungsabstand.
        # WEICH (eines darf fehlen): Setup/Matrix 1, Streuung, Trend.
        # Das entspricht der Scorecard-Stufe "Knapp" - streng genug, um BP
        # (mehrere Verfehlungen) auszuschliessen, aber nicht so streng, dass das
        # Long-Buch leer bleibt.
        HARD = ("Composite", "Upside")
        hard_fail = [m["label"] for m in mand
                     if not m["ok"] and any(h in m["label"] for h in HARD)]
        soft_fail = [m["label"] for m in mand
                     if not m["ok"] and not any(h in m["label"] for h in HARD)]
        ok = (not hard_fail) and len(soft_fail) <= 1 and not s.get("value_trap")
        detail = "; ".join(hard_fail + soft_fail)
        if s.get("value_trap"):
            detail = ("Value-Trap-Verdacht; " + detail).strip("; ")
        res = (ok, r.get("verdict", ""), detail, True)
    except Exception as e:
        res = (False, "Scorecard-Fehler", str(e), False)
    _SC_CACHE[ticker] = res
    return res


def candidates(size=60):
    """Kandidaten. Zweistufig: flacher Vorscan (API-schonend), dann TIEFE Pruefung
    der Shortlist + Qualitaets-Gates.

    Rueckgabe: (longs, shorts, puts)
      shorts = ECHTE Short-Positionen (unbegrenztes Risiko) -> strenge Regeln:
               stark ueberbewertet, schwaechere Qualitaet, KEIN Aufwaertstrend.
      puts   = Basiswerte fuer die KO-Put-BEIMISCHUNG (nur ~4 % Einsatz, Verlust
               auf den Einsatz begrenzt) -> mildere Regeln: ueberbewertet und nicht
               in einem starken Aufwaertstrend. So bleibt die Beimischung gemischt,
               auch wenn es (wie im Bullenmarkt ueblich) keine echten Shorts gibt.
    """
    try:
        import market_screener as ms
        usd = providers.get_fx_to_eur("USD") or 0.92
        tks, _ = ms.get_universe(["us", "de", "fr", "gb", "nl"], 5e9 / usd, size)
    except Exception:
        return [], [], []

    pre_l, pre_s = [], []
    for t in tks:                                   # Stufe 1: flacher Vorscan
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
        if comp >= 52 and up >= 10:      # weiter Vorscan, hartes Gate spaeter
            pre_l.append(t)
        elif up <= -8:                              # weit gefasst: Puts brauchen weniger
            pre_s.append(t)

    longs, shorts, puts = [], [], []
    for direction, pre in (("long", pre_l), ("short", pre_s)):
        for t in pre[:30]:                          # Stufe 2: tiefe Pruefung
            f = providers.get_fundamentals(t, deep=True)
            price = f.get("price")
            if not price:
                continue
            ep = valuation.classify_playbook(f)
            s = scoring.score_stock(f, None, preset=ep)
            comp = s["composite"]
            v = valuation.fair_value(f, None, ep)
            up = v.get("upside_pct")
            if v.get("fair_value_capped") and v.get("analyst_target"):
                up = (v["analyst_target"] / price - 1) * 100
            if comp is None or up is None:
                continue
            ok, why = _quality_gate(f, s, v, direction)
            if not ok:
                print(f"[hedgefund] {t} verworfen ({direction}): {why}")
                continue
            h = providers.get_price_history(t, period="1y", interval="1d")
            above = mom20 = mom60 = None
            if h is not None and not h.empty:
                cl = [float(x) for x in h["Close"].dropna()]
                if len(cl) > 61:
                    above = cl[-1] > sum(cl[-200:]) / min(len(cl), 200)
                    mom20, mom60 = cl[-1] / cl[-21] - 1, cl[-1] / cl[-61] - 1
            strong_uptrend = bool(above and (mom60 or 0) > 0.15)

            if direction == "long":
                # Schwellen konsistent mit der Scorecard (Composite >= 55, Upside >= 15).
                if comp >= 55 and up >= 15 and (mom60 is None or mom60 > -0.20):
                    # ECHTE Scorecard: ALLE Pflichtkriterien muessen erfuellt sein
                    # (inkl. Matrix-1-Setup, Insider, Trend) - sonst kein Long-Buch.
                    sc_ok, verdict, missing, _ev = scorecard_ok(t, f, s, v)
                    if not sc_ok:                    # auch bei "nicht pruefbar": NICHT rein
                        print(f"[hedgefund] {t} verworfen (long): Scorecard "
                              f"\"{verdict}\" - offen: {missing}")
                        continue
                    # EINSTIEGSZONEN-BONUS (kein harter Filter): Liegt der Kurs
                    # in der Zone (Kurs <= definierter Einstieg), ist der Titel
                    # attraktiver bepreist und wird im Ranking bevorzugt. Titel
                    # ueber der Zone bleiben kaufbar (das Depot soll aktiv sein
                    # und starken Trends folgen koennen), landen aber weiter
                    # hinten. So wird "zu teuer gekauft" seltener, ohne das
                    # Depot bei teurem Markt komplett in Cash zu zwingen.
                    _entry = v.get("entry_price")
                    _zonen_bonus = 0.0
                    if _entry and price:
                        if price <= _entry:
                            _zonen_bonus = 12.0       # in der Zone -> klar bevorzugt
                        elif price <= _entry * 1.05:
                            _zonen_bonus = 5.0        # knapp drueber (<5%) -> leicht bevorzugt
                    longs.append((comp * 0.6 + min(up, 60) * 0.5 + _zonen_bonus, t))
                continue
            # --- Short-Seite ---
            score = (-up) * 0.5 + max(60 - comp, 0) * 0.4
            # ECHTER Short: streng (unbegrenztes Verlustrisiko)
            if up <= -20 and comp <= 52 and not strong_uptrend and \
               ((not above) or (mom20 or 0) < 0):
                shorts.append((score, t))
            # KO-PUT-Beimischung: milder (Verlust auf den Einsatz begrenzt),
            # aber nie gegen einen starken Aufwaertstrend.
            if up <= -12 and not strong_uptrend:
                puts.append((score, t))

    for lst in (longs, shorts, puts):
        lst.sort(reverse=True)
    return ([t for _, t in longs], [t for _, t in shorts],
            [t for _, t in puts])


def _trail_stop(peak_pl):
    """Gewinn-Sicherung (Ratchet): ab +15 % Gewinn wird der Stop nachgezogen und
    steigt dann in 5er-Schritten mit. +15 -> Stop +10, +20 -> +15, +25 -> +20 ...
    Der Stop faellt NIE wieder zurueck (er haengt am hoechsten erreichten Gewinn)."""
    if peak_pl is None or peak_pl < 15.0:
        return None
    return 5.0 * math.floor(peak_pl / 5.0) - 5.0


def rebalance(state, longs_cand, shorts_cand, put_cand=None, revalidate=True):
    """Eine Pruefung: TP/SL anwenden, dann freie Slots fuellen. Mutiert state.
    put_cand = mildere Liste fuer die KO-Put-Beimischung (siehe candidates()).
    revalidate = bestehende Aktien-Longs erneut gegen die Scorecard pruefen."""
    now = time.time()
    held = {p["ticker"] for p in state["positions"]}
    # Sperrfrist (Cooldown): ein gerade geschlossener Titel darf nicht sofort
    # wieder gekauft werden. Ohne das drehte das Tool denselben Titel (z.B.
    # NWG.L) staendig hin und her - Verkauf, dann Minuten spaeter Rueckkauf,
    # fuer Cent-Betraege. state["cooldown"] = {ticker: zeit_bis}.
    _COOLDOWN_TAGE = 5
    cooldown = state.setdefault("cooldown", {})
    # abgelaufene Sperren aufraeumen
    for _tk in [k for k, v in cooldown.items() if v <= now]:
        cooldown.pop(_tk, None)
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
                _cost = p["qty"] * p["entry_eur"]
                state["trades"].insert(0, {"ts": now, "action": "close",
                    "ticker": p["ticker"], "dir": f'KO-{p["ko_dir"]}',
                    "pl_pct": -100.0, "gain_eur": round(-_cost, 2),
                    "einsatz_eur": round(_cost, 2), "why": "Knock-out"})
                held.discard(p["ticker"])
                continue
            tp, sl = TP_KO, SL_KO
        else:
            tp, sl = (TP_LONG, SL_LONG) if p["dir"] == "long" else (TP_SHORT, SL_SHORT)
        # Gewinn-Sicherung: hoechsten erreichten Gewinn merken, Stop nachziehen.
        peak = max(p.get("peak_pl") or 0.0, pl if pl is not None else 0.0)
        p["peak_pl"] = round(peak, 1)
        trail = _trail_stop(peak)
        p["trail_stop"] = trail

        exit_why = None
        if pl is not None:
            if pl >= tp - 1e-6:
                exit_why = "Take-Profit"
            elif pl <= sl + 1e-6:
                exit_why = "Stop-Loss"
            elif trail is not None and pl <= trail + 1e-6:
                exit_why = f"Gewinn-Stop (+{trail:.0f} %)"
        # Bestehende AKTIEN-Longs erneut gegen die Scorecard pruefen: faellt ein Titel
        # inzwischen durch (Signal erloschen), wird er geschlossen - sonst bliebe er
        # bis zum Stop-Loss liegen (so hing BP im Depot).
        # HYSTERESE: Nur schliessen, wenn der Titel DEUTLICH durchfaellt, nicht
        # schon bei haarscharfem Verfehlen. Sonst wird ein Titel, dessen
        # Kennzahlen um die Schwelle herum schwanken, staendig raus- und wieder
        # reingekauft (NWG.L-Effekt). Ein Titel muss erst durchfallen UND darf
        # nicht nur knapp daneben liegen.
        if (exit_why is None and p["dir"] == "long" and p.get("type") != "ko"
                and revalidate):
            try:
                _f = providers.get_fundamentals(p["ticker"], deep=True)
                # Nur bei belastbaren Daten neu bewerten - sonst schliesst ein
                # roic-Aussetzer faelschlich eine gute Position.
                if _f and _f.get("_vollstaendig", True):
                    _ep = valuation.classify_playbook(_f)
                    _s = scoring.score_stock(_f, None, preset=_ep)
                    _v = valuation.fair_value(_f, None, _ep)
                    _ok, _verd, _miss, _ev = scorecard_ok(p["ticker"], _f, _s, _v)
                    # deutlich durchgefallen = mehr als 1 Pflichtkriterium offen
                    _klar_raus = _ev and not _ok and len(_miss or []) >= 2
                    if _klar_raus:
                        exit_why = "Signal erloschen (Scorecard)"
                        print(f"[hedgefund] {p['ticker']} geschlossen: Scorecard "
                              f"\"{_verd}\" - offen: {_miss}")
            except Exception:
                pass
        if exit_why:
            cost = p["qty"] * p["entry_eur"]
            proceeds = cost * (1 + pl / 100)
            state["cash"] += proceeds
            state["trades"].insert(0, {
                "ts": now, "action": "close", "ticker": p["ticker"],
                "dir": (f'KO-{p["ko_dir"]}' if p.get("type") == "ko" else p["dir"]),
                "pl_pct": round(pl, 1),
                "gain_eur": round(proceeds - cost, 2),      # echter Euro-Gewinn/-Verlust
                "einsatz_eur": round(cost, 2),
                "why": exit_why})
            held.discard(p["ticker"])
            # Sperrfrist setzen, wenn wegen "Signal erloschen" geschlossen wurde -
            # damit derselbe Titel nicht im naechsten Lauf sofort zurueckgekauft
            # wird. Take-Profit/Stop-Loss/Knock-out lösen KEINE Sperre aus, das
            # sind gewollte Exits.
            if "erloschen" in exit_why:
                cooldown[p["ticker"]] = now + _COOLDOWN_TAGE * 86400
        else:
            p["last_eur"] = round(pe, 2)
            p["pl_pct"] = round(pl, 1) if pl is not None else None
            keep.append(p)
    state["positions"] = keep
    # 2) Entries (freie Slots)
    nl, ns = STRATS[state["strategy"]]
    if state["strategy"] == "core_ko":
        # Der Aktien-Kern und die KO-Calls greifen auf DIESELBE Long-Liste zu.
        # Ohne Reserve frisst der Kern alle Kandidaten -> es blieben nur Puts uebrig.
        # Daher: mindestens 2 Long-Kandidaten fuer KO-Calls freihalten.
        n_ko_calls_open = max(KO_N - 1 - len([p for p in state["positions"]
                                              if p.get("type") == "ko"
                                              and p["ko_dir"] == "call"]), 0)
        reserve = min(2, n_ko_calls_open) if longs_cand else 0
        nl = max(min(nl, len(longs_cand) - reserve), 2)
    for direction, n_max, cands in (("long", nl, longs_cand), ("short", ns, shorts_cand)):
        # WICHTIG: KO-Scheine haben zwar dir="long", sind aber KEINE Kern-Aktien.
        # Wurden sie mitgezaehlt, belegten sie die Aktien-Slots -> der Kern blieb
        # leer, obwohl gueltige Titel (z.B. NVDA) vorlagen.
        cur = [p for p in state["positions"]
               if p["dir"] == direction and p.get("type") != "ko"]
        if n_max <= 0:
            continue
        # Ziel: rund 80 % des Kapitals investieren, 20 % Cash-Reserve fuer neu
        # erkannte Chancen (dein Wunsch). Das Investitions-Budget wird auf die noch
        # FREIEN Slots verteilt - so werden auch bei wenigen Kandidaten (3 statt 8)
        # ~80 % angelegt, statt dass 70 % Bargeld liegen bleiben. Deckel bleibt
        # POS_CAP je Titel (Klumpenrisiko), Reserve bei core_ko fuer die KO-Scheine.
        INVEST_TARGET = 0.80
        ko_reserve = 0.0
        if state["strategy"] == "core_ko":
            n_open_ko = KO_N - len([p for p in state["positions"]
                                    if p.get("type") == "ko"])
            ko_reserve = max(n_open_ko, 0) * KO_EACH * state["start_capital"]
        free_slots = max(n_max - len(cur), 1)
        invest_budget = INVEST_TARGET * state["start_capital"] - ko_reserve
        # Budget je Titel = Investitionsziel / Anzahl tatsaechlich fuellbarer Titel
        # (nicht / freie Slots!). So werden auch bei wenigen Kandidaten ~80 % angelegt,
        # statt dass durch 8 geteilt wird und 70 % Cash liegen bleiben.
        # Deckel je Titel: normal POS_CAP (15 %); bei Knappheit bis max. 30 %
        # (darueber waere das Klumpenrisiko zu gross - dann bleibt bewusst Cash).
        n_fillable = min(len([t for t in cands
                              if t not in held and t not in cooldown]), free_slots)
        per_slot = invest_budget / max(n_fillable, 1)
        per_slot = min(per_slot, 0.30 * state["start_capital"])
        for t in cands:
            if len(cur) >= n_max or t in held or t in cooldown:
                continue
            pe, _ = _price_eur(t)
            if not pe:
                continue                       # naechsten Kandidaten versuchen
            # nie unter die 20 %-Reserve gehen
            reserve_floor = (1 - INVEST_TARGET) * state["start_capital"] + ko_reserve
            avail = state["cash"] - reserve_floor
            budget = min(per_slot, max(avail, 0))
            qty = int(budget / pe)
            if qty < 1 or budget < 50:
                continue                       # zu teuer/zu wenig Cash -> naechster Titel
            state["cash"] -= qty * pe
            pos = {"ticker": t, "dir": direction, "entry_eur": round(pe, 2),
                   "qty": qty, "opened": now, "last_eur": round(pe, 2), "pl_pct": 0.0,
                   "peak_pl": 0.0, "trail_stop": None}
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
        _put_pool = list(shorts_cand) + [t for t in (put_cand or [])
                                         if t not in shorts_cand]
        puts = [t for t in _put_pool if t not in core_t and t not in ko_t]
        # Ausgewogene Mischung: immer die Richtung mit dem kleineren Bestand zuerst.
        # Bei 3 freien Slots ergibt das 2 Calls + 1 Put (statt "was uebrig bleibt").
        n_free = max(KO_N - len(kos), 0)
        cnt = {"call": sum(1 for p in kos if p["ko_dir"] == "call"),
               "put": sum(1 for p in kos if p["ko_dir"] == "put")}
        pool = {"call": calls, "put": puts}
        plan = []
        for _ in range(n_free):
            order = sorted(("call", "put"),
                           key=lambda d: cnt[d] + sum(1 for x, _ in plan if x == d))
            pick = next((d for d in order if pool[d]), None)
            if pick is None:
                break                                # kein Kandidat mehr verfuegbar
            plan.append((pick, pool[pick].pop(0)))
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
                   "last_eur": round(pe, 2), "pl_pct": 0.0,
                   "peak_pl": 0.0, "trail_stop": None}
            state["positions"].append(pos)
            kos.append(pos)
            ko_t.add(t)
            state["trades"].insert(0, {"ts": now, "action": "open", "ticker": t,
                                       "dir": f"KO-{kd}", "pl_pct": None, "why": "Signal"})
    state["trades"] = state["trades"][:60]    # begrenzt: Aux-Speicher darf nicht platzen
    # 3) Gesamtwert
    val = state["cash"]
    for p in state["positions"]:
        pl = p.get("pl_pct") or 0
        val += p["qty"] * p["entry_eur"] * (1 + pl / 100)
    state["value_eur"] = round(val, 2)
    state["last_check"] = now
    return state


def refresh_prices():
    """NUR Kurse neu bewerten - es wird NICHTS gekauft oder verkauft.

    Bewusst getrennt von rebalance(): Take-Profit, Stop-Loss, Gewinn-Stop und die
    Slot-Nachbesetzung bleiben den offiziellen Pruefungen vorbehalten (2x taeglich
    bzw. "Jetzt pruefen & anpassen"). Hier siehst du nur, wo die Depots gerade
    stehen. Auch peak_pl/Gewinn-Stop werden NICHT veraendert - sonst wuerde ein
    kurzfristig hoher Zwischenkurs den Stop nachziehen, ohne dass die Regel-Logik
    ihn je gesehen haette."""
    hf = store.get_hf() or {}
    if not hf:
        return hf
    now = time.time()
    px_cache = {}
    for strat, s in hf.items():
        val = s.get("cash", 0.0)
        for p in s.get("positions", []):
            t = p["ticker"]
            if t not in px_cache:
                px_cache[t] = _price_eur(t)[0]
            pe = px_cache[t]
            if pe:
                pl = _pl_pct(p, pe)
                p["last_eur"] = round(pe, 2)
                p["pl_pct"] = round(pl, 1) if pl is not None else None
                if p.get("type") == "ko" and p.get("barrier_eur"):
                    hit = (pe <= p["barrier_eur"]) if p["ko_dir"] == "call" \
                        else (pe >= p["barrier_eur"])
                    p["barrier_hit"] = bool(hit)      # nur Anzeige - Schliessung
                    if hit:                            # macht die naechste Pruefung
                        p["pl_pct"] = -100.0
            val += p["qty"] * p["entry_eur"] * (1 + (p.get("pl_pct") or 0) / 100)
        s["value_eur"] = round(val, 2)
        s["last_price"] = now                          # getrennt von last_check!
        print(f"[hedgefund] {strat}: Wert {s['value_eur']:.0f} EUR (nur Kurse)")
    store.set_hf(hf)
    return hf


def fresh_state(strategy, grund=""):
    """Leeres Startdepot fuer eine Strategie (Papiergeld, keine Positionen).

    'grund' haelt fest, WARUM neu gestartet wurde. Ohne diesen Vermerk
    laesst sich eine Wertentwicklung spaeter nicht einordnen: Ein Depot,
    das vor zwei Wochen neu aufgesetzt wurde, ist mit einem seit Monaten
    laufenden schlicht nicht vergleichbar."""
    return {"strategy": strategy, "start_capital": START_CAPITAL,
            "cash": START_CAPITAL, "positions": [], "trades": [],
            "created": time.time(), "value_eur": START_CAPITAL,
            "last_check": None,
            "neustart_am": time.time(),
            "neustart_grund": grund or ""}


def reset(strategy, refill=True, scan_size=50, grund=""):
    """Ein Strategie-Depot komplett neu aufsetzen (alle Positionen verwerfen).
    refill=True baut direkt nach den aktuellen Regeln neu auf."""
    _SC_CACHE.clear()
    hf = store.get_hf() or {}
    st_ = fresh_state(strategy, grund)
    if refill:
        lc, sc, pc = candidates(scan_size)
        st_ = rebalance(st_, lc, sc, pc)
        st_["neustart_am"] = st_.get("neustart_am") or time.time()
        st_["neustart_grund"] = grund or ""
    hf[strategy] = st_
    store.set_hf(hf)
    return st_


def reset_all(refill=True, scan_size=60, grund=""):
    """ALLE Strategien gemeinsam neu aufsetzen.

    Sinnvoll, wenn sich die Datengrundlage geaendert hat - dann sind die
    bisherigen Ergebnisse nicht mehr mit den kuenftigen vergleichbar, weil
    sie unter anderen Voraussetzungen entstanden sind.

    Bewusst EIN gemeinsamer Kandidaten-Scan fuer alle Strategien: So starten
    sie am selben Tag aus derselben Auswahl, und ein spaeterer Vergleich
    misst die Regeln - nicht den Zufall unterschiedlicher Starttage."""
    _SC_CACHE.clear()
    hf = store.get_hf() or {}
    lc, sc, pc = ([], [], [])
    if refill:
        lc, sc, pc = candidates(scan_size)
        print(f"[hedgefund] Neustart: {len(lc)} Long-, {len(sc)} Short-, "
              f"{len(pc)} KO-Kandidaten.")
    jetzt = time.time()
    for strat in STRATS:
        st_ = fresh_state(strat, grund)
        st_["neustart_am"] = jetzt          # identischer Startzeitpunkt
        if refill:
            st_ = rebalance(st_, lc, sc, pc)
            st_["neustart_am"] = jetzt
            st_["neustart_grund"] = grund or ""
        hf[strat] = st_
        print(f"[hedgefund] {strat}: neu aufgesetzt, "
              f"{len(st_.get('positions') or [])} Positionen.")
    store.set_hf(hf)
    return hf


def run_all(scan_size=60):
    """Alle Strategie-Portfolios pruefen/anpassen (Cron-Einstieg, 2x taeglich)."""
    _SC_CACHE.clear()                     # Scorecard-Urteile je Lauf frisch holen
    hf = store.get_hf() or {}
    lc, sc, pc = candidates(scan_size)
    print(f"[hedgefund] Kandidaten: {len(lc)} Long, {len(sc)} Short, {len(pc)} KO-Put")
    for strat in STRATS:
        st_ = hf.get(strat) or fresh_state(strat)
        st_["strategy"] = strat
        hf[strat] = rebalance(st_, lc, sc, pc)
        print(f"[hedgefund] {strat}: Wert {hf[strat]['value_eur']:.0f} EUR, "
              f"{len(hf[strat]['positions'])} Positionen")
    store.set_hf(hf)
    return hf
