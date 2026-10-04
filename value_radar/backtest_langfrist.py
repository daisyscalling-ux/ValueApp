#!/usr/bin/env python3
"""
backtest_langfrist.py - Loesung B, Option 1: LANGFRIST-Ueberrendite.

FRAGE: Welche fundamentalen Eigenschaften fuehrten dazu, dass eine Aktie den
MARKT ueber 1-3 Jahre schlug? Das ist die Frage, fuer die Value/Quality-
Faktoren tatsaechlich gemacht sind (nicht kurzfristige Spruenge - die waren
regime-abhaengig und nicht robust, siehe backtest_fundamental).

ZIEL-VARIABLE: relative Ueberrendite = Aktie-Rendite MINUS S&P500-Rendite ueber
denselben Zeitraum. So faengt man ab, dass in Hausse-Phasen einfach alles
steigt - es zaehlt nur, ob die Aktie BESSER war als der Markt.

POINT-IN-TIME (das Kernstueck gegen Look-ahead):
  roic liefert KEIN Veroeffentlichungsdatum, nur period_end_date. Deshalb:
  Ein Quartalsbericht gilt erst PUBLIKATIONS_PUFFER Tage NACH Periodenende als
  bekannt. Zum Stichtag T nutzen wir nur Quartale mit:
      period_end_date + PUBLIKATIONS_PUFFER <= T
  Puffer 60 Tage - konservativ (SEC-Frist fuer 10-Q ist 40 Tage, die meisten
  grossen Firmen berichten nach 4-6 Wochen). Restrisiko: eine Firma, die
  ausnahmsweise >60 Tage braucht, wird zwischen Tag 60 und ihrer echten
  Meldung faelschlich als bekannt behandelt - selten, und konservativ.

METHODE wie Stufe 1: Survivorship vermieden (Mitgliederliste), Training/Test
getrennt, z-Test, nur Signale die in BEIDEN Phasen signifikant sind zaehlen.

Laeuft im GitHub-Workflow (braucht ROIC_API_KEY + yfinance).
"""

from __future__ import annotations

import os
import sys
import json
import time
import datetime as dt
from pathlib import Path

import numpy as np
import pandas as pd

# --- Parameter -------------------------------------------------------------
MITGLIEDER_CSV = "sp500_alle_mitglieder_seit_2020_bis_2026-10-03.csv"
START = "2016-01-01"   # frueh genug fuer Fundamental-Historie + lange Zukunftsfenster
ENDE = "2026-10-03"
UEBERRENDITE_SCHWELLE = 0.0   # 0 = schlaegt den Markt ueberhaupt; spaeter evtl. 0.05
PUBLIKATIONS_PUFFER = 60            # Tage nach Periodenende bis "bekannt"
HORIZONTE = {"1J": 252, "2J": 504, "3J": 756}   # Handelstage
STICHTAG_ABSTAND = 21              # ~monatlich
TRAIN_ENDE = "2021-06-30"   # Training: Stichtage bis Mitte 2021, Test danach
NETZ_TIMEOUT = int(os.getenv("NETZ_TIMEOUT_S", "20"))


def _melde(m: str) -> None:
    print(m, file=sys.stderr, flush=True)


def lade_mitglieder(pfad: str) -> pd.DataFrame:
    kandidaten = [pfad, f"daten/{pfad}", f"../{pfad}"]
    treffer = next((k for k in kandidaten if Path(k).exists()), None)
    if not treffer:
        raise FileNotFoundError(f"Mitgliederliste nicht gefunden: {kandidaten}")
    df = pd.read_csv(treffer)
    df.columns = [c.strip().lstrip("\ufeff") for c in df.columns]
    df = df.rename(columns={"Ticker": "ticker",
                            "Erste_Aufnahme_seit_2020": "aufnahme",
                            "Letzter_Austritt_seit_2020": "austritt"})
    df["aufnahme"] = pd.to_datetime(df["aufnahme"], errors="coerce")
    df["austritt"] = pd.to_datetime(df["austritt"], errors="coerce")
    return df[["ticker", "aufnahme", "austritt"]]


def ist_mitglied(row, t: pd.Timestamp) -> bool:
    if pd.notna(row["aufnahme"]) and t < row["aufnahme"]:
        return False
    if pd.notna(row["austritt"]) and t >= row["austritt"]:
        return False
    return True


# --- roic-Fundamentals (quarterly income) ----------------------------------
def hole_fundamentals(ticker: str) -> pd.DataFrame | None:
    """Quartals-income aus roic. Rueckgabe: DataFrame je Quartal mit
    period_end_date, revenue, eps, net_income, Margen - oder None."""
    import requests
    key = os.getenv("ROIC_API_KEY")
    if not key:
        return None
    # Symbol aufloesen (EXCHANGE:TICKER) - vereinfacht ueber tickers/search
    sym = _roic_symbol(ticker)
    url = f"https://api.roic.ai/v3.0.0/fundamental/income-statement/{sym}"
    try:
        r = requests.get(url, params={"period_type": "quarterly", "limit": 40, "apikey": key},
                         timeout=NETZ_TIMEOUT)
        if not r.ok:
            return None
        d = r.json()
        rows = d if isinstance(d, list) else d.get("data", [])
        if not rows:
            return None
        recs = []
        for z in rows:
            ped = z.get("period_end_date")
            if not ped:
                continue
            recs.append({
                "period_end": pd.to_datetime(ped, errors="coerce"),
                "revenue": _num(z.get("is_sales_revenue_turnover")),
                "eps": _num(z.get("eps")),
                "net_income": _num(z.get("is_net_income")),
                "gross_margin": _num(z.get("gross_margin")),
                "oper_margin": _num(z.get("oper_margin")),
                "profit_margin": _num(z.get("profit_margin")),
                "ebitda": _num(z.get("ebitda")),
            })
        df = pd.DataFrame(recs).dropna(subset=["period_end"]).sort_values("period_end")
        return df if len(df) >= 8 else None
    except Exception:
        return None


_SYM_CACHE: dict = {}
def _roic_symbol(ticker: str) -> str:
    if ticker in _SYM_CACHE:
        return _SYM_CACHE[ticker]
    import requests
    key = os.getenv("ROIC_API_KEY")
    try:
        r = requests.get("https://api.roic.ai/v3.0.0/tickers/search",
                         params={"query": ticker, "apikey": key}, timeout=NETZ_TIMEOUT)
        if r.ok:
            d = r.json()
            rows = d if isinstance(d, list) else d.get("data", [])
            basis = ticker.upper().split(".")[0]
            for row in rows:
                s = str(row.get("symbol", ""))
                if s.split(":")[-1].upper() == basis:
                    if row.get("listing_country_code") == "US" or row.get("is_primary"):
                        _SYM_CACHE[ticker] = s
                        return s
            if rows:
                _SYM_CACHE[ticker] = str(rows[0].get("symbol", ticker))
                return _SYM_CACHE[ticker]
    except Exception:
        pass
    _SYM_CACHE[ticker] = ticker
    return ticker


def _num(x):
    try:
        v = float(x)
        return v if np.isfinite(v) else np.nan
    except Exception:
        return np.nan


def lade_kurse(tickers, start, ende):
    import yfinance as yf
    teile = []
    for i in range(0, len(tickers), 50):
        block = tickers[i:i + 50]
        try:
            d = yf.download(block, start=start, end=ende, auto_adjust=True,
                            progress=False, threads=True)["Close"]
            if isinstance(d, pd.Series):
                d = d.to_frame(block[0])
            teile.append(d)
            _melde(f"[kurse] {i + len(block)}/{len(tickers)}")
        except Exception as e:
            _melde(f"[kurse] Block {i}: {e}")
    k = pd.concat(teile, axis=1)
    return k.loc[:, ~k.columns.duplicated()]


# --- Fundamentale Faktoren zum Stichtag T (point-in-time) ------------------
def faktoren_an(fund: pd.DataFrame, t: pd.Timestamp, preis_t: float) -> dict:
    """Nur Quartale, die zu T BEKANNT waren (period_end + Puffer <= T)."""
    grenze = t - pd.Timedelta(days=PUBLIKATIONS_PUFFER)
    bekannt = fund[fund["period_end"] <= grenze]
    if len(bekannt) < 4:   # mind. 1 Jahr bekannt (TTM)
        return {}
    letzte4 = bekannt.tail(4)
    hat_vorjahr = len(bekannt) >= 8
    vor4 = bekannt.tail(8).head(4) if hat_vorjahr else None

    eps_ttm = letzte4["eps"].sum()
    rev_ttm = letzte4["revenue"].sum()
    eps_ttm_vor = vor4["eps"].sum() if vor4 is not None else np.nan
    rev_ttm_vor = vor4["revenue"].sum() if vor4 is not None else np.nan

    f = {}
    # BEWERTUNG
    if eps_ttm and eps_ttm > 0:
        f["kgv"] = preis_t / eps_ttm
    # QUALITAET (Durchschnitt der letzten 4 Quartale)
    f["gross_margin"] = letzte4["gross_margin"].mean()
    f["oper_margin"] = letzte4["oper_margin"].mean()
    f["profit_margin"] = letzte4["profit_margin"].mean()
    # WACHSTUM (TTM vs Vorjahr-TTM)
    if rev_ttm_vor and rev_ttm_vor > 0:
        f["umsatz_wachstum"] = rev_ttm / rev_ttm_vor - 1
    if eps_ttm_vor and eps_ttm_vor > 0 and eps_ttm:
        f["eps_wachstum"] = eps_ttm / eps_ttm_vor - 1
    # BESCHLEUNIGUNG: juengstes Quartal-Wachstum vs. ein Jahr davor
    if len(bekannt) >= 5:
        q_neu = bekannt.iloc[-1]["revenue"]
        q_vor = bekannt.iloc[-5]["revenue"]
        q_neu2 = bekannt.iloc[-2]["revenue"]
        q_vor2 = bekannt.iloc[-6]["revenue"] if len(bekannt) >= 6 else np.nan
        if q_vor and q_vor > 0 and q_vor2 and q_vor2 > 0:
            g_neu = q_neu / q_vor - 1
            g_alt = q_neu2 / q_vor2 - 1
            f["wachstum_beschleunigung"] = g_neu - g_alt
    # MARGEN-TREND: steigt die operative Marge?
    if len(bekannt) >= 8:
        m_neu = bekannt.tail(4)["oper_margin"].mean()
        m_alt = bekannt.tail(8).head(4)["oper_margin"].mean()
        if pd.notna(m_neu) and pd.notna(m_alt):
            f["margen_trend"] = m_neu - m_alt
    return {k: v for k, v in f.items() if pd.notna(v)}


def main() -> int:
    import socket
    socket.setdefaulttimeout(NETZ_TIMEOUT)

    mitglieder = lade_mitglieder(MITGLIEDER_CSV)
    tickers = mitglieder["ticker"].tolist()

    # 1) Fundamentals holen (1 roic-Abruf je Titel)
    _melde(f"[fund] lade Fundamentals fuer {len(tickers)} Titel ...")
    fund_map = {}
    for i, tk in enumerate(tickers):
        if i % 50 == 0:
            _melde(f"[fund] {i}/{len(tickers)}")
        df = hole_fundamentals(tk)
        if df is not None:
            fund_map[tk] = df
    _melde(f"[fund] {len(fund_map)} Titel mit Fundamentals")

    # 2) Kurse holen (Titel + S&P500-Index als Benchmark)
    kurse = lade_kurse([t for t in tickers if t in fund_map], START, ENDE)
    kurse.index = pd.to_datetime(kurse.index)
    _melde(f"[kurse] {kurse.shape[0]} Tage, {kurse.shape[1]} Titel")
    import yfinance as yf
    _melde("[index] lade S&P500 (^GSPC) als Benchmark ...")
    idx = yf.download("^GSPC", start=START, end=ENDE, auto_adjust=True, progress=False)["Close"]
    if hasattr(idx, "columns"):
        idx = idx.iloc[:, 0]
    idx.index = pd.to_datetime(idx.index)

    # 3) Scan
    handelstage = kurse.index
    stichtage = handelstage[252::STICHTAG_ABSTAND]
    mitg_lookup = {r["ticker"]: r for _, r in mitglieder.iterrows()}
    daten = []
    for si, t in enumerate(stichtage):
        if si % 10 == 0:
            _melde(f"[scan] {si}/{len(stichtage)} ({t.date()})")
        for tk, fund in fund_map.items():
            if tk not in kurse.columns or not ist_mitglied(mitg_lookup[tk], t):
                continue
            serie = kurse[tk].loc[:t].dropna()
            if len(serie) < 10:
                continue
            preis_t = serie.iloc[-1]
            fak = faktoren_an(fund, t, preis_t)
            if not fak:
                continue
            e = {"ticker": tk, "datum": t, "train": t <= pd.Timestamp(TRAIN_ENDE), **fak}
            idx_t = idx.loc[:t].dropna()
            if idx_t.empty:
                continue
            idx_preis_t = idx_t.iloc[-1]
            for name, tage in HORIZONTE.items():
                fenster = kurse[tk].loc[t:].iloc[1:tage + 1].dropna()
                idx_fenster = idx.loc[t:].iloc[1:tage + 1].dropna()
                if len(fenster) < tage * 0.8 or len(idx_fenster) < tage * 0.8:
                    e[f"schlaegt_markt_{name}"] = np.nan   # zu wenig Zukunft
                else:
                    aktie_ret = fenster.iloc[-1] / preis_t - 1
                    markt_ret = idx_fenster.iloc[-1] / idx_preis_t - 1
                    ueberrendite = aktie_ret - markt_ret
                    e[f"schlaegt_markt_{name}"] = 1 if ueberrendite > UEBERRENDITE_SCHWELLE else 0
            daten.append(e)

    df = pd.DataFrame(daten)
    df.to_parquet("backtest_langfrist_rohdaten.parquet")
    _melde(f"[scan] {len(df)} Datenpunkte")
    auswerten(df)
    return 0


def auswerten(df: pd.DataFrame) -> None:
    faktoren = ["kgv", "gross_margin", "oper_margin", "profit_margin",
                "umsatz_wachstum", "eps_wachstum", "wachstum_beschleunigung",
                "margen_trend"]
    ergebnis = {}
    for ziel in [f"schlaegt_markt_{h}" for h in HORIZONTE]:
        d = df.dropna(subset=[ziel])
        ergebnis[ziel] = {
            "basisrate_train": round(d[d["train"]][ziel].mean() * 100, 1),
            "basisrate_test": round(d[~d["train"]][ziel].mean() * 100, 1),
            "n_train": int(d["train"].sum()), "n_test": int((~d["train"]).sum()),
            "faktoren": {},
        }
        for fak in faktoren:
            if fak not in d.columns:
                continue
            dd = d.dropna(subset=[fak])
            res = {}
            for phase, maske in [("train", dd["train"]), ("test", ~dd["train"])]:
                teil = dd[maske]
                if len(teil) < 100:
                    continue
                q = teil[fak].quantile([0.33, 0.67])
                gh = teil[teil[fak] >= q.iloc[1]][ziel]
                gt = teil[teil[fak] <= q.iloc[0]][ziel]
                hoch, tief = gh.mean(), gt.mean()
                nh, nt = len(gh), len(gt)
                pp = (gh.sum() + gt.sum()) / (nh + nt)
                se = (pp * (1 - pp) * (1 / nh + 1 / nt)) ** 0.5
                zscore = (hoch - tief) / se if se > 0 else 0.0
                res[phase] = {"oberstes_drittel": round(hoch * 100, 1),
                              "unterstes_drittel": round(tief * 100, 1),
                              "spread": round((hoch - tief) * 100, 1),
                              "z": round(zscore, 2), "signifikant": bool(abs(zscore) >= 1.96)}
            ergebnis[ziel]["faktoren"][fak] = res

    for zp in ("backtest_langfrist_ergebnis.json", "daten/backtest_langfrist_ergebnis.json"):
        try:
            p = Path(zp); p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(ergebnis, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass

    print("\n" + "=" * 72)
    print("LANGFRIST-BACKTEST - welche Faktoren schlugen den Markt ueber 1-3 Jahre?")
    print("(Ziel: Ueberrendite vs S&P500, point-in-time, 60-Tage-Puffer)")
    print("=" * 72)
    for ziel, e in ergebnis.items():
        print(f"\n### {ziel} ###  Basis: Train {e['basisrate_train']}% / Test {e['basisrate_test']}%")
        print(f"{'Faktor':24s} | {'Phase':5s} | ob.Dr | unt.Dr | Spread | signif")
        print("-" * 68)
        for fak, res in e["faktoren"].items():
            for ph in ("train", "test"):
                if ph in res:
                    r = res[ph]
                    tr = res.get("train", {})
                    marke = ""
                    if ph == "test" and r["signifikant"] and abs(r["spread"]) > 2 \
                       and tr.get("signifikant") and abs(tr.get("spread", 0)) > 2 \
                       and (r["spread"] > 0) == (tr.get("spread", 0) > 0):
                        marke = "  <- ROBUST"
                    print(f"{fak:24s} | {ph:5s} | {r['oberstes_drittel']:4.1f}% | "
                          f"{r['unterstes_drittel']:5.1f}% | {r['spread']:+5.1f}% | "
                          f"{'JA' if r['signifikant'] else 'nein'}{marke}")
    print("\nROBUST = signifikant in Training UND Test, gleiches Vorzeichen.")
    print("Nur robuste Faktoren haben echten (historischen) Vorhersagewert.")


if __name__ == "__main__":
    raise SystemExit(main())
