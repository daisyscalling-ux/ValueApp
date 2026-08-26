"""
bewertung_seite.py - Der neue Bewertungsblock als EINE Funktion.

Zwei Verwendungen:

1. Einbau in die Einzelanalyse (dashboard.py). Direkt nach dem bestehenden
   Fair-Value-Block einfuegen:

       import bewertung_seite
       bewertung_seite.rendern(f, v, preset=_playbook, ticker=ticker,
                               peer_funds=_peers, pe_hist=_pe_hist,
                               umsatz_reihe=_umsatz, eps_reihe=_eps_hist)

   Alle Zusatzdaten sind optional - fehlt eine Reihe, faellt der jeweilige
   Abschnitt still weg statt zu raten.

2. Eigenstaendige Vorschau ohne das restliche Dashboard:

       streamlit run bewertung_seite.py
"""

from __future__ import annotations

from typing import List, Optional, Sequence

import streamlit as st

import relval
import schaetzguete
import ui_bewertung as ui
import valuation

METHODEN_LABEL = {
    "justified_pe": "Faires KGV", "ev_ebitda": "EV/EBITDA", "dcf": "DCF",
    "pb": "KBV", "epv": "EPV", "fwd_pe": "Forward-KGV",
    "fwd_composite": "Forward-Composite", "hist_pe": "Historisches KGV",
    "analyst": "Analystenkonsens", "fallback": "Notbehelf",
}

PLAYBOOK_LABEL = {"quality": "Qualitaet", "cyclical": "Zykliker",
                  "inflection": "Inflection", "financial": "Finanztitel"}


def rendern(fund: dict, v: dict, preset: str = "quality",
            ticker: Optional[str] = None, peer_funds=None,
            pe_hist: Optional[dict] = None,
            ev_hist: Optional[Sequence[float]] = None,
            umsatz_reihe: Optional[Sequence[float]] = None,
            eps_reihe: Optional[Sequence[float]] = None,
            fcf_reihe: Optional[Sequence[float]] = None,
            ni_reihe: Optional[Sequence[float]] = None,
            waehrung: str = "USD", theme: str = "dunkel",
            start_abschnitt: int = 1) -> None:
    """Rendert den kompletten Bewertungsblock.

    fund   fund-Dict aus providers.get_fundamentals
    v      Rueckgabe von valuation.fair_value(fund, peer_funds, preset)
    """
    ui.inject_css(theme)
    n = start_abschnitt
    preis = fund.get("price")

    # =======================================================================
    # 1 - Innerer Wert, mit Szenario-Umschalter
    # =======================================================================
    ui.abschnitt(n, "Innerer Wert")
    n += 1

    matrix = valuation.szenario_matrix(fund, peer_funds, preset)
    sz = ui.szenario_umschalter("va_sz", index=1) if matrix else "base"

    wert = (matrix["blend"].get(sz) if matrix else v.get("fair_value")) or v.get("fair_value")
    v_sz = (matrix.get("ergebnisse", {}).get(sz) if matrix else None) or v
    mos = v.get("margin_of_safety") or 0.20
    einstieg = wert * (1 - mos) if wert else None
    abweichung = ((preis - wert) / wert) if (wert and preis) else None

    teile = " \u00b7 ".join(
        f'{METHODEN_LABEL.get(k, k)} {ui.de(val, 0)}'
        for k, val in (v_sz.get("methods") or {}).items())

    farbe = ui.C["red"] if (abweichung or 0) >= 0 else ui.C["green"]
    fall_kurz = {"bear": "Bear", "base": "Base", "bull": "Bull"}[sz]
    richtung = "ueberbewertet" if (abweichung or 0) >= 0 else "unterbewertet"

    text = (
        f'Der geblendete innere Wert liegt im {fall_kurz} Case bei '
        f'<b>{ui.geld(wert, waehrung)}</b>. Gegenueber dem Kurs von '
        f'{ui.geld(preis, waehrung)} erscheint die Aktie '
        f'<b style="color:{farbe}">{richtung} um '
        f'{abs(abweichung or 0) * 100:.0f} %</b>.<br><br>'
        f'<span style="color:{ui.C["muted"]}">Playbook '
        f'{PLAYBOOK_LABEL.get(preset, preset)} \u00b7 {teile}</span><br><br>'
        f'<b>Einstieg</b> bei {mos:.0%} risikoadjustierter Sicherheitsmarge: '
        f'<b>{ui.geld(einstieg, waehrung)}</b>')

    ui.wert_kopf(
        titel=f'{ticker or fund.get("ticker", "")} Innerer Wert',
        fall=f'{fall_kurz} Case', wert=wert, preis=preis, waehrung=waehrung,
        akzent="amber", balken_label="Innerer Wert", text_html=text)

    # =======================================================================
    # 2 - Woher der Wert kommt
    # =======================================================================
    ui.abschnitt(n, "Woher der Wert kommt")
    n += 1
    ui.diagnose_karte(v.get("dcf_diagnose"), v.get("herkunft"))

    d = v.get("dcf_diagnose")
    if d:
        cc = (valuation.conversion_aus_historie(fcf_reihe, ni_reihe)
              if (fcf_reihe and ni_reihe) else None)
        bloecke = [("DCF-Annahmen", [
            ("Startwachstum", ui.pct(d.get("wachstum_start"))),
            ("Terminalwachstum", ui.pct(d.get("terminal_growth"))),
            ("Prognosezeitraum", f'{d.get("jahre")} Jahre'),
            ("WACC", ui.pct(d.get("wacc"))),
        ])]
        if cc:
            bloecke.append(("Cash-Conversion (FCF / Nettogewinn)", [
                ("Median", ui.pct(cc["median"], 0)),
                ("Streuung", ui.de(cc["streuung"], 2)),
                ("Spanne", f'{ui.de(cc["min"], 2)} \u2013 {ui.de(cc["max"], 2)}'),
                ("Jahre", str(cc["n"])),
            ]))
        ui.treiber_panel(bloecke)
        if cc and cc.get("warnung"):
            ui.hinweise([cc["warnung"]])

    # =======================================================================
    # 3 - Reverse DCF
    # =======================================================================
    anker = valuation.wachstums_anker(umsatz_reihe or [],
                                 konsens=fund.get("revenue_growth_next"))
    rd = None
    if any(anker.get(k) is not None for k in ("cagr_3j", "cagr_5j", "cagr_10j")):
        rd = valuation.reverse_dcf_analyse(fund, anker, preset)

    if rd:
        ui.abschnitt(n, "Reverse DCF", "was der Kurs verlangt")
        n += 1
        c1, c2 = st.columns([1, 1.25])
        with c1:
            kz = (f'Kurs verlangt <b>{ui.pct(rd["impliziertes_wachstum"])} / Jahr</b>'
                  f' \u00b7 Korridor bis '
                  f'<b>{ui.pct(rd["korridor"]["hoch"])}</b>')
            if rd.get("implizierte_cash_basis"):
                kz += (f'<br>Cash-Basis: <b>{ui.de(rd["implizierte_cash_basis"], 2)}x'
                       f'</b> des heutigen Free Cashflows')
            ui.urteil_box(titel=rd["urteil_titel"], text=rd["urteil_text"],
                          ton=rd["urteil_ton"],
                          chip=f'Playbook {PLAYBOOK_LABEL.get(preset, preset)}',
                          kennzahlen=kz)
        with c2:
            k = rd["korridor"]
            marker = [(valuation.ANKER_LABEL[a].split()[0], val)
                      for a, val in k["anker"].items()]
            ui.korridor_balken(tief=k["tief"], mitte=k["mitte"], hoch=k["hoch"],
                               impliziert=rd["impliziertes_wachstum"],
                               marker=marker)
        ui.hinweise(rd["hinweise"])
        ui.benchmark_tabelle(rd["zeilen"], waehrung=waehrung)
        with st.expander("Beide Treiber gleichzeitig pruefen (Wachstum \u00d7 Cash-Basis)"):
            ui.gitter_tabelle(rd["gitter"], waehrung)

    # =======================================================================
    # 4 - Szenarien je Methode
    # =======================================================================
    if matrix:
        ui.abschnitt(n, "Szenarien", "je Methode")
        n += 1
        ui.szenario_tabelle(matrix, METHODEN_LABEL, waehrung)

    # =======================================================================
    # 5 - Bewertungshistorie
    # =======================================================================
    bericht = relval.bericht(fund, pe_hist, ev_hist)
    if bericht.get("kgv") or bericht.get("ev_ebitda"):
        ui.abschnitt(n, "Bewertungshistorie", "eigenes Perzentil")
        n += 1
        ui.perzentil_kacheln(bericht)
        band = bericht.get("band")
        if band:
            ui.hinweise([
                f"Die eigenen KGV-Quartile ({band['tief']} / {band['basis']} / "
                f"{band['hoch']}) sind der bessere Ausgangspunkt fuer das "
                f"Bewertungsniveau in den Szenarien als ein gesetzter Wert."])

    # =======================================================================
    # 6 - Schaetzguete
    # =======================================================================
    guete = None
    if ticker:
        guete = schaetzguete.fuer_ticker(ticker)
    if guete and guete.get("n"):
        ui.abschnitt(n, "Schaetzguete", "des Konsens")
        n += 1
        bl = (schaetzguete.geblendetes_eps(fund.get("eps_forward"), eps_reihe, guete)
              if eps_reihe else None)
        ui.sterne_karte(guete, bl)


# ---------------------------------------------------------------------------
# Eigenstaendige Vorschau
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    st.set_page_config(page_title="Value Radar \u00b7 Bewertung", layout="wide")

    ETN = {
        "ticker": "ETN", "price": 409.52, "market_cap": 159_000_000_000,
        "shares_out": 159_000_000_000 / 409.52,
        "free_cashflow": 3.9e9, "ebitda": 6.4e9, "net_income": 3.8e9,
        "revenue": 30.0e9, "net_debt": 8.0e9, "total_debt": 10.5e9,
        "eps_trailing": 9.83, "eps_forward": 11.80, "book_value_ps": 48.0,
        "revenue_growth": 0.05, "earnings_growth": -0.04, "revenue_growth_next": 0.131,
        "beta": 1.05, "roe": 0.215, "gross_margin": 0.385,
        "operating_margin": 0.177, "net_debt_ebitda": 1.25, "current_ratio": 1.5,
        "sector": "Industrials", "industry": "Specialty Industrial Machinery",
        "ev_ebitda": 26.1, "pb": 8.5, "target_mean": 469.11, "analyst_count": 24,
        "hist_pe_median": 22.4, "roic": 0.135,
        "total_equity": 18.6e9, "total_assets": 42.0e9,
    }
    PE_HIST = {"median": 21.7, "n": 10,
               "werte": [14.2, 16.8, 18.1, 19.5, 21.0, 22.4, 24.9, 28.6, 33.1, 38.5],
               "jahre": [str(j) for j in range(2016, 2026)]}
    UMSATZ = [20.1e9, 17.9e9, 19.6e9, 20.8e9, 23.2e9, 24.9e9, 26.5e9, 28.6e9, 30.0e9]
    EPS = [5.15, 6.14, 7.47, 8.47, 9.50, 10.06, 9.83]

    theme = st.sidebar.radio("Darstellung", ["dunkel", "hell"], index=0)
    st.sidebar.caption("dunkel = passend zum bestehenden Dashboard. "
                       "hell = AlphaSpread-naeher, aber Bruch zum Rest der App.")

    preset = valuation.classify_playbook(ETN)
    v = valuation.fair_value(ETN, None, preset)

    st.markdown(f"### Eaton Corporation PLC \u00b7 NYSE:ETN")
    st.caption(f"Vorschau mit den Zahlen vom 25.08.2026 \u00b7 Playbook: {preset} "
               f"\u00b7 Schaetzguete wird ohne Netzwerk uebersprungen")

    rendern(ETN, v, preset=preset, ticker=None, pe_hist=PE_HIST,
            ev_hist=[9.1, 10.4, 11.2, 12.8, 13.9, 15.1, 17.6, 20.2, 23.4, 26.8],
            umsatz_reihe=UMSATZ, eps_reihe=EPS,
            fcf_reihe=[2.4e9, 2.5e9, 2.6e9, 3.0e9, 3.5e9, 3.9e9],
            ni_reihe=[2.2e9, 2.1e9, 2.4e9, 3.2e9, 3.9e9, 3.8e9],
            theme=theme)
