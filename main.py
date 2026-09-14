#!/usr/bin/env python3
"""
main.py — Orchestrierung & CLI für das Value-Radar.

Befehle:
  screen  --universe FILE [--preset P]   Universum screenen + ranken
  score   --ticker T [--preset P]        Scoring eines Titels
  value   --ticker T [--preset P]        Bewertung (FairValue/Target/Einstieg)
  intel   --ticker T                     News/Peers/Supply-Chain/Insider
  report  --ticker T [--preset P]        Voller Einzelbericht (alles kombiniert)

Universe-Datei: ein Ticker pro Zeile (Zeilen mit # werden ignoriert).
Preset: quality | cyclical | inflection
"""
from __future__ import annotations
import argparse
import sys
import providers
import scoring
import valuation
import intel as intel_mod


def _load_universe(path: str) -> list[str]:
    out = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            t = line.strip()
            if t and not t.startswith("#"):
                out.append(t.split()[0].upper())
    return out


def _passes_screen(f: dict) -> bool:
    import config
    th = config.SCREEN_THRESHOLDS

    def le(key, cap):  # kleiner-gleich
        v = f.get(key)
        return v is None or v <= cap

    def ge(key, floor):  # groesser-gleich
        v = f.get(key)
        return v is None or v >= floor

    mc = f.get("market_cap")
    if mc is not None and mc < th["min_market_cap"]:
        return False
    checks = [
        le("ev_ebitda", th["max_ev_ebitda"]),
        le("pb", th["max_pb"]),
        ge("fcf_yield", th["min_fcf_yield"]),
        le("peg", th["max_peg"]),
        ge("roe", th["min_roic"]),  # ROE als ROIC-Proxy ohne Premiumdaten
        le("net_debt_ebitda", th["max_net_debt_ebitda"]),
        ge("current_ratio", th["min_current_ratio"]),
        ge("revenue_growth", th["min_revenue_growth"]),
    ]
    return all(checks)


def cmd_screen(args):
    tickers = _load_universe(args.universe)
    print(f"Lade {len(tickers)} Titel ...", file=sys.stderr)
    funds = []
    for t in tickers:
        f = providers.get_fundamentals(t)
        if f.get("price"):
            funds.append(f)
    # branchenrelatives Scoring innerhalb des geladenen Universums
    passed = [f for f in funds if _passes_screen(f)]
    print(f"{len(passed)}/{len(funds)} bestehen den Screen.\n", file=sys.stderr)

    scored = []
    for f in passed:
        peers = [p for p in funds if p.get("sector") == f.get("sector")
                 and p.get("ticker") != f.get("ticker")]
        s = scoring.score_stock(f, peers or None, preset=args.preset)
        scored.append(s)
    scored.sort(key=lambda x: x["composite"], reverse=True)

    print(f"{'Rank':<5}{'Ticker':<8}{'Score':<8}{'Sector':<22}{'Trap'}")
    print("-" * 60)
    for i, s in enumerate(scored, 1):
        trap = "!" if s["value_trap"] else ""
        print(f"{i:<5}{s['ticker']:<8}{s['composite']:<8}"
              f"{(s['sector'] or '')[:20]:<22}{trap}")


def cmd_score(args):
    f = providers.get_fundamentals(args.ticker)
    s = scoring.score_stock(f, None, preset=args.preset)
    print(f"\n{s['ticker']} ({s['name']}) — Preset: {args.preset}")
    print(f"Composite: {s['composite']}/100  ValueTrap: {s['value_trap']}")
    print("Kategorien:")
    for k, v in s["category_scores"].items():
        print(f"  {k:<12}{v}")


def cmd_value(args):
    f = providers.get_fundamentals(args.ticker)
    v = valuation.fair_value(f, None, preset=args.preset)
    print(f"\n{v['ticker']} — Bewertung ({args.preset})")
    print(f"  Kurs aktuell:    {v['price']}")
    print(f"  Fair Value:      {v['fair_value']}")
    print(f"  12M-Target:      {v['target_12m']}")
    print(f"  Einstieg (MoS {int(v['margin_of_safety']*100)}%): {v['entry_price']}")
    print(f"  Upside zu FV:    {v['upside_pct']}%")
    print(f"  WACC:            {v['wacc']}")
    print(f"  Reverse-DCF impl. Wachstum: {v['reverse_dcf_implied_growth']}")
    print(f"  Methoden: {v['methods']}")


def cmd_intel(args):
    data = intel_mod.gather(args.ticker)
    print(intel_mod.format_report(data))


def cmd_report(args):
    t = args.ticker
    f = providers.get_fundamentals(t)
    data = intel_mod.gather(t)
    f["_catalyst_score"] = data["catalyst_score"]  # Intel fliesst ins Scoring
    s = scoring.score_stock(f, None, preset=args.preset)
    v = valuation.fair_value(f, None, preset=args.preset)

    print("=" * 60)
    print(f" {f.get('name')} ({t})  |  {f.get('sector')} / {f.get('industry')}")
    print(f" Playbook-Preset: {args.preset}")
    print("=" * 60)
    print(f"\n[SCORING]  Composite {s['composite']}/100  "
          f"(ValueTrap: {s['value_trap']})")
    for k, val in s["category_scores"].items():
        print(f"   {k:<12}{val}")
    print(f"\n[BEWERTUNG]")
    print(f"   Kurs {v['price']} | FairValue {v['fair_value']} | "
          f"12M-Target {v['target_12m']} | Einstieg {v['entry_price']} "
          f"(MoS {int(v['margin_of_safety']*100)}%)")
    print(f"   Upside {v['upside_pct']}% | WACC {v['wacc']} | "
          f"Rev-DCF impl. g {v['reverse_dcf_implied_growth']}")
    print(f"   Methoden: {v['methods']}")
    print(intel_mod.format_report(data))
    print("\n" + "=" * 60)


def main():
    p = argparse.ArgumentParser(description="Value-Radar: Vor die Welle kommen.")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("screen"); sp.add_argument("--universe", required=True)
    sp.add_argument("--preset", default="quality")
    sp.set_defaults(func=cmd_screen)

    sc = sub.add_parser("score"); sc.add_argument("--ticker", required=True)
    sc.add_argument("--preset", default="quality"); sc.set_defaults(func=cmd_score)

    sv = sub.add_parser("value"); sv.add_argument("--ticker", required=True)
    sv.add_argument("--preset", default="quality"); sv.set_defaults(func=cmd_value)

    si = sub.add_parser("intel"); si.add_argument("--ticker", required=True)
    si.set_defaults(func=cmd_intel)

    sr = sub.add_parser("report"); sr.add_argument("--ticker", required=True)
    sr.add_argument("--preset", default="quality"); sr.set_defaults(func=cmd_report)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
