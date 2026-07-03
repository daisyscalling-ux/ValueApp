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


def dedupe_by_name(funds):
    """Doppel-Listings (z.B. AVGO vs 1YD.DE/1YDD.XC) auf eine Aktie je Firma reduzieren."""
    best = {}
    for f in funds:
        nm = (f.get("name") or f.get("ticker") or "").strip().lower()
        if not nm:
            continue
        if nm not in best or _pref(f) < _pref(best[nm]):
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


def compute(fund, hist_df, eps_rev, insider, events_8k, headlines):
    """Berechnet den Radar-Score + Ebenen + konkrete Trigger fuer eine Aktie."""
    from providers import SEC_ITEM_LABELS
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

    # ---- Gewichteter Score + Koinzidenz-Bonus ----
    score = (0.30 * events + 0.20 * fundamental + 0.25 * estimates + 0.25 * accumulation)
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
        "triggers": triggers,
    }
