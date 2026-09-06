"""
earnings_reaktion.py - Wie reagiert der Kurs auf Zahlen, und haelt die Reaktion?

WARUM DIESES MODUL

    Der Block "Wird der Beat bezahlt?" braucht die EPS-Ueberraschung, also den
    Analystenkonsens zum Berichtszeitpunkt. Den liefert roic nicht - der Block
    blieb deshalb leer.

    Die Termine der Earnings Calls sind aber da (roic.transcript_liste), und
    Tageskurse auch (roic.prices_history). Damit laesst sich eine verwandte,
    ebenfalls nuetzliche Frage beantworten - ohne Konsensdaten.

WAS ES MISST, UND WAS NICHT

    NICHT: ob ein Beat bezahlt wird. Ohne Konsens ist nicht bekannt, ob die
    Zahlen ueber oder unter der Erwartung lagen. Diese Einschraenkung bleibt.

    STATTDESSEN: das Reaktionsmuster.
      1. Schlusskurs am Tag vor dem Call  (Ausgangspunkt)
      2. Eroeffnung am Tag danach          (erste Reaktion, oft die groesste)
      3. Schluss eine Woche danach         (haelt es?)
      4. Schluss einen Monat danach        (haelt es laenger?)

    Die interessante Groesse ist nicht die erste Reaktion, sondern was davon
    uebrig bleibt. Ein Titel, der regelmaessig +6 % eroeffnet und binnen einer
    Woche alles zurueckgibt, verhaelt sich anders als einer, der die Bewegung
    haelt. Das eine ist Rauschen, das andere eine Neubewertung.

ZUR DEUTUNG

    Ein Muster aus acht bis zwoelf Quartalen ist ein Hinweis, keine Regel.
    Die Rueckgabe nennt deshalb immer die Zahl der Beobachtungen, und unter
    sechs wird gar kein Urteil gebildet.
"""

from __future__ import annotations

__version__ = "2026.09.25"

from datetime import datetime, timedelta
from typing import Dict, List, Optional

#: Unter so vielen ausgewerteten Quartalen ist jedes Muster Zufall.
MIN_QUARTALE = 6

#: Ab dieser durchschnittlichen Abgabe gilt die Reaktion als verpuffend.
VERPUFFT_PP = 2.0


def _als_datum(x) -> Optional[datetime]:
    if not x:
        return None
    s = str(x)[:10]
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def _kurse_als_karte(reihe) -> Dict[str, dict]:
    """Tageskurse nach Datum, damit sich Stichtage nachschlagen lassen."""
    out = {}
    for z in reihe or []:
        if not isinstance(z, dict):
            continue
        d = str(z.get("date") or z.get("datum") or "")[:10]
        if d:
            out[d] = z
    return out


def _kurs_am_oder_nach(karte: Dict[str, dict], tag: datetime,
                       feld: str = "close", max_tage: int = 6) -> Optional[float]:
    """Kurs am Stichtag - oder am naechsten Handelstag danach.

    Earnings Calls liegen oft abends nach Boersenschluss, Berichtstermine auf
    Feiertagen. Ohne diese Suche faellt jeder zweite Termin aus.
    """
    for i in range(max_tage + 1):
        d = (tag + timedelta(days=i)).strftime("%Y-%m-%d")
        z = karte.get(d)
        if z:
            v = z.get(feld) if z.get(feld) is not None else z.get("close")
            try:
                v = float(v)
                if v > 0:
                    return v
            except (TypeError, ValueError):
                pass
    return None


def _kurs_am_oder_vor(karte: Dict[str, dict], tag: datetime,
                      max_tage: int = 6) -> Optional[float]:
    for i in range(max_tage + 1):
        d = (tag - timedelta(days=i)).strftime("%Y-%m-%d")
        z = karte.get(d)
        if z and z.get("close"):
            try:
                v = float(z["close"])
                if v > 0:
                    return v
            except (TypeError, ValueError):
                pass
    return None


def erheben(ticker: str, max_quartale: int = 12) -> dict:
    """Reaktionsmuster um die Earnings-Termine.

    Braucht nur roic: Termine aus transcript_liste, Kurse aus prices_history.
    Kein Analystenkonsens, keine zweite Quelle.
    """
    import roic

    if not roic.enabled() or not roic.covers(ticker):
        return {"ticker": ticker, "quartale": [],
                "hinweis": "roic deckt diesen Titel nicht ab"}

    try:
        calls = roic.transcript_liste(ticker, limit=40) or []
    except Exception as e:
        return {"ticker": ticker, "quartale": [],
                "hinweis": f"Termine nicht ladbar: {e}"}
    if not calls:
        return {"ticker": ticker, "quartale": [],
                "hinweis": "keine Earnings-Termine gefunden"}

    termine = []
    for c in calls:
        d = _als_datum(c.get("datum") or c.get("date"))
        if d:
            termine.append((d, c))
    termine.sort(key=lambda x: x[0], reverse=True)
    termine = termine[:max_quartale]
    if not termine:
        return {"ticker": ticker, "quartale": [],
                "hinweis": "Termine ohne brauchbares Datum"}

    # Kurse in EINEM Abruf holen: vom aeltesten Termin bis heute plus Puffer.
    von = (termine[-1][0] - timedelta(days=10)).strftime("%Y-%m-%d")
    try:
        reihe = roic.prices_history(ticker, von=von, limit=1000, order="asc")
    except Exception as e:
        return {"ticker": ticker, "quartale": [],
                "hinweis": f"Kurse nicht ladbar: {e}"}
    karte = _kurse_als_karte(reihe)
    if not karte:
        return {"ticker": ticker, "quartale": [],
                "hinweis": "keine Kursdaten fuer den Zeitraum"}

    quartale = []
    for d, c in termine:
        vorher = _kurs_am_oder_vor(karte, d - timedelta(days=1))
        # Der Call liegt meist abends nach Schluss - die erste handelbare
        # Reaktion ist die Eroeffnung des Folgetags.
        eroeffnung = _kurs_am_oder_nach(karte, d + timedelta(days=1), "open")
        woche = _kurs_am_oder_nach(karte, d + timedelta(days=7))
        monat = _kurs_am_oder_nach(karte, d + timedelta(days=30))
        if not vorher or not eroeffnung:
            continue

        def pct(x):
            return round((x / vorher - 1) * 100, 2) if x else None

        quartale.append({
            "datum": d.strftime("%Y-%m-%d"),
            "quartal": (c.get("quartal") or c.get("quarter")
                        or c.get("fiscal_quarter")),
            "jahr": c.get("jahr") or c.get("year") or c.get("fiscal_year"),
            "kurs_vorher": round(vorher, 2),
            "reaktion_pct": pct(eroeffnung),
            "nach_woche_pct": pct(woche),
            "nach_monat_pct": pct(monat),
        })

    return {"ticker": ticker, "quartale": quartale,
            **auswerten(quartale)}


def auswerten(quartale: List[dict]) -> dict:
    """Was sagt das Muster - wenn es genug Beobachtungen gibt?"""
    n = len(quartale or [])
    if n < MIN_QUARTALE:
        return {"n": n, "urteil": None,
                "hinweis": (f"erst {n} auswertbare Quartale, "
                            f"mindestens {MIN_QUARTALE} noetig")}

    reaktionen = [q["reaktion_pct"] for q in quartale
                  if q.get("reaktion_pct") is not None]
    mit_woche = [q for q in quartale
                 if q.get("reaktion_pct") is not None
                 and q.get("nach_woche_pct") is not None]

    positiv = sum(1 for r in reaktionen if r >= 0)
    schnitt = round(sum(reaktionen) / len(reaktionen), 2) if reaktionen else None
    ausschlag = (round(sum(abs(r) for r in reaktionen) / len(reaktionen), 2)
                 if reaktionen else None)

    # Bleibt die erste Reaktion bestehen? Gemessen als Abgabe: Wie viel des
    # ersten Ausschlags ist nach einer Woche noch da?
    haltequote = None
    abgabe = None
    if mit_woche:
        # ABSOLUTE Bewegung vergleichen, nicht die vorzeichenbehaftete.
        #
        # Erste Fassung mittelte (nach_woche - reaktion). Bei einem Titel, der
        # Aufwaertsreaktionen abgibt UND Abwaertsreaktionen aufholt, heben sich
        # die Vorzeichen im Mittel auf: Die Abgabe kam bei 0,06 Pp. heraus,
        # obwohl KEINE einzige Bewegung gehalten hatte. Das Urteil lautete
        # "gemischtes Bild" statt "verpufft".
        diffs = [abs(q["nach_woche_pct"]) - abs(q["reaktion_pct"])
                 for q in mit_woche]
        abgabe = round(sum(diffs) / len(diffs), 2)
        gehalten = sum(1 for q in mit_woche
                       if (q["reaktion_pct"] >= 0 and q["nach_woche_pct"] >= q["reaktion_pct"] * 0.5)
                       or (q["reaktion_pct"] < 0 and q["nach_woche_pct"] <= q["reaktion_pct"] * 0.5))
        haltequote = round(gehalten / len(mit_woche) * 100)

    # Die Haltequote entscheidet, nicht die mittlere Abgabe: Sie zaehlt
    # Einzelfaelle und kann sich nicht wegmitteln.
    if haltequote is not None and haltequote < 40:
        urteil = "Reaktion verpufft meist innerhalb einer Woche"
        ton = "gelb"
    elif haltequote is not None and haltequote >= 60:
        urteil = "Reaktion haelt ueberwiegend"
        ton = "gruen"
    else:
        urteil = "gemischtes Bild"
        ton = "grau"

    return {
        "n": n,
        "positiv_pct": round(positiv / len(reaktionen) * 100) if reaktionen else None,
        "schnitt_reaktion_pct": schnitt,
        "mittlerer_ausschlag_pct": ausschlag,
        "abgabe_nach_woche_pp": abgabe,
        "haltequote_pct": haltequote,
        "urteil": urteil,
        "ton": ton,
    }
