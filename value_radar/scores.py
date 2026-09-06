
# -*- coding: utf-8 -*-
"""scores.py - Wissenschaftlich etablierte Fundamental-Scores fuer die
Long/Short-Auswahl. Alle drei arbeiten auf roic-Jahresdaten (mehrjaehrig).

  Piotroski F-Score (0-9): fundamentale STAERKE. Hoch = Long-Kandidat, filtert
     Value-Fallen (billige Titel, die nur billig sind, weil sie kranken).
  Altman Z-Score: PLEITERISIKO. Niedrig (<1.8) = Short-Warnsignal.
  Beneish M-Score: BILANZMANIPULATION. Hoch (>-2.22) = Short-Warnsignal.

WICHTIG - Grenzen (aus der Fachliteratur):
  - Alle drei gelten NICHT fuer Banken, Versicherer, REITs - andere
    Bilanzstruktur. Dort geben die Funktionen None zurueck.
  - Historisch belegt, aber keine Garantie; viele Faktoren sind schwaecher
    geworden, seit sie oeffentlich bekannt sind.
  - Braucht zwei Geschaeftsjahre (Vorjahresvergleich). Fehlen Daten -> None.
"""
from __future__ import annotations

__version__ = "2026.09.25"   # Beneish mit Komponenten, Treibern, TATA-Test


def _num(x):
    try:
        f = float(x)
        return f
    except (TypeError, ValueError):
        return None


def _g(d, *keys):
    """Erstes vorhandenes Feld aus einem roic-Datensatz."""
    if not isinstance(d, dict):
        return None
    for k in keys:
        v = d.get(k)
        if v is not None:
            return v
    return None


# roic-Feldnamen (mit is_/bs_/cf_-Praefixen, wie im Backtest bestaetigt)
_F_NETINCOME = ("is_net_income", "is_earn_for_common")
_F_REVENUE = ("is_sales_revenue_turnover", "is_sales_and_services_revenues")
_F_GROSSPROFIT = ("is_gross_profit",)
_F_OPINCOME = ("is_oper_income",)
_F_SGA = ("is_sg_and_a_expense", "is_operating_expn")
_F_DEPR = ("cf_depr_amort", "is_depr_exp")
_F_OPCF = ("cf_cash_from_oper", "ttm_cash_from_oper")
_F_ASSETS = ("bs_tot_asset", "bs_total_assets")
_F_CURASSETS = ("bs_cur_asset_report", "bs_total_current_assets")
_F_CURLIAB = ("bs_cur_liab", "bs_total_current_liabilities")
_F_LTDEBT = ("bs_lt_borrow", "bs_long_term_borrowings")
_F_TOTLIAB = ("bs_tot_liab",)
_F_SHARES = ("is_sh_for_diluted_eps", "bs_sh_out")
_F_RECEIV = ("bs_accounts_receivable", "bs_acct_note_rcv")
_F_RETEARN = ("bs_retain_earnings", "bs_pure_retained_earnings")
_F_WORKCAP = None  # wird berechnet
_F_EBIT = ("is_oper_income",)
_F_MKTCAP = ("market_cap",)


def _ist_finanzwert(sektor: str | None, fund: dict | None = None) -> bool:
    """Banken/Versicherer/REITs ausschliessen - Scores dort ungueltig."""
    s = (sektor or "").lower()
    if any(k in s for k in ("financ", "bank", "insur", "reit", "versicher")):
        return True
    # datenbasiert: hohe Kreditforderungen deuten auf Bank
    if fund and fund.get("_ist_bank"):
        return True
    return False


# ===========================================================================
# PIOTROSKI F-SCORE (0-9) - fundamentale Staerke, Long-Signal
# ===========================================================================
def piotroski_f(akt: dict, vorjahr: dict, sektor: str | None = None,
                fund: dict | None = None) -> dict | None:
    """Neun Kriterien nach Piotroski (2000). akt/vorjahr = roic-Jahresdaten
    (jeweils ein gemischtes Dict aus income+balance+cashflow des Jahres).
    Gibt {score, details, ...} zurueck oder None (Finanzwert/Daten fehlen)."""
    if _ist_finanzwert(sektor, fund):
        return None
    if not isinstance(akt, dict) or not isinstance(vorjahr, dict):
        return None

    # --- Rohwerte aktuelles Jahr ---
    ni = _num(_g(akt, *_F_NETINCOME))
    rev = _num(_g(akt, *_F_REVENUE))
    assets = _num(_g(akt, *_F_ASSETS))
    opcf = _num(_g(akt, *_F_OPCF))
    gross = _num(_g(akt, *_F_GROSSPROFIT))
    cur_a = _num(_g(akt, *_F_CURASSETS))
    cur_l = _num(_g(akt, *_F_CURLIAB))
    ltdebt = _num(_g(akt, *_F_LTDEBT)) or 0.0
    shares = _num(_g(akt, *_F_SHARES))

    # --- Rohwerte Vorjahr ---
    ni_v = _num(_g(vorjahr, *_F_NETINCOME))
    rev_v = _num(_g(vorjahr, *_F_REVENUE))
    assets_v = _num(_g(vorjahr, *_F_ASSETS))
    gross_v = _num(_g(vorjahr, *_F_GROSSPROFIT))
    cur_a_v = _num(_g(vorjahr, *_F_CURASSETS))
    cur_l_v = _num(_g(vorjahr, *_F_CURLIAB))
    ltdebt_v = _num(_g(vorjahr, *_F_LTDEBT)) or 0.0
    shares_v = _num(_g(vorjahr, *_F_SHARES))

    # Mindestdaten pruefen
    if None in (ni, assets, opcf, rev) or None in (assets_v, rev_v):
        return None
    if assets <= 0 or assets_v <= 0:
        return None

    roa = ni / assets
    roa_v = (ni_v / assets_v) if (ni_v is not None and assets_v) else None

    d = {}
    # --- Profitabilitaet (4) ---
    d["ni_positiv"] = 1 if ni > 0 else 0
    d["opcf_positiv"] = 1 if opcf > 0 else 0
    d["roa_steigt"] = 1 if (roa_v is not None and roa > roa_v) else 0
    d["accruals"] = 1 if (opcf / assets) > roa else 0   # CF-Qualitaet

    # --- Verschuldung / Liquiditaet (3) ---
    lev = ltdebt / assets if assets else None
    lev_v = ltdebt_v / assets_v if assets_v else None
    d["leverage_faellt"] = 1 if (lev is not None and lev_v is not None
                                 and lev < lev_v) else 0
    cr = (cur_a / cur_l) if (cur_a and cur_l and cur_l > 0) else None
    cr_v = (cur_a_v / cur_l_v) if (cur_a_v and cur_l_v and cur_l_v > 0) else None
    d["current_ratio_steigt"] = 1 if (cr is not None and cr_v is not None
                                      and cr > cr_v) else 0
    d["keine_neuen_aktien"] = 1 if (shares is not None and shares_v is not None
                                    and shares <= shares_v * 1.01) else 0

    # --- Effizienz (2) ---
    gm = (gross / rev) if (gross and rev and rev > 0) else None
    gm_v = (gross_v / rev_v) if (gross_v and rev_v and rev_v > 0) else None
    d["bruttomarge_steigt"] = 1 if (gm is not None and gm_v is not None
                                    and gm > gm_v) else 0
    at = rev / assets
    at_v = rev_v / assets_v
    d["asset_turnover_steigt"] = 1 if at > at_v else 0

    score = sum(d.values())
    return {
        "score": score,
        "max": 9,
        "details": d,
        "stark": score >= 7,          # 7-9 = solide Qualitaet
        "schwach": score <= 3,        # 0-3 = fundamental schwach
    }


# ===========================================================================
# ALTMAN Z-SCORE - Pleiterisiko (niedrig = Short-Warnsignal)
# ===========================================================================
def altman_z(akt: dict, sektor: str | None = None,
             fund: dict | None = None) -> dict | None:
    """Altman Z (1968) fuer Industrieunternehmen. Braucht Bilanz + GuV +
    Marktkapitalisierung. Gibt {z, zone} zurueck oder None."""
    if _ist_finanzwert(sektor, fund):
        return None
    assets = _num(_g(akt, *_F_ASSETS))
    if not assets or assets <= 0:
        return None
    cur_a = _num(_g(akt, *_F_CURASSETS))
    cur_l = _num(_g(akt, *_F_CURLIAB))
    ret_earn = _num(_g(akt, *_F_RETEARN))
    ebit = _num(_g(akt, *_F_EBIT))
    rev = _num(_g(akt, *_F_REVENUE))
    tot_liab = _num(_g(akt, *_F_TOTLIAB))
    # Marktkapitalisierung bevorzugt aus fund (aktuell), sonst aus Daten
    mktcap = None
    if fund:
        mktcap = _num(fund.get("market_cap"))
    if mktcap is None:
        mktcap = _num(_g(akt, *_F_MKTCAP))

    if None in (cur_a, cur_l, ret_earn, ebit, rev, tot_liab, mktcap):
        return None
    if tot_liab <= 0:
        return None

    wc = cur_a - cur_l
    # klassische Altman-Gewichte
    x1 = wc / assets
    x2 = ret_earn / assets
    x3 = ebit / assets
    x4 = mktcap / tot_liab
    x5 = rev / assets
    z = 1.2 * x1 + 1.4 * x2 + 3.3 * x3 + 0.6 * x4 + 1.0 * x5

    if z > 2.99:
        zone = "sicher"
    elif z >= 1.81:
        zone = "grau"
    else:
        zone = "gefahr"       # < 1.81 = Pleiterisiko
    return {"z": round(z, 2), "zone": zone, "gefahr": z < 1.81}


# ===========================================================================
# BENEISH M-SCORE - Wahrscheinlichkeit von Bilanzmanipulation
# ===========================================================================
def beneish_m(akt: dict, vorjahr: dict, sektor: str | None = None,
              fund: dict | None = None) -> dict | None:
    """Beneish M (1999). Acht Indizes aus Jahr/Vorjahr. M > -2.22 gilt als
    verdaechtig (moegliche Ergebnismanipulation). Gibt {m, verdaechtig}
    oder None, wenn Daten fehlen."""
    if _ist_finanzwert(sektor, fund):
        return None
    # Rohwerte
    rev = _num(_g(akt, *_F_REVENUE)); rev_v = _num(_g(vorjahr, *_F_REVENUE))
    recv = _num(_g(akt, *_F_RECEIV)); recv_v = _num(_g(vorjahr, *_F_RECEIV))
    gross = _num(_g(akt, *_F_GROSSPROFIT))
    gross_v = _num(_g(vorjahr, *_F_GROSSPROFIT))
    assets = _num(_g(akt, *_F_ASSETS)); assets_v = _num(_g(vorjahr, *_F_ASSETS))
    cur_a = _num(_g(akt, *_F_CURASSETS)); cur_a_v = _num(_g(vorjahr, *_F_CURASSETS))
    ppe = _num(_g(akt, "bs_net_fix_asset", "bs_gross_fix_asset"))
    ppe_v = _num(_g(vorjahr, "bs_net_fix_asset", "bs_gross_fix_asset"))
    depr = _num(_g(akt, *_F_DEPR)); depr_v = _num(_g(vorjahr, *_F_DEPR))
    sga = _num(_g(akt, *_F_SGA)); sga_v = _num(_g(vorjahr, *_F_SGA))
    ni = _num(_g(akt, *_F_NETINCOME))
    opcf = _num(_g(akt, *_F_OPCF))
    tot_liab = _num(_g(akt, *_F_TOTLIAB))
    tot_liab_v = _num(_g(vorjahr, *_F_TOTLIAB))

    # Mindestdaten
    if None in (rev, rev_v, gross, gross_v, assets, assets_v):
        return None
    if 0 in (rev_v, assets, assets_v) or rev == 0:
        return None

    try:
        # DSRI - Days Sales in Receivables Index
        if recv and recv_v and rev and rev_v:
            dsri = (recv / rev) / (recv_v / rev_v)
        else:
            dsri = 1.0
        # GMI - Gross Margin Index (Vorjahr/aktuell)
        gm = gross / rev; gm_v = gross_v / rev_v
        gmi = gm_v / gm if gm else 1.0
        # AQI - Asset Quality Index
        if cur_a is not None and ppe is not None and cur_a_v is not None and ppe_v is not None:
            aqi = (1 - (cur_a + ppe) / assets) / (1 - (cur_a_v + ppe_v) / assets_v)
        else:
            aqi = 1.0
        # SGI - Sales Growth Index
        sgi = rev / rev_v
        # DEPI - Depreciation Index
        if depr and depr_v and ppe and ppe_v:
            dep_rate = depr / (depr + ppe)
            dep_rate_v = depr_v / (depr_v + ppe_v)
            depi = dep_rate_v / dep_rate if dep_rate else 1.0
        else:
            depi = 1.0
        # SGAI - SG&A Index
        if sga and sga_v and rev and rev_v:
            sgai = (sga / rev) / (sga_v / rev_v)
        else:
            sgai = 1.0
        # LVGI - Leverage Index
        if tot_liab and tot_liab_v:
            lvgi = (tot_liab / assets) / (tot_liab_v / assets_v)
        else:
            lvgi = 1.0
        # TATA - Total Accruals to Total Assets
        if ni is not None and opcf is not None:
            tata = (ni - opcf) / assets
        else:
            tata = 0.0

        m = (-4.84 + 0.92 * dsri + 0.528 * gmi + 0.404 * aqi + 0.892 * sgi
             + 0.115 * depi - 0.172 * sgai + 4.679 * tata - 0.327 * lvgi)
        _teile = {"DSRI": round(dsri, 3), "GMI": round(gmi, 3),
                  "AQI": round(aqi, 3), "SGI": round(sgi, 3),
                  "DEPI": round(depi, 3), "SGAI": round(sgai, 3),
                  "LVGI": round(lvgi, 3), "TATA": round(tata, 4)}
        # Beitrag jedes Index zum M-Wert - ohne das laesst sich ein Verdacht
        # nicht einordnen. Bei stark wachsenden Firmen dominiert der SGI
        # (Umsatzwachstumsindex) das Ergebnis mechanisch: NVIDIA bekam mit
        # nahezu verdoppeltem Umsatz allein daraus fast einen ganzen Punkt.
        _beitrag = {"DSRI": 0.92 * dsri, "GMI": 0.528 * gmi, "AQI": 0.404 * aqi,
                    "SGI": 0.892 * sgi, "DEPI": 0.115 * depi,
                    "SGAI": -0.172 * sgai, "TATA": 4.679 * tata,
                    "LVGI": -0.327 * lvgi}
    except (ZeroDivisionError, TypeError):
        return None

    return {
        "m": round(m, 2),
        "teile": _teile,
        # Ueber dem Normalwert 1 liegende Indizes, nach Beitrag sortiert.
        "treiber": [k for k, _v in sorted(
            ((k, v) for k, v in _beitrag.items() if _teile.get(k, 1) > 1.05),
            key=lambda kv: -kv[1])][:3],
        # Wachstumsartefakt statt Manipulationsverdacht.
        #
        # Erste Fassung verlangte SGI > 1,5 UND groesster Beitrag. Damit fielen
        # Eli Lilly (M -1,91) und Western Digital (M -0,25) durch, obwohl bei
        # beiden die Treiber SGI und DEPI heissen - also Umsatzsprung und
        # Abschreibungsprofil, beides Wachstums- und Investitionsfolgen.
        #
        # Der tragfaehigere Test ist TATA: der Anteil der Abgrenzungen an der
        # Bilanzsumme. Genau dort zeigt sich Ergebnismanipulation - Gewinn, der
        # nicht durch operativen Cashflow gedeckt ist. Ist TATA unauffaellig
        # (Gewinn cashgedeckt), hat der Verdacht keine Substanz, egal wie hoch
        # die wachstumsgetriebenen Indizes stehen.
        "wachstumsgetrieben": bool(
            tata < 0.03                                   # Gewinn cashgedeckt
            and max(_beitrag, key=_beitrag.get) in ("SGI", "DEPI", "AQI")
            and sgi > 1.15),
        "tata_unauffaellig": bool(tata < 0.03),
        # Zwei Schwellen, weil in der Literatur zwei gebraeuchlich sind:
        #   -2.22  empfindlich, faengt mehr, irrt oefter -> als WARNSIGNAL
        #   -1.78  Beneishs Standardgrenze                -> fuer AUSSCHLUESSE
        # Der Unterschied ist nicht akademisch: Eli Lilly liegt mit -1.91
        # dazwischen. Unter der empfindlichen Grenze gilt es als verdaechtig,
        # unter Beneishs eigener nicht.
        "verdaechtig": m > -2.22,
        "verdaechtig_streng": m > -1.78,
        "schwelle_warnung": -2.22,
        "schwelle_streng": -1.78,
        "indizes": {"DSRI": round(dsri, 2), "GMI": round(gmi, 2),
                    "SGI": round(sgi, 2), "TATA": round(tata, 3)},
    }


# ===========================================================================
# Hilfsfunktion: baut aus roic-Jahreslisten die Jahr/Vorjahr-Dicts
# ===========================================================================
def jahres_paar(inc: list, bal: list, cf: list):
    """Fuehrt die neuesten zwei Jahre aus income/balance/cashflow zu je einem
    gemischten Dict (akt, vorjahr) zusammen. Gibt (akt, vorjahr) oder
    (None, None), wenn nicht genug Jahre da sind."""
    def _mische(idx):
        d = {}
        for liste in (inc, bal, cf):
            if isinstance(liste, list) and len(liste) > idx and isinstance(liste[idx], dict):
                d.update(liste[idx])
        return d if d else None
    if not all(isinstance(x, list) and len(x) >= 2 for x in (inc, bal)):
        return None, None
    return _mische(0), _mische(1)


# roic-Felder fuer Cashflow (Dorsey)
_F_FCF = ("cf_free_cash_flow_firm", "ttm_free_cash_flow")
_F_CAPEX = ("cf_cap_expenditures", "ttm_cap_expend")


# ===========================================================================
# DORSEY MOAT-PROFITABILITAET - anhaltend hohe Rentabilitaet = Burggraben
# ===========================================================================
def dorsey_moat(inc: list, bal: list, cf: list, jahre: int = 5) -> dict | None:
    """Dorseys vier Moat-Indikatoren, geprueft ueber MEHRERE Jahre (Konstanz
    zaehlt, nicht ein Ausreisser-Jahr). Schwellen: FCF/Umsatz > 5%, Nettomarge
    > 15%, ROE > 15%, ROA > 6-7%. Gibt je Kennzahl den Anteil der Jahre ueber
    der Schwelle zurueck + ein Gesamturteil. None bei zu wenig Daten."""
    if not all(isinstance(x, list) for x in (inc, bal, cf)):
        return None
    n = min(len(inc), len(bal), len(cf), jahre)
    if n < 2:
        return None

    fcf_sales, net_marg, roe_l, roa_l = [], [], [], []
    for i in range(n):
        ir = inc[i] if isinstance(inc[i], dict) else {}
        br = bal[i] if isinstance(bal[i], dict) else {}
        cr = cf[i] if isinstance(cf[i], dict) else {}
        rev = _num(_g(ir, *_F_REVENUE))
        ni = _num(_g(ir, *_F_NETINCOME))
        eq = _num(_g(br, "bs_total_equity"))
        assets = _num(_g(br, *_F_ASSETS))
        fcf = _num(_g(cr, *_F_FCF))
        if fcf is None:
            opcf = _num(_g(cr, *_F_OPCF))
            capex = _num(_g(cr, *_F_CAPEX))
            if opcf is not None and capex is not None:
                fcf = opcf - abs(capex)
        if rev and rev > 0:
            if fcf is not None:
                fcf_sales.append(fcf / rev)
            if ni is not None:
                net_marg.append(ni / rev)
        if ni is not None and eq and eq > 0:
            roe_l.append(ni / eq)
        if ni is not None and assets and assets > 0:
            roa_l.append(ni / assets)

    def _anteil(werte, schwelle):
        if not werte:
            return None
        return round(sum(1 for w in werte if w > schwelle) / len(werte), 2)

    a_fcf = _anteil(fcf_sales, 0.05)
    a_nm = _anteil(net_marg, 0.15)
    a_roe = _anteil(roe_l, 0.15)
    a_roa = _anteil(roa_l, 0.06)
    anteile = [a for a in (a_fcf, a_nm, a_roe, a_roa) if a is not None]
    if not anteile:
        return None
    schnitt = sum(anteile) / len(anteile)
    # Moat-Urteil: wie konstant liegen die Kennzahlen ueber Dorseys Schwellen?
    if schnitt >= 0.8:
        urteil = "breit"          # wide moat
    elif schnitt >= 0.5:
        urteil = "schmal"         # narrow moat
    else:
        urteil = "keiner"
    return {
        "jahre_geprueft": n,
        "fcf_sales_anteil": a_fcf,
        "net_margin_anteil": a_nm,
        "roe_anteil": a_roe,
        "roa_anteil": a_roa,
        "moat_urteil": urteil,
        "moat_score": round(schnitt, 2),
        # aktuelle Werte fuer die Anzeige
        "fcf_sales_akt": round(fcf_sales[0] * 100, 1) if fcf_sales else None,
        "net_margin_akt": round(net_marg[0] * 100, 1) if net_marg else None,
    }


# ===========================================================================
# DORSEY RED FLAG - Cashflow-vs-Gewinn-Divergenz
# ===========================================================================
def cashflow_gewinn_divergenz(inc: list, cf: list, jahre: int = 3) -> dict | None:
    """Dorseys wichtigster Red Flag: Steigt der Gewinn, waehrend der operative
    Cashflow faellt (oder viel langsamer waechst), bucht die Firma Umsaetze,
    ohne das Geld zu kassieren - Warnsignal (Bsp. Lucent). Gibt {divergenz,
    warnung} oder None."""
    if not all(isinstance(x, list) for x in (inc, cf)):
        return None
    n = min(len(inc), len(cf), jahre)
    if n < 2:
        return None
    # aktuelles Jahr vs. Vorjahr
    ni_akt = _num(_g(inc[0], *_F_NETINCOME))
    ni_vj = _num(_g(inc[1], *_F_NETINCOME))
    cf_akt = _num(_g(cf[0], *_F_OPCF))
    cf_vj = _num(_g(cf[1], *_F_OPCF))
    if None in (ni_akt, ni_vj, cf_akt, cf_vj):
        return None
    ni_wachstum = (ni_akt / ni_vj - 1) if ni_vj and ni_vj > 0 else None
    cf_wachstum = (cf_akt / cf_vj - 1) if cf_vj and cf_vj > 0 else None
    if ni_wachstum is None or cf_wachstum is None:
        return None
    divergenz = ni_wachstum - cf_wachstum
    # Warnung: Gewinn waechst deutlich, Cashflow faellt oder waechst kaum
    warnung = (ni_wachstum > 0.10 and cf_wachstum < ni_wachstum - 0.15)
    stark = (ni_wachstum > 0.10 and cf_wachstum < 0)   # CF faellt trotz Gewinn+
    return {
        "gewinn_wachstum": round(ni_wachstum, 3),
        "cashflow_wachstum": round(cf_wachstum, 3),
        "divergenz": round(divergenz, 3),
        "warnung": bool(warnung),
        "stark": bool(stark),
    }
