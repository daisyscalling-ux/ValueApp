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
from peer_metadata import FIELDS as PEER_FIELDS, coverage
from listing_identity import listing_matches
from listing_reference import apply_reference
from export_continuity import snapshots, baseline, scan_order, combine

EXPORT_FELDER = (
    "ticker", "name", "composite", "fair_value", "upside", "quantum",
    "entry", "price", "sector", "momentum", "quality", "value", "growth",
    "catalyst", "kauf_urteil", "analyst_count", "value_trap",
    "revenue_growth", "pe", "pb", "ev_ebitda", "roe", "ebitda_margin",
    "gross_margin", "net_debt_ebitda", "fcff_margin",
    # Fuer die Einzelanalyse-Kursziele (das, was CF sonst fehlt):
    "target_mean", "eps_forward", "eps_trailing", "beta",
    "52w_high", "52w_low", "hist_pe_median",
)
EXPORT_FELDER = tuple(dict.fromkeys(EXPORT_FELDER + PEER_FIELDS))


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
    _melde(f"[export] Universum roh: {len(universum)} Titel "
           f"(S&P500 + NASDAQ100 + STOXX600 + Nikkei225).")

    # WICHTIG: dieselbe Ticker-Aufbereitung wie der funktionierende Nachtlauf.
    # Ohne sie laufen Pence-Titel (BP.L), Zweitnotierungen (BHPL.XC) und
    # kaputte Symbole in yfinance-404 mit 30s-Timeout - genau der Grund, warum
    # der erste Lauf nur 28 von 1390 schaffte.
    try:
        # Zusammenfassen nur im selben Land (index_membership.collapse_same_market); das boersenuebergreifende
        # precompute.collapse_listings verdraengte gleichnamige Indexwerte (DTE.DE durch DTE, MRK.DE durch MRK).
        from index_membership import collapse_same_market
        prio = getattr(precompute, "_SUFFIX_PRIORITY", None)
        universum = precompute.filter_boersen(
            collapse_same_market(precompute.ersetze_pence_durch_adr(universum), prio if isinstance(prio, dict) else {}))
        _melde(f"[export] Universum aufbereitet: {len(universum)} Titel "
               f"(ADR-ersetzt, Zweitnotierungen entfernt).")
    except Exception as e:
        _melde(f"[export] Aufbereitung fehlgeschlagen (nutze roh): {e}")

    # Indexzugehoerigkeit je Ticker in Export-Schreibweise (Pence-Titel laufen als ADR).
    try:
        scope = roic.export_scope()
    except Exception:
        scope = {}
    scope = scope if isinstance(scope, dict) else {}
    mitglied = {k: list(v) for k, v in (scope.get("members") or {}).items()}
    pence = getattr(precompute, "PENCE_ZU_ADR", None)
    for orig, adr in (pence.items() if isinstance(pence, dict) else ()):
        if orig in mitglied and isinstance(adr, str):
            mitglied.setdefault(adr, list(mitglied[orig]))

    if not roic.enabled():
        _melde("[export] ROIC NICHT AKTIV - Abbruch (kein Schluessel?).")
        return 1

    now = dt.datetime.now(dt.timezone.utc)
    saved = baseline(universum, snapshots(AUSGABE), now)
    universum = scan_order(universum, saved)
    _melde(f"[export] {len(saved)} datierte Bestandswerte; aelteste/fehlende Titel zuerst.")
    attempted = 0
    ergebnisse = []
    identity_rejected = []
    uebersprungen = 0
    for i, ticker in enumerate(universum):
        verbraucht = (time.time() - start) / 60.0
        if verbraucht >= BUDGET_MIN:
            _melde(f"[export] Zeitbudget {BUDGET_MIN:.0f} min erreicht bei "
                   f"Titel {i}/{len(universum)} - speichere was da ist.")
            break
        attempted += 1
        try:
            row = precompute.score_ticker(ticker, deep=True)
        except Exception:
            row = None
        if not row or not row.get("price"):
            uebersprungen += 1
            continue
        if row.get('listing_symbol') and not listing_matches(ticker,row['listing_symbol']):
            identity_rejected.append({'ticker':ticker,'rejected_listing':row['listing_symbol']})
            continue
        # Nur die Export-Felder behalten
        schlank = {k: row.get(k) for k in EXPORT_FELDER if k in row}
        # Falls score_ticker den Ticker anders benennt, sicherstellen
        schlank["ticker"] = ticker
        schlank = apply_reference(schlank)
        if schlank.get('listing_reference_status') in ('expired','input_mismatch'):
            identity_rejected.append({'ticker':ticker,'rejected_listing':schlank.get('listing_symbol'),'reason':schlank['listing_reference_status']})
            continue
        ergebnisse.append(schlank)

        if (i + 1) % 50 == 0:
            _melde(f"[export] {i + 1}/{len(universum)} gescannt, "
                   f"{len(ergebnisse)} mit Daten, {verbraucht:.0f} min.")

    refreshed = len(ergebnisse)
    observed = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    ergebnisse = combine(universum, saved, ergebnisse, {r["ticker"] for r in identity_rejected}, observed)
    for r in ergebnisse:
        r["index_membership"] = mitglied.get(r["ticker"], [])
    # EBITDA-Marge: gekennzeichneter Ersatz aus dem eigenen Jahresabschluss, nur wenn ROIC keine liefert.
    import ebitda_margin_fallback
    _melde(f"[export] EBITDA-Marge aus Jahresabschluss ergaenzt: {ebitda_margin_fallback.apply(ergebnisse, Path(__file__).resolve().parent / 'daten' / 'fundamentals')}")

    # JSON schreiben
    AUSGABE.parent.mkdir(parents=True, exist_ok=True)
    ausgabe = {
        "stand": observed,
        "anzahl": len(ergebnisse),
        "scan": {"attempted": attempted, "refreshed": refreshed, "retained": len(ergebnisse)-refreshed, "pending": len(universum)-attempted, "complete": attempted == len(universum)},
        "universum_groesse": len(universum),
        "kandidaten": ergebnisse,
        "identity_rejected": identity_rejected,
        "peer_schema_version": 1,
        "peer_metadata_coverage": coverage(ergebnisse),
        "index_scope": {**{k: v for k, v in scope.items() if k != "members"},
                        "members": {t: mitglied[t] for t in dict.fromkeys(universum) if mitglied.get(t)}},
    }
    AUSGABE.write_text(json.dumps(ausgabe, ensure_ascii=False), encoding="utf-8")

    dauer = (time.time() - start) / 60.0
    _melde(f"[export] FERTIG: {len(ergebnisse)} Titel nach {AUSGABE} "
           f"({uebersprungen} ohne Daten, {dauer:.0f} min).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


