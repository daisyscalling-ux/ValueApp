"""
config.py — zentrale Konfiguration: Schwellen, Gewichte, Presets, API-Keys.
Alles hier ist bewusst anpassbar. Werte sind Startpunkte, keine Wahrheiten.
"""
from __future__ import annotations
import os


def _load_key(name: str, default: str = "") -> str:
    """Key-Quelle in dieser Reihenfolge:
       1) Umgebungsvariable  2) Streamlit-Secrets (.streamlit/secrets.toml bzw.
       Secrets-UI in der Cloud)  3) Default.
    So liegt NICHTS Sensibles im Code/Repo \u2013 wichtig fuer den Online-Deploy."""
    v = os.environ.get(name)
    if v:
        return v
    try:
        import streamlit as _st           # nur falls verfuegbar
        val = _st.secrets.get(name)        # wirft, wenn keine secrets.toml
        if val:
            return str(val)
    except Exception:
        pass
    return default


# ---------------------------------------------------------------------------
# API-Keys. NICHT im Code hinterlegen \u2013 in .streamlit/secrets.toml (lokal) oder
# in der Streamlit-Cloud unter Settings -> Secrets eintragen. Ohne Keys laeuft
# alles ueber yfinance (kostenlos, aber begrenzt).
#
# Datenquellen-Kombination je Kennzahl:
#   1) yfinance  (Basis/Taxonomie, kein Key)
#   2) Finnhub   (Kreuzpruefung Kurs/Marktkap./KGV/KBV)
#   3) FMP       (4. Quelle: Konsens bei Margen/ROE/Wachstum, hist. Median-KGV;
#                 kostenloser Key -> https://site.financialmodelingprep.com)
#   4) Stooq/EZB (schluesselfreie Absicherung fuer Kurshistorie & Wechselkurse)
# ---------------------------------------------------------------------------
FINNHUB_API_KEY = _load_key("FINNHUB_API_KEY", "")
FMP_API_KEY = _load_key("FMP_API_KEY", "")
ALPHAVANTAGE_API_KEY = _load_key("ALPHAVANTAGE_API_KEY", "")

# ---------------------------------------------------------------------------
# Screening-Schwellen (branchenrelativ denken!). None = Kriterium aus.
# ---------------------------------------------------------------------------
SCREEN_THRESHOLDS = {
    "min_market_cap": 100e6,      # Mindest-Marktkapitalisierung (USD)
    "max_ev_ebitda": 14.0,
    "max_pb": 3.5,
    "min_fcf_yield": 0.04,        # FCF / EV
    "max_peg": 2.0,
    "min_roic": 0.08,
    "max_net_debt_ebitda": 3.5,
    "min_current_ratio": 1.0,
    "min_revenue_growth": 0.0,    # >0 = wachsend
}

# ---------------------------------------------------------------------------
# Scoring: Gewichtspresets je Playbook (müssen je Preset auf 1.0 summieren).
# Kategorien: valuation, quality, growth, health, momentum, catalyst
# ---------------------------------------------------------------------------
SCORE_PRESETS = {
    "quality":    {"valuation": .25, "quality": .25, "growth": .20, "health": .15, "momentum": .10, "catalyst": .05},
    "cyclical":   {"valuation": .30, "quality": .15, "growth": .15, "health": .20, "momentum": .15, "catalyst": .05},
    "inflection": {"valuation": .15, "quality": .20, "growth": .35, "health": .10, "momentum": .15, "catalyst": .05},
    # Banken/Versicherer: EV/EBITDA & Net-Debt/EBITDA sind hier sinnlos (laufen neutral),
    # daher mehr Gewicht auf Bewertung (KBV/KGV) und Rentabilitaet (ROE/ROA).
    "financial":  {"valuation": .30, "quality": .30, "growth": .10, "health": .10, "momentum": .15, "catalyst": .05},
}

# Value-Trap-Strafe (Punkte vom Composite abgezogen, falls Negativ-Screen greift)
VALUE_TRAP_PENALTY = 20.0

# ---------------------------------------------------------------------------
# Bewertungs-Annahmen
# ---------------------------------------------------------------------------
VALUATION = {
    "risk_free_rate": 0.042,      # ~10y Treasury, anpassen
    "equity_risk_premium": 0.050,
    "default_beta": 1.1,
    "tax_rate": 0.21,
    "terminal_growth": 0.025,     # langfristiges Wachstum (<= BIP-Wachstum)
    "projection_years": 10,       # Horizont fuer DCF UND Reverse-DCF (konsistent)
    "high_growth_decay": True,    # g1 linear Richtung g_term abklingen lassen
}

# Margin-of-Safety je Playbook (Einstieg = FairValue * (1 - MoS))
MARGIN_OF_SAFETY = {"quality": 0.18, "cyclical": 0.25, "inflection": 0.25, "financial": 0.20}

# Sektor-Default-Multiples (grobe mid-cycle-Anker, wenn keine Peers vorliegen).
# Yahoo-Sektornamen als Schluessel.
SECTOR_EV_EBITDA = {
    "Technology": 16, "Communication Services": 9, "Consumer Cyclical": 10,
    "Consumer Defensive": 12, "Healthcare": 13, "Financial Services": 10,
    "Industrials": 12, "Energy": 6, "Basic Materials": 7, "Utilities": 10,
    "Real Estate": 16, "_default": 11,
}

# Sicherheits-Deckel: Fair Value darf max. dieses Vielfache / Bruchteil des
# aktuellen Kurses sein (faengt entgleiste Einzelmethoden ab).
FAIR_VALUE_MAX_MULT = 3.0
FAIR_VALUE_MIN_MULT = 0.3
