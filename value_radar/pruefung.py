"""
pruefung.py - Qualitaets-Gates fuer einen einzelnen Titel.

Ersetzt scorecard.py und matrices.py.

WARUM ERSETZT

    Es gab zwei unabhaengige Siebe fuer dieselbe Frage: die Scorecard mit
    sechs Pflicht-Gates und kandidat.gate_pruefen() mit acht. Beide beurteilen
    dieselbe Aktie mit unterschiedlichen Schwellen und koennen sich
    widersprechen - ein Titel konnte "Kaufkandidat" sein und gleichzeitig vom
    Screener ausgeschlossen werden. Zwei Antworten auf dieselbe Frage sind
    schlechter als eine, weil man keiner mehr trauen kann.

    Dazu kam Abnutzung, die im alten Code eingestanden war:

      "Gelockert wurde nur die Bonus-Schwelle, damit ueberhaupt genug Faelle
       fuer eine Auswertung zusammenkommen"
      "wodurch das Kriterium ohnehin fast immer 'bestanden' war - es filterte
       also praktisch nichts"

    Beides ist Muster M5 aus dem Audit-Plan: stille Wirkungslosigkeit. Beim
    zweiten Mal wurde die Ursache erkannt und richtig behandelt. Beim ersten
    wurde die Schwelle gesenkt, statt zu fragen, warum kein Titel besteht.

WAS UEBERNOMMEN WURDE

    Matrix 1 wird nicht ersetzt, sondern faellt weg: Ihre fundamentalen
    Kriterien (FCF-Trend, Net Debt/EBITDA, ROE gegen WACC) stehen inzwischen
    in der Finanzlage und der Forensik, mit sichtbaren Schwellen. Ihre
    technischen Kriterien (RSI, SMA200) rechnet das Momentum-Modul besser -
    risikoadjustiert und sektorbereinigt.

    Aus Matrix 2 bleibt EIN Teil, den das neue System sonst nirgends hat:
    fundamentales Momentum - Umsatzbeschleunigung und Ergebnisueberraschung.
    Das ist weder im Value-Profil noch im Kursmomentum abgedeckt.

    Die Kategorie "Narrative" (15 % Gewicht in Matrix 2) faellt ersatzlos weg.
    Es liess sich im Code keine belastbare Datengrundlage dafuer finden - ein
    weiches Kriterium mit hartem Gewicht.

WAS DAS HIER NICHT TUT

    Es rechnet nichts Eigenes. Die Gates kommen aus kandidat.gate_pruefen(),
    dieselbe Funktion, die der Screener benutzt. Damit ist ausgeschlossen,
    dass Einzelanalyse und Screener denselben Titel verschieden beurteilen.
"""

from __future__ import annotations

__version__ = "2026.09.22"

from typing import Dict, List, Optional

#: Wie viele Bonuspunkte aus einem bestandenen Titel einen Kaufkandidaten
#: machen. Bewusst NICHT gesenkt, wenn zu wenige Faelle entstehen - genau das
#: war der Fehler im Vorgaenger. Kommen keine Kandidaten zusammen, ist das
#: eine Aussage ueber den Markt, keine ueber die Schwelle.
BONUS_FUER_KAUFKANDIDAT = 2


# ---------------------------------------------------------------------------
# Fundamentales Momentum - der gerettete Teil aus Matrix 2
# ---------------------------------------------------------------------------

def fundamentales_momentum(fund: dict, historie=None) -> dict:
    """Beschleunigt sich das Geschaeft - unabhaengig vom Kurs?

    Kursmomentum misst, was der Markt tut. Das hier misst, was die Firma tut.
    Beides kann auseinanderlaufen, und die Luecke ist interessant: Ein Titel
    mit anziehendem Umsatzwachstum bei fallendem Kurs ist etwas anderes als
    einer, bei dem beides faellt.

    0-100. None, wenn zu wenig Historie vorliegt - kein Ersatzwert, weil ein
    erfundener Mittelwert hier so aussaehe wie eine Messung.
    """
    rows = sorted([z for z in (historie or []) if z.get("jahr") and z.get("revenue")],
                  key=lambda z: str(z["jahr"]))
    teile: Dict[str, float] = {}
    begruendung: List[str] = []

    if len(rows) >= 4:
        umsatz = [float(z["revenue"]) for z in rows]
        raten = [(umsatz[i] / umsatz[i - 1] - 1.0)
                 for i in range(1, len(umsatz)) if umsatz[i - 1] > 0]
        if len(raten) >= 3:
            jetzt, vorher = raten[-1], raten[-2]
            delta = jetzt - vorher
            # -10 Pp. = 0 Punkte, +10 Pp. = 100. Die Beschleunigung, nicht die
            # Hoehe: 5 % nach 2 % ist ein besseres Zeichen als 20 % nach 30 %.
            teile["Umsatzbeschleunigung"] = max(0.0, min(100.0,
                                                         (delta + 0.10) / 0.20 * 100))
            begruendung.append(f"Umsatzwachstum {vorher * 100:+.0f} % "
                               f"\u2192 {jetzt * 100:+.0f} %")

    # Ergebnisueberraschung: liegt der Konsens fuer das naechste Jahr ueber
    # dem, was zuletzt geliefert wurde?
    eps_t, eps_f = fund.get("eps_trailing"), fund.get("eps_forward")
    if eps_t and eps_f and eps_t > 0:
        sprung = eps_f / eps_t - 1.0
        teile["Ergebniserwartung"] = max(0.0, min(100.0, (sprung + 0.10) / 0.50 * 100))
        begruendung.append(f"erwartetes EPS {sprung * 100:+.0f} % ggue. TTM")

    # Margenrichtung
    margen = [z.get("profit_margin") for z in rows if z.get("profit_margin") is not None]
    if len(margen) >= 4:
        jetzt = float(margen[-1])
        schnitt = sum(float(m) for m in margen[:-1]) / len(margen[:-1])
        if schnitt:
            ab = (jetzt - schnitt) / abs(schnitt)
            teile["Margenrichtung"] = max(0.0, min(100.0, (ab + 0.30) / 0.60 * 100))
            begruendung.append(f"Nettomarge {jetzt * 100:.1f} % vs. Schnitt "
                               f"{schnitt * 100:.1f} %")

    if not teile:
        return {"score": None, "teile": {}, "begruendung": [],
                "hinweis": "zu wenig Historie fuer fundamentales Momentum"}

    return {"score": round(sum(teile.values()) / len(teile), 1),
            "teile": {k: round(v, 1) for k, v in teile.items()},
            "begruendung": begruendung,
            # Auf wie vielen der drei Bausteine steht der Wert? Unter zwei ist
            # er ein Hinweis, keine Messung.
            "basis": round(len(teile) / 3.0, 2)}


# ---------------------------------------------------------------------------
# Pruefung eines Titels
# ---------------------------------------------------------------------------

def pruefe(kandidat_obj, profil: str = "value",
           historie=None) -> dict:
    """Pflicht-Gates und Bonuspunkte fuer einen Titel.

    kandidat_obj: ein kandidat.Kandidat mit gefuellter Bewertung und Forensik.
    Die Gates kommen unveraendert aus kandidat.gate_pruefen() - dieselbe
    Funktion, die der Screener benutzt.
    """
    import kandidat as kd

    gruende = kd.gate_pruefen(kandidat_obj, profil)
    bestanden = not gruende

    fm = fundamentales_momentum(kandidat_obj.fund or {}, historie)

    # --- Bonuspunkte: Dinge, die einen Titel besser machen, aber sein
    #     Bestehen nicht entscheiden sollen.
    bonus: List[dict] = []

    def b(label, ok, detail):
        bonus.append({"label": label, "ok": bool(ok), "detail": detail})

    ke = kandidat_obj.kurserwartung or {}
    urteil_kurs = ke.get("urteil")
    b("Kurs verlangt weniger als geliefert wurde",
      urteil_kurs in ("konservativ", "fair"),
      {"konservativ": "deutlich unter dem Korridor",
       "fair": "im Korridor",
       "anspruchsvoll": "am oberen Rand",
       "zu_optimistisch": "ueber dem Korridor",
       "basis_unklar": "keine Aussage moeglich"}.get(urteil_kurs, "n/a"))

    perz = ((kandidat_obj.historie or {}).get("urteil") or {}).get("teuer_pct")
    b("Guenstig in der eigenen Historie",
      perz is not None and perz <= 35,
      f"{perz:.0f}. Perzentil" if perz is not None else "keine Historie")

    ma = kandidat_obj.multiple_anteil
    b("Fair Value ueberwiegend aus Cashflow",
      ma is not None and ma <= 0.60,
      f"{ma:.0%} aus Multiples" if ma is not None else "keine Herkunft")

    b("Fundamentales Momentum \u2265 60",
      fm.get("score") is not None and fm["score"] >= 60,
      f"{fm['score']:.0f}/100" if fm.get("score") is not None
      else fm.get("hinweis", "n/a"))

    p = (kandidat_obj.forensik.get("piotroski") or {}).get("score")
    b("Piotroski F \u2265 7",
      p is not None and p >= 7,
      f"{p}/9" if p is not None else "nicht berechenbar")

    erfuellt = sum(1 for x in bonus if x["ok"])

    if not bestanden:
        urteil = ("Verwerfen" if len(gruende) >= 2 else "Knapp verfehlt")
    elif erfuellt >= BONUS_FUER_KAUFKANDIDAT:
        urteil = "Kaufkandidat"
    else:
        urteil = "Solide \u2013 Watchlist"

    return {
        "urteil": urteil,
        "bestanden": bestanden,
        "ausschlussgruende": gruende,
        "bonus": bonus,
        "bonus_erfuellt": erfuellt,
        "bonus_noetig": BONUS_FUER_KAUFKANDIDAT,
        "fundamentales_momentum": fm,
        "profil": profil,
        # Damit im Zweifel nachvollziehbar bleibt, worauf das Urteil beruht.
        "datenstufe": kandidat_obj.datenstufe,
        "hinweise": (kandidat_obj.qualitaet or {}).get("hinweise") or [],
        "ton": urteil_ton(urteil),
    }


def urteil_ton(urteil: str) -> str:
    return {"Kaufkandidat": "gruen", "Solide \u2013 Watchlist": "gelb",
            "Knapp verfehlt": "gelb", "Verwerfen": "rot"}.get(urteil, "grau")
