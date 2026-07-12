"""
scorecard.py — Kauf-Scorecard.

Wendet die Entscheidungskette aus der Anleitung automatisch auf eine Aktie an:
6 Pflicht-Gates (alle muessen erfuellt sein) + 5 Bonuspunkte (Ziel >= 3).

Urteil:
  Kaufkandidat        : alle Pflicht-Gates erfuellt UND >= 3 Bonuspunkte
  Solide - Watchlist  : alle Pflicht-Gates erfuellt, aber < 3 Bonus
  Knapp - Watchlist   : genau 1 Pflicht-Gate verfehlt
  Verwerfen           : >= 2 Pflicht-Gates verfehlt
"""
from __future__ import annotations


def _analyst_positive(analyst, fund):
    a = analyst or {}
    buy, sell = a.get("buy"), a.get("sell")
    if buy is not None and sell is not None and (buy + sell) > 0:
        return buy > sell
    target = a.get("target_mean") or fund.get("target_mean")
    price = fund.get("price")
    if target and price:
        return target > price
    return None


def evaluate(fund, valu, composite, m1_total, m2_total,
             extras=None, insider=None, analyst=None, radar_score=None) -> dict:
    extras = extras or {}
    price = fund.get("price")
    upside = valu.get("upside_pct")
    spread = valu.get("spread_pct")
    peg = fund.get("peg")
    above_sma = extras.get("above_sma200")
    rsi = extras.get("rsi")
    base = extras.get("base_formed")
    buys = (insider or {}).get("recent_buys")
    sells = (insider or {}).get("recent_sells")
    analyst_pos = _analyst_positive(analyst, fund)

    mand = []

    def g(label, ok, detail):
        mand.append({"label": label, "ok": bool(ok), "detail": detail})

    g("Composite Score \u2265 55",
      composite is not None and composite >= 55,
      f"{composite:.0f}/100" if composite is not None else "keine Daten")

    # Matrix 1 = Setup/Timing (Chart, Revisionen, Volumen), NICHT eine zweite
    # Qualitaetspruefung - die steckt schon im Composite. Fehlt die Datenbasis,
    # gibt es keinen Wert (frueher: fehlende Daten zaehlten als "neutral" und
    # eine datenlose Aktie kam auf 29/45).
    g("Matrix 1 (Setup) \u2265 30 \u2013 mit belastbarer Datenbasis",
      m1_total is not None and m1_total >= 30,
      f"{m1_total}/45" if m1_total is not None
      else "zu wenig Daten \u2013 kein Setup-Urteil m\u00f6glich")

    reliable = valu.get("reliable", True)
    up_detail = f"{upside:+.1f} %" if upside is not None else "kein Fair Value"
    if upside is not None and not reliable:
        up_detail += " (Fair Value unsicher \u2013 gekappt/streuend)"
    g("Upside \u2265 +15 % (belastbarer Fair Value)",
      upside is not None and upside >= 15 and reliable,
      up_detail)

    g("Bewertungs-Streuung \u2264 60 %",
      spread is not None and spread <= 60,
      f"{spread:.0f} %" if spread is not None else "n/a")

    # Insider-VERKAEUFE sind KEIN Pflichtkriterium mehr (jetzt Bonus).
    # Begruendung: Verkaeufe sind verrauscht - Insider verkaufen aus vielen Gruenden
    # (Steuern, Diversifikation, Hauskauf). Aussagekraeftig sind vor allem KAEUFE.
    # Zudem fehlen Insiderdaten bei den Gratis-Quellen meist, wodurch das Kriterium
    # ohnehin fast immer "bestanden" war - es filterte also praktisch nichts.

    trend_bits = []
    if above_sma is not None:
        trend_bits.append("\u00fcber SMA200" if above_sma else "unter SMA200")
    if base:
        trend_bits.append("Boden gebildet")
    g("Kurs > SMA200 oder Boden gebildet", bool(above_sma) or bool(base),
      ", ".join(trend_bits) or "keine Technik-Daten")

    bonus = []

    def b_(label, ok, detail):
        bonus.append({"label": label, "ok": bool(ok), "detail": detail})

    b_("Matrix 2 \u2265 70",
       m2_total is not None and m2_total >= 70,
       f"{m2_total:.0f}/100" if m2_total is not None else "n/a")

    if buys is None and sells is None:
        b_("Insider: keine massiven Verk\u00e4ufe", False, "keine Insider-Daten")
    else:
        _b, _s = buys or 0, sells or 0
        b_("Insider: keine massiven Verk\u00e4ufe", not (_s >= 5 and _s > _b * 2),
           f"{_b} K\u00e4ufe / {_s} Verk\u00e4ufe")
    if buys:
        b_("Insider kaufen", (buys or 0) > (sells or 0),
           f"{buys} K\u00e4ufe / {sells or 0} Verk\u00e4ufe")

    b_("Radar-Score \u2265 60",
       radar_score is not None and radar_score >= 60,
       f"{radar_score:.0f}" if radar_score is not None else "nicht gescannt")

    b_("PEG < 1",
       peg is not None and 0 < peg < 1,
       f"{peg:.2f}" if peg else "n/a")

    b_("Analystenrating positiv",
       bool(analyst_pos),
       ("ja" if analyst_pos else "nein") if analyst_pos is not None else "n/a")

    has_buys = (buys or 0) > 0 and (buys or 0) >= (sells or 0)
    b_("Insiderk\u00e4ufe vorhanden", has_buys,
       f"{buys or 0} K\u00e4ufe / {sells or 0} Verk\u00e4ufe"
       if (buys is not None or sells is not None) else "keine Daten")

    # RSI-Warnung (kein Gate, nur Hinweis)
    rsi_warn = (rsi is not None and rsi >= 70)

    mand_pass = sum(1 for x in mand if x["ok"])
    all_pass = mand_pass == len(mand)
    bonus_count = sum(1 for x in bonus if x["ok"])
    failed = len(mand) - mand_pass

    if all_pass and bonus_count >= 3:
        verdict, vkey = "Kaufkandidat", "buy"
    elif all_pass:
        verdict, vkey = "Solide \u2013 Watchlist", "watch"
    elif failed == 1:
        verdict, vkey = "Knapp \u2013 Watchlist", "watch"
    else:
        verdict, vkey = "Verwerfen", "drop"

    return {
        "verdict": verdict, "vkey": vkey,
        "mandatory": mand, "bonus": bonus,
        "mand_pass": mand_pass, "mand_total": len(mand),
        "bonus_count": bonus_count, "bonus_total": len(bonus),
        "rsi_warn": rsi_warn, "rsi": rsi,
        "entry_price": valu.get("entry_price"),
        "fair_value": valu.get("fair_value"),
        "upside": upside,
    }
