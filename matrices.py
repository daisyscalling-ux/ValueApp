"""
matrices.py — die zwei eigenen Scoring-Matrizen des Nutzers, automatisch
ausgefuellt und nachvollziehbar.

MATRIX 1 (Setup-Score): 15 Kriterien, je 1-3 Punkte (max 45).
  Klassen: >=36 High Conviction, >=30 Sehr gut, >=24 Watchlist, sonst Ignore.
MATRIX 2 (Gewichteter Score): 0-10 je Kriterium, 4 Kategorien.
  Beitrag = (Summe/Max) * Gewicht * 100. Gesamt 0-100.
  Gewichte: Fundamental Momentum .40, Kapitalqualitaet .30, Sentiment .15, Narrative .15.

Jede Kennzahl wird aus den verfuegbaren Daten erkannt; fehlt etwas, wird neutral
angenommen und im Begruendungstext als "(n/a)" markiert. Alles ist im Dashboard
per Dropdown ueberschreibbar.
"""
from __future__ import annotations
import valuation


# ---------------------------------------------------------------------------
# Technische Indikatoren
# ---------------------------------------------------------------------------
def _rsi(closes, period=14):
    if closes is None or len(closes) < period + 1:
        return None
    gains, losses = [], []
    for i in range(1, len(closes)):
        d = closes[i] - closes[i - 1]
        gains.append(max(d, 0))
        losses.append(max(-d, 0))
    ag = sum(gains[:period]) / period
    al = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        ag = (ag * (period - 1) + gains[i]) / period
        al = (al * (period - 1) + losses[i]) / period
    if al == 0:
        return 100.0
    rs = ag / al
    return 100 - 100 / (1 + rs)


def _sma(closes, n):
    if closes is None or len(closes) < n:
        return None
    return sum(closes[-n:]) / n


# ---------------------------------------------------------------------------
# Signale aus allen Datenquellen ableiten
# ---------------------------------------------------------------------------
def build_signals(fund, hist_df, analyst, extras):
    """hist_df: DataFrame mit Spalten Close/Volume (taeglich). extras: get_signal_extras."""
    s = {}
    closes, vols = [], []
    if hist_df is not None and not getattr(hist_df, "empty", True):
        try:
            closes = [float(x) for x in hist_df["Close"].dropna().tolist()]
            if "Volume" in hist_df.columns:
                vols = [float(x) for x in hist_df["Volume"].fillna(0).tolist()]
        except Exception:
            pass
    price = fund.get("price") or (closes[-1] if closes else None)

    # --- Fundamentaldaten
    s["fcf_positive"] = (fund.get("free_cashflow") or 0) > 0
    s["net_debt_ebitda"] = fund.get("net_debt_ebitda")
    s["roe"] = fund.get("roe")
    s["wacc"] = valuation.wacc(fund.get("beta"), fund.get("market_cap"), fund.get("total_debt"))
    s["revenue_growth"] = fund.get("revenue_growth")
    s["ev_ebitda"] = fund.get("ev_ebitda")
    s["sector"] = fund.get("sector")

    # --- Mehrjahres-Reihen (neueste zuerst)
    rev, gp, ni, fcf = (extras.get(k) for k in ("revenue", "gross_profit", "net_income", "fcf"))
    # Umsatz-YoY + Beschleunigung
    if rev and len(rev) >= 2 and rev[1]:
        s["rev_yoy"] = rev[0] / rev[1] - 1
        if len(rev) >= 3 and rev[2]:
            s["rev_yoy_prev"] = rev[1] / rev[2] - 1
    # Bruttomarge YoY (pp)
    if gp and rev and len(gp) >= 2 and len(rev) >= 2 and rev[0] and rev[1]:
        s["gm_now"] = gp[0] / rev[0]
        s["gm_prev"] = gp[1] / rev[1]
        s["gm_yoy_pp"] = (s["gm_now"] - s["gm_prev"]) * 100
    # FCF-Trend (inkl. "stable", wenn die Reihe in enger Bandbreite liegt)
    if fcf and len(fcf) >= 3 and all(x is not None for x in fcf[:3]):
        rising = fcf[0] > fcf[1] > fcf[2]
        falling = fcf[0] < fcf[1] < fcf[2]
        band = max(abs(x) for x in fcf[:3]) or 1
        stable = (max(fcf[:3]) - min(fcf[:3])) / band < 0.10
        s["fcf_trend"] = ("stable" if stable else
                          "rising" if rising else
                          "falling" if falling else "volatile")
    elif fcf and len(fcf) >= 2 and all(x is not None for x in fcf[:2]):
        s["fcf_trend"] = "rising" if fcf[0] > fcf[1] else "falling"
    # FCF Conversion
    if fcf and ni and fcf[0] is not None and ni[0]:
        s["fcf_conversion"] = fcf[0] / ni[0]

    # --- Earnings / Revisionen
    le = extras.get("last_earnings") or {}
    s["earn_surprise"] = le.get("surprise_pct")
    er = extras.get("eps_rev") or {}
    s["eps_up"], s["eps_down"] = er.get("up"), er.get("down")

    # --- Analysten
    rt = extras.get("rec_trend") or {}
    s["rec_now"], s["rec_prev"] = rt.get("net_now"), rt.get("net_prev")
    s["analyst"] = analyst  # {buy,hold,sell}

    # --- Short Interest
    ss, ssp = extras.get("shares_short"), extras.get("shares_short_prior")
    if ss is not None and ssp:
        s["short_trend"] = ("rising_fast" if ss > ssp * 1.15 else
                            "rising" if ss > ssp * 1.05 else
                            "falling" if ss < ssp * 0.95 else "flat")

    # --- Technik
    s["rsi"] = _rsi(closes)
    s["rsi_prev5"] = _rsi(closes[:-5]) if closes and len(closes) > 25 else None
    s["sma20"], s["sma50"], s["sma200"] = _sma(closes, 20), _sma(closes, 50), _sma(closes, 200)
    s["price"] = price
    if price and s["sma200"]:
        s["sma200_dist"] = (price / s["sma200"] - 1) * 100
    if closes and len(closes) >= 40:
        recent_low = min(closes[-20:])
        prior_low = min(closes[-40:-20])
        if recent_low > prior_low * 1.02:
            s["chart"] = "higher_low"
        elif recent_low < prior_low * 0.98:
            s["chart"] = "lower_lows"
        else:
            s["chart"] = "sideways"
    # Volumen: Close/Volume koennen unterschiedlich lang sein (dropna vs fillna)
    # -> am Ende ausrichten, sonst verschieben sich die Tage gegeneinander.
    if vols and closes:
        L = min(len(vols), len(closes))
        vv, cc = vols[-L:], closes[-L:]
        if L >= 21:
            up_v = sum(vv[i] for i in range(-20, 0) if cc[i] >= cc[i - 1])
            dn_v = sum(vv[i] for i in range(-20, 0) if cc[i] < cc[i - 1])
            if up_v > dn_v * 1.15:
                s["volume"] = "accumulation"
            elif dn_v > up_v * 1.15:
                s["volume"] = "distribution"
            else:
                s["volume"] = "neutral"

    s["catalyst_score"] = fund.get("_catalyst_score", 50)
    return s


# ---------------------------------------------------------------------------
# MATRIX 1 — Spezifikation (Levels: index 0->1Pkt, 1->2Pkt, 2->3Pkt)
# ---------------------------------------------------------------------------
M1_SPEC = [
    ("fcf", "Free Cashflow (TTM)", ["Negativ", "Positiv, aber volatil", "Positiv & steigend"], "Yahoo Finance \u2192 Cash Flow \u2192 FCF"),
    ("nde", "Net Debt / EBITDA", ["> 3,5", "2 \u2013 3,5", "< 2"], "Balance Sheet & Income Statement"),
    ("roic", "ROIC > WACC", ["ROIC < WACC", "ROIC \u2248 WACC", "ROIC > WACC"], "gurufocus.com (ROE als Proxy)"),
    ("rev", "Umsatztrend (TTM vs. Vorjahr)", ["R\u00fcckl\u00e4ufig", "Stagnierend (\u00b13 %)", "Wachsend (> 3 %)"], "Total Revenue"),
    ("gm", "Bruttomarge (YoY)", ["Sinkend", "Stabil", "Steigend"], "Macrotrends \u2192 Gross Margin"),
    ("eps_rev", "EPS Revision 3 Monate", ["Abw\u00e4rts", "Unver\u00e4ndert", "Aufw\u00e4rts"], "Earnings Estimate"),
    ("earn", "Letzte Earnings", ["Miss", "Inline", "Beat"], "Earnings per Share"),
    ("guid", "Guidance", ["Gesenkt", "Best\u00e4tigt", "Angehoben / positiv"], "Suche nach Guidance (manuell)"),
    ("short", "Short Interest", ["Steigend", "Seitw\u00e4rts", "Fallend"], "finviz \u2192 Short Interest"),
    ("analyst", "Analystentrend", ["Downgrades", "Stabil", "Upgrades / Kursziele \u2191"], "Analyst Recommendation"),
    ("rsi", "RSI (14)", ["> 70 oder < 25", "45 \u2013 55", "30 \u2013 45 & steigend"], "RSI 14"),
    ("gd", "Lage zu GDs (20 / 50)", ["Unter beiden", "\u00dcber 20, unter 50", "\u00dcber 20 & 50"], "SMA 20/50"),
    ("sma200", "SMA200-Distanz", ["> 15 % darunter", "5\u201315 % darunter", "< 5 % / leicht dar\u00fcber"], "SMA 200"),
    ("vol", "Volumenstruktur", ["Abverkauf dominiert", "Neutral", "Akkumulation sichtbar"], "Volumen-Spikes"),
    ("chart", "Chartstruktur", ["Lower Lows", "Seitw\u00e4rts", "Higher Low"], "Swing-Tiefs"),
]


def auto_m1(s):
    """-> {key: (idx 0..2, begruendung)}"""
    r = {}

    def na(msg="keine Daten"):
        return (1, f"(n/a) {msg} \u2013 neutral")

    # FCF
    if not s.get("fcf_positive"):
        r["fcf"] = (0, "FCF negativ")
    elif s.get("fcf_trend") == "rising":
        r["fcf"] = (2, "FCF positiv & steigend")
    else:
        r["fcf"] = (1, "FCF positiv, aber nicht klar steigend")
    # Net Debt/EBITDA
    nde = s.get("net_debt_ebitda")
    r["nde"] = na() if nde is None else (
        (0, f"Net Debt/EBITDA {nde:.1f} (> 3,5)") if nde > 3.5 else
        (2, f"Net Debt/EBITDA {nde:.1f} (< 2)") if nde < 2 else
        (1, f"Net Debt/EBITDA {nde:.1f} (2\u20133,5)"))
    # ROIC vs WACC (ROE als Proxy) - ACHTUNG: ROE wird durch Verschuldung aufgeblaeht.
    # Ein hoch verschuldetes Unternehmen zeigt hohen ROE bei mieser Kapitalrendite.
    # Daher: kein voller Punkt, wenn der Hebel hoch ist (Net Debt/EBITDA > 3).
    roe, w = s.get("roe"), s.get("wacc")
    _lev = s.get("net_debt_ebitda")
    if roe is None or w is None:
        r["roic"] = na("ROE/WACC fehlt")
    else:
        sp = (roe - w) * 100
        _high_lev = _lev is not None and _lev > 3.0
        if sp > 1 and _high_lev:
            r["roic"] = (1, f"ROE {roe*100:.1f}% > WACC, aber Hebel hoch "
                            f"(Net Debt/EBITDA {_lev:.1f}) \u2013 ROE geschmeichelt")
        else:
            r["roic"] = (2, f"ROE {roe*100:.1f}% > WACC {w*100:.1f}%") if sp > 1 else \
                        (0, f"ROE {roe*100:.1f}% < WACC {w*100:.1f}%") if sp < -1 else \
                        (1, f"ROE \u2248 WACC ({sp:+.1f}pp)")
    # Umsatztrend
    g = s.get("rev_yoy")
    if g is None:
        g = s.get("revenue_growth")
    r["rev"] = na("kein Umsatztrend") if g is None else (
        (2, f"Umsatz +{g*100:.1f}% YoY") if g > 0.03 else
        (0, f"Umsatz {g*100:.1f}% YoY (r\u00fcckl\u00e4ufig)") if g < -0.03 else
        (1, f"Umsatz {g*100:.1f}% YoY (stagnierend)"))
    # Bruttomarge YoY
    gm = s.get("gm_yoy_pp")
    r["gm"] = na("keine Margenreihe") if gm is None else (
        (2, f"Bruttomarge {gm:+.1f}pp (steigend)") if gm > 0.3 else
        (0, f"Bruttomarge {gm:+.1f}pp (sinkend)") if gm < -0.3 else
        (1, f"Bruttomarge {gm:+.1f}pp (stabil)"))
    # EPS Revision
    up, dn = s.get("eps_up"), s.get("eps_down")
    if up is None and dn is None:
        r["eps_rev"] = na("keine Revisionsdaten")
    else:
        up, dn = up or 0, dn or 0
        r["eps_rev"] = (2, f"Revisionen {up}\u2191/{dn}\u2193 (aufw\u00e4rts)") if up > dn else \
                       (0, f"Revisionen {up}\u2191/{dn}\u2193 (abw\u00e4rts)") if dn > up else \
                       (1, f"Revisionen {up}\u2191/{dn}\u2193 (unver\u00e4ndert)")
    # Letzte Earnings
    sur = s.get("earn_surprise")
    r["earn"] = na("kein Surprise") if sur is None else (
        (2, f"Beat (+{sur:.1f}%)") if sur > 1 else
        (0, f"Miss ({sur:.1f}%)") if sur < -1 else
        (1, f"Inline ({sur:+.1f}%)"))
    # Guidance (nicht automatisierbar)
    r["guid"] = (1, "(n/a) Guidance manuell pr\u00fcfen \u2013 neutral")
    # Short Interest
    st = s.get("short_trend")
    r["short"] = na("kein Short-Trend") if st is None else (
        (2, "Short Interest fallend") if st == "falling" else
        (0, "Short Interest steigend") if st in ("rising", "rising_fast") else
        (1, "Short Interest seitw\u00e4rts"))
    # Analystentrend
    rn, rp = s.get("rec_now"), s.get("rec_prev")
    if rn is not None and rp is not None:
        r["analyst"] = (2, f"Analysten verbessert ({rp}\u2192{rn})") if rn > rp else \
                       (0, f"Analysten verschlechtert ({rp}\u2192{rn})") if rn < rp else \
                       (1, f"Analysten stabil ({rn})")
    else:
        an = s.get("analyst") or {}
        b, se = an.get("buy", 0), an.get("sell", 0)
        r["analyst"] = (2, f"{b} Buy vs {se} Sell") if b > se * 1.5 else \
                       (0, f"{b} Buy vs {se} Sell") if se > b else \
                       (1, f"{b} Buy / {se} Sell (stabil)") if an else na("keine Ratings")
    # RSI (Spez.: volle Punktzahl nur bei 30-45 UND steigend)
    rsi = s.get("rsi")
    rsi_prev = s.get("rsi_prev5")
    if rsi is None:
        r["rsi"] = na("RSI fehlt")
    elif rsi > 70 or rsi < 25:
        r["rsi"] = (0, f"RSI {rsi:.0f} (\u00fcberkauft/-verkauft)")
    elif 30 <= rsi <= 45:
        rising = rsi_prev is None or rsi >= rsi_prev
        r["rsi"] = ((2, f"RSI {rsi:.0f} (30\u201345, steigend)") if rising
                    else (1, f"RSI {rsi:.0f} (30\u201345, aber fallend)"))
    elif 45 < rsi <= 55:
        r["rsi"] = (1, f"RSI {rsi:.0f} (45\u201355)")
    else:
        r["rsi"] = (1, f"RSI {rsi:.0f}")
    # Lage zu GD20/50
    p, m20, m50 = s.get("price"), s.get("sma20"), s.get("sma50")
    if p and m20 and m50:
        if p > m20 and p > m50:
            r["gd"] = (2, "\u00fcber GD20 & GD50")
        elif p < m20 and p < m50:
            r["gd"] = (0, "unter GD20 & GD50")
        elif p > m20:
            r["gd"] = (1, "\u00fcber GD20, unter GD50")
        else:
            r["gd"] = (1, "unter GD20, \u00fcber GD50 (gemischt)")
    else:
        r["gd"] = na("GDs fehlen")
    # SMA200-Distanz
    d = s.get("sma200_dist")
    if d is None:
        r["sma200"] = na("SMA200 fehlt")
    elif d < -15:
        r["sma200"] = (0, f"{d:.0f}% unter SMA200 (> 15%)")
    elif -15 <= d <= -5:
        r["sma200"] = (1, f"{d:.0f}% unter SMA200 (5\u201315%)")
    elif d > 15:
        r["sma200"] = (1, f"{d:.0f}% \u00fcber SMA200 (Trend evtl. verpasst \u2192 max 2P)")
    else:
        r["sma200"] = (2, f"{d:+.0f}% zu SMA200 (nah)")
    # Volumen
    v = s.get("volume")
    r["vol"] = na("kein Volumensignal") if v is None else (
        (2, "Akkumulation sichtbar") if v == "accumulation" else
        (0, "Abverkauf dominiert") if v == "distribution" else
        (1, "Volumen neutral"))
    # Chartstruktur
    c = s.get("chart")
    r["chart"] = na("keine Struktur") if c is None else (
        (2, "Higher Low") if c == "higher_low" else
        (0, "Lower Lows") if c == "lower_lows" else
        (1, "Seitw\u00e4rts"))
    return r


def classify_m1(total):
    if total >= 36:
        return "High Conviction Setup"
    if total >= 30:
        return "Sehr gute Aktie"
    if total >= 24:
        return "Watchlist"
    return "Ignore"


# ---------------------------------------------------------------------------
# MATRIX 2 — Spezifikation (Buckets idx 0..3 -> Repr.-Score)
# ---------------------------------------------------------------------------
def _has_data(reason) -> bool:
    """Kriterien ohne Daten sind mit '(n/a)' markiert."""
    return not str(reason).startswith("(n/a)")


def auto_m1_coverage(s):
    """(vorhanden, moeglich) - wie viele Kriterien echte Daten haben."""
    auto = auto_m1(s)
    keys = [k for k, _n, _l, _w in M1_SPEC]
    have = [k for k in keys if k in auto and _has_data(auto[k][1])]
    return len(have), len(keys)


def auto_m1_total(s, min_coverage=0.6):
    """Matrix-1-Punkte (Skala 0-45), NUR ueber Kriterien mit echten Daten.

    FRUEHER: Fehlende Daten zaehlten als 'neutral' = 2 von 3 Punkten. Eine Aktie
    ganz OHNE Kennzahlen bekam so 29/45 - knapp an der Pflichtschwelle 30 vorbei.
    Das erzeugte Scheinsicherheit. JETZT: fehlende Kriterien werden ausgeklammert,
    das Ergebnis auf die 45er-Skala hochgerechnet. Ist die Datenlage zu duenn
    (< 60 % der Kriterien), gibt es KEINEN Score (None) statt eines erfundenen."""
    auto = auto_m1(s)
    keys = [k for k, _n, _l, _w in M1_SPEC]
    have = [(k, auto[k]) for k in keys if k in auto and _has_data(auto[k][1])]
    if not keys or len(have) / len(keys) < min_coverage:
        return None
    pts = sum(idx + 1 for _k, (idx, _r) in have)        # 1..3 je Kriterium
    return round(pts / (3 * len(have)) * 45)


M2_BUCKET_SCORE = [1, 4, 7, 10]   # 0-2 / 3-5 / 6-8 / 9-10

M2_CATS = [
    ("Fundamental Momentum", 0.40, [
        ("eps_rev", "EPS Revision 3M", ["negativ (> -5%)", "leicht negativ/flat", "leicht positiv (0..+5%)", "stark positiv (> +5%)"]),
        ("rev_acc", "Umsatztrend YoY", ["verlangsamt deutlich", "leicht r\u00fcckl\u00e4ufig", "stabil/leicht steigend", "klar beschleunigend"]),
        ("gm", "Bruttomarge YoY", ["stark r\u00fcckl\u00e4ufig (< -3%)", "leicht r\u00fcckl\u00e4ufig (-3..0)", "leicht steigend (0..+2)", "stark steigend (> +2)"]),
        ("earn", "Letzte Earnings", ["Miss + schwach", "Miss/schwach", "Beat leicht", "klarer Beat + Qualit\u00e4t"]),
        ("guid", "Guidance", ["gesenkt", "unsicher", "best\u00e4tigt", "angehoben"]),
    ]),
    ("Kapitalqualit\u00e4t", 0.30, [
        ("roic", "ROIC > WACC", ["ROIC < WACC", "ROIC = WACC", "ROIC leicht > WACC", "ROIC deutlich > WACC"]),
        ("fcf_trend", "FCF Trend", ["fallend", "volatil", "stabil", "wachsend"]),
        ("fcf_conv", "FCF Conversion", ["< 50%", "50\u201380%", "80\u2013100%", "> 100%"]),
        ("nde", "Net Debt / EBITDA", ["> 4", "3\u20134", "1\u20133", "< 1"]),
    ]),
    ("Sentiment", 0.15, [
        ("analyst", "Analystentrend", ["mehr Downgrades", "gemischt", "leicht positiv", "klare Upgrades"]),
        ("short", "Short Interest", ["stark steigend", "leicht steigend", "stabil", "fallend"]),
    ]),
    ("Narrative", 0.15, [
        ("catalyst", "Katalysator (<6M)", ["kein klarer", "unsicher", "wahrscheinlich", "konkret + terminiert"]),
        ("rerating", "Re-Rating Potenzial", ["kaum", "begrenzt", "moderat", "hoch"]),
        ("story", "Story", ["komplex", "teilweise klar", "verst\u00e4ndlich", "extrem klar"]),
    ]),
]


def auto_m2(s):
    """-> {key: (bucket idx 0..3, begruendung)}"""
    r = {}

    def na(msg="keine Daten"):
        return (1, f"(n/a) {msg} \u2013 neutral")

    # EPS Revision
    up, dn = s.get("eps_up"), s.get("eps_down")
    if up is None and dn is None:
        r["eps_rev"] = na("keine Revisionen")
    else:
        up, dn = up or 0, dn or 0
        r["eps_rev"] = (3, f"{up}\u2191/{dn}\u2193 stark positiv") if (dn == 0 and up > 0) or up >= 2 * max(dn, 1) else \
                       (2, f"{up}\u2191/{dn}\u2193 leicht positiv") if up > dn else \
                       (0, f"{up}\u2191/{dn}\u2193 negativ") if dn > up * 1.5 else \
                       (1, f"{up}\u2191/{dn}\u2193 flat")
    # Umsatz-Beschleunigung
    now, prev = s.get("rev_yoy"), s.get("rev_yoy_prev")
    if now is None:
        r["rev_acc"] = na("kein Umsatztrend")
    elif prev is None:
        r["rev_acc"] = (2, f"Umsatz {now*100:.1f}% YoY") if now > 0 else (1, f"Umsatz {now*100:.1f}% YoY")
    else:
        r["rev_acc"] = (3, f"beschleunigt ({prev*100:.0f}%\u2192{now*100:.0f}%)") if now > prev + 0.02 else \
                       (0, f"verlangsamt deutlich ({prev*100:.0f}%\u2192{now*100:.0f}%)") if now < prev - 0.05 else \
                       (1, f"leicht r\u00fcckl\u00e4ufig ({prev*100:.0f}%\u2192{now*100:.0f}%)") if now < prev else \
                       (2, f"stabil/leicht steigend ({now*100:.0f}%)")
    # Bruttomarge
    gm = s.get("gm_yoy_pp")
    r["gm"] = na("keine Margenreihe") if gm is None else (
        (3, f"{gm:+.1f}pp stark steigend") if gm > 2 else
        (2, f"{gm:+.1f}pp leicht steigend") if gm >= 0 else
        (1, f"{gm:+.1f}pp leicht r\u00fcckl\u00e4ufig") if gm > -3 else
        (0, f"{gm:+.1f}pp stark r\u00fcckl\u00e4ufig"))
    # Earnings
    sur = s.get("earn_surprise")
    r["earn"] = na("kein Surprise") if sur is None else (
        (3, f"klarer Beat (+{sur:.1f}%)") if sur > 5 else
        (2, f"Beat leicht (+{sur:.1f}%)") if sur > 0 else
        (1, f"Miss/schwach ({sur:.1f}%)") if sur > -5 else
        (0, f"Miss schwach ({sur:.1f}%)"))
    # Guidance (manuell)
    r["guid"] = (1, "(n/a) Guidance manuell pr\u00fcfen \u2013 'unsicher' angenommen")
    # ROIC vs WACC (ROE als Proxy) - Hebel-Korrektur wie in Matrix 1:
    # hohe Verschuldung blaeht den ROE auf -> kein Spitzenwert.
    roe, w = s.get("roe"), s.get("wacc")
    _lev2 = s.get("net_debt_ebitda")
    if roe is None or w is None:
        r["roic"] = na("ROE/WACC fehlt")
    else:
        sp = (roe - w) * 100
        _hl = _lev2 is not None and _lev2 > 3.0
        if sp > 0.5 and _hl:
            r["roic"] = (1, f"ROE \u2212 WACC {sp:+.1f}pp, aber Hebel hoch "
                            f"(Net Debt/EBITDA {_lev2:.1f}) \u2013 ROE geschmeichelt")
        else:
            r["roic"] = (3, f"ROE \u2212 WACC {sp:+.1f}pp (deutlich)") if sp > 3 else \
                        (2, f"ROE \u2212 WACC {sp:+.1f}pp (leicht)") if sp > 0.5 else \
                        (1, f"ROE \u2248 WACC ({sp:+.1f}pp)") if sp > -0.5 else \
                        (0, f"ROE < WACC ({sp:+.1f}pp)")
    # FCF Trend
    ft = s.get("fcf_trend")
    r["fcf_trend"] = na("keine FCF-Reihe") if ft is None else (
        (3, "FCF wachsend") if ft == "rising" else
        (0, "FCF fallend") if ft == "falling" else
        (2, "FCF stabil") if ft == "stable" else
        (1, "FCF volatil"))
    # FCF Conversion
    conv = s.get("fcf_conversion")
    r["fcf_conv"] = na("keine Conversion") if conv is None else (
        (3, f"FCF/NI {conv*100:.0f}% (> 100%)") if conv > 1 else
        (2, f"FCF/NI {conv*100:.0f}% (80\u2013100%)") if conv > 0.8 else
        (1, f"FCF/NI {conv*100:.0f}% (50\u201380%)") if conv > 0.5 else
        (0, f"FCF/NI {conv*100:.0f}% (< 50%)"))
    # Net Debt/EBITDA
    nde = s.get("net_debt_ebitda")
    r["nde"] = na() if nde is None else (
        (3, f"{nde:.1f} (< 1)") if nde < 1 else
        (2, f"{nde:.1f} (1\u20133)") if nde < 3 else
        (1, f"{nde:.1f} (3\u20134)") if nde < 4 else
        (0, f"{nde:.1f} (> 4)"))
    # Analystentrend
    rn, rp = s.get("rec_now"), s.get("rec_prev")
    if rn is not None and rp is not None:
        r["analyst"] = (3, f"klare Upgrades ({rp}\u2192{rn})") if rn > rp else \
                       (0, f"mehr Downgrades ({rp}\u2192{rn})") if rn < rp else \
                       (2, f"leicht positiv ({rn})") if rn > 0 else (1, f"gemischt ({rn})")
    else:
        an = s.get("analyst") or {}
        b, se = an.get("buy", 0), an.get("sell", 0)
        r["analyst"] = (3, f"{b} Buy vs {se} Sell") if b > se * 2 else \
                       (2, f"{b} Buy vs {se} Sell") if b > se else \
                       (1, f"{b} Buy / {se} Sell") if an else na("keine Ratings")
    # Short Interest
    st = s.get("short_trend")
    r["short"] = na("kein Short-Trend") if st is None else (
        (3, "fallend") if st == "falling" else
        (2, "stabil") if st == "flat" else
        (0, "stark steigend") if st == "rising_fast" else
        (1, "leicht steigend"))
    # Katalysator
    cs = s.get("catalyst_score", 50)
    r["catalyst"] = (3, f"Catalyst-Score {cs:.0f} (hoch)") if cs > 70 else \
                    (2, f"Catalyst-Score {cs:.0f}") if cs > 55 else \
                    (1, f"Catalyst-Score {cs:.0f}") if cs > 40 else \
                    (0, f"Catalyst-Score {cs:.0f} (schwach)")
    # Re-Rating: aktuelles EV/EBITDA vs Sektor-Default
    ev = s.get("ev_ebitda")
    sec_def = valuation.config.SECTOR_EV_EBITDA.get(s.get("sector"),
                                                    valuation.config.SECTOR_EV_EBITDA["_default"])
    if ev and ev > 0:
        ratio = ev / sec_def
        r["rerating"] = (3, f"EV/EBITDA {ev:.1f} \u226a Sektor {sec_def} (hoch)") if ratio < 0.7 else \
                        (2, f"EV/EBITDA {ev:.1f} < Sektor {sec_def} (moderat)") if ratio < 0.95 else \
                        (1, f"EV/EBITDA {ev:.1f} \u2248 Sektor {sec_def} (begrenzt)") if ratio < 1.2 else \
                        (0, f"EV/EBITDA {ev:.1f} > Sektor {sec_def} (kaum)")
    else:
        r["rerating"] = na("kein EV/EBITDA")
    # Story (manuell)
    r["story"] = (1, "(n/a) Story manuell pr\u00fcfen \u2013 'teilweise klar' angenommen")
    return r


# ---------------------------------------------------------------------------
# Bewertungs-Zusammenfassung (Matrix-1-Stil) ueber die bestehende Engine
# ---------------------------------------------------------------------------
def valuation_summary(fund, preset="quality"):
    v = valuation.fair_value(fund, None, preset=preset)
    meth = v.get("methods", {})
    pe = meth.get("justified_pe")
    ev = meth.get("ev_ebitda")
    dcf = meth.get("dcf")
    entry_no_dcf = (pe + ev) / 2 if (pe and ev) else (pe or ev)
    parts = [x for x in (pe, ev, dcf) if x]
    entry_dcf = sum(parts) / len(parts) if parts else None
    return {
        "forward_multiple_pe": pe, "ev_ebitda_model": ev, "dcf_model": dcf,
        "fair_value": v.get("fair_value"),
        "entry_no_dcf": entry_no_dcf,
        "entry_no_dcf_mos": {m: entry_no_dcf * (1 - m) if entry_no_dcf else None
                             for m in (0.10, 0.15, 0.20)},
        "entry_dcf": entry_dcf,
        "entry_dcf_mos": {m: entry_dcf * (1 - m) if entry_dcf else None
                          for m in (0.10, 0.15, 0.20)},
    }


def auto_m2_coverage(s):
    auto = auto_m2(s)
    keys = [k for _c, _w, crits in M2_CATS for k, _n, _b in crits]
    have = [k for k in keys if k in auto and _has_data(auto[k][1])]
    return len(have), len(keys)


def auto_m2_total(s, min_coverage=0.6):
    """Matrix-2-Score (0-100), NUR ueber Kriterien mit echten Daten.
    Kategorien ohne jedes Datum fallen raus, ihre Gewichte werden auf die
    verbleibenden verteilt. Zu duenne Datenlage -> None statt Fantasiewert."""
    auto = auto_m2(s)
    n_have, n_all = auto_m2_coverage(s)
    if not n_all or n_have / n_all < min_coverage:
        return None
    total, wsum = 0.0, 0.0
    for _cat, weight, crits in M2_CATS:
        avail = [k for k, _n, _b in crits
                 if k in auto and _has_data(auto[k][1])]
        if not avail:
            continue                                   # Kategorie ohne Daten: raus
        raw = sum(M2_BUCKET_SCORE[auto[k][0]] for k in avail)
        total += raw / (len(avail) * 10) * weight * 100
        wsum += weight
    if wsum <= 0:
        return None
    return round(total / wsum, 1)                       # auf vorhandene Gewichte normiert
