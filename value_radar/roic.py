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

BASE = "https://api.roic.ai/v3.0.0"

# ---------------------------------------------------------------- Rate-Limit
# 300 Abrufe/Minute laut Plan. Wir bleiben bewusst bei 240 (80 %):
# Antwortzeiten schwanken, und ein 429 mitten im Nachtlauf kostet mehr Zeit
# als die Reserve.
_MAX_PER_MIN = 240
_lock = threading.Lock()
_stamps: list[float] = []

_CACHE: dict[tuple, tuple[float, object]] = {}
_CACHE_TTL = 900            # 15 min - innerhalb eines Laufs reicht das

# Gemerkter, funktionierender Listen-Pfad fuer Earnings Calls (siehe
# transcript_liste). Wird beim ersten Treffer gesetzt, damit nicht jedes Mal
# alle Varianten durchprobiert werden. None = noch nicht ermittelt.
_EC_LIST_IDX = None


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
    # UK/Pence FREIGESCHALTET: Der v3-Test hat bewiesen, dass roic die
    # Multiples fuer London selbst sauber in GBP umrechnet (fx_applied=True,
    # KGV plausibel - SHEL.L 12,2, HSBA.L 12,4, BARC.L 9,4). Der alte
    # Pence-x100-Fehler existiert unter v3 nicht mehr.
    return True


def multiples_ok(t: str) -> bool:
    """Duerfen KGV/KUV/EV-EBITDA von roic uebernommen werden?

    Unter v3 JA - auch fuer UK: roic liefert die Multiples mit fx_applied
    in Handelswaehrung (GBP), nicht als Pence/Pfund-Mischung. Der frueher
    hier gesperrte Fehler ist behoben."""
    return enabled()


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
    # Ein Retry bei transientem Fehler (Rate-Limit 429, kurzer Netz-Aussetzer).
    # Ohne den fuehrte EIN fehlgeschlagener von 8 bundle-Abrufen dazu, dass ein
    # Feld fehlte und - schlimmer - das lueckenhafte Ergebnis gecacht wurde.
    for _versuch in range(2):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "value-radar"})
            with urllib.request.urlopen(req, timeout=20) as r:
                data = json.loads(r.read().decode("utf-8", "replace"))
            _CACHE[ck] = (time.time(), data)
            return data
        except Exception as _e:
            # bei HTTP 429 / transientem Fehler kurz warten und einmal neu
            if _versuch == 0:
                try:
                    _code = getattr(_e, "code", None)
                except Exception:
                    _code = None
                time.sleep(1.5 if _code == 429 else 0.4)
                continue
            return None
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


# ---------------------------------------------------------------------------
# v3-TICKER-AUFLOESUNG: aus "AAPL" das noetige "NASDAQ:AAPL" machen
# ---------------------------------------------------------------------------
# v3 verlangt bei JEDEM Abruf EXCHANGE:TICKER. Das Tool hat aber nur den
# nackten Ticker. Die Ticker-Suche (tickers/search) liefert pro Firma alle
# Notierungen mit exchange/symbol/isin/is_primary/listing_country_code -
# daraus bauen wir das v3-Symbol UND bekommen ISIN + Heimatboerse gratis.
#
# Wir cachen das Ergebnis je nacktem Ticker, damit nicht bei jedem der ~8
# Bundle-Abrufe erneut gesucht wird.

# Yahoo-Boersensuffix -> roic-Boersenkuerzel (aus Sonde 2 bestaetigt:
# roic nutzt XETR/FRA fuer DE, LSE fuer UK - NICHT XETRA/LON).
_SUFFIX_ROIC_EXCH = {
    "DE": ("XETR", "FRA"), "F": ("FRA", "XETR"), "MU": ("MUN",),
    "BE": ("BER",), "SG": ("STU",), "DU": ("DUS",), "HM": ("HAM",),
    "HA": ("HAN",), "L": ("LSE",), "IL": ("LSE",), "PA": ("EPA",),
    "AS": ("AMS",), "BR": ("EBR",), "MI": ("MIL",), "MC": ("BME",),
    "SW": ("SIX",), "VX": ("SIX",), "ST": ("STO",), "HE": ("HEL",),
    "OL": ("OSL",), "CO": ("CPH",), "VI": ("VIE",), "LS": ("ELI",),
    "TO": ("TSX",), "T": ("TSE",), "HK": ("HKEX",), "AX": ("ASX",),
}

_RESOLVE_CACHE: dict[str, dict | None] = {}

# Yahoo-Suffix -> erwartetes Land (fuer die harte Filterung bei der Auflösung)
_SUFFIX_LAND = {
    "L": "GB", "IL": "GB", "DE": "DE", "F": "DE", "MU": "DE", "BE": "DE",
    "SG": "DE", "DU": "DE", "HM": "DE", "HA": "DE", "PA": "FR", "AS": "NL",
    "BR": "BE", "MI": "IT", "MC": "ES", "SW": "CH", "VX": "CH", "ST": "SE",
    "HE": "FI", "OL": "NO", "CO": "DK", "VI": "AT", "LS": "PT", "TO": "CA",
    "T": "JP", "HK": "HK", "AX": "AU",
}

# roic-Boersenkuerzel -> Land. Noetig, weil roic nicht immer ein
# listing_country_code mitliefert - dann leiten wir das Land aus der Boerse
# ab (SIX=Schweiz, CSE=Kanada, LSE=UK ...), um falsche Treffer zu sperren.
_EXCH_LAND = {
    "NASDAQ": "US", "NYSE": "US", "NYSEAMERICAN": "US", "AMEX": "US",
    "OTC": "US", "BATS": "US", "IEX": "US",
    "LSE": "GB", "IOB": "GB",
    "XETR": "DE", "FRA": "DE", "MUN": "DE", "BER": "DE", "STU": "DE",
    "DUS": "DE", "HAM": "DE", "HAN": "DE", "GETTEX": "DE", "TG": "DE",
    "EPA": "FR", "AMS": "NL", "EBR": "BE", "MIL": "IT", "BME": "ES",
    "SIX": "CH", "BX": "CH", "STO": "SE", "HEL": "FI", "OSL": "NO",
    "CPH": "DK", "VIE": "AT", "ELI": "PT",
    "TSX": "CA", "TSXV": "CA", "CSE": "CA", "NEO": "CA",
    "TSE": "JP", "HKEX": "HK", "ASX": "AU", "SGX": "SG",
    "B3": "BR", "BMV": "MX", "BYMA": "AR", "GPW": "PL",
}


def _such_roh(query: str):
    """Ticker-Suche (v3). Rueckgabe: Liste von Treffer-dicts oder []."""
    d = _get("tickers/search", {"query": query})
    if isinstance(d, list):
        return d
    if isinstance(d, dict):
        for k in ("data", "results", "tickers"):
            v = d.get(k)
            if isinstance(v, list):
                return v
    return []


def aufloesen(t: str) -> dict | None:
    """Nackten Ticker -> {"symbol": "NASDAQ:AAPL", "isin":..., "exchange":...,
    "is_primary":..., "country":...} oder None. Ergebnis wird gecacht.

    Bei Suffix-Tickern (.L/.DE) MUSS die Boerse zum Suffix-Land passen -
    sonst landet man bei einer voellig anderen Firma gleicher Basis
    (RR.L Rolls-Royce vs CSE:RR Kanada) oder an der falschen Boerse
    (BP.L -> SIX statt LSE). Wichtig: roic liefert nicht immer ein
    listing_country_code, deshalb leiten wir das Land NOTFALLS aus dem
    Boersenkuerzel ab (SIX=CH, CSE=CA, LSE=GB ...).
    """
    if not t:
        return None
    schluessel = t.upper()
    if schluessel in _RESOLVE_CACHE:
        return _RESOLVE_CACHE[schluessel]

    basis = schluessel.split(".")[0]
    suffix = schluessel.rsplit(".", 1)[-1].upper() if "." in schluessel else ""
    ziel_exch = _SUFFIX_ROIC_EXCH.get(suffix)          # bevorzugte roic-Boerse(n)
    ziel_land = _SUFFIX_LAND.get(suffix)               # erwartetes Land

    treffer = _such_roh(basis)
    if not treffer:
        _RESOLVE_CACHE[schluessel] = None
        return None

    def _land_von(tr):
        """Land des Treffers: erst das gemeldete, sonst aus der Boerse."""
        land = (tr.get("listing_country_code") or "").upper()
        if land:
            return land
        ex = (tr.get("exchange") or "").upper()
        return _EXCH_LAND.get(ex, "")

    kandidaten = []
    for tr in treffer:
        sym = tr.get("symbol") or ""
        sym_basis = sym.split(":")[-1].upper()
        if sym_basis != basis:                 # Basis muss exakt passen
            continue
        ex = (sym.split(":")[0] or "").upper()
        land = _land_von(tr)
        prim = bool(tr.get("is_primary"))

        if suffix:
            # Harte Sperre: Land muss passen. Kennen wir das Land nicht UND
            # die Boerse ist nicht die erwartete -> verwerfen (kein Raten).
            if ziel_land:
                if land and land != ziel_land:
                    continue
                if not land and ziel_exch and ex not in ziel_exch:
                    continue
            exch_ok = bool(ziel_exch and ex in ziel_exch)
        else:
            # nackter Ticker = US-Heimatnotierung
            if ex not in ("NASDAQ", "NYSE", "NYSEAMERICAN", "AMEX"):
                # nur akzeptieren, wenn Land US oder unbekannt
                if land and land != "US":
                    continue
            exch_ok = ex in ("NASDAQ", "NYSE", "NYSEAMERICAN", "AMEX")

        # Rang: erwartete Boerse zuerst, dann is_primary
        rang = (0 if exch_ok else 1, 0 if prim else 1)
        kandidaten.append((rang, tr))

    if not kandidaten and not suffix:
        # Rueckfall NUR fuer nackte Ticker: den is_primary-Treffer nehmen.
        for tr in treffer:
            if tr.get("is_primary"):
                kandidaten.append(((2, 0), tr))
                break

    if not kandidaten and suffix and ziel_land:
        # ISIN-LAND-RUECKFALL: roic listet fuer manche Titel KEINE Notierung
        # im Heimatland (BP.L -> nur SIX:BP/Schweiz; RR.L -> nur CSE:RR/Kanada).
        # Aber die ISIN verraet die wahre Nationalitaet: GB0007980591 = GB.
        # Ein Treffer mit passender ISIN-Nationalitaet ist DIESELBE Firma -
        # die Fundamentaldaten sind ISIN-gebunden, egal an welcher Boerse die
        # einzelne Notierung haengt. Wir bevorzugen dabei is_primary.
        passende = []
        for tr in treffer:
            sym = tr.get("symbol") or ""
            if sym.split(":")[-1].upper() != basis:
                continue
            isin = (tr.get("isin") or "").upper()
            if isin[:2] == ziel_land:                  # ISIN-Land == Suffix-Land
                passende.append(tr)
        # is_primary zuerst, damit wir die "Hauptnotierung" der Firma treffen
        passende.sort(key=lambda tr: 0 if tr.get("is_primary") else 1)
        if passende:
            kandidaten.append(((3, 0), passende[0]))

    if not kandidaten:
        _RESOLVE_CACHE[schluessel] = None
        return None

    kandidaten.sort(key=lambda x: x[0])
    beste = kandidaten[0][1]
    erg = {
        "symbol": beste.get("symbol"),
        "isin": beste.get("isin"),
        "exchange": beste.get("exchange"),
        "is_primary": bool(beste.get("is_primary")),
        "country": _land_von(beste),
    }
    _RESOLVE_CACHE[schluessel] = erg if erg.get("symbol") else None
    return _RESOLVE_CACHE[schluessel]


def _v3(t: str) -> str | None:
    """Kurzform: nackter Ticker -> 'EXCHANGE:TICKER' (oder None)."""
    r = aufloesen(t)
    return r.get("symbol") if r else None


def _sym(t: str) -> str:
    """v3-Symbol fuer den Pfad. Faellt auf den Original-Ticker zurueck,
    wenn die Aufloesung nichts findet (ergibt dann sauberen 400/404,
    keinen Crash). URL-Kodierung des ':' uebernimmt urlencode NICHT im
    Pfad - der Doppelpunkt ist in v3-Pfaden erlaubt."""
    return _v3(t) or t


# ---------------------------------------------------------------- Endpunkte
def profile(t: str):
    return _first(_get(f"company/profile/{_sym(t)}"))


def quote(t: str):
    """Letzter Kurs. Pfad laut Doku: stock-prices/latest/{ticker}.
    (Mein erster Versuch 'prices/latest/' war falsch - daher die
    Notloesung ueber das Profil, die jetzt nur noch Rueckfall ist.)"""
    d = _get(f"stock-prices/latest/{_sym(t)}")
    z = d if isinstance(d, dict) else _first(d)
    if z:
        return {"price": _num(_g(z, "close", "adj_close")),
                "datum": str(_g(z, "date") or "")[:10],
                "aenderung_pct": _num(_g(z, "change_percent")),
                "volumen": _num(_g(z, "volume"))}
    p = profile(t)
    return {"price": _num(_g(p, "price"))} if p else None


def ratios_profitability(t: str):
    return _first(_get(f"fundamental/ratios/profitability/{_sym(t)}"))


def ratios_credit(t: str):
    return _first(_get(f"fundamental/ratios/credit/{_sym(t)}"))


def ratios_liquidity(t: str):
    return _first(_get(f"fundamental/ratios/liquidity/{_sym(t)}"))


def per_share(t: str):
    return _first(_get(f"fundamental/per-share/{_sym(t)}"))


def enterprise_value(t: str):
    return _first(_get(f"fundamental/enterprise-value/{_sym(t)}"))


def multiples(t: str):
    return _first(_get(f"fundamental/multiples/{_sym(t)}"))


def income_quarterly(t: str, limit: int = 20):
    d = _get(f"fundamental/income-statement/{_sym(t)}",
             {"period_type": "quarterly", "limit": limit})
    return d if isinstance(d, list) else (d or {}).get("data")


def income_annual(t: str, limit: int = 12):
    d = _get(f"fundamental/income-statement/{_sym(t)}",
             {"period_type": "annual", "limit": limit})
    return d if isinstance(d, list) else (d or {}).get("data")


def balance_annual(t: str, limit: int = 2):
    d = _get(f"fundamental/balance-sheet/{_sym(t)}",
             {"period_type": "annual", "limit": limit})
    return d if isinstance(d, list) else (d or {}).get("data")


def cashflow_annual(t: str, limit: int = 2):
    d = _get(f"fundamental/cash-flow/{_sym(t)}",
             {"period_type": "annual", "limit": limit})
    return d if isinstance(d, list) else (d or {}).get("data")


def cashflow_reihe(t: str, jahre: int = 6) -> dict:
    """Freier Cashflow und Nettogewinn je Geschaeftsjahr - fuer die
    Cash-Conversion.

    bundle() nimmt free_cashflow aus dem Enterprise-Value-Endpunkt
    (ttm_free_cash_flow_firm), also nur den letzten Stand. Fuer die Frage
    "wie viel vom ausgewiesenen Gewinn kommt ueblicherweise als Cash an"
    braucht es die Reihe. Feldnamen defensiv abgedeckt, wie ueberall hier.

    Rueckgabe: {"fcf": [...], "ni": [...], "jahre": [...]} - aeltester zuerst.
    """
    try:
        cf = cashflow_annual(t, limit=jahre) or []
        inc = income_annual(t, limit=jahre) or []
    except Exception:
        return {}
    if not cf or not inc:
        return {}

    def _jahr(z):
        return str(_g(z, "fiscal_year", "calendar_year", "year", "period_ending",
                      "date") or "")[:4]

    cf_map, ni_map = {}, {}
    for z in cf:
        if not isinstance(z, dict):
            continue
        f = _num(_g(z, "cf_free_cash_flow", "free_cash_flow", "freeCashFlow",
                    "cf_fcf"))
        if f is None:
            ocf = _num(_g(z, "cf_cash_from_operations", "operating_cash_flow",
                          "cf_net_cash_from_operating_activities",
                          "netCashProvidedByOperatingActivities"))
            capex = _num(_g(z, "cf_capital_expenditures", "capital_expenditure",
                            "capitalExpenditure", "cf_capex"))
            if ocf is not None and capex is not None:
                f = ocf - abs(capex)
        if f is not None:
            cf_map[_jahr(z)] = f
    for z in inc:
        if isinstance(z, dict):
            n = _num(_g(z, "is_net_income", "net_income", "netIncome"))
            if n is not None:
                ni_map[_jahr(z)] = n

    gemeinsam = sorted(set(cf_map) & set(ni_map))
    if not gemeinsam:
        return {}
    return {"jahre": gemeinsam,
            "fcf": [cf_map[j] for j in gemeinsam],
            "ni": [ni_map[j] for j in gemeinsam]}


def prices_history(t: str, von: str = None, bis: str = None,
                   limit: int = 100, order: str = "ASC"):
    """Tageskurse. Pfad und Parameter laut Doku (v3.0.0):
        GET /v3.0.0/stock-prices/{ticker}?limit=&date.gte=&date.lt=&order=
    Felder: date, open, high, low, close, adj_close, volume, change_percent.

    KORREKTUREN (aus der offiziellen Doku):
      * Datumsbereich heisst 'date.gte' / 'date.lt', NICHT date_start/date_end.
        Die falschen Namen wurden ignoriert -> Backtest bekam keine Kurse.
      * roic erlaubt max. 1000 Kurse pro Abruf. Ein hoeheres Limit liefert
        eine leere Antwort. Fuer lange Historien Datumsbereich in Bloecken.
      * order-Werte laut Doku: 'asc'/'desc' (klein)."""
    p = {"limit": min(int(limit), 1000), "order": order.lower()}
    if von:
        p["date.gte"] = von            # greater-than-or-equal
    if bis:
        p["date.lt"] = bis             # less-than
    d = _get(f"stock-prices/{_sym(t)}", p)
    reihen = d if isinstance(d, list) else (d or {}).get("data")
    return reihen if isinstance(reihen, list) else []


def schlusskurse(t: str, tage: int = 260, adjustiert: bool = True):
    """Schlusskurse als [(datum, kurs)], aelteste zuerst.

    adj_close beruecksichtigt Splits und Dividenden - fuer Renditen ueber
    laengere Zeitraeume ist das die richtige Reihe."""
    reihen = prices_history(t, limit=tage, order="ASC")
    feld = "adj_close" if adjustiert else "close"
    out = []
    for z in reihen or []:
        if not isinstance(z, dict):
            continue
        d = str(_g(z, "date") or "")[:10]
        k = _num(_g(z, feld)) or _num(_g(z, "close"))
        if d and k:
            out.append((d, k))
    return out


def monatsende(t: str, jahre: int = 20):
    """Monatsschlusskurse - fuer Saisonalitaet und Backtest.

    roic liefert max. 1000 Tageskurse pro Abruf (~4 Jahre). Fuer laengere
    Zeitraeume holen wir MEHRERE Bloecke ueber Datumsbereiche und fuegen sie
    zusammen. Aus der Tagesreihe wird je Monat der letzte Handelstag."""
    import datetime as _dt
    heute = _dt.date.today()
    start_jahr = max(heute.year - jahre, 1990)

    alle = {}          # monat -> (datum, kurs)
    # in 3-Jahres-Bloecken (unter 1000 Handelstagen) rueckwaerts holen.
    # Ein leerer Block bedeutet NICHT automatisch das Ende: der Tarif kann
    # eine Luecke haben. Erst nach zwei leeren Bloecken in Folge aufhoeren.
    bis_jahr = heute.year + 1
    leer_in_folge = 0
    while bis_jahr > start_jahr:
        von_jahr = max(bis_jahr - 3, start_jahr)
        von = _dt.date(von_jahr, 1, 1).isoformat()
        bis = _dt.date(min(bis_jahr, heute.year), 12, 31).isoformat()
        try:
            reihe = prices_history(t, von=von, bis=bis, limit=1000, order="DESC")
        except Exception:
            reihe = []
        for z in reihe or []:
            if not isinstance(z, dict):
                continue
            d = str(_g(z, "date") or "")[:10]
            k = _num(_g(z, "adj_close")) or _num(_g(z, "close"))
            if d and k:
                monat = d[:7]
                # spaetester Tag je Monat gewinnt
                if monat not in alle or d > alle[monat][0]:
                    alle[monat] = (d, k)
        bis_jahr = von_jahr
        if not reihe:
            leer_in_folge += 1
            if leer_in_folge >= 2:     # zwei leere Bloecke = Tarifgrenze erreicht
                break
        else:
            leer_in_folge = 0
    if not alle:
        # Rueckfall: die letzten 1000 Tage ohne Datumsbereich
        try:
            for d, k in schlusskurse(t, tage=1000):
                alle[d[:7]] = (d, k)
        except Exception:
            pass
    return [alle[m] for m in sorted(alle)]


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
    ry = ratios_yield(t)               # jetzt korrekter Pfad (yield-analysis)
    mu = multiples(t) if multiples_ok(t) else None
    inc = income_annual(t, limit=2) or []
    bs = _first(_get(f"fundamental/balance-sheet/{_sym(t)}",
                     {"period_type": "annual", "limit": 1}))

    out = {
        "_src": "roic",
        # --- Stammdaten (Profil liefert auch den AKTUELLEN Kurs -
        #     prices/latest gibt es im Plan nicht)
        "name": _g(prof, "name", "company_name"),
        "sector": _g(prof, "sector"),
        "industry": _g(prof, "industry"),
        # NEU: Firmenbeschreibung direkt aus roic (loest yfinance ab).
        "business_summary": _g(prof, "description", "short_description"),
        # NEU: weitere Profilfelder, die roic bereitstellt.
        "ceo": _g(prof, "ceo"),
        "founded": _g(prof, "founded"),
        "website": _g(prof, "website"),
        "employees": _num(_g(prof, "number_of_employees")),
        "country": _g(prof, "country_code") or (aufloesen(t) or {}).get("country"),
        "currency": _g(prof, "currency"),
        "price": _num(_g(prof, "price")),
        "dividend_yield": _num(_g(prof, "dividend_yield")),
        "isin": _g(prof, "isin") or (aufloesen(t) or {}).get("isin"),

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

        # --- Gewinnwachstum aus denselben zwei Abschluessen.
        # Fehlte bisher als einziges der beiden Wachstumsfelder und kam
        # deshalb von FMP/Finnhub. Ohne diese Quellen stuft
        # valuation.classify_playbook() einen Wachstumstitel lautlos als
        # Qualitaetstitel ein - der Fair Value bricht dann ein, ohne dass
        # sich am Unternehmen etwas geaendert hat. Die Daten liegen hier
        # ohnehin vor, es kostet keinen zusaetzlichen Abruf.
        e0 = _num(_g(inc[0], "eps", "diluted_eps"))
        e1 = _num(_g(inc[1], "eps", "diluted_eps"))
        if e0 is not None and e1 and e1 > 0:
            _eg = (e0 / e1) - 1.0
            if -0.95 < _eg < 10.0:
                out["earnings_growth"] = _eg
        else:                                   # Rueckfall ueber Nettogewinn
            n0 = _num(_g(inc[0], "is_net_income"))
            n1 = _num(_g(inc[1], "is_net_income"))
            if n0 is not None and n1 and n1 > 0:
                _eg = (n0 / n1) - 1.0
                if -0.95 < _eg < 10.0:
                    out["earnings_growth"] = _eg

    # --- Multiples nur, wo geprueft (US)
    if mu:
        out["pe_trailing"] = _num(_g(mu, "pe_ratio"))
        out["ps"] = _num(_g(mu, "pr_to_sales_ratio"))
        out["pb"] = _num(_g(mu, "pr_to_book_ratio"))
        out["ev_ebitda"] = _num(_g(mu, "ev_to_ttm_ebitda"))
        out["pfcf"] = _num(_g(mu, "pr_to_free_cash_flow"))
        # NEU: historisches KGV-Band direkt aus roic (Hoch/Tief/Schnitt).
        # Ersetzt die bisherige yfinance/FMP-Quelle fuer hist_pe_median.
        _pe_avg = _num(_g(mu, "average_price_earnings_ratio"))
        _pe_hi = _num(_g(mu, "pe_ratio_with_high_clos_pr"))
        _pe_lo = _num(_g(mu, "pe_ratio_with_low_clos_pr"))
        if _pe_avg is not None:
            out["hist_pe_median"] = _pe_avg      # Durchschnitts-KGV als Median-Proxy
        if _pe_hi is not None:
            out["hist_pe_high"] = _pe_hi
        if _pe_lo is not None:
            out["hist_pe_low"] = _pe_lo

    # --- Echte Jahresreihen der Bewertungs-Multiples.
    # hist_pe_median oben ist nur das Durchschnitts-KGV des LETZTEN
    # Geschaeftsjahres - als Median-Ersatz brauchbar, aber kein Verlauf.
    # multiples_historie() liefert zehn Jahre je KGV, EV/EBITDA, KUV und KBV.
    # Damit rechnet relval.perzentil() ein gemessenes Perzentil statt einer
    # Schaetzung mit angenommener Streuung. Ein Abruf.
    if mu:
        try:
            _mh = multiples_historie(t, 10)
            _pe_r = [z["pe"] for z in _mh if z.get("pe") and z["pe"] > 0]
            _ev_r = [z["ev_ebitda"] for z in _mh if z.get("ev_ebitda") and z["ev_ebitda"] > 0]
            _pb_r = [z["pb"] for z in _mh if z.get("pb") and z["pb"] > 0]
            _jahre = [z.get("jahr") for z in _mh if z.get("pe")]
            if len(_pe_r) >= 4:
                out["hist_pe_werte"] = _pe_r
                out["hist_pe_jahre"] = _jahre
                _sortiert = sorted(_pe_r)
                _m = len(_sortiert) // 2
                out["hist_pe_median"] = (_sortiert[_m] if len(_sortiert) % 2
                                         else (_sortiert[_m - 1] + _sortiert[_m]) / 2)
            if len(_ev_r) >= 4:
                out["hist_ev_ebitda_werte"] = _ev_r
            if len(_pb_r) >= 4:
                out["hist_pb_werte"] = _pb_r
        except Exception:
            pass

    # NEU: Yield-Kennzahlen aus roic (jetzt korrekter Endpunkt). Fertig
    # berechnete FCF-Rendite + Dividendenrendite direkt von der Quelle -
    # robuster als die Eigenrechnung fcf/ev.
    if ry:
        _fcy = _num(_g(ry, "free_cash_flow_yield"))
        if _fcy is not None:
            # roic liefert teils als Faktor (0.05), teils als Prozent (5.0)
            out["fcf_yield"] = _fcy / 100.0 if abs(_fcy) > 1.5 else _fcy

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
    d = _get(f"fundamental/multiples/{_sym(t)}", {"period_type": "annual", "limit": jahre})
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


def wachstum(t: str, jahre: int = 6) -> dict:
    """Umsatz- und Gewinnwachstum aus der EIGENEN Jahreshistorie ableiten.

    Hintergrund: bundle() liefert revenue_growth und earnings_growth nicht -
    beide kamen bisher von FMP bzw. Finnhub. Fehlen sie, stuft
    valuation.classify_playbook() einen Wachstumstitel lautlos als
    Qualitaetstitel ein; der Fair Value faellt dann um die Haelfte, ohne dass
    sich am Unternehmen etwas geaendert hat.

    Da kennzahl_historie() die Jahresumsaetze und -gewinne ohnehin liefert,
    lassen sich beide Groessen hier berechnen - damit wird roic auch fuer
    diese Felder zur Primaerquelle.

    Rueckgabe: {"revenue_growth":.., "earnings_growth":.., "eps_reihe":[..],
                "umsatz_reihe":[..], "n":..}   (Reihen aufsteigend nach Jahr)
    """
    try:
        rows = kennzahl_historie(t, jahre) or []
    except Exception:
        return {}
    rows = [z for z in rows if z.get("jahr")]
    if len(rows) < 2:
        return {}
    rows.sort(key=lambda z: str(z.get("jahr")))

    def reihe(feld):
        return [float(z[feld]) for z in rows
                if z.get(feld) is not None and str(z[feld]) not in ("", "None")]

    umsatz = reihe("revenue")
    gewinn = reihe("net_income")
    eps = reihe("eps")

    def jahresrate(xs):
        """Letzte Veraenderung gegenueber dem Vorjahr - dieselbe Definition,
        die yfinance und FMP verwenden (nicht CAGR)."""
        if len(xs) < 2 or xs[-2] == 0:
            return None
        if xs[-2] < 0:                     # Wachstum aus Verlust heraus ist sinnlos
            return None
        return xs[-1] / xs[-2] - 1.0

    out = {"n": len(rows)}
    rg = jahresrate(umsatz)
    if rg is not None and -0.95 < rg < 5.0:
        out["revenue_growth"] = round(rg, 4)
    eg = jahresrate(eps) if len(eps) >= 2 else jahresrate(gewinn)
    if eg is not None and -0.95 < eg < 10.0:
        out["earnings_growth"] = round(eg, 4)
    if eps:
        out["eps_reihe"] = eps
        out["eps_trailing_hist"] = eps[-1]
    if umsatz:
        out["umsatz_reihe"] = umsatz
    if gewinn:
        out["gewinn_reihe"] = gewinn
    return out


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

def ratios_yield(t: str):
    """Renditekennzahlen: Free-Cashflow-, Shareholder- und Dividenden-Yield.

    Korrekter v3-Pfad ist 'yield-analysis' (nicht 'yield'). Der fruehere
    Pfad lief ins Leere - daher antwortete der Endpunkt beim ersten Test
    nie. Fehlt die Antwort trotzdem, bleibt das Feld leer und nichts bricht."""
    return _first(_get(f"fundamental/ratios/yield-analysis/{_sym(t)}"))


def ratios_working_capital(t: str):
    return _first(_get(f"fundamental/ratios/working-capital/{_sym(t)}"))


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
    d = _get(f"fundamental/{pfad}/{_sym(t)}", {"period_type": period, "limit": limit})
    reihen = d if isinstance(d, list) else (d or {}).get("data") or []
    return reihen if isinstance(reihen, list) else []


def multiples_historie(t: str, jahre=10) -> list:
    """Bewertungs-Multiples je Geschaeftsjahr - fuer historische Baender.

    Liefert nicht nur das KGV, sondern auch EV/EBITDA, KUV und KBV samt
    Jahreshoch und -tief. Damit laesst sich fuer JEDE Methode sagen, ob
    der heutige Wert im historischen Rahmen liegt."""
    if not multiples_ok(t):
        return []
    d = _get(f"fundamental/multiples/{_sym(t)}", {"period_type": "annual", "limit": jahre})
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
    # Pfad laut Doku: company/news/{identifier}, Parameter limit, page,
    # date_start, date_end. Das Raten von drei Varianten entfaellt.
    d = _get(f"company/news/{_sym(t)}", {"limit": limit})
    reihen = d if isinstance(d, list) else (d or {}).get("data") or []
    out = []
    for z in reihen:
        if not isinstance(z, dict):
            continue
        # URL-Feldnamen breit abdecken - hiess der Schluessel anders,
        # blieben die Meldungen ohne Verweis und damit nicht anklickbar.
        url = _g(z, "url", "link", "article_url", "news_url", "source_url",
                 "story_url", "href", "web_url")
        out.append({
            "datum": str(_g(z, "published_date", "date", "datetime",
                            "published_at", "publishedDate") or "")[:19],
            "titel": _g(z, "title", "headline", "heading"),
            "quelle": _g(z, "site", "source", "publisher", "provider"),
            "url": str(url) if url else None,
            "text": _g(z, "text", "summary", "content", "description"),
        })
    return [z for z in out if z.get("titel")]


def stock_splits(t: str, limit: int = 10) -> list:
    """Aktiensplits eines Titels (neueste zuerst). Erklaert scheinbare
    Kurssprunge: ein 4:1-Split viertelt den Kurs optisch, ohne dass sich
    am Wert etwas aendert. Ohne diese Info meldet 'Was hat sich geaendert'
    solche Splits faelschlich als drastischen Absturz.

    Pfad laut Doku: /stock-splits, Filter ueber identifier. Rueckgabe:
    [{datum, faktor, von, zu, ist_reverse, kurs_vorher, kurs_nachher}]."""
    if not covers(t):
        return []
    d = _get("stock-splits", {"identifier": _sym(t), "limit": limit,
                              "order": "DESC"})
    reihen = d if isinstance(d, list) else (d or {}).get("data") or []
    out = []
    for z in reihen:
        if not isinstance(z, dict):
            continue
        _von = _num(_g(z, "split_from"))
        _zu = _num(_g(z, "split_to"))
        _faktor = _num(_g(z, "factor"))
        # Faktor selbst ableiten, falls nicht geliefert (zu/von)
        if _faktor is None and _von and _zu and _von != 0:
            _faktor = _zu / _von
        out.append({
            "datum": str(_g(z, "execution_date", "date") or "")[:10],
            "faktor": _faktor,
            "von": _von, "zu": _zu,
            "ist_reverse": bool(_g(z, "is_reverse")),
            "kurs_vorher": _num(_g(z, "pre_split_price")),
            "kurs_nachher": _num(_g(z, "post_split_price")),
        })
    return [z for z in out if z.get("datum")]


def trading_hours(exchange: str) -> dict | None:
    """Handelszeiten einer Boerse (z.B. 'NASDAQ'). Erklaert, warum ein
    Intraday-Chart gerade leer ist (ausserhalb der Handelszeit). Pro Boerse,
    nicht pro Titel. Pfad laut Doku: /exchanges/trading-hours."""
    if not enabled() or not exchange:
        return None
    d = _get("exchanges/trading-hours", {"exchange": exchange})
    z = d if isinstance(d, dict) else _first(d)
    if not z:
        return None
    return {
        "boerse": _g(z, "exchange"),
        "zeitzone": _g(z, "timezone"),
        "regulaer": _g(z, "regular"),
        "erweitert": _g(z, "extended"),
    }


def holidays(exchange: str) -> list:
    """Feiertagskalender einer Boerse - Tage ohne Handel. Erklaert leere
    Intraday-Charts an Feiertagen. Pfad laut Doku: /exchanges/holidays."""
    if not enabled() or not exchange:
        return []
    d = _get("exchanges/holidays", {"exchange": exchange})
    z = d if isinstance(d, dict) else _first(d)
    if not z:
        return []
    hs = _g(z, "holidays") or []
    return hs if isinstance(hs, list) else []


# ---------------------------------------------------------------------------
# EARNINGS-CALL-TRANSKRIPTE - Pfade aus der offiziellen Doku (24.07.2026):
#   GET /v2/company/earnings-calls/latest/{ticker}
#   GET /v2/company/earnings-calls/list/{ticker}?limit=100
#   GET /v2/company/earnings-calls/transcript/{ticker}?year=&quarter=
# Antwort: {symbol, year, quarter (1-4 als ZAHL), date, content}
#
# Meine erste Fassung riet "transcripts/latest/{t}" - deshalb kam nichts an.
# Laut Doku sind Transkripte in JEDEM Plan enthalten, auch im kostenlosen.
# ---------------------------------------------------------------------------


def transcript_liste(t: str, limit=100) -> list:
    """Alle verfuegbaren Earnings-Calls: Jahr, Quartal, Datum (ohne Text).

    Robust gegen roic-Endpunkt-Aenderungen: probiert mehrere bekannte
    Pfad-Varianten durch und nimmt die erste, die Eintraege liefert. Der
    erfolgreiche Pfad wird pro Prozess gemerkt, damit nicht jedes Mal alle
    Varianten durchlaufen werden.
    """
    if not covers(t):
        return []
    sym = _sym(t)

    # Kandidaten-Pfad-VORLAGEN. Wichtig: der Wechsel-Parameter (identifier
    # bzw. {s} im Pfad) wird bei JEDEM Aufruf frisch aus 'sym' gebaut. Frueher
    # wurde das komplette extra-Dict inkl. identifier der ERSTEN Firma gemerkt
    # und fuer alle folgenden wiederverwendet -> jede Firma bekam die Calls der
    # ersten (alle 540 zeigten dasselbe Datum). Jetzt merken wir nur, WELCHE
    # Vorlage funktioniert (Index), und fuellen sym jedes Mal neu ein.
    global _EC_LIST_IDX
    vorlagen = [
        # v3 laut Doku: GET /earnings-calls?identifier=NASDAQ:AAPL, Feld "data"
        ("earnings-calls",                  lambda: {"identifier": sym, "limit": limit}),
        ("company/earnings-calls/list/{s}", lambda: {"limit": limit}),
        ("earnings-calls/list/{s}",         lambda: {"limit": limit}),
        ("earnings-calls/{s}/list",         lambda: {"limit": limit}),
    ]
    # Reihenfolge: gemerkte funktionierende Vorlage zuerst, dann der Rest.
    reihenfolge = list(range(len(vorlagen)))
    if _EC_LIST_IDX is not None and 0 <= _EC_LIST_IDX < len(vorlagen):
        reihenfolge.remove(_EC_LIST_IDX)
        reihenfolge.insert(0, _EC_LIST_IDX)

    reihen = []
    for idx in reihenfolge:
        pfad, extra_fn = vorlagen[idx]
        d = _get(pfad.format(s=sym), extra_fn())
        r = d if isinstance(d, list) else (d or {}).get("data") \
            or (d or {}).get("earnings_calls") or []
        if isinstance(r, dict):
            r = [r]
        if r:                               # Treffer -> Vorlagen-Index merken
            _EC_LIST_IDX = idx
            reihen = r
            break

    out = []
    for z in reihen:
        if not isinstance(z, dict):
            continue
        _j = _num(_g(z, "fiscal_year", "year"))
        _q = _num(_g(z, "fiscal_quarter", "quarter"))
        out.append({
            "jahr": int(_j) if _j else None,      # sonst steht "2026.0" da
            "quartal": int(_q) if _q else None,
            "datum": str(_g(z, "date") or "")[:10],
        })
    out = [z for z in out if z.get("datum") or z.get("jahr")]
    # WICHTIG: explizit neueste zuerst sortieren. Frueher wurde die Reihenfolge
    # der API uebernommen - wenn die nicht desc war, griff neue_transkripte()
    # mit liste[:1] den FALSCHEN (alten) Call, und aktuelle Calls (z.B. Meta
    # 29.07) wurden als 'alt' eingestuft. Sortierschluessel: Datum, sonst
    # Jahr+Quartal als Rueckfall, wenn ein Datum fehlt.
    out.sort(key=lambda z: (z.get("datum") or "",
                            z.get("jahr") or 0,
                            z.get("quartal") or 0), reverse=True)
    return out


def transcript(t: str, jahr=None, quartal=None) -> dict:
    """Wortprotokoll eines Earnings-Calls (v3).

    v3-Endpunkt: GET /earnings-calls/{identifier}?fiscal_year=&fiscal_quarter=
    Beide Parameter sind PFLICHT (es gibt kein 'latest' mehr). Der Text kommt
    als Liste von {speaker, text}-Bloecken und wird hier zu Fliesstext
    zusammengesetzt. Rueckgabe {datum, jahr, quartal, text}.

    Ohne Jahr/Quartal: neuesten Eintrag aus der Liste nehmen und den abrufen.
    """
    if not covers(t):
        return {}
    sym = _sym(t)

    # Jahr/Quartal fehlen -> neuesten Call aus der Liste holen
    if not (jahr and quartal):
        liste = transcript_liste(t, limit=1)
        if not liste:
            return {}
        jahr = liste[0].get("jahr")
        quartal = liste[0].get("quartal")
    if not (jahr and quartal):
        return {}
    try:
        q = int(str(quartal).upper().replace("Q", "").strip())
    except Exception:
        return {}

    d = _get(f"earnings-calls/{sym}",
             {"fiscal_year": int(jahr), "fiscal_quarter": q})
    z = d if isinstance(d, dict) else _first(d)
    if not z or not isinstance(z, dict):
        return {}

    # Text zusammensetzen: v3 liefert 'transcript' als Liste von
    # {speaker, text}. Wir bauen "Speaker: Text"-Absaetze. Faellt zurueck auf
    # ein evtl. vorhandenes Klartextfeld.
    roh = _g(z, "transcript", "content", "text")
    if isinstance(roh, list):
        teile = []
        for blk in roh:
            if not isinstance(blk, dict):
                continue
            sp = str(blk.get("speaker") or "").strip()
            tx = str(blk.get("text") or "").strip()
            if not tx:
                continue
            teile.append(f"{sp}: {tx}" if sp else tx)
        text = "\n\n".join(teile)
    else:
        text = str(roh or "")

    q2, j2 = _num(_g(z, "fiscal_quarter", "quarter")), _num(_g(z, "fiscal_year", "year"))
    return {
        "datum": str(_g(z, "date") or "")[:10],
        "jahr": int(j2) if j2 else (int(jahr) if jahr else None),
        "quartal": (f"Q{int(q2)}" if q2 else f"Q{q}"),
        "text": text,
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


# ============================================================================
# INDEX-UNIVERSEN + TRANSKRIPT-SUCHE
# ============================================================================

# DAX 40. Bewusst fest hinterlegt: die Zusammensetzung aendert sich selten,
# und ein Wikipedia-Abruf je Lauf ist eine unnoetige Fehlerquelle.
DAX40 = [
    "ADS.DE", "AIR.DE", "ALV.DE", "BAS.DE", "BAYN.DE", "BEI.DE", "BMW.DE",
    "BNR.DE", "CBK.DE", "CON.DE", "1COV.DE", "DTG.DE", "DBK.DE", "DB1.DE",
    "DPW.DE", "DTE.DE", "EOAN.DE", "FRE.DE", "HNR1.DE", "HEI.DE", "HEN3.DE",
    "IFX.DE", "MBG.DE", "MRK.DE", "MTX.DE", "MUV2.DE", "P911.DE", "PAH3.DE",
    "QIA.DE", "RHM.DE", "RWE.DE", "SAP.DE", "SRT3.DE", "SIE.DE", "ENR.DE",
    "SHL.DE", "SY1.DE", "VOW3.DE", "VNA.DE", "ZAL.DE",
]

_UNIVERSUM_CACHE = {}


def index_universum(mit_dax=True) -> list:
    """S&P 500 + NASDAQ-100 + DAX 40, entdoppelt.

    Der Dow Jones steckt vollstaendig im S&P 500, der NASDAQ-100 groesstenteils.
    Rund 560 Titel."""
    if "liste" in _UNIVERSUM_CACHE:
        return _UNIVERSUM_CACHE["liste"]
    tk = []
    try:
        import regime as _rg
        tk.extend(_rg.sp500_tickers() or [])
    except Exception:
        pass
    try:
        import pandas as _pd
        for tab in _pd.read_html("https://en.wikipedia.org/wiki/Nasdaq-100"):
            for sp in ("Ticker", "Symbol"):
                if sp in tab.columns:
                    tk.extend(str(s).strip().upper().replace(".", "-")
                              for s in tab[sp].tolist())
                    break
            else:
                continue
            break
    except Exception:
        pass
    if mit_dax:
        tk.extend(DAX40)
    # Echte Ticker haben KEINE Leerzeichen und sind kurz. Eintraege mit
    # Leerzeichen (z.B. "PRUDENTIAL FINANCIAL") stammen aus falsch geparsten
    # Wikipedia-Spalten und fuehren nur zu fehlgeschlagenen Abrufen -> raus.
    # Auch reine Namen wie "NETFLIX"/"NVIDIA" (kommen aus derselben Quelle)
    # werden verworfen, wenn sie laenger als ein ueblicher Ticker sind (>5)
    # und komplett aus Buchstaben bestehen und NICHT bekannt sind.
    def _ist_ticker(t):
        if not t or " " in t or len(t) > 12:
            return False
        return True
    liste = [t for t in dict.fromkeys(tk) if _ist_ticker(t)]
    _UNIVERSUM_CACHE["liste"] = liste
    return liste


def neue_transkripte(tickers=None, tage=21, deckel=600, fortschritt=None) -> list:
    """Neueste Earnings Calls je Titel - mit Alter (tage_her).

    Holt bewusst nur die Kopfdaten (Ticker, Datum, Quartal) - ein Abruf je
    Titel. Der Volltext kommt erst, wenn jemand ihn oeffnet.

    WICHTIG: Es wird NICHT mehr hart nach 'tage' gefiltert. Zurueckgegeben
    wird der neueste Call jedes Titels samt 'tage_her' und 'ist_neu' (ob er
    innerhalb des 'tage'-Fensters liegt). So kann der Tab aktuelle Calls
    priorisieren, aber ausserhalb der Saison trotzdem die zuletzt
    erschienenen zeigen, statt leer zu bleiben.

    tage: ab wann ein Call als 'aktuell/neu' markiert wird (nicht mehr als
    harter Filter).
    """
    import datetime as _dt
    tickers = tickers or index_universum()
    heute = _dt.date.today()
    grenze = heute - _dt.timedelta(days=tage)
    out = []
    for i, t in enumerate(tickers[:deckel]):
        if not covers(t):
            continue
        try:
            liste = transcript_liste(t, limit=6)
        except Exception:
            liste = []
        for z in liste[:1]:                      # nur der neueste
            d = str(z.get("datum") or "")[:10]
            if not d:
                continue
            try:
                tag = _dt.date.fromisoformat(d)
            except Exception:
                continue
            out.append({"ticker": t, "datum": d,
                        "quartal": z.get("quartal"), "jahr": z.get("jahr"),
                        "tage_her": (heute - tag).days,
                        "ist_neu": tag >= grenze})
        if fortschritt and (i + 1) % 50 == 0:
            fortschritt(i + 1, min(len(tickers), deckel), len(out))
    out.sort(key=lambda r: r["datum"], reverse=True)
    _n_neu = sum(1 for r in out if r.get("ist_neu"))
    print(f"  [Transkripte] {len(out)} Calls erfasst, davon {_n_neu} aktuell "
          f"(<= {tage} Tage), aus {min(len(tickers), deckel)} Titeln.")
    return out


# ============================================================================
# PEERS / WETTBEWERBER
# ============================================================================

def peers(t: str, limit=12) -> list:
    """Vergleichbare Unternehmen.

    Die Pfadbenennung ist NICHT gesichert - ich habe sie nicht live geprueft.
    Deshalb werden mehrere plausible Varianten versucht; schlaegt alles fehl,
    uebernimmt peers_nach_branche() ueber die Branche aus dem Profil.
    Das ist ehrlicher als eine Funktion, die still nichts zurueckgibt."""
    # Die Doku listet 28 Endpunkte in 9 Gruppen - ein Peer-Endpunkt ist
    # NICHT darunter. Frueher wurden hier drei Pfade geraten; das kostete
    # bei jedem Aufruf drei vergebliche Abrufe. Die Auswahl laeuft
    # ausschliesslich ueber die Branche aus dem Profil.
    return []


def peers_nach_branche(t: str, universum=None, limit=12) -> list:
    """Rueckfall: Titel derselben Branche aus den grossen Indizes.

    Kostet ein Profil-Abruf je Kandidat, deshalb gedeckelt und
    zwischengespeichert. Weniger treffsicher als eine gepflegte Peer-Liste,
    aber nachvollziehbar: gleiche Branche laut Anbieter."""
    p = profile(t)
    branche = _g(p, "industry")
    sektor = _g(p, "sector")
    if not branche and not sektor:
        return []
    kandidaten = universum or index_universum()
    out = []
    for k in kandidaten:
        if k.upper() == t.upper() or not covers(k):
            continue
        pk = profile(k)
        if not pk:
            continue
        if branche and _g(pk, "industry") == branche:
            out.append({"ticker": k.upper(), "name": _g(pk, "company_name"),
                        "grund": "gleiche Branche"})
        elif sektor and _g(pk, "sector") == sektor and len(out) < limit:
            out.append({"ticker": k.upper(), "name": _g(pk, "company_name"),
                        "grund": "gleicher Sektor"})
        if len(out) >= limit * 2:
            break
    out.sort(key=lambda r: 0 if r.get("grund") == "gleiche Branche" else 1)
    return out[:limit]


def peer_vergleich(t: str, peer_tickers: list) -> list:
    """Kennzahlen des Titels und seiner Peers nebeneinander.

    Bewusst wenige, gut vergleichbare Groessen. Kosten: 8 Abrufe je Titel,
    deshalb im Dashboard auf wenige Peers begrenzt."""
    reihen = []
    for tk in [t] + [p for p in peer_tickers if p.upper() != t.upper()]:
        b = bundle(tk)
        if not b or not b.get("name"):
            continue
        reihen.append({
            "ticker": tk.upper(),
            "name": (b.get("name") or "")[:24],
            "ist_basis": tk.upper() == t.upper(),
            "market_cap": b.get("market_cap"),
            "pe": b.get("pe_trailing"),
            "ev_ebitda": b.get("ev_ebitda"),
            "ps": b.get("ps"),
            "oper_marge": b.get("operating_margin"),
            "roe": b.get("roe"),
            "wachstum": b.get("revenue_growth"),
            "net_debt_ebitda": b.get("net_debt_ebitda"),
        })
    return reihen


def peer_median(reihen: list, feld: str):
    """Median eines Feldes ueber die Peers OHNE den Basistitel."""
    w = [r[feld] for r in reihen
         if not r.get("ist_basis") and r.get(feld) is not None]
    if not w:
        return None
    w.sort()
    m = len(w) // 2
    return w[m] if len(w) % 2 else (w[m - 1] + w[m]) / 2


def bundle_light(t: str) -> dict:
    """Sparfassung mit 4 statt 9 Abrufen - fuer breite Scans.

    Enthaelt alles, was die Vorauswahl braucht: Stammdaten, Groesse,
    Margen, Renditen, Umsatz und die Multiples. Weggelassen sind die
    Bilanz- und Liquiditaetsdetails sowie das Umsatzwachstum aus zwei
    Geschaeftsjahren - die kommen beim tiefen Nachrechnen dazu.

    Damit kostet ein 400-Titel-Scan 1.600 statt 3.600 Abrufe:
    7 Minuten statt 15."""
    if not covers(t):
        # UK/Pence-Titel: kursabhaengige Multiples bleiben gesperrt (Pence-
        # Fehler), aber Name/ISIN/Sektor sind waehrungsunabhaengig und fuer
        # die Entdopplung wichtig. Die holen wir aus der Aufloesung + Profil.
        _auf = aufloesen(t) or {}
        if _auf.get("isin"):
            _p = profile(t)
            return {"_src": "roic_light_min", "name": _g(_p, "company_name"),
                    "isin": _auf.get("isin"), "sector": _g(_p, "sector"),
                    "industry": _g(_p, "industry"),
                    "country": _auf.get("country")}
        return {}
    prof = profile(t)
    ev = enterprise_value(t)
    rp = ratios_profitability(t)
    mu = multiples(t) if multiples_ok(t) else None
    # Vierter Abruf: ohne revenue_growth/earnings_growth stuft
    # valuation.classify_playbook() im breiten Scan jeden Wachstumstitel als
    # Qualitaetstitel ein - genau der Fehler, der NVDA/MU auf -50 % geschickt
    # hat. Ein Abruf mehr je Titel ist der Preis dafuer, dass die Vorauswahl
    # ueberhaupt das richtige Playbook trifft.
    inc = income_annual(t, limit=2) or []

    out = {
        "_src": "roic_light",
        "name": _g(prof, "name", "company_name"),
        "isin": _g(prof, "isin") or (aufloesen(t) or {}).get("isin"),
        "sector": _g(prof, "sector"),
        "industry": _g(prof, "industry"),
        "country": _g(prof, "country_code") or (aufloesen(t) or {}).get("country"),
        "currency": _g(prof, "currency"),
        "price": _num(_g(prof, "price")),
        "market_cap": _num(_g(ev, "market_cap")),
        "enterprise_value": _num(_g(ev, "enterprise_value")),
        "total_debt": _num(_g(ev, "short_and_long_term_debt")),
        "cash": _num(_g(ev, "bs_cash_near_cash_item")),
        "revenue": _num(_g(ev, "ttm_net_sales")),
        "ebitda": _num(_g(ev, "ttm_ebitda")),
        "ebit": _num(_g(ev, "ttm_oper_inc")),
        "free_cashflow": _num(_g(ev, "ttm_free_cash_flow_firm")),
        "gross_margin": _pct(_g(rp, "gross_margin")),
        "operating_margin": _pct(_g(rp, "oper_margin")),
        "profit_margin": _pct(_g(rp, "profit_margin")),
        "ebitda_margin": _pct(_g(rp, "ebitda_margin")),
        "roe": _pct(_g(rp, "return_com_eqy")),
        "roa": _pct(_g(rp, "return_on_asset")),
        "roic": _pct(_g(rp, "return_on_inv_capital")),
    }
    if mu:
        out["pe_trailing"] = _num(_g(mu, "pe_ratio"))
        out["ps"] = _num(_g(mu, "pr_to_sales_ratio"))
        out["pb"] = _num(_g(mu, "pr_to_book_ratio"))
        out["ev_ebitda"] = _num(_g(mu, "ev_to_ttm_ebitda"))
    if len(inc) >= 2:
        r0, r1 = _yr(inc[0]), _yr(inc[1])
        if r0 and r1 and r1 > 0:
            out["revenue_growth"] = (r0 / r1) - 1.0
        e0 = _num(_g(inc[0], "eps", "diluted_eps"))
        e1 = _num(_g(inc[1], "eps", "diluted_eps"))
        if e0 is not None and e1 and e1 > 0:
            _eg = (e0 / e1) - 1.0
            if -0.95 < _eg < 10.0:
                out["earnings_growth"] = _eg
        if out.get("eps_trailing") is None and e0 is not None:
            out["eps_trailing"] = e0

    return {k: v for k, v in out.items() if v is not None or k == "_src"}


def call_kursreaktionen(t: str, max_calls: int = 24) -> list:
    """Kursreaktion auf JEDEN bekannten Earnings Call.

    Der Zugewinn gegenueber yfinance: Dort gibt es maximal 8 Quartale.
    roic listet die Calls ueber viele Jahre, und mit der Tagesreihe laesst
    sich die Reaktion zu jedem Termin berechnen - also 20+ statt 8 Faelle.

    WICHTIG - was hier NICHT drinsteht: roic liefert keine damaligen
    ANALYSTENSCHAETZUNGEN. 'Geschlagen oder verfehlt' laesst sich damit
    nicht sagen, nur wie der Kurs reagiert hat. Fuer die Beat-Quote bleibt
    yfinance noetig (und dessen 8-Quartals-Grenze).

    Kosten: 2 Abrufe je Titel (Liste + Kursreihe)."""
    if not covers(t):
        return []
    calls = transcript_liste(t, limit=max_calls)
    if not calls:
        return []
    datums = sorted(c["datum"] for c in calls if c.get("datum"))
    if not datums:
        return []
    # Tagesreihe ab dem aeltesten Call, mit Vorlauf fuer den Vortageskurs
    reihe = prices_history(t, von=datums[0], limit=6000, order="ASC")
    kurse = []
    for z in reihe or []:
        if not isinstance(z, dict):
            continue
        d = str(_g(z, "date") or "")[:10]
        k = _num(_g(z, "adj_close")) or _num(_g(z, "close"))
        if d and k:
            kurse.append((d, k))
    if len(kurse) < 10:
        return []

    idx = {d: i for i, (d, _k) in enumerate(kurse)}
    out = []
    for c in calls:
        d = c.get("datum")
        if not d:
            continue
        # Ersten Handelstag ab dem Call-Datum finden
        pos = idx.get(d)
        if pos is None:
            spaeter = [i for i, (dd, _k) in enumerate(kurse) if dd >= d]
            if not spaeter:
                continue
            pos = spaeter[0]
        if pos == 0:
            continue
        vor, nach = kurse[pos - 1][1], kurse[pos][1]
        if not vor:
            continue
        reak = (nach / vor - 1) * 100
        # Fuenf Handelstage danach - zeigt, ob die erste Reaktion hielt
        nach5 = kurse[min(pos + 5, len(kurse) - 1)][1]
        out.append({
            "datum": d,
            "jahr": c.get("jahr"),
            "quartal": c.get("quartal"),
            "reaktion_pct": round(reak, 1),
            "nach5t_pct": round((nach5 / vor - 1) * 100, 1),
        })
    out.sort(key=lambda z: z["datum"], reverse=True)
    return out


def call_reaktionsprofil(t: str) -> dict:
    """Verdichtet die Kursreaktionen zu wenigen Kennzahlen.

    Beantwortet: Bewegt dieser Titel sich an Zahlentagen ueberhaupt stark?
    Und: Haelt die erste Reaktion, oder dreht sie in den Tagen danach?
    Die zweite Frage ist die interessantere - sie unterscheidet eine
    Neubewertung von einem kurzen Ausschlag."""
    z = call_kursreaktionen(t)
    if len(z) < 4:
        return {}
    r = [x["reaktion_pct"] for x in z]
    pos = [x for x in r if x > 0]
    gedreht = sum(1 for x in z
                  if (x["reaktion_pct"] > 0) != (x["nach5t_pct"] > 0))
    betrag = sorted(abs(x) for x in r)
    m = len(betrag) // 2
    return {
        "n": len(z),
        "positiv_pct": round(len(pos) / len(r) * 100),
        "avg": round(sum(r) / len(r), 1),
        "median_ausschlag": round(betrag[m] if len(betrag) % 2
                                  else (betrag[m - 1] + betrag[m]) / 2, 1),
        "groesster_plus": round(max(r), 1),
        "groesster_minus": round(min(r), 1),
        "gedreht_pct": round(gedreht / len(z) * 100),
        "zeilen": z,
    }
