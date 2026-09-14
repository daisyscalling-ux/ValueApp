"""
test_bewertung_diagnose.py - Selbsttest der Bewertungserweiterung gegen valuation.py.

    python3 test_bewertung_diagnose.py

Nutzt ein fund-Dict mit den ETN-Zahlen vom 25.08.2026 (aus den AlphaSpread-
Screenshots). Kein Netzwerk, keine API-Keys.
"""

import valuation
import relval
import schaetzguete

PREIS = 409.52
MCAP = 159_000_000_000
SHARES = MCAP / PREIS

ETN = {
    "ticker": "ETN", "price": PREIS, "market_cap": MCAP, "shares_out": SHARES,
    "free_cashflow": 3.9e9, "ebitda": 6.4e9, "net_income": 3.8e9,
    "revenue": 30.0e9, "net_debt": 8.0e9, "total_debt": 10.5e9,
    "eps_trailing": 9.83, "eps_forward": 11.80, "book_value_ps": 48.0,
    "revenue_growth": 0.05, "earnings_growth": -0.04,
    "beta": 1.05, "roe": 0.215, "gross_margin": 0.385,
    "operating_margin": 0.177, "net_debt_ebitda": 1.25, "current_ratio": 1.5,
    "sector": "Industrials", "industry": "Specialty Industrial Machinery",
    "ev_ebitda": 26.1, "pb": 8.5, "target_mean": 469.11, "analyst_count": 24,
    "hist_pe_median": 22.4, "roic": 0.135,
    "total_equity": 18.6e9, "total_assets": 42.0e9,
}

PRESET = valuation.classify_playbook(ETN)
print("=" * 76)
print(f"Playbook automatisch erkannt: {PRESET}")

# ---------------------------------------------------------------------------
print("=" * 76)
print("1) fair_value() mit den neuen Feldern")
v = valuation.fair_value(ETN, None, PRESET)
print(f"   Fair Value          {v['fair_value']:>9.2f}   Upside {v['upside_pct']:+.1f} %")
print(f"   Einstieg (MoS {v['margin_of_safety']:.0%})  {v['entry_price']:>9.2f}")
print(f"   Methoden            {v['methods']}")

h = v.get("herkunft")
print("\n   HERKUNFT des Fair Value:")
for k, a in h["nach_herkunft"].items():
    print(f"     {valuation.HERKUNFT_LABEL[k]:22s} {a:6.1%}")
for hin in h["hinweise"]:
    print("     !", hin)

d = v.get("dcf_diagnose")
if d:
    print("\n   DCF-DIAGNOSE:")
    print(f"     DCF-Wert                 {d['wert_je_aktie']:>8.2f}")
    print(f"     Terminalwert-Anteil      {d['terminal_anteil']:>8.1%}")
    print(f"     Terminal-Multiple Modell {d['multiple_genutzt']:>8.1f}x")
    print(f"     ... vom Kurs verlangt    {d['multiple_impliziert']:>8.1f}x")
    print(f"     Heutiges FCF-Multiple    {d['multiple_heute']:>8.1f}x")
    for hin in d["hinweise"]:
        print("     !", hin)

# ---------------------------------------------------------------------------
print("=" * 76)
print("2) Reverse DCF, regime-bewusst")
umsatz = [20.1e9, 17.9e9, 19.6e9, 20.8e9, 23.2e9, 24.9e9, 26.5e9, 28.6e9, 30.0e9]
anker = valuation.wachstums_anker(umsatz, konsens=0.131)
print("   Anker:", {k: (f"{x:.1%}" if x else None) for k, x in anker.items()})
for pb in ("quality", "cyclical", "inflection", "financial"):
    k = valuation.rd_korridor(anker, pb)
    print(f"   Korridor {pb:11s} {k.tief:6.1%} - {k.hoch:6.1%}  (Mitte {k.mitte:5.1%})")

rd = valuation.reverse_dcf_analyse(ETN, anker, PRESET)
print(f"\n   Eingepreistes Startwachstum {rd['impliziertes_wachstum']:.1%}")
print(f"   Eingepreiste Cash-Basis     {rd['implizierte_cash_basis']:.2f}x heutiger FCF")
print(f"   Urteil                      {rd['urteil_titel']} [{rd['urteil_ton']}]")
print(f"   Beide gestreckt?            {rd['beide_gestreckt']}")
print(f"   Zweitmeinung (Konstant-g)   "
      f"{valuation.reverse_dcf_implied_growth(ETN):.1%}")
for hin in rd["hinweise"]:
    print("   ·", hin)
print("   Referenztabelle:")
for z in rd["zeilen"]:
    w = f"{z['wert']:8.2f}" if z["wert"] else "     n/a"
    u = f"{z['upside']:+6.0f}%" if z["upside"] is not None else "    n/a"
    print(f"     {z['label']:22s} {z['treiber']:6.1%} -> {w} {u}  "
          f"{'im Korridor' if z['im_korridor'] else 'ausserhalb'}")
print("   Iso-Linie (Cash-Basis -> noetiges Wachstum):")
g = rd["gitter"]
for i in range(0, len(g["cash_basis"]), 2):
    iso = g["iso_wachstum"][i]
    txt = f"{iso:6.1%}" if iso is not None else "nicht erreichbar"
    print(f"     {g['cash_basis'][i]:.2f}x FCF -> {txt}")

# ---------------------------------------------------------------------------
print("=" * 76)
print("3) Szenarien je Methode")
m = valuation.szenario_matrix(ETN, None, PRESET)
for k, zeile in m["methoden"].items():
    print(f"   {k:14s} " + "  ".join(
        f"{sz}={zeile.get(sz):8.2f}" if zeile.get(sz) else f"{sz}=     n/a"
        for sz in ("bear", "base", "bull")))
print(f"   {'BLEND':14s} " + "  ".join(
    f"{sz}={m['blend'][sz]:8.2f}" for sz in ("bear", "base", "bull")))
print(f"   Upside         " + "  ".join(
    f"{sz}={m['upside'][sz]:+7.1f}%" for sz in ("bear", "base", "bull")))
print(f"   Spanne {m['spanne_pct']:.0f} % · Kurs liegt bei {m['kurs_position']:.0f} % "
      f"der Spanne · Treiber {m['treiber']}")

# ---------------------------------------------------------------------------
print("=" * 76)
print("4) Bewertungshistorie (echtes Perzentil)")
pe_hist = {"median": 22.4, "n": 10,
           "werte": [14.2, 16.8, 18.1, 19.5, 21.0, 22.4, 24.9, 28.6, 33.1, 38.5],
           "jahre": [str(j) for j in range(2016, 2026)]}
b = relval.bericht(ETN, pe_hist,
                               ev_hist=[9.1, 10.4, 11.2, 12.8, 13.9, 15.1, 17.6,
                                        20.2, 23.4, 26.8])
kg = b["kgv"]
print(f"   KGV jetzt {kg['kgv_jetzt']:.1f} · Median {kg['median']:.1f} "
      f"-> {kg['perzentil']['teuer_pct']:.0f}. Perzentil "
      f"({kg['perzentil']['n']} Jahre)")
print(f"   Rueckkehrwert (Median x EPS) {kg['rueckkehrwert']:.2f}")
ev = b["ev_ebitda"]
print(f"   EV/EBITDA jetzt {ev['jetzt']:.1f} -> {ev['perzentil']['teuer_pct']:.0f}. "
      f"Perzentil · Rueckkehrwert {ev['rueckkehrwert']}")
print(f"   Urteil: {b['urteil']['label']} - {b['urteil']['text']}")
print(f"   Multiple-Band fuer Szenarien: {b['band']}")

print(f"   Alte Schaetzung (relval): {relval.historical_band(ETN)['pe_pctile']}. Perzentil "
      f"({relval.historical_band(ETN)['pctile_quelle']})")

# ---------------------------------------------------------------------------
print("=" * 76)
print("5) Schaetzguete")
paare = [(2.30, 2.36), (2.42, 2.48), (2.55, 2.62), (2.60, 2.58), (2.72, 2.78),
         (2.85, 2.91), (2.90, 2.95), (3.02, 3.05), (3.10, 3.04), (3.15, 3.09),
         (2.98, 2.86), (2.60, 2.45)]
q = schaetzguete.auswerten(paare)
print(f"   {q['n']} Quartale · {q['sterne']} Sterne · Score {q['score']:.0f} "
      f"· {q['label']}")
print(f"   Trefferquote {q['trefferquote']:.0%} · mittlere Abweichung "
      f"{q['mittlere_abweichung']:+.2%} · Bias {q['bias']}")
bl = schaetzguete.geblendetes_eps(11.80, [5.15, 6.14, 7.47, 8.47, 9.50, 10.06, 9.83], q)
print(f"   Konsens {bl['konsens']} · Trend {bl['trend']} · Gewicht "
      f"{bl['gewicht']:.0%} -> geblendet {bl['eps']}")

# Wirkung auf den Fair Value
f2 = dict(ETN)
schaetzguete.anwenden_auf_fund(f2, q, [5.15, 6.14, 7.47, 8.47, 9.50, 10.06, 9.83])
v2 = valuation.fair_value(f2, None, PRESET)
print(f"   Fair Value mit geblendetem EPS: {v2['fair_value']:.2f} "
      f"(vorher {v['fair_value']:.2f})")

# ---------------------------------------------------------------------------
print("=" * 76)
print("6) Cash-Conversion")
cc = valuation.conversion_aus_historie(
    [2.4e9, 2.5e9, 2.6e9, 3.0e9, 3.5e9, 3.9e9],
    [2.2e9, 2.1e9, 2.4e9, 3.2e9, 3.9e9, 3.8e9])
print(f"   Median {cc['median']:.0%} · Streuung {cc['streuung']:.2f} "
      f"· Spanne {cc['min']:.2f}-{cc['max']:.2f}")
print(f"   Warnung: {cc['warnung']}")

print("=" * 76)
print("OK - alle Bausteine laufen gegen die echte valuation.py")
