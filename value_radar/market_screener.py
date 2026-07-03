"""
market_screener.py — marktweites Screening (gegen "alles").

Reihenfolge der Quellen:
  1. FMP-Stock-Screener   (falls FMP_API_KEY gesetzt; serverseitig, breit)
  2. Yahoo-Screener       (kostenlos, via yfinance EquityQuery; Region + MarketCap)
  3. Eingebautes Universum (Sicherheitsnetz, falls 1+2 nicht verfuegbar)

Liefert eine Liste von Ticker-Symbolen (sortiert nach Market Cap absteigend),
die anschliessend im Dashboard pro Titel nachgeladen und lokal weitergefiltert
werden.
"""
from __future__ import annotations
import config

try:
    import yfinance as yf
except Exception:
    yf = None
try:
    from yfinance import EquityQuery
except Exception:
    EquityQuery = None
try:
    import requests
except Exception:
    requests = None

# Yahoo-Regionscodes
DEFAULT_REGIONS = ["us", "de", "nl", "fr", "gb", "ch"]
REGION_CHOICES = ["us", "de", "nl", "fr", "gb", "ch", "it", "es", "se", "dk",
                  "fi", "no", "ca", "jp", "hk", "au"]

# Sicherheitsnetz: breites Universum liquider Werte (US + Europa), falls
# weder Yahoo- noch FMP-Screener erreichbar sind.
DEFAULT_UNIVERSE = [
    # US Mega/Large
    "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "AVGO", "TSLA", "AMD",
    "INTC", "QCOM", "TXN", "MU", "AMAT", "LRCX", "KLAC", "MRVL", "ADI", "ON",
    "ORCL", "CRM", "ADBE", "CSCO", "IBM", "NOW", "INTU", "PANW", "SNPS", "CDNS",
    "JPM", "BAC", "WFC", "GS", "MS", "C", "BLK", "SCHW", "AXP", "V", "MA",
    "UNH", "JNJ", "LLY", "PFE", "MRK", "ABBV", "TMO", "ABT", "DHR", "BMY",
    "XOM", "CVX", "COP", "SLB", "EOG", "PSX", "MPC", "VLO", "OXY",
    "WMT", "COST", "HD", "LOW", "TGT", "NKE", "MCD", "SBUX", "PG", "KO",
    "PEP", "PM", "MO", "CL", "MDLZ", "GIS",
    "BA", "CAT", "DE", "GE", "HON", "RTX", "LMT", "NOC", "GD", "ETN", "EMR",
    "UNP", "UPS", "FDX", "CSX", "NSC",
    "GEV", "NEE", "DUK", "SO", "D", "VST", "CEG", "AEP",
    "DIS", "NFLX", "CMCSA", "T", "VZ", "TMUS",
    "F", "GM", "DAL", "UAL", "LUV",
    "FCX", "NUE", "DOW", "LIN", "SHW", "NEM",
    # Europe (Yahoo-Suffixe)
    "ASML.AS", "ASM.AS", "BESI.AS", "PRX.AS", "AD.AS", "INGA.AS", "WKL.AS",
    "SAP.DE", "SIE.DE", "ALV.DE", "DTE.DE", "MUV2.DE", "MRK.DE", "IFX.DE",
    "BAS.DE", "BAYN.DE", "BMW.DE", "MBG.DE", "VOW3.DE", "DB1.DE", "RHM.DE",
    "AIR.DE", "MC.PA", "OR.PA", "RMS.PA", "SU.PA", "AI.PA", "TTE.PA", "SAN.PA",
    "BNP.PA", "CS.PA", "DG.PA", "EL.PA", "SAF.PA",
    "NESN.SW", "ROG.SW", "NOVN.SW", "UBSG.SW", "ZURN.SW", "ABBN.SW", "LONN.SW",
    "AZN.L", "SHEL.L", "HSBA.L", "ULVR.L", "RIO.L", "BP.L", "GSK.L", "DGE.L",
    "NOVO-B.CO", "MAERSK-B.CO",
]


def screen_fmp(min_mcap_usd: float, size: int = 300) -> list[str]:
    if not config.FMP_API_KEY or requests is None:
        return []
    try:
        r = requests.get(
            "https://financialmodelingprep.com/api/v3/stock-screener",
            params={"marketCapMoreThan": int(min_mcap_usd),
                    "isActivelyTrading": "true",
                    "isFund": "false", "isEtf": "false",
                    "limit": max(int(size) * 6, 600),
                    "apikey": config.FMP_API_KEY}, timeout=25)
        data = r.json()
        if not isinstance(data, list):
            return []
        # FMP sortiert nicht zuverlaessig -> nach Marktkap. absteigend ordnen,
        # damit oben die groessten (globalen) Unternehmen stehen.
        data.sort(key=lambda x: (x.get("marketCap") or 0), reverse=True)
        return [x.get("symbol") for x in data if x.get("symbol")][:size]
    except Exception:
        return []


def screen_yahoo(regions: list[str], min_mcap_usd: float,
                 size: int = 200) -> list[str]:
    if yf is None or EquityQuery is None:
        return []
    try:
        if len(regions) > 1:
            region_q = EquityQuery("or", [EquityQuery("eq", ["region", r])
                                          for r in regions])
        else:
            region_q = EquityQuery("eq", ["region", regions[0]])
        q = EquityQuery("and", [
            region_q,
            EquityQuery("gt", ["intradaymarketcap", float(min_mcap_usd)]),
        ])
        out, offset = [], 0
        while offset < size:
            batch = yf.screen(q, size=min(250, size - offset), offset=offset,
                              sortField="intradaymarketcap", sortAsc=False)
            quotes = (batch or {}).get("quotes", []) if isinstance(batch, dict) else []
            if not quotes:
                break
            out.extend(x.get("symbol") for x in quotes if x.get("symbol"))
            offset += len(quotes)
            if len(quotes) < 250:
                break
        return out
    except Exception:
        return []


def get_universe(regions: list[str], min_mcap_usd: float,
                 size: int = 200) -> tuple[list[str], str]:
    """Gibt (tickers, quelle) zurueck. quelle in {Yahoo, FMP, eingebaut}.
    Yahoo zuerst, weil es echte Laenderabdeckung bietet; der FMP-Gratis-Tarif
    liefert v.a. US/EOD-Daten und wuerde das Universum US-lastig machen."""
    tickers, src = [], ""
    tickers = screen_yahoo(regions, min_mcap_usd, size)
    src = "Yahoo" if tickers else ""
    if not tickers and config.FMP_API_KEY:
        tickers = screen_fmp(min_mcap_usd, size)
        src = "FMP" if tickers else ""
    if not tickers:
        tickers, src = DEFAULT_UNIVERSE, "eingebaut"

    seen, uniq = set(), []
    for t in tickers:
        if t and t not in seen:
            seen.add(t)
            uniq.append(t)
    return uniq[:size], src
