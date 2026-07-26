"""
radar.py — "Das Micron von morgen": Scanner fuer Frueh-Signale eines
moeglichen Kursausbruchs, bevor der breite Markt reagiert.

Vier Signal-Ebenen, kombiniert zum "Vor-der-Welle-Score" (0-100):
  1. EVENTS        (30%) — SEC-8-K-Katalysatoren + News-Trigger
                            (\u00dcbernahme, Fusion, Kooperation, Grossauftrag ...)
  2. FUNDAMENTAL   (20%) — Wachstumsniveau + Auftragseingang/Backlog-Hinweise
  3. ESTIMATES     (25%) — Schaetzungs-Momentum (EPS-Revisionen)
  4. AKKUMULATION  (25%) — Insiderkaeufe, Volumen-Spike, Short-Trend, Setup

Koinzidenz-Bonus: leuchten >=3 Ebenen gleichzeitig, wird der Score angehoben —
genau die Mehrfach-Konstellation ist das staerkste Vorbeben.

Alles degradiert sauber: fehlt eine Quelle, faellt nur ihr Beitrag weg.
"""
from __future__ import annotations

# Themen-Universen fuer den engen, schnellen Scan
THEMES = {
    "Memory & Semis": ["MU", "NVDA", "AMD", "AVGO", "MRVL", "LRCX", "AMAT", "KLAC",
                       "ADI", "ON", "TXN", "INTC", "QCOM", "ASML", "STM", "WOLF",
                       "TER", "ENTG", "ACLS", "SITM", "AOSL"],
    "AI-Infrastruktur": ["NVDA", "AVGO", "SMCI", "DELL", "ANET", "VRT", "CRDO",
                         "ALAB", "MRVL", "CIEN", "COHR", "LITE", "PSTG", "NTAP"],
    "Power & Grid": ["GEV", "ETN", "PWR", "VRT", "NEE", "VST", "CEG", "TLN",
                     "NRG", "PRME", "GNRC", "AGX", "POWL", "HUBB", "AMSC"],
    "Defense & Space": ["LMT", "RTX", "NOC", "GD", "LHX", "HWM", "KTOS", "AVAV",
                        "RKLB", "LDOS", "BWXT", "HEI", "CW", "MRCY"],
    "Energie & Uran": ["CCJ", "UEC", "UUUU", "DNN", "NXE", "LEU", "OKLO", "SMR",
                       "VST", "CEG", "EOG", "FANG", "AR"],
    "Healthcare/Biotech Mid": ["VKTX", "CRNX", "RXRX", "TEM", "HIMS", "EXAS",
                               "NTRA", "ALNY", "SRPT", "MDGL"],
    "Financials & Banken": ["C", "JPM", "BAC", "WFC", "GS", "MS", "SCHW", "USB",
                            "PNC", "COF", "AXP", "BLK", "KKR", "APO",
                            "DBK.DE", "CBK.DE", "ALV.DE", "MUV2.DE"],
    "Konsum & Industrie": ["AMZN", "COST", "WMT", "HD", "MCD", "NKE", "SBUX",
                           "CAT", "DE", "HON", "GE", "UNP", "UPS", "BA"],
}

# Hauptbranchen fuer den marktweiten Branchen-Scan (yfinance-Sektor, optional Branchen-Stichwort)
BRANCHES = {
    "Technologie": ("Technology", None),
    "Industrie": ("Industrials", None),
    "Finanzen (Banken/Dienstleister)": ("Financial Services", None),
    "Versicherungen": ("Financial Services", "insurance"),
    "Gesundheit/Pharma": ("Healthcare", None),
    "Energie": ("Energy", None),
    "Rohstoffe/Chemie": ("Basic Materials", None),
    "Konsum zyklisch": ("Consumer Cyclical", None),
    "Konsum defensiv": ("Consumer Defensive", None),
    "Versorger": ("Utilities", None),
    "Immobilien (REITs)": ("Real Estate", None),
    "Kommunikation/Medien": ("Communication Services", None),
}


def in_branch(fund, sector, industry_kw=None) -> bool:
    if (fund.get("sector") or "") != sector:
        return False
    if industry_kw and industry_kw.lower() not in (fund.get("industry") or "").lower():
        return False
    return True

# Katalysator-Stichwoerter (DE/EN) fuer die News-Triggererkennung
EVENT_KW = {
    "\u00dcbernahme/M&A": ["\u00fcbernahme", "acquisition", "acquire", "takeover",
                           "fusion", "merger", "to buy", "buyout", "kauft"],
    "Kooperation": ["kooperation", "partnership", "partnerschaft", "collaboration",
                    "teams up", "joint venture", "strategic alliance"],
    "Grossauftrag": ["gro\u00dfauftrag", "grossauftrag", "supply agreement", "contract win",
                     "auftrag", "order", "design win", "milliarden-auftrag", "wins deal"],
    "Beteiligung/Stake": ["stake", "beteiligung", "investment in", "einstieg bei"],
}
BACKLOG_KW = ["backlog", "auftragseingang", "auftragsbestand", "bookings",
              "book-to-bill", "record orders", "rekordauftr"]

# Positive 8-K Items und ihr Event-Gewicht
SEC_EVENT_WEIGHT = {"2.01": 45, "1.01": 40, "8.01": 22, "7.01": 15, "3.02": 8}


def _pref(f):
    """Sortierschluessel: bevorzugt Ticker OHNE Boersen-Suffix (.DE/.F/.XC ...),
    dann kuerzeren Ticker, dann hoehere Marktkapitalisierung."""
    t = f.get("ticker", "") or ""
    return (1 if "." in t else 0, len(t), -(f.get("market_cap") or 0))


_SUFFIX_LAND = {
    "": "US", "DE": "DE", "F": "DE", "MU": "DE", "BE": "DE", "SG": "DE",
    "DU": "DE", "HM": "DE", "HA": "DE", "STU": "DE",
    "L": "GB", "IL": "GB", "PA": "FR", "AS": "NL", "BR": "BE",
    "MI": "IT", "MC": "ES", "SW": "CH", "VX": "CH", "ST": "SE",
    "HE": "FI", "OL": "NO", "CO": "DK", "VI": "AT", "LS": "PT",
    "TO": "CA", "T": "JP", "HK": "HK", "AX": "AU",
}


def _ticker_land(t):
    if "." not in (t or ""):
        return "US"
    return _SUFFIX_LAND.get(t.rsplit(".", 1)[-1].upper(), "?")


def _dedupe_isin(funds):
    """Auslands-Zweitnotierungen ueber die ISIN entfernen (APC.DE/0R2V.L ->
    AAPL). Titel ohne ISIN bleiben fuer die Namens-Entdopplung erhalten."""
    gruppen, ohne = {}, []
    for f in funds:
        isin = f.get("isin")
        if isin:
            gruppen.setdefault(str(isin).upper(), []).append(f)
        else:
            ohne.append(f)
    behalten = []
    for isin, g in gruppen.items():
        if len(g) == 1:
            behalten.append(g[0])
            continue
        land = str(isin)[:2].upper()

        def _rang(f):
            t = f.get("ticker") or ""
            return (0 if _ticker_land(t) == land else 1,
                    0 if "." not in t else 1)
        g.sort(key=_rang)
        behalten.append(g[0])
    return behalten + ohne


def _norm_firma(name):
    """Firmenname auf Vergleichsform bringen (Rechtsformen/Zusaetze weg)."""
    if not name:
        return ""
    s = str(name).lower()
    for w in (" plc", " inc.", " inc", " corp.", " corp", " ag", " se",
              " nv", " sa", " ltd.", " ltd", " limited", " group", " holdings",
              " company", " co.", " the ", ",", "."):
        s = s.replace(w, " ")
    return " ".join(s.split())


def dedupe_by_name(funds):
    """Doppel-Listings auf eine Aktie je Firma reduzieren. ZWEISTUFIG:
    zuerst ueber die ISIN (stabilster Schluessel), dann ueber den Namen -
    Letzteres faengt Auslands-Zweitnotierungen wie 0R2V.L / APC8.F, fuer die
    roic oft keine ISIN liefert. Beide Stufen bevorzugen die Heimatboerse."""
    def _rang(f):
        t = f.get("ticker") or ""
        isin = f.get("isin")
        land = (str(isin)[:2].upper() if isin and len(str(isin)) >= 2
                else _ticker_land(t))
        return (0 if _ticker_land(t) == land else 1,
                0 if "." not in t else 1)

    # Stufe 1: ISIN
    funds = _dedupe_isin(funds)

    # Stufe 2: Name (auch gegen die ISIN-Gewinner pruefen)
    best = {}
    for f in funds:
        nm = _norm_firma(f.get("name")) or (f.get("ticker") or "").lower()
        if not nm:
            continue
        if nm not in best or _rang(f) < _rang(best[nm]):
            best[nm] = f
    return list(best.values())


def _vol_spike(vols):
    if not vols or len(vols) < 30:
        return None
    recent = sum(vols[-5:]) / 5
    base = sum(vols[-60:-5]) / max(len(vols[-60:-5]), 1)
    return (recent / base) if base else None


def _setup(price, hi, lo, closes):
    """Gibt (label, punkte, trigger) fuer die Chart-Lage zurueck."""
    if not (price and hi and lo and hi > lo):
        return (0, None)
    pos = (price - lo) / (hi - lo)            # 0=Tief, 1=Hoch
    mom_1m = None
    if closes and len(closes) >= 21 and closes[-21]:
        mom_1m = price / closes[-21] - 1
    if pos <= 0.4 and (mom_1m or 0) > 0:
        return (25, f"Basenbildung am Tief, +{(mom_1m or 0)*100:.0f}% (1M)")
    if pos >= 0.85 and (mom_1m or 0) > 0.05:
        return (15, "Ausbruch nahe 52W-Hoch")
    if pos <= 0.4:
        return (10, "nahe 52W-Tief (Boden gesucht)")
    return (0, None)


def _catalyst(closes, events, spike):
    """Erkennt einen FRISCHEN, scharfen Kursausbruch. Es zaehlen nur die juengsten
    Sessions (1/3/5 Tage) -> die Frische ist eingebaut: eine Bewegung von letzter
    Woche ist morgen aus dem Fenster. Bestaetigung durch News/Volumen verstaerkt.
    Rueckgabe: (bonus_punkte, trigger|None, info|None)."""
    cl = [c for c in (closes or []) if c and c > 0]
    if len(cl) < 6:
        return 0, None, None

    def ret(n):
        return (cl[-1] / cl[-1 - n] - 1) if (len(cl) > n and cl[-1 - n]) else None
    moves = [x for x in (ret(1), ret(3), ret(5)) if x is not None]
    if not moves:
        return 0, None, None
    up_move, dn_move = max(moves), min(moves)
    confirmed = (events >= 14) or bool(spike and spike > 1.8)
    if up_move >= 0.08:                       # frischer Ausbruch nach oben
        base = 22 if up_move >= 0.20 else (14 if up_move >= 0.12 else 8)
        pts = min(base + (12 if confirmed else 0), 34)
        why = "mit News/Volumen" if confirmed else "ohne klaren Ausl\u00f6ser"
        trig = f"\U0001f525 Frischer Ausbruch +{up_move*100:.0f}% ({why})"
        return pts, trig, {"dir": "up", "move": round(up_move * 100, 1),
                           "confirmed": bool(confirmed), "fresh": True}
    if dn_move <= -0.12:                       # scharfer Absturz -> nur Sichtbarkeit
        trig = f"\u26a0 Kurssturz {dn_move*100:.0f}% \u2013 Ereignis pr\u00fcfen"
        return 0, trig, {"dir": "down", "move": round(dn_move * 100, 1),
                         "confirmed": bool(confirmed), "fresh": True}
    return 0, None, None


def catalyst_flag(closes, price=None, fair_value=None):
    """Leichtgewichtiger Katalysator-Hinweis aus der Kurshistorie allein (kein
    News-Abruf noetig) - fuer Einzelanalyse/Portfolio. Enthaelt zusaetzlich die
    Warnung, wenn der Kurs dem fairen Wert nach einem Ausbruch weit vorauseilt."""
    _pts, trig, info = _catalyst(closes or [], 0, None)
    warning = None
    if info and info.get("dir") == "up" and price and fair_value and fair_value > 0:
        if price > fair_value * 1.5:
            warning = ("Kurs der Nachricht weit vorausgeeilt \u2013 liegt deutlich "
                       f"\u00fcber dem fairen Wert. Euphorie? Beobachten, nicht "
                       "hinterherlaufen.")
    return {"trigger": trig, "info": info, "warning": warning}


def compute(fund, hist_df, eps_rev, insider, events_8k, headlines):
    """Berechnet den Radar-Score + Ebenen + konkrete Trigger fuer eine Aktie."""
    triggers = []
    closes, vols = [], []
    if hist_df is not None and not getattr(hist_df, "empty", True):
        try:
            closes = [float(x) for x in hist_df["Close"].dropna().tolist()]
            if "Volume" in hist_df.columns:
                vols = [float(x) for x in hist_df["Volume"].fillna(0).tolist()]
        except Exception:
            pass
    price = fund.get("price") or (closes[-1] if closes else None)
    heads_l = [h.lower() for h in (headlines or [])]

    # ---- 1) EVENTS ----
    ev = 0
    for f8 in (events_8k or []):
        for code in f8.get("items", []):
            wgt = SEC_EVENT_WEIGHT.get(code)
            if wgt:
                ev += wgt
                from providers import SEC_ITEM_LABELS
                triggers.append(f"8-K {f8.get('date','')}: {SEC_ITEM_LABELS.get(code, code)}")
    for kind, kws in EVENT_KW.items():
        if any(any(k in h for k in kws) for h in heads_l):
            ev += 14
            triggers.append(f"News-Trigger: {kind}")
    events = min(ev, 100)

    # ---- 2) FUNDAMENTAL ----
    fu = 0
    g = fund.get("revenue_growth")
    if g is not None:
        if g > 0.20:
            fu += 30; triggers.append(f"Umsatzwachstum +{g*100:.0f}%")
        elif g > 0.10:
            fu += 20
        elif g > 0:
            fu += 10
    if any(any(k in h for k in BACKLOG_KW) for h in heads_l):
        fu += 30; triggers.append("Auftragseingang/Backlog erw\u00e4hnt")
    gm = fund.get("gross_margin")
    if gm and gm > 0.5:
        fu += 10
    fundamental = min(fu, 100)

    # ---- 3) ESTIMATES ----
    es = 0
    up, dn = (eps_rev or {}).get("up", 0), (eps_rev or {}).get("down", 0)
    if up or dn:
        if up >= 2 * max(dn, 1):
            es += 60; triggers.append(f"EPS-Sch\u00e4tzungen stark angehoben ({up}\u2191/{dn}\u2193)")
        elif up > dn:
            es += 35; triggers.append(f"EPS-Sch\u00e4tzungen angehoben ({up}\u2191/{dn}\u2193)")
        elif dn > up:
            es += 0
    rec = (fund.get("recommendation") or "").lower()
    if rec in ("buy", "strong_buy"):
        es += 15
    estimates = min(es, 100)

    # ---- 4) AKKUMULATION ----
    ac = 0
    spike = _vol_spike(vols)
    if spike:
        if spike > 2.5:
            ac += 40; triggers.append(f"Volumen-Spike x{spike:.1f}")
        elif spike > 1.5:
            ac += 22; triggers.append(f"erh\u00f6htes Volumen x{spike:.1f}")
    ins = insider or {}
    if ins.get("buys", 0) > ins.get("sells", 0) and ins.get("buys", 0) > 0:
        ac += 30; triggers.append(f"Insiderk\u00e4ufe ({ins.get('buys')})")
    pts, trig = _setup(price, fund.get("52w_high"), fund.get("52w_low"), closes)
    if pts:
        ac += pts
        if trig:
            triggers.append(trig)
    accumulation = min(ac, 100)

    # ---- Frischer Katalysator (News/Ausbruch, zeitlich frisch) ----
    cat_pts, cat_trig, cat_info = _catalyst(closes, events, spike)
    if cat_trig:
        triggers.insert(0, cat_trig)

    # ---- Gewichteter Score + Koinzidenz-Bonus ----
    score = (0.30 * events + 0.20 * fundamental + 0.25 * estimates + 0.25 * accumulation)
    score = min(100, score + cat_pts)          # frischer Katalysator als Bonus obendrauf
    firing = sum(1 for x in (events, fundamental, estimates, accumulation) if x >= 40)
    if firing >= 4:
        score = min(100, score * 1.25); triggers.insert(0, "\u26a1 Mehrfach-Signal (4 Ebenen)")
    elif firing >= 3:
        score = min(100, score * 1.15); triggers.insert(0, "\u26a1 Mehrfach-Signal (3 Ebenen)")

    return {
        "ticker": fund.get("ticker"),
        "name": fund.get("name"),
        "sector": fund.get("sector"),
        "score": round(score, 1),
        "layers": {"events": round(events), "fundamental": round(fundamental),
                   "estimates": round(estimates), "accumulation": round(accumulation)},
        "firing": firing,
        "catalyst": cat_info,
        "triggers": triggers,
    }
