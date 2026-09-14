"""
warum_fair_value.py - Warum ist der Fair Value so, wie er ist?

    python3 warum_fair_value.py NVDA
    python3 warum_fair_value.py NVDA --flach     # Scan-Pfad statt Einzelanalyse

Zeigt die komplette Kette in einer Ausgabe:
  Schluessel -> Datenquellen -> fehlende Felder -> Playbook -> jede Methode
  einzeln -> Gewichte -> Fair Value. Und zusaetzlich, was das Ergebnis WAERE,
  wenn die fehlenden Felder da waeren.

Gedacht fuer den Fall "Titel X zeigt ploetzlich -65 %": danach ist klar, ob
das Modell so rechnet oder ob Daten fehlen.
"""

import sys

import config
import providers
import valuation

METHODEN = ["justified_pe", "fwd_pe", "fwd_composite", "hist_pe",
            "ev_ebitda", "pb", "epv", "dcf", "analyst"]


def _method_werte(f, preset):
    """Ruft jede Methode einzeln auf - robust gegen unterschiedliche Signaturen."""
    out = {}
    for m in METHODEN:
        fn = None
        for kandidat in (m, f"multiple_{m}", f"{m}_wert", f"{m}_number"):
            fn = getattr(valuation, kandidat, None)
            if callable(fn):
                break
        if not callable(fn):
            out[m] = None
            continue
        for args in ((f, None, preset), (f, preset), (f, None), (f,)):
            try:
                r = fn(*args)
                out[m] = round(r, 2) if isinstance(r, (int, float)) else None
                break
            except TypeError:
                continue
            except Exception:
                out[m] = None
                break
    if f.get("target_mean"):
        out["analyst"] = f["target_mean"]
    return out


def main(ticker, deep=True):
    print(f"{'=' * 78}\nWARUM {ticker}?  (Pfad: {'Einzelanalyse deep=True' if deep else 'Scan deep=False'})\n{'=' * 78}")

    print("\n1) Schluessel")
    for n in ("ROIC_API_KEY", "FINNHUB_API_KEY", "FMP_API_KEY", "TIINGO_API_KEY"):
        q = (config.schluessel_quelle(n) if hasattr(config, "schluessel_quelle")
             else ("gesetzt" if getattr(config, n, "") else "FEHLT"))
        print(f"   {n:18s} {q}")
    if not getattr(config, "ROIC_API_KEY", ""):
        print("   ACHTUNG: roic ist inaktiv. Wenn der Schluessel in "
              ".streamlit/secrets.toml steht, dieses Skript AUS dem Projektordner "
              "starten - sonst wird die Datei nicht gefunden und die App rechnet "
              "mit anderen Daten als dieses Skript.")

    f = providers.get_fundamentals(ticker, deep=deep) or {}
    if not f:
        print("\n   Keine Daten - Abbruch.")
        return

    print("\n2) Quellen")
    q = f.get("_feldquellen") or {}
    if q:
        from collections import Counter
        for k, n in Counter(q.values()).most_common():
            print(f"   {k:22s} {n} Felder")
    print(f"   roic aktiv:          {bool(f.get('_roic'))}")
    if f.get("_roic_felder"):
        print(f"   davon von roic:      {len(f['_roic_felder'])} Felder")
    if f.get("_fmp_luecken"):
        print(f"   von FMP nachgeladen: {', '.join(f['_fmp_luecken'])}")
    if f.get("_offene_luecken"):
        print(f"   WEITERHIN OFFEN:     {', '.join(f['_offene_luecken'])}")

    print("\n3) Einstufung")
    for k in ("sector", "industry", "revenue_growth", "earnings_growth", "_ist_zyklisch"):
        print(f"   {k:18s} {f.get(k)}")
    preset = valuation.classify_playbook(f)
    print(f"   -> Playbook          {preset}")
    if f.get("revenue_growth") is None and f.get("earnings_growth") is None:
        print("   ACHTUNG: ohne Wachstumsdaten faellt jeder Wachstumstitel auf 'quality' "
              "- mit ganz anderen Gewichten.")

    print("\n4) Methoden einzeln")
    preis = f.get("price")
    werte = _method_werte(dict(f), preset)
    gew = valuation._WEIGHTS.get(preset, {})
    for m in METHODEN:
        w = werte.get(m)
        g = gew.get(m)
        marke = f"  Gewicht {g:.0%}" if g else ""
        if w and preis:
            print(f"   {m:15s} {w:10.2f}  ({w / preis - 1:+7.1%}){marke}")
        else:
            print(f"   {m:15s} {'--':>10s}  {'':>10s}{marke}"
                  + ("   <-- faellt aus!" if g else ""))

    print("\n5) Ergebnis")
    v = valuation.fair_value(dict(f), None, preset)
    print(f"   Kurs        {preis}")
    print(f"   Fair Value  {v.get('fair_value')}   Upside {v.get('upside_pct')} %")
    print(f"   Einstieg    {v.get('entry_price')}  (MoS {v.get('margin_of_safety')})")
    dq = v.get("datenqualitaet") or {}
    print(f"   Datenbasis  {dq.get('stufe')}")
    for w in dq.get("warnungen", []):
        print(f"     ! {w}")
    h = v.get("herkunft") or {}
    if h.get("nach_herkunft"):
        print("   Herkunft:   " + " | ".join(f"{k} {a:.0%}"
                                             for k, a in h["nach_herkunft"].items()))

    print("\n6) Rohdaten (alle Felder, die in die Rechnung gehen)")
    for k in sorted(f):
        if k.startswith("_") and k not in ("_roic", "_roic_fx", "_ist_zyklisch",
                                           "_offene_luecken", "_fmp_luecken"):
            continue
        val = f[k]
        if isinstance(val, (list, dict)):
            val = f"<{type(val).__name__}, {len(val)} Eintraege>"
        elif isinstance(val, str) and len(val) > 60:
            val = val[:60] + "..."
        print(f"   {k:24s} {val}")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    tief = "--flach" not in sys.argv
    datei = "--datei" in sys.argv

    if datei:
        import io
        puffer = io.StringIO()
        echt = sys.stdout
        sys.stdout = puffer
    try:
        for t in (args or ["NVDA"]):
            main(t.upper(), deep=tief)
    finally:
        if datei:
            sys.stdout = echt
            name = f"warum_{'_'.join(a.upper() for a in (args or ['NVDA']))}.txt"
            with open(name, "w", encoding="utf-8") as fh:
                fh.write(puffer.getvalue())
            print(puffer.getvalue())
            print(f"\n-> auch gespeichert in {name}")
