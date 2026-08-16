"""
providers.py — Datenzugriff mit sauberer Degradation.

Standard: yfinance (kostenlos, kein Key). Wenn FINNHUB_API_KEY / FMP_API_KEY
gesetzt sind, werden reichere Daten (Revisionen, Sentiment, Supply-Chain,
Transcripts, Insider) ergänzt. Fehlt etwas, wird None/[] zurückgegeben –
das restliche System läuft weiter.

Alle Netzwerk-Calls sind defensiv in try/except gekapselt.
"""
from __future__ import annotations
from typing import Any, Optional
import math
import time
import config

try:
    import roic as _roic
except Exception:                                   # pragma: no cover
    _roic = None

try:
    import yfinance as yf
except Exception:  # pragma: no cover
    yf = None

try:
    import requests
except Exception:  # pragma: no cover
    requests = None


def _safe(d: dict, key: str, default=None):
    v = d.get(key, default)
    if v is None:
        return default
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return default
    return v


def _num(x):
    try:
        f = float(x)
        return None if (math.isnan(f) or math.isinf(f)) else f
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Fundamentaldaten -> normalisiertes Dict
# ---------------------------------------------------------------------------
_COOLDOWN = {}          # Quelle -> Zeitstempel, bis zu dem sie uebersprungen wird


def _is_down(name):
    return _COOLDOWN.get(name, 0) > time.time()


_FAILS = {}             # Quelle -> Anzahl aufeinanderfolgender Fehler


def _trip(name, secs=60):
    """Quelle erst nach 2 aufeinanderfolgenden Fehlern voruebergehend deaktivieren.
    Ein einzelner transienter 429 soll NICHT sofort alle folgenden Ticker um die
    Quelle bringen (das drueckte sonst Scores/Fair Values im ganzen Portfolio)."""
    _FAILS[name] = _FAILS.get(name, 0) + 1
    if _FAILS[name] >= 2:
        _COOLDOWN[name] = time.time() + secs


def _ok(name):
    """Erfolgreicher Abruf -> Fehlerzaehler zuruecksetzen."""
    _FAILS[name] = 0


def _fh(path, params):
    """Finnhub-GET. Ein Retry, mit Circuit-Breaker bei Rate-Limit -> schnell."""
    if not config.FINNHUB_API_KEY or requests is None or _is_down("finnhub"):
        return None
    p = dict(params)
    p["token"] = config.FINNHUB_API_KEY
    for attempt in range(2):
        try:
            r = requests.get(f"https://finnhub.io/api/v1/{path}", params=p, timeout=10)
            if r.status_code == 200:
                _ok("finnhub")
                return r.json()
            if r.status_code == 429:               # Limit -> nicht weiter haemmern
                _trip("finnhub")
                return None
        except Exception:
            pass
        if attempt == 0:
            time.sleep(0.4)
    return None


def _num(x):
    try:
        if x is None:
            return None
        v = float(x)
        return v if v == v else None       # NaN raus
    except Exception:
        return None


def _yf_bundle(info):
    """yfinance-Rohwerte normalisiert (Margen/ROE als Ratio 0-1, wie geliefert)."""
    return {
        "price": _num(info.get("currentPrice")) or _num(info.get("regularMarketPrice")),
        "name": info.get("longName"), "sector": info.get("sector"),
        "industry": info.get("industry"), "currency": info.get("currency"),
        "country": info.get("country"),
        "shares_out": _num(info.get("sharesOutstanding")),
        "market_cap": _num(info.get("marketCap")),
        "enterprise_value": _num(info.get("enterpriseValue")),
        "beta": _num(info.get("beta")),
        "pe_trailing": _num(info.get("trailingPE")), "pe_forward": _num(info.get("forwardPE")),
        "pb": _num(info.get("priceToBook")), "ev_ebitda": _num(info.get("enterpriseToEbitda")),
        "ev_sales": _num(info.get("enterpriseToRevenue")),
        "ps": _num(info.get("priceToSalesTrailing12Months")),
        "peg": _num(info.get("pegRatio")) or _num(info.get("trailingPegRatio")),
        "roe": _num(info.get("returnOnEquity")), "roa": _num(info.get("returnOnAssets")),
        "gross_margin": _num(info.get("grossMargins")),
        "operating_margin": _num(info.get("operatingMargins")),
        "profit_margin": _num(info.get("profitMargins")),
        "revenue_growth": _num(info.get("revenueGrowth")),
        # Umsatz: wurde bisher NIE gesetzt, obwohl valuation.py danach fragt.
        # Folge: die EPV-Methode fiel immer auf den KUV-Umweg zurueck.
        "revenue": _num(info.get("totalRevenue")),
        "earnings_growth": _num(info.get("earningsGrowth")),
        "debt_to_equity": _num(info.get("debtToEquity")),
        "current_ratio": _num(info.get("currentRatio")),
        "quick_ratio": _num(info.get("quickRatio")),
        "ebitda": _num(info.get("ebitda")), "free_cashflow": _num(info.get("freeCashflow")),
        "operating_cashflow": _num(info.get("operatingCashflow")),
        "eps_trailing": _num(info.get("trailingEps")), "eps_forward": _num(info.get("forwardEps")),
        "book_value_ps": _num(info.get("bookValue")),
        "total_debt": _num(info.get("totalDebt")), "cash": _num(info.get("totalCash")),
        "target_mean": _num(info.get("targetMeanPrice")),
        # Spannweite der Kursziele: Ein Mittelwert aus 60 und 131 USD sieht
        # praezise aus, ist aber ein Kompromiss zwischen zwei Lagern. Ohne
        # Hoch/Tief laesst sich nicht erkennen, wie belastbar er ist.
        "target_high": _num(info.get("targetHighPrice")),
        "target_low": _num(info.get("targetLowPrice")),
        "analyst_count": _num(info.get("numberOfAnalystOpinions")),
        "business_summary": info.get("longBusinessSummary") or None,
        "recommendation": info.get("recommendationKey"),
        "52w_high": _num(info.get("fiftyTwoWeekHigh")), "52w_low": _num(info.get("fiftyTwoWeekLow")),
    }


def _finnhub_bundle(ticker):
    """Finnhub-Quelle normalisiert auf dieselbe Skala wie yfinance
    (Margen/ROE/Wachstum: Prozent -> Ratio; Mio. -> absolut)."""
    B = {}
    q = _fh("quote", {"symbol": ticker})
    if q and _num(q.get("c")):
        B["price"] = _num(q.get("c"))
    p = _fh("stock/profile2", {"symbol": ticker})
    if p:
        B["name"] = p.get("name") or None
        B["country"] = p.get("country") or None
        # WICHTIG: Finnhubs quote-Endpoint liefert fuer US-gelistete Symbole (ohne
        # Boersen-Suffix wie .HK/.DE) IMMER USD-Kurse. Die Profil-Waehrung nennt bei
        # China-ADRs (NTES, BABA, ...) aber teils HKD/CNY -> wuerde die EUR-Umrechnung
        # ruinieren (NTES 111 USD -> "16 EUR"). Daher: ohne Suffix immer USD.
        B["currency"] = "USD" if "." not in ticker else (p.get("currency") or None)
        B["industry"] = p.get("finnhubIndustry") or None
        if _num(p.get("shareOutstanding")):
            B["shares_out"] = _num(p.get("shareOutstanding")) * 1e6
        if _num(p.get("marketCapitalization")):
            B["market_cap_usd"] = _num(p.get("marketCapitalization")) * 1e6
    m = _fh("stock/metric", {"symbol": ticker, "metric": "all"})
    if m and isinstance(m.get("metric"), dict):
        M = m["metric"]

        def gv(*keys):
            for k in keys:
                if _num(M.get(k)) is not None:
                    return _num(M.get(k))
            return None

        def ratio(lo, hi, *keys):           # Prozent -> Ratio, mit Plausibilitaetsgrenze
            v = gv(*keys)
            if v is None:
                return None
            v = v / 100.0
            return v if lo <= v <= hi else None

        B["pe_trailing"] = gv("peTTM", "peBasicExclExtraTTM", "peExclExtraTTM")
        B["pb"] = gv("pbQuarterly", "pbAnnual")
        B["ps"] = gv("psTTM", "psAnnual")
        B["eps_trailing"] = gv("epsTTM", "epsInclExtraItemsTTM")
        B["book_value_ps"] = gv("bookValuePerShareQuarterly", "bookValuePerShareAnnual")
        B["beta"] = gv("beta")
        B["52w_high"] = gv("52WeekHigh")
        B["52w_low"] = gv("52WeekLow")
        B["current_ratio"] = gv("currentRatioQuarterly", "currentRatioAnnual")
        B["roe"] = ratio(-3, 3, "roeTTM", "roeRfy")
        B["roa"] = ratio(-2, 2, "roaTTM", "roaRfy")
        B["gross_margin"] = ratio(-2, 2, "grossMarginTTM", "grossMarginAnnual")
        B["operating_margin"] = ratio(-2, 2, "operatingMarginTTM", "operatingMarginAnnual")
        B["profit_margin"] = ratio(-2, 2, "netProfitMarginTTM", "netProfitMarginAnnual")
        B["revenue_growth"] = ratio(-5, 10, "revenueGrowthTTMYoy", "revenueGrowthQuarterlyYoy")
        B["earnings_growth"] = ratio(-5, 10, "epsGrowthTTMYoy", "epsGrowthQuarterlyYoy")
    return {k: v for k, v in B.items() if v is not None}


def _pick(*vals):
    for v in vals:
        if v is not None:
            return v
    return None


def _consensus(*vals):
    """Median der vorhandenen Werte (robust gegen einen Ausreisser).
    Bei 2 Werten = Mittelwert, bei 3 = mittlerer Wert."""
    xs = sorted(v for v in vals if v is not None)
    if not xs:
        return None
    n = len(xs)
    if n == 1:
        return xs[0]
    if n % 2:
        return xs[n // 2]
    return (xs[n // 2 - 1] + xs[n // 2]) / 2.0


def _fmp_get(path, params=None):
    """FMP-GET. Ein Retry, mit Circuit-Breaker bei Rate-Limit -> schnell."""
    if not config.FMP_API_KEY or requests is None or _is_down("fmp"):
        return None
    p = dict(params or {})
    p["apikey"] = config.FMP_API_KEY
    for attempt in range(2):
        try:
            r = requests.get(f"https://financialmodelingprep.com/api/v3/{path}",
                             params=p, timeout=12)
            if r.status_code == 200:
                _ok("fmp")
                return r.json()
            if r.status_code == 429:
                _trip("fmp")
                return None
        except Exception:
            pass
        if attempt == 0:
            time.sleep(0.4)
    return None


# ---------------------------------------------------------------------------
# Tiingo: saubere Kurse + verlaessliche Waehrung. NUR Preis/Waehrung, keine
# Fundamentaldaten (im Gratis-Tarif nicht enthalten). Best effort mit
# Circuit-Breaker; faellt bei Fehlern lautlos auf die anderen Quellen zurueck.
# ---------------------------------------------------------------------------
_TIINGO_META = {}          # Ticker -> {"currency":..., "name":...} (prozess-Cache)


def _tiingo_get(path, params=None):
    key = getattr(config, "TIINGO_API_KEY", "")
    if not key or requests is None or _is_down("tiingo"):
        return None
    p = dict(params or {})
    p["token"] = key
    for attempt in range(2):
        try:
            r = requests.get(f"https://api.tiingo.com/{path}", params=p,
                             headers={"Content-Type": "application/json"}, timeout=10)
            if r.status_code == 200:
                _ok("tiingo")
                return r.json()
            if r.status_code in (429, 403):        # Limit/kein Zugriff -> pausieren
                _trip("tiingo")
                return None
        except Exception:
            pass
        if attempt == 0:
            time.sleep(0.4)
    return None


def _tiingo_meta(ticker):
    """Metadaten (v.a. Waehrung) - einmal je Ticker, gecacht."""
    if ticker in _TIINGO_META:
        return _TIINGO_META[ticker]
    meta = {}
    d = _tiingo_get(f"tiingo/daily/{ticker}")
    if isinstance(d, dict):
        meta = {"currency": (d.get("priceCurrency") or d.get("currency") or "").upper() or None,
                "name": d.get("name") or None}
    _TIINGO_META[ticker] = meta
    return meta


def _tiingo_eod(ticker):
    """Letzter EOD-Schlusskurs (adjustiert) + Waehrung, gepaart. (preis, waehrung)."""
    d = _tiingo_get(f"tiingo/daily/{ticker}/prices")
    px = None
    if isinstance(d, list) and d:
        row = d[-1]
        px = _num(row.get("adjClose")) or _num(row.get("close"))
    cur = (_tiingo_meta(ticker) or {}).get("currency")
    return (px if px and px > 0 else None), cur


def _tiingo_iex(ticker):
    """US-Intraday (IEX) letzter/mid Preis. (preis, waehrung) - IEX ist USD."""
    d = _tiingo_get(f"iex/{ticker}")
    if isinstance(d, list) and d:
        row = d[0]
        px = _num(row.get("last")) or _num(row.get("tngoLast")) or _num(row.get("mid"))
        if px and px > 0:
            return px, "USD"
    return None, None


def _fmp_bundle(ticker):
    """Vierte Quelle (FMP) normalisiert. Margen/ROE/Wachstum kommen bereits als
    Ratio (0-1) -> direkt mit yfinance vergleichbar, ideal zum Gegenpruefen."""
    B = {}
    prof = _fmp_get(f"profile/{ticker}")
    if isinstance(prof, list) and prof:
        d = prof[0]
        B["price"] = _num(d.get("price"))
        B["name"] = d.get("companyName") or None
        B["currency"] = d.get("currency") or None
        B["country"] = d.get("country") or None
        B["industry"] = d.get("industry") or None
        B["sector"] = d.get("sector") or None
        B["beta"] = _num(d.get("beta"))
        B["business_summary"] = d.get("description") or None
        if _num(d.get("mktCap")):
            B["market_cap"] = _num(d.get("mktCap"))
        rng = d.get("range")
        if isinstance(rng, str) and "-" in rng:
            try:
                lo, hi = rng.split("-")
                B["52w_low"], B["52w_high"] = _num(lo), _num(hi)
            except Exception:
                pass
    rt = _fmp_get(f"ratios-ttm/{ticker}")
    if isinstance(rt, list) and rt:
        d = rt[0]
        B["pe_trailing"] = _num(d.get("peRatioTTM"))
        B["pb"] = _num(d.get("priceToBookRatioTTM"))
        B["ps"] = _num(d.get("priceToSalesRatioTTM"))
        B["roe"] = _num(d.get("returnOnEquityTTM"))
        B["roa"] = _num(d.get("returnOnAssetsTTM"))
        B["gross_margin"] = _num(d.get("grossProfitMarginTTM"))
        B["operating_margin"] = _num(d.get("operatingProfitMarginTTM"))
        B["profit_margin"] = _num(d.get("netProfitMarginTTM"))
        B["current_ratio"] = _num(d.get("currentRatioTTM"))
        B["quick_ratio"] = _num(d.get("quickRatioTTM"))
    km = _fmp_get(f"key-metrics-ttm/{ticker}")
    if isinstance(km, list) and km:
        d = km[0]
        B["book_value_ps"] = _num(d.get("bookValuePerShareTTM"))
        B["ev_ebitda"] = _num(d.get("enterpriseValueOverEBITDATTM"))
        B["ev_sales"] = _num(d.get("evToSalesTTM"))
        if _num(d.get("enterpriseValueTTM")):
            B["enterprise_value"] = _num(d.get("enterpriseValueTTM"))
        if B.get("pe_trailing") is None:
            B["pe_trailing"] = _num(d.get("peRatioTTM"))
    gr = _fmp_get(f"financial-growth/{ticker}", {"limit": 1})
    if isinstance(gr, list) and gr:
        d = gr[0]
        B["revenue_growth"] = _num(d.get("revenueGrowth"))
        B["earnings_growth"] = _num(d.get("epsgrowth"))
    # Historischer Median-KGV (fuer Markt-Fair-Value-Methode): Jahres-KGVs 5-8J
    hist = _fmp_get(f"ratios/{ticker}", {"limit": 8})
    if isinstance(hist, list) and hist:
        pes = sorted(_num(x.get("priceEarningsRatio")) for x in hist
                     if _num(x.get("priceEarningsRatio")) and 0 < x.get("priceEarningsRatio", 0) < 120)
        if len(pes) >= 4:
            mid = len(pes) // 2
            B["hist_pe_median"] = (pes[mid] if len(pes) % 2 else
                                   (pes[mid - 1] + pes[mid]) / 2)
    return {k: v for k, v in B.items() if v is not None}


def _merge_sources(ticker, A, B, C=None, use_tiingo=False):
    """Kombiniert mehrere normalisierte Quellen feldweise. Eindeutige Groessen
    (Kurs, Aktien, KGV/KBV) werden konsistent abgeleitet/gegengeprueft; bei
    skalengleichen Ratios (Margen/ROE/Wachstum) entscheidet der Median (Konsens)."""
    C = C or {}
    warn = []
    # Tiingo zuerst (nur deep): sauberer Kurs + verlaessliche Waehrung, GEPAART aus
    # EINER Quelle -> behebt Waehrungs-Verwechslungen strukturell (z.B. NTES).
    t_px = t_cur = None
    if use_tiingo:
        try:
            t_px, t_cur = _tiingo_eod(ticker)
        except Exception:
            t_px = t_cur = None
    if t_px:
        price = t_px
        currency = t_cur or A.get("currency") or C.get("currency") or "USD"
    else:
        price = _pick(A.get("price"), C.get("price"), B.get("price"))
        # Handelswaehrung NUR aus yfinance/fmp. Finnhubs Profil liefert teils die
        # Bilanz-/Reporting-Waehrung (z.B. HKD bei US-ADRs wie NTES) -> das wuerde die
        # EUR-Umrechnung voellig verzerren (NTES 111 USD -> faelschlich ~16 EUR).
        currency = A.get("currency") or C.get("currency") or "USD"
    refs = [(n, s.get("price")) for n, s in (("yfinance", A), ("finnhub", B), ("fmp", C))
            if s.get("price")]
    if len(refs) >= 2:
        lo = min(p for _, p in refs)
        hi = max(p for _, p in refs)
        if lo > 0 and (hi - lo) / lo > 0.5:
            warn.append("Kurse aus Quellen stark uneinig (evtl. andere B\u00f6rse/W\u00e4hrung): "
                        + ", ".join(f"{n} {p:.2f}" for n, p in refs))
        elif lo > 0 and (hi - lo) / lo > 0.06:
            warn.append("Kurs uneinig: " + ", ".join(f"{n} {p:.2f}" for n, p in refs))
    shares = _pick(A.get("shares_out"), B.get("shares_out"))
    eps = _pick(A.get("eps_trailing"), C.get("eps_trailing"), B.get("eps_trailing"))
    bvps = _pick(A.get("book_value_ps"), C.get("book_value_ps"), B.get("book_value_ps"))

    # Marktkap.: Kurs x Aktien ist quellenuebergreifend konsistent -> bevorzugt
    mc_calc = price * shares if (price and shares) else None
    mc_rep = _pick(A.get("market_cap"), C.get("market_cap"))
    if mc_calc and mc_rep and mc_rep > 0 and abs(mc_calc - mc_rep) / mc_rep > 0.25:
        warn.append("Marktkap.: Kurs x Aktien weicht von gemeldetem Wert ab")
    market_cap = mc_calc or mc_rep
    if market_cap is None and currency == "USD":
        market_cap = B.get("market_cap_usd")

    # KGV / KBV: gemeldet/abgeleitet konsistent, sonst Konsens der Quellen
    pe = A.get("pe_trailing")
    if pe is None and price and eps and eps > 0:
        pe = price / eps
    pe = _pick(pe, _consensus(C.get("pe_trailing"), B.get("pe_trailing")))
    pb = A.get("pb")
    if pb is None and price and bvps and bvps > 0:
        pb = price / bvps
    pb = _pick(pb, _consensus(C.get("pb"), B.get("pb")))

    src = ["yfinance"]
    if B:
        src.append("finnhub")
    if C:
        src.append("fmp")
    ebitda = A.get("ebitda")
    ev = _pick(A.get("enterprise_value"), C.get("enterprise_value"))
    fcf = A.get("free_cashflow")
    total_debt = A.get("total_debt") or 0.0
    cash = A.get("cash") or 0.0
    net_debt = total_debt - cash

    def cons(field):
        return _consensus(A.get(field), C.get(field), B.get(field))

    return {
        "ticker": ticker.upper(),
        "name": _pick(A.get("name"), C.get("name"), B.get("name")) or ticker.upper(),
        "isin": _pick(A.get("isin"), C.get("isin"), B.get("isin")),
        "sector": A.get("sector") or C.get("sector") or "Unknown",
        "industry": _pick(A.get("industry"), C.get("industry"), B.get("industry")) or "Unknown",
        "currency": currency,
        "country": _pick(A.get("country"), C.get("country"), B.get("country")) or "?",
        "price": price,
        "market_cap": market_cap,
        "enterprise_value": ev,
        "shares_out": shares,
        "beta": _pick(A.get("beta"), C.get("beta"), B.get("beta")) or config.VALUATION["default_beta"],
        "pe_trailing": pe,
        "pe_forward": A.get("pe_forward"),
        "pb": pb,
        "ev_ebitda": _pick(A.get("ev_ebitda"), C.get("ev_ebitda")),
        "ev_sales": _pick(A.get("ev_sales"), C.get("ev_sales")),
        "ps": _pick(A.get("ps"), _consensus(C.get("ps"), B.get("ps"))),
        "peg": A.get("peg"),
        "fcf_yield": (fcf / ev) if (fcf and ev) else None,
        "roe": cons("roe"),
        "roa": cons("roa"),
        "gross_margin": cons("gross_margin"),
        "operating_margin": cons("operating_margin"),
        "profit_margin": cons("profit_margin"),
        "revenue_growth": cons("revenue_growth"),
        "earnings_growth": cons("earnings_growth"),
        "debt_to_equity": A.get("debt_to_equity"),
        "current_ratio": cons("current_ratio"),
        "quick_ratio": _pick(A.get("quick_ratio"), C.get("quick_ratio")),
        "net_debt": net_debt,
        "net_debt_ebitda": (net_debt / ebitda) if (ebitda and ebitda > 0) else None,
        "ebit": ebitda,
        "ebitda": ebitda,
        "free_cashflow": fcf,
        "operating_cashflow": A.get("operating_cashflow"),
        "eps_trailing": eps,
        "eps_forward": A.get("eps_forward"),
        "book_value_ps": bvps,
        "total_debt": total_debt,
        "cash": cash,
        "target_mean": A.get("target_mean"),
        "target_high": A.get("target_high"),
        "target_low": A.get("target_low"),
        "analyst_count": A.get("analyst_count"),
        "business_summary": _pick(A.get("business_summary"), C.get("business_summary")),
        "hist_pe_median": C.get("hist_pe_median"),
        "recommendation": A.get("recommendation"),
        "52w_high": _pick(A.get("52w_high"), C.get("52w_high"), B.get("52w_high")),
        "52w_low": _pick(A.get("52w_low"), C.get("52w_low"), B.get("52w_low")),
        "data_sources": "+".join(src),
        "_warnings": warn,
    }


def get_fundamentals(ticker: str, deep: bool = False) -> dict[str, Any]:
    """Kombiniert mehrere Datenquellen feldweise zu einem moeglichst verlaesslichen
    Kennzahlen-Dict. yfinance (Taxonomie-Basis) + Finnhub + (bei deep=True) FMP fuer
    echten Kennzahlen-Konsens; Stooq als letzte Preis-Absicherung.
    deep=True nur fuer Einzelanalysen verwenden (FMP-Tageslimit schonen)."""
    info = {}
    if yf is not None and not _is_down("yfinance"):
        for attempt in range(2):                 # 1 Retry: yfinance faellt oft transient aus
            try:
                info = yf.Ticker(ticker).info or {}
                if info.get("sector") or info.get("currentPrice") or info.get("regularMarketPrice"):
                    break
            except Exception:
                info = {}
            if attempt == 0:
                time.sleep(0.4)
    A = _yf_bundle(info)
    # Robustheit gegen yfinance-Versionswechsel/API-Aussetzer: fehlen Kurs oder
    # Waehrung im info-Dict, liefert fast_info sie meist trotzdem (stabile API).
    if yf is not None and (not A.get("price") or not A.get("currency")):
        try:
            fi = yf.Ticker(ticker).fast_info
            if not A.get("price"):
                A["price"] = _num(getattr(fi, "last_price", None)
                                  or (fi.get("last_price") if hasattr(fi, "get") else None))
            if not A.get("currency"):
                A["currency"] = (getattr(fi, "currency", None)
                                 or (fi.get("currency") if hasattr(fi, "get") else None))
            if not A.get("market_cap"):
                A["market_cap"] = _num(getattr(fi, "market_cap", None)
                                       or (fi.get("market_cap") if hasattr(fi, "get") else None))
        except Exception:
            pass
    B = _finnhub_bundle(ticker)
    # roic.ai ersetzt FMP als Tiefen-Quelle, wo es den Ticker abdeckt
    # (US immer, Europa erst nach v3-Freigabe - Fehler vom Support bestaetigt).
    # 300 Abrufe/min statt 250/Tag: deep kann jetzt auch im Scan laufen.
    R = None
    if _roic is not None and _roic.covers(ticker):
        try:
            # Beim flachen Scan die Sparfassung (3 Abrufe statt 8). Sonst
            # wuerde eine breite Vorauswahl allein durch roic minutenlang
            # dauern - und die Zusatzfelder braucht sie gar nicht.
            R = (_roic.bundle(ticker) if deep
                 else _roic.bundle_light(ticker))
        except Exception:
            R = None
    C = None
    if deep and not R:
        C = _fmp_bundle(ticker)          # Rueckfall nur noch ohne roic
    merged = _merge_sources(ticker, A, B, C, use_tiingo=deep)
    # roic-Werte gewinnen feldweise, wo vorhanden - ausser Kurs/Waehrung:
    # die bleiben bei yfinance, weil dort die Pence-Normalisierung haengt.
    if R:
        # ------------------------------------------------------------------
        # WAEHRUNGS-ABGLEICH. roic normalisiert internationale Abschluesse
        # auf USD (Anbieterangabe), unser Kurs kommt von yfinance in
        # Handelswaehrung. Ungeprueft gemischt ergaebe das falsche
        # Verhaeltniszahlen - dieselbe Fehlerklasse wie BP.L mit KGV 168.091.
        #
        # Statt zu raten oder pauschal zu verwerfen wird der Faktor GEMESSEN:
        # Beide Quellen liefern einen Kurs fuer denselben Titel. Ihr
        # Verhaeltnis IST der Umrechnungsfaktor - unabhaengig davon, welche
        # Waehrungen im Spiel sind. Damit lassen sich die absoluten Werte
        # umrechnen, statt sie wegzuwerfen.
        #
        # Einheitenlose Groessen (Margen, Renditen, Wachstum, Verhaeltnisse)
        # bleiben unberuehrt - sie sind waehrungsunabhaengig.
        # ------------------------------------------------------------------
        _ABSOLUT = {                      # Betraege und Je-Aktie-Werte
            "market_cap", "enterprise_value", "cash", "total_debt",
            "net_debt", "revenue", "ebitda", "ebit", "free_cashflow",
            "net_income", "book_value_ps", "eps_trailing",
        }
        _px_y, _px_r = merged.get("price"), R.get("price")
        _faktor = 1.0
        if _px_y and _px_r and _px_r > 0:
            _q = _px_y / _px_r
            if 0.2 <= _q <= 5.0 and abs(_q - 1.0) > 0.02:
                _faktor = _q          # verschiedene Waehrungen/Einheiten
                merged["_roic_fx"] = round(_q, 4)
        _roic_felder = []
        for k, v in R.items():
            if k in ("price", "currency", "_src") or v is None:
                continue
            if _faktor != 1.0 and k in _ABSOLUT:
                try:
                    v = v * _faktor
                except Exception:
                    continue
            merged[k] = v
            _roic_felder.append(k)
        merged["_roic"] = True
        # Diagnose: welche Felder kamen tatsaechlich von roic? (fuer die
        # Quellenanzeige im Aktienvergleich - aendert keine Berechnung)
        merged["_roic_felder"] = sorted(_roic_felder)
        # Historisches KGV-Band: bisher bei ALLEN Titeln leer (FMP-Quote),
        # dadurch lief relval.py ins Leere. roic liefert es aus Jahres-EPS
        # plus Jahresschlusskursen - nur bei deep, kostet 2 Extra-Abrufe.
        if deep and not merged.get("hist_pe_median"):
            try:
                h = _roic.pe_history(ticker)      # fertiges Band, 1 Abruf
                if h and h.get("median"):
                    merged["hist_pe_median"] = h["median"]
                    merged["hist_pe_values"] = h.get("werte")
                    merged["hist_pe_jahre"] = h.get("jahre")
                    merged["hist_pe_hoch"] = h.get("spanne_hoch")
                    merged["hist_pe_tief"] = h.get("spanne_tief")
                    merged["hist_pe_n"] = h.get("n")
            except Exception:
                pass
        # NEU: 52-Wochen-Hoch/Tief aus der roic-Kurshistorie ableiten (loest
        # yfinance ab). Nur bei deep - ein Extra-Abruf, den der breite Scan
        # nicht rechtfertigt. roic hat die Kurse, also nehmen wir sie von dort.
        if deep:
            try:
                _reihe = _roic.schlusskurse(ticker, tage=260)   # ~1 Handelsjahr
                _kurse = [k for _, k in _reihe if k]
                if len(_kurse) >= 30:               # genug Datenpunkte
                    _r_hi, _r_lo = max(_kurse), min(_kurse)
                    # roic-Kurse ggf. in anderer Einheit als der Anzeigekurs -
                    # denselben gemessenen Faktor anwenden wie oben.
                    if _faktor != 1.0:
                        _r_hi *= _faktor
                        _r_lo *= _faktor
                    merged["52w_high"] = _r_hi
                    merged["52w_low"] = _r_lo
                    if "52w_high" not in _roic_felder:
                        _roic_felder.append("52w_high")
                        _roic_felder.append("52w_low")
                        merged["_roic_felder"] = sorted(_roic_felder)
            except Exception:
                pass
    if merged.get("price") is None:                 # Quelle: Stooq als letzte Absicherung
        sp = _stooq_last(ticker)
        if sp:
            merged["price"] = sp
            merged["data_sources"] = merged.get("data_sources", "") + "+stooq"
            if merged.get("market_cap") is None and merged.get("shares_out"):
                merged["market_cap"] = sp * merged["shares_out"]
            if merged.get("pe_trailing") is None and merged.get("eps_trailing"):
                e = merged["eps_trailing"]
                merged["pe_trailing"] = sp / e if e and e > 0 else None

    # --- Pence-Normalisierung (GBp/GBX -> GBP) --------------------------------
    # Londoner Titel liefern bei yfinance den KURS in Pence (BP.L: 517.1 GBp),
    # die je-Aktie-Kennzahlen (EPS, Buchwert) und Summen (Marktkap., Schulden)
    # aber in PFUND. Dadurch rechneten alle EPS-/Buchwert-basierten Methoden
    # Werte um den Faktor 100 zu niedrig -> der Plausibilitaetsfilter warf sie
    # als "unplausibel" raus, uebrig blieben Ausreisser. Ergebnis: BP.L mit
    # Fair Value 1043 bei Kurs 517 (+102 % Upside) und die Meldung
    # "Fair Value aus nur einer Methode" bei praktisch allen .L-/.XC-Tickern.
    # Fix: die KURSSEITE auf Pfund bringen, dann sind alle Groessen konsistent.
    # Die EUR-Umrechnung liefert unveraendert dasselbe Ergebnis, weil fx_to_eur
    # fuer GBp bisher den Faktor 0.01 anwendete.
    # WICHTIG: "GBP" (Pfund) darf NICHT umgerechnet werden - nur GBp/GBX (Pence).
    _cur = (merged.get("currency") or "").strip()
    _CCY_CACHE[ticker] = _cur          # Cache fuer is_pence() - spart Extra-Abrufe
    if _cur in ("GBp", "GBX", "gbx"):
        for _k in ("price", "target_mean", "target_high", "target_low",
                   "52w_high", "52w_low",
                   "entry_price", "prev_close", "day_high", "day_low"):
            _v = merged.get(_k)
            if isinstance(_v, (int, float)) and _v:
                merged[_k] = _v / 100.0
        merged["currency"] = "GBP"
        merged["_pence_normalised"] = True
        # KGV neu bilden, falls es aus dem Pence-Kurs stammte
        _e = merged.get("eps_trailing")
        if _e and _e > 0 and merged.get("price"):
            merged["pe_trailing"] = merged["price"] / _e
    # Vollstaendigkeits-Flag fuer die Cache-Entscheidung. Bei einem deep-Abruf
    # SOLL roic die Kernfelder liefern. Fehlen sie (roic hatte einen
    # Schluckauf: Rate-Limit, Netz-Aussetzer), ist das Ergebnis unvollstaendig
    # und darf NICHT lange gecacht werden - sonst klebt die Luecke stundenlang,
    # obwohl roic laengst wieder liefert. Genau das war der Grund, warum ein
    # App-Neustart "geholfen" hat.
    if deep:
        _kernfelder = ("free_cashflow", "ebitda", "book_value_ps",
                       "market_cap", "revenue")
        _roic_aktiv = bool(merged.get("_roic"))
        _kern_da = sum(1 for k in _kernfelder if merged.get(k) is not None)
        # vollstaendig, wenn roic aktiv war UND die Mehrheit der Kernfelder da ist
        merged["_vollstaendig"] = bool(_roic_aktiv and _kern_da >= 3)
    else:
        merged["_vollstaendig"] = True     # flache Abrufe: kein roic-Anspruch
    return merged


_EU_SUFFIX = (".AS", ".PA", ".L", ".SW", ".MI", ".MC", ".VI", ".BR", ".HE",
              ".ST", ".OL", ".CO", ".LS", ".IR")
_HOME_SUFFIX = (".DE", ".F", ".MU", ".SG", ".BE", ".DU", ".HM")   # Deutschland


def _sym_rank(item, query):
    """Rangfolge der Suchtreffer: exakter Ticker > Aktie > US-Primaerlisting
    (kein Suffix) > Heimat (DE) > EU. Asiatische Zweitlistings (.HK/.SS/.T ...)
    bekommen keinen Bonus, damit z.B. 'Netease' das US-ADR NTES trifft und nicht
    die Hongkong-Aktie 9999.HK (HKD)."""
    sym = (item.get("symbol") or "").upper()
    typ = (item.get("type") or "").upper()
    q = (query or "").strip().upper()
    score = 0
    if sym == q:
        score += 100
    if typ in ("EQUITY", "EQ", "S", "STOCK"):
        score += 20
    if "." not in sym:
        score += 12                     # US-Primaerlisting
    elif sym.endswith(_HOME_SUFFIX):
        score += 9
    elif sym.endswith(_EU_SUFFIX):
        score += 6
    return score


def search_symbol(query: str, limit: int = 8) -> list[dict]:
    """Namens-/Ticker-Suche. Yahoo zuerst; blockt Yahoo (Cookie/Crumb-Pflicht),
    springt die Finnhub-Suche ein. Liefert [{symbol,name,type,exchange}]."""
    if not query:
        return []
    out = []
    if requests is not None:
        try:
            r = requests.get("https://query2.finance.yahoo.com/v1/finance/search",
                             params={"q": query, "quotesCount": limit, "newsCount": 0},
                             headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
            for q in r.json().get("quotes", []):
                sym = q.get("symbol")
                if not sym:
                    continue
                out.append({
                    "symbol": sym,
                    "name": q.get("shortname") or q.get("longname") or "",
                    "type": q.get("quoteType") or q.get("typeDisp") or "",
                    "exchange": q.get("exchDisp") or q.get("exchange") or "",
                })
        except Exception:
            out = []
    if not out:                                   # Fallback: Finnhub-Symbolsuche
        try:
            res = _fh("search", {"q": query}) or {}
            for q in (res.get("result") or [])[:limit]:
                sym = q.get("symbol")
                if sym:
                    out.append({
                        "symbol": sym,
                        "name": q.get("description") or "",
                        "type": q.get("type") or "",
                        "exchange": "",
                    })
        except Exception:
            pass
    out.sort(key=lambda it: -_sym_rank(it, query))
    return out

def _stooq_history(ticker, interval):
    """Schluesselfreie zweite Quelle (Stooq) fuer Tages-/Wochenhistorie.
    Best-effort, v.a. fuer US-Titer ohne Boersen-Suffix."""
    if requests is None or interval not in ("1d", "1wk", "1mo"):
        return None
    sym = ticker.lower()
    if "." not in sym:
        sym = f"{sym}.us"
    imap = {"1d": "d", "1wk": "w", "1mo": "m"}
    try:
        import pandas as pd
        import io
        url = f"https://stooq.com/q/d/l/?s={sym}&i={imap[interval]}"
        r = requests.get(url, timeout=12, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code != 200 or not r.text or "Date" not in r.text[:50]:
            return None
        df = pd.read_csv(io.StringIO(r.text))
        if df.empty or "Close" not in df.columns:
            return None
        df["Date"] = pd.to_datetime(df["Date"])
        return df.set_index("Date")[["Close"]]
    except Exception:
        return None


def _stooq_last(ticker):
    """Letzter Tagesschluss von Stooq (dritte Preisquelle, letzte Absicherung)."""
    h = _stooq_history(ticker, "1d")
    try:
        if h is not None and not h.empty:
            return float(h["Close"].dropna().iloc[-1])
    except Exception:
        return None
    return None


def get_intraday_quote(ticker: str, native_currency: str = "USD"):
    """Aktuellster Intraday-Kurs als (preis, waehrung).
    Waehrend der deutschen Handelszeit (9:00-15:30), solange die US-Boerse noch
    geschlossen ist, wird ZUERST die deutsche Notierung (Frankfurt .F / Xetra .DE,
    in EUR) genutzt -> Kurse bewegen sich schon morgens. Sonst US-Kurs (native).
    None-Preis, wenn nichts verfuegbar."""
    import datetime as dt
    try:
        from zoneinfo import ZoneInfo
        now = dt.datetime.now(ZoneInfo("Europe/Berlin"))
    except Exception:
        now = dt.datetime.now()
    minutes = now.hour * 60 + now.minute
    us_regular = 15 * 60 + 30 <= minutes <= 22 * 60      # grob US-Regulaerhandel (dt. Zeit)
    de_hours = 9 * 60 <= minutes < 15 * 60 + 30          # dt. Boerse offen, US noch zu

    def _us_price():
        # Tiingo IEX zuerst (saubere US-Intraday-Referenz), dann yfinance, dann Finnhub.
        if "." not in ticker:
            try:
                tpx, _ = _tiingo_iex(ticker)
                if tpx and tpx > 0:
                    return tpx
            except Exception:
                pass
        if yf is not None:
            try:                                          # inkl. Pre/Post-Market
                h = yf.Ticker(ticker).history(period="1d", interval="1m", prepost=True)
                if h is not None and not h.empty:
                    last = h["Close"].dropna()
                    if len(last) and float(last.iloc[-1]) > 0:
                        return float(last.iloc[-1])
            except Exception:
                pass
        q = _fh("quote", {"symbol": ticker})
        if q and q.get("c"):
            try:
                c = float(q["c"])
                if c > 0:
                    return c
            except Exception:
                pass
        return None

    def _de_price():
        # Nur fuer Ticker ohne Boersen-Suffix (US-Titel). Best effort: die deutsche
        # Yahoo-Notierung heisst nicht immer TICKER.F (Apple=APC.F) -> greift daher
        # nicht bei jedem US-Titel, ist aber ein sicherer, kostenloser Versuch.
        if "." in ticker or yf is None:
            return None
        for suf in (".F", ".DE"):
            try:
                h = yf.Ticker(ticker + suf).history(period="1d", interval="5m")
                if h is not None and not h.empty:
                    last = h["Close"].dropna()
                    if len(last) and float(last.iloc[-1]) > 0:
                        return float(last.iloc[-1])
            except Exception:
                continue
        return None

    def _fertig(preis, waehrung):
        # Pence-Normalisierung auch fuer den Live-Kurs. Ohne das zeigte das
        # Portfolio den rohen Pence-Wert (BP.L: 645 statt 6,45) - der Basis-
        # Kurs aus get_fundamentals ist laengst normalisiert, der Live-Kurs
        # lief hier vorbei. Die deutsche Notierung (EUR) ist nie betroffen.
        if preis and waehrung != "EUR" and is_pence(ticker):
            return preis / 100.0, "GBP"
        return preis, waehrung

    if de_hours and not us_regular:            # deutscher Vormittag -> DE-Kurs zuerst
        p = _de_price()
        if p:
            return p, "EUR"
        p = _us_price()
        return _fertig(p, native_currency) if p else (None, native_currency)
    p = _us_price()
    if p:
        return _fertig(p, native_currency)
    p = _de_price()
    return (p, "EUR") if p else (None, native_currency)


def get_intraday_price(ticker: str) -> Optional[float]:
    """Rueckwaertskompatibel: nur der Preis (native Waehrung)."""
    return get_intraday_quote(ticker)[0]


_CCY_CACHE = {}            # Ticker -> Originalwaehrung (z.B. "GBp", "USD")


def is_pence(ticker: str) -> bool:
    """Notiert dieser Ticker in Pence (GBp/GBX)?

    Wird gebraucht, weil get_fundamentals die Kursseite auf Pfund normalisiert,
    die Kurshistorie und Quotes aber ROH aus yfinance kommen. Ohne diese
    Vereinheitlichung mischt man Pfund- und Pence-Kurse - genau daraus
    entstanden Renditen von +9900 % in der Trefferbilanz (Faktor 100).
    """
    if not ticker:
        return False
    # Ein Kuerzel OHNE Boersensuffix ist die US-Notierung (USD). Pence gibt
    # es nur an britischen Boersen, und die tragen immer ein Suffix (.L/.IL).
    # Ohne diesen Kurzschluss koennte yfinance fuer ein mehrfach vergebenes
    # Kuerzel (PRU: NYSE und LSE) die Londoner Waehrung GBp zurueckgeben und
    # den US-Kurs faelschlich durch 100 teilen.
    if "." not in ticker:
        return False
    cur = _CCY_CACHE.get(ticker)
    if cur is None:
        cur = ""
        if yf is not None:
            try:                                   # leichtgewichtig, kein voller info-Abruf
                fi = yf.Ticker(ticker).fast_info
                cur = (getattr(fi, "currency", None)
                       or (fi.get("currency") if hasattr(fi, "get") else "") or "")
            except Exception:
                cur = ""
        _CCY_CACHE[ticker] = cur
    return str(cur).strip() in ("GBp", "GBX", "gbx")


def normalise_price(ticker: str, px):
    """Einzelkurs auf dieselbe Einheit bringen wie get_fundamentals (Pfund)."""
    try:
        px = float(px)
    except (TypeError, ValueError):
        return None
    return px / 100.0 if is_pence(ticker) else px


def get_price_history(ticker: str, period: str = "1y", interval: str = "1d"):
    h = None
    if yf is not None:
        try:
            h = yf.Ticker(ticker).history(period=period, interval=interval)
        except Exception:
            h = None
    if h is None or getattr(h, "empty", True):
        h = _stooq_history(ticker, interval)      # zweite Quelle als Fallback
    # Pence -> Pfund, damit Historie und Fundamentaldaten dieselbe Einheit haben
    if h is not None and not getattr(h, "empty", True) and is_pence(ticker):
        try:
            for col in ("Open", "High", "Low", "Close", "Adj Close"):
                if col in h.columns:
                    h[col] = h[col] / 100.0
        except Exception:
            pass
    return h


def get_fx_to_eur(currency: str):
    """
    Multiplikator, um einen Betrag in 'currency' nach EUR umzurechnen.
    EUR -> 1.0. Pence (GBp/GBX) -> 0.01 * GBP-Kurs. Mehrere Quellen:
    yfinance zuerst, dann EZB/Frankfurter (schluesselfrei). Fehler -> None.
    """
    if not currency:
        return 1.0
    cur = currency.upper()
    pence = 1.0
    if cur in ("GBP", "GBX") or currency == "GBp":
        if currency in ("GBp", "GBX") or cur == "GBX":
            pence = 0.01
        cur = "GBP"
    if cur == "EUR":
        return 1.0 * pence
    rate = None
    if yf is not None:                                  # Quelle 1: yfinance
        try:
            h = yf.Ticker(f"{cur}EUR=X").history(period="5d")
            rate = float(h["Close"].dropna().iloc[-1])
        except Exception:
            rate = None
    if rate is None and requests is not None:           # Quelle 2: EZB / Frankfurter
        try:
            r = requests.get("https://api.frankfurter.app/latest",
                             params={"from": cur, "to": "EUR"}, timeout=10)
            if r.status_code == 200:
                rate = _num(r.json().get("rates", {}).get("EUR"))
        except Exception:
            rate = None
    return rate * pence if rate else None


def get_performance(ticker: str) -> dict:
    """Kursveraenderung 6M / 1J / YTD in % aus einem History-Abruf."""
    h = get_price_history(ticker, period="1y", interval="1d")
    if h is None or getattr(h, "empty", True):
        return {}
    try:
        import pandas as pd
        close = h["Close"].dropna()
        if close.empty:
            return {}
        idx = close.index
        try:
            idx = idx.tz_localize(None)
        except Exception:
            try:
                idx = idx.tz_convert(None)
            except Exception:
                pass
        close.index = idx
        last = float(close.iloc[-1])

        def pct(ref):
            ref = float(ref)
            return (last / ref - 1) * 100 if ref else None

        out = {"ch_1y": pct(close.iloc[0])}
        c6 = close[close.index >= (close.index[-1] - pd.Timedelta(days=182))]
        out["ch_6m"] = pct(c6.iloc[0]) if len(c6) else None
        ystart = pd.Timestamp(year=close.index[-1].year, month=1, day=1)
        cy = close[close.index >= ystart]
        out["ch_ytd"] = pct(cy.iloc[0]) if len(cy) else None
        return out
    except Exception:
        return {}


def get_rating_changes(ticker: str, limit: int = 8):
    """Analysten-Rating-Aenderungen (Upgrade/Downgrade) je Bank mit Datum.
    Quelle: Finnhub 'stock/upgrade-downgrade' - roic bietet diese
    Meinungs-Daten NICHT an, daher zwingend Finnhub. Gibt eine Liste von
    {datum, firma, von, zu, aktion} zurueck (neueste zuerst) oder None, wenn
    der Finnhub-Zugang das nicht liefert (Plan-abhaengig)."""
    d = _fh("stock/upgrade-downgrade", {"symbol": ticker})
    if not isinstance(d, list) or not d:
        return None
    out = []
    for e in d[:limit]:
        try:
            _ts = e.get("gradeTime")
            _datum = ""
            if _ts:
                import datetime as _dt
                _datum = _dt.datetime.utcfromtimestamp(int(_ts)).strftime("%d.%m.%Y")
            out.append({
                "datum": _datum,
                "firma": e.get("company") or "",
                "von": e.get("fromGrade") or "",
                "zu": e.get("toGrade") or "",
                "aktion": e.get("action") or ""})     # up/down/init/maintain
        except Exception:
            continue
    return out or None


def get_analyst_ratings(ticker: str):
    """Analystenrating als {buy, hold, sell}. Finnhub bevorzugt, sonst yfinance."""
    rev = get_estimate_revisions(ticker)
    if rev:
        return {"buy": (rev.get("strongBuy") or 0) + (rev.get("buy") or 0),
                "hold": rev.get("hold") or 0,
                "sell": (rev.get("sell") or 0) + (rev.get("strongSell") or 0)}
    if yf is None:
        return None
    try:
        rec = yf.Ticker(ticker).recommendations
        if rec is None or len(rec) == 0:
            return None
        if "period" in getattr(rec, "columns", []):
            m = rec[rec["period"] == "0m"]
            row = m.iloc[0] if len(m) else rec.iloc[0]
        else:
            row = rec.iloc[-1]

        def g(k):
            try:
                return int(row.get(k, 0) or 0)
            except Exception:
                return 0
        return {"buy": g("strongBuy") + g("buy"), "hold": g("hold"),
                "sell": g("sell") + g("strongSell")}
    except Exception:
        return None


# ---------------------------------------------------------------------------
# News / Intel
# ---------------------------------------------------------------------------
def get_financials(ticker: str) -> dict:
    """Mehrjahres-Finanzdaten fuer Trend-Kriterien (recent first)."""
    out = {"revenue": [], "gross_margin": [], "fcf": [], "net_income": None}
    if yf is None:
        return out
    try:
        tk = yf.Ticker(ticker)
        fin, cf = tk.financials, tk.cashflow

        def row(df, *names):
            for n in names:
                try:
                    if df is not None and n in df.index:
                        return [None if v is None else float(v) for v in df.loc[n].values]
                except Exception:
                    pass
            return []

        rev = row(fin, "Total Revenue")
        gp = row(fin, "Gross Profit")
        ni = row(fin, "Net Income", "Net Income Common Stockholders")
        out["revenue"] = [x for x in rev if x is not None]
        if rev and gp and len(rev) == len(gp):
            out["gross_margin"] = [g / r for g, r in zip(gp, rev) if r]
        if ni and ni[0] is not None:
            out["net_income"] = ni[0]
        fcf = row(cf, "Free Cash Flow")
        if not fcf:
            ocf = row(cf, "Operating Cash Flow", "Total Cash From Operating Activities")
            cap = row(cf, "Capital Expenditure")
            if ocf and cap and len(ocf) == len(cap):
                fcf = [o + c for o, c in zip(ocf, cap)]  # CapEx ist negativ
        out["fcf"] = [x for x in fcf if x is not None]
        return out
    except Exception:
        return out


def get_last_earnings_surprise(ticker: str):
    """'beat' / 'inline' / 'miss' aus der letzten berichteten EPS-Ueberraschung."""
    if yf is None:
        return None
    try:
        ed = yf.Ticker(ticker).earnings_dates
        if ed is None or ed.empty:
            return None
        cols = list(ed.columns)
        rep = ed.dropna(subset=["Reported EPS"]) if "Reported EPS" in cols else ed.dropna()
        if rep.empty:
            return None
        last = rep.iloc[0]
        sp = last.get("Surprise(%)") if "Surprise(%)" in cols else None
        if sp is None and "EPS Estimate" in cols and "Reported EPS" in cols:
            est, act = last.get("EPS Estimate"), last.get("Reported EPS")
            sp = ((act - est) / abs(est) * 100) if est else None
        if sp is None:
            return None
        sp = float(sp)
        return "beat" if sp > 1 else ("miss" if sp < -1 else "inline")
    except Exception:
        return None


def get_technicals(ticker: str) -> dict:
    """RSI(14), SMA20/50/200, Distanz zu SMA200, Volumen-/Strukturtrend."""
    out = {}
    h = get_price_history(ticker, period="1y", interval="1d")
    if h is None or getattr(h, "empty", True):
        return out
    try:
        close = h["Close"].dropna()
        if len(close) < 20:
            return out
        price = float(close.iloc[-1])
        out["price"] = price
        d = close.diff()
        gain = d.clip(lower=0).rolling(14).mean()
        loss = (-d.clip(upper=0)).rolling(14).mean().replace(0, 1e-9)
        rsi = 100 - 100 / (1 + gain / loss)
        if rsi.notna().sum() > 1:
            out["rsi"] = float(rsi.iloc[-1])
            out["rsi_rising"] = bool(rsi.iloc[-1] > rsi.iloc[-2])
        for n in (20, 50, 200):
            out[f"sma{n}"] = float(close.rolling(n).mean().iloc[-1]) if len(close) >= n else None
        s200 = out.get("sma200")
        out["dist_sma200"] = (price / s200 - 1) if s200 else None
        if "Volume" in h.columns:
            vol = h["Volume"].reindex(close.index).fillna(0)
            sgn = close.diff().apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))
            obv = (sgn * vol).cumsum()
            if len(obv) > 60:
                base = abs(obv.iloc[-60]) or 1
                r = (obv.iloc[-1] - obv.iloc[-60]) / base
                out["obv_trend"] = "up" if r > 0.05 else ("down" if r < -0.05 else "flat")
        if len(close) >= 120:
            half = close.iloc[-120:]
            a, b = half.iloc[:60].min(), half.iloc[60:].min()
            out["structure"] = ("higher_low" if b > a * 1.01
                                else "lower_low" if b < a * 0.99 else "sideways")
        return out
    except Exception:
        return out


NEWS_SITES = ["finance.yahoo.com", "investing.com", "onvista.de", "marketscreener.com"]
_ALLOWED_KEYS = ["yahoo", "investing", "onvista", "marketscreener"]


def _allowed_source(src) -> bool:
    s = (src or "").lower()
    return any(k in s for k in _ALLOWED_KEYS)


def _clean_name(name):
    """Firmensuffixe entfernen, damit die News-Suche besser greift."""
    if not name:
        return name
    s = name
    for suf in [", Inc.", " Inc.", " Inc", " Corporation", " Corp.", " Corp",
                " plc", " PLC", " S.A.", " AG", " SE", " N.V.", " NV", " Co.",
                " Company", " Ltd.", " Ltd", " Holdings", " Group", " (The)", ","]:
        s = s.replace(suf, "")
    return s.strip() or name


def _google_news_rss(query, limit):
    """Google-News-RSS: breit anfragen, danach nach erlaubten Quellen filtern
    (inkl. Subdomains wie de.investing.com via Quellen-URL)."""
    if requests is None or not query:
        return []
    try:
        import xml.etree.ElementTree as ET
        url = ("https://news.google.com/rss/search?q="
               + requests.utils.quote(f"{query} Aktie OR stock OR shares")
               + "&hl=de&gl=DE&ceid=DE:de")
        r = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        root = ET.fromstring(r.content)
        out = []
        for it in root.findall(".//item"):
            src = it.find("source")
            sname = src.text if src is not None else ""
            surl = src.get("url") if src is not None else ""
            if not (_allowed_source(sname) or _allowed_source(surl)):
                continue
            out.append({"headline": it.findtext("title"), "url": it.findtext("link"),
                        "source": sname or "News", "datetime": it.findtext("pubDate"),
                        "summary": None})
            if len(out) >= limit:
                break
        return out
    except Exception:
        return []


def _yf_news_filtered(ticker, limit):
    """yfinance-News, gefiltert auf die erlaubten Portale (Schema-robust)."""
    if yf is None:
        return []
    try:
        raw = yf.Ticker(ticker).news or []
    except Exception:
        return []
    out = []
    for n in raw:
        c = n.get("content") if isinstance(n.get("content"), dict) else None
        if c:
            url = (c.get("canonicalUrl") or {}).get("url") \
                or (c.get("clickThroughUrl") or {}).get("url")
            item = {"headline": c.get("title"), "url": url,
                    "source": (c.get("provider") or {}).get("displayName"),
                    "datetime": c.get("pubDate"), "summary": c.get("summary")}
        else:
            item = {"headline": n.get("title"), "url": n.get("link"),
                    "source": n.get("publisher"),
                    "datetime": n.get("providerPublishTime"), "summary": None}
        if item.get("headline") and _allowed_source(item.get("source")):
            out.append(item)
        if len(out) >= limit:
            break
    return out


def get_news(ticker: str, limit: int = 12, name: str = None) -> list[dict]:
    """Nur etablierte Portale: Yahoo Finance, Investing.com, onvista.de, marketscreener.com."""
    query = _clean_name(name) if name else ticker
    items = _google_news_rss(query, limit)
    if len(items) < limit:
        seen = {i["headline"] for i in items}
        for it in _yf_news_filtered(ticker, limit):
            if it["headline"] not in seen:
                items.append(it)
                seen.add(it["headline"])
    return items[:limit]


def get_peers(ticker: str) -> list[str]:
    """Wettbewerber/Peers. Finnhub bevorzugt, sonst leer."""
    if config.FINNHUB_API_KEY and requests is not None:
        try:
            r = requests.get("https://finnhub.io/api/v1/stock/peers",
                             params={"symbol": ticker.upper(),
                                     "token": config.FINNHUB_API_KEY}, timeout=15)
            peers = r.json()
            return [p for p in peers if p != ticker.upper()][:12]
        except Exception:
            pass
    return []


def get_supply_chain(ticker: str) -> dict[str, list]:
    """
    Kunden/Lieferanten. ECHTE Supply-Chain-Graphen sind institutionelle
    Premiumdaten (Bloomberg SPLC / FactSet). Hier: Best-Effort über Finnhub
    Premium-Endpoint, falls verfügbar. Sonst leer -> im Report ehrlich kennzeichnen.
    """
    result = {"customers": [], "suppliers": []}
    if config.FINNHUB_API_KEY and requests is not None:
        try:
            r = requests.get("https://finnhub.io/api/v1/stock/supply-chain",
                             params={"symbol": ticker.upper(),
                                     "token": config.FINNHUB_API_KEY}, timeout=15)
            data = r.json()
            for item in data.get("data", []):
                rel = (item.get("relationship") or "").lower()
                sym = item.get("symbol") or item.get("companyName")
                if "customer" in rel:
                    result["customers"].append(sym)
                elif "supplier" in rel:
                    result["suppliers"].append(sym)
        except Exception:
            pass
    return result


def get_estimate_revisions(ticker: str) -> Optional[dict]:
    """Schätzungs-Trend (Frühindikator). Finnhub recommendation/earnings trend."""
    if config.FINNHUB_API_KEY and requests is not None:
        try:
            r = requests.get("https://finnhub.io/api/v1/stock/recommendation",
                             params={"symbol": ticker.upper(),
                                     "token": config.FINNHUB_API_KEY}, timeout=15)
            data = r.json()
            if data:
                latest = data[0]
                return {"period": latest.get("period"),
                        "strongBuy": latest.get("strongBuy"),
                        "buy": latest.get("buy"), "hold": latest.get("hold"),
                        "sell": latest.get("sell"),
                        "strongSell": latest.get("strongSell")}
        except Exception:
            pass
    return None


def get_insider_activity(ticker: str) -> Optional[dict]:
    """Insider-Transaktionen (Frühsignal). Finnhub."""
    if config.FINNHUB_API_KEY and requests is not None:
        try:
            r = requests.get("https://finnhub.io/api/v1/stock/insider-transactions",
                             params={"symbol": ticker.upper(),
                                     "token": config.FINNHUB_API_KEY}, timeout=15)
            data = r.json().get("data", [])
            buys = sum(1 for x in data if (x.get("change") or 0) > 0)
            sells = sum(1 for x in data if (x.get("change") or 0) < 0)
            return {"recent_buys": buys, "recent_sells": sells, "n": len(data)}
        except Exception:
            pass
    return None


def get_signal_extras(ticker: str) -> dict:
    """Schwerere Signale fuer die Scoring-Matrizen (best effort, alles guarded):
    Mehrjahres-Reihen (Umsatz/Bruttogewinn/Nettogewinn/FCF), letzte Earnings,
    EPS-Revisionen, Analysten-Trend, Short-Interest."""
    out = {"revenue": None, "gross_profit": None, "net_income": None, "fcf": None,
           "last_earnings": {}, "eps_rev": {}, "rec_trend": {},
           "short_pct_float": None, "shares_short": None, "shares_short_prior": None}
    if yf is None:
        return out
    try:
        tk = yf.Ticker(ticker)
    except Exception:
        return out

    try:
        inc = tk.income_stmt
    except Exception:
        inc = None
    try:
        cf = tk.cashflow
    except Exception:
        cf = None

    def row(df, *names):
        try:
            if df is None or getattr(df, "empty", True):
                return None
            for n in names:
                if n in df.index:
                    s = df.loc[n].dropna()
                    vals = [_num(x) for x in s.values]
                    vals = [x for x in vals if x is not None]
                    return vals or None       # neueste zuerst
        except Exception:
            pass
        return None

    out["revenue"] = row(inc, "Total Revenue", "TotalRevenue")
    out["gross_profit"] = row(inc, "Gross Profit", "GrossProfit")
    out["net_income"] = row(inc, "Net Income", "NetIncome",
                            "Net Income Common Stockholders")

    # --- roic bevorzugen: yfinance liefert meist nur 4 Geschaeftsjahre,
    #     roic zehn. Die Matrizen bewerten Trends ueber mehrere Jahre -
    #     mit vier Punkten ist ein "Trend" kaum mehr als Rauschen.
    if _roic is not None and _roic.covers(ticker):
        try:
            _fin = _roic.financials(ticker, "income", "annual", 10)
            if _fin and len(_fin) >= 4:
                def _reihe(feld):
                    v = []
                    for z in _fin:                    # roic: neueste zuerst
                        x = z.get(feld)
                        try:
                            x = float(x) if x is not None else None
                        except Exception:
                            x = None
                        if x is not None:
                            v.append(x)
                    return v or None
                _r = _reihe("is_sales_revenue_turnover")
                _g = _reihe("is_gross_profit")
                _n = _reihe("is_net_income")
                # NUR ALS SATZ ersetzen. Einzeln zu tauschen waere ein
                # ernster Fehler: matrices rechnet gross_profit[0]/revenue[0]
                # - stammen die aus verschiedenen Quellen, koennen sich die
                # Geschaeftsjahre unterscheiden und die Bruttomarge ist falsch.
                if _r and _g and _n and len(_r) == len(_g) == len(_n):
                    out["revenue"], out["gross_profit"] = _r, _g
                    out["net_income"] = _n
                    out["_jahre_quelle"] = "roic"
                    out["_jahre_n"] = len(_r)
        except Exception:
            pass
    fcf = row(cf, "Free Cash Flow", "FreeCashFlow")
    if fcf is None:
        ocf = row(cf, "Operating Cash Flow", "OperatingCashFlow",
                  "Total Cash From Operating Activities")
        cap = row(cf, "Capital Expenditure", "CapitalExpenditures")
        if ocf and cap and len(ocf) == len(cap):
            fcf = [o + c for o, c in zip(ocf, cap)]   # Capex ist negativ
    out["fcf"] = fcf

    # FCF ebenfalls aus roic, wenn verfuegbar (laengere Reihe)
    if _roic is not None and _roic.covers(ticker):
        try:
            _cf = _roic.financials(ticker, "cashflow", "annual", 10)
            _v = []
            for z in (_cf or []):
                x = z.get("cf_free_cash_flow")
                try:
                    x = float(x) if x is not None else None
                except Exception:
                    x = None
                if x is not None:
                    _v.append(x)
            # nur uebernehmen, wenn auch die GuV aus roic kam - sonst
            # koennten fcf und net_income aus verschiedenen Jahren stammen
            # (fcf_conversion = fcf[0] / net_income[0])
            if len(_v) >= 4 and out.get("_jahre_quelle") == "roic":
                out["fcf"] = _v
        except Exception:
            pass

    try:
        info = tk.info
        out["short_pct_float"] = _num(info.get("shortPercentOfFloat"))
        out["shares_short"] = _num(info.get("sharesShort"))
        out["shares_short_prior"] = _num(info.get("sharesShortPriorMonth"))
    except Exception:
        pass

    try:
        df = tk.get_earnings_dates(limit=8)
        if df is not None and not df.empty and "Reported EPS" in df.columns:
            past = df[df["Reported EPS"].notna()]
            if not past.empty:
                r = past.iloc[0]
                out["last_earnings"] = {"estimate": _num(r.get("EPS Estimate")),
                                        "reported": _num(r.get("Reported EPS")),
                                        "surprise_pct": _num(r.get("Surprise(%)"))}
    except Exception:
        pass

    try:
        rv = getattr(tk, "eps_revisions", None)
        if rv is not None and not rv.empty:
            r = rv.iloc[0]
            out["eps_rev"] = {"up": _num(r.get("upLast30days")) or 0,
                              "down": _num(r.get("downLast30days")) or 0}
    except Exception:
        pass

    try:
        rec = tk.recommendations
        if rec is not None and len(rec) > 0 and "period" in rec.columns:
            def net(rw):
                g = lambda k: int(rw.get(k, 0) or 0)
                return g("strongBuy") + g("buy") - g("sell") - g("strongSell")
            cur = rec[rec["period"] == "0m"]
            prev = rec[rec["period"].isin(["-2m", "-3m"])]
            if len(cur):
                out["rec_trend"] = {"net_now": net(cur.iloc[0]),
                                    "net_prev": net(prev.iloc[0]) if len(prev) else None}
    except Exception:
        pass

    return out


# ===========================================================================
# RADAR-Datenquellen (Events, Schaetzungen, Insider) - kostenlos, erweiterbar
# ===========================================================================
_CIK_CACHE = None
_SEC_UA = {"User-Agent": "ValueRadar research tool contact@example.com"}


def get_cik_map():
    """Ticker -> 10-stellige CIK (einmalig von SEC geladen, gecached)."""
    global _CIK_CACHE
    if _CIK_CACHE is not None:
        return _CIK_CACHE
    if requests is None:
        return {}
    try:
        r = requests.get("https://www.sec.gov/files/company_tickers.json",
                         headers=_SEC_UA, timeout=20)
        m = {}
        for v in r.json().values():
            t, cik = v.get("ticker"), v.get("cik_str")
            if t and cik is not None:
                m[t.upper()] = str(cik).zfill(10)
        _CIK_CACHE = m
        return m
    except Exception:
        return {}


# 8-K Item-Codes -> Bedeutung (Auswahl der relevanten Katalysatoren)
SEC_ITEM_LABELS = {
    "1.01": "Wesentliche Vereinbarung (Vertrag/Kooperation)",
    "2.01": "Abschluss \u00dcbernahme/Verkauf",
    "1.02": "Vertrag beendet",
    "2.02": "Quartalszahlen",
    "5.02": "Management-Wechsel",
    "7.01": "Reg-FD-Mitteilung",
    "8.01": "Sonstiges wesentliches Ereignis",
    "3.02": "Kapitalerh\u00f6hung",
}


def get_recent_8k(ticker, days=90):
    """Aktuelle 8-K-Meldungen (US) mit Item-Codes. [] wenn keine/CIK fehlt."""
    cik = get_cik_map().get(ticker.upper())
    if not cik or requests is None:
        return []
    try:
        import datetime as dt
        r = requests.get(f"https://data.sec.gov/submissions/CIK{cik}.json",
                         headers=_SEC_UA, timeout=20)
        rec = r.json().get("filings", {}).get("recent", {})
        forms = rec.get("form", [])
        dates = rec.get("filingDate", [])
        items = rec.get("items", [])
        cutoff = dt.date.today() - dt.timedelta(days=days)
        out = []
        for i, fm in enumerate(forms):
            if fm != "8-K":
                continue
            d = dates[i] if i < len(dates) else ""
            try:
                if dt.date.fromisoformat(d) < cutoff:
                    continue
            except Exception:
                pass
            codes = [c.strip() for c in (items[i] if i < len(items) else "").replace(";", ",").split(",") if c.strip()]
            out.append({"date": d, "items": codes})
        return out
    except Exception:
        return []


def get_event_news(name, limit=25):
    """Breite News-Headlines (alle Quellen) fuer die Katalysator-Stichwortsuche."""
    if requests is None or not name:
        return []
    try:
        import xml.etree.ElementTree as ET
        url = ("https://news.google.com/rss/search?q="
               + requests.utils.quote(_clean_name(name))
               + "&hl=de&gl=DE&ceid=DE:de")
        r = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        root = ET.fromstring(r.content)
        return [(it.findtext("title") or "") for it in root.findall(".//item")[:limit]]
    except Exception:
        return []


def get_eps_revision_light(ticker):
    """Nur EPS-Revisionen (leichter Abruf, ohne Bilanz/GuV)."""
    if yf is None:
        return {}
    try:
        rv = getattr(yf.Ticker(ticker), "eps_revisions", None)
        if rv is not None and not rv.empty:
            r = rv.iloc[0]
            return {"up": _num(r.get("upLast30days")) or 0,
                    "down": _num(r.get("downLast30days")) or 0}
    except Exception:
        pass
    return {}


def get_insider_light(ticker):
    """Insider-Kaeufe/-Verkaeufe. Finnhub bevorzugt, sonst yfinance (best effort)."""
    fh = get_insider_activity(ticker)
    if fh and fh.get("n"):
        return {"buys": fh.get("recent_buys", 0), "sells": fh.get("recent_sells", 0)}
    if yf is None:
        return {}
    try:
        ip = yf.Ticker(ticker).insider_purchases
        if ip is not None and not ip.empty:
            buys = sells = 0
            col0 = ip.iloc[:, 0].astype(str).str.lower()
            shares = ip.iloc[:, 1]
            for lbl, val in zip(col0, shares):
                v = _num(val) or 0
                if "purchase" in lbl:
                    buys = int(v)
                elif "sale" in lbl:
                    sells = int(v)
            if buys or sells:
                return {"buys": buys, "sells": sells}
    except Exception:
        pass
    return {}


# ===========================================================================
# Screener-Zusatzdaten: Technik + Performance aus EINEM History-Abruf
# ===========================================================================
def get_screen_extras(ticker: str) -> dict:
    """Liefert Performance (1M/6M/12M/YTD), SMA200-Abstand, RSI(14), 52W-Position
    und ob die Aktie nach einem Rueckgang einen Boden gebildet hat."""
    out = {"ch_1m": None, "ch_6m": None, "ch_1y": None, "ch_ytd": None,
           "above_sma200": None, "sma200_gap": None, "rsi": None,
           "pct_from_low": None, "drawdown": None, "base_formed": None}
    h = get_price_history(ticker, period="1y", interval="1d")
    if h is None or getattr(h, "empty", True):
        return out
    try:
        import pandas as pd
        c = h["Close"].dropna()
        if len(c) < 30:
            return out
        try:
            c.index = c.index.tz_localize(None)
        except Exception:
            try:
                c.index = c.index.tz_convert(None)
            except Exception:
                pass
        last = float(c.iloc[-1])

        def pct(ref):
            ref = float(ref)
            return round((last / ref - 1) * 100, 1) if ref else None

        out["ch_1y"] = pct(c.iloc[0])
        for key, days in (("ch_1m", 30), ("ch_6m", 182)):
            seg = c[c.index >= (c.index[-1] - pd.Timedelta(days=days))]
            out[key] = pct(seg.iloc[0]) if len(seg) else None
        ystart = pd.Timestamp(year=c.index[-1].year, month=1, day=1)
        cy = c[c.index >= ystart]
        out["ch_ytd"] = pct(cy.iloc[0]) if len(cy) else None

        sma200 = float(c.tail(200).mean())
        out["above_sma200"] = bool(last >= sma200)
        out["sma200_gap"] = round((last / sma200 - 1) * 100, 1) if sma200 else None

        delta = c.diff().dropna()
        up = delta.clip(lower=0).tail(14).mean()
        dn = (-delta.clip(upper=0)).tail(14).mean()
        if dn and dn > 0:
            rs = up / dn
            out["rsi"] = round(100 - 100 / (1 + rs), 1)
        elif up and up > 0:
            out["rsi"] = 100.0

        hi = float(c.max())
        lo = float(c.min())
        out["pct_from_low"] = round((last / lo - 1) * 100, 1) if lo else None
        out["drawdown"] = round((last / hi - 1) * 100, 1) if hi else None

        # Bodenbildung: in 12M >15% gefallen, aber letzte ~3 Monate stabilisiert
        # (juengster Tiefpunkt-Abstand klein, geringe Schwankung ueber dem Tief)
        recent = c.tail(63)
        rmin = float(recent.min())
        stab = (last / rmin - 1) if rmin else None
        out["base_formed"] = bool(out["drawdown"] is not None and out["drawdown"] < -15
                                  and stab is not None and stab < 0.18 and last >= rmin)
        return out
    except Exception:
        return out


def get_dividend_years(ticker: str) -> Optional[int]:
    """Anzahl der Kalenderjahre mit Dividendenzahlung (max. ~12 Jahre Historie)."""
    try:
        import yfinance as yf
        div = yf.Ticker(ticker).dividends
        if div is None or getattr(div, "empty", True):
            return 0
        years = {d.year for d in div.index}
        return len(years)
    except Exception:
        return None


def get_earnings_history(ticker: str, limit: int = 12) -> list:
    """Earnings-Historie mit EPS-Schaetzung/Ist/Surprise UND der Kursreaktion
    am Tag nach dem Bericht. Fuer das 'Does the Beat Get Paid'-Streudiagramm
    und die Ergebnis-Tabelle.

    Kursreaktion = Schlusskurs am ersten Handelstag NACH dem Earnings-Datum
    gegen den Schlusskurs am letzten Tag DAVOR. Gibt eine Liste (neueste zuerst)
    von Dicts zurueck: {datum, eps_actual, eps_est, eps_surprise_pct,
    price_reaction_pct}. Leere Liste bei fehlenden Daten.
    """
    if yf is None or not ticker:
        return []
    import pandas as pd
    try:
        tk = yf.Ticker(ticker)
        df = tk.get_earnings_dates(limit=limit)
    except Exception:
        return []
    if df is None or getattr(df, "empty", True):
        return []
    if "Reported EPS" not in df.columns:
        return []
    # nur bereits berichtete Quartale (Reported EPS vorhanden)
    past = df[df["Reported EPS"].notna()].copy()
    if past.empty:
        return []
    # Kurshistorie einmal breit holen, dann je Datum die Reaktion bestimmen
    try:
        _hist = tk.history(period="5y", interval="1d")
    except Exception:
        _hist = None
    if _hist is not None and is_pence(ticker) and "Close" in _hist.columns:
        try:
            _hist = _hist.copy()
            _hist["Close"] = _hist["Close"] / 100.0
        except Exception:
            pass

    def _reaktion(edate):
        if _hist is None or getattr(_hist, "empty", True):
            return None
        try:
            idx = [x.date() for x in _hist.index]
            close = _hist["Close"].tolist()
            d = pd.to_datetime(edate).date()
            vor = [(dt, c) for dt, c in zip(idx, close) if dt <= d and c == c]
            nach = [(dt, c) for dt, c in zip(idx, close) if dt > d and c == c]
            if not vor or not nach:
                return None
            p_vor = vor[-1][1]
            p_nach = nach[0][1]
            if p_vor and p_vor > 0:
                return round((p_nach / p_vor - 1) * 100, 2)
        except Exception:
            return None
        return None

    out = []
    for edate, r in past.iterrows():
        est = _num(r.get("EPS Estimate"))
        act = _num(r.get("Reported EPS"))
        sp = _num(r.get("Surprise(%)"))
        if sp is None and est not in (None, 0) and act is not None:
            sp = round((act - est) / abs(est) * 100, 1)
        out.append({
            "datum": pd.to_datetime(edate).strftime("%Y-%m-%d"),
            "eps_actual": act, "eps_est": est,
            "eps_surprise_pct": sp,
            "price_reaction_pct": _reaktion(edate),
        })
    return out


def get_price_on(ticker: str, date) -> Optional[float]:
    """Schlusskurs am/zuletzt vor 'date' (YYYY-MM-DD oder Datum). None bei Fehler.
    Genutzt fuer Gewinn/Verlust seit Kauf im Portfoliocheck."""
    if yf is None or not ticker or not date:
        return None
    try:
        import pandas as pd
        from datetime import timedelta
        d = pd.to_datetime(date).date()
        start = (d - timedelta(days=8)).isoformat()
        end = (d + timedelta(days=5)).isoformat()
        h = yf.Ticker(ticker).history(start=start, end=end)
        if h is None or h.empty:
            return None
        idx_dates = [x.date() for x in h.index]
        before = [c for dt, c in zip(idx_dates, h["Close"].tolist()) if dt <= d and c == c]
        if before:
            return float(before[-1])
        after = [c for c in h["Close"].tolist() if c == c]
        return float(after[0]) if after else None
    except Exception:
        return None


_FX_HIST_CACHE = {}


def get_fx_to_eur_at(currency: str, ts):
    """Umrechnungsfaktor nach EUR zum DAMALIGEN Zeitpunkt.

    Noetig, weil ein Einstiegskurs mit dem Kurs von HEUTE umgerechnet
    einen Wert ergibt, den es so nie gab. Fuer die Trefferbilanz muss der
    Kurs des Einstiegstages gelten.

    ts = Unix-Zeitstempel. Rueckgabe None, wenn nicht ermittelbar - dann
    soll der Aufrufer ehrlich "unbekannt" anzeigen statt zu schaetzen."""
    if not currency:
        return 1.0
    cur = str(currency).strip()
    if cur.upper() == "EUR":
        return 1.0
    pence = 0.01 if cur in ("GBp", "GBX", "gbx") else 1.0
    basis = "GBP" if pence != 1.0 else cur.upper()
    try:
        import datetime as _dt
        tag = _dt.datetime.utcfromtimestamp(float(ts)).date()
    except Exception:
        return None
    key = (basis, tag.isoformat())
    if key in _FX_HIST_CACHE:
        v = _FX_HIST_CACHE[key]
        return v * pence if v is not None else None
    kurs = None
    if yf is not None:
        try:
            import datetime as _dt
            paar = f"{basis}EUR=X"
            h = yf.Ticker(paar).history(
                start=(tag - _dt.timedelta(days=7)).isoformat(),
                end=(tag + _dt.timedelta(days=2)).isoformat(),
                interval="1d")
            if h is not None and not getattr(h, "empty", True) and "Close" in h.columns:
                werte = [float(x) for x in h["Close"].tolist()
                         if x is not None and x == x]
                if werte:
                    kurs = werte[-1]          # letzter Kurs bis einschl. Stichtag
        except Exception:
            kurs = None
    _FX_HIST_CACHE[key] = kurs
    return kurs * pence if kurs is not None else None
