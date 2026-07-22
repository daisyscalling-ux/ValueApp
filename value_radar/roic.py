"""
roic.py — Anbindung der roic.ai-API (Individual-Plan, 300 Abrufe/Minute).

ROLLE IM WERKZEUG
  Bevorzugte Kennzahlenquelle fuer US-Titel. Ersetzt dort FMP (250/Tag
  erschoepft nach Minuten) und entlastet yfinance.

WICHTIGE EINSCHRAENKUNG — bitte nicht loeschen:
  Der roic.ai-Support hat uns im Juli 2026 ZWEI Fehler schriftlich
  bestaetigt: die GBP/Pence-Kursbehandlung und den Buchwert. Europaeische
  Multiples waren nachweislich kaputt (BP.L: KGV 168.091, EV/EBITDA 577).
  Deshalb gilt bis zur Freigabe von v3:
    * US-Ticker (kein Suffix)      -> roic.ai bevorzugt
    * Europa (.DE/.L/.PA/...)      -> weiter yfinance/Finnhub
  Schalter: config.ROIC_EU_ENABLED (Standard False). Erst nach bestandenem
  test_roic_live.py auf europaeischen Tickern umlegen.

EINHEITEN
  Profitabilitaets-Ratios kommen in PROZENT (Support-Aussage, von uns
  nachgerechnet: profit_margin 0.029049 heisst 0,029049 %). Wir rechnen
  auf Dezimalbrueche um, weil das ganze Werkzeug so rechnet.

Getestet: offline mit synthetischen Antworten. Live-Pruefung mit echtem
Schluessel: python test_roic_live.py
"""
from __future__ import annotations

import json
import threading
import time
import urllib.parse
import urllib.request

try:
    import config
except Exception:                                   # pragma: no cover
    config = None

BASE = "https://api.roic.ai/v2"

# ---------------------------------------------------------------- Rate-Limit
# 300 Abrufe/Minute laut Plan. Wir bleiben bewusst bei 240 (80 %):
# Antwortzeiten schwanken, und ein 429 mitten im Nachtlauf kostet mehr Zeit
# als die Reserve.
_MAX_PER_MIN = 240
_lock = threading.Lock()
_stamps: list[float] = []

_CACHE: dict[tuple, tuple[float, object]] = {}
_CACHE_TTL = 900            # 15 min - innerhalb eines Laufs reicht das


def _key():
    if config is not None and getattr(config, "ROIC_API_KEY", ""):
        return config.ROIC_API_KEY
    import os
    return os.getenv("ROIC_API_KEY", "")


def enabled() -> bool:
    return bool(_key())


def eu_enabled() -> bool:
    return bool(config is not None and getattr(config, "ROIC_EU_ENABLED", False))


def is_us_ticker(t: str) -> bool:
    """US-Notierung = kein Boersensuffix. 'BRK-B' zaehlt als US."""
    return "." not in (t or "")


# Boersen, die in Pence/Subeinheiten notieren. NUR hier greift der vom
# Support bestaetigte Kursfehler (BP.L: KGV 168.091, weil ein Pence-Kurs
# durch einen USD-Gewinn geteilt wurde).
_PENCE_SUFFIXE = ("L", "IL")


def is_pence_market(t: str) -> bool:
    if "." not in (t or ""):
        return False
    return t.rsplit(".", 1)[-1].upper() in _PENCE_SUFFIXE


def covers(t: str) -> bool:
    """Darf roic.ai fuer diesen Ticker verwendet werden?

    KORREKTUR gegenueber der ersten Fassung: Ich hatte pauschal alles
    ausserhalb der USA gesperrt. Das war zu grob. Der bestaetigte Fehler
    betrifft die PENCE-Umrechnung - also London (.L/.IL). Fuer Tokio,
    Frankfurt oder Paris gilt er nicht.

    Entscheidend ist die Art der Kennzahl, nicht das Land:
      * einheitenlose Groessen (Margen, Wachstum, ROE) sind
        waehrungsunabhaengig und damit unbedenklich
      * kursabhaengige Multiples (KGV, EV/EBITDA) sind es nicht
    Siehe multiples_ok()."""
    if not enabled():
        return False
    if is_pence_market(t):
        return eu_enabled()          # London erst nach bestandenem v3-Test
    return True


def multiples_ok(t: str) -> bool:
    """Duerfen KGV/KUV/EV-EBITDA von roic uebernommen werden?

    Nur fuer US-Titel. Ausserhalb der USA hatten wir sie nicht geprueft,
    und genau dort lag der Fehler. Margen und Wachstum bleiben erlaubt -
    die sind einheitenlos."""
    return enabled() and (is_us_ticker(t) or eu_enabled())


def _throttle():
    with _lock:
        now = time.time()
        while _stamps and now - _stamps[0] > 60:
            _stamps.pop(0)
        if len(_stamps) >= _MAX_PER_MIN:
            warte = 60 - (now - _stamps[0]) + 0.05
            if warte > 0:
                time.sleep(warte)
        _stamps.append(time.time())


def _get(path: str, params: dict | None = None):
    """Ein Abruf. Rueckgabe: geparstes JSON oder None. Wirft nie."""
    k = _key()
    if not k:
        return None
    params = dict(params or {})
    params["apikey"] = k
    url = f"{BASE}/{path.lstrip('/')}?{urllib.parse.urlencode(params)}"
    ck = (path, tuple(sorted((p, v) for p, v in params.items() if p != "apikey")))
    hit = _CACHE.get(ck)
    if hit and time.time() - hit[0] < _CACHE_TTL:
        return hit[1]
    _throttle()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "value-radar"})
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read().decode("utf-8", "replace"))
        _CACHE[ck] = (time.time(), data)
        return data
    except Exception:
        return None


def _first(data):
    """roic liefert je nach Endpunkt Liste oder Objekt - erste Zeile holen."""
    if isinstance(data, list):
        return data[0] if data else None
    if isinstance(data, dict):
        for k in ("data", "results", "rows"):
            v = data.get(k)
            if isinstance(v, list):
                return v[0] if v else None
        return data or None
    return None


def _num(x):
    try:
        if x is None or (isinstance(x, str) and not x.strip()):
            return None
        v = float(x)
        return v if v == v else None
    except Exception:
        return None


def _pct(x):
    """Prozentwert der Ratio-Endpunkte -> Dezimalbruch (12.5 -> 0.125)."""
    v = _num(x)
    return v / 100.0 if v is not None else None


# ---------------------------------------------------------------- Endpunkte
def profile(t: str):
    return _first(_get(f"company/profile/{t}"))


def quote(t: str):
    """Kurs. ACHTUNG: prices/latest existiert im Individual-Plan NICHT -
    der aktuelle Kurs steht im Company Profile."""
    p = profile(t)
    return {"price": _num(_g(p, "price"))} if p else None


def ratios_profitability(t: str):
    return _first(_get(f"fundamental/ratios/profitability/{t}"))


def ratios_credit(t: str):
    return _first(_get(f"fundamental/ratios/credit/{t}"))


def ratios_liquidity(t: str):
    return _first(_get(f"fundamental/ratios/liquidity/{t}"))


def per_share(t: str):
    return _first(_get(f"fundamental/per-share/{t}"))


def enterprise_value(t: str):
    return _first(_get(f"fundamental/enterprise-value/{t}"))


def multiples(t: str):
    return _first(_get(f"fundamental/multiples/{t}"))


def income_quarterly(t: str, limit: int = 20):
    d = _get(f"fundamental/income-statement/{t}",
             {"period": "quarter", "limit": limit})
    return d if isinstance(d, list) else (d or {}).get("data")


def income_annual(t: str, limit: int = 12):
    d = _get(f"fundamental/income-statement/{t}",
             {"period": "annual", "limit": limit})
    return d if isinstance(d, list) else (d or {}).get("data")


def balance_annual(t: str, limit: int = 2):
    d = _get(f"fundamental/balance-sheet/{t}",
             {"period": "annual", "limit": limit})
    return d if isinstance(d, list) else (d or {}).get("data")


def cashflow_annual(t: str, limit: int = 2):
    d = _get(f"fundamental/cash-flow/{t}",
             {"period": "annual", "limit": limit})
    return d if isinstance(d, list) else (d or {}).get("data")


def prices_history(t: str, von: str, bis: str):
    d = _get(f"prices/historical/{t}", {"from": von, "to": bis})
    return d if isinstance(d, list) else (d or {}).get("data")


def search(q: str):
    d = _get("tickers/search", {"query": q})
    return d if isinstance(d, list) else (d or {}).get("data")


# ------------------------------------------------- Buendel fuer providers.py
# ---------------------------------------------------------------------------
# ECHTE Feldnamen (aus roic_felder.py am 22.07.2026 ausgelesen, nicht geraten).
#
# EINHEITEN - im selben Endpunkt gemischt, deshalb einzeln behandelt:
#   Margen/Renditen           -> Prozent  (gross_margin 46.9 = 46,9 %)
#   Verschuldungsverhaeltnisse-> teils Prozent (tot_debt_to_tot_eqy 133.8)
#   net_debt_to_ebitda, cur_ratio, quick_ratio -> ROH (0.43 = 0,43x)
# ---------------------------------------------------------------------------


def _g(d, *keys):
    """Erster vorhandener Schluessel; prueft auch die camelCase-Schreibweise."""
    if not d:
        return None
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
        camel = "".join(w.capitalize() if i else w
                        for i, w in enumerate(k.split("_")))
        if camel in d and d[camel] is not None:
            return d[camel]
    return None


def _yr(inc):
    """Umsatz einer Abschlusszeile - roic nennt ihn is_sales_revenue_turnover."""
    return _num(_g(inc, "is_sales_revenue_turnover",
                   "is_sales_and_services_revenues"))


def bundle(t: str) -> dict:
    """Kennzahlen im providers-Format.

    8 Abrufe je Titel -> bei 240/min rund 30 Titel pro Minute.
    Felder, die roic nicht sauber liefert, bleiben None und werden vom
    Merge aus yfinance/Finnhub gefuellt (Kursziele, Analystenzahl,
    Schaetzungen - die hat roic naemlich gar nicht)."""
    if not covers(t):
        return {}

    prof = profile(t)
    ev = enterprise_value(t)
    rp = ratios_profitability(t)
    rc = ratios_credit(t)
    rl = ratios_liquidity(t)
    mu = multiples(t) if multiples_ok(t) else None
    inc = income_annual(t, limit=2) or []
    bs = _first(_get(f"fundamental/balance-sheet/{t}",
                     {"period": "annual", "limit": 1}))

    out = {
        "_src": "roic",
        # --- Stammdaten (Profil liefert auch den AKTUELLEN Kurs -
        #     prices/latest gibt es im Plan nicht)
        "name": _g(prof, "company_name"),
        "sector": _g(prof, "sector"),
        "industry": _g(prof, "industry"),
        "country": _g(prof, "country_code"),
        "currency": _g(prof, "currency"),
        "price": _num(_g(prof, "price")),
        "dividend_yield": _num(_g(prof, "dividend_yield")),
        "isin": _g(prof, "isin"),

        # --- Groesse und Kapitalstruktur
        "market_cap": _num(_g(ev, "market_cap")),
        "enterprise_value": _num(_g(ev, "enterprise_value")),
        "shares_out": _num(_g(bs, "bs_sh_out")) or _num(_g(mu, "bs_sh_out")),
        "cash": _num(_g(ev, "bs_cash_near_cash_item")),
        "total_debt": _num(_g(ev, "short_and_long_term_debt")),
        "net_debt": _num(_g(bs, "net_debt")),

        # --- TTM-Groessen (aktueller als der Jahresabschluss)
        "revenue": _num(_g(ev, "ttm_net_sales")) or (_yr(inc[0]) if inc else None),
        "ebitda": _num(_g(ev, "ttm_ebitda")),
        "ebit": _num(_g(ev, "ttm_oper_inc")),
        "free_cashflow": _num(_g(ev, "ttm_free_cash_flow_firm")),
        "net_income": _num(_g(inc[0], "is_net_income")) if inc else None,

        # --- Margen und Renditen: PROZENT -> Dezimal
        "gross_margin": _pct(_g(rp, "gross_margin")),
        "operating_margin": _pct(_g(rp, "oper_margin")),
        "profit_margin": _pct(_g(rp, "profit_margin")),
        "ebitda_margin": _pct(_g(rp, "ebitda_margin")),
        "roe": _pct(_g(rp, "return_com_eqy")),
        "roa": _pct(_g(rp, "return_on_asset")),
        "roic": _pct(_g(rp, "return_on_inv_capital")),

        # --- Verschuldung: net_debt_to_ebitda ist ROH, D/E in Prozent
        "net_debt_ebitda": _num(_g(rc, "net_debt_to_ebitda")),
        "debt_to_equity": _pct(_g(rc, "tot_debt_to_tot_eqy")),
        "interest_coverage": _num(_g(rc, "total_debt_to_ebit")),

        # --- Liquiditaet: ROH
        "current_ratio": _num(_g(rl, "cur_ratio")),
        "quick_ratio": _num(_g(rl, "quick_ratio")),
        "altman_z": _num(_g(rl, "altman_z_score")),
    }

    # --- Buchwert je Aktie SELBST rechnen.
    # book_val_per_sh weicht ~6 % ab (verwaesserte vs. ausstehende Aktien),
    # und der Support hatte hier einen Fehler bestaetigt. Eigenkapital durch
    # Aktienzahl ist nachvollziehbar und pruefbar.
    eq, sh = _num(_g(bs, "bs_total_equity")), _num(_g(bs, "bs_sh_out"))
    if eq and sh and sh > 0:
        out["book_value_ps"] = eq / sh

    # --- Gewinn je Aktie
    if inc:
        out["eps_trailing"] = _num(_g(inc[0], "eps", "diluted_eps"))

    # --- Umsatzwachstum aus zwei Geschaeftsjahren
    if len(inc) >= 2:
        r0, r1 = _yr(inc[0]), _yr(inc[1])
        if r0 and r1 and r1 > 0:
            out["revenue_growth"] = (r0 / r1) - 1.0

    # --- Multiples nur, wo geprueft (US)
    if mu:
        out["pe_trailing"] = _num(_g(mu, "pe_ratio"))
        out["ps"] = _num(_g(mu, "pr_to_sales_ratio"))
        out["pb"] = _num(_g(mu, "pr_to_book_ratio"))
        out["ev_ebitda"] = _num(_g(mu, "ev_to_ttm_ebitda"))
        out["pfcf"] = _num(_g(mu, "pr_to_free_cash_flow"))

    return {k: v for k, v in out.items() if v is not None or k == "_src"}


def pe_history(t: str, jahre: int = 10) -> dict:
    """Historisches KGV-Band - der Baustein, der relval.py aktiviert.

    GROSSE VEREINFACHUNG gegenueber meiner ersten Fassung: Ich wollte das
    aus Jahres-EPS und Kurshistorie nachbauen (2 Abrufe, fehleranfaellig).
    roic liefert es fertig - je Geschaeftsjahr:
        average_price_earnings_ratio   Durchschnitts-KGV des Jahres
        pe_ratio_with_high_clos_pr     KGV beim Jahreshoch
        pe_ratio_with_low_clos_pr      KGV beim Jahrestief
    Ein Abruf mit limit=N genuegt.

    Rueckgabe: {median, werte, jahre, spanne_hoch, spanne_tief} oder {}."""
    if not multiples_ok(t):
        return {}
    d = _get(f"fundamental/multiples/{t}", {"period": "annual", "limit": jahre})
    reihen = d if isinstance(d, list) else (d or {}).get("data") or []
    werte, hochs, tiefs, labels = [], [], [], []
    for z in reihen:
        v = _num(_g(z, "average_price_earnings_ratio"))
        if v is None:
            v = _num(_g(z, "pe_ratio"))
        if v is not None and 1 <= v <= 200:      # Plausibilitaet
            werte.append(round(v, 1))
            labels.append(str(_g(z, "fiscal_year") or _g(z, "period_label") or ""))
            h = _num(_g(z, "pe_ratio_with_high_clos_pr"))
            lo = _num(_g(z, "pe_ratio_with_low_clos_pr"))
            if h and 1 <= h <= 300:
                hochs.append(h)
            if lo and 1 <= lo <= 300:
                tiefs.append(lo)
    if len(werte) < 3:
        return {}
    srt = sorted(werte)
    mid = len(srt) // 2
    median = srt[mid] if len(srt) % 2 else (srt[mid - 1] + srt[mid]) / 2
    return {
        "median": round(median, 1),
        "werte": werte,
        "jahre": labels,
        "spanne_hoch": round(max(hochs), 1) if hochs else None,
        "spanne_tief": round(min(tiefs), 1) if tiefs else None,
        "n": len(werte),
    }


def kennzahl_historie(t: str, jahre: int = 10) -> list:
    """Mehrjahresreihe der Kernkennzahlen - fuer Trendbeurteilung.

    Beantwortet 'werden die Margen besser oder schlechter?' - eine Frage,
    die das Werkzeug bisher gar nicht stellen konnte, weil yfinance nur
    Momentaufnahmen liefert."""
    if not covers(t):
        return []
    inc = income_annual(t, limit=jahre) or []
    out = []
    for z in inc:
        out.append({
            "jahr": _g(z, "fiscal_year"),
            "datum": str(_g(z, "date") or "")[:10],
            "revenue": _yr(z),
            "ebitda": _num(_g(z, "ebitda")),
            "net_income": _num(_g(z, "is_net_income")),
            "eps": _num(_g(z, "eps")),
            "gross_margin": _pct(_g(z, "gross_margin")),
            "oper_margin": _pct(_g(z, "oper_margin")),
            "profit_margin": _pct(_g(z, "profit_margin")),
        })
    return [z for z in out if z["jahr"]]


def status() -> dict:
    """Fuer die Anzeige im Dashboard."""
    return {
        "aktiv": enabled(),
        "eu_freigeschaltet": eu_enabled(),
        "limit_pro_minute": _MAX_PER_MIN,
        "hinweis": ("US-Titel: roic.ai bevorzugt. Europa: weiter yfinance, "
                    "bis v3 die vom Support bestaetigten Fehler behebt "
                    "(GBP-Kurse, Buchwert)."),
    }


# ============================================================================
# VOLLE KENNZAHLEN, FINANZDATEN, TRANSKRIPTE
# ============================================================================

def ratios_working_capital(t: str):
    return _first(_get(f"fundamental/ratios/working-capital/{t}"))


def ratios_alle(t: str) -> dict:
    """Alle vier Kennzahlenblöcke in einem Aufruf-Bündel (4 Abrufe).

    Rohwerte OHNE Umrechnung - die Einordnung passiert in kennzahlen.py,
    weil dort auch steht, welches Feld Prozent und welches ein rohes
    Verhaeltnis ist."""
    if not covers(t):
        return {}
    return {
        "profitabilitaet": ratios_profitability(t) or {},
        "verschuldung": ratios_credit(t) or {},
        "liquiditaet": ratios_liquidity(t) or {},
        "kapitalbindung": ratios_working_capital(t) or {},
    }


def financials(t: str, art="income", period="annual", limit=10) -> list:
    """Mehrjahresreihen: art = income | balance | cashflow.

    Das ist der eigentliche Zugewinn gegenueber yfinance: dort gibt es
    Momentaufnahmen, hier zehn Jahre. Erst damit laesst sich fragen, ob
    eine Marge steigt oder faellt."""
    if not covers(t):
        return []
    pfad = {"income": "income-statement", "balance": "balance-sheet",
            "cashflow": "cash-flow"}.get(art, "income-statement")
    d = _get(f"fundamental/{pfad}/{t}", {"period": period, "limit": limit})
    reihen = d if isinstance(d, list) else (d or {}).get("data") or []
    return reihen if isinstance(reihen, list) else []


def multiples_historie(t: str, jahre=10) -> list:
    """Bewertungs-Multiples je Geschaeftsjahr - fuer historische Baender.

    Liefert nicht nur das KGV, sondern auch EV/EBITDA, KUV und KBV samt
    Jahreshoch und -tief. Damit laesst sich fuer JEDE Methode sagen, ob
    der heutige Wert im historischen Rahmen liegt."""
    if not multiples_ok(t):
        return []
    d = _get(f"fundamental/multiples/{t}", {"period": "annual", "limit": jahre})
    reihen = d if isinstance(d, list) else (d or {}).get("data") or []
    out = []
    for z in reihen:
        out.append({
            "jahr": _g(z, "fiscal_year"),
            "pe": _num(_g(z, "average_price_earnings_ratio")) or _num(_g(z, "pe_ratio")),
            "pe_hoch": _num(_g(z, "pe_ratio_with_high_clos_pr")),
            "pe_tief": _num(_g(z, "pe_ratio_with_low_clos_pr")),
            "ev_ebitda": _num(_g(z, "avg_ev_to_ttm_ebitda")) or _num(_g(z, "ev_to_ttm_ebitda")),
            "ev_ebitda_hoch": _num(_g(z, "high_ev_to_ttm_ebitda")),
            "ev_ebitda_tief": _num(_g(z, "low_ev_to_ttm_ebitda")),
            "ps": _num(_g(z, "average_price_to_sales_ratio")) or _num(_g(z, "pr_to_sales_ratio")),
            "pb": _num(_g(z, "average_price_to_book_ratio")) or _num(_g(z, "pr_to_book_ratio")),
            "pfcf": _num(_g(z, "average_price_to_free_cash_flow")) or _num(_g(z, "pr_to_free_cash_flow")),
            "kurs_hoch": _num(_g(z, "pr_high")),
            "kurs_tief": _num(_g(z, "pr_low")),
        })
    return [z for z in out if z.get("jahr")]


def news(t: str, limit=15) -> list:
    """Firmennachrichten. Ergaenzt marketnews.py, ersetzt es nicht."""
    if not covers(t):
        return []
    d = _get(f"company/news/{t}", {"limit": limit})
    reihen = d if isinstance(d, list) else (d or {}).get("data") or []
    out = []
    for z in reihen:
        out.append({
            "datum": str(_g(z, "published_date", "date", "datetime") or "")[:19],
            "titel": _g(z, "title", "headline"),
            "quelle": _g(z, "site", "source", "publisher"),
            "url": _g(z, "url", "link"),
            "text": _g(z, "text", "summary", "content"),
        })
    return [z for z in out if z.get("titel")]


def transcript_liste(t: str, limit=8) -> list:
    """Verfuegbare Earnings-Calls (Quartal/Jahr/Datum)."""
    if not covers(t):
        return []
    d = _get(f"transcripts/list/{t}", {"limit": limit})
    reihen = d if isinstance(d, list) else (d or {}).get("data") or []
    out = []
    for z in reihen:
        out.append({"jahr": _g(z, "year", "fiscal_year"),
                    "quartal": _g(z, "quarter", "period"),
                    "datum": str(_g(z, "date") or "")[:10]})
    return [z for z in out if z.get("datum") or z.get("jahr")]


def transcript(t: str, jahr=None, quartal=None) -> dict:
    """Wortprotokoll eines Earnings-Calls.

    Ohne Jahr/Quartal: das neueste. Rueckgabe {datum, quartal, jahr, text}."""
    if not covers(t):
        return {}
    if jahr and quartal:
        d = _get(f"transcripts/{t}", {"year": jahr, "quarter": quartal})
    else:
        d = _get(f"transcripts/latest/{t}")
    z = _first(d)
    if not z:
        return {}
    return {
        "datum": str(_g(z, "date") or "")[:10],
        "jahr": _g(z, "year", "fiscal_year"),
        "quartal": _g(z, "quarter", "period"),
        "text": _g(z, "content", "transcript", "text") or "",
    }


def ticker_suche(q: str, limit=10) -> list:
    """Symbolsuche ueber roic - Ergaenzung zur yfinance-Suche."""
    if not enabled():
        return []
    d = _get("tickers/search", {"query": q, "limit": limit})
    reihen = d if isinstance(d, list) else (d or {}).get("data") or []
    out = []
    for z in reihen:
        out.append({"symbol": _g(z, "ticker", "symbol"),
                    "name": _g(z, "company_name", "name"),
                    "boerse": _g(z, "exchange_short_name", "exchange"),
                    "land": _g(z, "country_code", "country")})
    return [z for z in out if z.get("symbol")]
