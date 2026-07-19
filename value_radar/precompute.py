"""
precompute.py — taeglicher Nacht-Job (ohne Streamlit lauffaehig).

Aufgabe:
  1) Fuer Portfolio-Titel + Watchlist die Kennzahlen berechnen (Composite,
     Fair Value, Upside, Quantum) - dieselbe Logik wie in der App.
  2) Einen bounded Screener- und Radar-Scan machen (Top-Ideen).
  3) Alles mit dem gestrigen Stand (Snapshot) vergleichen -> Aenderungen.
  4) Aenderungen als "Feed" ins Google Sheet schreiben (Startseite zeigt sie),
     Snapshot aktualisieren, und eine E-Mail-Zusammenfassung senden.

Start:  python precompute.py
Benoetigt Umgebungsvariablen (siehe AUTO_UPDATE_SETUP.md):
  GSHEET_ID, GCP_SERVICE_ACCOUNT, FINNHUB_API_KEY, FMP_API_KEY,
  SMTP_HOST/PORT/USER/PASS, EMAIL_TO.

Robust: Jede Sektion ist gekapselt - faellt eine aus, laufen die anderen weiter.
"""
from __future__ import annotations
import time
import datetime as dt

import providers
import scoring
import valuation
import store
import notify

try:
    import radar
except Exception:
    radar = None
try:
    import market_screener as ms
except Exception:
    ms = None

# ---- Schwellen fuer "meldenswerte" Aenderungen --------------------------------
COMP_DELTA = 5          # Composite-Aenderung ab X Punkten melden
UPSIDE_FLIP = True      # Vorzeichenwechsel des Upside melden
SCREENER_TOP = 15       # so viele Screener-Top-Ideen speichern
RADAR_TOP = 15
UNIVERSE_SIZE = 90      # bounded: schont FMP-Tageslimit & Laufzeit


def _berlin_now():
    try:
        from zoneinfo import ZoneInfo
        return dt.datetime.now(ZoneInfo("Europe/Berlin"))
    except Exception:
        return dt.datetime.now()


def score_ticker(t: str, deep: bool = True) -> dict | None:
    """Kennzahlen fuer einen Ticker - identische Logik wie in der App."""
    try:
        f = providers.get_fundamentals(t, deep=deep)
    except Exception:
        return None
    if not f or not f.get("price"):
        return None
    preset = valuation.classify_playbook(f)
    s = scoring.score_stock(f, None, preset=preset)
    comp = s.get("composite")
    v = valuation.fair_value(f, None, preset)
    # EXAKT dieselbe Upside-Logik wie in der App (display_upside):
    # Modell-Upside wenn nicht gekappt, sonst Analysten-Ziel als Rueckfall.
    up = v.get("upside_pct")
    if v.get("fair_value_capped"):
        if v.get("analyst_target") and f.get("price"):
            up = round((v["analyst_target"] / f["price"] - 1) * 100, 1)
        # sonst: gekappter Modellwert bleibt stehen (wie App)
    analyst = None
    if deep:
        try:
            analyst = providers.get_analyst_ratings(t)
        except Exception:
            analyst = None
    mom = (s.get("category_scores") or {}).get("momentum")
    q = scoring.quantum_score(comp, v, analyst, momentum=mom)
    return {
        "ticker": t,
        "name": (f.get("name") or "")[:40],
        "composite": round(comp) if comp is not None else None,
        "fair_value": round(v["fair_value"], 2) if v.get("fair_value") else None,
        "upside": round(up, 1) if up is not None else None,
        "quantum": q.get("score"),
        "entry": round(v["entry_price"], 2) if v.get("entry_price") else None,
        "price": round(f["price"], 2) if f.get("price") else None,
        "sector": f.get("sector"),
    }


def collect_portfolio_tickers() -> list:
    seen, out = set(), []
    try:
        for _name, rows in (store.load_all() or {}).items():
            for r in rows or []:
                t = str(r.get("ticker") or "").strip().upper()
                if t and t not in seen:
                    seen.add(t)
                    out.append(t)
    except Exception:
        pass
    return out


def scan_list(tickers, deep=True, label=""):
    res = {}
    for i, t in enumerate(tickers):
        r = score_ticker(t, deep=deep)
        if r:
            res[t] = r
        if (i + 1) % 10 == 0:
            print(f"  [{label}] {i+1}/{len(tickers)} ...")
    return res


_SUFFIX_PRIORITY = {
    "DE": 1, "F": 2, "MU": 3, "SG": 4, "BE": 5, "HM": 6, "HA": 7, "DU": 8,
    "VI": 9, "L": 10, "PA": 11, "AS": 12, "MI": 13, "SW": 14, "MC": 15,
    "XC": 60, "IL": 61,          # Zweitnotierungen verlieren immer
}


def _canon_base(t):
    """Basissymbol + Prioritaet, inkl. .XC-Zweitnotierungen (BHPL.XC = BHP.L)."""
    if "." not in t:
        return t, 0
    base, suf = t.split(".", 1)
    suf = suf.upper()
    pri = _SUFFIX_PRIORITY.get(suf, 50)
    if suf in ("XC", "IL") and len(base) > 2 and base.endswith("L"):
        base = base[:-1]
    return base, pri


def collapse_listings(tickers):
    """Doppelnotierungen auf eine reduzieren. Fehlte im Nachtlauf komplett -
    deshalb tauchten BHP.L und BHPL.XC beide im Screener auf."""
    out, pos = [], {}
    for t in tickers:
        base, pri = _canon_base(t)
        if base not in pos:
            pos[base] = len(out)
            out.append(t)
        else:
            _b, prev_pri = _canon_base(out[pos[base]])
            if pri < prev_pri:
                out[pos[base]] = t
    return out


def _rescore_deep(ranked, label=""):
    """Top-Kandidaten TIEF nachrechnen.

    Der Scan laeuft flach (deep=False), um Datenlimits zu schonen - das ist
    fuer die Rangfolge in Ordnung. Die GESPEICHERTEN Zahlen sollen aber
    dieselben sein, die die Einzelanalyse zeigt (die tief rechnet). Sonst
    steht im Screener +30 % und beim Aufruf der Aktie -19 %.
    Nur die Top-Treffer werden nachgerechnet - das sind wenige Abrufe."""
    out = []
    for r in ranked:
        t = r.get("ticker")
        if not t:
            continue
        try:
            d = score_ticker(t, deep=True)
        except Exception:
            d = None
        out.append(d or r)
    if out:
        print(f"  [{label}] {len(out)} Top-Treffer tief nachgerechnet.")
    return out


# Vollstaendige Scan-Ergebnisse (auch die aussortierten schwachen Titel).
# Noetig fuer die Kontrollgruppe der Trefferbilanz: ohne schlechte Setups
# laesst sich nicht pruefen, ob die Scorecard ueberhaupt TRENNT - oder ob
# einfach der ganze Markt gestiegen ist.
_LAST_SCAN = {}


def screener_scan() -> list:
    """Bounded Screener-Scan (shallow, um FMP-Limit zu schonen)."""
    if ms is None:
        return []
    try:
        usd = providers.get_fx_to_eur("USD") or 0.92
        tickers, _src = ms.get_universe(["us", "de", "fr", "gb", "nl"],
                                        (5e9) / usd, UNIVERSE_SIZE)
        tickers = collapse_listings(tickers)     # BHP.L + BHPL.XC -> nur eine
    except Exception:
        return []
    scored = scan_list(tickers, deep=False, label="Screener")
    _LAST_SCAN["Screener"] = scored
    ranked = sorted(
        [r for r in scored.values() if (r.get("composite") or 0) >= 55
         and (r.get("upside") or -999) >= 5],
        key=lambda r: (r.get("composite") or 0) + min((r.get("upside") or 0) * 0.3, 15),
        reverse=True)
    # Top-Treffer tief nachrechnen -> gespeicherte Upside = Einzelanalyse-Upside
    top = _rescore_deep(ranked[:SCREENER_TOP], "Screener")
    # nach dem Nachrechnen neu sortieren, die Zahlen koennen sich geaendert haben
    return sorted(top, key=lambda r: (r.get("composite") or 0)
                  + min((r.get("upside") or 0) * 0.3, 15), reverse=True)


def worst_candidates(n=10):
    """Die SCHWAECHSTEN Titel aus den letzten Scans - Kontrollgruppe.

    Erfasst werden Titel mit niedrigem Score ODER negativem Upside
    (also teuer bewertet). Wenn die Scorecard etwas taugt, muessen diese
    im Schnitt SCHLECHTER laufen als die Treffer. Tun sie das nicht,
    trennt das Modell nicht - eine Erkenntnis, die man nur mit
    Gegenprobe gewinnen kann."""
    pool = {}
    for label, scored in _LAST_SCAN.items():
        for tk, r in (scored or {}).items():
            comp, up = r.get("composite"), r.get("upside")
            if comp is None:
                continue
            # schwaches Setup: niedriger Score oder deutlich ueberbewertet
            if comp < 45 or (up is not None and up < -10):
                cur = pool.get(tk)
                rank = comp + min((up or 0) * 0.3, 15)
                if cur is None or rank < cur[0]:
                    pool[tk] = (rank, r)
    worst = sorted(pool.items(), key=lambda kv: kv[1][0])[:n]
    return [dict(r, ticker=tk) for tk, (_rank, r) in worst]


def radar_scan() -> list:
    """Bounded Radar-Scan ueber die kuratierten Themen-Ticker (shallow)."""
    if radar is None:
        return []
    tickers, seen = [], set()
    for _theme, lst in getattr(radar, "THEMES", {}).items():
        for t in lst:
            if t not in seen:
                seen.add(t)
                tickers.append(t)
    tickers = collapse_listings(tickers)
    scored = scan_list(tickers, deep=False, label="Radar")
    _LAST_SCAN["Radar"] = scored
    ranked = sorted(
        [r for r in scored.values() if (r.get("composite") or 0) >= 55],
        key=lambda r: (r.get("composite") or 0) + min((r.get("upside") or 0) * 0.3, 15),
        reverse=True)
    top = _rescore_deep(ranked[:RADAR_TOP], "Radar")
    return sorted(top, key=lambda r: (r.get("composite") or 0)
                  + min((r.get("upside") or 0) * 0.3, 15), reverse=True)


def _eur(x):
    try:
        return f"{x:,.2f}\u20ac".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "\u2014"


def diff_changes(old_snap, new_rows, section):
    """Vergleicht neue Werte je Ticker mit dem alten Snapshot -> Aenderungen."""
    changes = []
    for t, r in new_rows.items():
        o = old_snap.get(t)
        nc, up = r.get("composite"), r.get("upside")
        entry, price = r.get("entry"), r.get("price")
        # Neue Kaufzone erreicht (Kurs <= Einstieg)
        if entry and price and price <= entry:
            was_in = o and o.get("price") and o.get("entry") and o["price"] <= o["entry"]
            if not was_in:
                changes.append({"ticker": t, "name": r.get("name"), "section": section,
                                "kind": "buyzone",
                                "text": f"{t} in Kaufzone: Kurs {_eur(price)} \u2264 "
                                        f"Einstieg {_eur(entry)}"})
        if o is None:
            continue
        oc = o.get("composite")
        if nc is not None and oc is not None and abs(nc - oc) >= COMP_DELTA:
            arrow = "\u2197" if nc > oc else "\u2198"
            changes.append({"ticker": t, "name": r.get("name"), "section": section,
                            "kind": "composite",
                            "text": f"{t} Composite {arrow} {oc}\u2192{nc}"})
        ou = o.get("upside")
        if UPSIDE_FLIP and up is not None and ou is not None and (up >= 0) != (ou >= 0):
            changes.append({"ticker": t, "name": r.get("name"), "section": section,
                            "kind": "upside_flip",
                            "text": f"{t} Upside dreht {ou:+.0f}%\u2192{up:+.0f}%"})
    return changes


def diff_newcomers(old_list_tickers, new_rows, section):
    """Neu in Screener/Radar-Top aufgetaucht."""
    out = []
    old = set(old_list_tickers or [])
    for r in new_rows:
        if r["ticker"] not in old:
            out.append({"ticker": r["ticker"], "name": r.get("name"), "section": section,
                        "kind": "new_idea",
                        "text": f"Neu in {section}-Top: {r['ticker']} "
                                f"(Score {r.get('composite')}, Upside "
                                f"{('%+d%%' % r['upside']) if r.get('upside') is not None else 'n/a'})"})
    return out


def run():
    started = _berlin_now()
    print(f"=== precompute Start {started:%d.%m.%Y %H:%M} (dt. Zeit) ===")
    if store.backend() != "sheet":
        print("WARNUNG: Google Sheets nicht aktiv - Ergebnisse landen nur lokal "
              "und werden von der Cloud-App nicht gelesen.")
        # Praezise Ursache benennen, damit die richtigen Secrets gesetzt werden.
        import os as _os
        _id = _os.getenv("GSHEET_ID")
        _raw = _os.getenv("GCP_SERVICE_ACCOUNT")
        print(f"  - GSHEET_ID gesetzt: {'JA' if _id else 'NEIN (Secret fehlt!)'}")
        if not _raw:
            print("  - GCP_SERVICE_ACCOUNT gesetzt: NEIN (Secret fehlt!)")
        else:
            print(f"  - GCP_SERVICE_ACCOUNT gesetzt: JA ({len(_raw)} Zeichen)")
            try:
                import json as _j
                _d = _j.loads(_raw)
                _mail = _d.get("client_email", "?")
                print(f"    -> gueltiges JSON, Service-Account: {_mail}")
                print(f"    -> Dieses Konto MUSS als Editor fuers Sheet freigegeben sein.")
            except Exception as _e:
                print(f"    -> JSON NICHT lesbar: {_e}")
                print("    -> Das Secret muss der KOMPLETTE JSON-Inhalt sein "
                      "(inkl. geschweifter Klammern), nicht der Dateipfad.")
        print("  Anleitung: GOOGLE_SHEETS_SETUP.md")

    old = store.get_snapshot() or {}
    old_snaps = old if isinstance(old, dict) else {}
    prev_scr = old_snaps.get("_screener_top", [])
    prev_rad = old_snaps.get("_radar_top", [])

    # 1) Portfolio + Watchlist (deep)
    pf_tickers = collect_portfolio_tickers()
    wl_tickers = [t for t in store.get_watchlist() if t not in pf_tickers]
    print(f"Portfolio-Titel: {len(pf_tickers)} | Watchlist: {len(wl_tickers)}")
    holdings = scan_list(pf_tickers, deep=True, label="Portfolio")
    watch = scan_list(wl_tickers, deep=True, label="Watchlist")

    # 2) Screener + Radar (bounded, shallow)
    print("Screener-Scan ...")
    scr = screener_scan()
    print("Radar-Scan ...")
    rad = radar_scan()

    # 3) Aenderungen bestimmen
    changes = []
    changes += diff_changes(old_snaps, holdings, "Portfolio")
    changes += diff_changes(old_snaps, watch, "Watchlist")
    changes += diff_newcomers(prev_scr, scr, "Screener")
    changes += diff_newcomers(prev_rad, rad, "Radar")

    ts = time.time()
    for c in changes:
        c["ts"] = ts

    # 4) Snapshot fuer den naechsten Vergleich bauen
    new_snap = {}
    new_snap.update(holdings)
    new_snap.update(watch)
    new_snap["_screener_top"] = [r["ticker"] for r in scr]
    new_snap["_radar_top"] = [r["ticker"] for r in rad]
    new_snap["_screener_rows"] = scr
    new_snap["_radar_rows"] = rad
    store.set_snapshot(new_snap)

    # 5) Aenderungs-Feed fortschreiben (neueste zuerst, gekappt)
    feed = changes + (store.get_changes() or [])
    store.set_changes(feed[:60])
    print(f"{len(changes)} neue Aenderung(en) erkannt.")

    # 5b) KI-Briefing (ein Claude-Aufruf; erklaert News + neue Screener/Radar-Titel).
    #     Defensiv: ohne Key / bei Fehler bleibt briefing = None.
    briefing_text = None
    try:
        import ai_briefing
        news_items = []
        try:
            import marketnews
            for sec in ("US-Markt", "Aktien-News"):
                news_items += marketnews.get_section(sec, limit=6)
        except Exception:
            news_items = []
        briefing_text = ai_briefing.generate(
            changes, news_items, holdings, watch, scr, rad)
        if briefing_text:
            store.set_briefing(briefing_text)
            print("[precompute] KI-Briefing erzeugt.")
    except Exception as e:
        print(f"[precompute] KI-Briefing uebersprungen: {e}")

    # 5c) Fortlaufende Hedgefonds-Papier-Portfolios pruefen/anpassen (2x taeglich)
    try:
        import hedgefund
        hedgefund.run_all()
    except Exception as e:
        print(f"[precompute] Hedgefonds-Update uebersprungen: {e}")

    # 5d) Signal-Tagebuch: heutige Screener-/Radar-Signale festhalten (Vorwaerts-Test).
    #     Ehrlich: JEDES Signal wird erfasst, auch die spaeteren Fehlschlaege.
    #     Zusaetzlich das SCORECARD-URTEIL mitschreiben - so laesst sich spaeter
    #     messen, ob 'Kaufkandidat' die 'Verwerfen'-Titel wirklich schlaegt.
    print(f"[trackrecord] Signal-Erfassung startet: {len(scr or [])} Screener-, "
          f"{len(rad or [])} Radar-Treffer vorhanden.")
    try:
        import trackrecord
        import scorecard as _sc
        import matrices as _mx

        def _analyse(t):
            """Urteil UND passende Screener-Strategie in EINEM Datenabruf.
            Die Strategien lagen bisher ungenutzt in screener_presets.py -
            der Nachtlauf filterte nur generisch nach Score und Upside.
            Jetzt wird festgehalten, WELCHE Vorlage ein Titel erfuellt."""
            out = {"verdict": "", "strategie": "", "radar_score": None,
                   "radar_firing": None}
            try:
                f = providers.get_fundamentals(t, deep=True)
                ep = valuation.classify_playbook(f)
                s = scoring.score_stock(f, None, preset=ep)
                v = valuation.fair_value(f, None, ep)
                hist = providers.get_price_history(t, period="1y", interval="1d")
                extras = providers.get_signal_extras(t)
                sig = _mx.build_signals(f, hist, None, extras)
                res = _sc.evaluate(f, v, s.get("composite"),
                                   _mx.auto_m1_total(sig), _mx.auto_m2_total(sig),
                                   extras, None, None)
                out["verdict"] = res.get("verdict", "")
                # Welche Screener-Vorlage passt? Bei mehreren: die mit der
                # besseren Soft-Quote. Keine Treffer -> "keine".
                try:
                    import screener_presets as _sp
                    best, best_q = "", -1.0
                    for key in _sp.PRESETS:
                        ev = _sp.evaluate(key, f, extras, v)
                        if ev.get("passed"):
                            tot = ev.get("soft_total") or 1
                            q = (ev.get("soft_pass") or 0) / tot
                            if q > best_q:
                                best, best_q = key, q
                    out["strategie"] = best or "keine"
                except Exception:
                    pass
                # ECHTER Radar-Score (radar.compute) - dieselbe Zahl, die der
                # Radar-Tab zeigt. Bisher wurde r.get("radar") gelesen, ein Feld
                # das score_ticker nie liefert -> der Score war immer leer.
                # Fundamentaldaten und Historie sind hier schon geladen, es
                # kommen nur die Event-Abrufe dazu.
                try:
                    import radar as _rd
                    try:
                        _ev8 = providers.get_recent_8k(t) or []
                    except Exception:
                        _ev8 = []
                    try:
                        _news = providers.get_event_news(f.get("name") or t) or []
                    except Exception:
                        _news = []
                    _heads = [h.get("headline", "") if isinstance(h, dict) else str(h)
                              for h in _news]
                    # EPS-Revisionen und Insider mitgeben, sonst bleiben zwei der
                    # vier Ebenen leer und der Score faellt systematisch zu
                    # niedrig aus (im Test 6 statt realistisch 40-60).
                    try:
                        _eps_rev = providers.get_eps_revision_light(t)
                    except Exception:
                        _eps_rev = None
                    try:
                        _ins = providers.get_insider_light(t)
                    except Exception:
                        _ins = None
                    _rr = _rd.compute(f, hist, _eps_rev, _ins, _ev8, _heads)
                    out["radar_score"] = _rr.get("score")
                    out["radar_firing"] = _rr.get("firing")
                except Exception:
                    pass
            except Exception:
                pass
            return out

        sig_new = []
        for r in (scr or [])[:10]:
            tk = r.get("ticker")
            if not tk:
                continue
            _a = _analyse(tk)
            sig_new.append({"ticker": tk, "quelle": "Screener",
                            "score": r.get("composite"), "upside": r.get("upside"),
                            "strategie": _a.get("strategie", ""),
                            "verdict": _a.get("verdict", ""), "price": r.get("price")})
        for r in (rad or [])[:10]:
            tk = r.get("ticker")
            if not tk:
                continue
            # BUG: r.get("radar") gibt es in score_ticker nicht -> Score war immer
            # None. Der Radar-Score ist "quantum" (Q-Score), Rueckfall composite.
            _a = _analyse(tk)
            sig_new.append({"ticker": tk, "quelle": "Radar",
                            "score": (_a.get("radar_score")
                                      if _a.get("radar_score") is not None
                                      else (r.get("quantum")
                                            if r.get("quantum") is not None
                                            else r.get("composite"))),
                            "firing": _a.get("radar_firing"),
                            "upside": r.get("upside"),
                            "strategie": _a.get("strategie", ""),
                            "verdict": _a.get("verdict", ""), "price": r.get("price")})

        # KONTROLLGRUPPE: die schwaechsten Titel aus denselben Scans.
        # Ohne sie kann man nicht unterscheiden, ob die Scorecard trennt
        # oder ob einfach der gesamte Markt gestiegen ist.
        try:
            weak = worst_candidates(10)
            for r in weak:
                tk = r.get("ticker")
                if not tk:
                    continue
                # Merkmal festhalten: WARUM gilt der Titel als schwach?
                # Ohne diese Angabe weiss man spaeter nicht, ob die Kontroll-
                # gruppe wegen schlechter Qualitaet oder wegen Ueberbewertung
                # verloren hat - zwei voellig verschiedene Aussagen.
                _c, _u = r.get("composite"), r.get("upside")
                if _c is not None and _c < 45 and _u is not None and _u < -10:
                    _merkmal = "Score niedrig + \u00fcberbewertet"
                elif _c is not None and _c < 45:
                    _merkmal = f"Score niedrig ({_c})"
                elif _u is not None and _u < -10:
                    _merkmal = f"\u00fcberbewertet ({_u:+.0f} %)"
                else:
                    _merkmal = "schwaches Setup"
                _a = _analyse(tk)
                sig_new.append({"ticker": tk, "quelle": "Negativ",
                                "score": r.get("composite"),
                                "upside": r.get("upside"),
                                "merkmal": _merkmal,
                                "strategie": _a.get("strategie", ""),
                                "verdict": _a.get("verdict", ""), "price": r.get("price")})
            print(f"[trackrecord] Kontrollgruppe: {len(weak)} schwache Setups "
                  f"zur Gegenprobe erfasst.")
        except Exception as e:
            print(f"[trackrecord] Kontrollgruppe uebersprungen: {e}")

        if not sig_new:
            print("[trackrecord] WARNUNG: keine Kandidaten aus Screener/Radar - "
                  "es gibt nichts zu erfassen. Laufen die Scans durch?")
        added = trackrecord.record(sig_new)
        # Kontrolle: hat der Speicher die Signale wirklich aufgenommen?
        try:
            total = len(store.get_signals() or [])
            print(f"[trackrecord] {added} neu, {total} im Speicher. "
                  f"Backend={store.backend()}.")
            if store.backend() != "sheet":
                print("[trackrecord] WARNUNG: Backend ist NICHT 'sheet' - die Cloud-App "
                      "liest aus dem Sheet und sieht diese Signale daher nicht!")
        except Exception as _e:
            print(f"[trackrecord] Kontrolle fehlgeschlagen: {_e}")
    except Exception as e:
        import traceback
        print(f"[precompute] Signal-Tagebuch FEHLER: {e}")
        traceback.print_exc()

    # 6) E-Mail
    _send_email(changes, holdings, watch, scr, rad, started, briefing_text)
    print("=== precompute fertig ===")


def _send_email(changes, holdings, watch, scr, rad, started, briefing_text=None):
    subj = (f"Value Radar \u2013 {len(changes)} \u00c4nderung(en) "
            f"({started:%d.%m.%Y})")
    if not changes:
        subj = f"Value Radar \u2013 keine wesentlichen \u00c4nderungen ({started:%d.%m.%Y})"

    def _rows_html(title, rows):
        if not rows:
            return ""
        body = "".join(
            f"<tr><td><b>{c['ticker']}</b></td><td>{c.get('name','')}</td>"
            f"<td>{c.get('composite','')}</td>"
            f"<td>{('%+d%%' % c['upside']) if c.get('upside') is not None else '\u2014'}</td>"
            f"<td>{c.get('quantum','')}</td></tr>"
            for c in rows)
        return (f"<h3>{title}</h3><table border='0' cellpadding='6' "
                "style='border-collapse:collapse'>"
                "<tr style='color:#888'><th align='left'>Ticker</th>"
                "<th align='left'>Name</th><th>Comp</th><th>Upside</th>"
                "<th>Quantum</th></tr>" + body + "</table>")

    ch_html = "<p><i>Heute keine meldenswerten \u00c4nderungen.</i></p>"
    if changes:
        by = {}
        for c in changes:
            by.setdefault(c["section"], []).append(c)
        ch_html = ""
        for sec, lst in by.items():
            ch_html += f"<h3>\u0394 {sec}</h3><ul>" + "".join(
                f"<li>{c['text']}</li>" for c in lst) + "</ul>"

    briefing_html = ""
    if briefing_text:
        _safe = (briefing_text.replace("&", "&amp;").replace("<", "&lt;")
                 .replace(">", "&gt;").replace("\n", "<br>"))
        briefing_html = (
            "<div style='background:#f6f8fa;border-left:4px solid #FFB000;"
            "padding:12px 16px;margin:8px 0;border-radius:4px'>"
            "<h3 style='margin:0 0 8px 0'>\U0001f9e0 KI-Briefing (Claude)</h3>"
            f"<div style='font-size:14px;line-height:1.5'>{_safe}</div></div>")

    html = (
        f"<div style='font-family:Arial,sans-serif;color:#111'>"
        f"<h2>Value Radar \u2013 T\u00e4gliches Update</h2>"
        f"<p style='color:#666'>Stand {started:%d.%m.%Y %H:%M} (dt. Zeit)</p>"
        f"{briefing_html}"
        f"{ch_html}"
        f"{_rows_html('Portfolio', list(holdings.values()))}"
        f"{_rows_html('Watchlist', list(watch.values()))}"
        f"{_rows_html('Screener \u2013 Top-Ideen', scr)}"
        f"{_rows_html('Radar \u2013 Top-Ideen', rad)}"
        f"<p style='color:#999;font-size:12px;margin-top:20px'>"
        f"Automatischer Report \u00b7 kein Anlagerat \u00b7 Werte sind Modellsch\u00e4tzungen."
        f"</p></div>")
    text = "Value Radar Update. \u00c4nderungen:\n" + "\n".join(
        f"- [{c['section']}] {c['text']}" for c in changes) if changes else \
        "Value Radar: keine wesentlichen \u00c4nderungen."
    notify.send_email(subj, html, text)


if __name__ == "__main__":
    run()
