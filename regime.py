"""
regime.py — Marktumfeld, Sektor-Saisonalitaet und Reaktion auf Quartalszahlen.

Drei Fragen, die sich mit freien Daten EHRLICH beantworten lassen:

  1) WANN laufen welche Sektoren gut?      -> sector_seasonality()
     Monatsstatistik aus Sektor-ETFs ueber viele Jahre.

  2) WAS fuehrt gerade?                    -> leadership() / market_state()
     Relative Staerke der Sektoren + Zustand des Gesamtmarkts. So zeigt
     sich ein Boom (z.B. KI) als anhaltende Tech-Outperformance, ohne dass
     man ihn benennen muss.

  3) WIE reagiert eine Aktie auf Zahlen?   -> earnings_reactions()
     Historie aus Ueberraschung (Ist gegen Erwartung) und Kursreaktion.
     Der interessante Fall ist "geschlagen und trotzdem gefallen" - dann
     war die Erwartung im Kurs schon zu hoch.

GRENZEN - bitte ernst nehmen:
  * yfinance liefert maximal 8 Quartale je Titel. Acht Datenpunkte sind
    KEINE Statistik. Das Reaktionsprofil ist ein Hinweis, kein Beweis.
  * Saisonalitaet ueber 20 Jahre heisst 20 Werte je Monat. Auch das ist
    duenn, und Muster wie "Sell in May" sind seit Jahrzehnten bekannt -
    was bekannt ist, wird eingepreist.
  * Alle Aussagen sind BESCHREIBEND (was war), nicht vorhersagend
    (was kommt). Ob sie tragen, entscheidet die Trefferbilanz.
"""
from __future__ import annotations

try:
    import providers
except Exception:                                  # pragma: no cover
    providers = None

# Sektor-ETFs als Stellvertreter. Bewusst die grossen, liquiden SPDRs -
# lange Historie, keine Exotik.
SECTOR_ETFS = {
    "Technology":             ("XLK", "Technologie"),
    "Energy":                 ("XLE", "Energie"),
    "Financial Services":     ("XLF", "Finanzdienstleistungen"),
    "Healthcare":             ("XLV", "Gesundheit"),
    "Consumer Cyclical":      ("XLY", "Konsum zyklisch"),
    "Consumer Defensive":     ("XLP", "Konsum defensiv"),
    "Industrials":            ("XLI", "Industrie"),
    "Basic Materials":        ("XLB", "Rohstoffe"),
    "Utilities":              ("XLU", "Versorger"),
    "Real Estate":            ("XLRE", "Immobilien"),
    "Communication Services": ("XLC", "Kommunikation"),
}
BENCH = "SPY"
MONATE = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun",
          "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"]

_CACHE = {}


try:
    import roic as _roic
except Exception:                                  # pragma: no cover
    _roic = None


def _jahre(period):
    try:
        return int(str(period).lower().replace("y", "").strip())
    except Exception:
        return 20


def _roic_monatsreihe(ticker, jahre):
    """Monatsschlusskurse aus roic. Rueckgabe [(datum, kurs)] oder []."""
    if _roic is None or not _roic.enabled():
        return []
    try:
        if not _roic.covers(ticker):
            return []
        return _roic.monatsende(ticker, jahre=jahre)
    except Exception:
        return []


def _hist(ticker, period="20y", interval="1mo"):
    if providers is None:
        return None
    key = (ticker, period, interval)
    if key in _CACHE:
        return _CACHE[key]
    try:
        h = providers.get_price_history(ticker, period=period, interval=interval)
    except Exception:
        h = None
    _CACHE[key] = h
    return h


def _reihe(ticker, period="20y", interval="1mo"):
    """Kursreihe als [(datum, kurs)] - roic bevorzugt, sonst yfinance.

    roic liefert adjustierte Schlusskurse in einem Abruf und unterliegt
    keiner Drosselung durch Gratislimits. Fuer ETFs ist die Abdeckung
    aber nicht garantiert - deshalb der Rueckfall."""
    key = ("_reihe", ticker, period, interval)
    if key in _CACHE:
        return _CACHE[key]
    daten = []
    if interval == "1mo":
        daten = _roic_monatsreihe(ticker, _jahre(period))
    if len(daten) < 24:
        daten = _closes(_hist(ticker, period, interval))
    _CACHE[key] = daten
    return daten


def _monat(d):
    """Monatsnummer aus einem Datum - egal ob Zeitstempel oder Text.

    roic liefert '2026-07-31' als Zeichenkette, yfinance einen Zeitstempel
    mit .month. Ohne diese Vereinheitlichung waere die Saisonalitaet
    STILL leergelaufen: Der Zugriff .month scheitert bei Text, der Fehler
    wurde abgefangen und jeder Monat uebersprungen."""
    try:
        return int(d.month)
    except Exception:
        pass
    try:
        return int(str(d)[5:7])
    except Exception:
        return None


def _closes(h):
    """Schlusskurse als Liste von (datum, kurs) - robust gegen Formatvarianten."""
    if h is None or getattr(h, "empty", True):
        return []
    try:
        col = "Close" if "Close" in h.columns else h.columns[0]
        out = []
        for idx, val in zip(h.index, h[col].tolist()):
            if val is None or val != val:               # NaN
                continue
            out.append((idx, float(val)))
        return out
    except Exception:
        return []


# ---------------------------------------------------------------- Saisonalitaet
def sector_seasonality(sector, years=20):
    """Monatsstatistik eines Sektors.

    Rueckgabe je Monat: Durchschnitt, Median, Trefferquote (Anteil positiver
    Monate) und n. Das n gehoert IMMER mit angezeigt - bei n=20 ist ein
    Unterschied von zwei Prozentpunkten Rauschen."""
    ent = SECTOR_ETFS.get(sector)
    if not ent:
        return None
    etf, label = ent
    rows = _reihe(etf, period=f"{years}y", interval="1mo")
    if len(rows) < 24:
        return None
    monatlich = {i: [] for i in range(1, 13)}
    for i in range(1, len(rows)):
        d_prev, p_prev = rows[i - 1]
        d_cur, p_cur = rows[i]
        if not p_prev:
            continue
        m = _monat(d_cur)
        if not m:
            continue
        monatlich[m].append((p_cur / p_prev - 1) * 100)
    out = []
    for m in range(1, 13):
        v = monatlich[m]
        if not v:
            continue
        v_sorted = sorted(v)
        n = len(v)
        out.append({
            "monat": MONATE[m - 1],
            "n": n,
            "avg": round(sum(v) / n, 2),
            "median": round(v_sorted[n // 2], 2),
            "trefferquote": round(sum(1 for x in v if x > 0) / n * 100),
        })
    return {"sektor": label, "etf": etf, "monate": out}


def best_months(sector, years=20, top=3):
    """Die statistisch staerksten und schwaechsten Monate eines Sektors."""
    s = sector_seasonality(sector, years)
    if not s or not s["monate"]:
        return None
    srt = sorted(s["monate"], key=lambda r: -r["avg"])
    return {"sektor": s["sektor"], "etf": s["etf"],
            "stark": srt[:top], "schwach": srt[-top:][::-1],
            "n_min": min(r["n"] for r in s["monate"])}


# ------------------------------------------------------------------- Fuehrung
def _ret_over(rows, monate):
    if len(rows) <= monate:
        return None
    p_alt, p_neu = rows[-1 - monate][1], rows[-1][1]
    if not p_alt:
        return None
    return (p_neu / p_alt - 1) * 100


def leadership(years=3):
    """Welche Sektoren fuehren aktuell - gegen den Gesamtmarkt gemessen.

    Ein Boom braucht keinen Namen: Wenn Technologie ueber 3, 6 und 12
    Monate deutlich vor dem Index liegt, IST das der KI-Boom, ohne dass
    das Modell wissen muss, wie er heisst. Das ist robuster als eine
    Stichwortliste, die man staendig pflegen muesste."""
    bench = _reihe(BENCH, period=f"{years}y", interval="1mo")
    if len(bench) < 13:
        return None
    b3, b6, b12 = (_ret_over(bench, 3), _ret_over(bench, 6), _ret_over(bench, 12))
    out = []
    for sector, (etf, label) in SECTOR_ETFS.items():
        rows = _reihe(etf, period=f"{years}y", interval="1mo")
        if len(rows) < 13:
            continue
        r3, r6, r12 = (_ret_over(rows, 3), _ret_over(rows, 6), _ret_over(rows, 12))
        if r12 is None or b12 is None:
            continue
        rel = {
            "sektor": label, "etf": etf, "key": sector,
            "rel_3m": round(r3 - b3, 1) if (r3 is not None and b3 is not None) else None,
            "rel_6m": round(r6 - b6, 1) if (r6 is not None and b6 is not None) else None,
            "rel_12m": round(r12 - b12, 1),
        }
        vals = [v for v in (rel["rel_3m"], rel["rel_6m"], rel["rel_12m"])
                if v is not None]
        rel["schnitt"] = round(sum(vals) / len(vals), 1) if vals else None
        # "anhaltend" = ueber alle drei Zeitraeume vorn. Das trennt einen
        # echten Trend von einem Strohfeuer der letzten Wochen.
        rel["anhaltend"] = all(v is not None and v > 0 for v in
                               (rel["rel_3m"], rel["rel_6m"], rel["rel_12m"]))
        out.append(rel)
    out.sort(key=lambda r: -(r["schnitt"] or -999))
    return out


# ---------------------------------------------------------------------------
# KURATIERTE THEMEN-KOERBE
# ---------------------------------------------------------------------------
# WICHTIG: Diese Liste ist von Hand gepflegt, NICHT automatisch entdeckt. Das
# System misst nur das Momentum der hier definierten Themen - es findet keine
# NEUEN Trends von selbst. Die breite Sektor-Auswertung (leadership) bleibt der
# datengetriebene Teil; diese Koerbe sind die gezielte Ergaenzung fuer
# Sub-Themen, die quer durch mehrere Sektoren laufen (z.B. Datacenter-Kuehlung:
# Industrie + Versorger + Spezialtitel) und die kein sauberer Sektor-ETF
# abbildet. Titel gelegentlich pruefen/aktualisieren.
THEMEN_KOERBE = {
    "datacenter_kuehlung": {
        "label": "Datacenter-K\u00fchlung & Power",
        "beschreibung": "Strom-, K\u00fchl- und Infrastruktur f\u00fcr KI-Rechenzentren",
        "ticker": ["ETN", "VRT", "JCI", "PWR", "NVT"],
    },
    "ai_infrastruktur": {
        "label": "KI-Infrastruktur (Chips & Netz)",
        "beschreibung": "Halbleiter und Netzwerk-Hardware f\u00fcr KI-Training",
        "ticker": ["NVDA", "AVGO", "AMD", "ANET", "TSM"],
    },
    "elektrifizierung": {
        "label": "Elektrifizierung & Netz",
        "beschreibung": "Stromnetze, Kabel, Transformatoren, Netzausbau",
        "ticker": ["ETN", "PWR", "GEV", "PRY.MI", "NEXANS.PA"],
    },
    "verteidigung": {
        "label": "Verteidigung & R\u00fcstung",
        "beschreibung": "Steigende Wehretats in USA und Europa",
        "ticker": ["LMT", "RTX", "NOC", "RHM.DE", "BA.L"],
    },
    "onshoring": {
        "label": "Onshoring & Automatisierung",
        "beschreibung": "R\u00fcckverlagerung der Produktion, Fabrikautomation",
        "ticker": ["ROK", "EMR", "ABBN.SW", "FANUY", "PH"],
    },
    "energie_infra": {
        "label": "Energie-Infrastruktur",
        "beschreibung": "Erdgas, Pipelines, LNG, Kraftwerksbau",
        "ticker": ["WMB", "KMI", "GEV", "VST", "CEG"],
    },
}


def _korb_rendite(ticker_liste, monate, years=3):
    """Mittlere Rendite eines Titelkorbs ueber 'monate' Monate. Ein Korb ist
    gleichgewichtet - jeder Titel zaehlt gleich. Titel ohne genug Historie
    werden ausgelassen (mit Fallzahl, damit ein duenner Korb sichtbar ist)."""
    rets, n_ok = [], 0
    for t in ticker_liste:
        rows = _reihe(t, period=f"{years}y", interval="1mo")
        if len(rows) < monate + 1:
            continue
        r = _ret_over(rows, monate)
        if r is not None:
            rets.append(r)
            n_ok += 1
    if not rets:
        return None, 0
    return sum(rets) / len(rets), n_ok


def themen_momentum(years=3):
    """Momentum der kuratierten Themen-Koerbe gegen den Gesamtmarkt.

    Gleiche Methode wie leadership(): relative Staerke ueber 3/6/12 Monate,
    'anhaltend' wenn ueber alle drei Zeitraeume vorn. Der Unterschied ist nur,
    dass ein Korb aus mehreren Aktien gemittelt wird statt eines Sektor-ETF.

    Jeder Eintrag nennt seine Fallzahl (wie viele Titel echte Daten hatten) -
    ein Korb, bei dem nur 2 von 5 Titeln Daten liefern, ist mit Vorsicht zu
    lesen. Das Ergebnis ist beschreibend (was war), keine Prognose."""
    bench = _reihe(BENCH, period=f"{years}y", interval="1mo")
    if len(bench) < 13:
        return None
    b3, b6, b12 = (_ret_over(bench, 3), _ret_over(bench, 6), _ret_over(bench, 12))
    out = []
    for key, korb in THEMEN_KOERBE.items():
        r3, n3 = _korb_rendite(korb["ticker"], 3, years)
        r6, _ = _korb_rendite(korb["ticker"], 6, years)
        r12, n12 = _korb_rendite(korb["ticker"], 12, years)
        if r12 is None or b12 is None:
            continue
        eintrag = {
            "key": key,
            "label": korb["label"],
            "beschreibung": korb["beschreibung"],
            "n_titel": n12,
            "n_gesamt": len(korb["ticker"]),
            "ticker": korb["ticker"],
            "rel_3m": round(r3 - b3, 1) if (r3 is not None and b3 is not None) else None,
            "rel_6m": round(r6 - b6, 1) if (r6 is not None and b6 is not None) else None,
            "rel_12m": round(r12 - b12, 1),
        }
        vals = [v for v in (eintrag["rel_3m"], eintrag["rel_6m"], eintrag["rel_12m"])
                if v is not None]
        eintrag["schnitt"] = round(sum(vals) / len(vals), 1) if vals else None
        eintrag["anhaltend"] = all(v is not None and v > 0 for v in
                                   (eintrag["rel_3m"], eintrag["rel_6m"],
                                    eintrag["rel_12m"]))
        # Beschleunigt sich der Trend? (3M-Staerke > 12M-Staerke = frisch,
        # 3M < 12M = flaut ab). Hilft zu sehen, ob ein Thema gerade anzieht.
        if eintrag["rel_3m"] is not None and eintrag["rel_12m"] is not None:
            eintrag["beschleunigt"] = eintrag["rel_3m"] > eintrag["rel_12m"]
        else:
            eintrag["beschleunigt"] = None
        out.append(eintrag)
    out.sort(key=lambda r: -(r["schnitt"] or -999))
    return out


def market_state(years=3):
    """Zustand des Gesamtmarkts: Abstand zum Hoch der letzten 12 Monate."""
    rows = _reihe(BENCH, period=f"{years}y", interval="1mo")
    if len(rows) < 13:
        return None
    letzte12 = [p for _d, p in rows[-13:]]
    hoch, akt = max(letzte12), rows[-1][1]
    dd = (akt / hoch - 1) * 100 if hoch else 0.0
    if dd <= -20:
        lage, hinweis = "Baisse", "defensive Sektoren liefen historisch besser"
    elif dd <= -10:
        lage, hinweis = "Korrektur", "erhöhte Schwankung, Trends brechen häufiger"
    elif dd <= -5:
        lage, hinweis = "Rücksetzer", "normale Marktbewegung"
    else:
        lage, hinweis = "Aufwärts", "Trendfolge lief historisch besser"
    return {"lage": lage, "drawdown": round(dd, 1), "hinweis": hinweis}


def bewertungs_kontext(fund, fair_value=None):
    """MARKTKONTEXT-EBENE 2+3: Ordnet die Bewertung einer EINZELNEN Aktie in
    ihre eigene Historie ein - der entscheidende Punkt, damit '30 % ueber Fair
    Value' richtig gelesen wird.

    Zwei Einordnungen:
      A) Fair-Value-Abstand: Kurs vs. uebergebener Fair Value (die Marktmeinung
         relativ zu den Fundamentaldaten). NICHT im Fair Value verrechnet -
         reine Gegenueberstellung.
      B) Historische Bewertung: Wo steht das aktuelle KGV in der eigenen
         Spanne der letzten Jahre? (Perzentil-Naeherung ueber hist_pe_*.)
         So wird '+30 %' relativiert: liegt die Aktie IMMER hoch, ist es
         normal; liegt sie ungewoehnlich hoch, ist es ein echtes Signal.

    Rueckgabe: {fv_abstand, fv_text, pe_perzentil, pe_lage, pe_text, gesamt}
    Ohne Vermischung mit dem Fair Value.
    """
    price = fund.get("price")
    out = {"fv_abstand": None, "fv_text": "", "pe_perzentil": None,
           "pe_lage": None, "pe_text": "", "gesamt": ""}

    # --- A) Fair-Value-Abstand (Markt vs. Fundamentaldaten) ---
    if fair_value and price:
        ab = (price / fair_value - 1) * 100
        out["fv_abstand"] = round(ab, 1)
        if ab <= -20:
            out["fv_text"] = (f"Kurs {ab:.0f} % UNTER Fair Value - Markt "
                              f"deutlich pessimistischer als die Fundamentaldaten")
        elif ab <= -5:
            out["fv_text"] = f"Kurs {ab:.0f} % unter Fair Value - leicht guenstig"
        elif ab < 5:
            out["fv_text"] = "Kurs nahe Fair Value - fair bewertet"
        elif ab < 20:
            out["fv_text"] = f"Kurs {ab:+.0f} % ueber Fair Value - leicht teuer"
        else:
            out["fv_text"] = (f"Kurs {ab:+.0f} % ueber Fair Value - Markt "
                              f"deutlich optimistischer als die Fundamentaldaten")

    # --- B) Historische Bewertung (KGV-Perzentil in eigener Spanne) ---
    pe_akt = fund.get("pe_ttm") or fund.get("trailing_pe")
    werte = fund.get("hist_pe_values")
    lo, hi = fund.get("hist_pe_tief"), fund.get("hist_pe_hoch")
    if pe_akt and pe_akt > 0:
        perzentil = None
        if werte and len(werte) >= 5:
            unter = sum(1 for w in werte if w <= pe_akt)
            perzentil = round(unter / len(werte) * 100)
        elif lo and hi and hi > lo:
            perzentil = round(max(0, min(100, (pe_akt - lo) / (hi - lo) * 100)))
        if perzentil is not None:
            out["pe_perzentil"] = perzentil
            if perzentil >= 80:
                out["pe_lage"] = "teuer"
                out["pe_text"] = (f"KGV im {perzentil}. Perzentil der eigenen "
                                  f"Historie - teurer als sonst fast immer")
            elif perzentil >= 60:
                out["pe_lage"] = "leicht teuer"
                out["pe_text"] = (f"KGV im {perzentil}. Perzentil - etwas ueber "
                                  f"dem eigenen Schnitt")
            elif perzentil >= 40:
                out["pe_lage"] = "normal"
                out["pe_text"] = (f"KGV im {perzentil}. Perzentil - im eigenen "
                                  f"Normbereich")
            elif perzentil >= 20:
                out["pe_lage"] = "leicht guenstig"
                out["pe_text"] = (f"KGV im {perzentil}. Perzentil - unter dem "
                                  f"eigenen Schnitt")
            else:
                out["pe_lage"] = "guenstig"
                out["pe_text"] = (f"KGV im {perzentil}. Perzentil - guenstiger "
                                  f"als sonst fast immer")

    # --- Gesamteinordnung (verbindet A und B in Worten, NICHT als Zahl) ---
    teile = []
    if out["fv_text"]:
        teile.append(out["fv_text"])
    if out["pe_text"]:
        teile.append(out["pe_text"])
    if teile:
        if (out.get("fv_abstand") or 0) >= 20 and (out.get("pe_perzentil") or 0) >= 80:
            out["gesamt"] = ("Teuer auf beiden Ebenen: ueber Fair Value UND am "
                             "oberen Rand der eigenen Bewertungshistorie.")
        elif (out.get("fv_abstand") or 0) <= -15 and (out.get("pe_perzentil") or 100) <= 25:
            out["gesamt"] = ("Guenstig auf beiden Ebenen: unter Fair Value UND "
                             "am unteren Rand der eigenen Historie.")
        else:
            out["gesamt"] = " \u00b7 ".join(teile)
    return out


def markt_regime():
    """MARKTKONTEXT-EBENE 1: Zustand des Gesamtmarkts aus HARTEN, messbaren
    Indikatoren - keine Geopolitik-Raterei, sondern deren messbare Wirkung.

    Kombiniert:
      - Trend: steht der breite Markt (SPY) ueber/unter seinem 200-Tage-Schnitt?
      - Angst: wo steht der VIX relativ zu seinem ueblichen Niveau (~19)?
      - Drawdown: Abstand zum 12-Monats-Hoch (aus market_state).

    Rueckgabe: {ampel, punkte, trend, vix, vix_level, drawdown, faktoren, text}
    ampel: 'gruen' | 'gelb' | 'rot' - fuer die schnelle Einordnung.
    Bewusst KEINE Vermischung mit dem Fair Value - reine Umfeld-Info.
    """
    faktoren = []
    punkte = 0          # >0 = stuetzend, <0 = riskant

    # --- Trend: SPY vs. eigener SMA200 (Tagesbasis) ---
    trend = None
    try:
        tag = _reihe(BENCH, period="2y", interval="1d")
        if tag and len(tag) >= 200:
            closes = [p for _d, p in tag]
            sma200 = sum(closes[-200:]) / 200
            akt = closes[-1]
            abstand = (akt / sma200 - 1) * 100 if sma200 else 0.0
            if akt >= sma200:
                trend = {"lage": "ueber SMA200", "abstand": round(abstand, 1)}
                punkte += 1
                faktoren.append(f"Markt ueber 200-Tage-Schnitt "
                                f"({abstand:+.1f} %) - Aufwaertsregime")
            else:
                trend = {"lage": "unter SMA200", "abstand": round(abstand, 1)}
                punkte -= 1
                faktoren.append(f"Markt UNTER 200-Tage-Schnitt "
                                f"({abstand:+.1f} %) - fragiles Regime")
    except Exception:
        pass

    # --- Angst: VIX-Level ---
    vix = None
    vix_level = None
    try:
        vrows = _reihe("^VIX", period="6mo", interval="1d")
        if vrows:
            vix = round(vrows[-1][1], 1)
            if vix < 17:
                vix_level = "niedrig"
                punkte += 1
                faktoren.append(f"VIX {vix} - niedrige Angst, ruhiger Markt")
            elif vix < 22:
                vix_level = "normal"
                faktoren.append(f"VIX {vix} - normales Schwankungsniveau")
            elif vix < 30:
                vix_level = "erhoeht"
                punkte -= 1
                faktoren.append(f"VIX {vix} - erhoehte Nervositaet")
            else:
                vix_level = "hoch"
                punkte -= 2
                faktoren.append(f"VIX {vix} - hohe Angst/Stress am Markt")
    except Exception:
        pass

    # --- Drawdown vom 12-Monats-Hoch (bestehende Logik) ---
    ms = market_state()
    drawdown = None
    if ms:
        drawdown = ms["drawdown"]
        if drawdown <= -20:
            punkte -= 2
        elif drawdown <= -10:
            punkte -= 1
        elif drawdown >= -3:
            # Markt nahe am 12-Monats-Hoch = Staerke, nicht neutral. Ohne das
            # landete selbst ein Markt direkt unter seinem Hoch auf "gemischt".
            punkte += 1
        faktoren.append(f"{ms['drawdown']:+.1f} % vom 12-Monats-Hoch ({ms['lage']})")

    # --- Ampel aus der Summe ---
    if punkte >= 2:
        ampel, text = "gruen", "stuetzendes Marktumfeld"
    elif punkte <= -2:
        ampel, text = "rot", "riskantes Marktumfeld - erhoehte Vorsicht"
    else:
        ampel, text = "gelb", "gemischtes Marktumfeld"

    return {"ampel": ampel, "punkte": punkte, "trend": trend,
            "vix": vix, "vix_level": vix_level, "drawdown": drawdown,
            "faktoren": faktoren, "text": text}


# -------------------------------------------------- Reaktion auf Quartalszahlen
def earnings_reactions(ticker, max_quartale=8):
    """Wie hat die Aktie auf vergangene Quartalszahlen reagiert?

    Je Termin: Ueberraschung in Prozent und die Kursreaktion danach.
    Vier Faelle, wobei die beiden mittleren die aufschlussreichen sind:

      geschlagen + gestiegen  -> Erwartung war zu niedrig (normal)
      geschlagen + GEFALLEN   -> Erwartung war im Kurs schon zu hoch,
                                 oder der Ausblick enttaeuschte
      verfehlt + GESTIEGEN    -> Pessimismus war uebertrieben
      verfehlt + gefallen     -> normal

    ACHTUNG: maximal 8 Quartale. Das reicht fuer ein Stimmungsbild,
    nicht fuer eine belastbare Aussage."""
    if providers is None:
        return None
    try:
        import yfinance as yf
    except Exception:
        return None
    try:
        df = yf.Ticker(ticker).get_earnings_dates(limit=max_quartale * 2)
    except Exception:
        return None
    if df is None or getattr(df, "empty", True):
        return None
    if "Reported EPS" not in df.columns:
        return None

    hist = _closes(_hist(ticker, period="5y", interval="1d"))
    if not hist:
        return None

    def _reaktion(termin):
        """Kursaenderung vom Tag vor bis zum Tag nach dem Termin."""
        vor = naeh = None
        for d, p in hist:
            try:
                if d.date() < termin.date():
                    vor = p
                elif naeh is None and d.date() >= termin.date():
                    naeh = p
                    break
            except Exception:
                continue
        if vor and naeh:
            return (naeh / vor - 1) * 100
        return None

    out = []
    try:
        zeilen = list(df.iterrows())
    except Exception:
        return None
    for termin, r in zeilen:
        try:
            ist = r.get("Reported EPS")
            soll = r.get("EPS Estimate")
            if ist is None or ist != ist or soll is None or soll != soll:
                continue
            ueb = r.get("Surprise(%)")
            if ueb is None or ueb != ueb:
                ueb = ((ist - soll) / abs(soll) * 100) if soll else None
            reak = _reaktion(termin)
            if reak is None:
                continue
            beat = (ist > soll)
            out.append({
                "datum": str(termin)[:10],
                "erwartet": round(float(soll), 3),
                "gemeldet": round(float(ist), 3),
                "ueberraschung_pct": round(float(ueb), 1) if ueb is not None else None,
                "reaktion_pct": round(reak, 1),
                "beat": beat,
                "fall": ("geschlagen + gestiegen" if beat and reak > 0 else
                         "geschlagen + GEFALLEN" if beat else
                         "verfehlt + GESTIEGEN" if reak > 0 else
                         "verfehlt + gefallen"),
            })
        except Exception:
            continue
    return out[:max_quartale] or None


def reaction_profile(ticker):
    """Verdichtet die Reaktionshistorie zu einem Profil.

    ZWEI getrennte Fragen, die oft verwechselt werden:

      1) Liegen die ANALYSTEN falsch?  -> Beat-Quote
         Wie oft uebertrifft das Unternehmen die Schaetzung? Eine hohe
         Quote heisst: die Erwartung ist systematisch zu niedrig.

      2) BELOHNT der Markt das?        -> Belohnungsquote
         Steigt der Kurs nach guten Zahlen? Eine niedrige Quote heisst:
         der Markt rechnet mit dem Beat, er steckt schon im Kurs.

    Erst BEIDE zusammen ergeben eine verwertbare Aussage. Nur wenn die
    Analysten zu tief liegen UND der Markt darauf reagiert, ist die
    Fehleinschaetzung ueberhaupt nutzbar."""
    rows = earnings_reactions(ticker)
    if not rows:
        return None
    beats = [r for r in rows if r["beat"]]
    misses = [r for r in rows if not r["beat"]]
    beat_pos = [r for r in beats if r["reaktion_pct"] > 0]
    miss_pos = [r for r in misses if r["reaktion_pct"] > 0]
    n = len(rows)
    beat_quote = round(len(beats) / n * 100)
    belohnt = round(len(beat_pos) / len(beats) * 100) if beats else None

    prof = {
        "n": n,
        "n_beats": len(beats),
        "beat_quote": beat_quote,               # liegen die Analysten zu tief?
        "beat_belohnt_pct": belohnt,            # reagiert der Markt darauf?
        "miss_verziehen_pct": (round(len(miss_pos) / len(misses) * 100)
                               if misses else None),
        "avg_reaktion": round(sum(r["reaktion_pct"] for r in rows) / n, 1),
        "avg_reaktion_beat": (round(sum(r["reaktion_pct"] for r in beats)
                                    / len(beats), 1) if beats else None),
        "avg_ueberraschung": (round(sum(r["ueberraschung_pct"] for r in rows
                                        if r.get("ueberraschung_pct") is not None)
                                    / max(1, sum(1 for r in rows
                                                 if r.get("ueberraschung_pct")
                                                 is not None)), 1)),
        "faelle": {
            "geschlagen + gestiegen": len(beat_pos),
            "geschlagen + GEFALLEN": len(beats) - len(beat_pos),
            "verfehlt + GESTIEGEN": len(miss_pos),
            "verfehlt + gefallen": len(misses) - len(miss_pos),
        },
        "zeilen": rows,
    }

    # --- Zusammenfuehrung: sind die Analysten falsch UND laesst sich das nutzen?
    if n < 4:
        prof["analysten"] = "zu wenige Termine"
        prof["markt"] = "zu wenige Termine"
        prof["urteil"] = "zu wenige Termine für eine Aussage"
        return prof

    if beat_quote >= 75:
        prof["analysten"] = "liegen systematisch zu tief"
    elif beat_quote <= 40:
        prof["analysten"] = "liegen eher zu hoch"
    else:
        prof["analysten"] = "treffen es ungefähr"

    if belohnt is None:
        prof["markt"] = "keine Beats im Zeitraum"
    elif belohnt >= 70:
        prof["markt"] = "belohnt gute Zahlen"
    elif belohnt <= 40:
        prof["markt"] = "belohnt gute Zahlen NICHT"
    else:
        prof["markt"] = "reagiert uneinheitlich"

    if beat_quote >= 75 and belohnt is not None and belohnt >= 70:
        prof["urteil"] = ("Analysten unterschätzen das Unternehmen wiederholt "
                          "UND der Markt reagiert darauf – das Muster wäre "
                          "nutzbar, wenn es anhält")
    elif beat_quote >= 75 and belohnt is not None and belohnt <= 40:
        prof["urteil"] = ("Beats sind hier die Regel und deshalb eingepreist – "
                          "gute Zahlen allein bewegen den Kurs nicht mehr")
    elif beat_quote <= 40 and prof["miss_verziehen_pct"] is not None \
            and prof["miss_verziehen_pct"] >= 60:
        prof["urteil"] = ("verfehlt oft, wird aber verziehen – der Kurs hängt "
                          "an anderen Faktoren als den Quartalszahlen")
    else:
        prof["urteil"] = "kein klares Muster"
    return prof


def anomalien(ticker):
    """Termine, an denen der Kurs GEGEN die Zahlen lief.

    Das sind die lehrreichen Faelle: geschlagen und trotzdem gefallen
    (Erwartung war zu hoch) oder verfehlt und trotzdem gestiegen
    (Pessimismus war uebertrieben)."""
    rows = earnings_reactions(ticker)
    if not rows:
        return []
    return [r for r in rows
            if (r["beat"] and r["reaktion_pct"] < -2)
            or (not r["beat"] and r["reaktion_pct"] > 2)]


# ============================================================================
# TERMINKALENDER — wer meldet demnaechst, und was ist zu erwarten?
# ============================================================================
def next_earnings(ticker, max_wochen=4):
    """Naechster Quartalstermin innerhalb des Zeitfensters.

    yfinance liefert kuenftige Termine als Zeilen OHNE gemeldeten Gewinn.
    Rueckgabe: {datum, tage, eps_estimate} oder None."""
    try:
        import yfinance as yf
        import datetime as _dt
    except Exception:
        return None
    try:
        df = yf.Ticker(ticker).get_earnings_dates(limit=16)
    except Exception:
        return None
    if df is None or getattr(df, "empty", True):
        return None
    if "Reported EPS" not in df.columns:
        return None
    try:
        jetzt = _dt.datetime.now(_dt.timezone.utc)
    except Exception:
        return None
    kandidaten = []
    try:
        for termin, r in df.iterrows():
            ist = r.get("Reported EPS")
            if ist is not None and ist == ist:      # bereits gemeldet
                continue
            try:
                t = termin.to_pydatetime()
                if t.tzinfo is None:
                    t = t.replace(tzinfo=_dt.timezone.utc)
            except Exception:
                continue
            tage = (t - jetzt).days
            if 0 <= tage <= max_wochen * 7:
                est = r.get("EPS Estimate")
                kandidaten.append({
                    "datum": str(termin)[:10],
                    "tage": tage,
                    "eps_estimate": (round(float(est), 3)
                                     if est is not None and est == est else None),
                })
    except Exception:
        return None
    if not kandidaten:
        return None
    kandidaten.sort(key=lambda r: r["tage"])
    return kandidaten[0]


def _erwartung_spannung(f, eps_rev, profil):
    """Steht die Analystenschaetzung im Widerspruch zu beobachtbaren Trends?

    WICHTIG: Das prueft NICHT, ob eine Schaetzung "richtig" ist - das kann
    niemand vorab wissen. Es sammelt nur Spannungen zwischen der Erwartung
    und dem, was die Zahlen zeigen. Jede Spannung ist eine FRAGE, keine
    Antwort."""
    pro, contra = [], []

    # 1) Historie: wird die Schaetzung gewohnheitsmaessig uebertroffen?
    if profil and profil.get("n", 0) >= 4:
        bq = profil.get("beat_quote")
        if bq is not None and bq >= 75:
            pro.append(f"übertrifft die Schätzung in {bq} % der Fälle")
        elif bq is not None and bq <= 40:
            contra.append(f"verfehlt die Schätzung häufig (Beat-Quote {bq} %)")

    # 2) Richtung der Revisionen
    r = eps_rev or {}
    up, down = r.get("up"), r.get("down")
    if up is not None and down is not None:
        if up > down:
            pro.append(f"Schätzungen zuletzt angehoben ({up} hoch / {down} runter)")
        elif down > up:
            contra.append(f"Schätzungen zuletzt gesenkt ({down} runter / {up} hoch)")

    # 3) Erwarteter Gewinnrueckgang trotz wachsendem Umsatz
    epsf, epst = f.get("eps_forward"), f.get("eps_trailing")
    rg = f.get("revenue_growth")
    if epsf is not None and epst is not None and epst > 0 and epsf < epst * 0.95:
        if rg is not None and rg >= 0.05:
            pro.append(f"Gewinnrückgang erwartet, obwohl Umsatz +{rg*100:.0f} % wächst")
        else:
            contra.append("Gewinnrückgang erwartet")

    # 4) Cashflow gegen Buchgewinn
    fcf, ni = f.get("free_cashflow"), f.get("net_income")
    if fcf and ni is not None and ni <= 0 < fcf:
        pro.append("positiver Cashflow trotz Buchverlust")

    return pro, contra


def earnings_preview(ticker, max_wochen=4):
    """Volles Bild vor einem Quartalstermin.

    Verbindet vier Dinge:
      * wann gemeldet wird
      * wie die Aktie historisch auf Beats/Misses reagiert hat
      * was die Analysten erwarten
      * welche beobachtbaren Trends dieser Erwartung widersprechen

    Das Urteil sagt bewusst NICHT "kaufen" - es sagt, ob die Konstellation
    ueberhaupt interessant ist und worauf zu achten waere."""
    if providers is None:
        return None
    termin = next_earnings(ticker, max_wochen)
    if not termin:
        return None
    try:
        f = providers.get_fundamentals(ticker, deep=False) or {}
    except Exception:
        f = {}
    if not f.get("price"):
        return None
    try:
        eps_rev = providers.get_eps_revision_light(ticker)
    except Exception:
        eps_rev = None
    profil = reaction_profile(ticker)
    pro, contra = _erwartung_spannung(f, eps_rev, profil)

    out = {
        "ticker": ticker,
        "name": (f.get("name") or "")[:32],
        "sektor": f.get("sector"),
        "datum": termin["datum"],
        "tage": termin["tage"],
        "eps_estimate": termin["eps_estimate"],
        "eps_forward": f.get("eps_forward"),
        "revenue_growth": (round(f["revenue_growth"] * 100, 1)
                           if f.get("revenue_growth") is not None else None),
        "beat_quote": (profil or {}).get("beat_quote"),
        "belohnt_pct": (profil or {}).get("beat_belohnt_pct"),
        "n_termine": (profil or {}).get("n"),
        "avg_reaktion_beat": (profil or {}).get("avg_reaktion_beat"),
        "pro": pro, "contra": contra,
        "profil_urteil": (profil or {}).get("urteil"),
    }

    # --- Einordnung. Bewusst zurueckhaltend und immer mit Fallzahl im Blick.
    bq, bel, n = out["beat_quote"], out["belohnt_pct"], out["n_termine"] or 0
    if n < 4:
        out["urteil"] = "zu wenig Historie – Termin nur als Risiko vormerken"
        out["ampel"] = "grau"
    elif bq is not None and bq >= 75 and bel is not None and bel >= 70:
        out["urteil"] = ("übertrifft meist UND wird dafür belohnt – die "
                         "interessanteste Konstellation, aber auf dünner Basis")
        out["ampel"] = "gruen"
    elif bq is not None and bq >= 75 and bel is not None and bel <= 40:
        out["urteil"] = ("übertrifft meist, aber der Markt zahlt nichts dafür – "
                         "gute Zahlen sind hier bereits eingepreist")
        out["ampel"] = "gelb"
    elif bq is not None and bq <= 40:
        out["urteil"] = "verfehlt die Schätzung häufig – erhöhtes Rückschlagrisiko"
        out["ampel"] = "rot"
    else:
        out["urteil"] = "kein klares Muster – Termin als Schwankungsrisiko sehen"
        out["ampel"] = "grau"
    if len(pro) >= 2:
        out["urteil"] += f" · {len(pro)} Punkte sprechen gegen die Erwartung"
    return out


def earnings_scan(tickers, max_wochen=4, limit=40):
    """Welche Titel melden in den naechsten Wochen? Mit voller Einordnung.

    Bewusst gedeckelt: je Titel fallen mehrere Abrufe an. Fuer Portfolio
    und Watchlist ist das unproblematisch, fuer ein Universum von hunderten
    Tickern nicht."""
    out = []
    for t in list(dict.fromkeys(tickers))[:limit]:
        try:
            p = earnings_preview(t, max_wochen)
        except Exception:
            p = None
        if p:
            out.append(p)
    out.sort(key=lambda r: r["tage"])
    return out


# ============================================================================
# S&P-500-UNIVERSUM
# ============================================================================
_SP500_CACHE = {}


def sp500_tickers():
    """Aktuelle S&P-500-Mitglieder. Wikipedia zuerst, sonst Rueckfall auf
    die groessten US-Titel aus dem vorhandenen Screener."""
    if "list" in _SP500_CACHE:
        return _SP500_CACHE["list"]
    out = []
    try:
        import pandas as _pd
        tabs = _pd.read_html(
            "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")
        for t in tabs:
            if "Symbol" in t.columns:
                out = [str(s).strip().upper().replace(".", "-")
                       for s in t["Symbol"].tolist()]
                break
    except Exception:
        out = []
    if not out:                                   # Rueckfall
        try:
            import market_screener as _ms
            out, _src = _ms.get_universe(["us"], 5e9, 500)
        except Exception:
            out = []
    out = [t for t in dict.fromkeys(out) if t]
    _SP500_CACHE["list"] = out
    return out


def earnings_scan_universe(tickers=None, max_wochen=4, deep_limit=60,
                           fortschritt=None):
    """ZWEISTUFIG ueber ein grosses Universum.

    Stufe 1 (billig): nur der Termin je Titel - ein Abruf. Bei 500 Titeln
                      sind das 500 Abrufe.
    Stufe 2 (teuer):  volle Einordnung NUR fuer die, die im Fenster melden.
                      Ausserhalb der Berichtssaison sind das wenige, mitten
                      drin einige Dutzend.

    Ohne diese Trennung waeren es ueber 3.000 Abrufe je Lauf."""
    tickers = tickers or sp500_tickers()
    faellig = []
    for i, t in enumerate(tickers):
        try:
            n = next_earnings(t, max_wochen)
            if n:
                faellig.append((t, n["tage"]))
        except Exception:
            pass
        if fortschritt and (i + 1) % 50 == 0:
            fortschritt(i + 1, len(tickers), len(faellig))
    faellig.sort(key=lambda x: x[1])
    print(f"  [Earnings] {len(faellig)} von {len(tickers)} melden in "
          f"{max_wochen} Wochen -> {min(len(faellig), deep_limit)} werden "
          f"tief analysiert.")
    out = []
    for t, _tage in faellig[:deep_limit]:
        try:
            p = earnings_preview(t, max_wochen)
        except Exception:
            p = None
        if p:
            out.append(p)
    out.sort(key=lambda r: r["tage"])
    return out


# ============================================================================
# ERWARTUNGSLUECKE — wo laeuft das Geschaeft der Schaetzung davon?
# ----------------------------------------------------------------------------
# WAS DAS IST UND WAS NICHT
#   Das sagt KEINEN Beat voraus. Rund 75 % aller S&P-500-Unternehmen
#   uebertreffen die Schaetzung ohnehin - "es wird geschlagen" ist zu 75 %
#   richtig, ganz ohne Modell, und der Markt weiss das auch.
#
#   Gesucht wird deshalb etwas anderes: Stellen, an denen die ANALYSTEN-
#   ERWARTUNG dem beobachtbaren Geschaeftsverlauf hinterherlaeuft. Wenn
#   der Umsatz drei Quartale in Folge beschleunigt, die Schaetzung fuer das
#   naechste Quartal aber einen Rueckgang unterstellt, ist das eine messbare
#   Spannung - kein Beweis, aber eine Frage, der man nachgehen kann.
#
#   Genau diese Konstellation lag bei Intel Q2 2026 vor: 16,1 statt 14,4
#   Mrd. Umsatz. Ob unser Filter sie VORHER gefunden haette, weiss man
#   erst, wenn die Trefferbilanz genug Faelle gesammelt hat.
#
# DATENGRENZEN
#   Ist-Zahlen je Quartal: roic, viele Jahre.
#   Damalige Schaetzungen: nur yfinance, maximal 8 Quartale.
#   Kommende Schaetzung: yfinance (eps_forward, Revisionen).
# ============================================================================


def _quartalsreihe(ticker, n=12):
    """Umsatz und Gewinn je Quartal aus roic - aelteste zuerst."""
    if _roic is None or not _roic.enabled() or not _roic.covers(ticker):
        return []
    try:
        roh = _roic.financials(ticker, "income", "quarter", n) or []
    except Exception:
        return []
    out = []
    for z in roh:
        if not isinstance(z, dict):
            continue
        d = str(z.get("date") or "")[:10]
        rev = z.get("is_sales_revenue_turnover") or z.get(
            "is_sales_and_services_revenues")
        eps = z.get("eps") or z.get("diluted_eps")
        try:
            rev = float(rev) if rev is not None else None
            eps = float(eps) if eps is not None else None
        except Exception:
            continue
        if d and rev:
            out.append({"datum": d, "revenue": rev, "eps": eps})
    out.sort(key=lambda z: z["datum"])
    return out


def _beschleunigung(reihe):
    """Waechst der Umsatz zuletzt schneller als davor?

    Verglichen werden die letzten drei Quartalsveraenderungen mit den drei
    davor - so faellt Saisonalitaet weniger ins Gewicht als bei einem
    einzelnen Quartalsvergleich."""
    if len(reihe) < 8:
        return None
    def _wachstum(a, b):
        return (b / a - 1) * 100 if a else None
    v = []
    for i in range(1, len(reihe)):
        w = _wachstum(reihe[i - 1]["revenue"], reihe[i]["revenue"])
        if w is not None:
            v.append(w)
    if len(v) < 6:
        return None
    neu = sum(v[-3:]) / 3
    alt = sum(v[-6:-3]) / 3
    return round(neu - alt, 1)


def erwartungsluecke(ticker):
    """Wo laeuft das Geschaeft der Analystenerwartung davon?

    Rueckgabe: {punkte, spannungen, gegen, urteil, ...} oder None."""
    if providers is None:
        return None
    try:
        f = providers.get_fundamentals(ticker, deep=True) or {}
    except Exception:
        f = {}
    if not f.get("price"):
        return None
    reihe = _quartalsreihe(ticker, 12)
    profil = reaction_profile(ticker)
    try:
        rev_rev = providers.get_eps_revision_light(ticker) or {}
    except Exception:
        rev_rev = {}

    spannungen, gegen = [], []
    punkte = 0

    # 1) Beschleunigt das Geschaeft?
    besch = _beschleunigung(reihe)
    if besch is not None:
        if besch >= 3:
            spannungen.append(f"Umsatzwachstum beschleunigt "
                              f"(+{besch:.1f} Prozentpunkte gegenüber den "
                              "drei Quartalen davor)")
            punkte += 2
        elif besch <= -3:
            gegen.append(f"Umsatzwachstum verlangsamt sich ({besch:.1f} Pp)")
            punkte -= 1

    # 2) Sequenzielle Erholung nach schwachen Quartalen
    if len(reihe) >= 4:
        letzte = [z["revenue"] for z in reihe[-4:]]
        if letzte[-1] > letzte[-2] > letzte[-3]:
            spannungen.append("Umsatz steigt zwei Quartale in Folge")
            punkte += 1
        eps4 = [z["eps"] for z in reihe[-4:] if z.get("eps") is not None]
        if len(eps4) >= 3 and eps4[0] < 0 <= eps4[-1]:
            spannungen.append("Rückkehr in die Gewinnzone")
            punkte += 2

    # 3) Richtung der Revisionen
    up, down = rev_rev.get("up"), rev_rev.get("down")
    if up is not None and down is not None and (up + down) > 0:
        if up > down:
            spannungen.append(f"Schätzungen zuletzt angehoben "
                              f"({up} hoch / {down} runter)")
            punkte += 1
        elif down > up * 2:
            gegen.append(f"Schätzungen deutlich gesenkt ({down} runter / {up} hoch)")
            punkte -= 2

    # 4) Erwartet die Schaetzung einen Rueckgang, obwohl der Umsatz waechst?
    epsf, epst = f.get("eps_forward"), f.get("eps_trailing")
    rg = f.get("revenue_growth")
    if epsf is not None and epst is not None and epst > 0 and epsf < epst * 0.95:
        if rg is not None and rg >= 0.05:
            spannungen.append(f"Gewinnrückgang erwartet, obwohl der Umsatz "
                              f"um {rg*100:.0f} % wächst")
            punkte += 2

    # 5) Historie: wird gewohnheitsmaessig uebertroffen?
    bq = (profil or {}).get("beat_quote")
    n_prof = (profil or {}).get("n") or 0
    if n_prof >= 4 and bq is not None:
        if bq >= 75:
            spannungen.append(f"übertrifft die Schätzung in {bq} % der "
                              f"letzten {n_prof} Quartale")
            punkte += 1
        elif bq <= 40:
            gegen.append(f"verfehlt häufig (Beat-Quote {bq} % aus {n_prof})")
            punkte -= 2

    # 6) Belohnt der Markt Beats ueberhaupt?
    bel = (profil or {}).get("beat_belohnt_pct")
    if bel is not None and n_prof >= 4:
        if bel <= 40:
            gegen.append(f"gute Zahlen wurden zuletzt nur in {bel} % der Fälle "
                         "belohnt – ein Beat allein bewegt den Kurs kaum")
            punkte -= 1

    if punkte >= 5:
        urteil = ("mehrere unabhängige Spannungen – die Erwartung wirkt "
                  "niedrig gegenüber dem Geschäftsverlauf")
        ampel = "gruen"
    elif punkte >= 3:
        urteil = "einzelne Spannungen, kein klares Bild"
        ampel = "gelb"
    elif punkte <= -2:
        urteil = "die Erwartung wirkt eher zu hoch als zu niedrig"
        ampel = "rot"
    else:
        urteil = "keine auffällige Lücke zwischen Erwartung und Verlauf"
        ampel = "grau"

    return {
        "ticker": ticker,
        "punkte": punkte,
        "ampel": ampel,
        "urteil": urteil,
        "spannungen": spannungen,
        "gegen": gegen,
        "beschleunigung_pp": besch,
        "n_quartale": len(reihe),
        "beat_quote": bq,
        "belohnt_pct": bel,
        "reihe": reihe[-8:],
    }
