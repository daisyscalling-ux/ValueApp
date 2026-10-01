#!/usr/bin/env python3
"""
earnings_only.py - Taeglicher Mini-Lauf: NUR die Earnings-Call-Suche.

Frueher steckte die Earnings-Suche im grossen Nachtlauf. Jetzt getrennt:
Der grosse Lauf (Fair Value, Scores, Universum) laeuft nur alle 3 Tage, weil
sich Fundamentaldaten kaum aendern. Earnings Calls dagegen kommen taeglich neu
rein - also laeuft NUR diese Suche jeden Tag.

Schlank und schnell: nur die Kopfdaten der Calls (Firma, Datum, Quartal), keine
Volltexte. ~2-5 Minuten.
"""

from __future__ import annotations

import os
import sys
import time


def _melde(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def main() -> int:
    import socket
    socket.setdefaulttimeout(int(os.getenv("NETZ_TIMEOUT_S", "20")))

    start = time.time()
    try:
        import roic
        import store
    except Exception as e:
        _melde(f"[earnings] Import fehlgeschlagen: {e}")
        return 1

    if not roic.enabled():
        _melde("[earnings] ROIC NICHT AKTIV - Abbruch.")
        return 1

    deckel = int(os.getenv("TRANSKRIPT_DECKEL", "1500"))
    # Das grosse Universum (US + Europa + Asien), damit auch internationale
    # Earnings erscheinen - nicht nur index_universum (US+DAX).
    try:
        tickers = roic.export_universum()
    except Exception:
        tickers = None
    try:
        neu = roic.neue_transkripte(tickers=tickers, tage=90, deckel=deckel)
    except Exception as e:
        _melde(f"[earnings] Suche fehlgeschlagen: {e}")
        return 1

    if not hasattr(store, "set_transkripte"):
        _melde("[earnings] store.set_transkripte fehlt - Abbruch.")
        return 1

    try:
        store.set_transkripte(neu)
    except Exception as e:
        _melde(f"[earnings] Sheet-Speichern fehlgeschlagen: {e}")

    # Fuer Cloudflare: die Calls der letzten 90 Tage als JSON ins Repo.
    # Cloudflare liest sie von raw.githubusercontent.com und zeigt sie ohne
    # Suche als Liste an.
    try:
        import json, datetime as _dt
        from pathlib import Path as _P
        # nur echte Calls mit Datum, neueste zuerst
        calls = [c for c in neu if c.get("datum")]
        calls.sort(key=lambda c: c.get("datum", ""), reverse=True)
        schlank = [{
            "ticker": c.get("ticker"),
            "firma": c.get("firma") or c.get("name") or c.get("titel"),
            "datum": c.get("datum"),
            "quartal": c.get("quartal"),
            "jahr": c.get("jahr"),
            "tage_her": c.get("tage_her"),
        } for c in calls]
        ausgabe = {
            "stand": _dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
            "anzahl": len(schlank),
            "calls": schlank,
        }
        pfad = _P("daten/cf_earnings.json")
        pfad.parent.mkdir(parents=True, exist_ok=True)
        pfad.write_text(json.dumps(ausgabe, ensure_ascii=False), encoding="utf-8")
        _melde(f"[earnings] {len(schlank)} Calls nach {pfad} exportiert.")
    except Exception as e:
        _melde(f"[earnings] JSON-Export fehlgeschlagen: {e}")

    dauer = (time.time() - start) / 60.0
    _n_neu = sum(1 for r in neu if r.get("ist_neu"))
    _melde(f"[earnings] FERTIG: {len(neu)} Calls (davon {_n_neu} aktuell) "
           f"nach {dauer:.1f} min gespeichert.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
