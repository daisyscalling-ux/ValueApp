#!/usr/bin/env python3
"""
kandidat_diagnose.py - Warum erzeugt der Nachtlauf keine Kaufkandidaten?

Vergleicht fuer eine Handvoll Titel das Urteil, das der NACHTLAUF (_analyse
in precompute) faellt, mit den Einzel-Gates. Zeigt bei "kein Kaufkandidat"
GENAU, welches Pflicht-Gate scheitert und wie viele Bonuspunkte fehlen.

So sehen wir schwarz auf weiss, ob HSBC & Co. im Nachtlauf wirklich
Kaufkandidat werden - oder an welchem Gate es scheitert.

AUFRUF (PowerShell):  $env:ROIC_API_KEY="dein_key"; python kandidat_diagnose.py
        eigene Titel:  python kandidat_diagnose.py HSBC AAPL MU
"""
import os
import sys


def _key():
    if os.getenv("ROIC_API_KEY"):
        return
    for p in (".streamlit/secrets.toml", "../.streamlit/secrets.toml"):
        if os.path.isfile(p):
            for z in open(p, encoding="utf-8"):
                if z.strip().startswith("ROIC_API_KEY"):
                    os.environ["ROIC_API_KEY"] = \
                        z.split("=", 1)[1].strip().strip('"').strip("'")
                    return


_key()

import providers    # noqa: E402
import scoring       # noqa: E402
import valuation     # noqa: E402
import scorecard as sc  # noqa: E402
import matrices as mx   # noqa: E402

STANDARD = ["DELL", "AAPL", "MU", "LLY", "BARC.L"]


def diagnose(t):
    print("=" * 60)
    print(t)
    print("=" * 60)
    f = providers.get_fundamentals(t, deep=True)
    if not f or not f.get("price"):
        print("  kein Kurs / keine Daten")
        return
    ep = valuation.classify_playbook(f)
    s = scoring.score_stock(f, None, preset=ep)
    v = valuation.fair_value(f, None, ep)
    hist = providers.get_price_history(t, period="1y", interval="1d")
    extras = providers.get_signal_extras(t)
    try:
        screen_extras = providers.get_screen_extras(t) or {}
    except Exception:
        screen_extras = {}
    try:
        insider = providers.get_insider_activity(t)
    except Exception:
        insider = None
    try:
        analyst = providers.get_analyst_ratings(t)
    except Exception:
        analyst = None

    # EXAKT wie der reparierte Nachtlauf (_analyse):
    sig = mx.build_signals(f, hist, analyst, extras)
    res = sc.evaluate(f, v, s.get("composite"),
                      mx.auto_m1_total(sig), mx.auto_m2_total(sig),
                      screen_extras, insider, analyst)

    print(f"  Composite: {s.get('composite')}")
    print(f"  Upside:    {v.get('upside_pct')}")
    print(f"  Urteil:    {res.get('verdict')}  (vkey {res.get('vkey')})")
    print()
    print("  Pflicht-Gates:")
    fehlend = []
    for g in res.get("mandatory", []):
        mark = "\u2713" if g["ok"] else "\u2717"
        if not g["ok"]:
            fehlend.append(g["label"])
        print(f"    {mark} {g['label']:46} {g.get('detail','')}")
    nb = sum(1 for b in res.get("bonus", []) if b["ok"])
    print(f"  Bonus: {nb} erfuellt")
    print()
    if res.get("verdict") == "Kaufkandidat":
        print("  => KAUFKANDIDAT - erscheint in der Trefferbilanz.")
    elif fehlend:
        print(f"  => KEIN Kaufkandidat. Es scheitert an: {', '.join(fehlend)}")
    else:
        print(f"  => Alle Gates ok, aber nur {nb} Bonus (mind. 1 noetig).")
    print()


def main():
    titel = sys.argv[1:] or STANDARD
    for t in titel:
        diagnose(t)

    # Sonderfall: dieselbe Firma, zwei Notierungen - muessen GLEICH bewertet
    # werden (oder eine sollte via ISIN entdoppelt sein).
    print("\n" + "#" * 60)
    print("# DOPPELNOTIERUNG-CHECK: FRES.L vs FNLPF (beide Fresnillo)")
    print("#" * 60)
    import roic
    for t in ("FRES.L", "FNLPF"):
        try:
            r = roic.aufloesen(t)
            f = providers.get_fundamentals(t, deep=True)
            print(f"\n  {t}:")
            print(f"    roic-Symbol: {r.get('symbol') if r else 'nicht aufloesbar'}")
            print(f"    ISIN:        {f.get('isin')}")
            print(f"    Kurs:        {f.get('price')} {f.get('currency')}")
            ep = valuation.classify_playbook(f)
            comp = scoring.score_stock(f, None, preset=ep).get("composite")
            v = valuation.fair_value(f, None, ep)
            print(f"    Composite:   {comp}")
            print(f"    Upside:      {v.get('upside_pct')}")
        except Exception as e:
            print(f"  {t}: Fehler {e}")
    print("\n  -> Gleiche ISIN? Dann MUSS die Entdopplung eine der beiden")
    print("     entfernen. Verschiedene Composites bei gleicher Firma sind")
    print("     ein Bewertungsfehler (verschiedene Datenquellen/Waehrung).")

    print("\n" + "=" * 60)
    print("Schick mir die Ausgabe. Wenn DELL hier 'KAUFKANDIDAT' zeigt,")
    print("greift der Fix - dann fehlt nur noch ein frischer Nachtlauf,")
    print("damit die Trefferbilanz sich fuellt. Zeigt es ein scheiterndes")
    print("Gate, sehen wir genau, wo es klemmt.")


if __name__ == "__main__":
    main()
