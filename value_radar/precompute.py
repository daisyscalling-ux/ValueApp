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

VERSION-Kennung: wird bei jedem Lauf ausgegeben und mit jedem Signal
gespeichert. Damit laesst sich sofort sehen, ob auf GitHub wirklich die
aktuelle Datei liegt - der haeufigste Grund fuer "die neue Spalte bleibt leer".
Benoetigt Umgebungsvariablen (siehe AUTO_UPDATE_SETUP.md):
  GSHEET_ID, GCP_SERVICE_ACCOUNT, FINNHUB_API_KEY, FMP_API_KEY,
  SMTP_HOST/PORT/USER/PASS, EMAIL_TO.

Robust: Jede Sektion ist gekapselt - faellt eine aus, laufen die anderen weiter.
"""
from __future__ import annotations

# Bei jeder inhaltlichen Aenderung hochzaehlen. Wird im Lauf-Log ausgegeben
# und mit jedem Signal gespeichert -> man sieht, welcher Code ein Signal
# erzeugt hat.
CODE_VERSION = "2026-07-29-av"   # bei jeder Aenderung hochzaehlen

# Analysten-Historie fuer die Value-Trap-Trenderkennung. In run() aus dem
# Speicher geladen, waehrend des Laufs von score_ticker fortgeschrieben, am
# Ende zurueckgespeichert. _SEEN verhindert Mehrfach-Fortschreibung pro Lauf.
_ANALYST_HIST = {}
_ANALYST_SEEN = set()

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
RADAR_DELTA = 8         # Radar-Score-Sprung ab X Punkten melden
UPSIDE_DELTA = 8        # Upside-Sprung ab X Prozentpunkten melden
# ---------------------------------------------------------------------------
# Skalierung: Mit roic.ai (300 Abrufe/min statt FMP 250/Tag) darf der Lauf
# deutlich breiter und tiefer werden. OHNE Schluessel bleiben die alten,
# engen Grenzen - sonst laeuft der Job in dieselben Quoten wie bisher.
# ---------------------------------------------------------------------------
try:
    import roic as _roic_mod
    _ROIC_AKTIV = _roic_mod.enabled()
except Exception:
    _roic_mod, _ROIC_AKTIV = None, False

if _ROIC_AKTIV:
    SCREENER_TOP = 30       # mehr Top-Ideen speichern
    RADAR_TOP = 30
    # Wie viele Kandidaten die Signal-Erfassung pruefen darf (Kaufzone). Die
    # Raenge 31-100 kommen mit flachen Scan-Werten (entry/price vorhanden), nur
    # die Top 30 werden teuer tief nachgerechnet. So werden auch guenstige
    # Titel mit mittlerem Score (z.B. Morgan Stanley, Composite 60, Rang ~40)
    # als Kaufkandidat erfasst, ohne 100 Tiefabrufe je Scan.
    SIGNAL_KANDIDATEN = 100
    # Mit der Sparfassung (3 Abrufe je Titel in der Vorauswahl) kostet ein
    # 600er-Universum rund 7,5 Minuten statt 20. Das ist der eigentliche
    # Gewinn der bezahlten Anbindung: Breite statt Rationierung.
    UNIVERSE_SIZE = 600
    # Vorauswahl bewusst FLACH (Sparfassung, 3 Abrufe je Titel). Die
    # gespeicherten Zahlen bleiben trotzdem deckungsgleich mit der
    # Einzelanalyse, weil _rescore_deep die Top-Titel ohnehin tief
    # nachrechnet. Alles tief zu scannen kostete 8 Abrufe je Titel und
    # damit bei 600 Titeln 20 Minuten - fuer Raenge, die sich dadurch
    # kaum verschieben.
    SCAN_DEEP = False
    EARNINGS_DEEP_LIMIT = 150
    RADAR_MARKT = 250       # Marktschnitt zusaetzlich zu den Themen-Tickern
    MOM_UNIVERSE_SIZE = 400 # Momentum: breites Feld, damit relative Staerke traegt
    MOM_TOP = 25            # so viele Momentum-Titel als Signale erfassen
    print(f"[roic] aktiv - Universum {UNIVERSE_SIZE}, "
          f"Top {SCREENER_TOP} tief nachgerechnet.")
else:
    SCREENER_TOP = 15       # so viele Screener-Top-Ideen speichern
    RADAR_TOP = 15
    SIGNAL_KANDIDATEN = 40  # ohne roic engeres Feld (API-Limits)
    UNIVERSE_SIZE = 90      # bounded: schont FMP-Tageslimit & Laufzeit
    SCAN_DEEP = False
    EARNINGS_DEEP_LIMIT = 60
    RADAR_MARKT = 0         # ohne roic kein Marktschnitt - Limits zu eng
    MOM_UNIVERSE_SIZE = 90
    MOM_TOP = 15


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
    # Analysten-Schaetzungen mitschneiden (nur bei deep, nur 1x pro Titel/Lauf).
    # Daraus entsteht ueber Wochen der Trend, der fallende Kursziele als
    # Value-Trap-Signal erkennt. _ANALYST_HIST wird in run() geladen+gespeichert.
    if deep and f.get("target_mean") and t not in _ANALYST_SEEN:
        try:
            _tr = scoring.analyst_trend_update(
                _ANALYST_HIST, t, f.get("target_mean"),
                f.get("eps_forward"), f.get("analyst_count"))
            f["_analyst_trend"] = _tr
            _ANALYST_SEEN.add(t)
        except Exception:
            pass
    elif _ANALYST_HIST.get(t):
        # schon in diesem Lauf erfasst ODER kein Ziel: vorhandenen Trend nutzen
        try:
            _reihe = _ANALYST_HIST.get(t) or []
            if len(_reihe) >= 2:
                _alt, _neu = _reihe[0]["target_mean"], _reihe[-1]["target_mean"]
                if _alt and _alt > 0:
                    _d = (_neu / _alt - 1) * 100
                    f["_analyst_trend"] = {
                        "richtung": ("fallend" if _d <= -5 else
                                     "steigend" if _d >= 5 else "stabil"),
                        "target_delta_pct": round(_d, 1), "punkte": len(_reihe)}
        except Exception:
            pass
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
    # Analysten-Skepsis: liegt das Analysten-Kursziel unter unserem Fair Value?
    # (negativ = Analysten vorsichtiger als unsere Rechnung). Kostet nichts,
    # die Werte stehen schon in v/f.
    _askep = None
    _atgt, _fv = v.get("analyst_target"), v.get("fair_value")
    if _atgt and _fv and _fv > 0:
        _askep = (_atgt / _fv - 1) * 100
    # Analysten-Trend (fallende Kursziele) wird vom Aufrufer reingereicht, weil
    # er die persistente Historie verwaltet.
    _atrend = f.get("_analyst_trend")
    q = scoring.quantum_score(comp, v, analyst, momentum=mom,
                              analyst_skepsis=_askep, analyst_trend=_atrend)
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
        # --- Zusatzfelder fuer Strategie-Filter (kosten keine Extra-Abrufe,
        #     stehen alle schon in f bzw. s)
        "vs_52w_high": (round((f["price"] / f["52w_high"] - 1) * 100, 1)
                        if f.get("52w_high") and f.get("price") else None),
        "vs_52w_low": (round((f["price"] / f["52w_low"] - 1) * 100, 1)
                       if f.get("52w_low") and f.get("price") else None),
        "momentum": (s.get("category_scores") or {}).get("momentum"),
        "quality": (s.get("category_scores") or {}).get("quality"),
        "value": (s.get("category_scores") or {}).get("value"),
        "growth": (s.get("category_scores") or {}).get("growth"),
        "catalyst": (s.get("category_scores") or {}).get("catalyst"),
        "cat_neutral": s.get("cat_neutral") or {},
        "analyst_count": f.get("analyst_count"),
        "value_trap": s.get("value_trap"),
        # Value-Trap-Warnungen aus dem Quantum Score (fuer das Symbol in Listen)
        "vt_warnung": q.get("value_trap_warnung") or [],
        "revenue_growth": (round(f["revenue_growth"] * 100, 1)
                           if f.get("revenue_growth") is not None else None),
        # --- Schmidlins "ergiebige Wertpaare" fuer die Vorauswahl (alle schon
        #     in f vorhanden, keine Extra-Abrufe): KGV+Wachstum, KBV+EKR,
        #     EV/EBITDA+Marge. Damit lassen sich guenstige Titel MIT soliden
        #     Fundamentaldaten in einem Schritt finden.
        "pe": (round(f["price"] / f["eps_trailing"], 1)
               if f.get("eps_trailing") and f.get("eps_trailing") > 0
               and f.get("price") else None),
        "pb": (round(f["price"] / f["book_value_ps"], 2)
               if f.get("book_value_ps") and f.get("book_value_ps") > 0
               and f.get("price") else None),
        "ev_ebitda": (round(f["ev_ebitda"], 1)
                      if f.get("ev_ebitda") is not None else None),
        "roe": (round(f["roe"] * 100, 1) if f.get("roe") is not None else None),
        "ebitda_margin": (round(f["ebitda"] / f["revenue"] * 100, 1)
                          if f.get("ebitda") and f.get("revenue")
                          and f.get("revenue") > 0 else None),
        "gross_margin": (round(f["gross_margin"] * 100, 1)
                         if f.get("gross_margin") is not None else None),
        "net_debt_ebitda": f.get("net_debt_ebitda"),
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


# ---------------------------------------------------------------------------
# ISIN-BASIERTE ENTDOPPLUNG - die eigentliche Loesung
# ---------------------------------------------------------------------------
# APC.DE, 0R2V.L und AAPL sind DIESELBE Firma (Apple), tragen aber voellig
# verschiedene Symbole - collapse_listings (Basissymbol) und die Namens-
# Entdopplung greifen da nicht zuverlaessig. Der stabile Schluessel ist die
# ISIN: Alle drei haben US0378331005. Ihr Laendercode (US) sagt zugleich,
# wo die HEIMATBOERSE liegt.
#
# Regel: Bei mehreren Notierungen derselben ISIN gewinnt die, deren Boerse
# zum ISIN-Land passt (US-ISIN -> US-Notierung ohne Suffix = AAPL). Fehlt
# die Heimatnotierung, bleibt die am besten passende - aber Auslands-
# Zweitnotierungen verschwinden.
# ---------------------------------------------------------------------------

# Boersensuffix -> Land, um "passt zur ISIN" zu pruefen.
_SUFFIX_LAND = {
    "": "US", "DE": "DE", "F": "DE", "MU": "DE", "BE": "DE", "SG": "DE",
    "DU": "DE", "HM": "DE", "HA": "DE", "STU": "DE",
    "L": "GB", "IL": "GB", "PA": "FR", "AS": "NL", "BR": "BE",
    "MI": "IT", "MC": "ES", "SW": "CH", "VX": "CH", "ST": "SE",
    "HE": "FI", "OL": "NO", "CO": "DK", "VI": "AT", "LS": "PT",
    "TO": "CA", "T": "JP", "HK": "HK", "AX": "AU",
}


def _ticker_land(t: str) -> str:
    """Land der Boerse aus dem Ticker-Suffix (leeres Suffix = US)."""
    if "." not in t:
        return "US"
    return _SUFFIX_LAND.get(t.rsplit(".", 1)[-1].upper(), "?")


def _isin_land(isin) -> str:
    """Die ersten zwei Buchstaben der ISIN sind das Emittentenland."""
    if not isin or len(str(isin)) < 2:
        return ""
    return str(isin)[:2].upper()


def entdopple_nach_isin(rows):
    """rows: Liste von dicts mit 'ticker' und moeglichst 'isin'.

    Reduziert je Firma auf die Heimatnotierung - ZWEISTUFIG:
      1) ueber die ISIN (stabilster Schluessel)
      2) fuer Titel OHNE ISIN zusaetzlich ueber den Firmennamen

    Der zweite Schritt ist noetig, weil roic Auslands-Zweitnotierungen wie
    0R2V.L (London IOB) oder APC8.F (Frankfurt) oft nicht abdeckt - dann
    fehlt die ISIN, und ohne Namens-Rueckfall bliebe Apple dreifach stehen.
    Beide Stufen bevorzugen die Heimatboerse.
    """
    # Reihenfolge merken, um am Ende die Original-Ordnung zu halten
    reihenfolge = {}
    for i, r in enumerate(rows):
        reihenfolge.setdefault(r.get("ticker"), i)

    def _heimat_rang(r, land):
        t = r.get("ticker") or ""
        passt = _ticker_land(t) == land if land else False
        kein_suffix = "." not in t
        luecken = sum(1 for k in ("composite", "score", "price", "upside")
                      if r.get(k) is None)
        return (0 if passt else 1, 0 if kein_suffix else 1, luecken)

    # --- Stufe 1: nach ISIN
    gruppen, ohne_isin = {}, []
    for r in rows:
        isin = r.get("isin")
        if isin:
            gruppen.setdefault(str(isin).upper(), []).append(r)
        else:
            ohne_isin.append(r)

    behalten = []
    for isin, gruppe in gruppen.items():
        land = _isin_land(isin)
        gruppe.sort(key=lambda r: _heimat_rang(r, land))
        behalten.append(gruppe[0])

    # --- Stufe 2: die ISIN-losen zusaetzlich nach Firmenname buendeln
    # (und dabei auch gegen bereits behaltene Titel desselben Namens pruefen,
    #  damit 0R2V.L nicht neben AAPL ueberlebt).
    name_index = {}                       # norm_name -> Index in behalten
    for i, r in enumerate(behalten):
        nm = _norm_name(r.get("name"))
        if nm:
            name_index[nm] = i

    for r in ohne_isin:
        nm = _norm_name(r.get("name"))
        if not nm:                        # ohne Name nicht raten -> behalten
            behalten.append(r)
            continue
        if nm in name_index:
            # Es gibt schon eine Notierung dieser Firma - die mit dem
            # besseren Heimat-Rang gewinnt (meist die mit ISIN = Heimat).
            j = name_index[nm]
            best = min(behalten[j], r,
                       key=lambda x: _heimat_rang(x, _isin_land(x.get("isin"))
                                                  or _ticker_land(x.get("ticker") or "")))
            behalten[j] = best
        else:
            name_index[nm] = len(behalten)
            behalten.append(r)

    # --- Stufe 3: Aktiengattungen derselben Firma auf EINE reduzieren.
    # GOOG/GOOGL (Alphabet) oder BP-A.L/BP-B.L haben VERSCHIEDENE ISINs -
    # es sind rechtlich verschiedene Papiere, aber dieselbe Firma. Fuer die
    # Anzeige soll nur eine Gattung erscheinen. Gewaehlt wird die "Haupt-
    # gattung": kuerzester/suffixloser Basisticker, bei Gleichstand der mit
    # den wenigsten Datenluecken. Das fasst A/B/C-Klassen zusammen, ohne
    # verschiedene FIRMEN zu vermengen (der Name muss exakt passen).
    def _gattungs_rang(r):
        t = (r.get("ticker") or "").upper()
        base = t.split(".")[0]
        # "-A"/"-B"-Klassen sind meist Nebengattungen -> nachrangig.
        hat_klasse = "-" in base
        # Sonderfall Alphabet: GOOGL (Klasse A, MIT Stimmrecht) ist die
        # Hauptgattung, nicht das kuerzere GOOG (Klasse C, ohne Stimmrecht).
        ist_goog_c = (base == "GOOG")
        luecken = sum(1 for k in ("composite", "score", "price", "upside")
                      if r.get(k) is None)
        # kleiner = besser
        return (0 if not hat_klasse else 1,
                1 if ist_goog_c else 0,
                luecken, len(base), t)

    per_name = {}
    for r in behalten:
        nm = _norm_name(r.get("name"))
        if not nm:
            per_name.setdefault(id(r), []).append(r)   # namenlos: einzeln
            continue
        per_name.setdefault(nm, []).append(r)

    final = []
    for key, gruppe in per_name.items():
        if len(gruppe) == 1:
            final.append(gruppe[0])
        else:
            gruppe.sort(key=_gattungs_rang)
            final.append(gruppe[0])

    behalten = final
    behalten.sort(key=lambda r: reihenfolge.get(r.get("ticker"), 1e9))
    return behalten


def heimat_oder_none(ticker: str, isin) -> bool:
    """True, wenn 'ticker' eine AUSLANDS-Zweitnotierung ist (ISIN-Land passt
    nicht zum Boersen-Land). Fuer den Fall, dass die Heimatnotierung ohnehin
    im Universum steht und die Zweitnotierung raus kann."""
    land = _isin_land(isin)
    if not land:
        return False                     # ohne ISIN nichts entfernen
    return _ticker_land(ticker) != land


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


def _pessimismus(f, analyst):
    """Ist die Erwartungshaltung niedrig? (Stufe 1)

    Gesucht sind Titel, bei denen Analysten UND Gewinnerwartung negativ sind.
    Genau dort ist die Positionierung einseitig - eine positive Ueberraschung
    trifft auf niemanden, der schon investiert ist."""
    gruende = []
    a = analyst or {}
    buy, sell = a.get("buy"), a.get("sell")
    if buy is not None and sell is not None and (buy + sell) > 0 and sell >= buy:
        gruende.append("Analysten mehrheitlich negativ")
    px, tgt = f.get("price"), f.get("target_mean")
    if px and tgt and tgt < px * 0.98:
        gruende.append("Kursziel unter Kurs")
    epsf = f.get("eps_forward")
    if epsf is not None and epsf <= 0:
        gruende.append("Verlust erwartet")
    ni = f.get("net_income")
    if ni is not None and ni <= 0:
        gruende.append("zuletzt Verlust")
    return gruende


def _widerspruch(f, eps_rev, insider):
    """Spricht etwas GEGEN den Pessimismus? (Stufe 2)

    Der entscheidende Teil. Bei AMC waere hier aufgefallen: Nettoverlust,
    aber 190 Mio. freier Cashflow, steigender Umsatz und sich weitende
    Margen. Solche Widersprueche zwischen Buchgewinn und Zahlungsstrom
    sind das, was ein Screener finden kann."""
    treffer = []
    fcf, ni = f.get("free_cashflow"), f.get("net_income")
    if fcf and fcf > 0 and ni is not None and ni <= 0:
        treffer.append("Cashflow positiv trotz Verlust")
    rg = f.get("revenue_growth")
    if rg is not None and rg >= 0.05:
        treffer.append(f"Umsatz +{rg*100:.0f} %")
    om = f.get("operating_margin")
    if om is not None and om > 0:
        treffer.append("operativ profitabel")
    r = eps_rev or {}
    up, down = r.get("up"), r.get("down")
    if up is not None and down is not None and up > down:
        treffer.append("Schätzungen werden angehoben")
    ins = insider or {}
    if (ins.get("buys") or 0) > (ins.get("sells") or 0):
        treffer.append("Insider kaufen")
    return treffer


def contrarian_scan(max_treffer=10):
    """EXPERIMENTELL: niedrige Erwartungen + Hinweise, dass sie zu tief sind.

    Zweistufig: erst Titel mit negativer Erwartungshaltung finden, dann
    pruefen, ob harte Zahlen dem widersprechen. Es wird NICHT versucht,
    die Ueberraschung vorherzusagen - nur die Stellen zu finden, an denen
    eine Ueberraschung ueberhaupt Wirkung haette.

    Die Gruppe wird in der Trefferbilanz mitgemessen wie jede andere. Ob
    sie taugt, entscheidet die Auswertung nach Monaten - nicht die Idee."""
    pool = {}
    for _label, scored in _LAST_SCAN.items():
        for tk in (scored or {}):
            pool.setdefault(tk, None)
    if not pool:
        return []
    kandidaten = []
    for t in list(pool)[:120]:                 # Deckel gegen Abruf-Explosion
        try:
            f = providers.get_fundamentals(t, deep=False)
            if not f or not f.get("price"):
                continue
            try:
                analyst = providers.get_analyst_ratings(t)
            except Exception:
                analyst = None
            pess = _pessimismus(f, analyst)
            if len(pess) < 2:                  # Erwartung muss klar niedrig sein
                continue
            try:
                eps_rev = providers.get_eps_revision_light(t)
            except Exception:
                eps_rev = None
            try:
                ins = providers.get_insider_light(t)
            except Exception:
                ins = None
            wid = _widerspruch(f, eps_rev, ins)
            if len(wid) < 2:                   # mind. zwei Gegenbelege
                continue
            kandidaten.append({
                "ticker": t,
                "price": round(f["price"], 2),
                "pessimismus": "; ".join(pess[:2]),
                "widerspruch": "; ".join(wid[:3]),
                "n_wid": len(wid),
            })
        except Exception:
            continue
    kandidaten.sort(key=lambda r: -r["n_wid"])
    print(f"  [Contrarian] {len(kandidaten)} Kandidaten (experimentell).")
    return kandidaten[:max_treffer]


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
        tickers = filter_boersen(collapse_listings(ersetze_pence_durch_adr(tickers)))   # nur Heimatnotierungen
    except Exception:
        return []
    scored = scan_list(tickers, deep=SCAN_DEEP, label="Screener")
    scored = collapse_scored(scored, "Screener")   # Dubletten ueber den Namen
    _LAST_SCAN["Screener"] = scored
    ranked = sorted(
        [r for r in scored.values() if (r.get("composite") or 0) >= 55
         and (r.get("upside") or -999) >= 5],
        key=lambda r: (r.get("composite") or 0) + min((r.get("upside") or 0) * 0.3, 15),
        reverse=True)
    # Top-Treffer tief nachrechnen -> gespeicherte Upside = Einzelanalyse-Upside.
    # NUR die Top 30 werden tief nachgerechnet (teuer: 8 Abrufe je Titel). Die
    # Raenge 31-100 kommen mit ihren flachen Scan-Werten mit - die enthalten
    # bereits entry/price/vs_52w (score_ticker berechnet sie fuer jeden Titel),
    # also genug fuer die Kaufzonen-Pruefung der Signal-Erfassung. So sieht die
    # Signal-Erfassung bis zu 100 Kandidaten (z.B. Morgan Stanley auf Rang ~40),
    # ohne dass 100 teure Tiefabrufe den Nachtlauf sprengen.
    _deep = _rescore_deep(ranked[:SCREENER_TOP], "Screener")
    _deep_ticker = {r.get("ticker") for r in _deep}
    _flach_rest = [r for r in ranked[SCREENER_TOP:SIGNAL_KANDIDATEN]
                   if r.get("ticker") not in _deep_ticker]
    top = _deep + _flach_rest
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
    # Mit roic zusaetzlich einen Marktschnitt aufnehmen. Die 113 kuratierten
    # Themen-Ticker sind eine Vorauswahl von MIR - das Radar findet dort
    # naturgemaess nur, was ich vorher fuer interessant hielt. Ein breiter
    # Schnitt kann Titel liefern, an die keiner von uns gedacht hat.
    if _ROIC_AKTIV and ms is not None:
        try:
            usd = providers.get_fx_to_eur("USD") or 0.92
            markt, _q = ms.get_universe(["us", "de", "fr", "gb", "nl"],
                                        (3e9) / usd, RADAR_MARKT)
            neu_dazu = [t for t in markt if t not in seen]
            tickers.extend(neu_dazu)
            print(f"  [Radar] {len(neu_dazu)} Markttitel zusaetzlich "
                  f"zu {len(seen)} Themen-Tickern.")
        except Exception as e:
            print(f"  [Radar] Marktschnitt uebersprungen: {e}")

    tickers = filter_boersen(collapse_listings(ersetze_pence_durch_adr(tickers)))
    scored = scan_list(tickers, deep=SCAN_DEEP, label="Radar")
    scored = collapse_scored(scored, "Radar")      # Dubletten ueber den Namen
    _LAST_SCAN["Radar"] = scored
    ranked = sorted(
        [r for r in scored.values() if (r.get("composite") or 0) >= 55],
        key=lambda r: (r.get("composite") or 0) + min((r.get("upside") or 0) * 0.3, 15),
        reverse=True)
    _deep = _rescore_deep(ranked[:RADAR_TOP], "Radar")
    _deep_ticker = {r.get("ticker") for r in _deep}
    _flach_rest = [r for r in ranked[RADAR_TOP:SIGNAL_KANDIDATEN]
                   if r.get("ticker") not in _deep_ticker]
    top = _deep + _flach_rest
    return sorted(top, key=lambda r: (r.get("composite") or 0)
                  + min((r.get("upside") or 0) * 0.3, 15), reverse=True)


def _eur(x):
    try:
        return f"{x:,.2f}\u20ac".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "\u2014"


def _wahrscheinlich_split(alt_preis, neu_preis):
    """Erkennt am Kursverhaeltnis, ob zwischen zwei Laeufen wahrscheinlich ein
    Aktiensplit lag - dann ist ein scheinbarer Kurssturz (oder -sprung) kein
    echtes Ereignis. Ein 2:1-Split halbiert den Kurs optisch, 3:1 drittelt ihn,
    ein Reverse-Split verdoppelt/verdreifacht ihn. Wir pruefen, ob das
    Verhaeltnis nahe an einem gaengigen Split-Faktor liegt.

    Kein API-Abruf - rein aus den zwei Kursen, damit der Nachtlauf schnell
    bleibt. Liefert True, wenn ein Split die Kursaenderung gut erklaert."""
    if not alt_preis or not neu_preis or alt_preis <= 0 or neu_preis <= 0:
        return False
    q = neu_preis / alt_preis
    # gaengige Split-Verhaeltnisse (Kurs faellt) und Reverse (Kurs steigt)
    faktoren = [1/2, 1/3, 1/4, 1/5, 1/6, 1/7, 1/8, 1/10, 1/20,
                2, 3, 4, 5, 6, 8, 10, 2/3, 3/2, 3/4, 4/3]
    for f in faktoren:
        if abs(q - f) / f < 0.04:      # innerhalb 4 % eines Split-Faktors
            return True
    return False


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
            # Split-Check: fiel der Kurs nur optisch durch einen Split unter den
            # Einstieg, ist das keine echte Kaufzone. Alten Kurs gegen neuen.
            _split = o and _wahrscheinlich_split(o.get("price"), price)
            if not was_in and not _split:
                changes.append({"ticker": t, "name": r.get("name"), "section": section,
                                "kind": "buyzone",
                                "text": f"{t} in Kaufzone: Kurs {_eur(price)} \u2264 "
                                        f"Einstieg {_eur(entry)}"})
        if o is None:
            continue
        oc = o.get("composite")
        if nc is not None and oc is not None and abs(nc - oc) >= COMP_DELTA:
            # Der breite Scan laeuft flach - der gemeldete Sprung kann teils
            # Rechenrauschen sein (flach 52 vs. tief 56). Bevor wir eine so
            # drastische Aenderung melden, den NEUEN Wert TIEF nachrechnen,
            # damit die Startseite denselben Composite zeigt wie die
            # Einzelanalyse. Nur bei tatsaechlichen Spruengen (wenige Titel).
            nc_tief = nc
            _neu_kat = {}
            try:
                _d = score_ticker(t, deep=True)
                if _d and _d.get("composite") is not None:
                    nc_tief = _d["composite"]
                    _neu_kat = {k: _d.get(k) for k in
                                ("quality", "value", "growth", "momentum",
                                 "catalyst", "value_trap")}
            except Exception:
                pass
            # Nach dem tiefen Nachrechnen nur melden, wenn der Sprung bleibt.
            if abs(nc_tief - oc) >= COMP_DELTA:
                # SCHEIN-AENDERUNG ABFANGEN: Wenn eine Kategorie nur deshalb
                # springt, weil in einem Lauf die Daten fehlten (Score fiel auf
                # den Neutralwert 50 zurueck) und im anderen wieder da waren,
                # ist das KEINE echte fundamentale Aenderung, sondern
                # schwankende Datenverfuegbarkeit (typisch bei .L-Titeln mit
                # roic-Aussetzern - genau der Fall III.L Wachstum 0<->50). Solche
                # Titel NICHT melden, sonst pendelt die Startseite taeglich.
                _neu_neutral = (_d.get("cat_neutral") if _d else {}) or {}
                _alt_neutral = o.get("cat_neutral") or {}
                _daten_flip = False
                for _k in ("quality", "value", "growth", "momentum"):
                    _alt, _neu = o.get(_k), _neu_kat.get(_k)
                    if _alt is None or _neu is None:
                        continue
                    if abs(_neu - _alt) >= 8:
                        # war eine der beiden Seiten ein Neutral-Rueckfall?
                        if _neu_neutral.get(_k) or _alt_neutral.get(_k):
                            _daten_flip = True
                            break
                if _daten_flip:
                    # Datenlage schwankte - Snapshot still aktualisieren, aber
                    # KEINE Aenderungsmeldung erzeugen.
                    r["composite"] = nc_tief
                    for _k, _val in _neu_kat.items():
                        if _val is not None:
                            r[_k] = _val
                    continue
                arrow = "\u2197" if nc_tief > oc else "\u2198"
                _delta = nc_tief - oc
                _staerke = ("drastisch" if abs(_delta) >= 15
                            else "deutlich" if abs(_delta) >= 8 else "leicht")
                # Welche Kennzahlen haben sich geaendert? (alt aus Snapshot vs neu)
                _gruende = []
                _lbl = {"quality": "Qualit\u00e4t", "value": "Bewertung",
                        "growth": "Wachstum", "momentum": "Momentum",
                        "catalyst": "Katalysator"}
                for _k, _name in _lbl.items():
                    _alt, _neu = o.get(_k), _neu_kat.get(_k)
                    if _alt is not None and _neu is not None and abs(_neu - _alt) >= 8:
                        _pf = "\u2197" if _neu > _alt else "\u2198"
                        _gruende.append(f"{_name} {_pf} {round(_alt)}\u2192{round(_neu)}")
                # Value-Trap neu ausgeloest?
                if _neu_kat.get("value_trap") and not o.get("value_trap"):
                    _gruende.append("Value-Trap-Warnung neu ausgel\u00f6st")
                _grund_txt = ("; ".join(_gruende[:3]) if _gruende
                              else "mehrere Faktoren leicht ver\u00e4ndert")
                changes.append({"ticker": t, "name": r.get("name"), "section": section,
                                "kind": "composite", "delta": _delta,
                                "gruende": _gruende,
                                "text": f"{t} Composite {arrow} {oc}\u2192{nc_tief} "
                                        f"({_staerke}): {_grund_txt}"})
                r["composite"] = nc_tief
                # neue Kategorie-Scores in die Zeile schreiben (fuer Snapshot)
                for _k, _val in _neu_kat.items():
                    if _val is not None:
                        r[_k] = _val
        ou = o.get("upside")
        # Plausibilitaet: Ein Upside-Sprung sollte zum Kursverlauf passen. Faellt
        # der Kurs, steigt der Upside (und umgekehrt) - das ist echt. Aendert
        # sich der Upside STARK, obwohl der Kurs kaum bewegt ist, stammt die
        # Aenderung aus der Fair-Value-BASIS (andere Daten) - dann ist es oft
        # ein Dateneffekt, kein echtes Signal. Genau der ALV.DE-Fall: Composite
        # runter (Wachstum weg), Upside gleichzeitig rauf - widerspruechlich,
        # weil beides aus derselben Datenaenderung kommt.
        _op = o.get("price")
        _kurs_erklaert_upside = True
        # Split-Check: liegt zwischen den Laeufen ein Split, sind Kurs UND
        # Upside optisch verzerrt - keine dieser Meldungen ist dann echt.
        _ist_split = _wahrscheinlich_split(_op, price)
        if _ist_split:
            _kurs_erklaert_upside = False
        if (ou is not None and up is not None and _op and price
                and abs(up - ou) >= UPSIDE_DELTA and not _ist_split):
            _kurs_delta = (price / _op - 1) * 100 if _op else 0
            _upside_delta = up - ou
            # Wenn Kurs faellt, sollte Upside steigen: die Vorzeichen von
            # Kursaenderung und Upside-Aenderung sind dann GEGENLAEUFIG.
            # Passt die Richtung nicht ODER ist die Kursbewegung viel zu klein
            # fuer den Upside-Sprung, ist es ein Basis-Effekt.
            if abs(_kurs_delta) < abs(_upside_delta) * 0.4:
                # Kurs bewegte sich viel weniger als der Upside - Basis-Effekt
                _kurs_erklaert_upside = False
        if UPSIDE_FLIP and up is not None and ou is not None and (up >= 0) != (ou >= 0):
            if _kurs_erklaert_upside:
                changes.append({"ticker": t, "name": r.get("name"), "section": section,
                                "kind": "upside_flip",
                                "text": f"{t} Upside dreht {ou:+.0f}%\u2192{up:+.0f}%"})
        # Deutlicher Upside-Sprung (auch ohne Vorzeichenwechsel)
        elif (up is not None and ou is not None and abs(up - ou) >= UPSIDE_DELTA
              and _kurs_erklaert_upside):
            arrow = "\u2197" if up > ou else "\u2198"
            changes.append({"ticker": t, "name": r.get("name"), "section": section,
                            "kind": "upside_jump",
                            "text": f"{t} Upside {arrow} {ou:+.0f}%\u2192{up:+.0f}%"})
        # Radar-Score-Sprung
        nr, orr = r.get("radar_score"), o.get("radar_score")
        if nr is not None and orr is not None and abs(nr - orr) >= RADAR_DELTA:
            arrow = "\u2197" if nr > orr else "\u2198"
            changes.append({"ticker": t, "name": r.get("name"), "section": section,
                            "kind": "radar",
                            "text": f"{t} Radar-Score {arrow} {orr:.0f}\u2192{nr:.0f}"})
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



# Auf Modulebene gehoben: _analyse wurde auch von live_scan() genutzt,
# lag aber innerhalb von run(). Dort war der Name unbekannt - der
# Aufruf lief in ein 'except' und der Radar-Score im Live-Scan blieb
# deshalb IMMER leer, ohne dass es auffiel.
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
        # ZWEI verschiedene extras-Quellen - genau wie die Einzelanalyse:
        #  * get_signal_extras: Umsatzreihen/Revisionen fuer die Matrix-Signale
        #  * get_screen_extras: above_sma200/rsi fuer das SMA200-Gate der Scorecard
        # Frueher bekam die Scorecard hier nur get_signal_extras - das enthaelt
        # KEIN above_sma200. Dadurch fiel das Pflicht-Gate "Kurs > SMA200" mit
        # "keine Technik-Daten" aus, und aus einem Kaufkandidaten wurde
        # faelschlich "Knapp - Watchlist". Genau die Abweichung App vs. Nachtlauf.
        extras = providers.get_signal_extras(t)
        try:
            screen_extras = providers.get_screen_extras(t) or {}
        except Exception:
            screen_extras = {}
        # Insider- und Analystendaten VOR build_signals laden, damit der
        # Nachtlauf exakt denselben Pfad wie die Einzelanalyse nutzt: die
        # Analyse gibt intel.get("analyst") an build_signals weiter (fuer die
        # Matrix-2-Signale) UND an die Scorecard. Wenn hier None statt der
        # Analystendaten steht, weichen Matrix-2-Total und damit das Urteil ab.
        try:
            _insider = providers.get_insider_activity(t)
        except Exception:
            _insider = None
        try:
            _analyst = providers.get_analyst_ratings(t)
        except Exception:
            _analyst = None
        sig = _mx.build_signals(f, hist, _analyst, extras)
        res = _sc.evaluate(f, v, s.get("composite"),
                           _mx.auto_m1_total(sig), _mx.auto_m2_total(sig),
                           screen_extras, _insider, _analyst)
        out["verdict"] = res.get("verdict", "")
        out["vkey"] = res.get("vkey", "")     # "buy"/"watch"/"drop" - robuster Filter
        out["isin"] = f.get("isin")     # fuer die ISIN-Entdopplung der Signale
        # Einstiegskurs und aktueller Kurs - fuer die Kaufzonen-Pruefung.
        # Ein Signal darf NUR erfasst werden, wenn der Kurs die Einstiegszone
        # erreicht hat (Kurs <= Einstieg). Sonst tauchten Titel wie LLY in der
        # Trefferbilanz auf, deren Kurs weit ueber dem Einstieg lag - die
        # Strategie kann so nie funktionieren.
        out["entry"] = (round(v["entry_price"], 2)
                        if v.get("entry_price") else None)
        out["price"] = f.get("price")
        out["upside"] = v.get("upside_pct")
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



def run():
    started = _berlin_now()
    # Analysten-Historie laden (fuer die Value-Trap-Trenderkennung). Wird
    # waehrend des Laufs fortgeschrieben und am Ende zurueckgespeichert.
    global _ANALYST_HIST, _ANALYST_SEEN
    try:
        _ANALYST_HIST = store.get_analyst_hist() or {}
    except Exception:
        _ANALYST_HIST = {}
    _ANALYST_SEEN = set()
    # Versionsstempel GANZ nach vorn. Ohne ihn ist im Log nicht erkennbar,
    # welcher Stand tatsaechlich laeuft - genau daran haben wir mehrfach Zeit
    # verloren: Der Job scheiterte an Code, der im Repo laengst korrigiert war.
    print(f"=== precompute Start {started:%d.%m.%Y %H:%M} (dt. Zeit) \u00b7 "
          f"Code-Version {CODE_VERSION} ===")
    print(f"    Datei: {__file__}")
    try:
        import roic as _rv
        print(f"    Datenquelle: roic.ai "
              f"{'AKTIV' if _rv.enabled() else 'NICHT konfiguriert'} \u00b7 "
              f"Universum {UNIVERSE_SIZE}")
    except Exception:
        print("    Datenquelle: roic.py nicht gefunden \u2013 alte Fassung?")
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

    # Abschnittsweise absichern. Der Lauf macht inzwischen sieben Dinge -
    # faellt eines aus (Netz, Quote, Datenlage), sollen die uebrigen
    # trotzdem gespeichert werden. Frueher hat ein einziger Fehler den
    # ganzen Job mit Code 1 beendet und NICHTS geschrieben.
    _fehler = []

    def _abschnitt(name, fn, standard):
        try:
            return fn()
        except Exception as _e:
            import traceback
            print(f"[FEHLER] Abschnitt '{name}': {type(_e).__name__}: {_e}")
            traceback.print_exc()
            _fehler.append(name)
            return standard

    holdings = _abschnitt("Portfolio",
                          lambda: scan_list(pf_tickers, deep=True,
                                            label="Portfolio"), {})
    watch = _abschnitt("Watchlist",
                       lambda: scan_list(wl_tickers, deep=True,
                                         label="Watchlist"), {})

    # 2) Screener + Radar (bounded, shallow)
    print("Screener-Scan ...")
    scr = _abschnitt("Screener", screener_scan, [])
    print("Radar-Scan ...")
    rad = _abschnitt("Radar", radar_scan, [])
    print("Momentum-Scan ...")
    # Momentum als eigener Nachtlauf-Abschnitt: Top-Titel werden als Signale
    # erfasst und in der Trefferbilanz gegen den Index getestet - so laesst
    # sich messen, ob die Momentum-Auswahl ueber Monate etwas taugt.
    mom = _abschnitt("Momentum",
                     lambda: momentum_scan(universum=MOM_UNIVERSE_SIZE,
                                           top_n=MOM_TOP), [])

    # 3) Aenderungen bestimmen
    changes = []
    changes += diff_changes(old_snaps, holdings, "Portfolio")
    changes += diff_changes(old_snaps, watch, "Watchlist")
    # BREITE Veraenderungen: der Screener-Scan deckt ~600 Titel ueber alle
    # Branchen und fuenf Laender ab. Wir vergleichen jeden davon mit dem
    # Vortags-Snapshot und melden starke Spruenge in Composite, Radar-Score
    # oder Upside. Das ist die Startseiten-Logik "Was hat sich geaendert".
    _scr_map = {r["ticker"]: r for r in scr if r.get("ticker")}
    _rad_map = {r["ticker"]: r for r in rad if r.get("ticker")}
    # Radar-Score aus dem Radar-Scan in die Screener-Zeilen mischen, damit
    # diff_changes auch Radar-Spruenge sieht.
    for _t, _r in _scr_map.items():
        if _t in _rad_map and _rad_map[_t].get("score") is not None:
            _r.setdefault("radar_score", _rad_map[_t].get("score"))
    _prev_breit = old_snaps.get("_breit", {})
    changes += diff_changes(_prev_breit, _scr_map, "Markt")
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
    # Breite Werte je Titel fuer den naechsten Vergleich (nur die Felder, die
    # diff_changes braucht - haelt den Snapshot klein).
    new_snap["_breit"] = {
        t: {"composite": r.get("composite"), "upside": r.get("upside"),
            "radar_score": r.get("radar_score"), "name": r.get("name"),
            "price": r.get("price"), "entry": r.get("entry"),
            # Kategorie-Scores fuer den "warum hat sich der Score geaendert"-
            # Vergleich auf der Startseite
            "quality": r.get("quality"), "value": r.get("value"),
            "growth": r.get("growth"), "momentum": r.get("momentum"),
            "catalyst": r.get("catalyst"), "value_trap": r.get("value_trap")}
        for t, r in _scr_map.items()}
    store.set_snapshot(new_snap)
    # Analysten-Historie zurueckspeichern (fortgeschrieben in score_ticker).
    try:
        store.set_analyst_hist(_ANALYST_HIST)
        _mit_trend = sum(1 for r in _ANALYST_HIST.values() if len(r) >= 2)
        print(f"[value-trap] Analysten-Historie: {len(_ANALYST_HIST)} Titel, "
              f"{_mit_trend} mit auswertbarem Trend (>=2 Messpunkte).")
    except Exception as _e:
        print(f"[value-trap] Analysten-Historie speichern fehlgeschlagen: {_e}")

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

        # (_analyse steht jetzt auf Modulebene)
        sig_new = []
        print(f"[trackrecord] Erfassung mit Code-Version {CODE_VERSION}")

        def _kurs_plausibel(row, analyse):
            """False, wenn der Kurs unzuverlaessig ist (Datenfehler). Kriterium:
            Kurs liegt deutlich AUSSERHALB der eigenen 52-Wochen-Spanne - das
            ist physikalisch unmoeglich bei sauberen Daten und deutet auf einen
            kaputten Kurs hin (typisch bei duenn gehandelten OTC-Titeln wie
            SSNLF, wo der Momentum-Score auf 404 schoss). Solche Titel duerfen
            NICHT als Kaufkandidat erfasst werden - ihr 'guenstig' beruht auf
            Datenmuell, nicht auf echter Unterbewertung.

            Nutzt vs_52w_high/vs_52w_low (prozentualer Abstand, im Screener-Row
            vorhanden). Kleine Toleranz (8 %), damit ein legitimes neues
            52W-Hoch/-Tief nicht faelschlich als kaputt gilt."""
            vs_hoch = row.get("vs_52w_high")   # >0 => Kurs UEBER 52W-Hoch
            vs_tief = row.get("vs_52w_low")    # <0 => Kurs UNTER 52W-Tief
            if vs_hoch is not None and vs_hoch > 8:
                return False
            if vs_tief is not None and vs_tief < -8:
                return False
            return True

        def _in_kaufzone(analyse, row):
            """True, wenn der Kurs die Einstiegszone erreicht hat. Toleranz:
            bis 5 % ueber dem Einstieg gilt noch als 'knapp in der Zone' -
            konsistent mit dem Hedgefonds-Modus. So faellt nicht jeder Titel
            raus, der nur ein paar Prozent ueber dem exakten Einstieg notiert
            (sonst kamen gar keine Signale mehr, weil die Top-Titel fast nie
            18-25 % unter Fair Value liegen). Ohne belastbaren Einstieg (kein
            Fair Value) wird weiterhin NICHT erfasst - lieber kein Signal als
            ein Fehlkauf weit ueber der Zone.
            """
            entry = analyse.get("entry")
            price = analyse.get("price") or row.get("price")
            if not entry or not price:
                return False
            return price <= entry * 1.05

        _uebersprungen = 0
        _zone_abstand = []       # Diagnose: wie weit ueber der Zone?
        _kein_entry = 0          # Diagnose: wie viele ohne Einstiegskurs?
        _kein_daten = 0          # Diagnose: wie viele ganz ohne Analyse?
        _kurs_kaputt = 0         # Diagnose: wie viele mit kaputtem Kurs raus?
        for r in (scr or [])[:SIGNAL_KANDIDATEN]:
            tk = r.get("ticker")
            if not tk:
                continue
            # Kaputte Kurse (ausserhalb 52W-Spanne) gar nicht erst als Kandidat
            # behandeln - ihr "guenstig" beruht auf Datenmuell (z.B. SSNLF).
            if not _kurs_plausibel(r, {}):
                _kurs_kaputt += 1
                continue
            # Kaufzone ZUERST billig mit den Scan-Werten pruefen (entry/price
            # stehen schon im Row). Erst wenn ein Titel in der Zone liegt, den
            # teuren _analyse-Tiefabruf machen. So koennen wir bis zu 100
            # Kandidaten pruefen, ohne 100 Tiefabrufe - nur die wenigen echten
            # Kaufkandidaten kosten einen Abruf.
            _entry = r.get("entry")
            _preis = r.get("price")
            if not _preis:
                _kein_daten += 1
                continue
            if not _entry:
                _kein_entry += 1
                continue
            _zone_abstand.append((tk, round((_preis / _entry - 1) * 100, 1)))
            if not (_preis <= _entry * 1.05):
                _uebersprungen += 1
                continue
            # In der Zone -> jetzt Tiefanalyse fuer die Zusatzfelder
            _a = _analyse(tk)
            _entry = _a.get("entry") or _entry
            _preis = _a.get("price") or _preis
            sig_new.append({"ticker": tk, "quelle": "Screener", "name": r.get("name"),
                            "isin": _a.get("isin"),
                            "score": r.get("composite"), "upside": r.get("upside"),
                            "strategie": _a.get("strategie", ""),
                            "entry": _entry,
                            "verdict": _a.get("verdict", ""),
                            "vkey": _a.get("vkey", ""), "price": _preis})
        for r in (rad or [])[:SIGNAL_KANDIDATEN]:
            tk = r.get("ticker")
            if not tk:
                continue
            if not _kurs_plausibel(r, {}):
                _kurs_kaputt += 1
                continue
            # Kaufzone zuerst billig mit Scan-Werten pruefen, _analyse nur fuer
            # Titel in der Zone (wie beim Screener - erlaubt Top 100 ohne 100
            # Tiefabrufe).
            _entry = r.get("entry")
            _preis = r.get("price")
            if not _entry or not _preis:
                _uebersprungen += 1
                continue
            _zone_abstand.append((tk, round((_preis / _entry - 1) * 100, 1)))
            if not (_preis <= _entry * 1.05):
                _uebersprungen += 1
                continue
            # In der Zone -> Tiefanalyse fuer Score/Zusatzfelder
            _a = _analyse(tk)
            _entry = _a.get("entry") or _entry
            _preis = _a.get("price") or _preis
            sig_new.append({"ticker": tk, "quelle": "Radar", "name": r.get("name"),
                            "isin": _a.get("isin"),
                            "score": (_a.get("radar_score")
                                      if _a.get("radar_score") is not None
                                      else (r.get("quantum")
                                            if r.get("quantum") is not None
                                            else r.get("composite"))),
                            "firing": _a.get("radar_firing"),
                            "upside": r.get("upside"),
                            "strategie": _a.get("strategie", ""),
                            "entry": _entry,
                            "verdict": _a.get("verdict", ""),
                            "vkey": _a.get("vkey", ""), "price": _preis})
        if _uebersprungen:
            print(f"[trackrecord] {_uebersprungen} Titel uebersprungen "
                  f"(Kurs nicht in Einstiegszone).")
        # NEU: Warum wurde uebersprungen? Fehlt der Einstiegskurs oder liegen
        # die Titel wirklich ueber der Zone? Das unterscheidet ein Daten-/
        # Fair-Value-Problem von einem echten "alles zu teuer".
        print(f"[trackrecord] Diagnose Screener: {_kein_daten} ohne Kurs-Daten, "
              f"{_kein_entry} ohne Einstiegskurs (kein Fair Value), "
              f"{len(_zone_abstand)} mit berechenbarer Zone, "
              f"{_kurs_kaputt} mit kaputtem Kurs aussortiert.")
        if _zone_abstand:
            _sortiert = sorted(_zone_abstand, key=lambda x: x[1])
            print(f"[trackrecord] Abstand zur Zone (Kurs vs Einstieg): "
                  f"{_sortiert[:8]}")

        # Momentum-Signale: der Momentum-Score selbst ist die Kennzahl. Kein
        # Scorecard-Urteil (das misst Substanz, nicht Trend) - stattdessen wird
        # der Score gespeichert, damit die Trefferbilanz spaeter zeigen kann,
        # ob hohe Momentum-Scores den Index geschlagen haben.
        for r in (mom or [])[:MOM_TOP]:
            tk = r.get("ticker")
            if not tk:
                continue
            sig_new.append({
                "ticker": tk, "quelle": "Momentum", "name": r.get("name"),
                "score": r.get("score"),
                "verdict": ("Momentum stark" if r.get("ampel") == "gruen"
                            else "Momentum mittel" if r.get("ampel") == "gelb"
                            else "Momentum schwach"),
                "vkey": ("mom_buy" if r.get("ampel") == "gruen" else "mom"),
                "strategie": "Momentum",
                "mom_12_1": r.get("mom_12_1"),
                "rel_staerke": r.get("rel_staerke"),
                # Rohen Kurs in Handelswaehrung durchreichen - NICHT mit _fx in
                # EUR umrechnen. Die Trefferbilanz haelt den Wechselkurs separat
                # fest (entry_fx) und rechnet selbst um. Frueher wurde hier
                # bereits * _fx multipliziert -> Einstieg landete in EUR (440 USD
                # * 0,87 = 383), waehrend der Vergleichskurs in USD kam. Ergebnis
                # war ein erfundener Upside (~15%), obwohl der Titel heute
                # eingestiegen ist. Jetzt konsistent zu Screener/Radar.
                "price": r.get("price")})

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
                sig_new.append({"ticker": tk, "quelle": "Negativ", "name": r.get("name"),
                                "score": r.get("composite"),
                                "upside": r.get("upside"),
                                "merkmal": _merkmal,
                                "strategie": _a.get("strategie", ""),
                                "verdict": _a.get("verdict", ""), "price": r.get("price")})
            print(f"[trackrecord] Kontrollgruppe: {len(weak)} schwache Setups "
                  f"zur Gegenprobe erfasst.")
        except Exception as e:
            print(f"[trackrecord] Kontrollgruppe uebersprungen: {e}")

        # EXPERIMENTELL: Gegen-den-Strom-Gruppe. Niedrige Erwartungen plus
        # harte Zahlen, die dagegen sprechen. Wird nur GEMESSEN - ob die
        # Idee taugt, zeigt die Trefferbilanz nach Monaten.
        try:
            for r in contrarian_scan(10):
                tk = r.get("ticker")
                if not tk:
                    continue
                _a = _analyse(tk)
                sig_new.append({"ticker": tk, "quelle": "Contrarian", "name": r.get("name"),
                                "score": None, "upside": None,
                                "merkmal": r.get("pessimismus", ""),
                                "strategie": r.get("widerspruch", ""),
                                "verdict": _a.get("verdict", ""),
                                "price": r.get("price")})
        except Exception as e:
            print(f"[trackrecord] Contrarian uebersprungen: {e}")

        # EARNINGS-SCAN ueber den S&P 500. Zweistufig, damit die Abrufzahl
        # beherrschbar bleibt. Ergebnis wird gespeichert (Dashboard liest nur)
        # und die klaren Faelle werden als Signal protokolliert - damit sich
        # messen laesst, ob die Logik trifft.
        try:
            import regime as _rg
            _tk = _rg.sp500_tickers()
            print(f"[earnings] Universum: {len(_tk)} Titel")
            _erg = _rg.earnings_scan_universe(_tk, max_wochen=4,
                                             deep_limit=EARNINGS_DEEP_LIMIT)
            store.set_earnings(_erg)
            print(f"[earnings] {len(_erg)} Termine mit Einordnung gespeichert.")
            for _e in _erg:
                # Nur die eindeutigen Faelle protokollieren. Gelb und Grau
                # sind ausdruecklich KEINE Aussage - sie zu loggen wuerde die
                # Auswertung mit Rauschen fuellen.
                if _e.get("ampel") not in ("gruen", "rot"):
                    continue
                # Erwartungsluecke mit protokollieren - nur so laesst sich
                # spaeter pruefen, ob dieser Teil ueberhaupt etwas beitraegt.
                _luecke = None
                try:
                    _luecke = _rg.erwartungsluecke(_e["ticker"])
                except Exception:
                    pass
                sig_new.append({
                    "ticker": _e["ticker"], "name": _e.get("name"),
                    "quelle": ("Earnings+" if _e["ampel"] == "gruen"
                               else "Earnings-"),
                    "luecke": (_luecke or {}).get("punkte"),
                    "luecke_urteil": (_luecke or {}).get("urteil", "")[:70],
                    "score": _e.get("beat_quote"),
                    "upside": None,
                    "merkmal": (f"meldet in {_e['tage']} T · Beat "
                                f"{_e.get('beat_quote')}% · belohnt "
                                f"{_e.get('belohnt_pct')}%"),
                    "strategie": "; ".join((_e.get("pro") or [])[:2]),
                    "verdict": "",
                    "price": None,
                })
        except Exception as e:
            print(f"[earnings] uebersprungen: {e}")

        # NEUE EARNINGS CALLS ueber S&P 500 + NASDAQ-100 + DAX.
        # Nur die Kopfdaten (1 Abruf je Titel, ~560 Titel = gut 2 Minuten).
        # Volltexte holt das Dashboard erst beim Oeffnen - alles andere
        # waeren Megabyte an ungelesenem Text im Speicher.
        _tr_status = {"stand": "", "roic_aktiv": bool(_ROIC_AKTIV)}
        try:
            if _ROIC_AKTIV:
                _tk_uni = _roic_mod.index_universum()
                print(f"[transkripte] Universum: {len(_tk_uni)} Titel")
                _neu = _roic_mod.neue_transkripte(_tk_uni, tage=21, deckel=600)
                # Diagnose: was liefert transcript_liste fuer bekannte Titel,
                # die diese Woche gemeldet haben? Zeigt, ob das Problem an der
                # API-Antwort oder an der Datumslogik liegt.
                for _dt_t in ("META", "GOOGL", "MSFT", "AMZN", "AAPL"):
                    try:
                        _dl = _roic_mod.transcript_liste(_dt_t, limit=3)
                        if _dl:
                            print(f"  [EC-Diag] {_dt_t}: neuester Call "
                                  f"{_dl[0].get('datum')} "
                                  f"(Q{_dl[0].get('quartal')} {_dl[0].get('jahr')})")
                        else:
                            print(f"  [EC-Diag] {_dt_t}: transcript_liste LEER")
                    except Exception as _de:
                        print(f"  [EC-Diag] {_dt_t}: Fehler {_de}")
                if not hasattr(store, "set_transkripte"):
                    print("[transkripte] ABBRUCH: store.py ist veraltet "
                          "(set_transkripte fehlt) - bitte neu hochladen.")
                    raise RuntimeError("store.py veraltet")
                store.set_transkripte(_neu)
                _n_akt = sum(1 for r in _neu if r.get("ist_neu"))
                print(f"[transkripte] {len(_neu)} Calls gespeichert, "
                      f"{_n_akt} aktuell.")
                _tr_status["stand"] = (f"{len(_neu)} Calls erfasst, "
                                       f"{_n_akt} aktuell (Universum "
                                       f"{len(_tk_uni)} Titel)")
            else:
                print("[transkripte] uebersprungen (roic nicht aktiv - "
                      "kein API-Key in dieser Umgebung).")
                _tr_status["stand"] = ("\u00dcBERSPRUNGEN: roic-Key fehlt im "
                                       "Nachtlauf (GitHub-Secret ROIC_API_KEY "
                                       "pruefen). Der Test-Button in der App "
                                       "nutzt einen anderen Key.")
        except Exception as e:
            print(f"[transkripte] uebersprungen: {e}")
            _tr_status["stand"] = f"FEHLER: {e}"
        try:
            if hasattr(store, "set_transkript_status"):
                store.set_transkript_status(_tr_status)
        except Exception:
            pass

        for _s in sig_new:                    # Herkunft des Signals festhalten
            _s["codever"] = CODE_VERSION
        # Diagnose: wie viele der erfassten Signale sind echte KAUFKANDIDATEN
        # (Scorecard-Urteil "Kaufkandidat" / vkey "buy")? Wenn hier 0 steht,
        # erfuellt gerade kein Titel ALLE Pflichtkriterien - dann ist die leere
        # Kaufkandidaten-Liste korrekt und kein Bug. Steht hier >0, aber die
        # Bilanz zeigt nichts, liegt es an der Anzeige.
        _n_kauf = sum(1 for _s in sig_new
                      if _s.get("vkey") == "buy"
                      or str(_s.get("verdict", "")).strip() == "Kaufkandidat")
        print(f"[trackrecord] davon echte Kaufkandidaten (Scorecard erfuellt): "
              f"{_n_kauf} von {len(sig_new)}")
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
    try:
        _send_email(changes, holdings, watch, scr, rad, started, briefing_text)
    except Exception as _e:
        print(f"[FEHLER] E-Mail: {_e}")
        _fehler.append("E-Mail")

    # 7) Auto-Depot (50k, selbstverwaltet) einen Schritt weiterlaufen lassen.
    #    Nutzt dieselben Scans, die oben schon liefen - so wird das Depot
    #    taeglich neu bewertet, ohne dass der Nutzer manuell klicken muss.
    try:
        import autodepot as _ad
        _ad.durchlauf(scan_size=UNIVERSE_SIZE, erlauben_shorts=True)
        print("[autodepot] Depot aktualisiert.")
    except Exception as _e:
        print(f"[FEHLER] Auto-Depot: {_e}")
        _fehler.append("Auto-Depot")

    if _fehler:
        print(f"=== precompute fertig MIT FEHLERN in: {', '.join(_fehler)} ===")
        print("    Die uebrigen Abschnitte wurden gespeichert.")
    else:
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




def live_scan(universum=90, top_n=15, tief=True, fortschritt=None,
              strategie="Standard (wie Nachtlauf)"):
    """Derselbe Scan wie im Nachtlauf - aber auf Knopfdruck.

    Ablauf identisch zu screener_scan()/radar_scan(), damit die Zahlen zu
    denen des Cron passen:
      1) Universum holen und Zweitnotierungen zusammenfassen
      2) alle Titel flach bewerten (Composite, Quantum, Upside)
      3) die besten tief nachrechnen - inkl. Radar-Score

    Schritt 3 ist teuer (mehrere Abrufe je Titel), deshalb nur fuer top_n.
    'fortschritt' ist ein Rueckruf fortschritt(fertig, gesamt, phase).

    HINWEIS: Das ist eine Momentaufnahme, keine Empfehlung. Ein hoher Score
    heisst 'passt zu den Kriterien', nicht 'wird steigen'."""
    if ms is None:
        return []
    try:
        usd = providers.get_fx_to_eur("USD") or 0.92
        tickers, _src = ms.get_universe(["us", "de", "fr", "gb", "nl"],
                                        (5e9) / usd, universum)
        tickers = filter_boersen(collapse_listings(ersetze_pence_durch_adr(tickers)))
    except Exception as e:
        print(f"[live_scan] Universum nicht ladbar: {e}")
        return []

    # --- Phase 1: flach ueber das ganze Universum
    scored = {}
    # Phase 1 parallelisieren: Jeder Titel macht mehrere Netzabrufe, die die
    # meiste Zeit WARTEN (I/O). Sequenziell summiert sich das bei 150 Titeln
    # auf Minuten - lange genug, dass Streamlit den Lauf abbricht. Mit einem
    # Thread-Pool laufen mehrere Titel gleichzeitig; roic drosselt sich selbst
    # ueber seinen Lock, die roic-Rate wird also eingehalten.
    from concurrent.futures import ThreadPoolExecutor, as_completed
    fertig = 0
    gesamt = len(tickers)
    # 8 gleichzeitig ist ein guter Kompromiss: schnell genug, ohne yfinance
    # oder roic zu ueberfahren.
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(score_ticker, t, False): t for t in tickers}
        for fut in as_completed(futures):
            t = futures[fut]
            try:
                # Pro Titel hart begrenzen - ein haengender Abruf darf nicht
                # den ganzen Scan blockieren.
                r = fut.result(timeout=20)
                if r:
                    scored[t] = r
            except Exception:
                pass
            fertig += 1
            if fortschritt:
                fortschritt(fertig, gesamt, "breit")
    scored = collapse_scored(scored, "Live")       # Dubletten ueber den Namen
    _LAST_SCAN["Live"] = scored

    # --- Strategie anwenden: erst filtern, dann nach ihrem Kriterium sortieren
    strat = STRATEGIEN.get(strategie) or STRATEGIEN["Standard (wie Nachtlauf)"]
    passend = [r for r in scored.values() if strat["filter"](r)]
    ranked = sorted(passend, key=strat["sort"], reverse=True)
    auswahl = ranked[:top_n]
    print(f"  [live_scan] {strategie}: {len(passend)} von {len(scored)} "
          f"Titeln erfuellen die Kriterien.")

    if not tief:
        return auswahl

    # --- Phase 2: die Besten tief nachrechnen, inklusive Radar
    # Auch hier parallel: top_n ist zwar klein (10-30), aber jeder Titel macht
    # deep-Fundamentals PLUS _analyse (Radar) - das sind die teuersten Abrufe.
    def _tief_rechnen(r):
        t = r["ticker"]
        try:
            tiefer = score_ticker(t, deep=True) or r
        except Exception:
            tiefer = r
        radar_score = radar_ebenen = None
        try:
            a = _analyse(t)
            radar_score = a.get("radar_score")
            radar_ebenen = a.get("radar_firing")
            tiefer["verdict"] = a.get("verdict")
            tiefer["strategie"] = a.get("strategie")
        except Exception:
            pass
        tiefer["radar_score"] = radar_score
        tiefer["radar_ebenen"] = radar_ebenen
        return tiefer

    out = []
    fertig_t = 0
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(_tief_rechnen, r): r for r in auswahl}
        for fut in as_completed(futures):
            try:
                out.append(fut.result(timeout=30))
            except Exception:
                out.append(futures[fut])       # Rohwert behalten
            fertig_t += 1
            if fortschritt:
                fortschritt(fertig_t, len(auswahl), "tief")

    return sorted(out, key=strat["sort"], reverse=True)


# ============================================================================
# STRATEGIEN fuer den Live-Scan
# ----------------------------------------------------------------------------
# Jede Strategie ist ein Filter plus eine Sortierung. Bewusst KEINE
# "besten" Strategie - jede sucht etwas anderes und hat ihre eigene Schwaeche,
# die im Feld 'risiko' benannt wird. Wer sie vergleichen will, laesst sie in
# der Trefferbilanz gegeneinander laufen.
# ============================================================================

def _s_standard(r):
    return True


def _s_gefallen(r):
    """Deutlich unter dem Jahreshoch, aber fundamental in Ordnung."""
    v = r.get("vs_52w_high")
    return (v is not None and v <= -25
            and (r.get("composite") or 0) >= 50
            and (r.get("upside") or -999) >= 10
            and not r.get("value_trap"))


def _s_ausbruch(r):
    """Nahe am Jahreshoch mit Rueckenwind."""
    v = r.get("vs_52w_high")
    return (v is not None and v >= -8
            and (r.get("momentum") or 0) >= 55
            and (r.get("composite") or 0) >= 45)


def _s_qualitaet(r):
    """Gute Substanz zu vertretbarem Preis - kein Schnaeppchen, kein Drama."""
    return ((r.get("quality") or 0) >= 60
            and (r.get("composite") or 0) >= 58
            and 5 <= (r.get("upside") or -999) <= 45
            and not r.get("value_trap"))


def _s_uebersehen(r):
    """Wenig beobachtete Titel mit ordentlichen Kennzahlen."""
    n = r.get("analyst_count")
    return (n is not None and n <= 8
            and (r.get("composite") or 0) >= 55
            and (r.get("upside") or -999) >= 10)


# --- Schmidlins "ergiebige Wertpaare" (Kapitel 9.3) ------------------------
# Kennzahl NIE isoliert lesen: ein niedriges KGV ist nur gut bei Wachstum,
# ein niedriges KBV nur bei guter Eigenkapitalrendite, ein niedriges
# EV/EBITDA nur bei solider Marge. Sonst droht die Value-Falle.

def _s_kgv_wachstum(r):
    """Guenstiges KGV UND echtes Wachstum (Schmidlins PEG-Gedanke).
    Niedriges KGV allein ist oft eine Falle; erst mit Wachstum wird es zur
    Chance."""
    pe = r.get("pe")
    g = r.get("revenue_growth")
    if pe is None or g is None or pe <= 0:
        return False
    # KGV unter 18 UND Wachstum ueber 8% -> impliziertes PEG < ~1.5
    return pe < 18 and g > 8 and not r.get("value_trap")


def _s_kbv_ekr(r):
    """Guenstiges KBV UND hohe Eigenkapitalrendite. Ein Titel unter Buchwert
    ist nur interessant, wenn er sein Eigenkapital auch rentabel einsetzt -
    sonst ist der niedrige Buchwert-Multiplikator berechtigt."""
    pb = r.get("pb")
    roe = r.get("roe")
    if pb is None or roe is None or pb <= 0:
        return False
    # KBV unter 2 UND EKR ueber 12% (Schmidlins Mindest-Rentabilitaet)
    return pb < 2.0 and roe > 12 and not r.get("value_trap")


def _s_ev_marge(r):
    """Guenstiges EV/EBITDA UND solide EBITDA-Marge. Ein niedriges EV/EBITDA
    ist nur dann ein Schnaeppchen, wenn die Marge (= Preismacht/Qualitaet)
    stimmt - sonst ist es ein Margen-schwacher Titel zu Recht billig."""
    ev = r.get("ev_ebitda")
    m = r.get("ebitda_margin")
    if ev is None or m is None or ev <= 0:
        return False
    # EV/EBITDA unter 10 UND EBITDA-Marge ueber 15%
    return ev < 10 and m > 15 and not r.get("value_trap")


STRATEGIEN = {
    "Standard (wie Nachtlauf)": {
        "filter": _s_standard,
        "sort": lambda r: (r.get("composite") or 0)
                          + min((r.get("upside") or 0) * 0.3, 15),
        "was": "Alle Titel nach Composite plus gedeckelter Upside – "
               "identisch zum nächtlichen Job.",
        "risiko": "Keine Auswahl nach Marktlage; findet, was insgesamt am "
                  "besten abschneidet.",
        "spalten": [],
    },
    "Gefallen, aber gut bewertet": {
        "filter": _s_gefallen,
        "sort": lambda r: (r.get("upside") or 0) + (r.get("composite") or 0) * 0.5,
        "was": "Mindestens 25 % unter dem 52-Wochen-Hoch, Composite ab 50, "
               "Upside ab 10 %, keine erkannte Wertfalle. Die Wette: Der "
               "Markt hat überreagiert.",
        "risiko": "**Das ist die riskanteste Annahme im ganzen Werkzeug.** "
                  "Ein Kurs fällt meist aus einem Grund, und die Mehrheit der "
                  "gefallenen Titel fällt weiter. Der Filter unterscheidet "
                  "nicht zwischen Überreaktion und berechtigtem Absturz.",
        "spalten": [("vs. 52W-Hoch %", "vs_52w_high")],
    },
    "Möglicher Ausbruch (erhöhtes Risiko)": {
        "filter": _s_ausbruch,
        "sort": lambda r: (r.get("momentum") or 0) + (r.get("composite") or 0) * 0.4,
        "was": "Höchstens 8 % unter dem 52-Wochen-Hoch, Momentum ab 55, "
               "Composite ab 45. Die Wette: Stärke setzt sich fort.",
        "risiko": "Trendfolge funktioniert, bis sie es nicht mehr tut – und "
                  "der Wendepunkt sieht vorher aus wie die stärkste Phase. "
                  "Titel am Jahreshoch sind zudem selten günstig; hier wird "
                  "bewusst Bewertung gegen Schwung getauscht.",
        "spalten": [("vs. 52W-Hoch %", "vs_52w_high"), ("Momentum", "momentum")],
    },
    "Qualität zum fairen Preis": {
        "filter": _s_qualitaet,
        "sort": lambda r: (r.get("quality") or 0) * 0.6 + (r.get("composite") or 0) * 0.4,
        "was": "Qualitätsscore ab 60, Composite ab 58, Upside zwischen 5 und "
               "45 %. Die Obergrenze ist Absicht: Eine Upside von 200 % "
               "bedeutet meist fehlerhafte Daten, nicht ein Schnäppchen.",
        "risiko": "Gute Firmen sind selten billig. Diese Auswahl findet "
                  "wenige Titel und verpasst Erholungen nach Abstürzen – "
                  "dafür sind die Datenlagen meist solider.",
        "spalten": [("Qualität", "quality")],
    },
    "Übersehen (wenig Analysten)": {
        "filter": _s_uebersehen,
        "sort": lambda r: (r.get("composite") or 0)
                          + min((r.get("upside") or 0) * 0.3, 15),
        "was": "Höchstens 8 Analysten, Composite ab 55, Upside ab 10 %. Die "
               "Wette: Wo weniger hinschauen, ist mehr übersehen.",
        "risiko": "Geringe Abdeckung heißt auch dünnere Datenlage – Kursziele "
                  "und Schätzungen beruhen auf wenigen Meinungen und sind "
                  "entsprechend unzuverlässig. Zudem oft geringere "
                  "Handelbarkeit.",
        "spalten": [("Analysten", "analyst_count")],
    },
    "Schmidlin: KGV + Wachstum": {
        "filter": _s_kgv_wachstum,
        "sort": lambda r: (r.get("revenue_growth") or 0) * 1.5
                          + (r.get("composite") or 0) * 0.3
                          - (r.get("pe") or 30),
        "was": "G\u00fcnstiges KGV (unter 18) UND echtes Umsatzwachstum (\u00fcber 8 %). "
               "Schmidlins PEG-Gedanke: Ein niedriges KGV ist nur mit Wachstum "
               "eine Chance, sonst oft eine Falle.",
        "risiko": "Wachstum ist die fehleranf\u00e4lligste Bewertungskomponente. "
                  "Historisches Wachstum setzt sich nicht zwingend fort \u2013 "
                  "gerade bei zyklischem R\u00fcckenwind kann es t\u00e4uschen.",
        "spalten": [("KGV", "pe"), ("Wachstum %", "revenue_growth")],
    },
    "Schmidlin: KBV + Eigenkapitalrendite": {
        "filter": _s_kbv_ekr,
        "sort": lambda r: (r.get("roe") or 0) * 1.2
                          + (r.get("composite") or 0) * 0.3
                          - (r.get("pb") or 5) * 5,
        "was": "G\u00fcnstiges KBV (unter 2) UND hohe Eigenkapitalrendite (\u00fcber "
               "12 %). Ein Titel nahe Buchwert ist nur interessant, wenn er "
               "sein Kapital auch rentabel einsetzt.",
        "risiko": "Die ausgewiesene EKR kann durch hohe Verschuldung "
                  "aufgebl\u00e4ht sein (siehe ungehebelte EKR in der "
                  "Einzelanalyse). Ein niedriges KBV kann auch zweifelhafte "
                  "Bilanzwerte widerspiegeln.",
        "spalten": [("KBV", "pb"), ("EKR %", "roe")],
    },
    "Schmidlin: EV/EBITDA + Marge": {
        "filter": _s_ev_marge,
        "sort": lambda r: (r.get("ebitda_margin") or 0) * 1.0
                          + (r.get("composite") or 0) * 0.3
                          - (r.get("ev_ebitda") or 15) * 2,
        "was": "G\u00fcnstiges EV/EBITDA (unter 10) UND solide EBITDA-Marge (\u00fcber "
               "15 %). Ein niedriges EV/EBITDA ist nur ein Schn\u00e4ppchen, wenn "
               "die Marge \u2013 also Preismacht und Qualit\u00e4t \u2013 stimmt.",
        "risiko": "EBITDA blendet Abschreibungen und Zinsen aus \u2013 bei "
                  "kapitalintensiven oder hochverschuldeten Firmen kann das "
                  "die wahre Lage beschönigen. Immer gegen den Cashflow "
                  "gegenpr\u00fcfen.",
        "spalten": [("EV/EBITDA", "ev_ebitda"), ("EBITDA-Marge %", "ebitda_margin")],
    },
}


def branchen_uebersicht(universum=200, fortschritt=None):
    """Laedt ein breites Universum und gibt je Titel Sektor + Industrie zurueck.

    Zeigt, welchem Sektor das Tool jede Aktie zuordnet - genau die Einteilung,
    die Screener/Radar/Momentum verwenden. Parallel geladen, ISIN-entdoppelt,
    damit keine Zweitnotierungen (Apple dreifach) erscheinen.
    """
    if ms is None:
        return []
    try:
        usd = providers.get_fx_to_eur("USD") or 0.92
        tickers, _src = ms.get_universe(["us", "de", "fr", "gb", "nl"],
                                        (5e9) / usd, universum)
        tickers = filter_boersen(collapse_listings(ersetze_pence_durch_adr(tickers)))
    except Exception as e:
        print(f"[branchen_uebersicht] Universum nicht ladbar: {e}")
        return []

    from concurrent.futures import ThreadPoolExecutor, as_completed

    def _lade(t):
        try:
            f = providers.get_fundamentals(t, deep=False)
            if not f or not f.get("price"):
                return None
            return {"ticker": t, "name": f.get("name"),
                    "isin": f.get("isin"),
                    "sector": f.get("sector"), "industry": f.get("industry")}
        except Exception:
            return None

    geladen, fertig, gesamt = [], 0, len(tickers)
    with ThreadPoolExecutor(max_workers=8) as pool:
        futs = {pool.submit(_lade, t): t for t in tickers}
        for fut in as_completed(futs):
            try:
                r = fut.result(timeout=20)
                if r:
                    geladen.append(r)
            except Exception:
                pass
            fertig += 1
            if fortschritt:
                fortschritt(fertig, gesamt, "laden")

    geladen = entdopple_nach_isin(geladen)      # keine Zweitnotierungen
    print(f"  [branchen_uebersicht] {len(geladen)} Titel geladen.")
    return geladen


def momentum_scan(universum=200, top_n=25, fortschritt=None):
    """Momentum-Scan: findet Titel mit starkem, aufmerksamkeitsstarkem Trend.

    Ablauf parallel wie live_scan:
      1) Universum holen, Zweitnotierungen zusammenfassen
      2) je Titel Fundamentaldaten + Momentum-Snapshot laden (fuer Sektor,
         52W, Analysten und die Kursreihe)
      3) Branchen-Mediane bilden (relative Staerke braucht die Peers)
      4) Momentum-Score je Titel, nach Score sortiert zurueck

    Wichtig: Das ist eine Momentaufnahme des Trends, keine Prognose. Momentum
    kehrt sich abrupt um - der Score misst Staerke JETZT, nicht die Zukunft.
    """
    if ms is None:
        return []
    try:
        import momentum as momo
    except Exception as e:
        print(f"[momentum_scan] Modul fehlt: {e}")
        return []
    try:
        usd = providers.get_fx_to_eur("USD") or 0.92
        tickers, _src = ms.get_universe(["us", "de", "fr", "gb", "nl"],
                                        (5e9) / usd, universum)
        tickers = filter_boersen(collapse_listings(ersetze_pence_durch_adr(tickers)))
    except Exception as e:
        print(f"[momentum_scan] Universum nicht ladbar: {e}")
        return []

    from concurrent.futures import ThreadPoolExecutor, as_completed

    # --- Phase 1: Fundamentaldaten + 6M-Performance je Titel (parallel)
    def _lade(t):
        try:
            f = providers.get_fundamentals(t, deep=False)
            if not f or not f.get("price"):
                return None
            f["_ticker"] = t
            f["_fx"] = providers.get_fx_to_eur(f.get("currency", "USD")) or 1.0
            m = providers.get_screen_extras(t) or {}
            f["ch_6m"] = m.get("ch_6m")            # fuer den Branchen-Median
            f["_snap"] = m
            return f
        except Exception:
            return None

    geladen = []
    fertig = 0
    gesamt = len(tickers)
    with ThreadPoolExecutor(max_workers=8) as pool:
        futs = {pool.submit(_lade, t): t for t in tickers}
        for fut in as_completed(futs):
            try:
                f = fut.result(timeout=20)
                if f:
                    geladen.append(f)
            except Exception:
                pass
            fertig += 1
            if fortschritt:
                fortschritt(fertig, gesamt, "laden")

    # Auslands-Zweitnotierungen ueber die ISIN raus (APC.DE/0R2V.L -> AAPL),
    # BEVOR die Branchen-Mediane gebildet werden - sonst zaehlt Apple dreifach.
    # 'geladen' enthaelt schon 'ticker' und 'isin' aus get_fundamentals.
    for f in geladen:
        f.setdefault("ticker", f.get("_ticker"))
    geladen = entdopple_nach_isin(geladen)

    # --- Phase 2: Branchen-Mediane (relative Staerke)
    mediane = momo.branchen_mediane(geladen)

    # --- Phase 3: Momentum-Score je Titel
    ergebnisse = []
    for f in geladen:
        t = f["_ticker"]
        med = mediane.get(f.get("sector"))
        try:
            r = momo.bausteine(t, f, branchen_median_6m=med)
            if r and r.get("score") is not None:
                r["_fx"] = f.get("_fx") or 1.0
                ergebnisse.append(r)
        except Exception:
            pass

    ergebnisse.sort(key=lambda r: r["score"], reverse=True)
    print(f"  [momentum_scan] {len(ergebnisse)} Titel bewertet, "
          f"Top {top_n} zurueck.")
    return ergebnisse[:top_n]
# DOPPELNOTIERUNGEN ueber den FIRMENNAMEN zusammenfassen
# ----------------------------------------------------------------------------
# Die symbolbasierte Variante (_canon_base) greift nur, wenn die Symbole
# verwandt sind (BHP.L / BHPL.XC). Sie versagt bei den haeufigsten Faellen:
#   NVIDIA   -> NVDA, NVD.DE, NVDG.F, NVDD.XC
#   Alphabet -> GOOGL, GOOG, ABEA.DE, ABEC.DE, ABE0.F, ABEAD.XC
# Kein gemeinsames Basissymbol. Der Firmenname dagegen ist identisch.
# ============================================================================

_RECHTSFORMEN = (
    "incorporated", "corporation", "aktiengesellschaft", "limited",
    "holdings", "holding", "company", "group", "inc", "corp", "plc",
    "ag", "nv", "n v", "sa", "s a", "se", "ltd", "co", "kgaa", "asa",
    "ab", "oyj", "spa", "s p a", "bv", "b v", "class a", "class b",
    "class c", "adr", "ads", "sponsored", "the",
)


def _norm_name(name):
    """Firmennamen auf einen vergleichbaren Kern reduzieren.

    'NVIDIA Corporation' und 'NVIDIA Corp' -> 'nvidia'
    'Alphabet Inc.' und 'Alphabet Inc. Class C' -> 'alphabet'
    """
    if not name:
        return ""
    s = str(name).lower()
    # Punkte OHNE Leerzeichen entfernen, sonst zerfaellt "p.l.c." in drei
    # Buchstaben und passt nicht mehr auf "plc".
    s = s.replace(".", "")
    for z in ",()&'\"-/":
        s = s.replace(z, " ")
    teile = [w for w in s.split() if w]
    # Gattungszusatz am Ende abschneiden: "... class c", "... series a"
    if len(teile) >= 2 and teile[-2] in ("class", "serie", "series") \
            and len(teile[-1]) <= 2:
        teile = teile[:-2]
    # Rechtsformen und Gattungszusaetze hinten abschneiden
    while teile and teile[-1] in _RECHTSFORMEN:
        teile.pop()
    # auch einzelne Vorkommen entfernen (z.B. "sponsored adr" in der Mitte)
    teile = [w for w in teile if w not in _RECHTSFORMEN]
    return " ".join(teile)


def _listing_rang(r):
    """Sortierschluessel: welche Notierung soll die Gruppe vertreten?

    1) vollstaendige Daten schlagen lueckenhafte
    2) Heimatboerse vor Zweitnotierung (bestehende Suffix-Prioritaet)
    3) kuerzeres Basissymbol (GOOG vor GOOGL, BP vor BP-B)
    4) alphabetisch - nur damit das Ergebnis reproduzierbar ist
    """
    t = r.get("ticker") or ""
    luecken = sum(1 for k in ("composite", "upside", "fair_value", "price")
                  if r.get(k) is None)
    base, pri = _canon_base(t)
    return (luecken, pri, len(base), t)


def collapse_scored(scored, label=""):
    """Bewertete Titel nach Firmenname entdoppeln.

    Laeuft NACH der Bewertung, weil der Name erst dann vorliegt. Das kostet
    keine zusaetzlichen Abrufe - die Namen kommen aus derselben Abfrage.

    Titel ohne Namen bleiben unangetastet: lieber eine Dublette zu viel als
    zwei verschiedene Firmen faelschlich zusammengeworfen."""
    werte = list(scored.values() if isinstance(scored, dict) else scored)

    # ZUERST nach ISIN entdoppeln - der stabilste Schluessel. Faengt genau die
    # Faelle, an denen die Namens-Entdopplung scheitert: APC.DE / 0R2V.L / AAPL
    # heissen alle "Apple", tragen aber verschiedene Symbole; ueber die ISIN
    # US0378331005 bleibt nur die Heimatnotierung AAPL. Titel ohne ISIN gehen
    # unveraendert in die anschliessende Namens-Entdopplung.
    vor_isin = len(werte)
    werte = entdopple_nach_isin(werte)
    if len(werte) < vor_isin:
        print(f"  [{label or 'dedup'}] {vor_isin - len(werte)} Auslands-"
              f"Zweitnotierung(en) ueber ISIN entfernt.")

    gruppen, ohne_namen = {}, []
    for r in werte:
        key = _norm_name(r.get("name"))
        if not key:
            ohne_namen.append(r)
            continue
        gruppen.setdefault(key, []).append(r)

    out, entfernt = [], 0
    for key, gruppe in gruppen.items():
        if len(gruppe) > 1:
            gruppe = sorted(gruppe, key=_listing_rang)
            entfernt += len(gruppe) - 1
        out.append(gruppe[0])
    out.extend(ohne_namen)

    if entfernt:
        print(f"  [{label or 'dedup'}] {entfernt} Doppelnotierung(en) entfernt "
              f"-> {len(out)} Titel.")
    return {r["ticker"]: r for r in out} if isinstance(scored, dict) else out


# Einstiegspunkt ganz am Ende: Alles, was der Lauf braucht,
# muss VORHER definiert sein. Stand er weiter oben, waren spaeter
# angehaengte Funktionen (z.B. collapse_scored) zur Laufzeit noch
# unbekannt - genau daran ist der Nachtlauf gescheitert.
# ============================================================================
# ZWEITNOTIERUNGEN GANZ AUSSCHLIESSEN
# ----------------------------------------------------------------------------
# .IL (London International Order Book) und .XC (Zweitnotierung ohne
# Heimatboerse) sind ausnahmslos Doppelnotierungen auslaendischer Firmen.
# Sie bringen drei Probleme:
#   1) Sie liefern oft KEINEN Firmennamen - dann kann die namensbasierte
#      Entdopplung sie nicht zuordnen und sie erscheinen als eigener Titel
#      (0NC6.IL, 0NZF.IL).
#   2) Ihre Kurse stehen haeufig in einer anderen Einheit oder Waehrung als
#      die Heimatnotierung - daher unsinnige Renditen wie -52 %.
#   3) Sie sind fuer einen Privatanleger praktisch nicht handelbar.
# Es geht also nichts verloren: Die Heimatnotierung derselben Firma bleibt.
# ============================================================================

AUSGESCHLOSSENE_BOERSEN = ("IL", "XC")

# Grosse Firmen mit Pence-Londonnotierung (.L) UND US-ADR. Die Londonzeile
# notiert in Pence und ist bei roic der bestaetigte Fehlerfall (BP.L: KGV
# 168.091); die ADR notiert in USD und wird sauber bewertet. Deshalb wird
# .L VOR dem Scan durch die ADR ersetzt - dieselbe Firma, bessere Datenlage.
# Nur eindeutige Faelle, wo ADR und Londonzeile klar dieselbe Firma sind.
PENCE_ZU_ADR = {
    "BP.L": "BP", "SHEL.L": "SHEL", "HSBA.L": "HSBC", "AZN.L": "AZN",
    "GSK.L": "GSK", "ULVR.L": "UL", "RIO.L": "RIO", "BTI.L": "BTI",
    "VOD.L": "VOD", "NGG.L": "NGG", "BCS.L": "BCS", "LYG.L": "LYG",
    "PUK.L": "PUK", "SMFG.L": "SMFG", "DEO.L": "DEO", "RELX.L": "RELX",
    "PSO.L": "PSO", "WPP.L": "WPP", "AAL.L": "AAL",
}


def ersetze_pence_durch_adr(tickers):
    """Londoner Pence-Notierungen durch ihre US-ADR ersetzen."""
    out, getauscht = [], []
    for t in tickers:
        adr = PENCE_ZU_ADR.get(t.upper())
        if adr:
            out.append(adr)
            getauscht.append(f"{t}->{adr}")
        else:
            out.append(t)
    if getauscht:
        print(f"  [ADR] {len(getauscht)} Pence-Notierung(en) durch ADR "
              f"ersetzt: {', '.join(getauscht[:6])}"
              f"{' ...' if len(getauscht) > 6 else ''}")
    # doppelte entfernen, Reihenfolge halten
    return list(dict.fromkeys(out))


def ist_zweitnotierung(t: str) -> bool:
    if "." not in (t or ""):
        return False
    base, suf = t.rsplit(".", 1)
    suf = suf.upper()
    if suf in AUSGESCHLOSSENE_BOERSEN:
        return True
    # London IOB: Ticker beginnen mit einer Ziffer (0R2V.L, 0QZ8.L ...) -
    # das sind fast ausnahmslos Zweitnotierungen auslaendischer Titel, keine
    # echten UK-Aktien. Echte LSE-Titel fangen mit einem Buchstaben an.
    if suf == "L" and base[:1].isdigit():
        return True
    return False


def filter_boersen(tickers):
    """Zweitnotierungen aus einer Tickerliste entfernen."""
    raus = [t for t in tickers if ist_zweitnotierung(t)]
    if raus:
        print(f"  [Filter] {len(raus)} Zweitnotierung(en) ausgeschlossen: "
              f"{', '.join(raus[:8])}{' ...' if len(raus) > 8 else ''}")
    return [t for t in tickers if not ist_zweitnotierung(t)]


# ============================================================================
# EINSTIEGSPUNKT - MUSS ganz am Ende stehen, damit ALLE Funktionen (auch
# filter_boersen, ist_zweitnotierung, ersetze_pence_durch_adr weiter oben)
# bereits definiert sind, wenn run() sie aufruft. Frueher stand dieser Block
# in der Mitte der Datei - dadurch waren die danach definierten Funktionen
# zur Laufzeit von run() noch nicht bekannt (NameError: filter_boersen).
# ============================================================================
if __name__ == "__main__":
    run()
