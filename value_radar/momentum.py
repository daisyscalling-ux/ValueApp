"""
momentum.py — Momentum-Bewertung fuer den gleichnamigen Tab.

Was Momentum ist und was nicht:
    Momentum ist der am besten belegte Faktor der Kapitalmarktforschung
    (Jegadeesh/Titman 1993 und viele Repliken): Titel, die zuletzt stark
    liefen, laufen im Schnitt noch einige Monate weiter. ABER es ist auch
    der gefaehrlichste Faktor - er kehrt sich abrupt um ("Momentum-Crash",
    z.B. 2009), gerade in Wendephasen des Marktes. Ein hoher Score heisst
    "starker Trend, viel Aufmerksamkeit" - NICHT "wird weiter steigen".

Datenehrlichkeit - drei Dinge, die wir NICHT wirklich messen:
    - "Interesse" im Sinne von Suchvolumen/Social Media haben wir nicht.
      Ersatz: relatives Handelsvolumen + Analysten-Abdeckung. Das ist
      Markt-Aufmerksamkeit, nicht Publikums-Interesse.
    - Kaeufer-/Verkaeufer-Ueberlegenheit messen wir ueber OBV (Volumen an
      Auf- vs. Ab-Tagen) - ein Proxy, kein Blick ins Orderbuch.
    - Der Branchenvergleich braucht Peer-Kurse; fehlen sie, entfaellt der
      Baustein und der Score wird aus den uebrigen gebildet (transparent
      ausgewiesen).

Der Score ist bewusst 0-100 und additiv aus benannten Bausteinen, damit in
der Trefferbilanz nachvollziehbar bleibt, WARUM ein Titel oben stand.
"""
from __future__ import annotations

try:
    import providers
except Exception:                                   # pragma: no cover
    providers = None


# Schwellen zentral, damit sie an einer Stelle justierbar sind.
RSI_UEBERHITZT = 85.0          # darueber: kurzfristige Umkehr wahrscheinlich
RSI_ZU_KALT = 45.0            # darunter: (noch) kein Momentum
MIN_VOLUMEN_FAKTOR = 0.5     # relatives Volumen darunter -> zu illiquide


def _pct(a, b):
    try:
        return (float(a) / float(b) - 1.0) * 100.0
    except Exception:
        return None


def bausteine(ticker: str, f: dict, hist=None, branchen_median_6m=None) -> dict:
    """Alle Momentum-Rohwerte fuer einen Titel sammeln.

    'f' sind die Fundamentaldaten (fuer Sektor, Analysten, 52W).
    'branchen_median_6m' ist die 6M-Performance-Mitte der Branche (optional).
    Rueckgabe: dict mit Rohwerten + 'teilscores' + 'score' + 'ampel'.
    """
    if providers is None:
        return {}
    mom = {}
    try:
        m = providers.get_momentum_snapshot(ticker) or {}
    except Exception:
        m = {}
    try:
        tech = providers.get_technicals(ticker) or {}
    except Exception:
        tech = {}

    ch_1m = m.get("ch_1m")
    ch_6m = m.get("ch_6m")
    ch_1y = m.get("ch_1y")
    rsi = m.get("rsi") or tech.get("rsi")
    above200 = m.get("above_sma200")
    sma_gap = m.get("sma200_gap")
    obv = tech.get("obv_trend")
    sma50 = tech.get("sma50")
    sma200 = tech.get("sma200")
    preis = f.get("price")
    hoch52 = f.get("52w_high")

    # 12-1-Momentum: Jahresrendite ohne den letzten Monat (Forschungsstandard,
    # weil der juengste Monat zur kurzfristigen Umkehr neigt).
    mom_12_1 = None
    if ch_1y is not None and ch_1m is not None:
        # additive Naeherung reicht fuer die Rangordnung
        mom_12_1 = round(ch_1y - ch_1m, 1)

    # Abstand zum 52-Wochen-Hoch (0 = am Hoch, negativ = darunter)
    zu_hoch = _pct(preis, hoch52) if (preis and hoch52) else None

    # Relatives Volumen (Aufmerksamkeit) - aus der Kurshistorie, falls da
    rel_vol = None
    try:
        h = hist if hist is not None else providers.get_price_history(
            ticker, period="6mo", interval="1d")
        if h is not None and not getattr(h, "empty", True) and "Volume" in h.columns:
            v = h["Volume"].dropna()
            if len(v) >= 20:
                schnitt = float(v.tail(60).mean()) or 1.0
                heute = float(v.tail(5).mean())          # 5-Tage gegen 60-Tage
                rel_vol = round(heute / schnitt, 2) if schnitt else None
    except Exception:
        pass

    # Branchenvergleich: schlaegt der Titel den Branchen-Median auf 6M?
    rel_staerke = None
    if ch_6m is not None and branchen_median_6m is not None:
        rel_staerke = round(ch_6m - branchen_median_6m, 1)

    analysten = f.get("analyst_count")

    # ---------------- Teilscores (jeweils 0..max) ----------------
    ts = {}

    # 1) Trendstaerke (12-1-Momentum) - Kern, max 30
    if mom_12_1 is not None:
        ts["Trend (12-1)"] = max(0, min(30, round((mom_12_1 + 10) / 60 * 30)))
    # 2) Relative Staerke zur Branche - max 20
    if rel_staerke is not None:
        ts["Relative Staerke"] = max(0, min(20, round((rel_staerke + 10) / 30 * 20)))
    elif ch_6m is not None:
        # ohne Peers: 6M-Absolutperformance ersatzweise, aber niedriger gewichtet
        ts["6M-Performance"] = max(0, min(12, round((ch_6m + 5) / 40 * 12)))
    # 3) Naehe zum 52W-Hoch - max 15
    if zu_hoch is not None:
        # 0 % (am Hoch) = 15 Punkte, -25 % = 0
        ts["Naehe 52W-Hoch"] = max(0, min(15, round((zu_hoch + 25) / 25 * 15)))
    # 4) Kaeufer-/Verkaeufer-Ueberlegenheit (OBV) - max 15
    if obv == "up":
        ts["Kaeufer-Uebergewicht (OBV)"] = 15
    elif obv == "flat":
        ts["Kaeufer-Uebergewicht (OBV)"] = 7
    elif obv == "down":
        ts["Kaeufer-Uebergewicht (OBV)"] = 0
    # 5) Trendqualitaet (ueber SMA200 und SMA50>SMA200) - max 10
    if above200:
        q = 6
        if sma50 and sma200 and sma50 > sma200:
            q += 4
        ts["Trendqualitaet"] = q
    elif above200 is False:
        ts["Trendqualitaet"] = 0
    # 6) Aufmerksamkeit (relatives Volumen) - max 10
    if rel_vol is not None:
        ts["Aufmerksamkeit (Volumen)"] = max(0, min(10, round((rel_vol - 0.7) / 1.3 * 10)))

    score = sum(ts.values())

    # ---------------- Warnungen / Abzuege ----------------
    warnungen = []
    if rsi is not None and rsi >= RSI_UEBERHITZT:
        warnungen.append(f"RSI {rsi:.0f} - ueberhitzt, kurzfristige Umkehr moeglich")
        score = max(0, score - 10)
    if rsi is not None and rsi < RSI_ZU_KALT:
        warnungen.append(f"RSI {rsi:.0f} - (noch) kein Momentum")
    if rel_vol is not None and rel_vol < MIN_VOLUMEN_FAKTOR:
        warnungen.append("Handelsvolumen unter dem Schnitt - schwaches Interesse")
    if zu_hoch is not None and zu_hoch < -30:
        warnungen.append(f"{abs(zu_hoch):.0f} % unter 52W-Hoch - kein Hoch-Momentum")
    if not analysten:
        warnungen.append("kaum Analysten-Abdeckung - duenn beobachtet")

    score = max(0, min(100, round(score)))
    ampel = ("gruen" if score >= 65 else
             "gelb" if score >= 45 else "rot")

    return {
        "ticker": ticker,
        "name": (f.get("name") or "")[:40],
        "score": score,
        "ampel": ampel,
        "teilscores": ts,
        "warnungen": warnungen,
        # Rohwerte fuer die Anzeige
        "ch_1m": ch_1m, "ch_6m": ch_6m, "ch_1y": ch_1y,
        "mom_12_1": mom_12_1, "rsi": rsi, "zu_hoch": zu_hoch,
        "rel_vol": rel_vol, "rel_staerke": rel_staerke, "obv": obv,
        "above_sma200": above200, "sma200_gap": sma_gap,
        "analyst_count": analysten,
        "sektor": f.get("sector"), "industrie": f.get("industry"),
        "price": preis, "_fx": f.get("_fx"),
    }


def branchen_mediane(rows_f: list) -> dict:
    """Aus einer Liste von Fundamentaldaten je Sektor den 6M-Median bilden.

    rows_f: Liste von dicts mit 'sector' und 'ch_6m' (falls schon geladen).
    Fehlt ch_6m, wird der Titel bei der Median-Bildung ausgelassen.
    """
    from collections import defaultdict
    buckets = defaultdict(list)
    for r in rows_f:
        sek = r.get("sector")
        ch = r.get("ch_6m")
        if sek and ch is not None:
            buckets[sek].append(ch)
    out = {}
    for sek, werte in buckets.items():
        werte.sort()
        n = len(werte)
        if n:
            out[sek] = (werte[n // 2] if n % 2 else
                        (werte[n // 2 - 1] + werte[n // 2]) / 2)
    return out
