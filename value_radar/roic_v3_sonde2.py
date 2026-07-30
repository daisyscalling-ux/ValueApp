#!/usr/bin/env python3
"""
roic_v3_sonde2.py - Klaert die zwei offenen v3-Fragen:

  1) TICKER-SUCHE gab 401 (Auth). Test: geht sie mit Bearer-Header?
     Und wie heisst der richtige Suchpfad?
  2) EXCHANGE-PRAEFIX: Wir haben nur "AAPL", v3 will "NASDAQ:AAPL".
     Woher kommt die Boerse? Kandidaten:
       - die Ticker-Suche liefert sie
       - ein "Universe"/"exchange"-Endpunkt listet Symbole
       - man kann NASDAQ:AAPL erraten (aber KO=NYSE, nicht ableitbar)

Diese Sonde testet BEIDE Auth-Methoden (Query ?apikey= UND Bearer-Header)
gegen mehrere moegliche Such-/Auffindungs-Pfade. Nichts wird veraendert.

AUFRUF (PowerShell):  $env:ROIC_API_KEY="dein_key"; python roic_v3_sonde2.py
"""
import json
import os
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://api.roic.ai/v3.0.0"


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


def ruf(path, auth="query", params=None):
    """Ein Abruf. auth='query' -> ?apikey=, auth='bearer' -> Header.
    Gibt (status, daten) zurueck und druckt eine kompakte Zeile."""
    params = dict(params or {})
    headers = {"User-Agent": "roic-v3-sonde2"}
    if auth == "query":
        params["apikey"] = KEY
    else:
        headers["Authorization"] = f"Bearer {KEY}"
    qs = ("?" + urllib.parse.urlencode(params)) if params else ""
    url = f"{BASE}/{path.lstrip('/')}{qs}"
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=20) as r:
            status = r.status
            roh = r.read().decode("utf-8", "replace")
        try:
            daten = json.loads(roh)
        except Exception:
            daten = roh[:200]
        tag = f"[{status}/{auth}]"
        print(f"  {tag:16} {path:38} {str(params.get('query', '') or params.get('q', ''))}")
        return status, daten
    except urllib.error.HTTPError as e:
        print(f"  [{e.code}/{auth}]".ljust(18) + f"{path:38}")
        return e.code, None
    except Exception as e:
        print(f"  [ERR/{auth}]".ljust(18) + f"{path:38} {e}")
        return None, None


def zeig_felder(daten, titel):
    """Bei Erfolg: Struktur zeigen, damit wir sehen, ob die Boerse drinsteht."""
    if not daten:
        return
    obj = None
    if isinstance(daten, list) and daten:
        obj = daten[0]
    elif isinstance(daten, dict):
        for k in ("data", "results", "tickers", "matches"):
            v = daten.get(k)
            if isinstance(v, list) and v:
                obj = v[0]
                break
        if obj is None:
            obj = daten
    if isinstance(obj, dict):
        print(f"       {titel}: {sorted(obj.keys())[:12]}")
        # Nach boersenrelevanten Feldern suchen
        for feld in ("exchange", "symbol", "ticker", "mic", "exchange_symbol",
                     "company_symbols", "primary_exchange", "full_symbol"):
            if feld in obj:
                print(f"         {feld} = {obj[feld]}")


def main():
    if not KEY:
        print("Kein ROIC_API_KEY. Setzen und erneut starten.")
        return
    print("=" * 68)
    print(f"roic v3-Sonde 2   Key ...{KEY[-4:]}")
    print("=" * 68)

    print("\n[1] TICKER-SUCHE - beide Auth-Methoden, mehrere Pfade")
    for pfad in ("tickers/search", "ticker/search", "search",
                 "companies/search", "tickers"):
        for auth in ("query", "bearer"):
            s, d = ruf(pfad, auth, {"query": "Apple"})
            if s == 200:
                zeig_felder(d, "Suchtreffer")

    print("\n[2] Alternative Such-Parameter (q statt query)")
    for pfad in ("tickers/search", "search"):
        s, d = ruf(pfad, "bearer", {"q": "Apple"})
        if s == 200:
            zeig_felder(d, "Suchtreffer")

    print("\n[3] Profil mit Bearer (Gegenprobe - muss auch 200 geben)")
    s, d = ruf("company/profile/NASDAQ:AAPL", "bearer")
    if s == 200:
        zeig_felder(d, "Profil AAPL")

    print("\n[4] Liefert das PROFIL die Boerse? (company_symbols/exchange)")
    s, d = ruf("company/profile/NASDAQ:AAPL", "query")
    if s == 200 and isinstance(d, (dict, list)):
        obj = d[0] if isinstance(d, list) else d
        if isinstance(obj, dict):
            print(f"       exchange        = {obj.get('exchange')}")
            print(f"       company_symbols = {obj.get('company_symbols')}")

    print("\n[5] Gibt es einen Symbol-/Universe-Endpunkt zum Nachschlagen?")
    for pfad in ("tickers/list", "tickers", "companies/list",
                 "reference/tickers", "exchanges"):
        for auth in ("query", "bearer"):
            s, d = ruf(pfad, auth)
            if s == 200:
                zeig_felder(d, pfad)
                break

    print("\n[6] Direkter Test: geht HSBC + europaeische Titel unter v3?")
    # HSBC koennte NYSE (ADR) oder LSE sein - beide probieren
    for ex_t in ("NYSE:HSBC", "LSE:HSBA", "LON:HSBA", "NASDAQ:HSBC",
                 "XETRA:SAP", "ETR:SAP", "FRA:SAP"):
        s, d = ruf(f"company/profile/{ex_t}", "query")
        if s == 200:
            obj = d[0] if isinstance(d, list) else d
            if isinstance(obj, dict):
                print(f"       -> {ex_t}: {obj.get('company_symbols') or obj.get('exchange')}")

    print("\n" + "=" * 68)
    print("Schick mir die Ausgabe. Entscheidend: welche Auth+Pfad-Kombi bei")
    print("der Ticker-Suche 200 gibt, und ob dort (oder im Profil) die Boerse")
    print("steht. Damit koennen wir aus 'AAPL' das noetige 'NASDAQ:AAPL' bauen.")


if __name__ == "__main__":
    main()
