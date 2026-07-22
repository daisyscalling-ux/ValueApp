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
