#!/usr/bin/env python3
"""
test_bewertung.py - Warum nutzt der Fair Value nur 2 Methoden?

Mein erstes Skript (test_datenlage.py) hatte zwei falsche Feldnamen und hat
dadurch 'analyst' und 'fwd_pe' faelschlich als fehlend gemeldet. Dieses Skript
misst korrekt: Es rechnet JEDE Methode einzeln aus und zeigt, welcher Filter
sie anschliessend entfernt.

AUFRUF (im Ordner mit providers.py):
    python test_bewertung.py
    python test_bewertung.py BP.L SHEL.L

Kostet nichts, aendert nichts.
"""
import sys

import providers
import valuation as V

DEFAULT = ["AAPL", "BP.L", "SHEL.L", "GSK.L", "SAP.DE"]


def analyse(tk):
    print("\n" + "=" * 64)
    print(f"TICKER: {tk}")
    print("=" * 64)
    try:
        f = providers.get_fundamentals(tk, deep=True)
    except Exception as e:
        print(f"  Abruf fehlgeschlagen: {e}")
        return
    if not f:
        print("  Keine Daten.")
        return

    price = f.get("price")
    preset = V.classify_playbook(f)
    print(f"  Kurs: {price} {f.get('currency') or ''} | Playbook: {preset}")
    print(f"  Datenquellen: {f.get('data_sources') or '(keine Angabe)'}")

    # Liefern die Schluesselfelder ueberhaupt Werte?
    print("\n  SCHLUESSELFELDER:")
    for key, label in [("target_mean", "Analysten-Kursziel"),
                       ("analyst_count", "Anzahl Analysten"),
                       ("hist_pe_median", "hist. KGV-Median (nur FMP deep)"),
                       ("eps_forward", "EPS naechstes Jahr"),
                       ("free_cashflow", "Free Cashflow"),
                       ("shares_out", "Aktienanzahl")]:
        v = f.get(key)
        print(f"    {'OK ' if v not in (None, '', 0) else '-- '} {label}: {v}")

    # Jede Methode einzeln rechnen
    methods = {
        "justified_pe": V.justified_pe(f, preset),
        "ev_ebitda": V.multiple_ev_ebitda(f, None, preset),
        "dcf": V.dcf_two_stage(f, preset),
        "pb": V.multiple_pb(f, preset),
        "epv": V.epv(f, preset),
        "fwd_pe": V.fwd_pe(f, preset),
        "fwd_composite": V.fwd_composite(f, preset),
        "hist_pe": V.hist_pe(f, preset),
        "analyst": V.analyst_target(f),
    }
    weights = V._WEIGHTS.get(preset, V._WEIGHTS["quality"])

    print("\n  METHODEN EINZELN (x Kurs = Verhaeltnis zum aktuellen Kurs):")
    raw = {}
    for k, v in methods.items():
        in_preset = k in weights
        if v is None or v <= 0:
            print(f"    --   {k:14} kein Wert" +
                  ("" if in_preset else "   (im Playbook nicht gewichtet)"))
            continue
        ratio = (v / price) if price else 0
        mark = "OK " if in_preset else "-- "
        note = "" if in_preset else "   (im Playbook nicht gewichtet)"
        print(f"    {mark}  {k:14} {v:10.2f}   = {ratio:4.2f}x Kurs{note}")
        if in_preset:
            raw[k] = v

    if not raw:
        print("\n  -> keine gewichtete Methode verfuegbar.")
        return

    # Filter 1: Plausibilitaet 0.25x .. 4.0x Kurs
    sane = {k: v for k, v in raw.items()
            if not price or (0.25 * price <= v <= 4.0 * price)}
    dropped1 = [k for k in raw if k not in sane]
    if dropped1:
        print(f"\n  Filter 1 (Plausibilitaet 0,25x-4x Kurs) entfernt: {dropped1}")

    # Filter 2: Ausreisser gegen Median (nur ab 3 Methoden)
    core = dict(sane)
    if len(sane) >= 3:
        med0 = V._median(list(sane.values()))
        core = {k: v for k, v in sane.items()
                if med0 and (med0 / 2.0) <= v <= (med0 * 2.0)}
        dropped2 = [k for k in sane if k not in core]
        if len(core) < 2:
            core = dict(sane)
            print("  Filter 2 uebersprungen (sonst blieben <2 Methoden)")
        elif dropped2:
            print(f"  Filter 2 (Median-Band) entfernt: {dropped2}  "
                  f"(Median war {med0:.2f})")

    print(f"\n  -> {len(core)} Methoden bilden den Fair Value: {list(core)}")

    res = V.fair_value(f, None, preset)
    fv, up = res.get("fair_value"), res.get("upside")
    print(f"  fair_value = {fv}  (n_methods={res.get('n_methods')}, "
          f"reliable={res.get('reliable')}, spread={res.get('spread_pct')}%)")
    if fv and price:
        print(f"  Verhaeltnis Fair Value / Kurs: {fv / price:.2f}x  "
              f"(Upside {up:+.0f}%)" if up is not None else "")
        if fv / price > 1.6:
            print("  !! Auffaellig: mehr als 60 % Upside. Bei einem Standardwert")
            print("     wie BP/Shell ist das meist ein Modellfehler, kein Fund.")


def main():
    for tk in (sys.argv[1:] or DEFAULT):
        analyse(tk)
    print("\n" + "=" * 64)
    print("WORAUF ES ANKOMMT:")
    print("- 'Datenquellen': steht dort FMP? Wenn nicht, fehlt hist_pe_median")
    print("  systembedingt (nur FMP deep liefert es) - und der Gratis-Tarif")
    print("  von FMP deckt nur US ab.")
    print("- Welche Methoden liefern > 2x Kurs? Die treiben den Fair Value hoch.")
    print("- Was entfernen Filter 1 und 2? Wenn dort die NIEDRIGEN Werte")
    print("  rausfliegen und die hohen bleiben, ist der Filter das Problem.")


if __name__ == "__main__":
    main()
