"""
kennzahlen.py — Finanzkennzahlen einordnen: gut, mittel oder bedenklich.

WAS DAS IST
  Eine Ampel je Kennzahl, mit einer kurzen Begruendung in Klartext. Damit
  laesst sich eine Bilanz lesen, ohne jede Kennzahl auswendig zu kennen.

WAS DAS NICHT IST
  Kein Urteil ueber die Aktie. Eine gruene Bilanz sagt nichts darueber,
  ob der Kurs steigt - sie sagt, dass das Unternehmen finanziell stabil
  aussieht. Beides wird oft verwechselt.

DIE WICHTIGSTE EINSCHRAENKUNG - bitte ernst nehmen:
  Schwellenwerte sind BRANCHENABHAENGIG. Ein Current Ratio von 0,89 ist
  bei Apple unproblematisch (Kunden zahlen sofort, Lieferanten spaeter),
  bei einem Maschinenbauer waere es ein Warnzeichen. Eine Nettomarge von
  4 % ist im Einzelhandel gut und bei Software katastrophal.
  Deshalb: Wo eine Branchenabhaengigkeit besonders stark ist, steht das
  im Hinweistext. Die Ampel ersetzt kein Nachdenken.

EINHEITEN (aus der echten roic-Antwort abgeleitet)
  Margen und Renditen kommen in PROZENT   (gross_margin 46.9 = 46,9 %)
  Verschuldung teils in Prozent           (tot_debt_to_tot_eqy 133.8)
  net_debt_to_ebitda, cur_ratio, quick_ratio sind ROHE Verhaeltnisse
"""
from __future__ import annotations
import re

# ---------------------------------------------------------------------------
# Schwellen. Aufbau je Eintrag:
#   (Anzeigename, Endpunkt-Feld, Einheit, gut_ab, mittel_ab, richtung, Hinweis)
#
# richtung "hoch" = groesser ist besser, "tief" = kleiner ist besser
# Einheit  "pct"  = Wert kommt in Prozent, wird als Prozent angezeigt
#          "roh"  = reines Verhaeltnis (0,89x)
#          "tage" = Tage
# ---------------------------------------------------------------------------

PROFITABILITAET = [
    ("Bruttomarge", "gross_margin", "pct", 40, 20, "hoch",
     "Stark branchenabhängig: Software 70 %+, Handel oft unter 25 %."),
    ("Operative Marge", "oper_margin", "pct", 15, 5, "hoch",
     "Was nach allen operativen Kosten übrig bleibt."),
    ("Nettomarge", "profit_margin", "pct", 10, 3, "hoch",
     "Nach Zinsen und Steuern. Unter 3 % bleibt wenig Puffer."),
    ("EBITDA-Marge", "ebitda_margin", "pct", 20, 8, "hoch",
     "Vor Abschreibungen – bei kapitalintensiven Firmen schmeichelhaft."),
    ("Eigenkapitalrendite", "return_com_eqy", "pct", 15, 8, "hoch",
     "Vorsicht: Aktienrückkäufe verkleinern das Eigenkapital und treiben "
     "diesen Wert nach oben, ohne dass das Geschäft besser wird."),
    ("Gesamtkapitalrendite", "return_on_asset", "pct", 8, 3, "hoch",
     "Schwerer zu schönen als die Eigenkapitalrendite."),
    ("Kapitalrendite (ROIC)", "return_on_inv_capital", "pct", 12, 6, "hoch",
     "Die aussagekräftigste Renditekennzahl: Ertrag auf das eingesetzte "
     "Kapital, unabhängig von der Finanzierung."),
    ("Steuerquote", "eff_tax_rate", "pct", None, None, "info",
     "Nur zur Einordnung. Dauerhaft sehr niedrige Quoten können später "
     "steigen und den Gewinn drücken."),
    ("Ausschüttungsquote", "dvd_payout_ratio", "pct", None, None, "info",
     "Über 80 % ist die Dividende bei einem schwachen Jahr gefährdet."),
]

VERSCHULDUNG = [
    ("Nettoverschuldung / EBITDA", "net_debt_to_ebitda", "roh", 2.0, 4.0, "tief",
     "Wie viele Jahre Bruttoergebnis nötig wären, um die Nettoschulden zu "
     "tilgen. Über 4 wird es eng, wenn die Zinsen steigen."),
    ("Verschuldungsgrad (D/E)", "tot_debt_to_tot_eqy", "pct", 100, 200, "tief",
     "Schulden im Verhältnis zum Eigenkapital. Bei Banken und "
     "Immobilienfirmen sind hohe Werte normal."),
    ("Schulden / Gesamtkapital", "tot_debt_to_tot_cap", "pct", 40, 65, "tief",
     "Anteil der Fremdfinanzierung an der gesamten Kapitalstruktur."),
    ("Gesamtschulden / EBIT", "total_debt_to_ebit", "roh", 3.0, 6.0, "tief",
     "Strenger als die EBITDA-Variante, weil Abschreibungen abgezogen sind."),
    ("Langfr. Schulden / Vermögen", "lt_debt_to_tot_asset", "pct", 25, 45, "tief",
     "Wie viel des Vermögens langfristig fremdfinanziert ist."),
]

LIQUIDITAET = [
    ("Current Ratio", "cur_ratio", "roh", 1.5, 1.0, "hoch",
     "Kurzfristiges Vermögen gegen kurzfristige Schulden. ACHTUNG: Bei "
     "Firmen mit starker Verhandlungsmacht (Apple: 0,89) ist ein Wert "
     "unter 1 unbedenklich – sie kassieren vor Zahlung der Lieferanten."),
    ("Quick Ratio", "quick_ratio", "roh", 1.0, 0.7, "hoch",
     "Wie Current Ratio, aber ohne Vorräte – der strengere Test."),
    ("Cash Ratio", "cash_ratio", "roh", 0.5, 0.2, "hoch",
     "Nur Barmittel gegen kurzfristige Schulden."),
    ("Altman Z-Score", "altman_z_score", "roh", 3.0, 1.8, "hoch",
     "Insolvenzrisiko-Maß. Über 3 gilt als sicher, unter 1,8 als "
     "gefährdet. Für Banken und Versicherungen nicht aussagekräftig."),
    ("Cashflow / Verbindlichkeiten", "cash_flow_to_tot_liab", "pct", 20, 10, "hoch",
     "Wie viel der Schulden das Unternehmen jährlich erwirtschaftet."),
]

KAPITALBINDUNG = [
    ("Forderungslaufzeit", "acct_rcv_days", "tage", 45, 90, "tief",
     "Wie lange Kunden im Schnitt zahlen. Steigt der Wert über Jahre, "
     "können Zahlungsprobleme bei Kunden dahinterstecken."),
    ("Lagerdauer", "invent_days", "tage", 60, 120, "tief",
     "Wie lange Waren im Lager liegen. Im Handel und bei Verderblichem "
     "sind niedrige Werte entscheidend."),
    ("Cash Conversion Cycle", "cash_conversion_cycle", "tage", 30, 90, "tief",
     "Tage zwischen Bezahlung der Lieferanten und Geldeingang vom Kunden. "
     "NEGATIV ist ausgezeichnet – dann finanzieren die Lieferanten das "
     "Geschäft (Apple: −72 Tage)."),
    ("Lagerumschlag", "invent_turn", "roh", 8, 4, "hoch",
     "Wie oft das Lager pro Jahr umgeschlagen wird."),
]

BLOECKE = [
    ("Profitabilität", "profitabilitaet", PROFITABILITAET),
    ("Verschuldung", "verschuldung", VERSCHULDUNG),
    ("Liquidität", "liquiditaet", LIQUIDITAET),
    ("Kapitalbindung", "kapitalbindung", KAPITALBINDUNG),
]


def _num(x):
    try:
        if x is None:
            return None
        v = float(x)
        return v if v == v else None
    except Exception:
        return None


def _ampel(wert, gut, mittel, richtung):
    """gruen / gelb / rot / grau (keine Bewertung moeglich)."""
    if wert is None or richtung == "info" or gut is None:
        return "grau"
    if richtung == "hoch":
        if wert >= gut:
            return "gruen"
        return "gelb" if wert >= mittel else "rot"
    # richtung == "tief"
    if wert <= gut:
        return "gruen"
    return "gelb" if wert <= mittel else "rot"


def bewerte(rohdaten: dict) -> list:
    """rohdaten = Ergebnis von roic.ratios_alle().

    Rueckgabe: Liste von Bloecken mit bewerteten Kennzahlen."""
    out = []
    for titel, schluessel, definitionen in BLOECKE:
        quelle = (rohdaten or {}).get(schluessel) or {}
        zeilen = []
        for name, feld, einheit, gut, mittel, richtung, hinweis in definitionen:
            w = _num(quelle.get(feld))
            if w is None:
                continue
            zeilen.append({
                "name": name,
                "wert": w,
                "einheit": einheit,
                "anzeige": (f"{w:,.1f} %".replace(",", ".") if einheit == "pct"
                            else f"{w:,.0f} T".replace(",", ".") if einheit == "tage"
                            else f"{w:,.2f}".replace(".", ",")),
                "ampel": _ampel(w, gut, mittel, richtung),
                "richtung": richtung,
                "schwelle_gut": gut,
                "schwelle_mittel": mittel,
                "hinweis": hinweis,
            })
        if zeilen:
            out.append({"titel": titel, "zeilen": zeilen})
    return out


def zusammenfassung(bewertet: list) -> dict:
    """Zaehlt die Ampeln - fuer eine Kopfzeile ueber der Tabelle."""
    g = ge = r = 0
    schwach = []
    for block in bewertet or []:
        for z in block["zeilen"]:
            if z["ampel"] == "gruen":
                g += 1
            elif z["ampel"] == "gelb":
                ge += 1
            elif z["ampel"] == "rot":
                r += 1
                schwach.append(f"{z['name']} ({z['anzeige']})")
    gesamt = g + ge + r
    if not gesamt:
        return {"gruen": 0, "gelb": 0, "rot": 0, "urteil": "keine Daten",
                "schwach": []}
    anteil = g / gesamt
    if r == 0 and anteil >= 0.6:
        urteil = "finanziell solide"
    elif r <= 2 and anteil >= 0.4:
        urteil = "überwiegend in Ordnung"
    elif r >= 5:
        urteil = "mehrere Schwachstellen"
    else:
        urteil = "gemischtes Bild"
    return {"gruen": g, "gelb": ge, "rot": r, "gesamt": gesamt,
            "urteil": urteil, "schwach": schwach[:6]}


def trend(reihen: list, feld: str, jahre: int = 5) -> dict | None:
    """Entwicklung einer Kennzahl ueber mehrere Jahre.

    Beantwortet die Frage, die eine Momentaufnahme nicht beantworten kann:
    Wird es besser oder schlechter?"""
    werte = []
    for z in (reihen or [])[:jahre]:
        w = _num(z.get(feld))
        if w is not None:
            werte.append((z.get("fiscal_year") or z.get("jahr"), w))
    if len(werte) < 3:
        return None
    werte.sort(key=lambda x: str(x[0]))
    erst, letzt = werte[0][1], werte[-1][1]
    if erst == 0:
        return None
    aend = (letzt - erst) / abs(erst) * 100
    if aend > 15:
        richtung, wort = "auf", "deutlich verbessert"
    elif aend > 5:
        richtung, wort = "auf", "leicht verbessert"
    elif aend < -15:
        richtung, wort = "ab", "deutlich verschlechtert"
    elif aend < -5:
        richtung, wort = "ab", "leicht verschlechtert"
    else:
        richtung, wort = "flach", "stabil"
    return {"werte": werte, "aenderung_pct": round(aend, 1),
            "richtung": richtung, "wort": wort,
            "von": werte[0][0], "bis": werte[-1][0]}


# ===========================================================================
# EARNINGS-CALL: KERNSTELLEN STATT ZUSAMMENFASSUNG
# ---------------------------------------------------------------------------
# Warum keine echte Zusammenfassung: Dafuer braeuchte es ein Sprachmodell,
# und dessen Ergebnis waere eine Deutung, die wie eine Tatsache aussieht.
# Was hier passiert, ist nachpruefbar: Saetze werden nach Thema sortiert
# und WOERTLICH gezeigt. Die Deutung bleibt beim Leser.
#
# Zusaetzlich getrennt wird der VORTRAG vom FRAGETEIL. Der Vortrag ist
# vorbereitet und klingt fast immer gut. Im Frageteil zeigt sich, woran
# Analysten haken - dort steht das Aufschlussreiche.
# ===========================================================================

THEMEN = [
    ("Ausblick", ("guidance", "outlook", "we expect", "we anticipate",
                  "full year", "next quarter", "fiscal 20", "forecast",
                  "we now see", "raising our", "lowering our")),
    ("Margen & Kosten", ("margin", "cost invest", "pricing", "headwind from cost",
                         "operating leverage", "efficiency", "restructur")),
    ("Nachfrage", ("demand", "orders", "backlog", "bookings", "pipeline",
                   "customer", "volume")),
    ("Risiken", ("headwind", "challenge", "uncertain", "weakness", "decline",
                 "pressure", "slowdown", "softness", "cautious", "risk")),
    ("Kapitalverwendung", ("buyback", "repurchase", "dividend", "capital "
                           "allocation", "capex", "acquisition", "debt")),
]

_FRAGE_MARKER = ("question-and-answer", "question and answer",
                 "q&a session", "we will now begin the question",
                 "first question", "operator:")


def _saetze(text):
    out, akt = [], []
    for teil in text.replace("\n", " ").split(". "):
        t = teil.strip()
        if 40 <= len(t) <= 400:
            out.append(t + ("." if not t.endswith(".") else ""))
        akt = out
    return akt


def teile_transkript(text: str) -> dict:
    """Trennt Vortrag und Frageteil."""
    if not text:
        return {"vortrag": "", "fragen": "", "geteilt": False}
    low = text.lower()
    pos = -1
    for m in _FRAGE_MARKER:
        p = low.find(m)
        if p > len(text) * 0.2:          # nicht schon in der Begruessung
            pos = p if pos < 0 else min(pos, p)
    if pos < 0:
        return {"vortrag": text, "fragen": "", "geteilt": False}
    return {"vortrag": text[:pos], "fragen": text[pos:], "geteilt": True}


def kernstellen(text: str, max_je_thema: int = 4) -> list:
    """Woertliche Fundstellen je Thema - keine Deutung.

    Rueckgabe: [{thema, stellen: [{satz, teil}]}]"""
    if not text:
        return []
    t = teile_transkript(text)
    quellen = [("Vortrag", t["vortrag"])]
    if t["fragen"]:
        quellen.append(("Frageteil", t["fragen"]))

    out = []
    for thema, begriffe in THEMEN:
        stellen, gesehen = [], set()
        for teil_name, teil_text in quellen:
            for s in _saetze(teil_text):
                sl = s.lower()
                if any(b in sl for b in begriffe):
                    kern = sl[:70]
                    if kern in gesehen:
                        continue
                    gesehen.add(kern)
                    stellen.append({"satz": s, "teil": teil_name})
                if len(stellen) >= max_je_thema * 2:
                    break
        # Frageteil bevorzugen: dort steht das Ungeschoente
        stellen.sort(key=lambda x: 0 if x["teil"] == "Frageteil" else 1)
        if stellen:
            out.append({"thema": thema, "stellen": stellen[:max_je_thema]})
    return out


def zusammenfassung_call(text: str, max_fakten=6, max_fragen=4) -> dict:
    """Faktenorientierte Zusammenfassung eines Earnings Calls - bewusst OHNE
    Stimmungsdeutung. Das Management klingt fast immer zuversichtlich; eine
    Stimmungsauswertung wuerde nur die PR messen. Stattdessen extrahieren wir:

      fakten   : Saetze mit nachpruefbaren Zahlen (Umsatz, Gewinn, Wachstum,
                 Guidance-Prozente) - das Konkrete, nicht das Gefuehlte.
      ausblick : Saetze mit klaren Zukunftsaussagen (guidance, we expect ...).
      nachfragen: die kritischen Analystenfragen aus dem Q&A - dort steht das
                 Ungeschoente, hier wird nachgehakt.
      themen   : die haeufigsten Themen (woran sich der Call abarbeitet).

    Alles woertliche Fundstellen, keine Deutung. Kein Anlagerat."""
    if not text:
        return {"fakten": [], "ausblick": [], "nachfragen": [], "themen": []}
    t = teile_transkript(text)
    vortrag, fragen = t["vortrag"], t["fragen"]

    # 1) Fakten: Saetze mit harten Zahlen (%, Mrd/Mio, "revenue of", "EPS of")
    _zahl = re.compile(
        r"(\$?\d[\d.,]*\s?(?:%|percent|billion|million|bps|basis points)"
        r"|revenue of|net income of|eps of|earnings per share of|grew \d"
        r"|increased \d|decreased \d|up \d|down \d|margin of)",
        re.IGNORECASE)
    fakten = []
    _gesehen = set()
    for s in _saetze(vortrag):
        if _zahl.search(s) and 40 <= len(s) <= 320:
            _k = s.lower()[:60]
            if _k not in _gesehen:
                _gesehen.add(_k)
                fakten.append(s.strip())
        if len(fakten) >= max_fakten:
            break

    # 2) Ausblick: Saetze mit klaren Zukunftsaussagen
    _aus_marker = ("guidance", "we expect", "we anticipate", "we now see",
                   "full year", "next quarter", "raising our", "lowering our",
                   "we forecast", "for fiscal", "going forward", "we project")
    ausblick = []
    _gesehen2 = set()
    for s in _saetze(vortrag):
        sl = s.lower()
        if any(m in sl for m in _aus_marker) and 40 <= len(s) <= 320:
            _k = sl[:60]
            if _k not in _gesehen2:
                _gesehen2.add(_k)
                ausblick.append(s.strip())
        if len(ausblick) >= 4:
            break

    # 3) Nachfragen: die Analystenfragen aus dem Q&A. Fragen an Fragezeichen
    #    trennen (der normale Satz-Splitter teilt nur an Punkten).
    nachfragen = []
    if fragen:
        _frage_ein = ("could you", "can you", "how do you", "what about",
                      "i wanted to ask", "i'm curious", "wondering if",
                      "help us understand", "walk us through", "clarify")
        # an ? UND . aufsplitten, damit einzelne Fragen entstehen
        _roh = re.split(r"(?<=[?.])\s+", fragen.replace("\n", " "))
        _gesehen3 = set()
        for s in _roh:
            s = s.strip()
            sl = s.lower()
            ist_frage = s.endswith("?") or any(e in sl for e in _frage_ein)
            if ist_frage and 30 <= len(s) <= 300:
                _k = sl[:50]
                if _k not in _gesehen3:
                    _gesehen3.add(_k)
                    nachfragen.append(s)
            if len(nachfragen) >= max_fragen:
                break

    # 4) Themen nach Haeufigkeit (worum kreist der Call?)
    low = text.lower()
    _themen_zaehler = [(thema, sum(low.count(b) for b in begriffe))
                       for thema, begriffe in THEMEN]
    _themen_zaehler.sort(key=lambda x: -x[1])
    themen = [{"thema": th, "nennungen": n} for th, n in _themen_zaehler if n > 0]

    return {"fakten": fakten, "ausblick": ausblick,
            "nachfragen": nachfragen, "themen": themen}
    """Wenige nachpruefbare Masszahlen - ausdruecklich KEINE Stimmungsanalyse.

    Der Anteil des Frageteils ist die interessanteste davon: Ein sehr
    langer Frageteil bedeutet meist, dass viel nachgehakt wurde."""
    if not text:
        return {}
    t = teile_transkript(text)
    ges = len(text)
    fragen = len(t["fragen"])
    low = text.lower()
    return {
        "zeichen": ges,
        "lesedauer_min": round(ges / 1100),
        "geteilt": t["geteilt"],
        "frageanteil_pct": round(fragen / ges * 100) if ges and t["geteilt"] else None,
        "nennungen": {thema: sum(low.count(b) for b in begriffe)
                      for thema, begriffe in THEMEN},
    }
