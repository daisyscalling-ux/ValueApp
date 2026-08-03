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
    "fallback": "Konsens-/Median-Sch\u00e4tzung (Rueckfall)",
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


def _dcf_parametrisiert(fund, preset, g_shift, r_shift) -> Optional[float]:
    """Wie dcf_two_stage, aber mit verschobenem Anfangswachstum (g_shift) und
    Diskontsatz (r_shift). Basis fuer die Bear/Base/Bull-Szenarien - die groesste
    Bewertungsunsicherheit steckt genau in diesen zwei Annahmen (Damodaran:
    'die groesste Intangible ist zukuenftiges Wachstum'). Statt einer
    Punktschaetzung zeigt das eine ehrliche Bandbreite."""
    if preset == "cyclical":
        return None
    fcf, shares = fund.get("free_cashflow"), fund.get("shares_out")
    if not fcf or not shares or fcf <= 0:
        return None
    years = max(int(V.get("projection_years", 10)), 2)
    g_term = V["terminal_growth"]
    g1 = fund.get("revenue_growth")
    if g1 is None:
        g1 = fund.get("earnings_growth") or 0.06
    cap = 0.25 if preset == "inflection" else 0.16
    g1 = max(min(g1, cap), -0.03)
    # Szenario-Verschiebung des Wachstums, danach erneut hart deckeln, damit
    # das Bull-Szenario nicht ins Unrealistische laeuft.
    g1 = max(min(g1 + g_shift, cap + 0.05), -0.06)
    r = wacc(fund.get("beta"), fund.get("market_cap"), fund.get("total_debt"))
    r = r + r_shift
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


def szenario_werte(fund, preset="quality") -> Optional[dict]:
    """Bear / Base / Bull als ehrliche Bandbreite statt einer Punktschaetzung.
    Die Verschiebung des Wachstums skaliert mit dem erwarteten Wachstum selbst:
    schneller wachsende Firmen sind unsicherer (Damodaran), also breitere
    Spanne. Der Diskontsatz wird fix verschoben (Risiko-Neubewertung).
    Gibt None zurueck, wenn der DCF fuer diesen Titel nicht traegt (z.B.
    zyklisch oder negativer Free Cashflow) - dann gibt es bewusst keine
    Scheingenauigkeit."""
    base = dcf_two_stage(fund, preset)
    if base is None:
        return None
    # Wachstums-Unsicherheit: mindestens 3 Pp., mehr bei hoeherem Wachstum.
    g = fund.get("revenue_growth")
    if g is None:
        g = fund.get("earnings_growth") or 0.06
    g_unsicher = max(0.03, abs(g) * 0.5)     # z.B. g=20% -> +/-10 Pp.
    bear = _dcf_parametrisiert(fund, preset, g_shift=-g_unsicher, r_shift=+0.015)
    bull = _dcf_parametrisiert(fund, preset, g_shift=+g_unsicher, r_shift=-0.010)
    if bear is None or bull is None:
        return None
    lo, hi = min(bear, base, bull), max(bear, base, bull)
    price = fund.get("price")
    return {
        "bear": round(bear, 2),
        "base": round(base, 2),
        "bull": round(bull, 2),
        "spanne_pct": round((hi - lo) / base * 100, 0) if base else None,
        "preis": price,
        "kurs_position": (round((price - lo) / (hi - lo) * 100, 0)
                          if price and hi > lo else None),
    }
def multiple_pb(fund, preset="quality") -> Optional[float]:
    bvps = fund.get("book_value_ps")
    # Fallback: Buchwert je Aktie aus Kurs und KBV rekonstruieren, wenn das
    # direkte Feld fehlt (bei manchen Banken wie JPM/Citi liefert die Quelle
    # book_value_ps nicht, aber pb schon). Ohne diesen Fallback bekamen genau
    # diese Titel keinen Fair Value, weil bei Finanzwerten pb die Hauptmethode
    # ist.
    if (not bvps or bvps <= 0):
        _price, _pb = fund.get("price"), fund.get("pb")
        if _price and _pb and _pb > 0:
            bvps = _price / _pb
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
    """EBIT-Schaetzung: operative Marge x Umsatz.

    FRUEHER wurde der Umsatz IMMER aus MarketCap/KUV hergeleitet. Ist das
    KUV verzerrt (z.B. weil die Quelle es mit einem Pence-Kurs gegen
    Pfund-Umsaetze rechnet), wird der Umsatz um Groessenordnungen falsch -
    und der EPV-Wert entgleist (BP.L: 1792 statt ~5 je Aktie).
    Jetzt: echtes Umsatzfeld bevorzugen, KUV nur als Rueckfall, und das
    Ergebnis gegen den Umsatz auf Plausibilitaet pruefen."""
    om = fund.get("operating_margin")
    rev = fund.get("revenue")
    mc, ps = fund.get("market_cap"), fund.get("ps")

    if not (rev and rev > 0) and (mc and ps and ps > 0):
        derived = mc / ps                      # Rueckfall: Umsatz aus KUV
        # Grober Realitaetscheck: Umsatz zwischen 1 % und 100x der Marktkap.
        if 0.01 * mc <= derived <= 100 * mc:
            rev = derived

    if om and om > 0 and rev and rev > 0:
        return om * rev
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
# Ausgeduennt auf die 3 etabliertesten Kernmethoden je Aktientyp + Analyst
# als Anker (~15%). Weniger, dafuer die verlaesslichsten Methoden - das macht
# den Fair Value robuster und nachvollziehbarer. Der Analyst-Konsens bleibt
# als marktbasierter Stabilisator drin, aber mit reduziertem Gewicht, damit
# der Fair Value staerker von den Fundamentaldaten getragen wird (und damit
# unabhaengiger vom Markt - wichtig, um ihn spaeter GEGEN den Markt zu messen).
_WEIGHTS = {
    # Quality: DCF (Ertragskraft) + faires KGV + EV/EBITDA
    "quality":    {"dcf": .30, "justified_pe": .30, "ev_ebitda": .25, "analyst": .15},
    # Inflection: Forward-Multiples + DCF (Zukunftssicht fuer Wachstum/Turnaround)
    "inflection": {"fwd_pe": .30, "fwd_composite": .25, "dcf": .30, "analyst": .15},
    # Cyclical: mid-cycle-Multiple + Substanz (Buchwert) + normalisierte Ertragskraft
    "cyclical":   {"ev_ebitda": .35, "pb": .25, "epv": .25, "analyst": .15},
    # Financial: KBV (Bank-Standard) + faires KGV + Forward-KGV
    "financial":  {"pb": .35, "justified_pe": .30, "fwd_pe": .20, "analyst": .15},
}


def eigenes_ziel(fund, fair_value, preset="quality", regime_ampel=None,
                 pe_perzentil=None, analyst_target=None):
    """Eigenes, ausgewogenes 12-Monats-Kursziel - der 'eigene Analyst'.

    Projiziert den FAIR VALUE 12 Monate voraus, mit drei transparenten,
    datenbasierten Anpassungen. Ausgewogen = bester Schaetzwert, keine
    kuenstliche Marge nach oben oder unten. Gibt neben dem Ziel eine
    vollstaendige Herleitung zurueck, damit nachvollziehbar bleibt, WIE es
    entstand und wie es zum Analystenkonsens steht.

    Bewusst KEINE Auftragsbestaende/News (stehen nicht in den strukturierten
    Daten) - nur was das Tool belastbar weiss: Wachstum, Qualitaet, Bewertungs-
    historie, Marktregime.

    Rueckgabe: {ziel, upside_pct, herleitung: [...], vs_analyst, basis}
    """
    if not fair_value or fair_value <= 0:
        return None
    schritte = []
    ziel = float(fair_value)
    schritte.append(f"Basis: Fair Value {fair_value:.2f}")

    # --- 1) Wachstums-Projektion, qualitaetsgewichtet ---
    g = fund.get("revenue_growth")
    if g is None:
        g = fund.get("earnings_growth")
    if g is None:
        g = 0.0
    g = max(min(g, 0.25), -0.10)          # roh auf [-10%, +25%] begrenzen

    # Qualitaet bestimmen (0..1): hohe Qualitaet -> Wachstum zaehlt voll
    roic = fund.get("roic")
    opm = fund.get("operating_margin")
    q_faktor = 0.6                         # neutraler Default
    if roic is not None:
        # ROIC 5% -> 0.4, 15% -> 0.85, 25%+ -> 1.0
        q_faktor = max(0.4, min(1.0, 0.4 + (roic - 0.05) * 3.0))
    elif opm is not None:
        q_faktor = max(0.4, min(1.0, 0.4 + opm * 2.0))

    g_eff = g * q_faktor
    g_eff = max(min(g_eff, 0.12), -0.10)   # Deckel gegen Fantasie: max +12%
    ziel_nach_g = ziel * (1 + g_eff)
    schritte.append(
        f"Wachstum {g*100:+.1f}% \u00d7 Qualitaet {q_faktor:.2f} "
        f"= {g_eff*100:+.1f}% wirksam \u2192 {ziel_nach_g:.2f}")
    ziel = ziel_nach_g

    # --- 2) Bewertungs-Rueckkehr (mean reversion ueber KGV-Perzentil) ---
    if pe_perzentil is not None:
        # 80.+ Perzentil (teuer) -> bis -6% daempfen; 20- (guenstig) -> bis +6%
        if pe_perzentil >= 80:
            adj = -0.06 * ((pe_perzentil - 80) / 20.0 + 0.5)
        elif pe_perzentil <= 20:
            adj = 0.06 * ((20 - pe_perzentil) / 20.0 + 0.5)
        else:
            adj = 0.0
        adj = max(min(adj, 0.06), -0.06)
        if abs(adj) >= 0.005:
            ziel_nach_b = ziel * (1 + adj)
            lage = "historisch teuer" if adj < 0 else "historisch guenstig"
            schritte.append(
                f"Bewertungs-Ruckkehr ({lage}, KGV-Perzentil "
                f"{pe_perzentil}) \u2192 {adj*100:+.1f}% \u2192 {ziel_nach_b:.2f}")
            ziel = ziel_nach_b

    # --- 3) Marktregime-Daempfung (klein, max -5%) ---
    if regime_ampel == "rot":
        ziel_nach_r = ziel * 0.95
        schritte.append(f"Marktregime rot \u2192 -5% Vorsicht \u2192 {ziel_nach_r:.2f}")
        ziel = ziel_nach_r
    elif regime_ampel == "gelb":
        ziel_nach_r = ziel * 0.98
        schritte.append(f"Marktregime gelb \u2192 -2% \u2192 {ziel_nach_r:.2f}")
        ziel = ziel_nach_r

    ziel = round(ziel, 2)
    price = fund.get("price")
    upside = round((ziel / price - 1) * 100, 1) if price else None

    # Vergleich zum Analystenkonsens
    vs_analyst = None
    if analyst_target and analyst_target > 0:
        vs_analyst = round((ziel / analyst_target - 1) * 100, 1)

    return {"ziel": ziel, "upside_pct": upside, "herleitung": schritte,
            "vs_analyst": vs_analyst, "basis": round(float(fair_value), 2)}


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
    price = fund.get("price")

    # -- Robuste Methodenauswahl (verhindert die >1000%-Divergenzen) ------------
    # 1) Verfuegbare, positive Methoden im Playbook.
    raw = {k: v for k, v in methods.items() if v and v > 0 and k in weights}

    # 2) Plausibilitaets-Filter gegen den Kurs: Ein einzelner Fair Value, der
    #    <0.25x oder >4x Kurs impliziert, stammt fast immer aus einer fuer diese
    #    Aktie ungeeigneten Methode (neg. EBITDA, Blasen-KGV, DCF ohne FCF). Raus.
    def _plausible(v):
        return True if not price else (0.25 * price <= v <= 4.0 * price)
    sane = {k: v for k, v in raw.items() if _plausible(v)}

    # 3) Ausreisser gegen den Median der plausiblen Methoden entfernen: nur was
    #    im Band [Median/2, Median*2] liegt, bildet den "Core". So kann eine
    #    einzelne stark abweichende Methode das Ergebnis nicht mehr verzerren.
    if len(sane) >= 3:
        med0 = _median(list(sane.values()))
        core = {k: v for k, v in sane.items()
                if med0 and (med0 / 2.0) <= v <= (med0 * 2.0)}
        if len(core) < 2:
            core = dict(sane)
    else:
        core = dict(sane)

    # 4) Analysten-Konsens als marktbasierten Anker IMMER einbeziehen (wenn
    #    plausibel) - stabilisiert gerade schwer bewertbare Titel.
    anl_raw = methods.get("analyst")
    anl_ok = bool(anl_raw and anl_raw > 0 and _plausible(anl_raw))
    if anl_ok:
        core["analyst"] = anl_raw

    # 5) Letzter Rueckfall, falls alles gefiltert wurde: Analystenziel, sonst
    #    der (gegen den Kurs geklammerte) Median aller Rohwerte -> nie "kein Wert".
    used_fallback = False
    if not core:
        fb = anl_raw if (anl_raw and anl_raw > 0) else _median(list(raw.values()))
        if fb and price:
            fb = max(min(fb, 2.0 * price), 0.5 * price)
        if fb:
            core = {"fallback": fb}
            used_fallback = True

    # 6) Anzeige: die (bis zu) 3 Methoden, die dem Ergebnis am naechsten liegen -
    #    sie erklaeren den Fair Value und wirken konsistent (statt 3x nach Gewicht).
    avail = dict(core)

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

    # Divergenz Modell vs. Analysten transparent machen (Core ohne Analyst)
    model_vals = [v for k, v in core.items() if k not in ("analyst", "fallback")]
    model_fv = _median(model_vals) if model_vals else None
    anl = core.get("analyst") or (anl_raw if anl_ok else None)
    divergence = (round((anl / model_fv - 1) * 100, 1)
                  if (anl and model_fv) else None)

    fv, capped, lo, hi, spread = None, False, None, None, None
    if core:
        vals = list(core.values())
        lo, hi = min(vals), max(vals)
        med = _median(vals)
        spread = round((hi - lo) / med * 100, 0) if med else None
        # Gewichteter Schnitt der Core-Methoden (Playbook-Gewichte, renormalisiert;
        # unbekannte Keys wie 'fallback' erhalten ein neutrales Gewicht).
        wsum = sum(weights.get(k, 0.15) for k in core)
        fv = (sum(core[k] * weights.get(k, 0.15) for k in core) / wsum) if wsum else med
        if fv and price:                            # letzter Sicherheits-Deckel
            if fv > price * config.FAIR_VALUE_MAX_MULT:
                fv, capped = price * config.FAIR_VALUE_MAX_MULT, True
            elif fv < price * config.FAIR_VALUE_MIN_MULT:
                fv, capped = price * config.FAIR_VALUE_MIN_MULT, True

    # Anzeige auf die 3 dem Ergebnis naechsten Methoden reduzieren (repraesentativ)
    if fv and len(avail) > 3:
        near = sorted(avail.items(), key=lambda kv: abs(kv[1] - fv))[:3]
        avail = dict(near)

    mos = config.MARGIN_OF_SAFETY.get(preset, 0.20)
    entry = fv * (1 - mos) if fv else None
    g1 = fund.get("revenue_growth")
    if g1 is None:                                  # nur bei fehlendem Wert ersetzen
        g1 = V["terminal_growth"]                   # (0.0-Wachstum bleibt 0.0)
    g1 = max(min(g1, 0.12), 0.0)
    target_12m = fv * (1 + g1) if fv else None
    price = fund.get("price")
    upside = ((fv / price - 1) * 100) if (fv and price) else None

    # Verlaesslichkeit auf Basis des bereinigten Core (Ausreisser sind schon raus,
    # daher ist die Streuung aussagekraeftig). Ein plausibler Analysten-Anker hebt
    # die Verlaesslichkeit auf mind. "mittel" - so erreichen deutlich mehr Titel
    # eine belastbare Angabe statt "niedrig/kein Wert".
    n_core = len([k for k in core if k != "fallback"])
    has_anchor = "analyst" in core
    sp = spread if spread is not None else 999
    if used_fallback or n_core == 0:
        confidence, reliable = "niedrig", False
    elif n_core >= 3 and sp <= 35:
        confidence, reliable = "hoch", True
    elif n_core >= 2 and sp <= 60:
        confidence, reliable = "mittel", True
    elif n_core == 1 and has_anchor:               # nur Analysten-Anker -> brauchbar
        confidence, reliable = "mittel", True
    elif n_core >= 2 and sp <= 90:                 # noch vertretbare Streuung
        confidence, reliable = "mittel", True
    else:                                          # echte, grosse Uneinigkeit -> ehrlich
        confidence, reliable = "niedrig", False
    if capped and confidence == "hoch":
        confidence = "mittel"
    n_methods = len(avail)

    return {
        "ticker": fund.get("ticker"),
        "price": price,
        "methods": {k: round(v, 2) for k, v in avail.items()},
        "n_methods": n_methods,
        "fair_value": round(fv, 2) if fv else None,
        "fair_value_capped": capped,
        # Notbehelf-Kennzeichen: TRUE heisst, dass KEINE Bewertungsmethode
        # ein plausibles Ergebnis lieferte. Der angezeigte Wert ist dann nur
        # der gegen den Kurs geklammerte Median der Rohwerte - also faktisch
        # der halbe oder doppelte Kurs. Das MUSS sichtbar sein, sonst haelt
        # man eine Notbremse fuer eine Bewertung.
        "used_fallback": used_fallback,
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
        "szenarien": szenario_werte(fund, preset),
    }


def analyst_spread(fund) -> Optional[dict]:
    """Wie uneinig sind die Analysten? Eigenes Feld, kein Eingriff in die Rechnung.

    Der Mittelwert allein taeuscht Praezision vor. Bei GM lagen im Juli 2026
    Kursziele von 60 USD (Wells Fargo, Underweight) bis 131 USD (Citigroup,
    Buy) vor - Faktor 2,2 bei derselben Firma und identischer Faktenlage.
    Der Mittelwert von ~95 USD ist dann kein Konsens, sondern ein Kompromiss
    zwischen zwei unvereinbaren Lagern.

    Rueckgabe: mean/low/high/n, Spannweite in Prozent des Mittelwerts,
    eine Einstufung und ein Vertrauensfaktor 0.4-1.0, den der Aufrufer
    verwenden KANN - die Kernrechnung bleibt unangetastet."""
    mean = fund.get("target_mean")
    low, high = fund.get("target_low"), fund.get("target_high")
    n = fund.get("analyst_count")
    if not mean or mean <= 0:
        return None
    out = {"mean": round(float(mean), 2),
           "low": round(float(low), 2) if low else None,
           "high": round(float(high), 2) if high else None,
           "n": int(n) if n else None}
    if not low or not high or high <= low:
        out.update({"spanne_pct": None, "einstufung": "keine Spannweite verfügbar",
                    "vertrauen": 1.0})
        return out
    spanne = (high - low) / mean * 100
    out["spanne_pct"] = round(spanne, 1)
    out["faktor"] = round(high / low, 2) if low > 0 else None
    if spanne < 30:
        out["einstufung"] = "Analysten weitgehend einig"
        out["vertrauen"] = 1.0
    elif spanne < 50:
        out["einstufung"] = "normale Streuung"
        out["vertrauen"] = 0.85
    elif spanne < 80:
        out["einstufung"] = "deutlich uneinig – Mittelwert wenig aussagekräftig"
        out["vertrauen"] = 0.6
    else:
        out["einstufung"] = ("stark gespalten – der Mittelwert ist ein Kompromiss "
                             "zwischen unvereinbaren Lagern")
        out["vertrauen"] = 0.4
    return out


def datenaktualitaet(fund, naechster_termin_tage=None) -> dict:
    """Wie frisch sind die Zahlen, auf denen die Bewertung beruht?

    Eigenes Feld, keine Korrektur. Ein Fair Value auf zwei Nachkommastellen
    suggeriert Genauigkeit - wenn das Unternehmen aber HEUTE meldet, rechnet
    er mit ueberholten Zahlen. Das gehoert sichtbar gemacht, nicht
    stillschweigend weggerechnet."""
    out = {"stufe": "normal", "hinweis": "", "termin_tage": naechster_termin_tage}
    t = naechster_termin_tage
    if t is None:
        out["hinweis"] = "kein Quartalstermin bekannt"
        return out
    if t <= 1:
        out["stufe"] = "kritisch"
        out["hinweis"] = ("meldet heute oder morgen – die Bewertung beruht auf "
                          "Zahlen, die gleich überholt sind")
    elif t <= 7:
        out["stufe"] = "achtung"
        out["hinweis"] = f"meldet in {t} Tagen – Zahlen ändern sich bald"
    elif t <= 21:
        out["stufe"] = "hinweis"
        out["hinweis"] = f"meldet in {t} Tagen"
    else:
        out["hinweis"] = f"nächster Termin in {t} Tagen"
    return out
