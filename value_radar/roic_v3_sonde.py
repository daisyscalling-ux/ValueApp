#!/usr/bin/env python3
"""
roic_v3_sonde.py - Ermittelt die echte v3-Struktur, ohne zu raten.

roic hat auf API v3 umgestellt. Bekannt aus der Doku:
  - BASE ist jetzt  https://api.roic.ai/v3.0.0
  - Ticker im Format EXCHANGE:TICKER, z.B. NASDAQ:AAPL
  - Profil-Pfad: company/profile/{EX:TICKER}

Offen (und genau das testet diese Sonde mit deinem Key):
  1) Akzeptiert v3 auch den NACKTEN Ticker (AAPL) oder zwingend NASDAQ:AAPL?
  2) Wie heissen die uebrigen Endpunkte (Bilanz, Cashflow, Multiples, ...)?
  3) Liefert die Ticker-Suche die Boerse mit (damit wir EX:TICKER bauen koennen)?

Die Sonde macht ROHE Abrufe und zeigt je Variante den HTTP-Status. Nichts wird
veraendert - sie liest nur. Schick mir die Ausgabe, dann stelle ich roic.py
gezielt auf die tatsaechlich funktionierenden Pfade um.

AUFRUF (PowerShell):  $env:ROIC_API_KEY="dein_key"; python roic_v3_sonde.py
        (cmd)         set ROIC_API_KEY=dein_key && python roic_v3_sonde.py
"""
import json
import os
import urllib.error
import urllib.parse
import urllib.request

BASE_V3 = "https://api.roic.ai/v3.0.0"


def _key():
    if os.getenv("ROIC_API_KEY"):
        return os.environ["ROIC_API_KEY"]
    for p in (".streamlit/secrets.toml", "../.streamlit/secrets.toml"):
        if os.path.isfile(p):
            for zeile in open(p, encoding="utf-8"):
                if zeile.strip().startswith("ROIC_API_KEY"):
                    return zeile.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


KEY = _key()


def sonde(path, beschreibung=""):
    """Roher Abruf gegen v3. Gibt (status, kurzinhalt) und druckt eine Zeile."""
    url = f"{BASE_V3}/{path.lstrip('/')}?" + urllib.parse.urlencode({"apikey": KEY})
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "roic-v3-sonde"})
        with urllib.request.urlopen(req, timeout=20) as r:
            status = r.status
            roh = r.read().decode("utf-8", "replace")
        try:
            daten = json.loads(roh)
            # Bei Erfolg: welche Felder? (erste Zeile, falls Liste)
            if isinstance(daten, list) and daten:
                felder = sorted(daten[0].keys())[:8] if isinstance(daten[0], dict) else []
            elif isinstance(daten, dict):
                inner = daten.get("data")
                if isinstance(inner, list) and inner and isinstance(inner[0], dict):
                    felder = sorted(inner[0].keys())[:8]
                else:
                    felder = sorted(daten.keys())[:8]
            else:
                felder = []
            print(f"  [{status}] {path:52} {beschreibung}")
            if felder:
                print(f"         Felder: {felder}")
            return status, daten
        except Exception:
            print(f"  [{status}] {path:52} {beschreibung} (kein JSON)")
            return status, roh[:150]
    except urllib.error.HTTPError as e:
        print(f"  [{e.code}] {path:52} {beschreibung}")
        return e.code, None
    except Exception as e:
        print(f"  [ERR] {path:52} {e}")
        return None, None


def main():
    if not KEY:
        print("Kein ROIC_API_KEY gefunden. Setzen und erneut starten.")
        return
    print("=" * 70)
    print(f"roic v3-Sonde   BASE={BASE_V3}")
    print(f"Key: Laenge {len(KEY)}, endet auf ...{KEY[-4:]}")
    print("=" * 70)

    print("\n[A] TICKER-FORMAT: nackt vs. EXCHANGE:TICKER (Profil)")
    sonde("company/profile/AAPL", "nackter Ticker")
    sonde("company/profile/NASDAQ:AAPL", "mit NASDAQ-Praefix")
    sonde("company/profile/NYSE:AAPL", "mit NYSE-Praefix (falsch, zur Kontrolle)")

    print("\n[B] TICKER-SUCHE: liefert sie die Boerse mit?")
    # verschiedene moegliche Pfade probieren
    for p in ("tickers/search", "ticker/search", "search/tickers", "tickers"):
        sonde(f"{p}?query=Apple" if "?" not in p else p, "Suche 'Apple'")
    # Variante mit query als Teil des Pfads
    sonde("tickers/search/Apple", "Suche als Pfadsegment")

    print("\n[C] KERN-ENDPUNKTE mit NASDAQ:AAPL (die wir wirklich brauchen)")
    ex = "NASDAQ:AAPL"
    endpunkte = [
        (f"company/profile/{ex}",                 "Profil (Name/ISIN/Sektor)"),
        (f"fundamental/ratios/profitability/{ex}", "Profitabilitaets-Ratios"),
        (f"fundamental/per-share/{ex}",            "Je-Aktie"),
        (f"fundamental/enterprise-value/{ex}",     "Enterprise Value / Market Cap"),
        (f"fundamental/multiples/{ex}",            "Multiples (KGV etc.)"),
        (f"fundamental/income-statement/{ex}",     "GuV"),
        (f"fundamental/balance-sheet/{ex}",        "Bilanz"),
        (f"fundamental/cash-flow/{ex}",            "Cashflow"),
        (f"stock-prices/latest/{ex}",              "letzter Kurs"),
        (f"company/news/{ex}",                     "News"),
    ]
    for p, b in endpunkte:
        sonde(p, b)

    print("\n[D] Falls [C] scheitert: alternative Pfad-Schreibweisen fuer Profil")
    for p in (f"companies/profile/{ex}", f"company/{ex}/profile",
              f"fundamental/profile/{ex}", f"profile/{ex}"):
        sonde(p, "alternative Schreibweise")

    print("\n" + "=" * 70)
    print("Schick mir diese komplette Ausgabe. Aus den [200]-Zeilen lese ich")
    print("die echten v3-Pfade ab und stelle roic.py darauf um - inklusive")
    print("der Frage, ob wir das EXCHANGE-Praefix brauchen und woher es kommt.")


if __name__ == "__main__":
    main()
