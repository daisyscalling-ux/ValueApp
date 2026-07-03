"""
screener_presets.py — fertige Screening-Vorlagen fuer den Screener-Tab.

Jede Vorlage ist eine Liste von Kriterien. Typen:
  hard : muss erfuellt sein, sonst faellt die Aktie raus
         (fehlt der Wert komplett, gilt das Kriterium als NICHT erfuellt)
  soft : zaehlt in die "Fit"-Quote ein (z. B. 7/9), filtert aber nicht hart

Wir nutzen nur Kennzahlen, die ueber Yahoo/Finnhub verlaesslich verfuegbar sind.
Wo eine Idealkennzahl fehlt (z. B. echtes 5-Jahres-Wachstum, Eigenkapitalquote),
nutzen wir eine dokumentierte Naeherung (TTM-Wachstum, Verschuldungsgrad).
"""
from __future__ import annotations


def _mcap_eur(fd):
    return (fd.get("market_cap") or 0) * (fd.get("_fx") or 1.0)


def _pe(fd):
    p = fd.get("pe_forward") or fd.get("pe_trailing")
    return p if (p and p > 0) else None


# Ein Kriterium: (key, label, typ, test(fd, ex, fv) -> bool|None)
#   fd = Fundamentaldaten, ex = Technik-Extras, fv = Bewertungsergebnis
def _crit(key, label, typ, test):
    return {"key": key, "label": label, "type": typ, "test": test}


PRESETS = {
    "Value & Qualit\u00e4t": {
        "desc": "Solide, profitable Unternehmen zu vern\u00fcnftigem Preis "
                "(KGV, Graham-Produkt, Wachstum, Substanz).",
        "playbook": "quality",
        "criteria": [
            _crit("mcap", "Marktkap. > 2 Mrd. \u20ac", "hard",
                  lambda fd, ex, fv: _mcap_eur(fd) > 2e9),
            _crit("pe", "KGV < 25", "hard",
                  lambda fd, ex, fv: _pe(fd) is not None and _pe(fd) < 25),
            _crit("pe_pb", "KGV \u00d7 KBV \u2264 50 (Graham)", "hard",
                  lambda fd, ex, fv: _pe(fd) and fd.get("pb") and 0 < _pe(fd) * fd["pb"] <= 50),
            _crit("eps_pos", "Gewinn positiv (EPS > 0)", "hard",
                  lambda fd, ex, fv: (fd.get("eps_trailing") or fd.get("eps_forward") or 0) > 0),
            _crit("fcf_pos", "Free Cashflow positiv", "hard",
                  lambda fd, ex, fv: (fd.get("free_cashflow") or 0) > 0),
            _crit("growth", "Erw. Gewinnwachstum > 10 %", "soft",
                  lambda fd, ex, fv: (fd.get("earnings_growth") or fd.get("revenue_growth") or -1) > 0.10),
            _crit("undervalued", "Kurs unter fairem Wert", "soft",
                  lambda fd, ex, fv: fv.get("upside_pct") is not None and fv["upside_pct"] > 0),
            _crit("peg", "PEG < 1 (g\u00fcnstiges Wachstum)", "soft",
                  lambda fd, ex, fv: fd.get("peg") is not None and 0 < fd["peg"] < 1),
            _crit("div", "Dividende seit \u2265 8 Jahren", "soft",
                  lambda fd, ex, fv: (fd.get("dividend_years") or 0) >= 8),
            _crit("moat", "Starke Marktposition (Bruttomarge > 40 %, ROE > 12 %)", "soft",
                  lambda fd, ex, fv: (fd.get("gross_margin") or 0) > 0.40 and (fd.get("roe") or 0) > 0.12),
            _crit("trend", "Kurs > SMA200 und RSI < 70", "soft",
                  lambda fd, ex, fv: ex.get("above_sma200") is True
                  and ex.get("rsi") is not None and ex["rsi"] < 70),
            _crit("analyst", "Analystenrating positiv", "soft",
                  lambda fd, ex, fv: (fd.get("recommendation") or "").lower()
                  in ("buy", "strong_buy", "strongbuy", "outperform", "overweight")
                  or (fd.get("target_mean") and fd.get("price") and fd["target_mean"] > fd["price"])),
        ],
    },
    "Turnaround / Comeback": {
        "desc": "Gro\u00dfe, gesunde Firmen, die gefallen sind und einen Boden bilden "
                "(Substanz + Cashflow vorhanden).",
        "playbook": "quality",
        "criteria": [
            _crit("mcap", "Marktkap. > 10 Mrd. \u20ac", "hard",
                  lambda fd, ex, fv: _mcap_eur(fd) > 10e9),
            _crit("p12", "12-Monats-Performance \u221250 % bis \u221210 %", "hard",
                  lambda fd, ex, fv: ex.get("ch_1y") is not None and -50 <= ex["ch_1y"] <= -10),
            _crit("p6", "6-Monats-Performance \u2264 +10 %", "hard",
                  lambda fd, ex, fv: ex.get("ch_6m") is not None and ex["ch_6m"] <= 10),
            _crit("p1", "1-Monats-Performance \u2265 \u221210 %", "hard",
                  lambda fd, ex, fv: ex.get("ch_1m") is not None and ex["ch_1m"] >= -10),
            _crit("pe", "KGV < 30", "hard",
                  lambda fd, ex, fv: _pe(fd) is not None and _pe(fd) < 30),
            _crit("ps", "KUV < 8", "hard",
                  lambda fd, ex, fv: (fd.get("ps") or fd.get("ev_sales")) is not None
                  and (fd.get("ps") or fd.get("ev_sales")) < 8),
            _crit("ev_ebitda", "EV/EBITDA < 20", "hard",
                  lambda fd, ex, fv: fd.get("ev_ebitda") is not None and 0 < fd["ev_ebitda"] < 20),
            _crit("rev_g", "Umsatzwachstum > 0 % (TTM)", "hard",
                  lambda fd, ex, fv: (fd.get("revenue_growth") or -1) > 0),
            _crit("ocf", "Operativer Cashflow positiv", "hard",
                  lambda fd, ex, fv: (fd.get("operating_cashflow") or 0) > 0),
            _crit("fcf", "Free Cashflow positiv", "hard",
                  lambda fd, ex, fv: (fd.get("free_cashflow") or 0) > 0),
            _crit("earn_g", "Gewinnwachstum > 0 % (TTM)", "soft",
                  lambda fd, ex, fv: (fd.get("earnings_growth") or -1) > 0),
            _crit("debt", "Moderate Verschuldung (D/E < 1,5)", "soft",
                  lambda fd, ex, fv: fd.get("debt_to_equity") is not None
                  and fd["debt_to_equity"] / 100 < 1.5),
            _crit("base", "Boden gebildet (nach Rueckgang stabilisiert)", "soft",
                  lambda fd, ex, fv: ex.get("base_formed") is True),
        ],
    },
}


def needs_extras(preset_key) -> bool:
    return True


def needs_dividends(preset_key) -> bool:
    return any(c["key"] == "div" for c in PRESETS[preset_key]["criteria"])


def evaluate(preset_key, fd, ex, fv) -> dict:
    crits = PRESETS[preset_key]["criteria"]
    res, hard_ok = [], True
    soft_pass = soft_total = 0
    for c in crits:
        try:
            ok = bool(c["test"](fd, ex or {}, fv or {}))
        except Exception:
            ok = False
        res.append((c["label"], c["type"], ok))
        if c["type"] == "hard" and not ok:
            hard_ok = False
        if c["type"] == "soft":
            soft_total += 1
            soft_pass += 1 if ok else 0
    return {"passed": hard_ok, "soft_pass": soft_pass, "soft_total": soft_total, "detail": res}
