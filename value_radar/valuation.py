"""
valuation.py — Bewertungs-Engine v4 (schlank: 3 Kernmethoden je Playbook).

Ziel: wenige, verlaessliche, marktnahe Verfahren mit geringer Streuung.

  justified_pe : "Faires KGV" (Sockel + Stabilitaet + Marktposition x Rentabilitaet
                 + Wachstumsaufschlag) x Forward-EPS          -> Hauptanker
  ev_ebitda    : Sektor/Peer-EV-EBITDA (wachstumsadjustiert) x EBITDA - Nettoschulden
  dcf          : zweistufiger Discounted-Cashflow (konservativ, Gordon-Terminal)
  pb           : Kurs-Buchwert (KBV) — ersetzt DCF bei Zyklikern (Tief-verzerrt)

Quality/Inflection:  faires KGV (.45) + EV/EBITDA (.30) + DCF (.25)
Cyclical:            EV/EBITDA (.40) + KBV (.35) + faires KGV (.25)

Fair Value = gewichteter Blend; zusaetzlich wird die Bewertungsspanne (min-max)
ausgewiesen, damit die Streuung sichtbar bleibt.
"""
from __future__ import annotations
from typing import Optional
import config

V = config.VALUATION

METHOD_LABELS = {
    "justified_pe": "Faires KGV (Punktesystem)",
    "ev_ebitda": "EV/EBITDA-Multiple (mid-cycle)",
    "dcf": "Discounted-Cashflow (DCF, 10J)",
    "pb": "Kurs-Buchwert (KBV)",
    "analyst": "Analysten-Konsensziel (\u00d8 Kursziel)",
    "epv": "Earnings Power Value (Null-Wachstum)",
    "fwd_pe": "Forward-Multiple (EPS n\u00e4chstes Jahr)",
    "fwd_composite": "Forward-Multiple 2 (KGV+EV/EBITDA-Schnitt)",
    "hist_pe": "Markt-Fair-Value (hist. Median-KGV)",
}

_SECTOR_PB = {
    "Technology": 6, "Communication Services": 3, "Consumer Cyclical": 4,
    "Consumer Defensive": 5, "Healthcare": 4, "Financial Services": 1.3,
    "Industrials": 4, "Energy": 1.6, "Basic Materials": 1.8, "Utilities": 1.6,
    "Real Estate": 1.8, "_default": 2.5,
}


def _median(xs):
    s = sorted(xs)
    n = len(s)
    return None if n == 0 else (s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2)


def _eps(fund):
    return fund.get("eps_forward") or fund.get("eps_trailing")


def _sector(fund, table):
    return table.get(fund.get("sector"), table["_default"])


# Klar zyklische Branchen (yfinance-Industry-Stichwoerter)
_CYCLICAL_INDUSTRIES = [
    "oil", "gas", "coal", "mining", "metals", "steel", "copper", "aluminum",
    "gold", "silver", "auto manufacturers", "auto parts", "airlines", "shipping",
    "marine", "homebuild", "memory", "semiconductor equipment", "chemicals",
    "paper", "lumber", "agricultural inputs", "building materials", "drilling",
]
_DEFENSIVE_SECTORS = {"Utilities", "Consumer Defensive", "Healthcare"}
_CYCLICAL_SECTORS = {"Energy", "Basic Materials"}


def classify_playbook(fund) -> str:
    """Automatische Zuordnung des passenden Bewertungs-Playbooks.

      financial : Banken/Versicherer/Finanzdienstleister  (KGV + KBV; kein DCF/EV-EBITDA)
      cyclical  : klar zyklische Branche oder Sektor Energie/Rohstoffe
      inflection: Hyperwachstum (Umsatzwachstum >= 25 %)
      quality   : Standard (Compounder, defensive Werte)

    Sektor-bewusst: defensive Sektoren (Versorger, Basiskonsum, Gesundheit) werden
    NICHT zyklisch, auch wenn ein Stichwort (z. B. "gas" bei Gasversorgern) passt.
    """
    sector = fund.get("sector") or ""
    industry = (fund.get("industry") or "").lower()

    # 1) Finanzwerte: eigenes Modell (Gewinn + Buchwert)
    if sector == "Financial Services":
        return "financial"

    # 2) zyklisch — aber nie bei defensiven Sektoren
    if sector not in _DEFENSIVE_SECTORS:
        if sector in _CYCLICAL_SECTORS or any(k in industry for k in _CYCLICAL_INDUSTRIES):
            return "cyclical"

    # 3) Hyperwachstum
    g = fund.get("revenue_growth")
    if g is None:
        g = fund.get("earnings_growth") or 0
    if g >= 0.25:
        return "inflection"

    # 4) Standard
    return "quality"


def wacc(beta, market_cap, total_debt, tax_rate=None) -> float:
    tax_rate = V["tax_rate"] if tax_rate is None else tax_rate
    re = V["risk_free_rate"] + (beta or V["default_beta"]) * V["equity_risk_premium"]
    rd = V["risk_free_rate"] + 0.015
    e, d = market_cap or 0.0, total_debt or 0.0
    tot = e + d
    w = re if tot <= 0 else (e / tot) * re + (d / tot) * rd * (1 - tax_rate)
    return max(w, 0.085)


# --- 1) Faires KGV ----------------------------------------------------------
def justified_pe_number(fund, preset="quality") -> Optional[float]:
    eps = _eps(fund)
    if not eps or eps <= 0:
        return None
    base = 7.0
    stab = 0.0
    if (fund.get("free_cashflow") or 0) > 0:
        stab += 1
    nde = fund.get("net_debt_ebitda")
    if nde is not None:
        stab += 1 if nde < 2 else (0.5 if nde < 3 else 0)
    cr = fund.get("current_ratio")
    if cr and cr > 1.2:
        stab += 1
    stab = min(stab, 3)
    roe = fund.get("roe")
    if roe is None:
        prof = 1.5
    else:
        prof = (0 if roe < 0.05 else 1 if roe < 0.10 else 2 if roe < 0.15
                else 3 if roe < 0.20 else 4)
    gm = fund.get("gross_margin")
    pos = (1 if (gm is None or gm < 0.30) else 1.5 if gm < 0.40 else 2 if gm < 0.50
           else 2.8 if gm < 0.65 else 3.5)
    moat = min(prof * pos, 14)
    g = fund.get("revenue_growth")
    if g is None:
        g = fund.get("earnings_growth") or 0
    gp = (0 if g < 0 else 0.5 if g < 0.03 else 1 if g < 0.05 else 2 if g < 0.07
          else 3 if g < 0.10 else 4 if g < 0.15 else 5 if g < 0.20 else
          6 if g < 0.25 else 7.5 if g < 0.35 else 9)     # Hyperwachstum differenziert
    fair_pe = base + stab + moat + gp
    if preset == "inflection":
        fair_pe *= 1.1
    cap = (50 if preset == "inflection" else 42 if preset == "quality"
           else 18 if preset == "financial" else 16)
    return max(6.0, min(fair_pe, cap))


def justified_pe(fund, preset="quality") -> Optional[float]:
    pe = justified_pe_number(fund, preset)
    eps = _eps(fund)
    return pe * eps if (pe and eps and eps > 0) else None


# --- 2) EV/EBITDA -----------------------------------------------------------
def multiple_ev_ebitda(fund, peer_funds, preset="quality") -> Optional[float]:
    shares, ebitda = fund.get("shares_out"), fund.get("ebitda")
    if not shares or not ebitda or ebitda <= 0:
        return None
    cyclical = (preset == "cyclical")
    if peer_funds:
        ms = [p["ev_ebitda"] for p in peer_funds if p.get("ev_ebitda") and 0 < p["ev_ebitda"] < 60]
        target = _median(ms) or _sector(fund, config.SECTOR_EV_EBITDA)
    else:
        target = _sector(fund, config.SECTOR_EV_EBITDA)
    if not cyclical:
        g = fund.get("revenue_growth") or 0
        if g > 0.10:                                  # Wachstumsaufschlag (wie beim KGV)
            target *= 1 + min((g - 0.10) * 2.0, 0.6)
        cur = fund.get("ev_ebitda")
        if cur and cur > 0:
            # Teilweise Rueckkehr zum Mittel statt Voll-Reversion: Qualitaetsfirmen
            # kehren selten ganz zum Sektorschnitt zurueck. 60% Anker + 40% eigenes
            # Multiple (gedeckelt bei 2.5x Anker) daempft den systematischen Downside.
            target = 0.6 * target + 0.4 * min(cur, 2.5 * target)
    else:
        target = min(target, 8.5)                     # niedriges Multiple auf (Peak-)EBITDA
    equity = target * ebitda - (fund.get("net_debt") or 0.0)
    return equity / shares if equity > 0 else None


# --- 3a) DCF (Quality/Inflection) ------------------------------------------
def dcf_two_stage(fund, preset="quality") -> Optional[float]:
    if preset == "cyclical":
        return None
    fcf, shares = fund.get("free_cashflow"), fund.get("shares_out")
    if not fcf or not shares or fcf <= 0:
        return None
    years = max(int(V.get("projection_years", 10)), 2)   # konsistent mit Reverse-DCF
    g_term = V["terminal_growth"]
    g1 = fund.get("revenue_growth")
    if g1 is None:
        g1 = fund.get("earnings_growth") or 0.06
    cap = 0.25 if preset == "inflection" else 0.16
    g1 = max(min(g1, cap), -0.03)
    r = wacc(fund.get("beta"), fund.get("market_cap"), fund.get("total_debt"))
    if r - g_term < 0.045:
        r = g_term + 0.045
    pv, cf = 0.0, fcf
    for t in range(1, years + 1):
        g_t = g1 + (g_term - g1) * (t - 1) / (years - 1)
        cf *= (1 + g_t)
        pv += cf / ((1 + r) ** t)
    terminal = cf * (1 + g_term) / (r - g_term) / ((1 + r) ** years)
    equity = pv + terminal - (fund.get("net_debt") or 0.0)
    return equity / shares if equity > 0 else None


# --- 3b) KBV (Cyclical) -----------------------------------------------------
def multiple_pb(fund, preset="quality") -> Optional[float]:
    bvps = fund.get("book_value_ps")
    if not bvps or bvps <= 0:
        return None
    target_pb = 1.8 if preset == "cyclical" else _sector(fund, _SECTOR_PB)
    return target_pb * bvps


# --- Reverse-DCF (impliziertes Wachstum, fuer Interpretation) ---------------
def reverse_dcf_implied_growth(fund, years=None) -> Optional[float]:
    price = fund.get("price")
    fcf, shares = fund.get("free_cashflow"), fund.get("shares_out")
    if not price or not fcf or not shares or fcf <= 0:
        return None
    target_equity = price * shares + (fund.get("net_debt") or 0.0)
    r = wacc(fund.get("beta"), fund.get("market_cap"), fund.get("total_debt"))
    g_term = V["terminal_growth"]
    if r - g_term < 0.04:
        r = g_term + 0.04
    yrs = years or V["projection_years"]

    def equity_for_g(g):
        pv, cf = 0.0, fcf
        for t in range(1, yrs + 1):
            cf *= (1 + g)
            pv += cf / ((1 + r) ** t)
        pv += cf * (1 + g_term) / (r - g_term) / ((1 + r) ** yrs)
        return pv

    lo, hi = -0.20, 0.60
    for _ in range(60):
        mid = (lo + hi) / 2
        if equity_for_g(mid) < target_equity:
            lo = mid
        else:
            hi = mid
    return round((lo + hi) / 2, 4)


# --- Neue Methoden (Nutzer-Formelsammlung, geprueft & korrigiert) -------------
def _ebit_estimate(fund) -> Optional[float]:
    """EBIT-Schaetzung: operative Marge x Umsatz (Umsatz = MarketCap/KUV),
    Fallback 0.8 x EBITDA. Unser 'ebit'-Feld ist nur ein EBITDA-Alias, daher
    hier bewusst konservativ herleiten."""
    om, mc, ps = fund.get("operating_margin"), fund.get("market_cap"), fund.get("ps")
    if om and om > 0 and mc and ps and ps > 0:
        return om * (mc / ps)
    ebitda = fund.get("ebitda")
    return 0.8 * ebitda if ebitda and ebitda > 0 else None


def epv(fund, preset="quality") -> Optional[float]:
    """Earnings Power Value (Greenwald): Wert bei NULL Wachstum ab heute.
    NOPAT = EBIT x (1 - Steuersatz); EV_epv = NOPAT / WACC.
    KORREKTUR ggue. Vorlage: Nettoverschuldung MUSS abgezogen werden, sonst
    wird der Unternehmenswert (EV) faelschlich als Eigenkapitalwert ausgegeben."""
    ebit = _ebit_estimate(fund)
    shares = fund.get("shares_out")
    if not ebit or not shares or ebit <= 0:
        return None
    nopat = ebit * (1 - V["tax_rate"])
    w = wacc(fund.get("beta"), fund.get("market_cap"), fund.get("total_debt"))
    ev_epv = nopat / w
    equity = ev_epv - (fund.get("net_debt") or 0.0)
    return equity / shares if equity > 0 else None


def fwd_pe(fund, preset="quality") -> Optional[float]:
    """Forward-Multiple (einfach): erwartetes EPS x Ziel-KGV.
    Ziel-KGV = unser faires KGV aus dem Punktesystem (kein gewuerfelter Wert)."""
    eps1 = fund.get("eps_forward")
    if not eps1 or eps1 <= 0:
        return None
    return eps1 * justified_pe_number(fund, preset)


def fwd_composite(fund, preset="quality") -> Optional[float]:
    """Forward-Multiple 2 (erweitert): Durchschnitt aus verfuegbaren Komponenten
    A) EPS_fwd x Ziel-KGV,  B) (EBITDA_fwd x Ziel-EV/EBITDA - Nettoverschuldung)/Aktien.
    (Umsatz-Komponente entfaellt mangels verlaesslicher Forward-Umsatzschaetzung
    in den freien Daten - lieber 2 solide Komponenten als 3 mit einer geratenen.)"""
    parts = []
    a = fwd_pe(fund, preset)
    if a:
        parts.append(a)
    ebitda, shares = fund.get("ebitda"), fund.get("shares_out")
    if ebitda and ebitda > 0 and shares:
        g = fund.get("revenue_growth")
        g = max(min(g if g is not None else 0.0, 0.30), -0.10)
        ebitda_fwd = ebitda * (1 + g)
        sector = fund.get("sector") or "_default"
        target = config.SECTOR_EV_EBITDA.get(sector, config.SECTOR_EV_EBITDA["_default"])
        if preset == "cyclical":
            target = min(target, 8.5)
        equity = ebitda_fwd * target - (fund.get("net_debt") or 0.0)
        if equity > 0:
            parts.append(equity / shares)
    if not parts:
        return None
    return sum(parts) / len(parts)


def hist_pe(fund, preset="quality") -> Optional[float]:
    """Markt-Fair-Value: Forward-EPS x historischer Median-KGV (5-8 Jahre).
    Braucht die historische KGV-Reihe (fund['hist_pe_median'], via FMP im
    Deep-Modus). Ohne Daten: Methode entfaellt still."""
    eps1 = fund.get("eps_forward") or fund.get("eps_trailing")
    med = fund.get("hist_pe_median")
    if not eps1 or eps1 <= 0 or not med or med <= 0:
        return None
    med = min(med, 60.0)                      # Ausreisser-Schutz
    return eps1 * med


# --- 4) Analysten-Konsensziel ------------------------------------------------
def analyst_target(fund) -> Optional[float]:
    """Durchschnittliches Analysten-Kursziel als externe Konsens-Quelle.
    Das ist der Wert, den Portale wie TradingView/Marketscreener/Banken zeigen \u2013
    er verankert unsere modellbasierte Bewertung in der Markt-Realit\u00e4t.
    Plausibilit\u00e4t: nur akzeptieren, wenn 0.3x..3.5x des Kurses (Datenfehler-Schutz)."""
    tgt, price = fund.get("target_mean"), fund.get("price")
    if not tgt or not price or price <= 0:
        return None
    if not (0.3 * price <= tgt <= 3.5 * price):
        return None
    return float(tgt)


# --- Blend ------------------------------------------------------------------
# Analysten-Konsens ist bewusst substanziell gewichtet: unsere Modelle sind
# konservativ (mid-cycle-Multiples, gedeckelter DCF) und liegen bei teuren
# Wachstumsaktien systematisch unter dem Markt; der Analystenkonsens zieht die
# Bewertung Richtung dessen, was der Markt tatsaechlich einpreist.
_WEIGHTS = {
    "quality":    {"justified_pe": .15, "fwd_composite": .20, "dcf": .15, "epv": .05,
                   "ev_ebitda": .10, "hist_pe": .10, "analyst": .25},
    "inflection": {"fwd_pe": .15, "fwd_composite": .20, "dcf": .15, "justified_pe": .10,
                   "analyst": .40},
    "cyclical":   {"ev_ebitda": .25, "pb": .20, "epv": .15, "justified_pe": .15,
                   "analyst": .25},
    "financial":  {"justified_pe": .30, "pb": .30, "fwd_pe": .10, "hist_pe": .05,
                   "analyst": .25},
}


def fair_value(fund, peer_funds=None, preset="quality") -> dict:
    methods = {
        "justified_pe": justified_pe(fund, preset),
        "ev_ebitda": multiple_ev_ebitda(fund, peer_funds, preset),
        "dcf": dcf_two_stage(fund, preset),
        "pb": multiple_pb(fund, preset),
        "epv": epv(fund, preset),
        "fwd_pe": fwd_pe(fund, preset),
        "fwd_composite": fwd_composite(fund, preset),
        "hist_pe": hist_pe(fund, preset),
        "analyst": analyst_target(fund),
    }
    weights = _WEIGHTS.get(preset, _WEIGHTS["quality"])
    avail = {k: v for k, v in methods.items() if v and v > 0 and k in weights}

    # Begruendung der Methodenwahl (pro Aktie): was wurde warum genutzt/uebersprungen
    profile_notes = []
    if preset == "inflection":
        profile_notes.append("Wachstumsprofil: Forward-Multiples + DCF + Analysten; "
                             "EPV/KBV \u00fcbersprungen (bestrafen Wachstum)")
    elif preset == "cyclical":
        profile_notes.append("Zykliker: mid-cycle-Multiples + Substanz (EPV/KBV); "
                             "DCF \u00fcbersprungen (Peak-Cashflows verzerren)")
    elif preset == "financial":
        profile_notes.append("Finanztitel: KBV/KGV-basiert; EV/EBITDA & DCF nicht sinnvoll")
    else:
        profile_notes.append("Qualit\u00e4tsprofil: breiter Methodenmix inkl. EPV-Substanzanker")
    if "dcf" in weights and "dcf" not in avail:
        profile_notes.append("DCF entf\u00e4llt (kein positiver FCF)")
    if "epv" in weights and "epv" not in avail:
        profile_notes.append("EPV entf\u00e4llt (kein belastbares EBIT)")
    if preset in ("quality", "inflection") and "fwd_pe" in weights and "fwd_pe" not in avail \
            and "fwd_composite" not in avail:
        profile_notes.append("Forward-Multiples entfallen (kein Forward-EPS)")
    if "analyst" not in avail:
        profile_notes.append("kein Analysten-Konsensziel verf\u00fcgbar")

    # Divergenz Modell vs. Analysten transparent machen
    model_vals = [v for k, v in avail.items() if k != "analyst"]
    model_fv = _median(model_vals) if model_vals else None
    anl = avail.get("analyst")
    divergence = (round((anl / model_fv - 1) * 100, 1)
                  if (anl and model_fv) else None)

    fv, capped, lo, hi, spread = None, False, None, None, None
    if avail:
        vals = list(avail.values())
        lo, hi = min(vals), max(vals)
        med = _median(vals)
        spread = round((hi - lo) / med * 100, 0) if med else None
        wsum = sum(weights[k] for k in avail)
        fv = sum(avail[k] * weights[k] for k in avail) / wsum if wsum else med
        price = fund.get("price")
        if fv and price:
            if fv > price * config.FAIR_VALUE_MAX_MULT:
                fv, capped = price * config.FAIR_VALUE_MAX_MULT, True
            elif fv < price * config.FAIR_VALUE_MIN_MULT:
                fv, capped = price * config.FAIR_VALUE_MIN_MULT, True

    mos = config.MARGIN_OF_SAFETY.get(preset, 0.20)
    entry = fv * (1 - mos) if fv else None
    g1 = fund.get("revenue_growth")
    if g1 is None:                                  # nur bei fehlendem Wert ersetzen
        g1 = V["terminal_growth"]                   # (0.0-Wachstum bleibt 0.0)
    g1 = max(min(g1, 0.12), 0.0)
    target_12m = fv * (1 + g1) if fv else None
    price = fund.get("price")
    upside = ((fv / price - 1) * 100) if (fv and price) else None

    # Verlaesslichkeit: gekappte, stark streuende oder duenn belegte Werte sind unsicher
    n_methods = len(avail)
    reliable = bool(fv) and (not capped) and n_methods >= 2 and (spread is None or spread <= 80)
    if n_methods >= 3 and not capped and (spread or 0) <= 50:
        confidence = "hoch"
    elif n_methods >= 2 and not capped and (spread or 0) <= 80:
        confidence = "mittel"
    else:
        confidence = "niedrig"

    return {
        "ticker": fund.get("ticker"),
        "price": price,
        "methods": {k: round(v, 2) for k, v in avail.items()},
        "n_methods": n_methods,
        "fair_value": round(fv, 2) if fv else None,
        "fair_value_capped": capped,
        "model_fair_value": round(model_fv, 2) if model_fv else None,
        "analyst_target": round(anl, 2) if anl else None,
        "analyst_count": fund.get("analyst_count"),
        "model_vs_analyst_pct": divergence,
        "method_profile": " \u00b7 ".join(profile_notes),
        "confidence": confidence,
        "reliable": reliable,
        "range_low": round(lo, 2) if lo else None,
        "range_high": round(hi, 2) if hi else None,
        "spread_pct": spread,
        "target_12m": round(target_12m, 2) if target_12m else None,
        "entry_price": round(entry, 2) if entry else None,
        "margin_of_safety": mos,
        "upside_pct": round(upside, 1) if upside is not None else None,
        "reverse_dcf_implied_growth": reverse_dcf_implied_growth(fund),
        "wacc": round(wacc(fund.get("beta"), fund.get("market_cap"), fund.get("total_debt")), 4),
    }
