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
          "catalyst", "health", "cat_neutral", "value_trap", "vt_warnung", "kauf_urteil", "share_count_basis",
          "annual_supplement_applied", "supplement_annual_end", "supplement_retained_fields", "score_diagnostics",
          "peer_count", "composite_peer_metrics", "ev_ebitda_anchor", "cash_conversion", "cash_conversion_source", "cash_conversion_origin", "health_source", "health_parts", "health_raw", "health_profile",
          "market_cap", "market_cap_source", "eps_forward", "eps_forward_method", "eps_forward_source", "eps_forward_status", "eps_forward_check", "expectation_gap",
          "report_fx", "report_fx_status", "value_inputs", "eps_forward_no_profit", "roic_history_status", "eps_basis",
          "risk_free", "terminal_growth")
PRIVAT_ERLAUBT = {"_analyst_trend", "_cash_conversion_history", "_risk_coverage", "_pruef_eingang", "_cyclicality",
                  "_fundamental_supplement", "_supplement_symbol", "_rates"}


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
            "_quelle", "_roic_kursverhaeltnis", "_roic_felder", "_pence_normalised", "_src")


ZYKLIK_METHODE = "margin_cv_v1"


def zyklik(diagnose):
    """Datenbasierte Zyklik fuer App und Scanner (valuation.ts, dataCyclical prueft erneut und schliesst Finanzwerte
    und defensive Sektoren aus). Nur mit Margenreihe; das alte Flag _ist_zyklisch wird nicht mehr weitergegeben."""
    if not isinstance(diagnose, dict) or not isinstance(diagnose.get("margen"), list):
        return None
    return {"method": ZYKLIK_METHODE, "margins": _sauber(diagnose["margen"]), "cv": _sauber(diagnose.get("variationskoeffizient")),
            "cyclical": bool(diagnose.get("zyklisch")), "years": diagnose.get("jahre")}


# Seit 17.11.2026 (Entscheidung des Nutzers): Diese Felder nimmt die App nur von ROIC. Fehlen sie dort, fuellt
# providers.py sie still aus Yahoo (freeCashflow = Cashflow nach Zinsen, enterpriseToEbitda; ungekennzeichnet, teils
# andere Waehrung). Der Screener verwirft solche Werte; die Kennzahl bleibt wie in der App offen.
# Seit 17.11.2026 (zweiter Schritt, bundle-compare v5): auch KBV, Renditen, Margen und Current Ratio. Banken hatten im
# Screener Yahoo-Margen (Brutto 0 %, operativ 35-59 %), die App keine; die Qualitaet wich bei 7 von 50 Titeln um mehr
# als 5 Punkte ab (KeyCorp 9,5 gegen 38,3). Alle Felder liest die App aus denselben ROIC-Feldern (roic.ts bundleLight).
# net_debt_ebitda nicht: die App rechnet es selbst aus Nettoschulden und EBITDA.
NUR_ROIC = ("free_cashflow", "ev_ebitda", "pb", "roe", "roa", "gross_margin", "operating_margin", "current_ratio")


def eingabe(f, analyst=None):
    """Fund-Dict fuer evaluateStock: dieselben Feldnamen wie in der App; private Felder nur, wenn erlaubt."""
    d = {k: _sauber(v) for k, v in (f or {}).items() if not str(k).startswith("_") or k in PRIVAT_ERLAUBT}
    d["_pruef_eingang"] = {k: _sauber((f or {}).get(k)) for k in DIAGNOSE if (f or {}).get(k) is not None}
    roic_felder = set((f or {}).get("_roic_felder") or [])
    verworfen = [k for k in NUR_ROIC if d.get(k) is not None and k not in roic_felder]
    for k in verworfen:
        d[k] = None
    if verworfen:
        d["_pruef_eingang"]["nur_roic_verworfen"] = verworfen
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


def zinsen(pfad=None):
    """Rendite 10-jaehriger Staatsanleihen je Waehrung (daten/cf_rates.json, scripts/export_rates.py, seit 17.11.2026).
    Unveraendert weitergereicht; der App-Code (valuation.ts riskFree) prueft Methode, Alter und Wertebereich."""
    pfad = pfad or os.path.join(os.path.dirname(os.path.abspath(__file__)), "daten", "cf_rates.json")
    try:
        with open(pfad, encoding="utf-8") as fh:
            d = json.load(fh)
    except (OSError, ValueError):
        return None
    return _sauber(d) if isinstance(d, dict) else None


def ersatzdaten(row, ordner=None):
    """Ergaenzungsdatei je Notierung (daten/fundamentals/<listing_symbol>.json, wie die App sie laedt): Aktienzahl aus
    dem Jahresabschluss (Pruefung Kurs x Aktienzahl) und Analystenkonsens (gepruefte Prognose-EPS). Nur die noetigen
    Felder; die Datei muss zur Notierung gehoeren (symbol == listing_symbol). Ohne passende Datei wird
    _fundamental_supplement=None uebergeben: dann bleibt die Prognose-EPS im App-Rechenweg offen, statt den
    ungeprueften Anbieterwert zu nutzen. Der App-Code prueft Symbol, Alter, Basis und Konsens erneut."""
    leer = {"_fundamental_supplement": None, "_supplement_symbol": None}
    ordner = ordner or os.path.join(os.path.dirname(os.path.abspath(__file__)), "daten", "fundamentals")
    sym = row.get("listing_symbol") or row.get("ticker")
    if not isinstance(sym, str) or not sym:
        return leer
    try:
        with open(os.path.join(ordner, re.sub(r"[^A-Za-z0-9._-]", "_", sym) + ".json"), encoding="utf-8") as fh:
            s = json.load(fh)
    except (ValueError, OSError):
        return leer
    if not isinstance(s, dict) or s.get("symbol") != sym:
        return leer
    # Vollstaendige Ergaenzungsdatei wie in der Einzelanalyse (applySupplement: Jahresblock, Markt, EZB-Kurse,
    # Aktienbasis, Konsens, Cashflow-Historie, Splits); nur die Risiko-Diagnoseteile bleiben weg.
    weg = {"risk_annual", "annual_diagnostics"}
    return {"_supplement_symbol": sym,
            "_fundamental_supplement": {k: v for k, v in s.items() if k not in weg}}


# Seit 17.11.2026 (QA-Befund, zweiter Schritt): Das 52-Wochen-Band aus unbereinigten ROIC-Kursen (K52) enthielt nach
# Aktiensplits die Kurse vor dem Split (Mitsui Kinzoku Hoch 54.900 bei Kurs 1.344,5 nach 10:1 am 29.09.2026). Die
# Erkennung ueber adj_close/close (roic.kursband) griff im Lauf vom 17.11. bei keinem Titel. Die Ergaenzungsdatei derselben
# Notierung kennt die Splits (Yahoo, Datum und Verhaeltnis) und ein split-bereinigtes Band. Liegt ein Split im Fenster,
# gilt das ROIC-Band nicht: Ersatz durch das Yahoo-Band (hoechstens 7 Tage alt, Kurs passt auf 10 %), gekennzeichnet;
# sonst bleibt das Band offen.
BAND_METHODE = "supplement_split_band_v1"
# 400 statt 365 Tage (19.11.2026): Das ROIC-Band umfasst 260 Handelstage und reicht ueber ein Kalenderjahr zurueck;
# Netflix (Split 17.11.2025) fiel am 19.11.2026 aus dem 365-Tage-Fenster und behielt das Hoch 1.157,50.
SPLIT_FENSTER_TAGE = 400
WIDERSPRUCH = 1.5


def band_nach_split(row, eingang, heute=None):
    """Prueft Splits der letzten 365 Tage; setzt 52w_high/low in Zeile und Eingang neu und gibt die Kennzeichnung zurueck
    (None ohne Split im Fenster)."""
    import datetime as _dt
    heute = heute or _dt.datetime.now(_dt.timezone.utc).date()
    s = eingang.get("_fundamental_supplement") or {}
    splits = []
    for sp in s.get("splits") or []:
        try:
            d = _dt.date.fromisoformat(str(sp.get("date"))[:10])
            r = float(sp.get("ratio"))
        except (TypeError, ValueError, AttributeError):
            continue
        if 0 <= (heute - d).days <= SPLIT_FENSTER_TAGE and r > 0 and abs(r - 1) > 1e-9:
            splits.append({"date": d.isoformat(), "ratio": r})
    m = s.get("market") or {}
    if not splits:
        return _band_widerspruch(row, eingang, m, heute)
    f = m.get("fields") or {}
    lo, hi, px = f.get("52w_low"), f.get("52w_high"), f.get("price")
    grund = None
    try:
        alter = (heute - _dt.date.fromisoformat(str(m.get("quote_at"))[:10])).days
    except (TypeError, ValueError):
        alter = None
    preis = row.get("price")
    einheit = None
    # Londoner Notierungen: Pence (GBp) gegen Pfund. Nur der exakte Faktor 100 wird umgerechnet, gekennzeichnet.
    if all(isinstance(x, (int, float)) and x > 0 for x in (lo, hi, px)) and isinstance(preis, (int, float)) and preis > 0:
        for faktor in (100.0, 0.01):
            if abs(px / preis - 1) > 0.10 and abs(px * faktor / preis - 1) <= 0.10:
                lo, hi, px, einheit = lo * faktor, hi * faktor, px * faktor, faktor
                break
    if not all(isinstance(x, (int, float)) and x > 0 for x in (lo, hi, px)) or hi < lo:
        grund = "Kein bereinigtes 52-Wochen-Band in der Ergaenzungsdatei"
    elif alter is None or alter < 0 or alter > 7:
        grund = "Bereinigtes 52-Wochen-Band aelter als 7 Tage"
    elif not (isinstance(preis, (int, float)) and preis > 0 and abs(px / preis - 1) <= 0.10):
        grund = "Kurs der Ergaenzungsdatei passt nicht zum Kurs der Zeile (Einheit oder Stand)"
    if grund:
        lo = hi = None
    for z in (row, eingang):
        z["52w_low"], z["52w_high"] = lo, hi
    return {"method": BAND_METHODE, "splits": splits, "source": None if grund else "Yahoo Finance (Ergaenzungsdatei, split-bereinigt)",
            "quote_at": None if grund else m.get("quote_at"), "unit_factor": None if grund else einheit, "reason": grund}


def _band_widerspruch(row, eingang, m, heute):
    """Ohne Split: Weichen ROIC- und Yahoo-Band (gleiche Notierung, <= 7 Tage, Kurs auf 10 %) an einem Ende um mehr als
    WIDERSPRUCH ab, gilt das engere der beiden Baender, das den Kurs enthaelt (Compass: ROIC 27-2.527 durch gemischte
    Pence/Pfund; Rose: Yahoo 0,03-3,95). Enthaelt keines den Kurs, bleibt das Band offen. Sonst keine Aenderung (None)."""
    import datetime as _dt
    f = m.get("fields") or {}
    lo, hi, preis = row.get("52w_low"), row.get("52w_high"), row.get("price")
    ylo, yhi, ypx = f.get("52w_low"), f.get("52w_high"), f.get("price")
    zahlen = (lo, hi, preis, ylo, yhi, ypx)
    if not all(isinstance(x, (int, float)) and x > 0 for x in zahlen):
        return None
    try:
        alter = (heute - _dt.date.fromisoformat(str(m.get("quote_at"))[:10])).days
    except (TypeError, ValueError):
        return None
    if alter < 0 or alter > 7:
        return None
    faktor = None
    for fk in (100.0, 0.01):
        if abs(ypx / preis - 1) > 0.10 and abs(ypx * fk / preis - 1) <= 0.10:
            ylo, yhi, ypx, faktor = ylo * fk, yhi * fk, ypx * fk, fk
            break
    if abs(ypx / preis - 1) > 0.10:
        return None
    if not (hi > WIDERSPRUCH * yhi or yhi > WIDERSPRUCH * hi or lo > WIDERSPRUCH * ylo or ylo > WIDERSPRUCH * lo):
        return None
    passt = lambda a, b: a * 0.98 <= preis <= b * 1.02
    kandidaten = [(b / a, a, b, q) for a, b, q in ((lo, hi, "roic"), (ylo, yhi, "yahoo")) if b >= a and passt(a, b)]
    if not kandidaten:
        neu, quelle, grund = (None, None), None, "ROIC- und Yahoo-Band widersprechen sich, keines enthaelt den Kurs"
    else:
        _, a, b, quelle = min(kandidaten)
        neu, grund = (a, b), None
    for z in (row, eingang):
        z["52w_low"], z["52w_high"] = neu
    return {"method": BAND_METHODE, "splits": [], "conflict": True,
            "source": {"roic": "ROIC (unbereinigte Schlusskurse)", "yahoo": "Yahoo Finance (Ergaenzungsdatei)"}.get(quelle),
            "quote_at": m.get("quote_at") if quelle == "yahoo" else None, "unit_factor": faktor if quelle == "yahoo" else None,
            "reason": grund}


def _gueltig(neu):
    return isinstance(neu, dict) and not neu.get("error") and neu.get("scanner_method") == METHODE


def _uebernehmen(r, neu):
    for k in FELDER:
        r[k] = neu.get(k)
    # Berichtswaehrung umgerechnet (EZB) oder Jahresblock uebernommen: Anzeige- und Peer-Kennzahlen der Zeile aus
    # demselben Rechenweg, sonst blieben EPS, KGV, KBV, EV/EBITDA alt (Equinor KGV 209,6, Micron EPS 7,65).
    # Auch leere Werte uebernehmen: fehlt dem Jahresblock z. B. das EPS (Costco), darf die Zeile nicht das alte
    # ROIC-EPS des Vorjahres zeigen, mit dem gar nicht gerechnet wurde (offen statt falsch).
    for k, v in (neu.get("report_converted") or {}).items():
        r[k] = v


def anwenden(rows, js=None, node="node", risiko=None, ordner=None, zins=None):
    """Ersetzt in frisch gescannten Zeilen (mit _ts_input) die Bewertungsfelder durch die TS-Werte."""
    js = js if js is not None else os.environ.get("SCANNER_EVAL_JS")
    if risiko is None:
        risiko = risikodaten() if any(isinstance(r.get("_ts_input"), dict) for r in rows) else {}
    zinsdaten = zins if zins is not None else (zinsen() if any(isinstance(r.get("_ts_input"), dict) for r in rows) else None)
    offen = {}
    for r in rows:
        if isinstance(r.get("_ts_input"), dict):
            eingang = r.pop("_ts_input")
            eingang.update(_sauber(risiko.get(r.get("listing_symbol")) or {}))
            eingang.update(_sauber(ersatzdaten(r, ordner)))
            r["52w_band"] = band_nach_split(r, eingang)
            if zinsdaten:
                eingang["_rates"] = zinsdaten
            offen[r["ticker"]] = eingang
    # Zwei Durchgaenge (seit 17.11.2026): Die Peers waehlt der App-Code aus den Zeilen dieses Laufs. Frisch gescannte
    # Zeilen tragen die App-Felder (value_inputs, gepruefter Konsens, umgerechnete Kennzahlen) aber erst nach der
    # Bewertung; im ersten Durchgang fehlen sie allen Peers (Lauf 17.11.: 1.341 von 1.341 frisch), Forward-KGV, PEG und
    # FCF-Rendite liefen deshalb nur auf der festen Skala, waehrend die App gegen Peers des fertigen Universums rechnet.
    # Der zweite Durchgang rechnet mit Peer-Zeilen in dem Stand, den die App spaeter liest.
    ergebnis = rechnen(offen, js, node, universum=rows) if offen else {}
    stat = {"ts": 0, "python_v1": 0, "fehler": 0, "ausfall": ergebnis is None, "durchgaenge": 1 if offen else 0}
    if offen and ergebnis is not None:
        vorlaeufig = []
        for r in rows:
            k = dict(r)
            neu = ergebnis.get(r["ticker"]) if r["ticker"] in offen else None
            if _gueltig(neu):
                _uebernehmen(k, neu)
            vorlaeufig.append(k)
        zweit = rechnen(offen, js, node, universum=vorlaeufig)
        if zweit is not None:
            ergebnis, stat["durchgaenge"] = zweit, 2
    for r in rows:
        if r["ticker"] not in offen:
            continue
        neu = (ergebnis or {}).get(r["ticker"])
        if _gueltig(neu):
            _uebernehmen(r, neu)
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
