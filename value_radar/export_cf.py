#!/usr/bin/env python3
"""
export_cf.py - Exportiert das grosse Universum als JSON fuer Cloudflare.

Laeuft alle 3 Tage im GitHub-Workflow. Scannt S&P 500 + NASDAQ-100 +
STOXX Europe 600 + Nikkei 225 (~1300-1400 Titel ueber US/Europa/Asien) mit
derselben score_ticker-Logik wie der Streamlit-Nachtlauf und schreibt das
Ergebnis nach daten/cf_universum.json.

Cloudflare liest diese JSON von raw.githubusercontent.com - damit hat die
CF-App fuer alle drei Regionen Fair Value, Scores UND Kursziele (yfinance
deckt Europa/Asien ab, was Finnhub/FMP im Worker nicht koennen).

WARUM PYTHON DAS MACHT: yfinance (die breiteste Kurszielquelle) laeuft nur in
Python. Cloudflare Workers koennen es nicht. Also holt Python die Daten einmal
alle 3 Tage, Cloudflare zeigt sie nur an.
"""

from __future__ import annotations

import json
import os
import sys
import time
import datetime as dt
from pathlib import Path

# Zeitbudget: 300 roic-Aufrufe/Minute ist die Bremse. ~1350 Titel x 15 Aufrufe
# = ~20000 Aufrufe / 300 = ~67 min reine Abrufzeit. Mit Puffer 150 min Budget.
BUDGET_MIN = float(os.getenv("EXPORT_BUDGET_MIN", "150"))
# Obergrenze je Netzabruf (haengende Server nicht unbegrenzt warten lassen).
NETZ_TIMEOUT_S = int(os.getenv("NETZ_TIMEOUT_S", "20"))
AUSGABE = Path(os.getenv("EXPORT_PFAD", "daten/cf_universum.json"))

# Nur die Felder, die der Cloudflare-Scanner + die Einzelanalyse nutzen.
EXPORT_FELDER = (
    "ticker", "name", "composite", "fair_value", "upside", "quantum",
    "entry", "price", "sector", "momentum", "quality", "value", "growth",
    "catalyst", "kauf_urteil", "analyst_count", "value_trap",
    "revenue_growth", "pe", "pb", "ev_ebitda", "roe", "ebitda_margin",
    "gross_margin", "net_debt_ebitda",
    # Fuer die Einzelanalyse-Kursziele (das, was CF sonst fehlt):
    "target_mean", "eps_forward", "eps_trailing", "beta",
    "52w_high", "52w_low", "hist_pe_median",
)


def _melde(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def main() -> int:
    import socket
    socket.setdefaulttimeout(NETZ_TIMEOUT_S)

    start = time.time()
    try:
        import roic
        import precompute
    except Exception as e:
        _melde(f"[export] Import fehlgeschlagen: {e}")
        return 1

    # Universum laden
    try:
        universum = roic.export_universum()
    except Exception as e:
        _melde(f"[export] Universum laden fehlgeschlagen: {e}")
        return 1
    _melde(f"[export] Universum: {len(universum)} Titel "
           f"(S&P500 + NASDAQ100 + STOXX600 + Nikkei225).")

    if not roic.enabled():
        _melde("[export] ROIC NICHT AKTIV - Abbruch (kein Schluessel?).")
        return 1

    ergebnisse = []
    uebersprungen = 0
    for i, ticker in enumerate(universum):
        verbraucht = (time.time() - start) / 60.0
        if verbraucht >= BUDGET_MIN:
            _melde(f"[export] Zeitbudget {BUDGET_MIN:.0f} min erreicht bei "
                   f"Titel {i}/{len(universum)} - speichere was da ist.")
            break
        try:
            row = precompute.score_ticker(ticker, deep=True)
        except Exception:
            row = None
        if not row or not row.get("price"):
            uebersprungen += 1
            continue
        # Nur die Export-Felder behalten
        schlank = {k: row.get(k) for k in EXPORT_FELDER if k in row}
        # Falls score_ticker den Ticker anders benennt, sicherstellen
        schlank["ticker"] = row.get("ticker") or ticker
        ergebnisse.append(schlank)

        if (i + 1) % 50 == 0:
            _melde(f"[export] {i + 1}/{len(universum)} gescannt, "
                   f"{len(ergebnisse)} mit Daten, {verbraucht:.0f} min.")

    # JSON schreiben
    AUSGABE.parent.mkdir(parents=True, exist_ok=True)
    ausgabe = {
        "stand": dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "anzahl": len(ergebnisse),
        "universum_groesse": len(universum),
        "kandidaten": ergebnisse,
    }
    AUSGABE.write_text(json.dumps(ausgabe, ensure_ascii=False), encoding="utf-8")

    dauer = (time.time() - start) / 60.0
    _melde(f"[export] FERTIG: {len(ergebnisse)} Titel nach {AUSGABE} "
           f"({uebersprungen} ohne Daten, {dauer:.0f} min).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
