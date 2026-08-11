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

    # WACHSTUM aus dem Vorjahresvergleich berechnen. OHNE das fiel der DCF auf
    # den Notwert 6% zurueck und unterschaetzte den Fair Value massiv - genau
    # das hat der Backtest aufgedeckt (durchgehend negativer Upside).
    revenue_growth = None
    earnings_growth = None
    # Vorjahres-GuV finden (fiscal_year = fy - 1)
    _vorjahr = None
    for r in inc:
        if isinstance(r, dict) and _g(r, "fiscal_year") == (fy - 1 if fy else None):
            _vorjahr = r
            break
    if _vorjahr:
        _rev_vj = _num(_g(_vorjahr, "is_sales_revenue_turnover",
                          "is_sales_and_services_revenues"))
        _ni_vj = _num(_g(_vorjahr, "is_net_income", "is_earn_for_common"))
        if revenue and _rev_vj and _rev_vj > 0:
            revenue_growth = revenue / _rev_vj - 1
        if net_income and _ni_vj and _ni_vj > 0:
            earnings_growth = net_income / _ni_vj - 1

    # ZYKLUS-ERKENNUNG + NORMALISIERTE GEWINNE (gegen die Zyklus-Falle).
    # Ein Zykliker hat stark schwankende Gewinnmargen ueber die Jahre. Am
    # Gewinngipfel sieht er faelschlich "billig + stark" aus. Wir sammeln die
    # Nettomargen der verfuegbaren Jahre, messen ihre Schwankung, und wenn sie
    # gross ist, berechnen wir einen NORMALISIERTEN Gewinn aus der
    # Durchschnittsmarge x aktuellem Umsatz - statt des Spitzengewinns.
    _margen = []
    for r in inc:
        if not isinstance(r, dict):
            continue
        _rv = _num(_g(r, "is_sales_revenue_turnover",
                      "is_sales_and_services_revenues"))
        _ni = _num(_g(r, "is_net_income", "is_earn_for_common"))
        if _rv and _rv > 0 and _ni is not None:
            _margen.append(_ni / _rv)
    ist_zyklisch_daten = False
    net_income_normalisiert = net_income
    if len(_margen) >= 4:
        _schnitt_marge = sum(_margen) / len(_margen)
        # Standardabweichung der Margen
        _var = sum((m - _schnitt_marge) ** 2 for m in _margen) / len(_margen)
        _std = _var ** 0.5
        # Variationskoeffizient: Schwankung relativ zum Schnitt. Hoch =
        # zyklisch. Schwelle 0.4 = deutliche Schwankung. Zusaetzlich muss die
        # aktuelle Marge klar ueber dem Schnitt liegen (= Gipfelverdacht).
        _aktuelle_marge = (net_income / revenue) if (net_income and revenue
                                                     and revenue > 0) else None
        if _schnitt_marge and abs(_schnitt_marge) > 0.001:
            _variationskoeff = _std / abs(_schnitt_marge)
            if _variationskoeff > 0.4:
                ist_zyklisch_daten = True
                # normalisierten Gewinn NUR ansetzen, wenn aktueller Gewinn
                # ueber dem Zyklus-Schnitt liegt (Gipfel) - nicht im Tal
                # (dort waere die Firma sonst faelschlich "teuer").
                if (_aktuelle_marge is not None and revenue
                        and _aktuelle_marge > _schnitt_marge):
                    net_income_normalisiert = _schnitt_marge * revenue

    # BANKEN-ERKENNUNG aus den Daten (analog zur Zyklus-Erkennung). Banken
    # brauchen das financial-Playbook (KBV+KGV, KEIN DCF) - ein DCF auf eine
    # Bank liefert Unsinn. Im Backtest fehlt das Sektor-Label, also erkennen
    # wir Banken an harten Bilanzmerkmalen: nennenswerte Kreditforderungen
    # UND eine im Verhaeltnis zum Umsatz sehr grosse Bilanzsumme.
    _loans = _num(_g(bal_row, "bs_loans_receivable"))
    _bilanzsumme = _num(_g(bal_row, "bs_tot_asset", "bs_total_assets"))
    ist_bank_daten = False
    if _loans and _bilanzsumme and revenue and revenue > 0:
        # Kredite > 15 % der Bilanz UND Bilanz > 4x Umsatz = klar Bank/Finanz
        if _loans / _bilanzsumme > 0.15 and _bilanzsumme / revenue > 4:
            ist_bank_daten = True

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
    # Bei erkannten Zyklikern am Gipfel: EPS aus dem NORMALISIERTEN Gewinn -
    # so sieht der Titel nicht faelschlich spottbillig aus.
    eps_normalisiert = eps
    if (ist_zyklisch_daten and not ist_bank_daten
            and net_income_normalisiert is not None
            and shares and shares > 0):
        eps_normalisiert = net_income_normalisiert / shares

    # KENNZAHLEN FUER DEN COMPOSITE SCORE selbst berechnen (aus den Rohdaten,
    # ohne Extra-Abrufe). So laesst sich der Composite historisch nachbilden.
    _assets = _num(_g(bal_row, "bs_tot_asset", "bs_total_assets"))
    roe = (net_income / equity) if (net_income and equity and equity > 0) else None
    roa = (net_income / _assets) if (net_income and _assets and _assets > 0) else None
    gross_profit = _num(_g(inc_row, "is_gross_profit"))
    gross_margin = (gross_profit / revenue) if (gross_profit and revenue and revenue > 0) else None
    operating_margin = (ebit / revenue) if (ebit and revenue and revenue > 0) else None
    _cur_assets = _num(_g(bal_row, "bs_cur_asset_report", "bs_total_current_assets"))
    _cur_liab = _num(_g(bal_row, "bs_cur_liab"))
    current_ratio = (_cur_assets / _cur_liab) if (_cur_assets and _cur_liab and _cur_liab > 0) else None
    net_debt_ebitda = (net_debt / ebitda) if (net_debt is not None and ebitda and ebitda > 0) else None

    fund = {
        "revenue": revenue, "net_income": net_income_normalisiert,
        "net_income_roh": net_income,
        "ebit": ebit, "ebitda": ebitda, "shares_out": shares,
        "free_cashflow": fcf, "operating_cashflow": op_cf,
        "net_debt": net_debt, "total_debt": total_debt, "cash": cash,
        "book_value_ps": (equity / shares) if (equity and shares) else None,
        "eps_trailing": eps_normalisiert,
        "eps_roh": eps,
        "revenue_growth": revenue_growth,
        "earnings_growth": earnings_growth,
        # Composite-Kennzahlen:
        "roe": roe, "roa": roa,
        "gross_margin": gross_margin, "operating_margin": operating_margin,
        "current_ratio": current_ratio, "net_debt_ebitda": net_debt_ebitda,
        # Zyklus-Erkennung aus den Daten: setzt das cyclical-Playbook, auch
        # ohne Sektor-Label. So greift die mid-cycle-Bewertung.
        "_ist_zyklisch": ist_zyklisch_daten and not ist_bank_daten,
        "_ist_bank": ist_bank_daten,
        # Bank hat Vorrang: financial-Playbook (KEIN DCF). Sonst Energy fuer
        # erkannte Zykliker. Sonst kein Label (quality/inflection nach Wachstum).
        "sector": ("Financial Services" if ist_bank_daten
                   else "Energy" if ist_zyklisch_daten else None),
        "_backtest_fy": fy,
        "_period_end": _g(inc_row, "period_end_date", "date"),
    }
    # Bewertungs-Multiples aus den Rohdaten selbst berechnen, damit im Backtest
    # mehr Methoden als nur der DCF greifen (KGV, KBV, KUV, EV/EBITDA). roic
    # liefert historisch keine fertigen Multiples, aber aus Kurs+Fundamentaldaten
    # lassen sie sich exakt bilden - der Kurs wird spaeter in einzeltest gesetzt.
    # (Wir markieren sie, damit einzeltest sie nach dem Kurs-Setzen fuellt.)
    fund["_kann_multiples"] = True
    return fund, fy


def _ergaenze_multiples(fund):
    """Fuellt KGV/KBV/KUV/EV-EBITDA aus Kurs + Fundamentaldaten. Aufgerufen,
    nachdem der historische Kurs gesetzt wurde. So greifen im Backtest mehr
    Bewertungsmethoden als nur der DCF."""
    price = fund.get("price")
    if not price or price <= 0:
        return fund
    eps = fund.get("eps_trailing")
    if eps and eps > 0:
        fund["pe_trailing"] = price / eps
    bvps = fund.get("book_value_ps")
    if bvps and bvps > 0:
        fund["pb"] = price / bvps
    rev = fund.get("revenue")
    sh = fund.get("shares_out")
    if rev and sh and rev > 0:
        fund["ps"] = (price * sh) / rev
    ebitda = fund.get("ebitda")
    mc = fund.get("market_cap") or (price * sh if sh else None)
    nd = fund.get("net_debt") or 0
    if ebitda and ebitda > 0 and mc:
        fund["ev_ebitda"] = (mc + nd) / ebitda
    return fund
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
               haltedauer=HALTEDAUER_MONATE, scoring_mod=None):
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
        # jetzt die kursabhaengigen Multiples fuellen (KGV/KBV/KUV/EV-EBITDA),
        # damit im Backtest mehr Bewertungsmethoden greifen als nur der DCF.
        _ergaenze_multiples(fund)
        try:
            preset = valuation_mod.classify_playbook(fund)
            fv = valuation_mod.fair_value(fund, None, preset)
        except Exception:
            continue
        fair = fv.get("fair_value")
        if not fair or fair <= 0:
            continue
        upside_damals = (fair / kurs_damals - 1) * 100

        # Composite Score historisch nachbilden (fuer die feste Hypothese
        # 'Upside positiv UND Composite hoch'). scoring_mod optional.
        composite = None
        if scoring_mod is not None:
            # 52W-Hoch/-Tief aus der Kurshistorie der letzten 12 Monate vor dem
            # Stichtag setzen, damit die Momentum-Komponente echte Werte hat.
            _fenster = []
            _von_52w = _plus_monate(st, -12)
            for d, k in monatskurse:
                dd = _als_datum(d)
                if dd and _von_52w <= dd <= st and k:
                    _fenster.append(k)
            if len(_fenster) >= 3:
                fund["52w_high"] = max(_fenster)
                fund["52w_low"] = min(_fenster)
            try:
                _s = scoring_mod.score_stock(fund, None, preset=preset)
                composite = _s.get("composite")
            except Exception:
                composite = None

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
            "composite": round(composite, 1) if composite is not None else None,
            "net_debt_ebitda": (round(fund.get("net_debt_ebitda"), 2)
                                if fund.get("net_debt_ebitda") is not None else None),
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
    # Standard-Stichtag: 3 Jahre zurueck (liegt im 5-Jahres-Tarif-Fenster).
    # Der Dashboard-Aufruf sollte den tatsaechlich gewaehlten Stichtag geben.
    stichtag = stichtag or _d.date(_d.date.today().year - 3, 6, 15)
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


def jahres_stichtage(von_jahr, bis_jahr, pro_jahr=2):
    """Liste von Stichtagen. pro_jahr steuert die Dichte:
      1 = nur Jahresmitte (Juni)
      2 = Fruehjahr (April) + Herbst (Oktober) - verdoppelt die Datenpunkte
      4 = quartalsweise
    Mehr Stichtage = mehr Datenpunkte aus demselben 5-Jahres-Fenster. Die
    Monate sind so gewaehlt, dass die Vorjahreszahlen mit Puffer bekannt sind."""
    monate = {1: [6], 2: [4, 10], 4: [2, 5, 8, 11]}.get(pro_jahr, [6])
    out = []
    for j in range(von_jahr, bis_jahr + 1):
        for m in monate:
            out.append(_dt.date(j, m, 15))
    return out


def auswertung(alle_zeilen):
    """Fasst die Einzelzeilen zu den zwei Kernfragen zusammen."""
    if not alle_zeilen:
        return {"n": 0}

    n = len(alle_zeilen)
    # Frage 1: Treffsicherheit des Fair Value
    angenaehert = sum(1 for z in alle_zeilen if z["fv_angenaehert"])

    # Frage 2: Bringt hoher Upside mehr Rendite? RELATIV vergleichen - die obere
    # Haelfte nach Upside gegen die untere. So ist die Frage IMMER beantwortbar,
    # auch wenn (wie in einer teuren Marktphase) kein Titel absolut hohen Upside
    # hat. Zusaetzlich der absolute Schnitt >20% als Referenz.
    sortiert = sorted(alle_zeilen, key=lambda z: z["upside_pct"], reverse=True)
    haelfte = max(1, n // 2)
    obere = sortiert[:haelfte]           # hoechster Upside
    untere = sortiert[-haelfte:]         # niedrigster Upside

    def _schnitt(gruppe):
        if not gruppe:
            return None
        return round(sum(z["rendite_pct"] for z in gruppe) / len(gruppe), 1)

    def _median_rendite(gruppe):
        """Median der Renditen - robust gegen einzelne Ausreisser (z.B. ein
        +600%-Titel, der den Durchschnitt verzerrt)."""
        if not gruppe:
            return None
        werte = sorted(z["rendite_pct"] for z in gruppe)
        m = len(werte)
        if m % 2:
            return round(werte[m // 2], 1)
        return round((werte[m // 2 - 1] + werte[m // 2]) / 2, 1)

    # absolute Gruppen (Referenz)
    hoch_abs = [z for z in alle_zeilen if z["upside_pct"] > 20]
    niedrig_abs = [z for z in alle_zeilen if z["upside_pct"] <= 20]

    # Korrelation Upside <-> Rendite (grober Zusammenhangs-Indikator)
    ups = [z["upside_pct"] for z in alle_zeilen]
    rens = [z["rendite_pct"] for z in alle_zeilen]
    korr = None
    if n >= 3:
        mu_u = sum(ups) / n
        mu_r = sum(rens) / n
        cov = sum((u - mu_u) * (r - mu_r) for u, r in zip(ups, rens))
        var_u = sum((u - mu_u) ** 2 for u in ups)
        var_r = sum((r - mu_r) ** 2 for r in rens)
        if var_u > 0 and var_r > 0:
            korr = round(cov / (var_u ** 0.5 * var_r ** 0.5), 2)

    # Rang-Korrelation (Spearman) - robuster gegen Ausreisser, weil sie nur die
    # REIHENFOLGE zaehlt, nicht die absoluten Werte. Ein +600%-Titel ist dann
    # einfach "der hoechste", nicht ein 600er-Hebel auf den Schnitt.
    korr_rang = None
    if n >= 3:
        def _raenge(werte):
            paare = sorted(range(len(werte)), key=lambda i: werte[i])
            r = [0] * len(werte)
            for rang, idx in enumerate(paare):
                r[idx] = rang + 1
            return r
        ru = _raenge(ups)
        rr = _raenge(rens)
        mu_ru = sum(ru) / n
        mu_rr = sum(rr) / n
        cov_r = sum((a - mu_ru) * (b - mu_rr) for a, b in zip(ru, rr))
        var_ru = sum((a - mu_ru) ** 2 for a in ru)
        var_rr = sum((b - mu_rr) ** 2 for b in rr)
        if var_ru > 0 and var_rr > 0:
            korr_rang = round(cov_r / (var_ru ** 0.5 * var_rr ** 0.5), 2)

    return {
        "n": n,
        # Frage 1
        "fv_treffer_pct": round(angenaehert / n * 100, 1),
        "fv_treffer_abs": angenaehert,
        # Frage 2 - relativ (obere vs untere Haelfte nach Upside)
        # MEDIAN ist der Hauptwert (robust), Durchschnitt als Referenz daneben.
        "median_obere_haelfte": _median_rendite(obere),
        "median_untere_haelfte": _median_rendite(untere),
        "rendite_obere_haelfte": _schnitt(obere),
        "rendite_untere_haelfte": _schnitt(untere),
        "n_haelfte": haelfte,
        "upside_obere_min": round(min(z["upside_pct"] for z in obere), 1),
        "upside_untere_max": round(max(z["upside_pct"] for z in untere), 1),
        # Frage 2 - absolut (Referenz)
        "rendite_hoher_upside": _schnitt(hoch_abs),
        "n_hoher_upside": len(hoch_abs),
        "rendite_niedriger_upside": _schnitt(niedrig_abs),
        "n_niedriger_upside": len(niedrig_abs),
        # Zusammenhang
        "korrelation": korr,
        "korrelation_rang": korr_rang,
        "median_gesamt": _median_rendite(alle_zeilen),
        "rendite_gesamt": _schnitt(alle_zeilen),
        # Frage 3 - die VORAB festgelegte Hypothese:
        # 'Upside > 0 UND Composite >= 55' schlaegt den Rest (Median).
        **_hypothese_auswertung(alle_zeilen, _median_rendite, _schnitt),
    }


# Schwelle der festen Hypothese - VORAB festgelegt, wird NICHT nachtraeglich
# optimiert (das waere Overfitting). Upside positiv UND Composite mindestens 55.
HYP_UPSIDE_MIN = 0.0
HYP_COMPOSITE_MIN = 55.0

# STRENGERE feste Hypothese (Frage 4) - ebenfalls VORAB festgelegt, BEVOR das
# Ergebnis gesehen wurde. Kombination aus guenstig + stark + solide Bilanz.
# Diese drei Zahlen werden NICHT nachjustiert. Erwartung offen gehalten: es ist
# gut moeglich, dass zu wenige Titel alle drei erfuellen - dann lautet die
# ehrliche Antwort "nicht testbar", nicht "funktioniert (nicht)".
# Katalysator BEWUSST ausgelassen: historisch nicht sauber rekonstruierbar.
HYP2_UPSIDE_MIN = 15.0        # klar unterbewertet
HYP2_COMPOSITE_MIN = 60.0     # fundamental stark
HYP2_NETDEBT_EBITDA_MAX = 3.0 # solide Bilanz (nicht ueberschuldet)


def _hypothese_auswertung(zeilen, median_fn, schnitt_fn):
    """Testet die EINE vorab festgelegte Hypothese: Titel mit Upside > 0 UND
    Composite >= 55 bringen im Median mehr Rendite als der Rest. Nur auswertbar,
    wenn der Composite historisch vorliegt."""
    mit_comp = [z for z in zeilen if z.get("composite") is not None]
    if len(mit_comp) < 4:
        return {"hyp_verfuegbar": False}
    treffer = [z for z in mit_comp
               if z["upside_pct"] > HYP_UPSIDE_MIN
               and z["composite"] >= HYP_COMPOSITE_MIN]
    rest = [z for z in mit_comp if z not in treffer]

    # Strengere Hypothese 2: guenstig UND stark UND solide Bilanz.
    treffer2 = [z for z in mit_comp
                if z["upside_pct"] > HYP2_UPSIDE_MIN
                and z["composite"] >= HYP2_COMPOSITE_MIN
                and z.get("net_debt_ebitda") is not None
                and z["net_debt_ebitda"] < HYP2_NETDEBT_EBITDA_MAX]
    rest2 = [z for z in mit_comp if z not in treffer2]

    return {
        "hyp_verfuegbar": True,
        "hyp_median_treffer": median_fn(treffer),
        "hyp_median_rest": median_fn(rest),
        "hyp_schnitt_treffer": schnitt_fn(treffer),
        "hyp_schnitt_rest": schnitt_fn(rest),
        "hyp_n_treffer": len(treffer),
        "hyp_n_rest": len(rest),
        "hyp_treffer_fv_quote": (round(
            sum(1 for z in treffer if z["fv_angenaehert"]) / len(treffer) * 100, 1)
            if treffer else None),
        # Hypothese 2 (strenger)
        "hyp2_upside_min": HYP2_UPSIDE_MIN,
        "hyp2_composite_min": HYP2_COMPOSITE_MIN,
        "hyp2_netdebt_max": HYP2_NETDEBT_EBITDA_MAX,
        "hyp2_median_treffer": median_fn(treffer2),
        "hyp2_median_rest": median_fn(rest2),
        "hyp2_schnitt_treffer": schnitt_fn(treffer2),
        "hyp2_n_treffer": len(treffer2),
        "hyp2_n_rest": len(rest2),
        "hyp2_treffer_fv_quote": (round(
            sum(1 for z in treffer2 if z["fv_angenaehert"]) / len(treffer2) * 100, 1)
            if treffer2 else None),
        "hyp2_treffer_titel": sorted(set(z["ticker"] for z in treffer2)),
    }
