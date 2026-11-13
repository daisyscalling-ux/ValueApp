"""Scanner-Werte aus dem App-Rechenweg (evaluateStock in TypeScript), seit 13.11.2026.

Die Pipeline holt die Daten wie bisher (providers/ROIC); gerechnet wird mit derselben Methode wie in der
Einzelanalyse (risk_precompute/src/lib, identische Kopie aus valueapp-cf). Faellt die TS-Rechnung aus,
bleiben die Python-Werte stehen und werden als scanner_method "python-v1" gekennzeichnet; die App weist
darauf hin. Siehe BEWERTUNG_RISIKODATEN.md.
"""
import json
import math
import os
import subprocess
import tempfile

METHODE = "ts-evaluate-v1"
ALT = "python-v1"
FELDER = ("scanner_method", "playbook", "lifecycle_phase", "composite", "fair_value", "upside", "entry", "quantum",
          "target_12m", "fv_confidence", "fv_reliable", "valuation_issues", "momentum", "quality", "value", "growth",
          "catalyst", "health", "cat_neutral", "value_trap", "vt_warnung", "kauf_urteil")
PRIVAT_ERLAUBT = {"_analyst_trend", "_ist_zyklisch"}


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


def eingabe(f, analyst=None):
    """Fund-Dict fuer evaluateStock: dieselben Feldnamen wie in der App; private Felder nur, wenn erlaubt."""
    d = {k: _sauber(v) for k, v in (f or {}).items() if not str(k).startswith("_") or k in PRIVAT_ERLAUBT}
    if isinstance(analyst, dict):
        for k in ("buy", "hold", "sell"):
            if isinstance(analyst.get(k), (int, float)):
                d["analyst_" + k] = analyst[k]
    return d


def rechnen(eingaben, js, node="node", timeout=900):
    """Ruft das gebaute scanner-evaluate.mjs auf. Rueckgabe {ticker: Felder|{error}} oder None bei Ausfall."""
    if not eingaben:
        return {}
    if not js or not os.path.isfile(js):
        return None
    with tempfile.TemporaryDirectory() as tmp:
        ein, aus = os.path.join(tmp, "ein.json"), os.path.join(tmp, "aus.json")
        with open(ein, "w", encoding="utf-8") as fh:
            json.dump(eingaben, fh, ensure_ascii=False, allow_nan=False)
        try:
            subprocess.run([node, js, ein, aus], check=True, timeout=timeout, capture_output=True)
            with open(aus, encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, subprocess.SubprocessError, ValueError):
            return None


def anwenden(rows, js=None, node="node"):
    """Ersetzt in frisch gescannten Zeilen (mit _ts_input) die Bewertungsfelder durch die TS-Werte."""
    js = js if js is not None else os.environ.get("SCANNER_EVAL_JS")
    offen = {r["ticker"]: r.pop("_ts_input") for r in rows if isinstance(r.get("_ts_input"), dict)}
    ergebnis = rechnen(offen, js, node) if offen else {}
    stat = {"ts": 0, "python_v1": 0, "fehler": 0, "ausfall": ergebnis is None}
    for r in rows:
        if r["ticker"] not in offen:
            continue
        neu = (ergebnis or {}).get(r["ticker"])
        if isinstance(neu, dict) and not neu.get("error") and neu.get("scanner_method") == METHODE:
            for k in FELDER:
                r[k] = neu.get(k)
            stat["ts"] += 1
        else:
            r["scanner_method"] = ALT
            stat["fehler" if isinstance(neu, dict) else "python_v1"] += 1
    return stat
