"""
pruefe_korridor.py - Ist das Reverse-DCF-Gate richtig kalibriert?

    python3 pruefe_korridor.py COST UNH LLY ASML.AS C DVN

"Kurs verlangt mehr als das realistisch Lieferbare" ist mit Abstand der
haeufigste Ausschlussgrund geworden - 19 von 30 Titeln im letzten Lauf. Damit
ist es der maechtigste Filter im ganzen System, und er war nie an einem
Einzelfall geprueft.

Zwei Moeglichkeiten, und sie sehen von aussen gleich aus:
  a) Der Markt ist tatsaechlich teuer - dann ist das Gate richtig.
  b) Der Korridor ist zu eng - dann werfen wir zwei Drittel des Universums
     wegen einer Fehlkalibrierung weg.

Dieses Skript zeigt je Titel die Anker, den daraus gebildeten Korridor, das
eingepreiste Wachstum und die Umsatzhistorie, aus der alles stammt. Damit
laesst sich von Hand pruefen, ob das Urteil traegt.
"""

import sys

import providers
import roic
import valuation


def main(t: str) -> None:
    print(f"\n{'=' * 70}\n{t}\n{'=' * 70}")
    f = providers.get_fundamentals(t, deep=True) or {}
    if not f.get("price"):
        print("  Keine Daten.")
        return

    # umsatz_reihe fuehrt kennzahl_historie und income_annual zusammen -
    # genau der Pfad, den kandidat.pruefe() benutzt. Direkt kennzahl_historie
    # zu rufen wuerde die Verlaengerung gar nicht testen.
    hist = roic.umsatz_reihe(t, 15) if roic.enabled() else []
    rows = sorted([z for z in (hist or []) if z.get("revenue")],
                  key=lambda z: str(z.get("jahr")))
    if rows:
        print("  Umsatzhistorie (Mrd):")
        zeile = "   "
        for z in rows[-11:]:
            zeile += f" {str(z['jahr'])[-2:]}:{z['revenue'] / 1e9:6.1f}"
        print(zeile)
        if len(rows) >= 2:
            wachstum = [(rows[i]["revenue"] / rows[i - 1]["revenue"] - 1)
                        for i in range(1, len(rows))]
            print("   Jahresraten:  " + "  ".join(f"{w * 100:+.0f}%"
                                                  for w in wachstum[-10:]))

    preset = valuation.classify_playbook(f)
    anker = valuation.anker_aus_fund(f, historie=hist)
    print(f"\n  Playbook: {preset}")
    print("  Anker:")
    for k in ("cagr_3j", "cagr_5j", "cagr_10j", "konsens"):
        v = anker.get(k)
        print(f"    {k:12s} {'--' if v is None else f'{v * 100:6.1f} %'}")

    print(f"    Konsensquelle: {anker.get('_konsens_quelle')}")
    print(f"    Jahre Umsatzhistorie: {anker.get('_jahre')}")

    kor = valuation.rd_korridor(anker, preset)
    if not kor:
        print("  Kein Korridor (zu wenige Anker) - Gate greift nicht.")
        return
    _belastbar = len(kor.anker) >= 3
    print(f"\n  Korridor ({preset}-Gewichte): "
          f"{kor.tief * 100:.1f} % bis {kor.hoch * 100:.1f} %  "
          f"(Mitte {kor.mitte * 100:.1f} %)")
    print(f"    {len(kor.anker)} Anker -> "
          + ("belastbar, Gate darf ausschliessen"
             if _belastbar else
             "NICHT belastbar - Gate wertet nur als Hinweis"))
    print("    Gewichte:", {k: round(v, 2) for k, v in kor.gewichte.items()})

    g = valuation.impliziertes_wachstum(f, preset)
    if g is None:
        print("  Eingepreistes Wachstum nicht loesbar.")
        return
    pos = kor.position(g)
    print(f"  Der Kurs verlangt: {g * 100:.1f} % pro Jahr  ->  {pos}")

    print("\n  Gegenprobe - was waere der DCF bei den Ankern?")
    b = valuation._basis(f, preset)
    if b:
        for k in ("cagr_3j", "cagr_5j", "cagr_10j", "konsens"):
            v = anker.get(k)
            if v is None:
                continue
            w = valuation._wert_je_aktie(b["fcf"], b["shares"], b["net_debt"],
                                         v, b["g_term"], b["r"], b["years"])
            if w:
                print(f"    bei {k:10s} {v * 100:5.1f} %  ->  {w:8.2f} "
                      f"({(w / f['price'] - 1) * 100:+6.0f} % zum Kurs)")
        print(f"    Kurs                        {f['price']:8.2f}")

    print("\n  Einordnung: Liegt das eingepreiste Wachstum deutlich ueber ALLEN")
    print("  Ankern, ist das Urteil belastbar. Liegt es nur knapp ueber der")
    print("  Obergrenze, entscheidet die Gewichtung - dann lohnt ein Blick auf")
    print("  das Playbook.")


if __name__ == "__main__":
    for t in (sys.argv[1:] or ["COST"]):
        main(t.upper())
