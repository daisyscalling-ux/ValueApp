"""
config.py — zentrale Konfiguration: Schwellen, Gewichte, Presets, API-Keys.
Alles hier ist bewusst anpassbar. Werte sind Startpunkte, keine Wahrheiten.
"""
from __future__ import annotations
import os

# ---------------------------------------------------------------------------
# API-Keys (optional). Per Umgebungsvariable setzen, z.B.:
#   export FINNHUB_API_KEY="..."   /   export FMP_API_KEY="..."
# Ohne Keys läuft alles über yfinance (kostenlos, aber begrenzt).
#
# Datenquellen-Kombination je Kennzahl:
#   1) yfinance  (Basis/Taxonomie, kein Key)
#   2) Finnhub   (Kreuzprüfung Kurs/Marktkap./KGV/KBV; Key vorhanden)
#   3) FMP       (4. Quelle: echter Konsens bei Margen/ROE/Wachstum; KOSTENLOSER
#                 Key nötig -> https://site.financialmodelingprep.com/developer/docs
#                 dann:  export FMP_API_KEY="dein_key"). Nur in der Einzelanalyse
#                 aktiv (deep), um das Gratis-Tageslimit (~250 Calls) zu schonen.
#   4) Stooq/EZB (schlüsselfreie Absicherung für Kurshistorie & Wechselkurse)
# ---------------------------------------------------------------------------
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "d8tpv3pr01qhcnk5g5k0d8tpv3pr01qhcnk5g5kg")
FMP_API_KEY = os.getenv("FMP_API_KEY", "EdKxdl3ePaj2DxycU4AyhVWJwVfvl8F5")
ALPHAVANTAGE_API_KEY = os.getenv("ALPHAVANTAGE_API_KEY", "")
# Tiingo: saubere Kurse + verlaessliche Waehrung (EOD + US-Intraday via IEX).
# Nur Preis/Waehrung - KEINE Fundamentaldaten (im Gratis-Tarif nicht enthalten).
TIINGO_API_KEY = os.getenv("TIINGO_API_KEY", "")

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

# Typische KGV-Referenz je Sektor (grobe Median-Werte fuer den Peer-Vergleich).
# Bewusst konservativ; dienen als Orientierung, nicht als exakte Wahrheit.
SECTOR_PE = {
    "Technology": 26, "Communication Services": 18, "Consumer Cyclical": 20,
    "Consumer Defensive": 21, "Healthcare": 19, "Financial Services": 12,
    "Industrials": 19, "Energy": 11, "Basic Materials": 13, "Utilities": 17,
    "Real Estate": 30, "_default": 18,
}

# Sicherheits-Deckel: Fair Value darf max. dieses Vielfache / Bruchteil des
# aktuellen Kurses sein (faengt entgleiste Einzelmethoden ab).
FAIR_VALUE_MAX_MULT = 3.0
FAIR_VALUE_MIN_MULT = 0.3
