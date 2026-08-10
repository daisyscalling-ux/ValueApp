# -*- coding: utf-8 -*-
"""backtest.py - Ehrlicher historischer Bewertungs-Backtest.

Prueft ZWEI Fragen GETRENNT:

  Frage 1 (Treffsicherheit): Kommt der Kurs dem damals berechneten Fair Value
           naeher? Wenn das Tool "fair = 100, Kurs = 70" sagte, stieg der Kurs
           dann Richtung 100?

  Frage 2 (Rendite): Haetten die Titel mit hohem Upside den Markt geschlagen?

KERNPRINZIP - kein Look-ahead-Bias:
  roic liefert Geschaeftsjahres-Daten, aber KEIN Veroeffentlichungsdatum.
  Ein FY2020-Bericht erscheint aber erst ~Feb/Maerz 2021. Wir behandeln
  Jahreszahlen daher erst VEROEFFENTLICHUNGS_PUFFER_MONATE nach dem
  Geschaeftsjahresende als "bekannt". Lieber zu spaet als zu frueh - sonst
  betruegt sich der Backtest selbst und sieht besser aus als die Realitaet.

Das Modul ist eigenstaendig und beruehrt die Kern-Bewertung nicht. Es nutzt
NUR roic-Rohdaten (Fundamentaldaten + Kurshistorie) und unsere echte
valuation.fair_value-Logik - so testen wir das TATSAECHLICHE Tool, nicht
eine Nachbildung.
"""
from __future__ import annotations
import datetime as _dt

# Sicherheitspuffer: erst so viele Monate nach Geschaeftsjahresende gelten die
# Jahreszahlen als oeffentlich bekannt. 4 Monate deckt die allermeisten
# Berichtsfristen ab (US 10-K: 60-90 Tage, EU teils laenger).
VEROEFFENTLICHUNGS_PUFFER_MONATE = 4

# Mindestabstand fuer die Auswertung: wie weit in die Zukunft schauen wir,
# um zu pruefen, ob der Fair Value getroffen wurde / die Rendite kam.
HALTEDAUER_MONATE = 12


def _als_datum(s):
    """'2020-12-31' -> date. Robust gegen Teilstrings/None."""
    if not s:
        return None
    try:
        return _dt.date.fromisoformat(str(s)[:10])
    except Exception:
        return None


def _plus_monate(d: _dt.date, monate: int) -> _dt.date:
    """Datum + n Monate (grob, ohne dateutil)."""
    m = d.month - 1 + monate
    jahr = d.year + m // 12
    monat = m % 12 + 1
    tag = min(d.day, 28)          # 28 vermeidet Monatsend-Probleme
    return _dt.date(jahr, monat, tag)


def verfuegbar_ab(period_end_date) -> _dt.date | None:
    """Ab wann galten die Jahreszahlen als oeffentlich bekannt?
    = Geschaeftsjahresende + Puffer. Das ist der Look-ahead-Schutz."""
    ende = _als_datum(period_end_date)
    if not ende:
        return None
    return _plus_monate(ende, VEROEFFENTLICHUNGS_PUFFER_MONATE)


def fundamentaldaten_zum_stichtag(roic_mod, ticker, stichtag: _dt.date):
    """Rekonstruiert die Fundamentaldaten, die am 'stichtag' TATSAECHLICH
    bekannt waren - also den letzten Geschaeftsbericht, dessen Puffer-Frist
    vor dem Stichtag lag. Gibt (fund_dict, fiscal_year) zurueck oder (None,None).

    Nutzt NUR roic-Rohdaten. Rechnet KEINE heutigen Werte ein - genau das ist
    der Kern gegen Look-ahead-Bias."""
    try:
        inc = roic_mod.income_annual(ticker, limit=15) or []
        bal = roic_mod.balance_annual(ticker, limit=15) or []
        cf = roic_mod.cashflow_annual(ticker, limit=15) or []
    except Exception:
        return None, None
    if not inc:
        return None, None

    _g = roic_mod._g
    _num = roic_mod._num

    # Bilanz/Cashflow nach fiscal_year indizieren, um sie zur GuV zu matchen
    def _index(rows):
        out = {}
        for r in rows or []:
            if isinstance(r, dict):
                fy = _g(r, "fiscal_year")
                if fy is not None:
                    out[fy] = r
        return out
    bal_idx = _index(bal)
    cf_idx = _index(cf)

    # den JUENGSTEN Bericht finden, der am Stichtag schon bekannt war
    kandidat = None
    for r in inc:
        if not isinstance(r, dict):
            continue
        pend = _g(r, "period_end_date", "date")
        ab = verfuegbar_ab(pend)
        if ab and ab <= stichtag:
            # bekannt am Stichtag - merken, wenn es der bisher juengste ist
            if kandidat is None or _als_datum(pend) > kandidat[0]:
                kandidat = (_als_datum(pend), r, _g(r, "fiscal_year"))
    if not kandidat:
        return None, None

    _, inc_row, fy = kandidat
    bal_row = bal_idx.get(fy, {})
    cf_row = cf_idx.get(fy, {})

    # Fundamentaldaten-Dict im Format, das valuation.fair_value erwartet, aus
    # den historischen roic-Rohzeilen. WICHTIG: roic nutzt eigene Praefixe
    # (is_ = income statement, cf_ = cash flow, bs_ = balance sheet).
    revenue = _num(_g(inc_row, "is_sales_revenue_turnover",
                      "is_sales_and_services_revenues"))
    net_income = _num(_g(inc_row, "is_net_income", "is_earn_for_common"))
    ebit = _num(_g(inc_row, "is_oper_income"))
    shares = _num(_g(inc_row, "is_sh_for_diluted_eps", "is_avg_num_sh_for_eps"))
    eps = _num(_g(inc_row, "diluted_eps", "eps"))
    # Cashflow: roic liefert FCF teils fertig (ttm/firm), sonst selbst rechnen
    fcf = _num(_g(cf_row, "cf_free_cash_flow_firm", "ttm_free_cash_flow"))
    op_cf = _num(_g(cf_row, "cf_cash_from_oper", "ttm_cash_from_oper"))
    capex = _num(_g(cf_row, "cf_cap_expenditures", "ttm_cap_expend"))
    if fcf is None and op_cf is not None and capex is not None:
        fcf = op_cf - abs(capex)
    # Bilanz: net_debt und equity liefert roic direkt
    net_debt = _num(_g(bal_row, "net_debt"))
    cash = _num(_g(bal_row, "bs_cash_near_cash_item",
                   "bs_c_and_ce_and_sti_detailed"))
    equity = _num(_g(bal_row, "bs_total_equity"))
    total_debt = _num(_g(bal_row, "bs_tot_liab"))
    _st = _num(_g(bal_row, "bs_st_borrow"))
    _lt = _num(_g(bal_row, "bs_lt_borrow"))
    if total_debt is None and (_st is not None or _lt is not None):
        total_debt = (_st or 0) + (_lt or 0)
    if net_debt is None and total_debt is not None and cash is not None:
        net_debt = total_debt - cash
    # EBITDA aus EBIT + Abschreibungen annaehern, falls nicht direkt da
    ebitda = None
    _depr = _num(_g(cf_row, "cf_depr_amort", "cf_depreciation_amort"))
    if ebit is not None:
        ebitda = ebit + (_depr or 0)

    # EPS bevorzugt direkt aus roic, sonst aus net_income/shares
    if eps is None and net_income and shares:
        eps = net_income / shares

    fund = {
        "revenue": revenue, "net_income": net_income,
        "ebit": ebit, "ebitda": ebitda, "shares_out": shares,
        "free_cashflow": fcf, "operating_cashflow": op_cf,
        "net_debt": net_debt, "total_debt": total_debt, "cash": cash,
        "book_value_ps": (equity / shares) if (equity and shares) else None,
        "eps_trailing": eps,
        "sector": None, "_backtest_fy": fy,
        "_period_end": _g(inc_row, "period_end_date", "date"),
    }
    return fund, fy


def kurs_zum_stichtag(monatskurse, stichtag: _dt.date):
    """Naechstgelegener Monatsschlusskurs am oder vor dem Stichtag.
    monatskurse = [(datum_str, kurs)], aelteste zuerst (aus roic.monatsende)."""
    best = None
    for d, k in monatskurse or []:
        dd = _als_datum(d)
        if dd and dd <= stichtag:
            if best is None or dd > best[0]:
                best = (dd, k)
    return best[1] if best else None


def kurs_nach_monaten(monatskurse, start: _dt.date, monate: int):
    """Kurs 'monate' nach dem Startdatum (naechstgelegener danach)."""
    ziel = _plus_monate(start, monate)
    best = None
    for d, k in monatskurse or []:
        dd = _als_datum(d)
        if dd and dd >= ziel:
            if best is None or dd < best[0]:
                best = (dd, k)
    return best[1] if best else None


def einzeltest(roic_mod, valuation_mod, ticker, stichtage,
               haltedauer=HALTEDAUER_MONATE):
    """Backtest fuer EINEN Titel ueber mehrere Stichtage.

    Gibt pro Stichtag eine Zeile zurueck mit: damaliger Fair Value, Upside,
    Kurs damals, Kurs nach 'haltedauer' Monaten, tatsaechliche Rendite, und ob
    sich der Kurs dem Fair Value angenaehert hat.
    """
    try:
        monatskurse = roic_mod.monatsende(ticker, jahre=20)
    except Exception:
        monatskurse = []
    if not monatskurse:
        return []

    zeilen = []
    for st in stichtage:
        fund, fy = fundamentaldaten_zum_stichtag(roic_mod, ticker, st)
        if not fund:
            continue
        kurs_damals = kurs_zum_stichtag(monatskurse, st)
        if not kurs_damals or kurs_damals <= 0:
            continue
        # den damaligen Kurs in die Fundamentaldaten, damit fair_value rechnet
        fund["price"] = kurs_damals
        if fund.get("shares_out"):
            fund["market_cap"] = kurs_damals * fund["shares_out"]
        try:
            preset = valuation_mod.classify_playbook(fund)
            fv = valuation_mod.fair_value(fund, None, preset)
        except Exception:
            continue
        fair = fv.get("fair_value")
        if not fair or fair <= 0:
            continue
        upside_damals = (fair / kurs_damals - 1) * 100

        kurs_spaeter = kurs_nach_monaten(monatskurse, st, haltedauer)
        if not kurs_spaeter or kurs_spaeter <= 0:
            continue
        rendite = (kurs_spaeter / kurs_damals - 1) * 100

        # Frage 1: hat sich der Kurs dem Fair Value ANGENAEHERT?
        abstand_vorher = abs(fair - kurs_damals)
        abstand_nachher = abs(fair - kurs_spaeter)
        angenaehert = abstand_nachher < abstand_vorher

        zeilen.append({
            "ticker": ticker, "stichtag": st.isoformat(), "fy": fy,
            "kurs_damals": round(kurs_damals, 2),
            "fair_value": round(fair, 2),
            "upside_pct": round(upside_damals, 1),
            "kurs_spaeter": round(kurs_spaeter, 2),
            "rendite_pct": round(rendite, 1),
            "fv_angenaehert": angenaehert,
            "preset": preset,
        })
    return zeilen


def diagnose(roic_mod, ticker, stichtag=None):
    """Erklaert, warum ein Titel (keine) Datenpunkte liefert. Prueft Schritt
    fuer Schritt: kommt die Historie an, greifen die Feldnamen, klappt der
    Look-ahead-Filter, gibt es Kurse? Gibt eine Liste von Diagnose-Zeilen."""
    import datetime as _d
    stichtag = stichtag or _d.date(2020, 6, 15)
    zeilen = []
    try:
        inc = roic_mod.income_annual(ticker, limit=15) or []
    except Exception as e:
        return [f"income_annual Fehler: {e}"]
    zeilen.append(f"income_annual: {len(inc)} Jahre erhalten")
    if inc:
        _g = roic_mod._g
        _num = roic_mod._num
        r0 = inc[0]
        pend = _g(r0, "period_end_date", "date")
        rev = _num(_g(r0, "is_sales_revenue_turnover", "is_sales_and_services_revenues"))
        ni = _num(_g(r0, "is_net_income"))
        sh = _num(_g(r0, "is_sh_for_diluted_eps", "is_avg_num_sh_for_eps"))
        zeilen.append(f"  neuestes: FY-Ende {pend}, Umsatz {rev}, "
                      f"Nettogewinn {ni}, Aktien {sh}")
        ab = verfuegbar_ab(pend)
        zeilen.append(f"  verfuegbar ab: {ab}")
    fund, fy = fundamentaldaten_zum_stichtag(roic_mod, ticker, stichtag)
    if fund:
        zeilen.append(f"Fundamentaldaten zum {stichtag}: FY{fy}, "
                      f"FCF={fund.get('free_cashflow')}, "
                      f"shares={fund.get('shares_out')}, "
                      f"net_income={fund.get('net_income')}")
    else:
        zeilen.append(f"KEINE Fundamentaldaten zum {stichtag} rekonstruierbar")
    try:
        mk = roic_mod.monatsende(ticker, jahre=20)
        zeilen.append(f"Monatskurse: {len(mk)} Punkte"
                      + (f", von {mk[0][0]} bis {mk[-1][0]}" if mk else ""))
    except Exception as e:
        zeilen.append(f"monatsende Fehler: {e}")
    return zeilen


def jahres_stichtage(von_jahr, bis_jahr, monat=6):
    """Liste von Stichtagen: je ein Datum pro Jahr (Standard: Jahresmitte,
    damit die Vorjahreszahlen mit Puffer sicher bekannt sind)."""
    return [_dt.date(j, monat, 15) for j in range(von_jahr, bis_jahr + 1)]


def auswertung(alle_zeilen):
    """Fasst die Einzelzeilen zu den zwei Kernfragen zusammen."""
    if not alle_zeilen:
        return {"n": 0}

    n = len(alle_zeilen)
    # Frage 1: Treffsicherheit des Fair Value
    angenaehert = sum(1 for z in alle_zeilen if z["fv_angenaehert"])

    # Frage 2: Bringt hoher Upside mehr Rendite? Titel in zwei Gruppen teilen:
    # hoher Upside (>20%) vs. niedriger/negativer Upside.
    hoch = [z for z in alle_zeilen if z["upside_pct"] > 20]
    niedrig = [z for z in alle_zeilen if z["upside_pct"] <= 20]

    def _schnitt(gruppe):
        if not gruppe:
            return None
        return round(sum(z["rendite_pct"] for z in gruppe) / len(gruppe), 1)

    return {
        "n": n,
        # Frage 1
        "fv_treffer_pct": round(angenaehert / n * 100, 1),
        "fv_treffer_abs": angenaehert,
        # Frage 2
        "rendite_hoher_upside": _schnitt(hoch),
        "n_hoher_upside": len(hoch),
        "rendite_niedriger_upside": _schnitt(niedrig),
        "n_niedriger_upside": len(niedrig),
        "rendite_gesamt": _schnitt(alle_zeilen),
    }
