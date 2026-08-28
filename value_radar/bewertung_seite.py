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

__version__ = "2026.09.01"   # Signatur: rendern(..., fx=, waehrung=, start_abschnitt=)

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



# ---------------------------------------------------------------------------
# Abschnitte 1 und 2 als eigenstaendige Funktion auf MODULEBENE.
#
# Erste Fassung war eine verschachtelte Closure in rendern(). Streamlit
# erkennt Fragmente ueber Funktionsidentitaet und Widget-Pfad; eine Closure,
# die bei jedem Lauf neu entsteht und tief in with-Containern sitzt, ist dafuer
# keine verlaessliche Grundlage - der Umschalter reagierte danach gar nicht
# mehr. Modulebene plus ein einziges Argument ist das dokumentierte Muster.
# ---------------------------------------------------------------------------

def _abschnitt_wert(ctx: dict) -> None:
    v, fund, matrix = ctx["v"], ctx["fund"], ctx["matrix"]
    preis, preset, ticker = ctx["preis"], ctx["preset"], ctx["ticker"]
    waehrung, ab = ctx["waehrung"], ctx["start_abschnitt"]
    _w = ctx["w"]

    # =======================================================================
    # 1 - Innerer Wert, mit Szenario-Umschalter
    # =======================================================================
    # Datenluecken zuerst: ein Fair Value auf halber Datenbasis sieht genauso
    # aus wie einer auf voller - deshalb muss die Warnung VOR die Zahl.
    dq = v.get("datenqualitaet")
    vw = v.get("verworfene_methoden") or {}
    if vw:
        zeilen = [(f'{METHODEN_LABEL.get(k, k)} ({(d.get("gewicht") or 0):.0%} Gewicht)',
                   f'{ui.de(_w(d["wert"]), 2)} \u00b7 {d["vs_kurs"]:+.0f} % zum Kurs '
                   f'\u00b7 {d["grund"]}')
                  for k, d in vw.items()]
        ui.treiber_panel([("Verworfene Methoden", zeilen)])
    if dq and dq.get("warnungen"):
        ui.urteil_box(
            titel=f'Datenbasis {dq["stufe"]}',
            text=" ".join(dq["warnungen"]),
            ton=dq["ton"],
            chip=(f'{dq["gewichtsverlust"]:.0%} Gewicht fehlt'
                  if dq.get("gewichtsverlust") else ""))

    ui.abschnitt(ab, "Innerer Wert")

    if matrix:
        sz = ui.szenario_umschalter("va_sz", index=1)
    else:
        # Ohne Szenariomatrix gaebe es nichts umzuschalten - dann lieber
        # keinen Schalter als einen wirkungslosen.
        sz = "base"
        ui.hinweise(["Szenarien nicht verfuegbar: Der Titel laesst sich nur "
                     "im Base Case rechnen."])

    wert = (matrix["blend"].get(sz) if matrix else v.get("fair_value")) or v.get("fair_value")
    v_sz = (matrix.get("ergebnisse", {}).get(sz) if matrix else None) or v
    mos = v.get("margin_of_safety") or 0.20
    einstieg = wert * (1 - mos) if wert else None
    abweichung = ((preis - wert) / wert) if (wert and preis) else None

    teile = " \u00b7 ".join(
        f'{METHODEN_LABEL.get(k, k)} {ui.de(_w(val), 0)}'
        for k, val in (v_sz.get("methods") or {}).items())

    farbe = ui.C["red"] if (abweichung or 0) >= 0 else ui.C["green"]
    fall_kurz = {"bear": "Bear", "base": "Base", "bull": "Bull"}[sz]
    richtung = "ueberbewertet" if (abweichung or 0) >= 0 else "unterbewertet"

    text = (
        f'Der geblendete innere Wert liegt im {fall_kurz} Case bei '
        f'<b>{ui.geld(_w(wert), waehrung)}</b>. Gegenueber dem Kurs von '
        f'{ui.geld(_w(preis), waehrung)} erscheint die Aktie '
        f'<b style="color:{farbe}">{richtung} um '
        f'{abs(abweichung or 0) * 100:.0f} %</b>.<br><br>'
        f'<span style="color:{ui.C["muted"]}">Playbook '
        f'{PLAYBOOK_LABEL.get(preset, preset)} \u00b7 {teile}</span><br><br>'
        f'<b>Einstieg</b> bei {mos:.0%} risikoadjustierter Sicherheitsmarge: '
        f'<b>{ui.geld(_w(einstieg), waehrung)}</b>')

    ui.wert_kopf(
        titel=f'{ticker or fund.get("ticker", "")} Innerer Wert',
        fall=f'{fall_kurz} Case', wert=_w(wert), preis=_w(preis), waehrung=waehrung,
        akzent="amber", balken_label="Innerer Wert", text_html=text)

    # =======================================================================
    # 2 - Woher der Wert kommt
    # =======================================================================
    ui.abschnitt(ab + 1, "Woher der Wert kommt")
    ui.diagnose_karte(v.get("dcf_diagnose"), v.get("herkunft"))

    d = v.get("dcf_diagnose")
    if d:
        cc = fund.get("cash_conversion_info") or (
            valuation.conversion_aus_historie(ctx["fcf_reihe"], ctx["ni_reihe"])
            if (ctx["fcf_reihe"] and ctx["ni_reihe"]) else None)
        _fb = d.get("fcf_basis") or {}
        _basis_txt = ui.de(_w((_fb.get("basis") or 0) / 1e9), 2) + " Mrd"
        if _fb.get("quelle") == "normalisiert":
            _basis_txt += (
                f'<span class="from"> statt '
                f'{ui.de(_w((_fb.get("gemeldet") or 0) / 1e9), 2)} gemeldet</span>')
        bloecke = [("DCF-Annahmen", [
            ("Cashflow-Basis", _basis_txt),
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




#: Einmal beim Import registrieren, nicht bei jedem Seitenlauf.
_ABSCHNITT_WERT_FRAGMENT = (st.fragment(_abschnitt_wert)
                            if hasattr(st, "fragment") else None)


def _basis_warnung(ticker: str, v: dict) -> None:
    """Meldet, wenn sich die Rechengrundlage seit dem letzten Aufruf geaendert hat.

    Damit ist ein springender Fair Value kein Raetsel mehr: Entweder die
    Grundlage ist gleich - dann ist die Bewegung echt - oder es steht dort,
    welches Feld gefehlt hat.
    """
    if not ticker or not v.get("basis"):
        return
    try:
        import store as _store
        import valuation as _v
        # Die letzte Basis absichtlich OHNE Marker lesen: Sie soll auch nach
        # einem Bericht noch vergleichbar sein - dann steht in der Meldung,
        # dass sich die Grundlage geaendert hat, statt dass sie stumm neu
        # anfaengt.
        alt_eintrag = _store.get_anreicherung(ticker, "letzte_basis",
                                              max_alter_tage=90) or {}
        diff = _v.basis_vergleich(v["basis"], alt_eintrag.get("basis"))
        if diff:
            frueher = alt_eintrag.get("fair_value")
            kopf = "Rechengrundlage hat sich geaendert"
            if frueher and v.get("fair_value"):
                kopf += (f": Fair Value {ui.de(frueher, 2)} \u2192 "
                         f"{ui.de(v['fair_value'], 2)}")
            ui.urteil_box(titel=kopf, text=" \u00b7 ".join(diff["texte"]),
                          ton="gelb" if diff["verlaesslich"] else "rot",
                          chip="nicht vergleichbar" if not diff["verlaesslich"]
                          else "erweitert")
        _store.set_anreicherung(ticker, "letzte_basis",
                                {"basis": v["basis"],
                                 "fair_value": v.get("fair_value")})
    except Exception:
        pass


def rendern(fund: dict, v: dict, preset: str = "quality",
            ticker: Optional[str] = None, peer_funds=None,
            pe_hist: Optional[dict] = None,
            ev_hist: Optional[Sequence[float]] = None,
            umsatz_reihe: Optional[Sequence[float]] = None,
            eps_reihe: Optional[Sequence[float]] = None,
            fcf_reihe: Optional[Sequence[float]] = None,
            ni_reihe: Optional[Sequence[float]] = None,
            fx: float = 1.0, waehrung: str = "USD", theme: str = "dunkel",
            start_abschnitt: int = 1, ohne_reload: bool = False) -> None:
    """Rendert den kompletten Bewertungsblock.

    fund       fund-Dict aus providers.get_fundamentals
    v          Rueckgabe von valuation.fair_value(fund, peer_funds, preset)
    fx         Umrechnungsfaktor von der Handelswaehrung in `waehrung`.
               Gerechnet wird weiter in der Handelswaehrung - nur die ANZEIGE
               wird umgerechnet. Verhaeltniszahlen (Multiples, Wachstum,
               Perzentile) bleiben unberuehrt, sie sind waehrungsunabhaengig.
    waehrung   Anzeigewaehrung, z. B. "EUR"
    """
    def _w(x):
        """Betrag in die Anzeigewaehrung."""
        return x * fx if isinstance(x, (int, float)) and x is not None else x
    ui.inject_css(theme)
    n = start_abschnitt + 2      # 1 und 2 vergibt das Fragment
    preis = fund.get("price")

    # Die Szenariomatrix kostet drei fair_value-Laeufe und haengt NICHT am
    # gewaehlten Szenario - deshalb einmal vorab, ausserhalb des Fragments.
    # Sonst wuerde jeder Klick auf Bear/Bull sie neu berechnen.
    matrix = valuation.szenario_matrix(fund, peer_funds, preset)

    # ------------------------------------------------------------------
    # ohne_reload STANDARDMAESSIG AUS.
    #
    # Zwei Anlaeufe mit st.fragment sind gescheitert - erst als verschachtelte
    # Closure, dann auf Modulebene. Der Grund liegt nicht an der Registrierung:
    # Ein Fragment kann beim Neulauf nur in Container schreiben, die es SELBST
    # angelegt hat. Der Bewertungsblock sitzt in der Einzelanalyse tief in
    # Tabs und with-Bloecken, die ausserhalb entstehen - der Neulauf laeuft
    # dann ins Leere, und im Browser passiert genau: nichts.
    #
    # Ein Umschalter, der nichts tut, ist schlechter als einer, der die Seite
    # neu laedt. Wer es erneut versuchen will, setzt ohne_reload=True - aber
    # bitte erst, nachdem der Block aus den aeusseren Containern heraus ist.
    # ------------------------------------------------------------------
    _ctx = {"v": v, "fund": fund, "matrix": matrix, "preis": preis,
            "preset": preset, "ticker": ticker, "waehrung": waehrung,
            "start_abschnitt": start_abschnitt, "w": _w,
            "fcf_reihe": fcf_reihe, "ni_reihe": ni_reihe}
    _basis_warnung(ticker or fund.get("ticker"), v)

    if ohne_reload and _ABSCHNITT_WERT_FRAGMENT is not None:
        _ABSCHNITT_WERT_FRAGMENT(_ctx)
    else:
        _abschnitt_wert(_ctx)

    # =======================================================================
    # 3 - Reverse DCF
    # =======================================================================
    anker = valuation.wachstums_anker(umsatz_reihe or [],
                                      konsens=fund.get("revenue_growth_next"))
    rd = None
    if sum(1 for k in ("cagr_3j", "cagr_5j", "cagr_10j", "konsens")
           if anker.get(k) is not None) >= 2:
        rd = valuation.reverse_dcf_analyse(fund, anker, preset)
    elif umsatz_reihe:
        ui.hinweise([
            f"Reverse DCF uebersprungen: nur {anker.get('_jahre', 0)} Jahre "
            f"Umsatzhistorie. Ein Korridor aus so wenigen Punkten beschreibt die "
            f"letzte Phase, nicht den Zyklus - und wuerde einen teuren Kurs als "
            f"konservativ ausweisen."])

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
        _zeilen = [dict(z, wert=_w(z.get("wert"))) for z in rd["zeilen"]]
        ui.benchmark_tabelle(_zeilen, waehrung=waehrung)
        with st.expander("Beide Treiber gleichzeitig pruefen (Wachstum \u00d7 Cash-Basis)"):
            _g = rd["gitter"]
            _g_eur = dict(_g, preis=_w(_g["preis"]),
                          werte=[[_w(x) for x in reihe] for reihe in _g["werte"]])
            ui.gitter_tabelle(_g_eur, waehrung)

    # =======================================================================
    # 4 - Szenarien je Methode
    # =======================================================================
    if matrix:
        ui.abschnitt(n, "Szenarien", "je Methode")
        n += 1
        _m_eur = dict(matrix)
        _m_eur["preis"] = _w(matrix["preis"])
        _m_eur["methoden"] = {k: {sz: _w(x) for sz, x in d.items()}
                              for k, d in matrix["methoden"].items()}
        _m_eur["blend"] = {sz: _w(x) for sz, x in matrix["blend"].items()}
        if matrix.get("blend_konsistent"):
            _m_eur["blend_konsistent"] = {sz: _w(x)
                                          for sz, x in matrix["blend_konsistent"].items()}
        ui.szenario_tabelle(_m_eur, METHODEN_LABEL, waehrung)

    # =======================================================================
    # 5 - Bewertungshistorie
    # =======================================================================
    bericht = relval.bericht(fund, pe_hist, ev_hist)
    if bericht.get("kgv") or bericht.get("ev_ebitda"):
        ui.abschnitt(n, "Bewertungshistorie", "eigenes Perzentil")
        n += 1
        _b_eur = dict(bericht)
        for _k in ("kgv", "ev_ebitda"):
            if _b_eur.get(_k) and _b_eur[_k].get("rueckkehrwert"):
                _b_eur[_k] = dict(_b_eur[_k],
                                  rueckkehrwert=_w(_b_eur[_k]["rueckkehrwert"]))
        ui.perzentil_kacheln(_b_eur)
        band = bericht.get("band")
        if band:
            ui.hinweise([
                f"Die eigenen KGV-Quartile ({band['tief']} / {band['basis']} / "
                f"{band['hoch']}) sind der bessere Ausgangspunkt fuer das "
                f"Bewertungsniveau in den Szenarien als ein gesetzter Wert."])

    # =======================================================================
    # 6 - Schaetzguete
    # =======================================================================
    # providers hat die Auswertung ggf. schon gemacht und eps_forward gestutzt -
    # dann diese Zahlen zeigen, statt sie ein zweites Mal abzurufen.
    guete = fund.get("schaetzguete")
    bl = fund.get("eps_forward_herleitung")
    if not guete and ticker:
        guete = schaetzguete.fuer_ticker(ticker)
        bl = (schaetzguete.geblendetes_eps(fund.get("eps_forward"), eps_reihe, guete)
              if eps_reihe else None)
    if guete and guete.get("n"):
        ui.abschnitt(n, "Schaetzguete", "des Konsens")
        n += 1
        ui.sterne_karte(guete, bl)
        if fund.get("eps_forward_roh"):
            _roh, _neu = fund["eps_forward_roh"], fund.get("eps_forward")
            ui.hinweise([
                f"Der Konsens wurde von {ui.de(_roh, 2)} auf {ui.de(_neu, 2)} "
                f"gestutzt ({(_neu / _roh - 1) * 100:+.1f} %). Mit diesem Wert "
                f"rechnen fwd_pe, fwd_composite und hist_pe."])


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
