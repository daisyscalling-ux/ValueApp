#!/usr/bin/env python3
"""
pruef_fallback.py - Bei WIE VIELEN Titeln ist der Fair Value nur ein Notbehelf?

Hintergrund: Wenn keine einzige Bewertungsmethode ein plausibles Ergebnis
liefert, zeigt das Tool ersatzweise den gegen den Kurs geklammerten Median -
also den halben oder doppelten Kurs. Das sieht aus wie eine Bewertung, ist
aber keine. Erkennungszeichen: Upside von exakt -50 % oder +100 %.

Dieses Skript prueft Portfolio, Watchlist und optional eine eigene Liste
und sagt, wie verbreitet das Problem ist und welche Daten fehlen.

AUFRUF:
    python pruef_fallback.py                 # Portfolio + Watchlist
    python pruef_fallback.py GM F TSLA BMW.DE
"""
import sys

import providers
import valuation
import store


FELDER = ["eps_trailing", "eps_forward", "book_value_ps", "revenue",
          "ebitda", "target_mean", "free_cashflow", "total_debt",
          "sector", "market_cap"]


def titel_sammeln():
    tk = []
    try:
        for _name, rows in (store.load_all() or {}).items():
            for r in rows or []:
                t = str(r.get("ticker") or "").strip().upper()
                if t:
                    tk.append(t)
    except Exception as e:
        print(f"  (Portfolio nicht ladbar: {e})")
    try:
        for r in (store.get_watchlist() or []):
            t = str(r.get("ticker") if isinstance(r, dict) else r or "").strip().upper()
            if t:
                tk.append(t)
    except Exception as e:
        print(f"  (Watchlist nicht ladbar: {e})")
    return list(dict.fromkeys(tk))


def main():
    tickers = [a.strip().upper() for a in sys.argv[1:]] or titel_sammeln()
    if not tickers:
        print("Keine Titel gefunden. Gib welche an: python pruef_fallback.py GM F")
        return

    print("=" * 70)
    print(f"NOTBEHELF-PRUEFUNG  ({len(tickers)} Titel)")
    print("=" * 70)

    betroffen, ok, fehler = [], [], []
    fehlt_gesamt = {k: 0 for k in FELDER}

    for i, t in enumerate(tickers, 1):
        try:
            f = providers.get_fundamentals(t, deep=True)
            # Wie die App: Findet sich zum Rohtext kein Kurs, wird das
            # Boersensymbol gesucht ("GILEAD SCIENCES" -> "GILD"). Ohne
            # diesen Schritt meldet das Skript Fehler, die es nicht gibt.
            if not f or not f.get("price"):
                try:
                    tr = providers.search_symbol(t)
                    if tr:
                        sym = tr[0]["symbol"].upper()
                        f = providers.get_fundamentals(sym, deep=True)
                        if f and f.get("price"):
                            t = f"{t} -> {sym}"
                except Exception:
                    pass
            if not f or not f.get("price"):
                fehler.append((t, "kein Kurs"))
                continue
            ep = valuation.classify_playbook(f)
            v = valuation.fair_value(f, None, ep)
            fehlend = [k for k in FELDER if not f.get(k)]
            for k in fehlend:
                fehlt_gesamt[k] += 1
            if v.get("used_fallback"):
                betroffen.append((t, v.get("upside_pct"), len(fehlend), fehlend))
            else:
                ok.append((t, v.get("upside_pct"), v.get("n_methods"),
                           v.get("confidence")))
        except Exception as e:
            fehler.append((t, str(e)[:40]))
        if i % 10 == 0:
            print(f"  ... {i}/{len(tickers)}")

    n = len(betroffen) + len(ok)
    print(f"\n{'='*70}")
    print("ERGEBNIS")
    print("=" * 70)
    if n:
        anteil = len(betroffen) / n * 100
        print(f"  Notbehelf (unbrauchbar): {len(betroffen):3} von {n}  ({anteil:.0f} %)")
        print(f"  echte Bewertung:         {len(ok):3} von {n}")
    if fehler:
        print(f"  gar nicht abrufbar:      {len(fehler):3}")

    if betroffen:
        print(f"\n--- BETROFFEN (Fair Value ignorieren!) ---")
        for t, up, nf, fehlend in sorted(betroffen, key=lambda x: -x[2]):
            print(f"  {t:10} Upside {str(up):>7} %   {nf} Felder fehlen: "
                  f"{', '.join(fehlend[:4])}")

    if ok:
        print(f"\n--- IN ORDNUNG ---")
        for t, up, nm, conf in sorted(ok, key=lambda x: -(x[1] or 0))[:15]:
            print(f"  {t:10} Upside {str(up):>7} %   {nm} Methoden, "
                  f"Vertrauen {conf}")

    print(f"\n--- WELCHE DATEN FEHLEN AM HAEUFIGSTEN? ---")
    for k, c in sorted(fehlt_gesamt.items(), key=lambda x: -x[1]):
        if c:
            print(f"  {k:18} fehlt bei {c:3} Titeln")

    print(f"\n{'='*70}")
    print("SO LIEST DU DAS:")
    print("- Ist der Anteil klein (unter ~15 %), betrifft es Sonderfaelle -")
    print("  Titel mit luckenhaften Daten. Das Modell erkennt es intern und")
    print("  setzt reliable=False, es war nur nicht sichtbar.")
    print("- Ist der Anteil gross, stimmt etwas mit der Datenversorgung nicht.")
    print("  Dann zeigt die Liste unten, welches Feld systematisch fehlt.")


if __name__ == "__main__":
    main()
