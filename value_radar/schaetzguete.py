"""
schaetzguete.py - Punkt 5: Wie treffsicher war der Analystenkonsens hier?

Der Analystenkonsens hat in _WEIGHTS 15 % Gewicht - ungeprueft, fuer jeden
Titel gleich. Ob der Konsens fuer diese Aktie historisch treffsicher war,
weiss das Werkzeug bisher nicht, obwohl die Daten frei verfuegbar sind:
providers.get_last_earnings_surprise() liest bereits yf.Ticker().earnings_dates,
wirft aber alles ausser der letzten Ueberraschung weg.

Dieses Modul wertet die volle Reihe aus und leitet daraus zwei Dinge ab:
  - ein Gewicht, mit dem der Konsens gegen eine Trendfortschreibung geblendet
    wird (fuer eps_forward in justified_pe / fwd_pe / hist_pe)
  - eine Bias-Korrektur, wenn der Konsens systematisch zu hoch liegt

Ohne yfinance-Daten faellt alles still auf den Neutralzustand zurueck.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence

import math

#: Median-|Abweichung| -> Score. Linear interpoliert, ausserhalb geklemmt.
_KURVE = [(0.00, 100.0), (0.02, 92.0), (0.04, 80.0), (0.07, 64.0),
          (0.12, 45.0), (0.20, 25.0), (0.40, 10.0)]

#: Untergrenze des Konsensgewichts. Auch ein schwacher Konsens kennt die
#: Guidance des Unternehmens und ist damit nicht wertlos.
GEWICHT_UNTERGRENZE = 0.35

NEUTRAL = {"n": 0, "trefferquote": None, "mittlere_abweichung": None,
           "median_abweichung": None, "groesste_abweichung": None,
           "score": 50.0, "sterne": 3, "konsens_gewicht": 0.60,
           "bias": "neutral", "label": "Keine Daten", "ton": "grau",
           "reihe": []}


def _score(median_abs: float) -> float:
    if not math.isfinite(median_abs):
        return 50.0
    if median_abs <= _KURVE[0][0]:
        return _KURVE[0][1]
    if median_abs >= _KURVE[-1][0]:
        return _KURVE[-1][1]
    for (x0, y0), (x1, y1) in zip(_KURVE, _KURVE[1:]):
        if x0 <= median_abs <= x1:
            return y0 + (y1 - y0) * (median_abs - x0) / (x1 - x0)
    return 50.0


def _median(xs: List[float]) -> float:
    s = sorted(xs)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def auswerten(paare: Sequence[tuple], quartale: int = 12) -> dict:
    """paare: Folge von (schaetzung, berichtet), aeltester Eintrag zuerst."""
    sauber = []
    for est, act in paare or []:
        try:
            est, act = float(est), float(act)
        except (TypeError, ValueError):
            continue
        if not (math.isfinite(est) and math.isfinite(act)) or abs(est) < 1e-6:
            continue
        sauber.append((est, act, (act - est) / abs(est)))
    if not sauber:
        return dict(NEUTRAL)

    sauber = sauber[-quartale:]
    abw = [s[2] for s in sauber]
    median_abs = _median([abs(a) for a in abw])
    mittel = sum(abw) / len(abw)
    score = _score(median_abs)
    sterne = max(1, min(5, int(round(score / 20.0))))
    gewicht = GEWICHT_UNTERGRENZE + (1.0 - GEWICHT_UNTERGRENZE) * score / 100.0

    if mittel > 0.02:
        bias = "konservativ"        # Konsens wird regelmaessig uebertroffen
    elif mittel < -0.02:
        bias = "optimistisch"       # Konsens wird regelmaessig verfehlt
    else:
        bias = "neutral"

    if score >= 85:
        label, ton = "Sehr treffsicher", "gruen"
    elif score >= 70:
        label, ton = "Treffsicher", "gruen"
    elif score >= 50:
        label, ton = "Durchwachsen", "gelb"
    else:
        label, ton = "Unzuverlaessig", "rot"

    return {
        "n": len(sauber),
        "trefferquote": round(sum(1 for a in abw if a > 0) / len(abw), 3),
        "mittlere_abweichung": round(mittel, 4),
        "median_abweichung": round(median_abs, 4),
        "groesste_abweichung": round(max(abs(a) for a in abw), 4),
        "score": round(score, 1),
        "sterne": sterne,
        "konsens_gewicht": round(gewicht, 3),
        "bias": bias,
        "label": label,
        "ton": ton,
        "reihe": [{"schaetzung": e, "berichtet": a, "abweichung": round(d, 4)}
                  for e, a, d in sauber],
    }


def fuer_ticker(ticker: str, quartale: int = 12) -> dict:
    """Liest die EPS-Historie ueber providers.get_eps_history().

    Der Datenzugriff liegt bewusst bei providers - dort sitzen alle anderen
    Quellen auch, inklusive Circuit-Breaker und Fehlerbehandlung. Faellt still
    auf den Neutralzustand zurueck.
    """
    try:
        import providers
        return auswerten(providers.get_eps_history(ticker, quartale), quartale)
    except Exception:
        return dict(NEUTRAL)


# ---------------------------------------------------------------------------
# Anwendung: Konsens gegen Trend blenden
# ---------------------------------------------------------------------------

def _trend(reihe: Sequence[float], schritte: int = 1) -> Optional[float]:
    """Log-lineare Fortschreibung als konsensfreie Gegenprobe."""
    xs = [float(v) for v in (reihe or [])
          if v is not None and math.isfinite(float(v)) and float(v) > 0]
    if len(xs) < 3:
        return None
    n = len(xs)
    ys = [math.log(x) for x in xs]
    mx = (n - 1) / 2.0
    my = sum(ys) / n
    nen = sum((i - mx) ** 2 for i in range(n))
    if not nen:
        return None
    steigung = sum((i - mx) * (ys[i] - my) for i in range(n)) / nen
    achse = my - steigung * mx
    return math.exp(achse + steigung * (n - 1 + schritte))


def geblendetes_eps(konsens_eps: Optional[float], eps_historie: Sequence[float],
                    guete: dict) -> Optional[dict]:
    """Gewichteter Forward-EPS fuer justified_pe / fwd_pe / hist_pe.

    Bei systematisch optimistischem Konsens wird zusaetzlich um die mittlere
    Verfehlung korrigiert, statt den Konsens nur abzuwerten - eine Schaetzung,
    die immer 5 % zu hoch liegt, ist nach der Korrektur brauchbar.
    """
    trend = _trend(eps_historie)
    if konsens_eps is None and trend is None:
        return None
    if konsens_eps is None:
        return {"eps": round(trend, 2), "konsens": None, "trend": round(trend, 2),
                "gewicht": 0.0, "korrigiert": None}
    if trend is None:
        return {"eps": round(konsens_eps, 2), "konsens": round(konsens_eps, 2),
                "trend": None, "gewicht": 1.0, "korrigiert": None}

    w = guete.get("konsens_gewicht") or 0.60
    korr = konsens_eps
    if guete.get("bias") == "optimistisch" and guete.get("mittlere_abweichung"):
        korr = konsens_eps * (1.0 + guete["mittlere_abweichung"])

    return {"eps": round(w * korr + (1 - w) * trend, 2),
            "konsens": round(konsens_eps, 2),
            "korrigiert": round(korr, 2) if korr != konsens_eps else None,
            "trend": round(trend, 2),
            "gewicht": round(w, 3)}


def anwenden_auf_fund(fund: dict, guete: dict,
                      eps_historie: Optional[Sequence[float]] = None) -> Optional[dict]:
    """Setzt eps_forward im fund-Dict auf den geblendeten Wert.

    Veraendert fund IN PLACE und gibt die Herleitung zurueck, damit die
    Einzelanalyse zeigen kann, wie stark der Konsens gestutzt wurde. Wird
    NUR aufgerufen, wenn eine EPS-Historie vorliegt - sonst bleibt alles wie
    bisher.
    """
    if not eps_historie or len(eps_historie) < 3:
        return None
    bl = geblendetes_eps(fund.get("eps_forward"), eps_historie, guete)
    if not bl or not bl.get("eps") or bl["eps"] <= 0:
        return None
    fund["eps_forward_roh"] = fund.get("eps_forward")
    fund["eps_forward"] = bl["eps"]
    return bl
