#!/usr/bin/env python3
"""
test_eodhd.py - Prueft VOR dem Kauf, ob EODHD die Ticker und Felder liefert,
die Value Radar tatsaechlich braucht.

AUFRUF:
    python test_eodhd.py                  # mit Demo-Token (nur AAPL/MSFT u.ae.)
    python test_eodhd.py DEIN_API_TOKEN   # mit echtem/Gratis-Token: alle Ticker

Der Demo-Token ist frei, deckt aber nur wenige US-Ticker ab. Fuer den
aussagekraeftigen Test (BP.L, VWRL, 4GLD ...) brauchst du einen kostenlosen
Account-Token von eodhd.com/register - der Gratistarif hat 20 Aufrufe/Tag,
das reicht fuer diesen Test.

Das Skript kauft nichts und aendert nichts - es fragt nur ab und berichtet.
"""
import json
import sys
import urllib.request
import urllib.error

BASE = "https://eodhd.com/api"

# Deine Problemticker aus den Cron-Logs, mit EODHD-Schreibweise.
# EODHD nutzt SYMBOL.BOERSE (z.B. BP.LSE), nicht Yahoos BP.L.
TICKERS = [
    # (Yahoo-Ticker wie bei dir, EODHD-Ticker, warum er im Test ist)
    ("AAPL",     "AAPL.US",   "Kontrolle - muss immer klappen"),
    ("VWRL",     "VWRL.AS",   "DEIN DEPOT - yfinance: keine Kurse"),
    ("4GLD.DE",  "4GLD.XETRA","DEIN DEPOT - yfinance: keine Kurse"),
    ("BP.L",     "BP.LSE",    "Hedgefonds: 'Fair Value aus nur einer Methode'"),
    ("SHEL.L",   "SHEL.LSE",  "Hedgefonds abgelehnt (SHELL.XC)"),
    ("BHP.L",    "BHP.LSE",   "Hedgefonds abgelehnt"),
    ("GSK.L",    "GSK.LSE",   "Hedgefonds abgelehnt"),
    ("SAP.DE",   "SAP.XETRA", "Europa-Gegenprobe"),
    ("7269.T",   "7269.TSE",  "Asien - yfinance: Quote not found"),
]

# Felder, die deine Scorecard/Matrizen wirklich brauchen.
# (Kurs wird separat ueber den EOD-Endpoint geprueft, nicht hier.)
NEEDED = [
    ("market_cap",      "Marktkapitalisierung"),
    ("sector",          "Sektor"),
    ("pe_trailing",     "KGV"),
    ("eps_trailing",    "Gewinn je Aktie"),
    ("roe",             "Eigenkapitalrendite"),
    ("ev_ebitda",       "EV/EBITDA"),
    ("net_debt_ebitda", "Nettoverschuldung/EBITDA"),
    ("profit_margin",   "Nettomarge"),
    ("revenue_growth",  "Umsatzwachstum"),
    ("analyst_count",   "Anzahl Analysten"),
]


def _get(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "value-radar-test"})
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return {"_error": f"HTTP {e.code}"}
    except Exception as e:
        return {"_error": str(e)}


def check_price(tk, token):
    """Liefert EODHD ueberhaupt Kurse fuer diesen Ticker?"""
    d = _get(f"{BASE}/eod/{tk}?api_token={token}&fmt=json&period=d&order=d&limit=3")
    if isinstance(d, dict) and d.get("_error"):
        return None, d["_error"]
    if isinstance(d, list) and d:
        return d[0].get("close"), None
    return None, "leere Antwort"


def map_fundamentals(f):
    """Bildet die EODHD-Struktur auf die Felder ab, die Value Radar nutzt.
    So sehen wir, was WIRKLICH ankommt - nicht was die Werbung verspricht."""
    if not isinstance(f, dict) or f.get("_error"):
        return {}
    gen = f.get("General") or {}
    hl = f.get("Highlights") or {}
    val = f.get("Valuation") or {}
    tech = f.get("Technicals") or {}
    ana = f.get("AnalystRatings") or {}
    out = {
        "market_cap": hl.get("MarketCapitalization"),
        "sector": gen.get("Sector"),
        "pe_trailing": hl.get("PERatio"),
        "eps_trailing": hl.get("EarningsShare"),
        "roe": hl.get("ReturnOnEquityTTM"),
        "ev_ebitda": val.get("EnterpriseValueEbitda"),
        "net_debt_ebitda": None,        # wird unten aus der Bilanz gerechnet
        "profit_margin": hl.get("ProfitMargin"),
        "revenue_growth": hl.get("QuarterlyRevenueGrowthYOY"),
        "analyst_count": (ana.get("StrongBuy", 0) + ana.get("Buy", 0)
                          + ana.get("Hold", 0) + ana.get("Sell", 0)
                          + ana.get("StrongSell", 0)) or None,
    }
    # Nettoverschuldung/EBITDA aus der Bilanz versuchen
    try:
        bs = ((f.get("Financials") or {}).get("Balance_Sheet") or {}).get("yearly") or {}
        newest = sorted(bs.keys(), reverse=True)[0]
        row = bs[newest]
        debt = float(row.get("shortLongTermDebtTotal") or 0)
        cash = float(row.get("cash") or 0)
        ebitda = float(hl.get("EBITDA") or 0)
        if ebitda:
            out["net_debt_ebitda"] = round((debt - cash) / ebitda, 2)
    except Exception:
        pass
    return out


def check_fundamentals(tk, token):
    f = _get(f"{BASE}/fundamentals/{tk}?api_token={token}")
    if isinstance(f, dict) and f.get("_error"):
        return None, f["_error"]
    return map_fundamentals(f), None


def main():
    token = sys.argv[1] if len(sys.argv) > 1 else "demo"
    demo = token == "demo"
    print("=" * 66)
    print("EODHD-TEST fuer Value Radar")
    print(f"Token: {'DEMO (nur wenige US-Ticker!)' if demo else 'eigener Token'}")
    if demo:
        print("HINWEIS: Mit dem Demo-Token schlagen BP.LSE/VWRL.AS erwartungsgemaess")
        print("fehl. Fuer den echten Test einen Gratis-Token von eodhd.com nutzen:")
        print("   python test_eodhd.py DEIN_TOKEN")
    print("=" * 66)

    price_ok, fund_ok = [], []
    for ytk, etk, why in TICKERS:
        print(f"\n--- {ytk}  ->  EODHD: {etk}")
        print(f"    ({why})")
        px, err = check_price(etk, token)
        if px:
            print(f"    Kurs:        OK  -> {px}")
            price_ok.append(ytk)
        else:
            print(f"    Kurs:        FEHLT ({err})")

        fu, err = check_fundamentals(etk, token)
        if fu is None:
            print(f"    Fundamentals: FEHLT ({err})")
            continue
        have = [k for k, _ in NEEDED if fu.get(k) not in (None, "", 0)]
        miss = [lbl for k, lbl in NEEDED if fu.get(k) in (None, "", 0)]
        quote = len(have) / len(NEEDED) * 100
        print(f"    Fundamentals: {len(have)}/{len(NEEDED)} Felder ({quote:.0f} %)")
        if miss:
            print(f"      fehlt: {', '.join(miss)}")
        if quote >= 60:
            fund_ok.append(ytk)

    print("\n" + "=" * 66)
    print("ERGEBNIS")
    print("=" * 66)
    print(f"Kurse geliefert fuer:        {len(price_ok)}/{len(TICKERS)}  "
          f"{price_ok}")
    print(f"Fundamentals ausreichend:    {len(fund_ok)}/{len(TICKERS)}  "
          f"{fund_ok}")
    print()
    print("SO LIEST DU DAS:")
    print("- Kommen VWRL und 4GLD mit Kurs an? -> das EOD-Paket (16,58 $/Mon.)")
    print("  wuerde deine Depot-Kursluecken schliessen.")
    print("- Kommen BP/SHEL/GSK mit >=60 % Fundamentals an? -> das Fundamentals-")
    print("  Paket (49,99 $/Mon.) wuerde die Hedgefonds-Ablehnungen aufloesen.")
    print("- Bleiben die Felder auch bei EODHD leer, bringt der Kauf nichts.")
    print()
    print("Der Gratistarif hat 20 Aufrufe/Tag - dieser Test verbraucht bis zu")
    print(f"{len(TICKERS) * 2} Aufrufe. Ggf. auf zwei Tage aufteilen (TICKERS kuerzen).")


if __name__ == "__main__":
    main()
