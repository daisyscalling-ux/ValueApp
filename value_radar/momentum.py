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

__version__ = "2026.09.25"   # 12-1 multiplikativ, Vola, Sektorbereinigung

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


def bausteine(ticker: str, f: dict, hist=None, branchen_median_6m=None,
              branchen_median_12_1=None) -> dict:
    """Alle Momentum-Rohwerte fuer einen Titel sammeln.

    'f' sind die Fundamentaldaten (fuer Sektor, Analysten, 52W).
    'branchen_median_6m' ist die 6M-Performance-Mitte der Branche (optional).
    'branchen_median_12_1' dito fuer das 12-1-Momentum - damit wird der
    Trendscore gegen den Sektor bereinigt statt absolut gemessen.
    Rueckgabe: dict mit Rohwerten + 'teilscores' + 'score' + 'ampel'.
    """
    if providers is None:
        return {}
    mom = {}
    try:
        m = providers.get_screen_extras(ticker) or {}
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
    # MULTIPLIKATIV, nicht additiv.
    #
    # Vorher: ch_1y - ch_1m. Der Fehler waechst mit der Bewegung - also genau
    # bei den Titeln, die eine Momentum-Rangliste anfuehren sollen:
    #   +150 % Jahr / +20 % Monat  ->  additiv 130 %, richtig 108 %  (22 Pp.)
    #   + 60 % Jahr / + 5 % Monat  ->  additiv  55 %, richtig  52 %  ( 3 Pp.)
    # Bei einer Rangordnung nach genau dieser Groesse ist das kein Detail.
    mom_12_1 = None
    if ch_1y is not None and ch_1m is not None and ch_1m > -99:
        mom_12_1 = round(((1 + ch_1y / 100.0) / (1 + ch_1m / 100.0) - 1) * 100, 1)

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

    # VOLATILITAET und risikoadjustiertes Momentum.
    #
    # Der Modul-Docstring beschreibt die Gefahr korrekt: Momentum ohne
    # Risikoskalierung ist die Variante, die 2009 kollabiert ist. Behandelt
    # wurde sie bisher nicht - zwei Titel mit je 60 % Jahresrendite bekamen
    # dieselbe Punktzahl, egal ob bei 25 % oder 70 % Schwankung.
    #
    # Kennzahl ist die Rendite je Einheit Schwankung (Information Ratio).
    vola = None
    try:
        h2 = hist if hist is not None else providers.get_price_history(
            ticker, period="1y", interval="1d")
        if h2 is not None and not getattr(h2, "empty", True) and "Close" in h2.columns:
            c = h2["Close"].dropna()
            if len(c) >= 60:
                r = c.pct_change().dropna()
                vola = round(float(r.std()) * (252 ** 0.5) * 100, 1)
    except Exception:
        pass

    mom_risikoadj = None
    if mom_12_1 is not None and vola and vola > 5:
        mom_risikoadj = round(mom_12_1 / vola, 2)

    # Branchenvergleich: schlaegt der Titel den Branchen-Median auf 6M?
    rel_staerke = None
    if ch_6m is not None and branchen_median_6m is not None:
        rel_staerke = round(ch_6m - branchen_median_6m, 1)

    analysten = f.get("analyst_count")

    # ---------------- Teilscores (jeweils 0..max) ----------------
    ts = {}

    # 1) Trendstaerke - Kern, max 30
    #
    # Bevorzugt risikoadjustiert und gegen den Sektor bereinigt. Ohne
    # Sektorbereinigung besteht die Liste in Boomphasen zu vier Fuenfteln aus
    # einer Branche - das ist dann keine Titelauswahl mehr, sondern eine
    # Branchenwette mit Extraschritten.
    # Beide Korrekturen greifen NACHEINANDER, nicht alternativ. Die erste
    # Fassung hatte ein elif: mit Sektorbereinigung fiel die Risikoadjustierung
    # weg, und zwei Titel mit gleicher Rendite bei 22 % und 70 % Schwankung
    # bekamen wieder dieselbe Punktzahl. Genau der Fehler, der behoben werden
    # sollte.
    _basis_12_1 = mom_12_1
    _bereinigt = False
    if mom_12_1 is not None and branchen_median_12_1 is not None:
        _basis_12_1 = round(mom_12_1 - branchen_median_12_1, 1)
        _bereinigt = True

    if _basis_12_1 is not None:
        # Volatilitaet als DAEMPFUNG, nicht als Divisor.
        #
        # Die Division (Information Ratio) hat einen Vorzeichenfehler: Bei
        # negativem Ueberschuss wird der Wert durch hohe Schwankung WENIGER
        # negativ - ein schlechter, wilder Titel rutscht damit vor einen
        # schlechten, ruhigen. Im Test: -37,6 Pp. bei 22 % Vola ergab -1,71,
        # dieselben -37,6 Pp. bei 70 % Vola ergaben -0,54. Die Rangfolge stand
        # auf dem Kopf.
        #
        # Ein Faktor auf den Rohscore hat dieses Problem nicht: Er macht jeden
        # Titel schlechter, je staerker er schwankt, und laesst die Reihenfolge
        # innerhalb gleicher Schwankung unberuehrt.
        _label = "Trend (12-1 ggü. Sektor)" if _bereinigt else "Trend (12-1)"
        # Skala fuer den Sektorabstand: -50 bis +40 Prozentpunkte. Die erste
        # Fassung (-25 bis +25) drueckte alles unterhalb des Medians auf null -
        # vier von fuenf Testtiteln bekamen denselben Wert und waren nicht mehr
        # unterscheidbar. Ein Rang, der nicht trennt, ist kein Rang.
        _mitte, _spanne = (-50.0, 90.0) if _bereinigt else (-10.0, 60.0)
        _roh = max(0.0, min(30.0, (_basis_12_1 - _mitte) / _spanne * 30))
        if vola and vola > 5:
            # 1,0 bis 30 % Schwankung, linear auf 0,6 bei 80 % und darueber.
            _faktor = max(0.6, min(1.0, 1.0 - (vola - 30.0) / 125.0))
            _label += ", risikoadj."
        else:
            _faktor = 1.0
        ts[_label] = round(_roh * _faktor)
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
    ueberhitzt = bool(rsi is not None and rsi >= RSI_UEBERHITZT)
    if ueberhitzt:
        # Frueher kostete das 10 Punkte. Ein Titel mit 85 Punkten stand damit
        # trotz RSI 92 weit oben - der Abzug hat die Rangfolge kaum bewegt.
        # Ueberhitzung ist aber keine Eigenschaft, die man gegen Trendstaerke
        # aufrechnet: Sie sagt, dass der Einstieg JETZT schlecht ist. Deshalb
        # als eigenes Kennzeichen, das kandidat.gate_pruefen auswertet.
        warnungen.append(f"RSI {rsi:.0f} - ueberhitzt, Einstieg jetzt ungeeignet")
        score = max(0, score - 10)
    if rsi is not None and rsi < RSI_ZU_KALT:
        warnungen.append(f"RSI {rsi:.0f} - (noch) kein Momentum")
    if rel_vol is not None and rel_vol < MIN_VOLUMEN_FAKTOR:
        warnungen.append("Handelsvolumen unter dem Schnitt - schwaches Interesse")
    if zu_hoch is not None and zu_hoch < -30:
        warnungen.append(f"{abs(zu_hoch):.0f} % unter 52W-Hoch - kein Hoch-Momentum")
    if not analysten:
        warnungen.append("kaum Analysten-Abdeckung - duenn beobachtet")
    if vola is not None and vola > 60:
        warnungen.append(f"Schwankung {vola:.0f} % p. a. - die Trendstaerke "
                         f"steht auf duennem Eis")
    if mom_risikoadj is None and mom_12_1 is not None:
        warnungen.append("keine Kurshistorie fuer die Risikoadjustierung - "
                         "Trend nur absolut bewertet")

    score = max(0, min(100, round(score)))
    ampel = ("gruen" if score >= 65 else
             "gelb" if score >= 45 else "rot")

    return {
        "ticker": ticker,
        "name": (f.get("name") or "")[:40],
        "score": score,
        "ampel": ampel,
        "ueberhitzt": ueberhitzt,
        "teilscores": ts,
        "warnungen": warnungen,
        # Rohwerte fuer die Anzeige
        "ch_1m": ch_1m, "ch_6m": ch_6m, "ch_1y": ch_1y,
        "mom_12_1": mom_12_1, "vola": vola, "mom_risikoadj": mom_risikoadj,
        "mom_12_1_vs_sektor": (_basis_12_1 if _bereinigt else None),
        "rsi": rsi, "zu_hoch": zu_hoch,
        "rel_vol": rel_vol, "rel_staerke": rel_staerke, "obv": obv,
        "above_sma200": above200, "sma200_gap": sma_gap,
        "analyst_count": analysten,
        "sektor": f.get("sector"), "industrie": f.get("industry"),
        "price": preis, "_fx": f.get("_fx"),
    }


def branchen_mediane_12_1(rows: list) -> dict:
    """Sektor-Median des 12-1-Momentums.

    Gegenstueck zu branchen_mediane(), aber fuer die Groesse, die im Trendscore
    tatsaechlich zaehlt. rows: Liste aus bausteine()-Ergebnissen oder dicts mit
    'sektor'/'sector' und 'mom_12_1'.
    """
    from collections import defaultdict
    eimer = defaultdict(list)
    for r in rows:
        sek = r.get("sektor") or r.get("sector")
        m = r.get("mom_12_1")
        if sek and m is not None:
            eimer[sek].append(float(m))
    out = {}
    for sek, werte in eimer.items():
        # Unter fuenf Titeln je Sektor ist der Median Rauschen - dann lieber
        # keine Bereinigung als eine falsche.
        if len(werte) < 5:
            continue
        werte.sort()
        n = len(werte)
        out[sek] = (werte[n // 2] if n % 2
                    else (werte[n // 2 - 1] + werte[n // 2]) / 2)
    return out


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
