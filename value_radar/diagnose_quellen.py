"""
diagnose_quellen.py - Warum weicht ein Fair Value ab?

    python3 diagnose_quellen.py NVDA MU C

Prueft der Reihe nach:
  1. Welche API-Schluessel sind gesetzt?
  2. Welche kritischen fund-Felder kommen tatsaechlich an?
  3. Welches Playbook wird daraus abgeleitet - und haelt die Ableitung?
  4. Wie stark aendert sich der Fair Value, wenn die Zusatzquellen wegfallen?

Gedacht fuer genau den Fall, in dem ein Titel "ploetzlich" 50 % Downside zeigt.
"""

import sys

import config
import providers
import valuation

KRITISCH = [
    ("revenue_growth", "Playbook-Einstufung"),
    ("earnings_growth", "Playbook-Einstufung"),
    ("eps_forward", "fwd_pe / fwd_composite / hist_pe"),
    ("eps_trailing", "justified_pe"),
    ("hist_pe_median", "hist_pe"),
    ("ebitda", "ev_ebitda"),
    ("ev_ebitda", "ev_ebitda"),
    ("free_cashflow", "dcf"),
    ("book_value_ps", "pb"),
    ("target_mean", "analyst"),
    ("roe", "justified_pe"),
    ("gross_margin", "justified_pe"),
]


def schluessel():
    print("1) API-Schluessel")
    fehlt = config.fehlende_keys() if hasattr(config, "fehlende_keys") else []
    for name in ("FINNHUB_API_KEY", "FMP_API_KEY", "TIINGO_API_KEY", "ROIC_API_KEY"):
        gesetzt = bool(getattr(config, name, ""))
        print(f"   {name:20s} {'gesetzt' if gesetzt else 'FEHLT'}")
    if "FMP_API_KEY" in fehlt or "FINNHUB_API_KEY" in fehlt:
        print("   ACHTUNG: Ohne FMP/Finnhub fehlen Wachstums- und Multiple-Felder.")
        print("   Dann kippt die Playbook-Einstufung und der Fair Value faellt "
              "bei Wachstumstiteln deutlich.")
    print()


def titel(t):
    print(f"2) {t}")
    try:
        f = providers.get_fundamentals(t, deep=True)   # deep: roic voll + Lueckenfueller
    except Exception as e:
        print(f"   Abruf fehlgeschlagen: {e}\n")
        return
    if not f:
        print("   Keine Daten.\n")
        return

    fehlend = [(k, m) for k, m in KRITISCH if f.get(k) in (None, 0)]
    print(f"   Kurs {f.get('price')}  Sektor {f.get('sector')}")
    if fehlend:
        print("   Fehlende Felder:")
        for k, m in fehlend:
            print(f"     - {k:18s} -> betrifft {m}")
    else:
        print("   Alle kritischen Felder vorhanden.")

    qs = f.get("_feldquellen") or {}
    if qs:
        from collections import Counter
        z = Counter(qs.values())
        print("   Feldquellen: " + " | ".join(f"{k} {v}" for k, v in z.most_common()))
    if f.get("_fmp_luecken"):
        print(f"   Von FMP nachgeladen: {', '.join(f['_fmp_luecken'])}")
    if f.get("_offene_luecken"):
        print(f"   Weiterhin offen:     {', '.join(f['_offene_luecken'])}")

    preset = valuation.classify_playbook(f)
    v = valuation.fair_value(f, None, preset)
    dq = v.get("datenqualitaet") or {}
    print(f"   Playbook {preset} | Fair Value {v.get('fair_value')} "
          f"({v.get('upside_pct'):+.1f} %) | Methoden {list(v.get('methods') or {})}")
    print(f"   Datenbasis: {dq.get('stufe', '?')}")
    for w in dq.get("warnungen", []):
        print(f"     ! {w}")

    # Gegenprobe: was passiert ohne die Zusatzquellen?
    g = dict(f)
    for k in ("revenue_growth", "earnings_growth", "hist_pe_median", "ev_ebitda",
              "roe", "gross_margin", "operating_margin", "current_ratio", "pb",
              "book_value_ps", "beta", "eps_trailing"):
        g[k] = None
    p2 = valuation.classify_playbook(g)
    v2 = valuation.fair_value(g, None, p2)
    if v.get("fair_value") and v2.get("fair_value"):
        d = (v2["fair_value"] - v["fair_value"]) / v["fair_value"] * 100
        print(f"   Ohne FMP/Finnhub waere es: Playbook {p2}, Fair Value "
              f"{v2['fair_value']} ({v2['upside_pct']:+.1f} %) -> {d:+.0f} %")
    print()


if __name__ == "__main__":
    schluessel()
    for t in (sys.argv[1:] or ["NVDA", "MU", "C"]):
        titel(t.upper())
