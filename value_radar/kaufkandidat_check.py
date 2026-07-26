#!/usr/bin/env python3
"""
kaufkandidat_check.py — Warum stuft die Scorecard (fast) niemanden als
"Kaufkandidat" ein?

Die Trefferbilanz zeigt einen Titel nur dann als Kaufkandidat, wenn die
Scorecard ALLE 6 Pflicht-Gates vergibt PLUS mindestens 1 Bonuspunkt. Ein
einziges verfehltes Gate genuegt, und der Titel ist "nur" Watchlist.

Dieses Skript nimmt eine Handvoll Titel (Standard: die aus deinem Screenshot)
und zeigt je Titel, WELCHES Gate fehlt. So siehst du schwarz auf weiss, ob
"null Kaufkandidaten" ein echtes Urteil ist (die Titel erfuellen die
strengen Kriterien schlicht nicht) oder ein Datenproblem (z.B. kein Fair
Value -> Upside-Gate faellt automatisch).

AUFRUF (im Ordner value_radar, mit gesetztem roic-Schluessel):
    python kaufkandidat_check.py
    python kaufkandidat_check.py HSBC BHP.L RR.L      # eigene Titel
"""
import os
import sys


def _schluessel():
    if os.getenv("ROIC_API_KEY"):
        return
    for p in (".streamlit/secrets.toml", "../.streamlit/secrets.toml",
              os.path.expanduser("~/.streamlit/secrets.toml")):
        if os.path.isfile(p):
            try:
                for zeile in open(p, encoding="utf-8"):
                    if zeile.strip().startswith("ROIC_API_KEY"):
                        os.environ["ROIC_API_KEY"] = \
                            zeile.split("=", 1)[1].strip().strip('"').strip("'")
                        return
            except Exception:
                pass


_schluessel()

import providers          # noqa: E402
import scorecard          # noqa: E402
import valuation          # noqa: E402
import scoring            # noqa: E402
import matrices as _mx    # noqa: E402

STANDARD = ["HSBC", "RR.L", "BARC.L", "BHP.L", "LLY", "VOD"]


def pruefe(t):
    print("=" * 60)
    print(t)
    print("=" * 60)
    try:
        f = providers.get_fundamentals(t, deep=True)
    except Exception as e:
        print(f"  Fehler beim Laden: {e}")
        return
    if not f or not f.get("price"):
        print("  Keine Daten / kein Preis.")
        return

    try:
        ep = valuation.classify_playbook(f)
        s = scoring.score_stock(f, None, preset=ep)
        v = valuation.fair_value(f, None, ep)
        hist = providers.get_price_history(t, period="1y", interval="1d")
        extras = providers.get_signal_extras(t)
        sig = _mx.build_signals(f, hist, None, extras)
        res = scorecard.evaluate(f, v, s.get("composite"),
                                 _mx.auto_m1_total(sig), _mx.auto_m2_total(sig),
                                 extras, None, None)
    except Exception as e:
        print(f"  Scorecard-Fehler: {e}")
        import traceback
        traceback.print_exc()
        return

    comp = s.get("composite")
    print(f"  Urteil: {res.get('verdict')}  (Composite "
          f"{comp:.0f})" if comp is not None else f"  Urteil: {res.get('verdict')}")
    print()
    print("  Pflicht-Gates (ALLE muessen 'ja' sein):")
    alle_ok = True
    for g in res.get("mandatory", []):
        mark = "\u2713" if g["ok"] else "\u2717"
        if not g["ok"]:
            alle_ok = False
        print(f"    {mark} {g['label']:48} {g.get('detail', '')}")
    n_bonus = sum(1 for b in res.get("bonus", []) if b["ok"])
    print(f"\n  Bonuspunkte: {n_bonus} (mind. 1 noetig)")
    print()
    if res.get("verdict") == "Kaufkandidat":
        print("  => KAUFKANDIDAT.")
    elif alle_ok:
        print("  => Alle Gates ok, aber zu wenig Bonus -> nur Watchlist.")
    else:
        fehlend = [g["label"] for g in res.get("mandatory", []) if not g["ok"]]
        print(f"  => KEIN Kaufkandidat. Es fehlt: {', '.join(fehlend)}")
    print()


def main():
    titel = sys.argv[1:] or STANDARD
    if not os.getenv("ROIC_API_KEY"):
        print("Hinweis: kein ROIC_API_KEY gefunden - Daten evtl. unvollstaendig.\n")
    for t in titel:
        pruefe(t)
    print("=" * 60)
    print("Schick mir die Ausgabe. Dann sehen wir, ob 'null Kaufkandidaten'")
    print("das echte Urteil ist (Titel erfuellen die strengen Kriterien nicht)")
    print("oder ob ein Gate an fehlenden Daten scheitert (z.B. kein Fair Value")
    print("-> Upside-Gate faellt automatisch). Je nachdem justieren wir die")
    print("Schwellen oder lassen sie bewusst streng.")


if __name__ == "__main__":
    main()
