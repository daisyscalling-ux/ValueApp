"""Scanner-Werte aus dem App-Rechenweg (evaluateStock in TypeScript), seit 13.11.2026.

Die Pipeline holt die Daten wie bisher (providers/ROIC); gerechnet wird mit derselben Methode wie in der
Einzelanalyse (risk_precompute/src/lib, identische Kopie aus valueapp-cf). Faellt die TS-Rechnung aus,
bleiben die Python-Werte stehen und werden als scanner_method "python-v1" gekennzeichnet; die App weist
darauf hin. Siehe BEWERTUNG_RISIKODATEN.md.
"""
import json
import math
import os
import re
import subprocess
import tempfile

METHODE = "ts-evaluate-v1"
ALT = "python-v1"
FELDER = ("scanner_method", "playbook", "lifecycle_phase", "composite", "fair_value", "upside", "entry", "quantum",
          "target_12m", "fv_confidence", "fv_reliable", "valuation_issues", "momentum", "quality", "value", "growth",
          "catalyst", "health", "cat_neutral", "value_trap", "vt_warnung", "kauf_urteil",
          "peer_count", "composite_peer_metrics", "ev_ebitda_anchor", "cash_conversion", "cash_conversion_source", "health_source", "health_parts", "health_raw", "health_profile",
          "market_cap", "market_cap_source")
PRIVAT_ERLAUBT = {"_analyst_trend", "_cash_conversion_history", "_risk_coverage", "_pruef_eingang", "_cyclicality",
                  "_fundamental_supplement", "_supplement_symbol"}


def _sauber(x):
    """Nur JSON-faehige Werte; NaN/inf und fremde Objekte werden zu None."""
    if x is None or isinstance(x, (bool, str)):
        return x
    if isinstance(x, (int, float)):
        return x if math.isfinite(x) else None
    if isinstance(x, dict):
        return {str(k): _sauber(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_sauber(v) for v in x]
    try:                                   # numpy-Zahlen u. ae.
        v = float(x)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


# Rohwerte und Herkunft fuer gesperrte Zeilen (Datenpruefung der App): nur Diagnose, fliesst in keine Rechnung.
DIAGNOSE = ("price", "currency", "shares_out", "market_cap", "enterprise_value", "52w_high", "52w_low", "eps_trailing",
            "_quelle", "_roic_fx", "_roic_felder", "_pence_normalised", "_src")


ZYKLIK_METHODE = "margin_cv_v1"


def zyklik(diagnose):
    """Datenbasierte Zyklik fuer App und Scanner (valuation.ts, dataCyclical prueft erneut und schliesst Finanzwerte
    und defensive Sektoren aus). Nur mit Margenreihe; das alte Flag _ist_zyklisch wird nicht mehr weitergegeben."""
    if not isinstance(diagnose, dict) or not isinstance(diagnose.get("margen"), list):
        return None
    return {"method": ZYKLIK_METHODE, "margins": _sauber(diagnose["margen"]), "cv": _sauber(diagnose.get("variationskoeffizient")),
            "cyclical": bool(diagnose.get("zyklisch")), "years": diagnose.get("jahre")}


def eingabe(f, analyst=None):
    """Fund-Dict fuer evaluateStock: dieselben Feldnamen wie in der App; private Felder nur, wenn erlaubt."""
    d = {k: _sauber(v) for k, v in (f or {}).items() if not str(k).startswith("_") or k in PRIVAT_ERLAUBT}
    d["_pruef_eingang"] = {k: _sauber((f or {}).get(k)) for k in DIAGNOSE if (f or {}).get(k) is not None}
    z = zyklik((f or {}).get("_zyklus_diagnose"))
    if z:
        d["_cyclicality"] = z
    if isinstance(analyst, dict):
        for k in ("buy", "hold", "sell"):
            if isinstance(analyst.get(k), (int, float)):
                d["analyst_" + k] = analyst[k]
    return d


def rechnen(eingaben, js, node="node", timeout=900, universum=None):
    """Ruft das gebaute scanner-evaluate.mjs auf. Rueckgabe {ticker: Felder|{error}} oder None bei Ausfall.
    universum: alle Exportzeilen; daraus waehlt der App-Code die Peers (selectPeers)."""
    if not eingaben:
        return {}
    if not js or not os.path.isfile(js):
        return None
    with tempfile.TemporaryDirectory() as tmp:
        ein, aus = os.path.join(tmp, "ein.json"), os.path.join(tmp, "aus.json")
        with open(ein, "w", encoding="utf-8") as fh:
            json.dump({"universe": [_sauber({k: v for k, v in r.items() if k != "_ts_input"}) for r in (universum or [])],
                       "funds": eingaben}, fh, ensure_ascii=False, allow_nan=False)
        try:
            subprocess.run([node, js, ein, aus], check=True, timeout=timeout, capture_output=True)
            with open(aus, encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, subprocess.SubprocessError, ValueError):
            return None


def risikodaten(pfad=None):
    """Gepruefte Bilanzdaten der Risikopipeline je Notierung (cf_risk_coverage.json): Bilanzpruefung und Cash-Conversion.
    Der App-Code prueft sie erneut (verifiedCashConversion); hier nur Zuordnung nach listing_symbol."""
    pfad = pfad or os.path.join(os.path.dirname(os.path.abspath(__file__)), "daten", "cf_risk_coverage.json")
    try:
        with open(pfad, encoding="utf-8") as fh:
            daten = json.load(fh)
    except (OSError, ValueError):
        return {}
    out = {}
    for row in daten.get("stocks") or []:
        b = ((row or {}).get("domains") or {}).get("balance") or {}
        if isinstance(row.get("symbol"), str) and b:
            # Bilanzpruefung fuer die Bilanz-Kategorie (financial-health.ts) und die Cash-Conversion (DCF).
            out[row["symbol"]] = {"_risk_coverage": {"balance": b}, "_cash_conversion_history": b.get("cashConversion")}
    return out


def ersatzdaten(row, ordner=None):
    """Aktienzahl aus dem Jahresabschluss je Notierung (daten/fundamentals/<listing_symbol>.json, wie die App sie
    laedt) fuer die Pruefung von Kurs x Aktienzahl (normalizeMarketCap). Nur die noetigen Felder; die Datei muss
    zur Notierung gehoeren (symbol == listing_symbol), sonst wird sie nicht verwendet. Der App-Code prueft Symbol,
    Alter und Aktienbasis erneut."""
    ordner = ordner or os.path.join(os.path.dirname(os.path.abspath(__file__)), "daten", "fundamentals")
    sym = row.get("listing_symbol") or row.get("ticker")
    if not isinstance(sym, str) or not sym:
        return {}
    try:
        with open(os.path.join(ordner, re.sub(r"[^A-Za-z0-9._-]", "_", sym) + ".json"), encoding="utf-8") as fh:
            s = json.load(fh)
    except (ValueError, OSError):
        return {}
    a = s.get("annual") if isinstance(s, dict) else None
    if not isinstance(a, dict) or s.get("symbol") != sym:
        return {}
    w = (a.get("fields") or {}).get("weighted_shares")
    return {"_supplement_symbol": sym,
            "_fundamental_supplement": {"schema": s.get("schema"), "symbol": s.get("symbol"),
                                        "annual": {"end": a.get("end"), "currency": a.get("currency"),
                                                   "source": a.get("source"), "fields": {"weighted_shares": w}},
                                        "market": {"currency": (s.get("market") or {}).get("currency")},
                                        "share_basis": s.get("share_basis")}}


def anwenden(rows, js=None, node="node", risiko=None, ordner=None):
    """Ersetzt in frisch gescannten Zeilen (mit _ts_input) die Bewertungsfelder durch die TS-Werte."""
    js = js if js is not None else os.environ.get("SCANNER_EVAL_JS")
    if risiko is None:
        risiko = risikodaten() if any(isinstance(r.get("_ts_input"), dict) for r in rows) else {}
    offen = {}
    for r in rows:
        if isinstance(r.get("_ts_input"), dict):
            eingang = r.pop("_ts_input")
            eingang.update(_sauber(risiko.get(r.get("listing_symbol")) or {}))
            eingang.update(_sauber(ersatzdaten(r, ordner)))
            offen[r["ticker"]] = eingang
    ergebnis = rechnen(offen, js, node, universum=rows) if offen else {}
    stat = {"ts": 0, "python_v1": 0, "fehler": 0, "ausfall": ergebnis is None}
    for r in rows:
        if r["ticker"] not in offen:
            continue
        neu = (ergebnis or {}).get(r["ticker"])
        if isinstance(neu, dict) and not neu.get("error") and neu.get("scanner_method") == METHODE:
            for k in FELDER:
                r[k] = neu.get(k)
            # Gesperrte Bewertung: Rohwerte und Herkunft mitschreiben, damit die Ursache ohne neuen Abruf klar wird.
            if r.get("kauf_urteil") == "Daten prüfen":
                r["valuation_check_inputs"] = offen[r["ticker"]].get("_pruef_eingang") or {}
            else:
                r.pop("valuation_check_inputs", None)
            stat["ts"] += 1
        else:
            r["scanner_method"] = ALT
            stat["fehler" if isinstance(neu, dict) else "python_v1"] += 1
    return stat
