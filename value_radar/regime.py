"""
regime.py — Marktumfeld, Sektor-Saisonalitaet und Reaktion auf Quartalszahlen.

Drei Fragen, die sich mit freien Daten EHRLICH beantworten lassen:

  1) WANN laufen welche Sektoren gut?      -> sector_seasonality()
     Monatsstatistik aus Sektor-ETFs ueber viele Jahre.

  2) WAS fuehrt gerade?                    -> leadership() / market_state()
     Relative Staerke der Sektoren + Zustand des Gesamtmarkts. So zeigt
     sich ein Boom (z.B. KI) als anhaltende Tech-Outperformance, ohne dass
     man ihn benennen muss.

  3) WIE reagiert eine Aktie auf Zahlen?   -> earnings_reactions()
     Historie aus Ueberraschung (Ist gegen Erwartung) und Kursreaktion.
     Der interessante Fall ist "geschlagen und trotzdem gefallen" - dann
     war die Erwartung im Kurs schon zu hoch.

GRENZEN - bitte ernst nehmen:
  * yfinance liefert maximal 8 Quartale je Titel. Acht Datenpunkte sind
    KEINE Statistik. Das Reaktionsprofil ist ein Hinweis, kein Beweis.
  * Saisonalitaet ueber 20 Jahre heisst 20 Werte je Monat. Auch das ist
    duenn, und Muster wie "Sell in May" sind seit Jahrzehnten bekannt -
    was bekannt ist, wird eingepreist.
  * Alle Aussagen sind BESCHREIBEND (was war), nicht vorhersagend
    (was kommt). Ob sie tragen, entscheidet die Trefferbilanz.
"""
from __future__ import annotations

try:
    import providers
except Exception:                                  # pragma: no cover
    providers = None

# Sektor-ETFs als Stellvertreter. Bewusst die grossen, liquiden SPDRs -
# lange Historie, keine Exotik.
SECTOR_ETFS = {
    "Technology":             ("XLK", "Technologie"),
    "Energy":                 ("XLE", "Energie"),
    "Financial Services":     ("XLF", "Finanzdienstleistungen"),
    "Healthcare":             ("XLV", "Gesundheit"),
    "Consumer Cyclical":      ("XLY", "Konsum zyklisch"),
    "Consumer Defensive":     ("XLP", "Konsum defensiv"),
    "Industrials":            ("XLI", "Industrie"),
    "Basic Materials":        ("XLB", "Rohstoffe"),
    "Utilities":              ("XLU", "Versorger"),
    "Real Estate":            ("XLRE", "Immobilien"),
    "Communication Services": ("XLC", "Kommunikation"),
}
BENCH = "SPY"
MONATE = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun",
          "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"]

_CACHE = {}


def _hist(ticker, period="20y", interval="1mo"):
    if providers is None:
        return None
    key = (ticker, period, interval)
    if key in _CACHE:
        return _CACHE[key]
    try:
        h = providers.get_price_history(ticker, period=period, interval=interval)
    except Exception:
        h = None
    _CACHE[key] = h
    return h


def _closes(h):
    """Schlusskurse als Liste von (datum, kurs) - robust gegen Formatvarianten."""
    if h is None or getattr(h, "empty", True):
        return []
    try:
        col = "Close" if "Close" in h.columns else h.columns[0]
        out = []
        for idx, val in zip(h.index, h[col].tolist()):
            if val is None or val != val:               # NaN
                continue
            out.append((idx, float(val)))
        return out
    except Exception:
        return []


# ---------------------------------------------------------------- Saisonalitaet
def sector_seasonality(sector, years=20):
    """Monatsstatistik eines Sektors.

    Rueckgabe je Monat: Durchschnitt, Median, Trefferquote (Anteil positiver
    Monate) und n. Das n gehoert IMMER mit angezeigt - bei n=20 ist ein
    Unterschied von zwei Prozentpunkten Rauschen."""
    ent = SECTOR_ETFS.get(sector)
    if not ent:
        return None
    etf, label = ent
    rows = _closes(_hist(etf, period=f"{years}y", interval="1mo"))
    if len(rows) < 24:
        return None
    monatlich = {i: [] for i in range(1, 13)}
    for i in range(1, len(rows)):
        d_prev, p_prev = rows[i - 1]
        d_cur, p_cur = rows[i]
        if not p_prev:
            continue
        try:
            m = d_cur.month
        except Exception:
            continue
        monatlich[m].append((p_cur / p_prev - 1) * 100)
    out = []
    for m in range(1, 13):
        v = monatlich[m]
        if not v:
            continue
        v_sorted = sorted(v)
        n = len(v)
        out.append({
            "monat": MONATE[m - 1],
            "n": n,
            "avg": round(sum(v) / n, 2),
            "median": round(v_sorted[n // 2], 2),
            "trefferquote": round(sum(1 for x in v if x > 0) / n * 100),
        })
    return {"sektor": label, "etf": etf, "monate": out}


def best_months(sector, years=20, top=3):
    """Die statistisch staerksten und schwaechsten Monate eines Sektors."""
    s = sector_seasonality(sector, years)
    if not s or not s["monate"]:
        return None
    srt = sorted(s["monate"], key=lambda r: -r["avg"])
    return {"sektor": s["sektor"], "etf": s["etf"],
            "stark": srt[:top], "schwach": srt[-top:][::-1],
            "n_min": min(r["n"] for r in s["monate"])}


# ------------------------------------------------------------------- Fuehrung
def _ret_over(rows, monate):
    if len(rows) <= monate:
        return None
    p_alt, p_neu = rows[-1 - monate][1], rows[-1][1]
    if not p_alt:
        return None
    return (p_neu / p_alt - 1) * 100


def leadership(years=3):
    """Welche Sektoren fuehren aktuell - gegen den Gesamtmarkt gemessen.

    Ein Boom braucht keinen Namen: Wenn Technologie ueber 3, 6 und 12
    Monate deutlich vor dem Index liegt, IST das der KI-Boom, ohne dass
    das Modell wissen muss, wie er heisst. Das ist robuster als eine
    Stichwortliste, die man staendig pflegen muesste."""
    bench = _closes(_hist(BENCH, period=f"{years}y", interval="1mo"))
    if len(bench) < 13:
        return None
    b3, b6, b12 = (_ret_over(bench, 3), _ret_over(bench, 6), _ret_over(bench, 12))
    out = []
    for sector, (etf, label) in SECTOR_ETFS.items():
        rows = _closes(_hist(etf, period=f"{years}y", interval="1mo"))
        if len(rows) < 13:
            continue
        r3, r6, r12 = (_ret_over(rows, 3), _ret_over(rows, 6), _ret_over(rows, 12))
        if r12 is None or b12 is None:
            continue
        rel = {
            "sektor": label, "etf": etf, "key": sector,
            "rel_3m": round(r3 - b3, 1) if (r3 is not None and b3 is not None) else None,
            "rel_6m": round(r6 - b6, 1) if (r6 is not None and b6 is not None) else None,
            "rel_12m": round(r12 - b12, 1),
        }
        vals = [v for v in (rel["rel_3m"], rel["rel_6m"], rel["rel_12m"])
                if v is not None]
        rel["schnitt"] = round(sum(vals) / len(vals), 1) if vals else None
        # "anhaltend" = ueber alle drei Zeitraeume vorn. Das trennt einen
        # echten Trend von einem Strohfeuer der letzten Wochen.
        rel["anhaltend"] = all(v is not None and v > 0 for v in
                               (rel["rel_3m"], rel["rel_6m"], rel["rel_12m"]))
        out.append(rel)
    out.sort(key=lambda r: -(r["schnitt"] or -999))
    return out


def market_state(years=3):
    """Zustand des Gesamtmarkts: Abstand zum Hoch der letzten 12 Monate."""
    rows = _closes(_hist(BENCH, period=f"{years}y", interval="1mo"))
    if len(rows) < 13:
        return None
    letzte12 = [p for _d, p in rows[-13:]]
    hoch, akt = max(letzte12), rows[-1][1]
    dd = (akt / hoch - 1) * 100 if hoch else 0.0
    if dd <= -20:
        lage, hinweis = "Baisse", "defensive Sektoren liefen historisch besser"
    elif dd <= -10:
        lage, hinweis = "Korrektur", "erhöhte Schwankung, Trends brechen häufiger"
    elif dd <= -5:
        lage, hinweis = "Rücksetzer", "normale Marktbewegung"
    else:
        lage, hinweis = "Aufwärts", "Trendfolge lief historisch besser"
    return {"lage": lage, "drawdown": round(dd, 1), "hinweis": hinweis}


# -------------------------------------------------- Reaktion auf Quartalszahlen
def earnings_reactions(ticker, max_quartale=8):
    """Wie hat die Aktie auf vergangene Quartalszahlen reagiert?

    Je Termin: Ueberraschung in Prozent und die Kursreaktion danach.
    Vier Faelle, wobei die beiden mittleren die aufschlussreichen sind:

      geschlagen + gestiegen  -> Erwartung war zu niedrig (normal)
      geschlagen + GEFALLEN   -> Erwartung war im Kurs schon zu hoch,
                                 oder der Ausblick enttaeuschte
      verfehlt + GESTIEGEN    -> Pessimismus war uebertrieben
      verfehlt + gefallen     -> normal

    ACHTUNG: maximal 8 Quartale. Das reicht fuer ein Stimmungsbild,
    nicht fuer eine belastbare Aussage."""
    if providers is None:
        return None
    try:
        import yfinance as yf
    except Exception:
        return None
    try:
        df = yf.Ticker(ticker).get_earnings_dates(limit=max_quartale * 2)
    except Exception:
        return None
    if df is None or getattr(df, "empty", True):
        return None
    if "Reported EPS" not in df.columns:
        return None

    hist = _closes(_hist(ticker, period="5y", interval="1d"))
    if not hist:
        return None

    def _reaktion(termin):
        """Kursaenderung vom Tag vor bis zum Tag nach dem Termin."""
        vor = naeh = None
        for d, p in hist:
            try:
                if d.date() < termin.date():
                    vor = p
                elif naeh is None and d.date() >= termin.date():
                    naeh = p
                    break
            except Exception:
                continue
        if vor and naeh:
            return (naeh / vor - 1) * 100
        return None

    out = []
    try:
        zeilen = list(df.iterrows())
    except Exception:
        return None
    for termin, r in zeilen:
        try:
            ist = r.get("Reported EPS")
            soll = r.get("EPS Estimate")
            if ist is None or ist != ist or soll is None or soll != soll:
                continue
            ueb = r.get("Surprise(%)")
            if ueb is None or ueb != ueb:
                ueb = ((ist - soll) / abs(soll) * 100) if soll else None
            reak = _reaktion(termin)
            if reak is None:
                continue
            beat = (ist > soll)
            out.append({
                "datum": str(termin)[:10],
                "erwartet": round(float(soll), 3),
                "gemeldet": round(float(ist), 3),
                "ueberraschung_pct": round(float(ueb), 1) if ueb is not None else None,
                "reaktion_pct": round(reak, 1),
                "beat": beat,
                "fall": ("geschlagen + gestiegen" if beat and reak > 0 else
                         "geschlagen + GEFALLEN" if beat else
                         "verfehlt + GESTIEGEN" if reak > 0 else
                         "verfehlt + gefallen"),
            })
        except Exception:
            continue
    return out[:max_quartale] or None


def reaction_profile(ticker):
    """Verdichtet die Reaktionshistorie zu einem Profil.

    ZWEI getrennte Fragen, die oft verwechselt werden:

      1) Liegen die ANALYSTEN falsch?  -> Beat-Quote
         Wie oft uebertrifft das Unternehmen die Schaetzung? Eine hohe
         Quote heisst: die Erwartung ist systematisch zu niedrig.

      2) BELOHNT der Markt das?        -> Belohnungsquote
         Steigt der Kurs nach guten Zahlen? Eine niedrige Quote heisst:
         der Markt rechnet mit dem Beat, er steckt schon im Kurs.

    Erst BEIDE zusammen ergeben eine verwertbare Aussage. Nur wenn die
    Analysten zu tief liegen UND der Markt darauf reagiert, ist die
    Fehleinschaetzung ueberhaupt nutzbar."""
    rows = earnings_reactions(ticker)
    if not rows:
        return None
    beats = [r for r in rows if r["beat"]]
    misses = [r for r in rows if not r["beat"]]
    beat_pos = [r for r in beats if r["reaktion_pct"] > 0]
    miss_pos = [r for r in misses if r["reaktion_pct"] > 0]
    n = len(rows)
    beat_quote = round(len(beats) / n * 100)
    belohnt = round(len(beat_pos) / len(beats) * 100) if beats else None

    prof = {
        "n": n,
        "n_beats": len(beats),
        "beat_quote": beat_quote,               # liegen die Analysten zu tief?
        "beat_belohnt_pct": belohnt,            # reagiert der Markt darauf?
        "miss_verziehen_pct": (round(len(miss_pos) / len(misses) * 100)
                               if misses else None),
        "avg_reaktion": round(sum(r["reaktion_pct"] for r in rows) / n, 1),
        "avg_reaktion_beat": (round(sum(r["reaktion_pct"] for r in beats)
                                    / len(beats), 1) if beats else None),
        "avg_ueberraschung": (round(sum(r["ueberraschung_pct"] for r in rows
                                        if r.get("ueberraschung_pct") is not None)
                                    / max(1, sum(1 for r in rows
                                                 if r.get("ueberraschung_pct")
                                                 is not None)), 1)),
        "faelle": {
            "geschlagen + gestiegen": len(beat_pos),
            "geschlagen + GEFALLEN": len(beats) - len(beat_pos),
            "verfehlt + GESTIEGEN": len(miss_pos),
            "verfehlt + gefallen": len(misses) - len(miss_pos),
        },
        "zeilen": rows,
    }

    # --- Zusammenfuehrung: sind die Analysten falsch UND laesst sich das nutzen?
    if n < 4:
        prof["analysten"] = "zu wenige Termine"
        prof["markt"] = "zu wenige Termine"
        prof["urteil"] = "zu wenige Termine für eine Aussage"
        return prof

    if beat_quote >= 75:
        prof["analysten"] = "liegen systematisch zu tief"
    elif beat_quote <= 40:
        prof["analysten"] = "liegen eher zu hoch"
    else:
        prof["analysten"] = "treffen es ungefähr"

    if belohnt is None:
        prof["markt"] = "keine Beats im Zeitraum"
    elif belohnt >= 70:
        prof["markt"] = "belohnt gute Zahlen"
    elif belohnt <= 40:
        prof["markt"] = "belohnt gute Zahlen NICHT"
    else:
        prof["markt"] = "reagiert uneinheitlich"

    if beat_quote >= 75 and belohnt is not None and belohnt >= 70:
        prof["urteil"] = ("Analysten unterschätzen das Unternehmen wiederholt "
                          "UND der Markt reagiert darauf – das Muster wäre "
                          "nutzbar, wenn es anhält")
    elif beat_quote >= 75 and belohnt is not None and belohnt <= 40:
        prof["urteil"] = ("Beats sind hier die Regel und deshalb eingepreist – "
                          "gute Zahlen allein bewegen den Kurs nicht mehr")
    elif beat_quote <= 40 and prof["miss_verziehen_pct"] is not None \
            and prof["miss_verziehen_pct"] >= 60:
        prof["urteil"] = ("verfehlt oft, wird aber verziehen – der Kurs hängt "
                          "an anderen Faktoren als den Quartalszahlen")
    else:
        prof["urteil"] = "kein klares Muster"
    return prof


def anomalien(ticker):
    """Termine, an denen der Kurs GEGEN die Zahlen lief.

    Das sind die lehrreichen Faelle: geschlagen und trotzdem gefallen
    (Erwartung war zu hoch) oder verfehlt und trotzdem gestiegen
    (Pessimismus war uebertrieben)."""
    rows = earnings_reactions(ticker)
    if not rows:
        return []
    return [r for r in rows
            if (r["beat"] and r["reaktion_pct"] < -2)
            or (not r["beat"] and r["reaktion_pct"] > 2)]


# ============================================================================
# TERMINKALENDER — wer meldet demnaechst, und was ist zu erwarten?
# ============================================================================
def next_earnings(ticker, max_wochen=4):
    """Naechster Quartalstermin innerhalb des Zeitfensters.

    yfinance liefert kuenftige Termine als Zeilen OHNE gemeldeten Gewinn.
    Rueckgabe: {datum, tage, eps_estimate} oder None."""
    try:
        import yfinance as yf
        import datetime as _dt
    except Exception:
        return None
    try:
        df = yf.Ticker(ticker).get_earnings_dates(limit=16)
    except Exception:
        return None
    if df is None or getattr(df, "empty", True):
        return None
    if "Reported EPS" not in df.columns:
        return None
    try:
        jetzt = _dt.datetime.now(_dt.timezone.utc)
    except Exception:
        return None
    kandidaten = []
    try:
        for termin, r in df.iterrows():
            ist = r.get("Reported EPS")
            if ist is not None and ist == ist:      # bereits gemeldet
                continue
            try:
                t = termin.to_pydatetime()
                if t.tzinfo is None:
                    t = t.replace(tzinfo=_dt.timezone.utc)
            except Exception:
                continue
            tage = (t - jetzt).days
            if 0 <= tage <= max_wochen * 7:
                est = r.get("EPS Estimate")
                kandidaten.append({
                    "datum": str(termin)[:10],
                    "tage": tage,
                    "eps_estimate": (round(float(est), 3)
                                     if est is not None and est == est else None),
                })
    except Exception:
        return None
    if not kandidaten:
        return None
    kandidaten.sort(key=lambda r: r["tage"])
    return kandidaten[0]


def _erwartung_spannung(f, eps_rev, profil):
    """Steht die Analystenschaetzung im Widerspruch zu beobachtbaren Trends?

    WICHTIG: Das prueft NICHT, ob eine Schaetzung "richtig" ist - das kann
    niemand vorab wissen. Es sammelt nur Spannungen zwischen der Erwartung
    und dem, was die Zahlen zeigen. Jede Spannung ist eine FRAGE, keine
    Antwort."""
    pro, contra = [], []

    # 1) Historie: wird die Schaetzung gewohnheitsmaessig uebertroffen?
    if profil and profil.get("n", 0) >= 4:
        bq = profil.get("beat_quote")
        if bq is not None and bq >= 75:
            pro.append(f"übertrifft die Schätzung in {bq} % der Fälle")
        elif bq is not None and bq <= 40:
            contra.append(f"verfehlt die Schätzung häufig (Beat-Quote {bq} %)")

    # 2) Richtung der Revisionen
    r = eps_rev or {}
    up, down = r.get("up"), r.get("down")
    if up is not None and down is not None:
        if up > down:
            pro.append(f"Schätzungen zuletzt angehoben ({up} hoch / {down} runter)")
        elif down > up:
            contra.append(f"Schätzungen zuletzt gesenkt ({down} runter / {up} hoch)")

    # 3) Erwarteter Gewinnrueckgang trotz wachsendem Umsatz
    epsf, epst = f.get("eps_forward"), f.get("eps_trailing")
    rg = f.get("revenue_growth")
    if epsf is not None and epst is not None and epst > 0 and epsf < epst * 0.95:
        if rg is not None and rg >= 0.05:
            pro.append(f"Gewinnrückgang erwartet, obwohl Umsatz +{rg*100:.0f} % wächst")
        else:
            contra.append("Gewinnrückgang erwartet")

    # 4) Cashflow gegen Buchgewinn
    fcf, ni = f.get("free_cashflow"), f.get("net_income")
    if fcf and ni is not None and ni <= 0 < fcf:
        pro.append("positiver Cashflow trotz Buchverlust")

    return pro, contra


def earnings_preview(ticker, max_wochen=4):
    """Volles Bild vor einem Quartalstermin.

    Verbindet vier Dinge:
      * wann gemeldet wird
      * wie die Aktie historisch auf Beats/Misses reagiert hat
      * was die Analysten erwarten
      * welche beobachtbaren Trends dieser Erwartung widersprechen

    Das Urteil sagt bewusst NICHT "kaufen" - es sagt, ob die Konstellation
    ueberhaupt interessant ist und worauf zu achten waere."""
    if providers is None:
        return None
    termin = next_earnings(ticker, max_wochen)
    if not termin:
        return None
    try:
        f = providers.get_fundamentals(ticker, deep=False) or {}
    except Exception:
        f = {}
    if not f.get("price"):
        return None
    try:
        eps_rev = providers.get_eps_revision_light(ticker)
    except Exception:
        eps_rev = None
    profil = reaction_profile(ticker)
    pro, contra = _erwartung_spannung(f, eps_rev, profil)

    out = {
        "ticker": ticker,
        "name": (f.get("name") or "")[:32],
        "sektor": f.get("sector"),
        "datum": termin["datum"],
        "tage": termin["tage"],
        "eps_estimate": termin["eps_estimate"],
        "eps_forward": f.get("eps_forward"),
        "revenue_growth": (round(f["revenue_growth"] * 100, 1)
                           if f.get("revenue_growth") is not None else None),
        "beat_quote": (profil or {}).get("beat_quote"),
        "belohnt_pct": (profil or {}).get("beat_belohnt_pct"),
        "n_termine": (profil or {}).get("n"),
        "avg_reaktion_beat": (profil or {}).get("avg_reaktion_beat"),
        "pro": pro, "contra": contra,
        "profil_urteil": (profil or {}).get("urteil"),
    }

    # --- Einordnung. Bewusst zurueckhaltend und immer mit Fallzahl im Blick.
    bq, bel, n = out["beat_quote"], out["belohnt_pct"], out["n_termine"] or 0
    if n < 4:
        out["urteil"] = "zu wenig Historie – Termin nur als Risiko vormerken"
        out["ampel"] = "grau"
    elif bq is not None and bq >= 75 and bel is not None and bel >= 70:
        out["urteil"] = ("übertrifft meist UND wird dafür belohnt – die "
                         "interessanteste Konstellation, aber auf dünner Basis")
        out["ampel"] = "gruen"
    elif bq is not None and bq >= 75 and bel is not None and bel <= 40:
        out["urteil"] = ("übertrifft meist, aber der Markt zahlt nichts dafür – "
                         "gute Zahlen sind hier bereits eingepreist")
        out["ampel"] = "gelb"
    elif bq is not None and bq <= 40:
        out["urteil"] = "verfehlt die Schätzung häufig – erhöhtes Rückschlagrisiko"
        out["ampel"] = "rot"
    else:
        out["urteil"] = "kein klares Muster – Termin als Schwankungsrisiko sehen"
        out["ampel"] = "grau"
    if len(pro) >= 2:
        out["urteil"] += f" · {len(pro)} Punkte sprechen gegen die Erwartung"
    return out


def earnings_scan(tickers, max_wochen=4, limit=40):
    """Welche Titel melden in den naechsten Wochen? Mit voller Einordnung.

    Bewusst gedeckelt: je Titel fallen mehrere Abrufe an. Fuer Portfolio
    und Watchlist ist das unproblematisch, fuer ein Universum von hunderten
    Tickern nicht."""
    out = []
    for t in list(dict.fromkeys(tickers))[:limit]:
        try:
            p = earnings_preview(t, max_wochen)
        except Exception:
            p = None
        if p:
            out.append(p)
    out.sort(key=lambda r: r["tage"])
    return out


# ============================================================================
# S&P-500-UNIVERSUM
# ============================================================================
_SP500_CACHE = {}


def sp500_tickers():
    """Aktuelle S&P-500-Mitglieder. Wikipedia zuerst, sonst Rueckfall auf
    die groessten US-Titel aus dem vorhandenen Screener."""
    if "list" in _SP500_CACHE:
        return _SP500_CACHE["list"]
    out = []
    try:
        import pandas as _pd
        tabs = _pd.read_html(
            "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")
        for t in tabs:
            if "Symbol" in t.columns:
                out = [str(s).strip().upper().replace(".", "-")
                       for s in t["Symbol"].tolist()]
                break
    except Exception:
        out = []
    if not out:                                   # Rueckfall
        try:
            import market_screener as _ms
            out, _src = _ms.get_universe(["us"], 5e9, 500)
        except Exception:
            out = []
    out = [t for t in dict.fromkeys(out) if t]
    _SP500_CACHE["list"] = out
    return out


def earnings_scan_universe(tickers=None, max_wochen=4, deep_limit=60,
                           fortschritt=None):
    """ZWEISTUFIG ueber ein grosses Universum.

    Stufe 1 (billig): nur der Termin je Titel - ein Abruf. Bei 500 Titeln
                      sind das 500 Abrufe.
    Stufe 2 (teuer):  volle Einordnung NUR fuer die, die im Fenster melden.
                      Ausserhalb der Berichtssaison sind das wenige, mitten
                      drin einige Dutzend.

    Ohne diese Trennung waeren es ueber 3.000 Abrufe je Lauf."""
    tickers = tickers or sp500_tickers()
    faellig = []
    for i, t in enumerate(tickers):
        try:
            n = next_earnings(t, max_wochen)
            if n:
                faellig.append((t, n["tage"]))
        except Exception:
            pass
        if fortschritt and (i + 1) % 50 == 0:
            fortschritt(i + 1, len(tickers), len(faellig))
    faellig.sort(key=lambda x: x[1])
    print(f"  [Earnings] {len(faellig)} von {len(tickers)} melden in "
          f"{max_wochen} Wochen -> {min(len(faellig), deep_limit)} werden "
          f"tief analysiert.")
    out = []
    for t, _tage in faellig[:deep_limit]:
        try:
            p = earnings_preview(t, max_wochen)
        except Exception:
            p = None
        if p:
            out.append(p)
    out.sort(key=lambda r: r["tage"])
    return out
