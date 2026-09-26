"""
valuation.py — Bewertungs-Engine v4 (schlank: 3 Kernmethoden je Playbook).

Ziel: wenige, verlaessliche, marktnahe Verfahren mit geringer Streuung.

  justified_pe : "Faires KGV" (Sockel + Stabilitaet + Marktposition x Rentabilitaet
                 + Wachstumsaufschlag) x Forward-EPS          -> Hauptanker
  ev_ebitda    : Sektor/Peer-EV-EBITDA (wachstumsadjustiert) x EBITDA - Nettoschulden
  dcf          : zweistufiger Discounted-Cashflow (konservativ, Gordon-Terminal)
  pb           : Kurs-Buchwert (KBV) — ersetzt DCF bei Zyklikern (Tief-verzerrt)

Quality/Inflection:  faires KGV (.45) + EV/EBITDA (.30) + DCF (.25)
Cyclical:            EV/EBITDA (.40) + KBV (.35) + faires KGV (.25)

Fair Value = gewichteter Blend; zusaetzlich wird die Bewertungsspanne (min-max)
ausgewiesen, damit die Streuung sichtbar bleibt.
"""
from __future__ import annotations

__version__ = "2026.09.25"   # Anker an 5 Jahre, Plausibilitaet ohne Kursanker
from typing import Dict, List, Optional, Sequence, Tuple
import math
import config

V = config.VALUATION

METHOD_LABELS = {
    "justified_pe": "Faires KGV (Punktesystem)",
    "ev_ebitda": "EV/EBITDA-Multiple (mid-cycle)",
    "dcf": "Discounted-Cashflow (DCF, 10J)",
    "pb": "Kurs-Buchwert (KBV)",
    "analyst": "Analysten-Konsensziel (\u00d8 Kursziel)",
    "epv": "Earnings Power Value (Null-Wachstum)",
    "fwd_pe": "Forward-Multiple (EPS n\u00e4chstes Jahr)",
    "fwd_composite": "Forward-Multiple 2 (KGV+EV/EBITDA-Schnitt)",
    "hist_pe": "Markt-Fair-Value (hist. Median-KGV)",
    "fallback": "Konsens-/Median-Sch\u00e4tzung (Rueckfall)",
}

_SECTOR_PB = {
    "Technology": 6, "Communication Services": 3, "Consumer Cyclical": 4,
    "Consumer Defensive": 5, "Healthcare": 4, "Financial Services": 1.3,
    "Industrials": 4, "Energy": 1.6, "Basic Materials": 1.8, "Utilities": 1.6,
    "Real Estate": 1.8, "_default": 2.5,
}


def _median(xs):
    s = sorted(xs)
    n = len(s)
    return None if n == 0 else (s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2)


def _eps(fund):
    return fund.get("eps_forward") or fund.get("eps_trailing")


def _sector(fund, table):
    """Sektoranker aus einer Tabelle - mit vereinheitlichtem Namen.

    AUDIT-BEFUND SK1: Ohne Vereinheitlichung trafen acht von zwoelf
    beobachteten Sektornamen die Tabelle nicht und fielen still auf
    _default. Ein Energiewert bekam dann 11 statt 6, ein Techwert 11 statt
    16 - unsichtbar, weil ja ein Anker geliefert wurde.
    """
    sek = fund.get("sector")
    try:
        import sektor as _sk
        sek = _sk.normalisieren(sek) or sek
    except Exception:
        pass
    return table.get(sek, table["_default"])


# Klar zyklische Branchen (yfinance-Industry-Stichwoerter)
_CYCLICAL_INDUSTRIES = [
    "oil", "gas", "coal", "mining", "metals", "steel", "copper", "aluminum",
    "gold", "silver", "auto manufacturers", "auto parts", "airlines", "shipping",
    "marine", "homebuild", "memory", "semiconductor equipment", "chemicals",
    "paper", "lumber", "agricultural inputs", "building materials", "drilling",
]
_DEFENSIVE_SECTORS = {"Utilities", "Consumer Defensive", "Healthcare"}
_CYCLICAL_SECTORS = {"Energy", "Basic Materials"}


def classify_playbook(fund) -> str:
    """Automatische Zuordnung des passenden Bewertungs-Playbooks.

      financial : Banken/Versicherer/Finanzdienstleister  (KGV + KBV; kein DCF/EV-EBITDA)
      cyclical  : klar zyklische Branche oder Sektor Energie/Rohstoffe
      inflection: Hyperwachstum (Umsatzwachstum >= 25 %)
      quality   : Standard (Compounder, defensive Werte)

    Sektor-bewusst: defensive Sektoren (Versorger, Basiskonsum, Gesundheit) werden
    NICHT zyklisch, auch wenn ein Stichwort (z. B. "gas" bei Gasversorgern) passt.
    """
    sector = fund.get("sector") or ""
    industry = (fund.get("industry") or "").lower()

    # 0) datenbasierte Zyklus-Erkennung (z.B. aus dem Backtest): stark
    # schwankende Gewinnmargen -> cyclical, auch ohne Sektor-Label.
    if fund.get("_ist_zyklisch"):
        return "cyclical"

    # 1) Finanzwerte: eigenes Modell (Gewinn + Buchwert)
    if sector == "Financial Services":
        return "financial"

    # 2) zyklisch — aber nie bei defensiven Sektoren
    if sector not in _DEFENSIVE_SECTORS:
        if sector in _CYCLICAL_SECTORS or any(k in industry for k in _CYCLICAL_INDUSTRIES):
            return "cyclical"

    # 3) Hyperwachstum
    g = fund.get("revenue_growth")
    if g is None:
        g = fund.get("earnings_growth") or 0
    if g >= 0.25:
        return "inflection"

    # 4) Standard
    return "quality"


def zweitanker_bewertung(fund, preset: str = "quality",
                         sektor_multiple: Optional[float] = None) -> Optional[dict]:
    """Derselbe Titel, gerechnet am HEUTE gemessenen Sektormultiple.

    Ersetzt nichts. Der Fair Value aus fair_value() bleibt, wie er ist - dies
    hier ist eine zweite Lesart daneben.

    Warum nicht ersetzen: Verankert man den Fair Value am aktuellen
    Sektormultiple, sagt das Modell bei jedem Sektor genau das, was der Markt
    ohnehin sagt - fair bewertet. Es koennte nie mehr feststellen, dass ein
    Sektor zu billig ist, und genau dafuer ist es da. An Adobe gerechnet:

        fester Wert (Tabelle)  16,0x  ->  316 USD  (+19 % zum Kurs)
        Sektormedian heute     11,0x  ->  216 USD  (-19 %)
        Sektormedian 2021      28,0x  ->  555 USD  (+109 %)

    Drei Anker, drei Urteile, dieselbe Firma. Die Zahl allein entscheidet
    nichts - die Frage ist, welcher Anker traegt.
    """
    if not sektor_multiple or sektor_multiple <= 0:
        return None
    ebitda = fund.get("ebitda")
    shares = fund.get("shares_out")
    if not ebitda or ebitda <= 0 or not shares or shares <= 0:
        return None
    nd = fund.get("net_debt") or 0.0
    wert = (sektor_multiple * ebitda - nd) / shares
    if not math.isfinite(wert) or wert <= 0:
        return None
    preis = fund.get("price")
    return {
        "wert": round(wert, 2),
        "multiple": round(sektor_multiple, 2),
        "upside_pct": (round((wert / preis - 1) * 100, 1) if preis else None),
        "verfahren": "EV/EBITDA am gemessenen Sektormedian",
    }


def zyklisch_aus_margen(margen, aktuelle_marge=None,
                        schwelle: float = 0.40) -> dict:
    """Zyklizitaet aus der Margenschwankung statt aus dem Branchenlabel.

    Warum das noetig ist: `_CYCLICAL_INDUSTRIES` enthaelt "memory", aber die
    Branchenangabe fuer Micron lautet schlicht "Semiconductors". Der
    Musterzykliker der Halbleiterwelt wurde deshalb als Wachstumstitel
    eingestuft - mit gewinnbasierten Verfahren auf Gipfelgewinnen, also genau
    dem Fehler, den das cyclical-Playbook vermeiden soll.

    Dieselbe Regel steckt bereits in backtest.py und hat dort funktioniert;
    sie fehlte nur im laufenden Betrieb. Variationskoeffizient der Netto-
    margen ueber mindestens vier Jahre; ueber 0,4 gilt als deutlich zyklisch.

    Liegt die aktuelle Marge klar ueber dem Zyklusschnitt, ist zusaetzlich
    Gipfelverdacht angezeigt - dann sind Gewinnmultiplikatoren am
    truegerischsten.
    """
    xs = [float(m) for m in (margen or [])
          if m is not None and math.isfinite(float(m))]
    if len(xs) < 4:
        return {"zyklisch": False, "grund": "weniger als vier Jahre Margen"}

    schnitt = sum(xs) / len(xs)
    if abs(schnitt) < 0.001:
        return {"zyklisch": False, "grund": "Durchschnittsmarge nahe null"}
    std = (sum((m - schnitt) ** 2 for m in xs) / len(xs)) ** 0.5
    vk = std / abs(schnitt)

    gipfel = (aktuelle_marge is not None and aktuelle_marge > schnitt * 1.25)
    return {
        "zyklisch": vk > schwelle,
        "variationskoeffizient": round(vk, 2),
        "schnitt_marge": round(schnitt, 4),
        "aktuelle_marge": (round(aktuelle_marge, 4)
                           if aktuelle_marge is not None else None),
        "gipfelverdacht": bool(vk > schwelle and gipfel),
        "jahre": len(xs),
        "grund": (f"Margen schwanken um {vk:.0%} des Schnitts"
                  if vk > schwelle else
                  f"Margen stabil ({vk:.0%} Schwankung)"),
    }


def wacc(beta, market_cap, total_debt, tax_rate=None) -> float:
    tax_rate = V["tax_rate"] if tax_rate is None else tax_rate
    re = V["risk_free_rate"] + (beta or V["default_beta"]) * V["equity_risk_premium"]
    rd = V["risk_free_rate"] + 0.015
    e, d = market_cap or 0.0, total_debt or 0.0
    tot = e + d
    w = re if tot <= 0 else (e / tot) * re + (d / tot) * rd * (1 - tax_rate)
    return max(w, 0.085)


# --- 1) Faires KGV ----------------------------------------------------------
def ungehebelte_ekr(fund) -> Optional[float]:
    """Schmidlins ungehebelte Eigenkapitalrendite: normalisiert die ROE auf
    eine ANGEMESSENE Eigenkapitalbasis, statt eine durch hohe Verschuldung
    aufgeblaehte ROE zu verwenden. Faustregel: Mindest-EK-Quote = Sach-
    investitionsquote (CAPEX/operativer Cashflow). Kapitalintensive Modelle
    brauchen mehr Eigenkapital -> ehrlichere Rentabilitaet. Gibt die entschuldete
    ROE (Dezimal) oder None zurueck."""
    ni = fund.get("net_income")
    assets = fund.get("total_assets") or fund.get("_total_assets")
    # Bilanzsumme aus Eigenkapital + Schulden approximieren, falls nicht direkt da
    if not assets:
        bvps = fund.get("book_value_ps")
        shares = fund.get("shares_out")
        eq = (bvps * shares) if (bvps and shares) else None
        debt = fund.get("total_debt") or 0
        if eq:
            assets = eq + (debt or 0)
    if not ni or not assets or assets <= 0:
        return None
    # Sachinvestitionsquote = CAPEX / operativer Cashflow (Naeherung ueber FCF)
    opcf = fund.get("operating_cashflow")
    fcf = fund.get("free_cashflow")
    capex = None
    if opcf is not None and fcf is not None:
        capex = abs(opcf - fcf)
    sach_quote = None
    if capex is not None and opcf and opcf > 0:
        sach_quote = capex / opcf
    if sach_quote is None:
        sach_quote = 0.35       # neutraler Default, wenn CAPEX/CF fehlt
    # Mindest-EK-Quote sinnvoll begrenzen: nie unter 25% (sonst unrealistisch
    # hohe entschuldete ROE), nie ueber 80%.
    sach_quote = min(max(sach_quote, 0.25), 0.80)
    # fiktive angemessene EK-Basis = Bilanzsumme x Mindest-EK-Quote
    fiktives_ek = assets * sach_quote
    if fiktives_ek <= 0:
        return None
    return ni / fiktives_ek


def net_net_wert(fund) -> Optional[float]:
    """Schmidlins Net-Net (Graham): schnell liquidierbares Umlaufvermoegen
    minus ALLE Verbindlichkeiten, je Aktie. Liquide Mittel zu 100%,
    Forderungen und Vorraete mit Abschlag. Notiert die Aktie darunter, ist sie
    selbst im Liquidationsfall unterbewertet - staerkste Sicherheitsmarge.
    Gibt den Net-Net je Aktie oder None zurueck."""
    cash = fund.get("cash")
    cur_assets = fund.get("current_assets") or fund.get("_current_assets")
    receivables = fund.get("receivables")
    inventory = fund.get("inventory")
    tot_liab = fund.get("total_liabilities") or fund.get("total_debt")
    shares = fund.get("shares_out")
    if not shares or shares <= 0:
        return None
    # bevorzugt Einzelposten mit Graham-Abschlaegen, sonst Umlaufvermoegen grob
    if cash is not None and receivables is not None and inventory is not None:
        liquidierbar = cash + 0.75 * receivables + 0.5 * inventory
    elif cur_assets is not None:
        liquidierbar = cur_assets * 0.7      # pauschaler Graham-Abschlag
    elif cash is not None:
        liquidierbar = cash                  # nur Cash bekannt (sehr konservativ)
    else:
        return None
    if tot_liab is None:
        return None
    net_net = (liquidierbar - tot_liab) / shares
    return net_net


def peg_ratio(fund) -> Optional[float]:
    """KGV / erwartetes Gewinnwachstum (in %). Schmidlin fuer Wachstumswerte:
    < 1 guenstig, ~1 fair, > 1 teuer."""
    eps = _eps(fund)
    price = fund.get("price")
    if not eps or eps <= 0 or not price:
        return None
    kgv = price / eps
    g = fund.get("earnings_growth")
    if g is None:
        g = fund.get("revenue_growth")
    if g is None or g <= 0:
        return None
    g_pct = g * 100
    if g_pct < 1:
        return None
    return round(kgv / g_pct, 2)


def verwaesserung(fund) -> Optional[dict]:
    """Waechst der Gewinn JE AKTIE oder nur der absolute Gewinn? Grosse Luecke
    = Verwaesserung durch neue Aktien."""
    g_ni = fund.get("earnings_growth")
    g_eps = fund.get("eps_growth")
    if g_ni is None or g_eps is None:
        return None
    luecke = g_ni - g_eps
    return {"gewinn_wachstum": round(g_ni, 3), "eps_wachstum": round(g_eps, 3),
            "luecke": round(luecke, 3), "verwaessert": luecke > 0.03}


def dynamischer_verschuldungsgrad(fund) -> Optional[float]:
    """Net Debt / operativer Cashflow: in wie vielen Jahren waere die Firma
    schuldenfrei. < 3 solide, > 5 bedenklich."""
    nd = fund.get("net_debt")
    opcf = fund.get("operating_cashflow")
    if nd is None or not opcf or opcf <= 0:
        return None
    if nd <= 0:
        return 0.0
    return round(nd / opcf, 1)


def _eps_ist(fund):
    """Das TATSAECHLICH erzielte Ergebnis je Aktie - nicht die Prognose.

    AUDIT-BEFUND V1: justified_pe rechnete ueber _eps() mit eps_forward,
    sobald eine Schaetzung vorlag. Bei Adobe (trailing 14,70 / forward 20,60)
    ergab das +109 % statt +49 % zum Kurs - der Wert wurde als unplausibel
    verworfen, und 30 % Methodengewicht fielen weg.

    Zwei Gruende, warum hier das laufende Ergebnis gehoert:

      1. Die Methode fragt "welches KGV verdient dieses Geschaeft?" und wendet
         es auf den Gewinn an. Mit einer Prognose wird daraus ein
         Forward-Verfahren - und dupliziert damit fwd_pe.
      2. eps_forward ist der Analystenkonsens. Nutzt justified_pe ihn, stammt
         ein Teil des Werts aus dem Markt, waehrend die Herkunftszerlegung ihn
         als reine Multiple-Annahme ausweist. Die Aufschluesselung waere dann
         schlicht falsch.

    Faellt das laufende Ergebnis negativ aus, gibt die Methode nichts zurueck.
    Ein gerechtfertigtes KGV auf einen Verlust ist keine Groesse.
    """
    return fund.get("eps_trailing")


def faires_kgv(fund, preset="quality") -> Optional[float]:
    """Welches KGV verdient dieses Geschaeft - unabhaengig davon, WELCHES
    Ergebnis man darauf anwendet.

    AUDIT-BEFUND V2 (Folgefehler von V1): Die Leiter steckte in
    justified_pe_number(), und die gab None zurueck, sobald kein positives
    LAUFENDES Ergebnis vorlag. Nach der Umstellung auf eps_trailing (V1)
    lieferte sie damit auch fuer fwd_pe nichts - und fwd_pe rechnete
    `eps1 * None`, was mit TypeError abbrach. Getroffen hat es genau die
    Titel mit Verlust im laufenden Jahr und positiver Prognose, also
    Turnarounds. Im Long-Short-Suchlauf ueber viele Titel war das schnell
    einer dabei.

    Der Multiplikator selbst haengt nicht am EPS - er kommt aus Rentabilitaet,
    Marge, Verschuldung und Wachstum. Deshalb steht er jetzt fuer sich, und
    jede Methode entscheidet selbst, worauf sie ihn anwendet:

        justified_pe -> laufendes Ergebnis (eps_trailing)
        fwd_pe       -> erwartetes Ergebnis (eps_forward)
    """
    base = 7.0
    stab = 0.0
    if (fund.get("free_cashflow") or 0) > 0:
        stab += 1
    nde = fund.get("net_debt_ebitda")
    if nde is not None:
        stab += 1 if nde < 2 else (0.5 if nde < 3 else 0)
    cr = fund.get("current_ratio")
    if cr and cr > 1.2:
        stab += 1
    stab = min(stab, 3)
    # Rentabilitaet: bevorzugt die UNGEHEBELTE ROE (Schmidlin), sonst rohe ROE.
    # Verhindert, dass hochverschuldete Firmen faelschlich zu profitabel wirken.
    uroe = ungehebelte_ekr(fund)
    roe = fund.get("roe")
    _basis = uroe if uroe is not None else roe
    if _basis is None:
        prof = 1.5
    else:
        prof = (0 if _basis < 0.05 else 1 if _basis < 0.10 else 2 if _basis < 0.15
                else 3 if _basis < 0.20 else 4)
    gm = fund.get("gross_margin")
    pos = (1 if (gm is None or gm < 0.30) else 1.5 if gm < 0.40 else 2 if gm < 0.50
           else 2.8 if gm < 0.65 else 3.5)
    moat = min(prof * pos, 14)
    g = fund.get("revenue_growth")
    if g is None:
        g = fund.get("earnings_growth") or 0
    gp = (0 if g < 0 else 0.5 if g < 0.03 else 1 if g < 0.05 else 2 if g < 0.07
          else 3 if g < 0.10 else 4 if g < 0.15 else 5 if g < 0.20 else
          6 if g < 0.25 else 7.5 if g < 0.35 else 9)     # Hyperwachstum differenziert
    fair_pe = base + stab + moat + gp
    if preset == "inflection":
        fair_pe *= 1.1
    cap = (50 if preset == "inflection" else 42 if preset == "quality"
           else 18 if preset == "financial" else 16)
    return max(6.0, min(fair_pe, cap))


def justified_pe_number(fund, preset="quality") -> Optional[float]:
    """Faires KGV, aber nur wenn ein laufendes Ergebnis vorliegt.

    Duenne Huelle um faires_kgv() - beibehalten, weil mehrere Stellen im
    Projekt diesen Namen benutzen. Die Pruefung auf ein positives Ergebnis
    gehoert zu justified_pe, nicht zur Leiter.
    """
    eps = _eps_ist(fund)
    if not eps or eps <= 0:
        return None
    return faires_kgv(fund, preset)


def justified_pe(fund, preset="quality") -> Optional[float]:
    pe = justified_pe_number(fund, preset)
    eps = _eps_ist(fund)
    return pe * eps if (pe and eps and eps > 0) else None


# --- 2) EV/EBITDA -----------------------------------------------------------
def multiple_ev_ebitda(fund, peer_funds, preset="quality") -> Optional[float]:
    shares, ebitda = fund.get("shares_out"), fund.get("ebitda")
    if not shares or not ebitda or ebitda <= 0:
        return None
    cyclical = (preset == "cyclical")
    if peer_funds:
        ms = [p["ev_ebitda"] for p in peer_funds if p.get("ev_ebitda") and 0 < p["ev_ebitda"] < 60]
        target = _median(ms) or _sector(fund, config.SECTOR_EV_EBITDA)
    else:
        target = _sector(fund, config.SECTOR_EV_EBITDA)
    if not cyclical:
        g = fund.get("revenue_growth") or 0
        if g > 0.10:                                  # Wachstumsaufschlag (wie beim KGV)
            target *= 1 + min((g - 0.10) * 2.0, 0.6)
        cur = fund.get("ev_ebitda")
        if cur and cur > 0:
            # Teilweise Rueckkehr zum Mittel statt Voll-Reversion: Qualitaetsfirmen
            # kehren selten ganz zum Sektorschnitt zurueck. 60% Anker + 40% eigenes
            # Multiple (gedeckelt bei 2.5x Anker) daempft den systematischen Downside.
            target = 0.6 * target + 0.4 * min(cur, 2.5 * target)
    else:
        target = min(target, 8.5)                     # niedriges Multiple auf (Peak-)EBITDA
    equity = target * ebitda - (fund.get("net_debt") or 0.0)
    return equity / shares if equity > 0 else None


# --- 3a) DCF (Quality/Inflection) ------------------------------------------
def dcf_annahmen(fund, preset="quality") -> Optional[dict]:
    """Legt die Annahmen offen, die in den DCF eingehen - fuer die
    Nachvollziehbarkeit in der Einzelanalyse. Rechnet NICHTS neu, sondern
    spiegelt exakt die Schritte aus dcf_two_stage wider, damit der Nutzer
    sieht, WORAUF der Fair Value beruht (und unplausible Eingaben wie einen
    kaputten WACC sofort erkennt). Gibt None zurueck, wenn der DCF fuer diesen
    Titel nicht traegt."""
    fcf, shares = fund.get("free_cashflow"), fund.get("shares_out")
    if not fcf or not shares or fcf <= 0 or preset == "cyclical":
        return None
    years = max(int(V.get("projection_years", 10)), 2)
    g_term = V["terminal_growth"]
    g1_roh = fund.get("revenue_growth")
    _quelle_g = "Umsatzwachstum"
    if g1_roh is None:
        g1_roh = fund.get("earnings_growth")
        _quelle_g = "Gewinnwachstum"
    if g1_roh is None:
        g1_roh = 0.06
        _quelle_g = "Standardannahme (keine Wachstumsdaten)"
    cap = 0.25 if preset == "inflection" else 0.16
    g1 = max(min(g1_roh, cap), -0.03)
    _gedeckelt = (g1 != g1_roh)
    r = wacc(fund.get("beta"), fund.get("market_cap"), fund.get("total_debt"))
    _r_angehoben = False
    if r - g_term < 0.045:
        r = g_term + 0.045
        _r_angehoben = True
    return {
        "free_cashflow": fcf,
        "shares_out": shares,
        "jahre": years,
        "wachstum_start": g1,
        "wachstum_start_roh": g1_roh,
        "wachstum_quelle": _quelle_g,
        "wachstum_gedeckelt": _gedeckelt,
        "wachstum_cap": cap,
        "terminal_growth": g_term,
        "wacc": r,
        "wacc_angehoben": _r_angehoben,
        "net_debt": fund.get("net_debt") or 0.0,
        "beta": fund.get("beta"),
    }


def fcf_basis(fund, conversion: Optional[float] = None) -> dict:
    """Welcher Free Cashflow geht in den DCF - der gemeldete oder ein
    normalisierter?

    Der gemeldete TTM-Cashflow schwankt mit Working Capital, Steuerstichtagen
    und Einmaleffekten. Ein einzelnes schwaches Jahr zieht den DCF dann in die
    Tiefe, ohne dass sich am Geschaeft etwas geaendert hat. Normalisiert heisst:
    Nettogewinn x uebliche Cash-Conversion (Median mehrerer Jahre).

    Umgestellt wird nur, wenn eine Conversion aus der Historie vorliegt
    (fund["cash_conversion"], von providers gesetzt) - sonst bleibt es beim
    gemeldeten Wert. Beide Groessen werden zurueckgegeben, damit die
    Umstellung sichtbar ist und nicht still passiert.
    """
    gemeldet = fund.get("free_cashflow")
    conv = conversion if conversion is not None else fund.get("cash_conversion")
    ni = fund.get("net_income")
    normal = (ni * conv) if (conv and ni and ni > 0) else None

    if normal and normal > 0:
        basis, quelle = normal, "normalisiert"
    else:
        basis, quelle = gemeldet, "gemeldet"

    return {"basis": basis, "gemeldet": gemeldet, "normalisiert": normal,
            "conversion": conv, "quelle": quelle,
            "abweichung": ((normal / gemeldet - 1.0)
                           if (normal and gemeldet and gemeldet > 0) else None)}


def dcf_two_stage(fund, preset="quality",
                  conversion: Optional[float] = None) -> Optional[float]:
    if preset == "cyclical":
        return None
    shares = fund.get("shares_out")
    fcf = fcf_basis(fund, conversion)["basis"]
    if not fcf or not shares or fcf <= 0:
        return None
    years = max(int(V.get("projection_years", 10)), 2)   # konsistent mit Reverse-DCF
    g_term = V["terminal_growth"]
    g1 = fund.get("revenue_growth")
    if g1 is None:
        g1 = fund.get("earnings_growth") or 0.06
    cap = 0.25 if preset == "inflection" else 0.16
    g1 = max(min(g1, cap), -0.03)
    r = wacc(fund.get("beta"), fund.get("market_cap"), fund.get("total_debt"))
    if r - g_term < 0.045:
        r = g_term + 0.045
    pv, cf = 0.0, fcf
    for t in range(1, years + 1):
        g_t = g1 + (g_term - g1) * (t - 1) / (years - 1)
        cf *= (1 + g_t)
        pv += cf / ((1 + r) ** t)
    terminal = cf * (1 + g_term) / (r - g_term) / ((1 + r) ** years)
    equity = pv + terminal - (fund.get("net_debt") or 0.0)
    return equity / shares if equity > 0 else None


def _dcf_parametrisiert(fund, preset, g_shift, r_shift) -> Optional[float]:
    """Wie dcf_two_stage, aber mit verschobenem Anfangswachstum (g_shift) und
    Diskontsatz (r_shift). Basis fuer die Bear/Base/Bull-Szenarien - die groesste
    Bewertungsunsicherheit steckt genau in diesen zwei Annahmen (Damodaran:
    'die groesste Intangible ist zukuenftiges Wachstum'). Statt einer
    Punktschaetzung zeigt das eine ehrliche Bandbreite."""
    if preset == "cyclical":
        return None
    fcf, shares = fund.get("free_cashflow"), fund.get("shares_out")
    if not fcf or not shares or fcf <= 0:
        return None
    years = max(int(V.get("projection_years", 10)), 2)
    g_term = V["terminal_growth"]
    g1 = fund.get("revenue_growth")
    if g1 is None:
        g1 = fund.get("earnings_growth") or 0.06
    cap = 0.25 if preset == "inflection" else 0.16
    g1 = max(min(g1, cap), -0.03)
    # Szenario-Verschiebung des Wachstums, danach erneut hart deckeln, damit
    # das Bull-Szenario nicht ins Unrealistische laeuft.
    g1 = max(min(g1 + g_shift, cap + 0.05), -0.06)
    r = wacc(fund.get("beta"), fund.get("market_cap"), fund.get("total_debt"))
    r = r + r_shift
    if r - g_term < 0.045:
        r = g_term + 0.045
    pv, cf = 0.0, fcf
    for t in range(1, years + 1):
        g_t = g1 + (g_term - g1) * (t - 1) / (years - 1)
        cf *= (1 + g_t)
        pv += cf / ((1 + r) ** t)
    terminal = cf * (1 + g_term) / (r - g_term) / ((1 + r) ** years)
    equity = pv + terminal - (fund.get("net_debt") or 0.0)
    return equity / shares if equity > 0 else None


def szenario_werte(fund, preset="quality") -> Optional[dict]:
    """Bear / Base / Bull als ehrliche Bandbreite statt einer Punktschaetzung.
    Die Verschiebung des Wachstums skaliert mit dem erwarteten Wachstum selbst:
    schneller wachsende Firmen sind unsicherer (Damodaran), also breitere
    Spanne. Der Diskontsatz wird fix verschoben (Risiko-Neubewertung).
    Gibt None zurueck, wenn der DCF fuer diesen Titel nicht traegt (z.B.
    zyklisch oder negativer Free Cashflow) - dann gibt es bewusst keine
    Scheingenauigkeit."""
    base = dcf_two_stage(fund, preset)
    if base is None:
        return None
    # Wachstums-Unsicherheit: mindestens 3 Pp., mehr bei hoeherem Wachstum.
    g = fund.get("revenue_growth")
    if g is None:
        g = fund.get("earnings_growth") or 0.06
    g_unsicher = max(0.03, abs(g) * 0.5)     # z.B. g=20% -> +/-10 Pp.
    bear = _dcf_parametrisiert(fund, preset, g_shift=-g_unsicher, r_shift=+0.015)
    bull = _dcf_parametrisiert(fund, preset, g_shift=+g_unsicher, r_shift=-0.010)
    if bear is None or bull is None:
        return None
    lo, hi = min(bear, base, bull), max(bear, base, bull)
    price = fund.get("price")
    return {
        "bear": round(bear, 2),
        "base": round(base, 2),
        "bull": round(bull, 2),
        "spanne_pct": round((hi - lo) / base * 100, 0) if base else None,
        "preis": price,
        "kurs_position": (round((price - lo) / (hi - lo) * 100, 0)
                          if price and hi > lo else None),
    }
def multiple_pb(fund, preset="quality") -> Optional[float]:
    bvps = fund.get("book_value_ps")
    # Fallback NUR fuer Finanzwerte: Buchwert je Aktie aus Kurs und KBV
    # rekonstruieren, wenn das direkte Feld fehlt (bei manchen Banken wie
    # JPM/Citi liefert die Quelle book_value_ps nicht, aber pb schon). Bei
    # Finanzwerten ist pb die Hauptmethode, ohne sie gibt es keinen Fair Value.
    # WICHTIG: Nur bei preset=="financial", sonst verzerrt der Fallback bei
    # Wachstumstiteln (hohes pb) den Fair Value massiv nach unten - das hatte
    # z.B. NVIDIA faelschlich von +20% auf tief negativen Upside gedreht.
    if (not bvps or bvps <= 0) and preset == "financial":
        _price, _pb = fund.get("price"), fund.get("pb")
        if _price and _pb and _pb > 0:
            bvps = _price / _pb
    if not bvps or bvps <= 0:
        return None
    target_pb = 1.8 if preset == "cyclical" else _sector(fund, _SECTOR_PB)
    return target_pb * bvps


# --- Reverse-DCF (impliziertes Wachstum, fuer Interpretation) ---------------
def reverse_dcf_implied_growth(fund, years=None) -> Optional[float]:
    price = fund.get("price")
    fcf, shares = fund.get("free_cashflow"), fund.get("shares_out")
    if not price or not fcf or not shares or fcf <= 0:
        return None
    target_equity = price * shares + (fund.get("net_debt") or 0.0)
    r = wacc(fund.get("beta"), fund.get("market_cap"), fund.get("total_debt"))
    g_term = V["terminal_growth"]
    if r - g_term < 0.04:
        r = g_term + 0.04
    yrs = years or V["projection_years"]

    def equity_for_g(g):
        pv, cf = 0.0, fcf
        for t in range(1, yrs + 1):
            cf *= (1 + g)
            pv += cf / ((1 + r) ** t)
        pv += cf * (1 + g_term) / (r - g_term) / ((1 + r) ** yrs)
        return pv

    lo, hi = -0.20, 0.60
    for _ in range(60):
        mid = (lo + hi) / 2
        if equity_for_g(mid) < target_equity:
            lo = mid
        else:
            hi = mid
    return round((lo + hi) / 2, 4)


# --- Neue Methoden (Nutzer-Formelsammlung, geprueft & korrigiert) -------------
def _ebit_estimate(fund) -> Optional[float]:
    """EBIT-Schaetzung: operative Marge x Umsatz.

    FRUEHER wurde der Umsatz IMMER aus MarketCap/KUV hergeleitet. Ist das
    KUV verzerrt (z.B. weil die Quelle es mit einem Pence-Kurs gegen
    Pfund-Umsaetze rechnet), wird der Umsatz um Groessenordnungen falsch -
    und der EPV-Wert entgleist (BP.L: 1792 statt ~5 je Aktie).
    Jetzt: echtes Umsatzfeld bevorzugen, KUV nur als Rueckfall, und das
    Ergebnis gegen den Umsatz auf Plausibilitaet pruefen."""
    om = fund.get("operating_margin")
    rev = fund.get("revenue")
    mc, ps = fund.get("market_cap"), fund.get("ps")

    if not (rev and rev > 0) and (mc and ps and ps > 0):
        derived = mc / ps                      # Rueckfall: Umsatz aus KUV
        # Grober Realitaetscheck: Umsatz zwischen 1 % und 100x der Marktkap.
        if 0.01 * mc <= derived <= 100 * mc:
            rev = derived

    if om and om > 0 and rev and rev > 0:
        return om * rev
    ebitda = fund.get("ebitda")
    return 0.8 * ebitda if ebitda and ebitda > 0 else None


def epv(fund, preset="quality") -> Optional[float]:
    """Earnings Power Value (Greenwald): Wert bei NULL Wachstum ab heute.
    NOPAT = EBIT x (1 - Steuersatz); EV_epv = NOPAT / WACC.
    KORREKTUR ggue. Vorlage: Nettoverschuldung MUSS abgezogen werden, sonst
    wird der Unternehmenswert (EV) faelschlich als Eigenkapitalwert ausgegeben."""
    ebit = _ebit_estimate(fund)
    shares = fund.get("shares_out")
    if not ebit or not shares or ebit <= 0:
        return None
    nopat = ebit * (1 - V["tax_rate"])
    w = wacc(fund.get("beta"), fund.get("market_cap"), fund.get("total_debt"))
    ev_epv = nopat / w
    equity = ev_epv - (fund.get("net_debt") or 0.0)
    return equity / shares if equity > 0 else None


def fwd_pe(fund, preset="quality") -> Optional[float]:
    """Forward-Multiple (einfach): erwartetes EPS x Ziel-KGV.
    Ziel-KGV = unser faires KGV aus dem Punktesystem (kein gewuerfelter Wert)."""
    eps1 = fund.get("eps_forward")
    if not eps1 or eps1 <= 0:
        return None
    # Die Leiter direkt, nicht ueber justified_pe_number: Diese verlangt ein
    # positives laufendes Ergebnis, das fuer ein FORWARD-Verfahren aber gar
    # nicht noetig ist. Zusaetzlich gegen None abgesichert - ohne Rentabilitaets-
    # oder Margendaten kommt keine Leiter zustande.
    kgv = faires_kgv(fund, preset)
    return eps1 * kgv if kgv else None


def fwd_composite(fund, preset="quality") -> Optional[float]:
    """Forward-Multiple 2 (erweitert): Durchschnitt aus verfuegbaren Komponenten
    A) EPS_fwd x Ziel-KGV,  B) (EBITDA_fwd x Ziel-EV/EBITDA - Nettoverschuldung)/Aktien.
    (Umsatz-Komponente entfaellt mangels verlaesslicher Forward-Umsatzschaetzung
    in den freien Daten - lieber 2 solide Komponenten als 3 mit einer geratenen.)"""
    parts = []
    a = fwd_pe(fund, preset)
    if a:
        parts.append(a)
    ebitda, shares = fund.get("ebitda"), fund.get("shares_out")
    if ebitda and ebitda > 0 and shares:
        g = fund.get("revenue_growth")
        g = max(min(g if g is not None else 0.0, 0.30), -0.10)
        ebitda_fwd = ebitda * (1 + g)
        sector = fund.get("sector") or "_default"
        target = config.SECTOR_EV_EBITDA.get(sector, config.SECTOR_EV_EBITDA["_default"])
        if preset == "cyclical":
            target = min(target, 8.5)
        equity = ebitda_fwd * target - (fund.get("net_debt") or 0.0)
        if equity > 0:
            parts.append(equity / shares)
    if not parts:
        return None
    return sum(parts) / len(parts)


def hist_pe(fund, preset="quality") -> Optional[float]:
    """Markt-Fair-Value: Forward-EPS x historischer Median-KGV (5-8 Jahre).
    Braucht die historische KGV-Reihe (fund['hist_pe_median'], via FMP im
    Deep-Modus). Ohne Daten: Methode entfaellt still."""
    eps1 = fund.get("eps_forward") or fund.get("eps_trailing")
    med = fund.get("hist_pe_median")
    if not eps1 or eps1 <= 0 or not med or med <= 0:
        return None
    med = min(med, 60.0)                      # Ausreisser-Schutz
    return eps1 * med


# --- 4) Analysten-Konsensziel ------------------------------------------------
def analyst_target(fund) -> Optional[float]:
    """Durchschnittliches Analysten-Kursziel als externe Konsens-Quelle.
    Das ist der Wert, den Portale wie TradingView/Marketscreener/Banken zeigen \u2013
    er verankert unsere modellbasierte Bewertung in der Markt-Realit\u00e4t.
    Plausibilit\u00e4t: nur akzeptieren, wenn 0.3x..3.5x des Kurses (Datenfehler-Schutz)."""
    tgt, price = fund.get("target_mean"), fund.get("price")
    if not tgt or not price or price <= 0:
        return None
    if not (0.3 * price <= tgt <= 3.5 * price):
        return None
    return float(tgt)


# --- Blend ------------------------------------------------------------------
# Analysten-Konsens ist bewusst substanziell gewichtet: unsere Modelle sind
# konservativ (mid-cycle-Multiples, gedeckelter DCF) und liegen bei teuren
# Wachstumsaktien systematisch unter dem Markt; der Analystenkonsens zieht die
# Bewertung Richtung dessen, was der Markt tatsaechlich einpreist.
# Ausgeduennt auf die 3 etabliertesten Kernmethoden je Aktientyp + Analyst
# als Anker (~15%). Weniger, dafuer die verlaesslichsten Methoden - das macht
# den Fair Value robuster und nachvollziehbarer. Der Analyst-Konsens bleibt
# als marktbasierter Stabilisator drin, aber mit reduziertem Gewicht, damit
# der Fair Value staerker von den Fundamentaldaten getragen wird (und damit
# unabhaengiger vom Markt - wichtig, um ihn spaeter GEGEN den Markt zu messen).
_WEIGHTS = {
    # Quality: DCF (Ertragskraft) + faires KGV + EV/EBITDA
    "quality":    {"dcf": .30, "justified_pe": .30, "ev_ebitda": .25, "analyst": .15},
    # Inflection: Forward-Multiples + DCF (Zukunftssicht fuer Wachstum/Turnaround)
    "inflection": {"fwd_pe": .30, "fwd_composite": .25, "dcf": .30, "analyst": .15},
    # Cyclical: mid-cycle-Multiple + Substanz (Buchwert) + normalisierte Ertragskraft
    "cyclical":   {"ev_ebitda": .35, "pb": .25, "epv": .25, "analyst": .15},
    # Financial: KBV (Bank-Standard) + faires KGV + Forward-KGV
    "financial":  {"pb": .35, "justified_pe": .30, "fwd_pe": .20, "analyst": .15},
}


def kursziel_12m(fund, preset="quality") -> Optional[dict]:
    """12-Monats-KURSZIEL - was der Kurs erreichen kann, NICHT was die Firma
    wert ist.

    Bewusst getrennt vom Fair Value. Der Fair Value fragt "was ist das
    Geschaeft wert?" und mittelt dafuer mehrere Verfahren - bei uneinigen
    Methoden ein fauler Kompromiss. Das Kursziel fragt etwas anderes und
    beobachtbares: "Wohin bewegt sich der Kurs, wenn die Gewinne wie erwartet
    wachsen und der Markt sein normales Vielfache dafuer zahlt?"

    Rechnung (zwei beobachtbare Bausteine, kein Modell):
        Ziel = erwarteter Gewinn je Aktie  x  normales KGV

      1. erwarteter Gewinn = eps_forward (Analystenkonsens, real messbar)
      2. normales KGV      = historischer KGV-Median (was der Markt fuer
                             diese Firma ueblicherweise zahlt)

    Die Rueckkehr zum historischen KGV ist gedeckelt: Bei einem Titel, dessen
    KGV gerade explodiert oder eingebrochen ist, wuerde die volle Rueckkehr
    absurde Ziele erzeugen. Deshalb hoechstens eine begrenzte Bewegung des
    Multiples je Jahr.

    Rueckgabe: {ziel, upside_pct, eps_annahme, kgv_annahme, herleitung, vs_analyst}
    """
    kurs = fund.get("price")
    eps_fwd = fund.get("eps_forward")
    eps_ttm = fund.get("eps_trailing")
    if not kurs or kurs <= 0:
        return None

    # --- Baustein 1: erwarteter Gewinn ---------------------------------
    # Vorzug: Forward-EPS (Konsens). Fehlt es, aus dem TTM-EPS mit dem
    # begrenzten Gewinnwachstum hochrechnen - dann als "geschaetzt" markiert.
    eps_quelle = "Forward-EPS (Konsens)"
    eps = eps_fwd
    if not eps or eps <= 0:
        g = fund.get("earnings_growth")
        if g is None:
            g = fund.get("revenue_growth")
        if eps_ttm and eps_ttm > 0 and g is not None:
            eps = eps_ttm * (1 + max(min(g, 0.30), -0.20))
            eps_quelle = "TTM-EPS x Wachstum (kein Konsens vorhanden)"
        else:
            return None                    # ohne Gewinnbasis kein Kursziel

    # --- Baustein 2: normales Vielfache --------------------------------
    kgv_heute = kurs / eps_ttm if (eps_ttm and eps_ttm > 0) else None
    kgv_hist = fund.get("hist_pe_median")

    if kgv_hist and kgv_hist > 0:
        if kgv_heute and kgv_heute > 0:
            # Rueckkehr zum historischen Median. WICHTIG (Befund NEE): Frueher
            # war der Schritt symmetrisch auf 30% des Abstands gedeckelt -
            # dadurch konnte der Gewinnzuwachs (eps_forward > trailing, fast
            # immer) die KGV-Senkung locker schlagen, und JEDES Ziel zeigte
            # nach oben.
            #
            # Jetzt asymmetrisch: Ist der Titel TEUER (KGV ueber Schnitt), zieht
            # die Rueckkehr staerker nach unten - je teurer, desto mehr. Das
            # erzeugt fallende Ziele bei ueberbewerteten Aktien, wie es sein
            # soll. Nach oben (Titel billig) bleibt es zurueckhaltend.
            abstand = kgv_hist - kgv_heute        # negativ, wenn teuer
            teuer = kgv_heute > kgv_hist
            if teuer:
                # bis zu 55% der Ueberbewertung im ersten Jahr abbauen
                anteil = 0.55
                grenze = kgv_heute * 0.35         # bis -35% des KGV moeglich
            else:
                anteil = 0.25                     # billig: vorsichtig
                grenze = kgv_heute * 0.15
            schritt = abstand * anteil
            schritt = max(min(schritt, kgv_heute * 0.15), -grenze)
            kgv_ziel = kgv_heute + schritt
            _ri = "senkt" if teuer else "hebt"
            kgv_quelle = (f"{kgv_heute:.0f}x heute \u2192 {kgv_ziel:.0f}x "
                          f"(Rueckkehr {_ri} Richtung Schnitt {kgv_hist:.0f}x)")
        else:
            kgv_ziel = kgv_hist
            kgv_quelle = f"historischer Median {kgv_hist:.0f}x"
    elif kgv_heute and kgv_heute > 0:
        # Keine Historie: heutiges KGV halten (kein Multiple-Wandel unterstellt)
        kgv_ziel = kgv_heute
        kgv_quelle = f"{kgv_heute:.0f}x gehalten (keine KGV-Historie)"
    else:
        return None

    ziel = eps * kgv_ziel
    if not math.isfinite(ziel) or ziel <= 0:
        return None

    upside = (ziel / kurs - 1) * 100
    analyst = fund.get("target_mean")
    vs_analyst = ((ziel / analyst - 1) * 100) if analyst and analyst > 0 else None

    herleitung = [
        f"Erwarteter Gewinn: {eps:.2f} je Aktie ({eps_quelle})",
        f"Normales Vielfache: {kgv_quelle}",
        f"Ziel = {eps:.2f} \u00d7 {kgv_ziel:.0f} = {ziel:.0f}",
    ]

    # Plausibilitaet: Ein 12-Monats-Ziel ueber +/-50% ist keine belastbare
    # Prognose mehr, sondern eine Wette. Der Wert bleibt sichtbar (nicht
    # gedeckelt - das waere Schoenrechnerei), aber ausdruecklich markiert.
    extrem = abs(upside) > 50
    if extrem:
        herleitung.append(
            f"\u26a0 {upside:+.0f}% in 12 Monaten ist sehr viel - das setzt "
            f"voraus, dass Gewinnsprung UND Multiple gleichzeitig eintreten. "
            f"Als Richtung lesen, nicht als Punktziel.")

    return {
        "ziel": round(ziel, 2),
        "upside_pct": round(upside, 1),
        "extrem": extrem,
        "eps_annahme": round(eps, 2),
        "kgv_annahme": round(kgv_ziel, 1),
        "kgv_heute": round(kgv_heute, 1) if kgv_heute else None,
        "kgv_hist": kgv_hist,
        "analyst_target": analyst,
        "vs_analyst": round(vs_analyst, 1) if vs_analyst is not None else None,
        "herleitung": herleitung,
    }


def kurs_projektion(fund, kursziel_12m_wert=None, vola_pct=None,
                    preset="quality") -> Optional[dict]:
    """EXPERIMENTELL: Wohin koennte sich der Kurs in 1/3/6 Monaten bewegen,
    wenn alles normal verlaeuft?

    Ausdruecklich KEINE Vorhersage - niemand kann Kurse vorhersagen. Was das
    hier zeigt, ist eine mechanische Fortschreibung:

      Anker:  das 12-Monats-Ziel (erwarteter Gewinn x normales Multiple).
              Von dort aus wird linear zurueckgerechnet - in 1 Monat ist erst
              1/12 des Weges plausibel, in 6 Monaten die Haelfte.

      Spanne: die Unsicherheit waechst mit der Wurzel der Zeit (so verhalten
              sich Kursschwankungen). Aus der Jahresvolatilitaet ergibt sich
              je Horizont ein Band nach oben und unten.

    Der MITTELWERT ist kaum aussagekraeftig - die SPANNE ist die Botschaft:
    Sie zeigt, wie wenig ueber kurze Zeitraeume gesagt werden kann. Genau
    deshalb wird sie mitgeliefert und nicht versteckt.
    """
    kurs = fund.get("price")
    if not kurs or kurs <= 0:
        return None

    ziel = kursziel_12m_wert
    if ziel is None:
        kz = kursziel_12m(fund, preset)
        ziel = kz["ziel"] if kz else None
    # Ohne Ziel: nur Seitwaerts mit Vola-Band (keine Richtung unterstellt)
    jahres_rendite = (ziel / kurs - 1) if ziel else 0.0

    # Volatilitaet: aus Momentum-Daten, sonst aus Beta grob geschaetzt.
    if vola_pct is None:
        beta = fund.get("beta") or 1.0
        # Marktvola ~18 %/Jahr, mit Beta skaliert - grobe Naeherung.
        vola_pct = 18.0 * max(0.5, min(beta, 2.5))
    vola = vola_pct / 100.0

    import math
    horizonte = [("1 Monat", 1 / 12), ("3 Monate", 3 / 12), ("6 Monate", 6 / 12)]
    punkte = []
    for name, t in horizonte:
        # Erwartete Bewegung: anteilig am Jahresziel
        mitte = kurs * (1 + jahres_rendite * t)
        # Unsicherheitsband: 1 Standardabweichung, mit sqrt(t) skaliert
        band = kurs * vola * math.sqrt(t)
        punkte.append({
            "horizont": name,
            "monate": round(t * 12),
            "mitte": round(mitte, 2),
            "tief": round(mitte - band, 2),
            "hoch": round(mitte + band, 2),
            "spanne_pct": round(band / kurs * 100, 1),
        })

    return {
        "kurs": round(kurs, 2),
        "ziel_12m": round(ziel, 2) if ziel else None,
        "vola_pct": round(vola_pct, 1),
        "punkte": punkte,
        "warnung": ("Mechanische Fortschreibung, keine Vorhersage. Die Spanne "
                    "ist die eigentliche Aussage - sie zeigt, wie gross die "
                    "Unsicherheit auf kurze Sicht ist."),
    }


def eigenes_ziel(fund, fair_value, preset="quality", regime_ampel=None,
                 pe_perzentil=None, analyst_target=None):
    """Eigenes, ausgewogenes 12-Monats-Kursziel - der 'eigene Analyst'.

    Projiziert den FAIR VALUE 12 Monate voraus, mit drei transparenten,
    datenbasierten Anpassungen. Ausgewogen = bester Schaetzwert, keine
    kuenstliche Marge nach oben oder unten. Gibt neben dem Ziel eine
    vollstaendige Herleitung zurueck, damit nachvollziehbar bleibt, WIE es
    entstand und wie es zum Analystenkonsens steht.

    Bewusst KEINE Auftragsbestaende/News (stehen nicht in den strukturierten
    Daten) - nur was das Tool belastbar weiss: Wachstum, Qualitaet, Bewertungs-
    historie, Marktregime.

    Rueckgabe: {ziel, upside_pct, herleitung: [...], vs_analyst, basis}
    """
    if not fair_value or fair_value <= 0:
        return None
    schritte = []
    ziel = float(fair_value)
    schritte.append(f"Basis: Fair Value {fair_value:.2f}")

    # --- 1) Wachstums-Projektion, qualitaetsgewichtet ---
    g = fund.get("revenue_growth")
    if g is None:
        g = fund.get("earnings_growth")
    if g is None:
        g = 0.0
    g = max(min(g, 0.25), -0.10)          # roh auf [-10%, +25%] begrenzen

    # Qualitaet bestimmen (0..1): hohe Qualitaet -> Wachstum zaehlt voll
    roic = fund.get("roic")
    opm = fund.get("operating_margin")
    q_faktor = 0.6                         # neutraler Default
    if roic is not None:
        # ROIC 5% -> 0.4, 15% -> 0.85, 25%+ -> 1.0
        q_faktor = max(0.4, min(1.0, 0.4 + (roic - 0.05) * 3.0))
    elif opm is not None:
        q_faktor = max(0.4, min(1.0, 0.4 + opm * 2.0))

    g_eff = g * q_faktor
    g_eff = max(min(g_eff, 0.12), -0.10)   # Deckel gegen Fantasie: max +12%
    ziel_nach_g = ziel * (1 + g_eff)
    schritte.append(
        f"Wachstum {g*100:+.1f}% \u00d7 Qualitaet {q_faktor:.2f} "
        f"= {g_eff*100:+.1f}% wirksam \u2192 {ziel_nach_g:.2f}")
    ziel = ziel_nach_g

    # --- 2) Bewertungs-Rueckkehr (mean reversion ueber KGV-Perzentil) ---
    if pe_perzentil is not None:
        # 80.+ Perzentil (teuer) -> bis -6% daempfen; 20- (guenstig) -> bis +6%
        if pe_perzentil >= 80:
            adj = -0.06 * ((pe_perzentil - 80) / 20.0 + 0.5)
        elif pe_perzentil <= 20:
            adj = 0.06 * ((20 - pe_perzentil) / 20.0 + 0.5)
        else:
            adj = 0.0
        adj = max(min(adj, 0.06), -0.06)
        if abs(adj) >= 0.005:
            ziel_nach_b = ziel * (1 + adj)
            lage = "historisch teuer" if adj < 0 else "historisch guenstig"
            schritte.append(
                f"Bewertungs-Ruckkehr ({lage}, KGV-Perzentil "
                f"{pe_perzentil}) \u2192 {adj*100:+.1f}% \u2192 {ziel_nach_b:.2f}")
            ziel = ziel_nach_b

    # --- 3) Marktregime-Daempfung (klein, max -5%) ---
    if regime_ampel == "rot":
        ziel_nach_r = ziel * 0.95
        schritte.append(f"Marktregime rot \u2192 -5% Vorsicht \u2192 {ziel_nach_r:.2f}")
        ziel = ziel_nach_r
    elif regime_ampel == "gelb":
        ziel_nach_r = ziel * 0.98
        schritte.append(f"Marktregime gelb \u2192 -2% \u2192 {ziel_nach_r:.2f}")
        ziel = ziel_nach_r

    ziel = round(ziel, 2)
    price = fund.get("price")
    upside = round((ziel / price - 1) * 100, 1) if price else None

    # Vergleich zum Analystenkonsens
    vs_analyst = None
    if analyst_target and analyst_target > 0:
        vs_analyst = round((ziel / analyst_target - 1) * 100, 1)

    return {"ziel": ziel, "upside_pct": upside, "herleitung": schritte,
            "vs_analyst": vs_analyst, "basis": round(float(fair_value), 2)}


def fair_value(fund, peer_funds=None, preset="quality") -> dict:
    methods = {
        "justified_pe": justified_pe(fund, preset),
        "ev_ebitda": multiple_ev_ebitda(fund, peer_funds, preset),
        "dcf": dcf_two_stage(fund, preset),
        "pb": multiple_pb(fund, preset),
        "epv": epv(fund, preset),
        "fwd_pe": fwd_pe(fund, preset),
        "fwd_composite": fwd_composite(fund, preset),
        "hist_pe": hist_pe(fund, preset),
        "analyst": analyst_target(fund),
    }
    weights = _WEIGHTS.get(preset, _WEIGHTS["quality"])
    price = fund.get("price")

    # -- Robuste Methodenauswahl (verhindert die >1000%-Divergenzen) ------------
    # 1) Verfuegbare, positive Methoden im Playbook.
    raw = {k: v for k, v in methods.items() if v and v > 0 and k in weights}

    # 2) Plausibilitaets-Filter gegen den Kurs: Ein einzelner Fair Value, der
    #    <0.25x oder >4x Kurs impliziert, stammt fast immer aus einer fuer diese
    #    Aktie ungeeigneten Methode (neg. EBITDA, Blasen-KGV, DCF ohne FCF). Raus.
    # ------------------------------------------------------------------
    # PLAUSIBILITAET: Der Filter verankerte bisher fest am Kurs (0,25x bis 4x)
    # und unterstellte damit, dass der Markt ungefaehr recht hat. Fuer einen
    # Zykliker am Gewinngipfel ist das genau verkehrt: Dort sagen die
    # mid-cycle-Verfahren bewusst 70-85 % unter Kurs - und wurden dafuer
    # aussortiert. Bei Micron fielen so ueber 80 % des Methodengewichts weg,
    # und uebrig blieb ausgerechnet das Analystenziel.
    #
    # Zwei Korrekturen:
    #   1. Zykliker bekommen ein weiteres Band. Ein Faktor 8 zwischen Tal und
    #      Gipfel ist im Speichergeschaeft normal, kein Datenfehler.
    #   2. Sind sich die Verfahren EINIG, dass der Wert weit unter dem Kurs
    #      liegt (Median unter 0,3x Kurs), ist der Kurs kein brauchbarer Anker
    #      mehr. Dann greift nur noch der Median-Filter weiter unten - denn
    #      Uebereinstimmung mehrerer Verfahren ist ein Befund, kein Ausrutscher.
    # ------------------------------------------------------------------
    _untergrenze = 0.12 if preset == "cyclical" else 0.25
    _obergrenze = 5.0 if preset == "cyclical" else 4.0

    _roh_werte = sorted(v for v in raw.values()
                        if v is not None and math.isfinite(v) and v > 0)
    _median_roh = (_roh_werte[len(_roh_werte) // 2] if _roh_werte else None)
    _kurs_taugt_als_anker = not (price and _median_roh
                                 and _median_roh < 0.30 * price)

    def _plausible(v):
        if not price or not _kurs_taugt_als_anker:
            return True
        return _untergrenze * price <= v <= _obergrenze * price

    sane = {k: v for k, v in raw.items() if _plausible(v)}
    # Was der Plausibilitaetsfilter aussortiert, wird protokolliert. Faellt eine
    # Methode mit 30 % Gewicht heraus, verteilt sich ihr Gewicht auf den Rest -
    # der Fair Value steht dann auf einer voellig anderen Grundlage, ohne dass
    # das bisher irgendwo sichtbar war.
    _verworfen = {k: {"wert": round(v, 2),
                      "vs_kurs": round((v / price - 1) * 100, 1) if price else None,
                      "gewicht": weights.get(k),
                      "grund": (f"unter {_untergrenze:.2f}x Kurs"
                                if price and v < _untergrenze * price
                                else f"ueber {_obergrenze:.0f}x Kurs")}
                  for k, v in raw.items() if k not in sane}

    # 3) Ausreisser gegen den Median der plausiblen Methoden entfernen: nur was
    #    im Band [Median/2, Median*2] liegt, bildet den "Core". So kann eine
    #    einzelne stark abweichende Methode das Ergebnis nicht mehr verzerren.
    if len(sane) >= 3:
        med0 = _median(list(sane.values()))
        core = {k: v for k, v in sane.items()
                if med0 and (med0 / 2.0) <= v <= (med0 * 2.0)}
        for k, v in sane.items():
            if k not in core:
                _verworfen[k] = {"wert": round(v, 2),
                                 "vs_kurs": round((v / price - 1) * 100, 1) if price else None,
                                 "gewicht": weights.get(k),
                                 "grund": f"mehr als Faktor 2 vom Median ({med0:.0f}) entfernt"}
        if len(core) < 2:
            core = dict(sane)
    else:
        core = dict(sane)

    # 4) Analysten-Konsens als marktbasierten Anker IMMER einbeziehen (wenn
    #    plausibel) - stabilisiert gerade schwer bewertbare Titel.
    anl_raw = methods.get("analyst")
    anl_ok = bool(anl_raw and anl_raw > 0 and _plausible(anl_raw))
    if anl_ok:
        core["analyst"] = anl_raw

    # 5) Letzter Rueckfall, falls alles gefiltert wurde: Analystenziel, sonst
    #    der (gegen den Kurs geklammerte) Median aller Rohwerte -> nie "kein Wert".
    used_fallback = False
    if not core:
        fb = anl_raw if (anl_raw and anl_raw > 0) else _median(list(raw.values()))
        if fb and price:
            fb = max(min(fb, 2.0 * price), 0.5 * price)
        if fb:
            core = {"fallback": fb}
            used_fallback = True

    # 6) Anzeige: die (bis zu) 3 Methoden, die dem Ergebnis am naechsten liegen -
    #    sie erklaeren den Fair Value und wirken konsistent (statt 3x nach Gewicht).
    avail = dict(core)

    # Begruendung der Methodenwahl (pro Aktie): was wurde warum genutzt/uebersprungen
    profile_notes = []
    if preset == "inflection":
        profile_notes.append("Wachstumsprofil: Forward-Multiples + DCF + Analysten; "
                             "EPV/KBV \u00fcbersprungen (bestrafen Wachstum)")
    elif preset == "cyclical":
        profile_notes.append("Zykliker: mid-cycle-Multiples + Substanz (EPV/KBV); "
                             "DCF \u00fcbersprungen (Peak-Cashflows verzerren)")
    elif preset == "financial":
        profile_notes.append("Finanztitel: KBV/KGV-basiert; EV/EBITDA & DCF nicht sinnvoll")
    else:
        profile_notes.append("Qualit\u00e4tsprofil: breiter Methodenmix inkl. EPV-Substanzanker")
    if "dcf" in weights and "dcf" not in avail:
        profile_notes.append("DCF entf\u00e4llt (kein positiver FCF)")
    if "epv" in weights and "epv" not in avail:
        profile_notes.append("EPV entf\u00e4llt (kein belastbares EBIT)")
    if preset in ("quality", "inflection") and "fwd_pe" in weights and "fwd_pe" not in avail \
            and "fwd_composite" not in avail:
        profile_notes.append("Forward-Multiples entfallen (kein Forward-EPS)")
    if "analyst" not in avail:
        profile_notes.append("kein Analysten-Konsensziel verf\u00fcgbar")

    # Divergenz Modell vs. Analysten transparent machen (Core ohne Analyst)
    model_vals = [v for k, v in core.items() if k not in ("analyst", "fallback")]
    model_fv = _median(model_vals) if model_vals else None
    anl = core.get("analyst") or (anl_raw if anl_ok else None)
    divergence = (round((anl / model_fv - 1) * 100, 1)
                  if (anl and model_fv) else None)

    fv, capped, lo, hi, spread = None, False, None, None, None
    if core:
        vals = list(core.values())
        lo, hi = min(vals), max(vals)
        med = _median(vals)
        spread = round((hi - lo) / med * 100, 0) if med else None
        # Gewichteter Schnitt der Core-Methoden (Playbook-Gewichte, renormalisiert;
        # unbekannte Keys wie 'fallback' erhalten ein neutrales Gewicht).
        wsum = sum(weights.get(k, 0.15) for k in core)
        fv = (sum(core[k] * weights.get(k, 0.15) for k in core) / wsum) if wsum else med
        if fv and price:                            # letzter Sicherheits-Deckel
            if fv > price * config.FAIR_VALUE_MAX_MULT:
                fv, capped = price * config.FAIR_VALUE_MAX_MULT, True
            elif fv < price * config.FAIR_VALUE_MIN_MULT:
                fv, capped = price * config.FAIR_VALUE_MIN_MULT, True

    # Herkunftsanalyse VOR der Anzeige-Reduktion: sie muss den vollen Core
    # sehen, nicht die drei angezeigten Methoden. Faellt still aus, wenn das
    # Zusatzmodul fehlt.
    try:
        _herkunft = herkunft(core, weights)
    except Exception:
        _herkunft = None

    # Anzeige auf die 3 dem Ergebnis naechsten Methoden reduzieren (repraesentativ)
    if fv and len(avail) > 3:
        near = sorted(avail.items(), key=lambda kv: abs(kv[1] - fv))[:3]
        avail = dict(near)

    mos = config.MARGIN_OF_SAFETY.get(preset, 0.20)
    # Schmidlin: die geforderte Sicherheitsmarge steigt mit dem RISIKO des
    # einzelnen Titels, nicht nur mit dem Playbook-Typ. Schwache Bilanz oder
    # hohe Verschuldung -> hoehere Marge fordern (bis +12 Punkte).
    _risk_add = 0.0
    _nde = fund.get("net_debt_ebitda")
    if _nde is not None and _nde > 3:
        _risk_add += 0.04 if _nde <= 4 else 0.08     # hohe Verschuldung
    if (fund.get("free_cashflow") or 0) < 0:
        _risk_add += 0.04                            # verbrennt Cash
    _cr = fund.get("current_ratio")
    if _cr is not None and _cr < 1.0:
        _risk_add += 0.03                            # schwache Liquiditaet
    if fund.get("_ist_zyklisch"):
        _risk_add += 0.03                            # Zykliker: extra vorsichtig
    mos = min(mos + _risk_add, 0.55)                 # Deckel bei 55%
    fund["_mos_verwendet"] = round(mos, 3)
    entry = fv * (1 - mos) if fv else None
    g1 = fund.get("revenue_growth")
    if g1 is None:                                  # nur bei fehlendem Wert ersetzen
        g1 = V["terminal_growth"]                   # (0.0-Wachstum bleibt 0.0)
    g1 = max(min(g1, 0.12), 0.0)
    target_12m = fv * (1 + g1) if fv else None
    price = fund.get("price")
    upside = ((fv / price - 1) * 100) if (fv and price) else None

    # Verlaesslichkeit auf Basis des bereinigten Core (Ausreisser sind schon raus,
    # daher ist die Streuung aussagekraeftig). Ein plausibler Analysten-Anker hebt
    # die Verlaesslichkeit auf mind. "mittel" - so erreichen deutlich mehr Titel
    # eine belastbare Angabe statt "niedrig/kein Wert".
    n_core = len([k for k in core if k != "fallback"])
    has_anchor = "analyst" in core
    sp = spread if spread is not None else 999
    if used_fallback or n_core == 0:
        confidence, reliable = "niedrig", False
    elif n_core >= 3 and sp <= 35:
        confidence, reliable = "hoch", True
    elif n_core >= 2 and sp <= 60:
        confidence, reliable = "mittel", True
    elif n_core == 1 and has_anchor:               # nur Analysten-Anker -> brauchbar
        confidence, reliable = "mittel", True
    elif n_core >= 2 and sp <= 90:                 # noch vertretbare Streuung
        confidence, reliable = "mittel", True
    else:                                          # echte, grosse Uneinigkeit -> ehrlich
        confidence, reliable = "niedrig", False
    if capped and confidence == "hoch":
        confidence = "mittel"
    n_methods = len(avail)

    # Schmidlin Net-Net: harter Bodenwert. Wenn der Kurs UNTER dem Netto-
    # Liquidationswert liegt, ist der Titel selbst im Zerschlagungsfall billig.
    # Wir heben den fairen Wert nie kuenstlich an, markieren aber diese seltene,
    # sehr starke Unterbewertung.
    _netnet = net_net_wert(fund)
    _unter_netnet = bool(_netnet and price and price < _netnet)

    # Terminalwert-Anteil und impliziertes Terminal-Multiple des DCF.
    try:
        _dcf_diagnose = dcf_diagnose(fund, preset)
    except Exception:
        _dcf_diagnose = None

    try:
        _datenqualitaet = datenqualitaet(fund, preset, ergebnisse=raw)
        # Verworfene Methoden sind kein Datenproblem, aber dieselbe Klasse von
        # stiller Verschiebung - deshalb in dieselbe Warnzeile.
        if _datenqualitaet and _verworfen:
            # Wie viel Gewicht ist insgesamt weg - verworfen UND ausgefallen?
            _weg = sum((d.get("gewicht") or 0) for d in _verworfen.values())
            _weg += sum(weights.get(m, 0)
                        for m in _datenqualitaet.get("ausgefallene_methoden", []))
            _ges = sum(weights.values()) or 1.0
            _anteil_weg = _weg / _ges

            # Ab der Haelfte ist es keine Bewertung mehr, sondern eine
            # Hochrechnung aus dem Rest. Bei CrowdStrike fielen fwd_pe (30 %)
            # und fwd_composite (25 %) weg, weil das GAAP-Ergebnis bei einem
            # Umsatz von 4 Mrd nahe null liegt - der ausgewiesene Fair Value
            # stammte dann aus DCF und Analystenziel allein.
            #
            # Eine Zahl auf 45 % der vorgesehenen Verfahren sieht genauso aus
            # wie eine auf 100 % - deshalb wird sie hier ausdruecklich als
            # nicht belastbar gekennzeichnet, statt sie stillschweigend
            # weiterzureichen.
            if not _kurs_taugt_als_anker:
                _datenqualitaet["warnungen"].append(
                    "Alle Verfahren liegen weit unter dem Kurs - der Kurs wurde "
                    "deshalb nicht als Plausibilitaetsanker benutzt. Das ist "
                    "kein Datenfehler, sondern die Aussage des Modells.")
                _datenqualitaet["kurs_kein_anker"] = True

            if _anteil_weg >= 0.50:
                _datenqualitaet["nicht_belastbar"] = True
                _datenqualitaet["gewicht_weg"] = round(_anteil_weg, 3)
                _datenqualitaet["stufe"] = "nicht belastbar"
                _datenqualitaet["ton"] = "rot"
                _datenqualitaet["warnungen"].insert(0, (
                    f"{_anteil_weg:.0%} der vorgesehenen Verfahren tragen nicht. "
                    f"Der ausgewiesene Fair Value stammt aus dem Rest und ist "
                    f"keine belastbare Groesse - dieses Modell traegt den Titel "
                    f"nicht."))

            _schwer = {k: d for k, d in _verworfen.items() if (d.get("gewicht") or 0) >= 0.20}
            if _schwer:
                _txt = ", ".join(f"{k} ({d['wert']}, {d['vs_kurs']:+.0f} % zum Kurs, "
                                 f"{d['gewicht']:.0%} Gewicht)" for k, d in _schwer.items())
                _datenqualitaet["warnungen"].append(
                    f"Als unplausibel verworfen: {_txt}. Das Gewicht verteilt sich auf "
                    f"die uebrigen Methoden - der Fair Value beruht damit auf weniger "
                    f"Verfahren als vorgesehen.")
                if _datenqualitaet["ton"] == "gruen":
                    _datenqualitaet["ton"] = "gelb"
                    _datenqualitaet["stufe"] = "eingeschraenkt"
    except Exception:
        _datenqualitaet = None

    return {
        "ticker": fund.get("ticker"),
        "price": price,
        "methods": {k: round(v, 2) for k, v in avail.items()},
        "n_methods": n_methods,
        "fair_value": round(fv, 2) if fv else None,
        "fair_value_capped": capped,
        "net_net": round(_netnet, 2) if _netnet is not None else None,
        "unter_net_net": _unter_netnet,
        "mos_verwendet": fund.get("_mos_verwendet"),
        "ungehebelte_roe": (round(ungehebelte_ekr(fund), 3)
                            if ungehebelte_ekr(fund) is not None else None),
        # Notbehelf-Kennzeichen: TRUE heisst, dass KEINE Bewertungsmethode
        # ein plausibles Ergebnis lieferte. Der angezeigte Wert ist dann nur
        # der gegen den Kurs geklammerte Median der Rohwerte - also faktisch
        # der halbe oder doppelte Kurs. Das MUSS sichtbar sein, sonst haelt
        # man eine Notbremse fuer eine Bewertung.
        "used_fallback": used_fallback,
        "model_fair_value": round(model_fv, 2) if model_fv else None,
        "analyst_target": round(anl, 2) if anl else None,
        "analyst_count": fund.get("analyst_count"),
        "model_vs_analyst_pct": divergence,
        "method_profile": " \u00b7 ".join(profile_notes),
        "confidence": confidence,
        "reliable": reliable,
        "range_low": round(lo, 2) if lo else None,
        "range_high": round(hi, 2) if hi else None,
        "spread_pct": spread,
        "target_12m": round(target_12m, 2) if target_12m else None,
        "entry_price": round(entry, 2) if entry else None,
        "margin_of_safety": mos,
        "upside_pct": round(upside, 1) if upside is not None else None,
        "reverse_dcf_implied_growth": reverse_dcf_implied_growth(fund),
        "wacc": round(wacc(fund.get("beta"), fund.get("market_cap"), fund.get("total_debt")), 4),
        "szenarien": szenario_werte(fund, preset),
        "annahmen": dcf_annahmen(fund, preset),
        # --- Diagnostik und Herkunft (siehe Abschnitt am Dateiende) -----------
        "herkunft": _herkunft,
        "dcf_diagnose": _dcf_diagnose,
        "datenqualitaet": _datenqualitaet,
        "verworfene_methoden": _verworfen or None,
        "basis": basis_signatur(fund, preset, avail.keys() if avail else []),
    }


def analyst_spread(fund) -> Optional[dict]:
    """Wie uneinig sind die Analysten? Eigenes Feld, kein Eingriff in die Rechnung.

    Der Mittelwert allein taeuscht Praezision vor. Bei GM lagen im Juli 2026
    Kursziele von 60 USD (Wells Fargo, Underweight) bis 131 USD (Citigroup,
    Buy) vor - Faktor 2,2 bei derselben Firma und identischer Faktenlage.
    Der Mittelwert von ~95 USD ist dann kein Konsens, sondern ein Kompromiss
    zwischen zwei unvereinbaren Lagern.

    Rueckgabe: mean/low/high/n, Spannweite in Prozent des Mittelwerts,
    eine Einstufung und ein Vertrauensfaktor 0.4-1.0, den der Aufrufer
    verwenden KANN - die Kernrechnung bleibt unangetastet."""
    mean = fund.get("target_mean")
    low, high = fund.get("target_low"), fund.get("target_high")
    n = fund.get("analyst_count")
    if not mean or mean <= 0:
        return None
    out = {"mean": round(float(mean), 2),
           "low": round(float(low), 2) if low else None,
           "high": round(float(high), 2) if high else None,
           "n": int(n) if n else None}
    if not low or not high or high <= low:
        out.update({"spanne_pct": None, "einstufung": "keine Spannweite verfügbar",
                    "vertrauen": 1.0})
        return out
    spanne = (high - low) / mean * 100
    out["spanne_pct"] = round(spanne, 1)
    out["faktor"] = round(high / low, 2) if low > 0 else None
    if spanne < 30:
        out["einstufung"] = "Analysten weitgehend einig"
        out["vertrauen"] = 1.0
    elif spanne < 50:
        out["einstufung"] = "normale Streuung"
        out["vertrauen"] = 0.85
    elif spanne < 80:
        out["einstufung"] = "deutlich uneinig – Mittelwert wenig aussagekräftig"
        out["vertrauen"] = 0.6
    else:
        out["einstufung"] = ("stark gespalten – der Mittelwert ist ein Kompromiss "
                             "zwischen unvereinbaren Lagern")
        out["vertrauen"] = 0.4
    return out


def datenaktualitaet(fund, naechster_termin_tage=None) -> dict:
    """Wie frisch sind die Zahlen, auf denen die Bewertung beruht?

    Eigenes Feld, keine Korrektur. Ein Fair Value auf zwei Nachkommastellen
    suggeriert Genauigkeit - wenn das Unternehmen aber HEUTE meldet, rechnet
    er mit ueberholten Zahlen. Das gehoert sichtbar gemacht, nicht
    stillschweigend weggerechnet."""
    out = {"stufe": "normal", "hinweis": "", "termin_tage": naechster_termin_tage}
    t = naechster_termin_tage
    if t is None:
        out["hinweis"] = "kein Quartalstermin bekannt"
        return out
    if t <= 1:
        out["stufe"] = "kritisch"
        out["hinweis"] = ("meldet heute oder morgen – die Bewertung beruht auf "
                          "Zahlen, die gleich überholt sind")
    elif t <= 7:
        out["stufe"] = "achtung"
        out["hinweis"] = f"meldet in {t} Tagen – Zahlen ändern sich bald"
    elif t <= 21:
        out["stufe"] = "hinweis"
        out["hinweis"] = f"meldet in {t} Tagen"
    else:
        out["hinweis"] = f"nächster Termin in {t} Tagen"
    return out

# ---------------------------------------------------------------------------
# Datenqualitaet - warum ein Fair Value ploetzlich anders aussieht
# ---------------------------------------------------------------------------

#: Welche Felder eine Methode braucht - NUR fuer die Erklaerung, warum sie
#: ausgefallen ist. Ob sie ausgefallen ist, wird am tatsaechlichen Ergebnis
#: abgelesen, nicht an dieser Liste.
#:
#: Der Unterschied ist kein Detail: Die erste Fassung hat aus diesen Listen
#: GESCHLOSSEN, dass eine Methode entfaellt - und lag damit systematisch
#: falsch. justified_pe_number() braucht nur ein positives EPS; roe und
#: gross_margin gehen als Bonuspunkte ein, fehlen duerfen sie. multiple_ev_ebitda()
#: braucht shares_out und ebitda; das eigene ev_ebitda ist optional, ohne es
#: wird der Sektoranker genommen. Beide wurden deshalb bei fast jedem Titel
#: faelschlich als "entfaellt mangels Daten" gemeldet.
_FELDBEDARF = {
    "justified_pe": ["eps_trailing"],   # seit V1 ausdruecklich trailing
    "fwd_pe": ["eps_forward"],
    "fwd_composite": ["eps_forward"],
    "hist_pe": ["eps_forward", "hist_pe_median"],
    "ev_ebitda": ["ebitda", "shares_out"],
    "dcf": ["free_cashflow", "shares_out"],
    "pb": ["book_value_ps"],
    "epv": ["operating_margin", "revenue"],
    "analyst": ["target_mean"],
}

#: Felder, die nicht nur DA, sondern POSITIV sein muessen. Die Pruefung auf
#: `in (None, 0)` liess negative Werte durch - bei CrowdStrike meldete die
#: Diagnose deshalb "ev_ebitda ohne Ergebnis, obwohl die Daten vorliegen",
#: obwohl das EBITDA schlicht negativ war. Die Methode verlangt > 0.
_MUSS_POSITIV = {"ebitda", "eps_trailing", "eps_forward", "free_cashflow",
                 "book_value_ps", "shares_out", "hist_pe_median", "revenue"}


def _feld_fehlt(fund, k: str) -> bool:
    v = fund.get(k)
    if v is None:
        return True
    if k in _MUSS_POSITIV:
        try:
            return float(v) <= 0
        except (TypeError, ValueError):
            return True
    return v == 0

#: Ohne diese Felder kippt classify_playbook lautlos in ein anderes Playbook -
#: und damit in ein voellig anderes Gewichtungsschema. Das ist die
#: gefaehrlichste Datenluecke, weil sie sich nicht als Fehler zeigt, sondern
#: als plausibel aussehender, aber falscher Fair Value.
_PLAYBOOK_KRITISCH = ["revenue_growth", "earnings_growth"]


def datenqualitaet(fund, preset: str = "quality",
                   ergebnisse: Optional[Dict[str, float]] = None) -> dict:
    """Welche Methoden sind ausgefallen, und was bedeutet das?

    `ergebnisse` sind die TATSAECHLICH berechneten Methodenwerte
    (valuation.fair_value uebergibt sie). Nur was dort fehlt oder None ist,
    gilt als ausgefallen. Ohne diese Angabe faellt die Funktion auf die
    Feldpruefung zurueck - die ist ungenauer und neigt zu Fehlalarmen.

    Hintergrund: Faellt eine Datenquelle aus (abgelaufener Schluessel,
    Rate-Limit, Anbieterausfall), verschwinden einzelne Felder still. Die
    Bewertung rechnet dann mit weniger Methoden weiter und liefert eine Zahl,
    die aussieht wie immer - aber auf einer anderen Grundlage steht.
    """
    gewichte = _WEIGHTS.get(preset, _WEIGHTS["quality"])

    if ergebnisse is not None:
        ausgefallen = [m for m in gewichte
                       if gewichte.get(m, 0) > 0 and not ergebnisse.get(m)]
    else:
        ausgefallen = [m for m in gewichte
                       if gewichte.get(m, 0) > 0
                       and any(_feld_fehlt(fund, k)
                               for k in _FELDBEDARF.get(m, []))]

    # Warum? Nur fuer die tatsaechlich ausgefallenen Methoden nachschlagen.
    fehlt_je_methode = {}
    for m in ausgefallen:
        f = [k for k in _FELDBEDARF.get(m, []) if _feld_fehlt(fund, k)]
        if f:
            _detail = []
            for k in f:
                v = fund.get(k)
                _detail.append(k if v is None else f"{k} = {v:,.2f}".replace(",", " "))
            fehlt_je_methode[m] = _detail

    verlust = sum(gewichte.get(m, 0) for m in ausgefallen)
    gesamt = sum(gewichte.values()) or 1.0

    # classify_playbook nimmt revenue_growth und faellt nur ersatzweise auf
    # earnings_growth zurueck. Fehlt NUR earnings_growth, ist die Einstufung
    # nicht gefaehrdet - die Warnung war zu laut. Bei einem Verlustjahr ist
    # earnings_growth ohnehin nicht sinnvoll berechenbar.
    pb_luecken = ([k for k in _PLAYBOOK_KRITISCH if fund.get(k) is None]
                  if fund.get("revenue_growth") is None else [])

    warnungen = []
    if pb_luecken:
        warnungen.append(
            "Playbook-Einstufung unsicher: " + ", ".join(pb_luecken) + " fehlt. "
            "Ohne Wachstumsdaten wird ein Wachstumstitel als Qualitaetstitel "
            "eingestuft - mit anderen Gewichten und deutlich niedrigerem Fair Value.")
    # "dcf faellt aus" ohne Nennung eines fehlenden Feldes ist ebenfalls eine
    # Aussage - dann liegt es nicht an den Daten, sondern am Modell (negatives
    # Eigenkapital, EBITDA <= 0, unloesbarer Terminalwert). Beides muss man
    # unterscheiden koennen.
    _ohne_grund = [m for m in ausgefallen if m not in fehlt_je_methode]
    if _ohne_grund and verlust / gesamt <= 0.35:
        warnungen.append(
            f"Ohne Ergebnis, obwohl die Daten vorliegen: {', '.join(_ohne_grund)}. "
            f"Ursache liegt im Modell, nicht in der Datenlage.")
    if verlust / gesamt > 0.35:
        _mit_grund = ", ".join(
            (f"{m} (ohne {', '.join(fehlt_je_methode[m])})" if m in fehlt_je_methode
             else m) for m in ausgefallen)
        warnungen.append(
            f"{verlust / gesamt:.0%} des Methodengewichts entfallen: {_mit_grund}. "
            f"Die verbleibenden {(gesamt-verlust)/gesamt:.0%} werden neu gewichtet. "
            f"Die Bewertung hat dadurch eine schmalere Datenbasis.")
    if fund.get("target_mean") is None and gewichte.get("analyst", 0) > 0:
        warnungen.append(
            "Kein Analystenkursziel verfuegbar. Das Analystenmodell entfaellt; "
            "verfuegbare Modelle werden neu gewichtet. Ein gespeicherter Analystenwert "
            "wird nur beruecksichtigt, wenn er mit den Eingabedaten vorliegt.")
    _aus_sp = fund.get("_schaetzfelder_aus_speicher")
    if _aus_sp:
        warnungen.append(
            "Aus dem Zwischenspeicher statt frisch geholt: "
            + ", ".join(_aus_sp)
            + ". Das haelt den Fair Value stabil, wenn die Quelle gerade nicht "
              "antwortet - die Werte sind aber hoechstens 45 Tage alt.")

    if not warnungen:
        stufe, ton = "vollstaendig", "gruen"
    elif pb_luecken or verlust / gesamt > 0.5:
        stufe, ton = "kritisch", "rot"
    else:
        stufe, ton = "eingeschraenkt", "gelb"

    return {
        "stufe": stufe,
        "ton": ton,
        "gewichtsverlust": round(verlust / gesamt, 3),
        "ausgefallene_methoden": ausgefallen,
        "fehlende_felder": fehlt_je_methode,
        "playbook_luecken": pb_luecken,
        "warnungen": warnungen,
    }


# ==========================================================================
# BEWERTUNGS-DIAGNOSTIK, HERKUNFT UND SZENARIEN
# ==========================================================================

# ---------------------------------------------------------------------------
# Schwellen
# ---------------------------------------------------------------------------

TERMINAL_ANTEIL_WARN = 0.75    # ab hier ist der DCF faktisch eine Terminalwert-Wette
MULTIPLE_ANTEIL_WARN = 0.60    # ab hier haengt der Fair Value an Bewertungsniveaus
MARKT_ANTEIL_WARN = 0.25       # ab hier traegt der Analystenkonsens zu viel
CONVERSION_GRENZEN = (0.50, 1.30)


# ---------------------------------------------------------------------------
# Herkunft des Fair Value  (Selbstkritik)
# ---------------------------------------------------------------------------

#: Woraus jede Methode ihren Wert zieht. Der Analystenkonsens ist bewusst eine
#: eigene Kategorie: er ist weder Cashflow noch Multiple, sondern Marktmeinung -
#: und damit genau das, wogegen der Fair Value spaeter gemessen werden soll.
METHODEN_HERKUNFT: Dict[str, str] = {
    "justified_pe": "multiple",
    "fwd_pe": "multiple",
    "fwd_composite": "multiple",
    "hist_pe": "multiple",
    "ev_ebitda": "multiple",
    "pb": "substanz",
    "epv": "ertragskraft",
    "dcf": "cashflow",
    "analyst": "markt",
    "fallback": "notbehelf",
}

HERKUNFT_LABEL = {
    "multiple": "Multiple-Annahmen",
    "cashflow": "Cashflow-Prognose",
    "ertragskraft": "Ertragskraft (EPV)",
    "substanz": "Substanz (Buchwert)",
    "markt": "Analystenkonsens",
    "notbehelf": "Notbehelf",
    "unbekannt": "nicht zugeordnet",
}

HERKUNFT_FARBE = {
    "multiple": "#FFB000", "cashflow": "#3FB950", "ertragskraft": "#4FA8DE",
    "substanz": "#8A7CC8", "markt": "#6B7686", "notbehelf": "#F85149",
    "unbekannt": "#6B7686",
}


def herkunft(core: Dict[str, float], weights: Dict[str, float]) -> Optional[dict]:
    """Zerlegt den geblendeten Fair Value nach Herkunft der Annahme.

    `core` und `weights` sind exakt die Objekte, die valuation.fair_value()
    intern verwendet - dadurch stimmt die Zerlegung mit dem angezeigten Wert
    ueberein statt ihn nachzubauen.

    Gegenstueck zum Terminalwert-Anteil: Wenn im Quality-Playbook 30 % Gewicht
    auf justified_pe und 25 % auf ev_ebitda liegen, stammen ueber die Haelfte
    des Fair Value aus angenommenen Bewertungsniveaus - dieselbe Schieflage,
    die AlphaSpread vorgeworfen wird, wenn dort der Multiples-Wert als Headline
    steht. Diese Funktion macht sie sichtbar, statt sie zu bestreiten.
    """
    if not core:
        return None
    wsum = sum(weights.get(k, 0.15) for k in core)
    if not wsum:
        return None

    beitrag = {k: core[k] * weights.get(k, 0.15) / wsum for k in core}
    fv = sum(beitrag.values())
    if not fv:
        return None

    nach_herkunft: Dict[str, float] = {}
    for k, b in beitrag.items():
        h = METHODEN_HERKUNFT.get(k, "unbekannt")
        nach_herkunft[h] = nach_herkunft.get(h, 0.0) + b / fv

    mult = nach_herkunft.get("multiple", 0.0)
    markt = nach_herkunft.get("markt", 0.0)

    # Effektives gegen nominelles Gewicht: Weil fair_value() Methoden
    # herausfiltert und die Gewichte danach renormiert, kann eine Methode
    # deutlich schwerer wiegen als im Playbook vorgesehen. Der Analystenanker
    # mit nominell 15 % landet so schnell bei 30 % - eine Verschiebung, die
    # bisher nirgends sichtbar war.
    w_gesamt = sum(weights.values()) or 1.0
    verschiebung = {}
    for k in core:
        nominal = weights.get(k, 0.15) / w_gesamt
        effektiv = beitrag[k] / fv
        if nominal > 0 and (effektiv / nominal > 1.5 or effektiv / nominal < 0.6):
            verschiebung[k] = {"nominal": round(nominal, 3),
                               "effektiv": round(effektiv, 3),
                               "faktor": round(effektiv / nominal, 2)}

    hinweise: List[str] = []
    for k, d in verschiebung.items():
        if d["faktor"] > 1.5:
            hinweise.append(
                f"'{k}' wiegt effektiv {d['effektiv']:.0%} statt der vorgesehenen "
                f"{d['nominal']:.0%} - andere Methoden wurden herausgefiltert.")
    if mult > MULTIPLE_ANTEIL_WARN:
        hinweise.append(
            f"{mult:.0%} des Fair Value stammen aus angenommenen Bewertungsniveaus. "
            f"Der Wert reagiert damit staerker auf Multiple-Annahmen als auf die "
            f"operative Entwicklung.")
    if markt > MARKT_ANTEIL_WARN:
        hinweise.append(
            f"{markt:.0%} des Fair Value stammen aus dem Analystenkonsens. "
            f"Ein Fair Value, der den Markt zu stark einpreist, kann nicht mehr "
            f"unabhaengig gegen den Markt gemessen werden.")
    if "notbehelf" in nach_herkunft:
        hinweise.append("Keine Methode lieferte ein plausibles Ergebnis - der Wert "
                        "ist ein gegen den Kurs geklammerter Notbehelf.")

    return {
        "fair_value": round(fv, 2),
        "nach_herkunft": {k: round(v, 4) for k, v in
                          sorted(nach_herkunft.items(), key=lambda kv: -kv[1])},
        "nach_methode": {k: round(v / fv, 4) for k, v in
                         sorted(beitrag.items(), key=lambda kv: -kv[1])},
        "multiple_anteil": round(mult, 4),
        "markt_anteil": round(markt, 4),
        "gewichtsverschiebung": verschiebung,
        "hinweise": hinweise,
    }


# ---------------------------------------------------------------------------
# Punkt 2 - DCF-Diagnostik
# ---------------------------------------------------------------------------

def _dcf_teile(fcf, shares, net_debt, g1, g_term, r, years) -> dict:
    """Exakte Nachbildung von valuation.dcf_two_stage, aber mit offengelegten
    Bestandteilen. Jede Aenderung dort muss hier nachgezogen werden."""
    pv, cf = 0.0, float(fcf)
    verlauf = []
    for t in range(1, years + 1):
        g_t = g1 + (g_term - g1) * (t - 1) / (years - 1)
        cf *= (1 + g_t)
        bw = cf / ((1 + r) ** t)
        pv += bw
        verlauf.append({"jahr": t, "wachstum": g_t, "fcf": cf, "barwert": bw})
    terminal_roh = cf * (1 + g_term) / (r - g_term)
    terminal_bw = terminal_roh / ((1 + r) ** years)
    equity = pv + terminal_bw - (net_debt or 0.0)
    gesamt = pv + terminal_bw
    return {
        "barwert_explizit": pv,
        "terminal_roh": terminal_roh,
        "terminal_barwert": terminal_bw,
        "terminal_anteil": (terminal_bw / gesamt) if gesamt else None,
        "fcf_endjahr": cf,
        "equity": equity,
        "wert_je_aktie": equity / shares if (shares and equity > 0) else None,
        "verlauf": verlauf,
    }


def dcf_diagnose(fund, preset: str = "quality") -> Optional[dict]:
    """Terminalwert-Anteil und impliziertes Terminal-Multiple.

    Beim Gordon-Terminal ist das Terminal-Multiple nicht sichtbar, sondern
    steckt in (1+g)/(r-g). Genau deshalb wird es hier ausgerechnet: Ein DCF,
    dessen Wert zu 80 % im Terminalwert steckt, ist keine Cashflow-Bewertung,
    sondern eine Wette darauf, dass der Markt in zehn Jahren dieses Multiple
    bezahlt. Das gehoert vor die Klammer, nicht in eine Fussnote.
    """

    if preset == "cyclical":
        return None
    _basis = fcf_basis(fund)
    fcf, shares = _basis["basis"], fund.get("shares_out")
    if not fcf or not shares or fcf <= 0:
        return None

    years = max(int(V.get("projection_years", 10)), 2)
    g_term = V["terminal_growth"]
    g1 = fund.get("revenue_growth")
    if g1 is None:
        g1 = fund.get("earnings_growth") or 0.06
    cap = 0.25 if preset == "inflection" else 0.16
    g1 = max(min(g1, cap), -0.03)
    r = wacc(fund.get("beta"), fund.get("market_cap"), fund.get("total_debt"))
    if r - g_term < 0.045:
        r = g_term + 0.045

    net_debt = fund.get("net_debt") or 0.0
    teile = _dcf_teile(fcf, shares, net_debt, g1, g_term, r, years)

    # Terminal-Multiple: wie viele Endjahres-Cashflows der Terminalwert wert ist.
    mult_genutzt = (1 + g_term) / (r - g_term)

    # Was verlangt der Kurs? Barwert der expliziten Jahre ist fix; loese nach M.
    price = fund.get("price")
    mult_impliziert = None
    if price and price > 0:
        ziel_equity = price * shares + net_debt
        rest = ziel_equity - teile["barwert_explizit"]
        if rest > 0 and teile["fcf_endjahr"]:
            mult_impliziert = rest * ((1 + r) ** years) / teile["fcf_endjahr"]

    # Heutiges FCF-Multiple als Bodenhaftung.
    mcap = fund.get("market_cap") or (price * shares if price else None)
    mult_heute = (mcap / fcf) if (mcap and fcf) else None

    hinweise: List[str] = []
    ta = teile["terminal_anteil"]
    if ta and ta > TERMINAL_ANTEIL_WARN:
        hinweise.append(
            f"{ta:.0%} des DCF-Werts stecken im Terminalwert. Das Modell ist im Kern "
            f"eine Wette auf das Endmultiple, nicht auf die naechsten {years} Jahre.")
    if mult_impliziert and mult_genutzt and mult_impliziert > mult_genutzt * 1.25:
        hinweise.append(
            f"Der Kurs verlangt ein Terminal-Multiple von {mult_impliziert:.1f}x auf den "
            f"Endjahres-Cashflow; das Modell unterstellt {mult_genutzt:.1f}x.")
    if mult_impliziert and mult_impliziert < 0:
        hinweise.append("Der Kurs liegt unter dem Barwert der expliziten Prognosejahre - "
                        "der Markt preist den Terminalwert faktisch mit null.")
    if r - g_term <= 0.046:
        hinweise.append("Diskontsatz wurde auf den Mindestabstand zum Terminalwachstum "
                        "angehoben - der DCF ist hier besonders empfindlich.")

    if _basis["quelle"] == "normalisiert" and _basis.get("abweichung") is not None:
        hinweise.append(
            f"DCF rechnet mit normalisiertem Cashflow: Nettogewinn x "
            f"{_basis['conversion']:.0%} Conversion = {_basis['normalisiert']/1e9:.1f} Mrd "
            f"statt gemeldeter {_basis['gemeldet']/1e9:.1f} Mrd "
            f"({_basis['abweichung']:+.0%}).")

    return {
        "fcf_basis": _basis,
        "wert_je_aktie": (round(teile["wert_je_aktie"], 2)
                          if teile["wert_je_aktie"] else None),
        "terminal_anteil": round(ta, 4) if ta else None,
        "terminal_lastig": bool(ta and ta > TERMINAL_ANTEIL_WARN),
        "barwert_explizit": teile["barwert_explizit"],
        "terminal_barwert": teile["terminal_barwert"],
        "fcf_endjahr": teile["fcf_endjahr"],
        "multiple_genutzt": round(mult_genutzt, 1),
        "multiple_impliziert": (round(mult_impliziert, 1)
                                if mult_impliziert is not None else None),
        "multiple_heute": round(mult_heute, 1) if mult_heute else None,
        "wacc": round(r, 4),
        "wachstum_start": round(g1, 4),
        "terminal_growth": g_term,
        "jahre": years,
        "hinweise": hinweise,
    }


# ---------------------------------------------------------------------------
# Punkt 6 - Cash-Conversion
# ---------------------------------------------------------------------------

def conversion_aus_historie(fcf_reihe: Sequence[float],
                            ni_reihe: Sequence[float]) -> Optional[dict]:
    """Median und Streuung von FCF/Nettogewinn.

    Der Median ist der Treiber, die Streuung ist das Warnsignal: eine stark
    schwankende Conversion ist die quantitative Fassung von Dorseys
    Cashflow-vs-Gewinn-Divergenz (Lucent-Muster).
    """
    q = []
    for fcf, ni in zip(fcf_reihe or [], ni_reihe or []):
        try:
            fcf, ni = float(fcf), float(ni)
        except (TypeError, ValueError):
            continue
        if not (math.isfinite(fcf) and math.isfinite(ni)) or ni <= 0:
            continue
        q.append(fcf / ni)
    if not q:
        return None
    q_sort = sorted(q)
    n = len(q_sort)
    med = q_sort[n // 2] if n % 2 else (q_sort[n // 2 - 1] + q_sort[n // 2]) / 2
    mittel = sum(q) / n
    sd = math.sqrt(sum((x - mittel) ** 2 for x in q) / n) if n > 1 else 0.0

    warnung = None
    if med < 0.6:
        warnung = ("Nur ein kleiner Teil des ausgewiesenen Gewinns kommt als freier "
                   "Cashflow an - Gewinnqualitaet pruefen.")
    elif sd > 0.35:
        warnung = ("Die Cash-Conversion schwankt stark - der Fair Value reagiert "
                   "empfindlich darauf, welches Jahr als Basis dient.")

    return {
        "median": round(max(CONVERSION_GRENZEN[0], min(CONVERSION_GRENZEN[1], med)), 3),
        "median_roh": round(med, 3),
        "streuung": round(sd, 3),
        "min": round(min(q), 3),
        "max": round(max(q), 3),
        "n": n,
        "warnung": warnung,
    }


# ---------------------------------------------------------------------------
# Punkt 3 - Bear/Base/Bull je Methode
# ---------------------------------------------------------------------------

SZENARIEN = ("bear", "base", "bull")
SZENARIO_LABEL = {"bear": "Bear Case", "base": "Base Case", "bull": "Bull Case"}

#: Sekundaere Treiber schwingen nur anteilig aus. Ohne diese Daempfung wuerde
#: das Bear-Szenario dasselbe Risiko dreifach zaehlen: schwaechere Operative,
#: niedrigeres Bewertungsniveau UND hoehere Kapitalkosten sind grossenteils
#: dieselbe Aussage.
SEKUNDAER_DAEMPFUNG = 0.5


def _playbook_gewicht(preset: str, methode: str) -> float:
    """Gewicht einer Methode im Playbook; unbekannte Keys neutral bei 0.15 -
    genau wie in valuation.fair_value()."""
    w = _WEIGHTS.get(preset, _WEIGHTS["quality"])
    return w.get(methode, 0.15)


def _szenario_fund(fund: dict, szenario: str, g_delta: float,
                   op_delta: float, bewertungs_delta: float,
                   beta_delta: float) -> dict:
    """Kopie des fund-Dicts mit verschobenen PRIMITIVEN Treibern.

    Bewusst nicht die Methodenergebnisse verschieben, sondern die Eingangs-
    groessen - dann rechnen ALLE Methoden aus valuation.py das Szenario
    selbst durch, ohne dass ihre Logik dupliziert wird.
    """
    if szenario == "base":
        return dict(fund)

    vz = -1.0 if szenario == "bear" else 1.0
    d = SEKUNDAER_DAEMPFUNG
    f = dict(fund)

    # --- primaer: Wachstum ---------------------------------------------------
    for k in ("revenue_growth", "earnings_growth"):
        if f.get(k) is not None:
            f[k] = f[k] + vz * g_delta

    # --- primaer: operative Ausfuehrung (Marge/Cash) -------------------------
    op = 1.0 + vz * op_delta
    for k in ("free_cashflow", "ebitda", "eps_forward", "eps_trailing", "net_income"):
        if f.get(k) is not None:
            f[k] = f[k] * op
    if f.get("operating_margin") is not None:
        f["operating_margin"] = f["operating_margin"] * op

    # --- sekundaer: Bewertungsniveau -----------------------------------------
    bw = 1.0 + vz * bewertungs_delta * d
    for k in ("hist_pe_median", "ev_ebitda"):
        if f.get(k) is not None:
            f[k] = f[k] * bw

    # --- sekundaer: Kapitalkosten ueber Beta ---------------------------------
    if f.get("beta") is not None:
        f["beta"] = max(0.3, f["beta"] - vz * beta_delta * d)

    # Analystenziel bleibt unveraendert: es ist eine externe Konsensaussage,
    # kein Modelltreiber. Dass es die Spanne daempft, ist gewollt.
    return f


def szenario_matrix(fund: dict, peer_funds=None, preset: str = "quality") -> Optional[dict]:
    """Bear/Base/Bull je Bewertungsmethode - nicht nur fuer den DCF.

    Ruft valuation.fair_value() dreimal mit verschobenen Eingangsgroessen auf.
    Dadurch bleibt die Rechenlogik an genau einer Stelle und die Szenarien
    koennen nicht von der Hauptbewertung abdriften.

    Rueckgabe:
        {"methoden": {"dcf": {"bear":..,"base":..,"bull":..}, ...},
         "blend":    {"bear":..,"base":..,"bull":..},
         "upside":   {...}, "treiber": {...}, "preis": ..}
    """

    price = fund.get("price")
    if not price:
        return None

    # Unsicherheit skaliert mit dem erwarteten Wachstum (Damodaran): schneller
    # wachsende Firmen sind schwerer zu prognostizieren.
    g = fund.get("revenue_growth")
    if g is None:
        g = fund.get("earnings_growth") or 0.06
    g_delta = max(0.03, abs(g) * 0.5)
    op_delta = 0.12 if preset != "inflection" else 0.18
    bew_delta = 0.20
    beta_delta = 0.25

    methoden: Dict[str, Dict[str, Optional[float]]] = {}
    blend: Dict[str, Optional[float]] = {}
    upside: Dict[str, Optional[float]] = {}
    ergebnisse = {}

    for sz in SZENARIEN:
        f_sz = _szenario_fund(fund, sz, g_delta, op_delta, bew_delta, beta_delta)
        try:
            v = fair_value(f_sz, peer_funds, preset)
        except Exception:
            v = None
        ergebnisse[sz] = v
        if not v:
            blend[sz] = upside[sz] = None
            continue
        blend[sz] = v.get("fair_value")
        upside[sz] = v.get("upside_pct")
        for k, val in (v.get("methods") or {}).items():
            methoden.setdefault(k, {})[sz] = val

    # Methoden ohne Base-Wert wieder entfernen: sie tragen keine Aussage.
    methoden = {k: {sz: d.get(sz) for sz in SZENARIEN}
                for k, d in methoden.items() if d.get("base") is not None}

    if blend.get("base") is None:
        return None

    # --- Konsistenzpruefung ------------------------------------------------
    # Faellt eine Methode im Bear-Fall weg (z. B. DCF bei negativem Eigenkapital),
    # renormiert fair_value() die Gewichte auf die verbliebenen - und der
    # Bear-Wert kann dadurch HOEHER ausfallen als der Base-Wert. Das ist kein
    # Rechenfehler, sondern ein Artefakt des Methodenausfalls. Es zu verstecken
    # waere schlimmer als es zu zeigen: also beides ausweisen.
    gemeinsam = [k for k, d in methoden.items()
                 if all(d.get(sz) is not None for sz in SZENARIEN)]
    fehlend = {sz: [k for k, d in methoden.items() if d.get(sz) is None]
               for sz in SZENARIEN}

    blend_konsistent: Dict[str, Optional[float]] = {}
    if gemeinsam:
        w_ges = sum(_playbook_gewicht(preset, k) for k in gemeinsam)
        for sz in SZENARIEN:
            if w_ges:
                blend_konsistent[sz] = round(sum(
                    methoden[k][sz] * _playbook_gewicht(preset, k)
                    for k in gemeinsam) / w_ges, 2)
            else:
                blend_konsistent[sz] = None

    warnungen: List[str] = []
    for sz in ("bear", "bull"):
        if fehlend[sz]:
            warnungen.append(
                f"Im {SZENARIO_LABEL[sz]} entfaellt {', '.join(fehlend[sz])}; die "
                f"Gewichte verteilen sich auf die uebrigen Methoden. Der "
                f"{SZENARIO_LABEL[sz]}-Wert ist dadurch nicht direkt mit dem Base "
                f"Case vergleichbar - dafuer die Zeile 'nur gemeinsame Methoden'.")
    if (blend.get("bear") or 0) > (blend.get("base") or 0):
        warnungen.append(
            "Der Bear-Wert liegt ueber dem Base-Wert. Ursache ist der "
            "Methodenausfall, nicht ein besseres Szenario.")

    werte = [w for w in blend.values() if w]
    kurs_pos = None
    kurs_ausserhalb = None
    if len(werte) > 1 and max(werte) > min(werte):
        roh = (price - min(werte)) / (max(werte) - min(werte)) * 100
        kurs_pos = round(max(0.0, min(100.0, roh)), 0)
        if roh > 100:
            kurs_ausserhalb = "ueber allen Szenarien"
        elif roh < 0:
            kurs_ausserhalb = "unter allen Szenarien"

    return {
        "methoden": methoden,
        "blend": blend,
        "blend_konsistent": blend_konsistent or None,
        "gemeinsame_methoden": gemeinsam,
        "fehlende_methoden": {k: v for k, v in fehlend.items() if v},
        "warnungen": warnungen,
        "upside": upside,
        "preis": price,
        "spanne_pct": (round((max(werte) - min(werte)) / blend["base"] * 100, 0)
                       if len(werte) > 1 and blend["base"] else None),
        "kurs_position": kurs_pos,
        "kurs_ausserhalb": kurs_ausserhalb,
        "treiber": {
            "wachstum_pp": round(g_delta * 100, 1),
            "operativ_pct": round(op_delta * 100, 0),
            "bewertung_pct": round(bew_delta * SEKUNDAER_DAEMPFUNG * 100, 0),
            "beta_pp": round(beta_delta * SEKUNDAER_DAEMPFUNG, 2),
            "daempfung": SEKUNDAER_DAEMPFUNG,
        },
        "ergebnisse": ergebnisse,
    }

# ---------------------------------------------------------------------------
# Rechengrundlage festhalten
# ---------------------------------------------------------------------------

#: Felder, deren An- oder Abwesenheit den Fair Value verschiebt. Nicht ihre
#: WERTE - nur ob sie da waren. Ein Kurs aendert sich staendig, aber ob
#: cash_conversion vorlag oder nicht, entscheidet ueber die halbe Rechnung.
_BASIS_FELDER = ("eps_forward", "target_mean", "cash_conversion",
                 "schaetzguete", "hist_pe_median", "revenue_growth",
                 "earnings_growth", "ebitda", "free_cashflow", "book_value_ps")


def basis_signatur(fund, preset: str, methoden=None) -> dict:
    """Woraus wurde dieser Fair Value gerechnet?

    Zweck: Wenn derselbe Titel nach einem Neustart einen anderen Wert zeigt,
    soll man SEHEN, was sich geaendert hat - nicht raten. Verglichen wird die
    Grundlage, nicht das Ergebnis.
    """
    return {
        "playbook": preset,
        "felder": sorted(k for k in _BASIS_FELDER if fund.get(k)),
        "methoden": sorted(methoden or []),
        "eps_gestutzt": bool(fund.get("eps_forward_roh")),
        "fcf_basis": (fcf_basis(fund) or {}).get("quelle"),
        "roic": bool(fund.get("_roic")),
    }


def basis_vergleich(jetzt: dict, vorher: Optional[dict]) -> Optional[dict]:
    """Was hat sich gegenueber dem letzten Lauf geaendert?"""
    if not vorher or not jetzt:
        return None
    weg = [k for k in vorher.get("felder", []) if k not in jetzt.get("felder", [])]
    neu_da = [k for k in jetzt.get("felder", []) if k not in vorher.get("felder", [])]
    m_weg = [m for m in vorher.get("methoden", []) if m not in jetzt.get("methoden", [])]
    m_neu = [m for m in jetzt.get("methoden", []) if m not in vorher.get("methoden", [])]
    pb = (vorher.get("playbook") != jetzt.get("playbook"))
    fb = (vorher.get("fcf_basis") != jetzt.get("fcf_basis"))

    if not (weg or neu_da or m_weg or m_neu or pb or fb):
        return None

    texte = []
    if pb:
        texte.append(f"Playbook {vorher['playbook']} -> {jetzt['playbook']}")
    if weg:
        texte.append("Daten fehlen jetzt: " + ", ".join(weg))
    if neu_da:
        texte.append("Daten neu vorhanden: " + ", ".join(neu_da))
    if m_weg:
        texte.append("Methoden entfallen: " + ", ".join(m_weg))
    if m_neu:
        texte.append("Methoden neu dabei: " + ", ".join(m_neu))
    if fb:
        texte.append(f"Cashflow-Basis {vorher.get('fcf_basis')} -> {jetzt.get('fcf_basis')}")
    return {"geaendert": True, "texte": texte,
            "verlaesslich": not (weg or m_weg or pb)}


# ==========================================================================
# REVERSE DCF MIT REGIME-BEWUSSTEM KORRIDOR
# ==========================================================================

# ---------------------------------------------------------------------------
# Regime-Gewichte
# ---------------------------------------------------------------------------

#: Gewicht der Anker je Playbook. Wird ueber die vorhandenen Anker renormiert.
#: Gewichte fuer die kurzen Anker. Sie kommen dazu, weil die Datenlage keine
#: langen zulaesst - nicht weil sie besser waeren. Kurze Fenster reagieren
#: staerker auf Einmaleffekte, deshalb wiegen sie ueberall weniger als die
#: laengeren, die tatsaechlich vorhanden sind.
_KURZ_GEWICHTE = {"cagr_1j": 0.10, "cagr_2j": 0.15, "cagr_4j": 0.25}

PLAYBOOK_GEWICHTE: Dict[str, Dict[str, float]] = {
    # Zykliker: die lange Historie ist die ehrlichste Referenz - sie enthaelt
    # mindestens einen vollen Zyklus.
    "cyclical":   {"cagr_10j": 0.40, "cagr_5j": 0.25, "cagr_3j": 0.15, "konsens": 0.20},
    # Qualitaet: gleichmaessiger, der Konsens ist brauchbar.
    "quality":    {"cagr_10j": 0.20, "cagr_5j": 0.30, "cagr_3j": 0.25, "konsens": 0.25},
    # Inflection: die Vergangenheit ist per Definition nicht die These.
    "inflection": {"cagr_10j": 0.10, "cagr_5j": 0.20, "cagr_3j": 0.30, "konsens": 0.40},
    # Finanzwerte: Kreditzyklen laufen lang, kurze Fenster taeuschen.
    "financial":  {"cagr_10j": 0.35, "cagr_5j": 0.30, "cagr_3j": 0.15, "konsens": 0.20},
}

ANKER_LABEL = {
    "cagr_1j": "letztes Jahr",
    "cagr_2j": "2J Historie",
    "cagr_4j": "4J Historie",
    "cagr_3j": "3J Historie",
    "cagr_5j": "5J Historie",
    "cagr_10j": "10J+ Historie",
    "konsens": "Analystenkonsens",
    "modell": "Aktuelles DCF-Modell",
    "impliziert": "Vom Kurs verlangt",
}

URTEIL_TEXT = {
    "basis_unklar": ("Cashflow-Basis zu niedrig fuer eine Aussage",
                     "Der Kurs liesse sich nur mit unrealistischem Wachstum "
                     "erklaeren - wahrscheinlicher ist ein voruebergehend "
                     "gedruecktes Ergebnis als eine Blase. Der Reverse DCF "
                     "traegt diesen Titel nicht."),
    "konservativ": ("Konservativ eingepreist",
                    "Der Kurs verlangt weniger, als das Unternehmen historisch geliefert hat."),
    "fair": ("Plausibel eingepreist",
             "Die eingepreiste Erwartung liegt in der unteren Haelfte des Korridors."),
    "anspruchsvoll": ("Anspruchsvoll, aber erreichbar",
                      "Der Kurs verlangt mehr als den Erwartungswert, bleibt aber im Korridor."),
    "zu_optimistisch": ("Ueber dem realistisch Lieferbaren",
                        "Der Kurs verlangt mehr, als das Unternehmen im Betrachtungsfenster "
                        "je erreicht hat."),
}

URTEIL_TON = {"konservativ": "gruen", "fair": "gruen",
              "anspruchsvoll": "gelb", "zu_optimistisch": "rot",
              "basis_unklar": "grau"}


# ---------------------------------------------------------------------------
# Korridor
# ---------------------------------------------------------------------------

class Korridor:
    __slots__ = ("tief", "mitte", "hoch", "anker", "gewichte", "playbook")

    def __init__(self, tief, mitte, hoch, anker, gewichte, playbook):
        self.tief, self.mitte, self.hoch = tief, mitte, hoch
        self.anker, self.gewichte, self.playbook = anker, gewichte, playbook

    def position(self, x: Optional[float]) -> str:
        if x is None:
            return "fair"
        if x > self.hoch:
            return "zu_optimistisch"
        if x > self.mitte:
            return "anspruchsvoll"
        if x >= self.tief:
            return "fair"
        return "konservativ"

    def as_dict(self) -> dict:
        return {"tief": round(self.tief, 4), "mitte": round(self.mitte, 4),
                "hoch": round(self.hoch, 4),
                "anker": {k: round(v, 4) for k, v in self.anker.items()},
                "gewichte": {k: round(v, 3) for k, v in self.gewichte.items()},
                "playbook": self.playbook}


def rd_korridor(anker: Dict[str, Optional[float]], playbook: str = "quality",
             breite: float = 1.0) -> Optional[Korridor]:
    """Gewichteter Erwartungskorridor aus den vorhandenen Ankern.

    mitte = gewichteter Mittelwert
    tief  = mitte - breite x gewichtete Standardabweichung
    hoch  = mitte + breite x gewichtete Standardabweichung

    Anschliessend auf die tatsaechlich beobachteten Extremwerte begrenzt: der
    Korridor soll nie mehr behaupten, als die Datenlage hergibt.
    """
    pb = playbook if playbook in PLAYBOOK_GEWICHTE else "quality"
    basis = dict(PLAYBOOK_GEWICHTE[pb])
    basis.update(_KURZ_GEWICHTE)

    nutzbar = {k: float(v) for k, v in (anker or {}).items()
               if v is not None and k in basis and math.isfinite(float(v))}
    if len(nutzbar) < 2:
        # Ein einzelner Anker ergibt keinen Korridor, sondern eine Zahl mit
        # erfundener Streuung. Lieber kein Urteil als ein falsches.
        return None

    summe = sum(basis[k] for k in nutzbar)
    gew = {k: basis[k] / summe for k in nutzbar}

    mitte = sum(gew[k] * nutzbar[k] for k in nutzbar)
    sd = math.sqrt(sum(gew[k] * (nutzbar[k] - mitte) ** 2 for k in nutzbar))

    lo_beob, hi_beob = min(nutzbar.values()), max(nutzbar.values())
    if len(nutzbar) > 1:
        tief = max(lo_beob, mitte - breite * sd)
        hoch = min(hi_beob, mitte + breite * sd)
    else:
        tief, hoch = mitte * 0.8, mitte * 1.2

    # MINDESTBREITE. Liegen die Anker eng beieinander - eine Firma mit sehr
    # gleichmaessigem Wachstum -, schrumpft der Korridor auf einen Punkt. Dann
    # gilt jede Abweichung nach oben sofort als "zu optimistisch", und das Gate
    # wird beliebig streng. Im Test ergaben zwoelf Jahre stetiges Wachstum
    # einen Korridor von 6,4 % bis 6,5 %.
    #
    # Prognosen sind nicht auf Zehntelprozente genau. Zwei Prozentpunkte oder
    # ein Viertel des Mittelwerts - je nachdem, was groesser ist - ist die
    # Untergrenze dessen, was noch eine Aussage traegt.
    _min_breite = max(0.02, abs(mitte) * 0.25)
    if hoch - tief < _min_breite:
        halb = _min_breite / 2.0
        tief, hoch = mitte - halb, mitte + halb

    return Korridor(tief, mitte, hoch, nutzbar, gew, pb)


# ---------------------------------------------------------------------------
# DCF-Loeser (Struktur identisch zu valuation.dcf_two_stage)
# ---------------------------------------------------------------------------

def _wert_roh(fcf, shares, net_debt, g1, g_term, r, years) -> Optional[float]:
    """Wie _wert_je_aktie, aber ohne die Positiv-Bedingung - fuer die Bisektion.
    Ohne diese Fassung liefert der untere Suchrand None (negatives Eigenkapital)
    und die Loesung wird faelschlich als 'nicht loesbar' gemeldet."""
    if not shares:
        return None
    pv, cf = 0.0, float(fcf)
    for t in range(1, years + 1):
        g_t = g1 + (g_term - g1) * (t - 1) / (years - 1)
        cf *= (1 + g_t)
        pv += cf / ((1 + r) ** t)
    terminal = cf * (1 + g_term) / (r - g_term) / ((1 + r) ** years)
    return (pv + terminal - (net_debt or 0.0)) / shares


def _wert_je_aktie(fcf, shares, net_debt, g1, g_term, r, years) -> Optional[float]:
    pv, cf = 0.0, float(fcf)
    for t in range(1, years + 1):
        g_t = g1 + (g_term - g1) * (t - 1) / (years - 1)
        cf *= (1 + g_t)
        pv += cf / ((1 + r) ** t)
    terminal = cf * (1 + g_term) / (r - g_term) / ((1 + r) ** years)
    equity = pv + terminal - (net_debt or 0.0)
    return equity / shares if (shares and equity > 0) else None


def _basis(fund, preset: str) -> Optional[dict]:

    fcf = fcf_basis(fund)["basis"]
    shares = fund.get("shares_out")
    price = fund.get("price")
    if not fcf or not shares or not price or fcf <= 0:
        return None
    years = max(int(V.get("projection_years", 10)), 2)
    g_term = V["terminal_growth"]
    r = wacc(fund.get("beta"), fund.get("market_cap"), fund.get("total_debt"))
    if r - g_term < 0.045:
        r = g_term + 0.045
    g1 = fund.get("revenue_growth")
    if g1 is None:
        g1 = fund.get("earnings_growth") or 0.06
    cap = 0.25 if preset == "inflection" else 0.16
    return {"fcf": float(fcf), "shares": float(shares),
            "net_debt": float(fund.get("net_debt") or 0.0),
            "price": float(price), "years": years, "g_term": g_term, "r": r,
            "g1_modell": max(min(g1, cap), -0.03)}


def _loese(fn, ziel: float, lo: float, hi: float, schritte: int = 90) -> Optional[float]:
    """Bisektion fuer monoton steigende fn. None, wenn ziel ausserhalb liegt."""
    f_lo, f_hi = fn(lo), fn(hi)
    if f_lo is None or f_hi is None:
        return None
    if not (f_lo - 1e-9 <= ziel <= f_hi + 1e-9):
        return None
    for _ in range(schritte):
        mid = (lo + hi) / 2.0
        v = fn(mid)
        if v is None or v < ziel:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def impliziertes_wachstum(fund, preset: str = "quality") -> Optional[float]:
    """Startwachstum g1, das den aktuellen Kurs rechtfertigt (mit Abklingen)."""
    b = _basis(fund, preset)
    if not b:
        return None
    fn = lambda g: _wert_roh(b["fcf"], b["shares"], b["net_debt"],  # noqa: E731
                             g, b["g_term"], b["r"], b["years"])
    return _loese(fn, b["price"], -0.25, 0.70)


def implizierte_cash_basis(fund, preset: str = "quality") -> Optional[float]:
    """Faktor auf den heutigen Free Cashflow, der den Kurs rechtfertigt.

    1,00 = der Kurs ist mit dem heutigen FCF und dem Modellwachstum erklaerbar.
    1,40 = der Kurs verlangt 40 % mehr Cash-Basis als heute vorhanden ist.
    Das ist die zweite Achse: sie faengt genau den Fall, in dem nicht das
    Wachstum, sondern das Ausgangsniveau des Cashflows gestreckt wird.
    """
    b = _basis(fund, preset)
    if not b:
        return None
    fn = lambda f: _wert_roh(b["fcf"] * f, b["shares"], b["net_debt"],  # noqa: E731
                             b["g1_modell"], b["g_term"], b["r"], b["years"])
    return _loese(fn, b["price"], 0.02, 12.0)


# ---------------------------------------------------------------------------
# Anker aus der Historie
# ---------------------------------------------------------------------------

def cagr(reihe: Sequence[float], jahre: Optional[int] = None) -> Optional[float]:
    """CAGR aus einer Reihe (aeltester Wert zuerst)."""
    xs = [float(v) for v in (reihe or [])
          if v is not None and math.isfinite(float(v)) and float(v) > 0]
    if len(xs) < 2:
        return None
    if jahre is not None:
        xs = xs[-(jahre + 1):]
        if len(xs) < 2:
            return None
    return (xs[-1] / xs[0]) ** (1.0 / (len(xs) - 1)) - 1.0


#: Unter so vielen Jahren ist ein "historischer Korridor" keine Historie,
#: sondern eine Momentaufnahme. Bei NVDA lieferten drei Boomjahre einen
#: Korridor von 68-100 % p. a. - und der Kurs, der 88 % verlangt, wurde
#: dadurch als "konservativ eingepreist" ausgewiesen. Genau falsch herum.
MIN_ANKER_JAHRE = 5

#: Oberhalb dieser Rate ist die Frage nicht mehr, ob der Kurs im Korridor
#: liegt, sondern ob das Modell den Titel ueberhaupt tragen kann.
IMPLIZIT_ABSURD = 0.40


def wachstums_anker(umsatz_reihe: Sequence[float],
                    konsens: Optional[float] = None) -> Dict[str, Optional[float]]:
    """Ankerdict aus einer Jahresumsatzreihe (aeltester Wert ZUERST).

    Achtung: roic.kennzahl_historie und providers.get_financials liefern
    'recent first' - vor dem Aufruf umdrehen.
    """
    xs = [v for v in (umsatz_reihe or []) if v]
    n = len(xs)
    out = {"konsens": konsens}

    # ANKER AN DIE VERFUEGBARE HISTORIE ANPASSEN.
    #
    # Der urspruengliche Entwurf sah 3J/5J/10J vor. Beide Datenquellen liefern
    # aber genau fuenf Geschaeftsjahre - roic wie FMP, an sechs Titeln geprueft.
    # Damit gab es nie mehr als zwei Anker, der Korridor stand auf zu wenig
    # Grundlage und das Gate durfte bei KEINEM Titel ausschliessen.
    #
    # Statt weiter nach Daten zu suchen, die es nicht gibt: die Anker an das
    # anpassen, was da ist. Fuenf Jahrespunkte ergeben vier Intervalle, also
    # 1J-, 2J-, 3J- und 4J-Raten. Die sind untereinander korreliert - bei einem
    # Zykliker wie Devon (+57 %, -20 %, +4 %, +8 %) aber keineswegs gleich.
    # Genau aus dieser Streuung entsteht die Korridorbreite.
    #
    # Was damit NICHT mehr geht: der Vergleich ueber einen vollen Zyklus. Die
    # Playbook-Gewichtung "Zykliker -> lange Historie schwerer" laeuft bei vier
    # Jahren weitgehend ins Leere. Das ist eine Einschraenkung der Datenlage,
    # keine der Methode - und sie gehoert benannt statt kaschiert.
    for jahre, name in ((1, "cagr_1j"), (2, "cagr_2j"),
                        (3, "cagr_3j"), (4, "cagr_4j"),
                        (5, "cagr_5j"), (10, "cagr_10j")):
        if n >= jahre + 1:
            w = cagr(xs, jahre)
            if w is not None:
                out[name] = w
    out["_jahre"] = n
    out["_spanne_jahre"] = max(0, n - 1)
    return out


def anker_aus_fund(fund, historie: Optional[List[dict]] = None,
                   fin: Optional[dict] = None) -> Dict[str, Optional[float]]:
    """Bequemer Weg: Anker aus roic.kennzahl_historie ODER providers.get_financials.

    historie: Liste aus roic.kennzahl_historie(t) - Felder 'jahr', 'revenue'
    fin:      dict aus providers.get_financials(t) - Feld 'revenue' (recent first)
    """
    umsatz: List[float] = []
    if historie:
        rows = [z for z in historie if z.get("revenue")]
        rows.sort(key=lambda z: str(z.get("jahr") or ""))
        umsatz = [float(z["revenue"]) for z in rows]
    elif fin and fin.get("revenue"):
        umsatz = [float(x) for x in reversed(fin["revenue"]) if x]

    # KONSENS-ANKER: nur eine echte UMSATZ-Prognose, sonst gar keiner.
    #
    # Vorher stand hier ein Rueckfall auf earnings_growth. Da
    # revenue_growth_next in keinem Datensatz existierte, wurde damit IMMER
    # das Gewinnwachstum als Anker fuer das Umsatzwachstum benutzt - zwei
    # verschiedene Groessen. Die Folgen waren grotesk:
    #   UnitedHealth  Umsatz +12 %, Gewinn -16 %  -> Korridor -15,7 % bis 11,4 %
    #   Eli Lilly     Umsatz +45 %, Gewinn +95 %  -> Korridor 36,5 % bis 95,0 %
    # Ein Korridor mit Obergrenze 95 % Jahreswachstum ueber zehn Jahre bewertet
    # nichts mehr. Lieber ein Anker weniger als ein falscher.
    konsens = fund.get("revenue_growth_next")
    if konsens is None and umsatz and fund.get("revenue_growth") is not None:
        # Letzte gemessene Jahresrate ist zumindest dieselbe Groesse.
        konsens = fund.get("revenue_growth")
    anker = wachstums_anker(umsatz, konsens)
    anker["_konsens_quelle"] = ("Umsatzprognose"
                               if fund.get("revenue_growth_next") is not None
                               else ("letzte Jahresrate" if konsens is not None
                                     else "keiner"))
    return anker


# ---------------------------------------------------------------------------
# Benchmark-Tabelle und Gitter
# ---------------------------------------------------------------------------

def _benchmark(b: dict, kor: Korridor, impliziert: Optional[float],
               g_modell: Optional[float]) -> List[dict]:
    zeilen = []
    eintraege = list(kor.anker.items())
    if g_modell is not None:
        eintraege.append(("modell", g_modell))

    for key, g in eintraege:
        w = _wert_je_aktie(b["fcf"], b["shares"], b["net_debt"], g,
                           b["g_term"], b["r"], b["years"])
        zeilen.append({
            "key": key, "label": ANKER_LABEL.get(key, key), "treiber": g,
            "wert": round(w, 2) if w else None,
            "upside": round((w - b["price"]) / b["price"] * 100, 1) if w else None,
            "im_korridor": kor.tief <= g <= kor.hoch,
            "notiz": "",
        })
    if impliziert is not None:
        zeilen.append({
            "key": "impliziert", "label": ANKER_LABEL["impliziert"],
            "treiber": impliziert, "wert": round(b["price"], 2), "upside": 0.0,
            "im_korridor": kor.tief <= impliziert <= kor.hoch,
            "notiz": "= heutiger Kurs",
        })
    zeilen.sort(key=lambda z: z["treiber"])
    return zeilen


def rd_gitter(b: dict, g_bereich: Optional[Tuple[float, float]] = None,
           cash_bereich: Optional[Tuple[float, float]] = None,
           schritte: int = 8, g_imp: Optional[float] = None,
           cash_imp: Optional[float] = None) -> dict:
    """Wert je Aktie ueber Wachstum x Cash-Basis, plus Iso-Linie Wert == Kurs.

    Hier ist der Single-Assumption-Ansatz blind: Ein Kurs kann bei plausiblem
    Wachstum UND plausibler Cash-Basis unerreichbar sein, weil er beide
    gleichzeitig am oberen Rand verlangt.
    """
    # Bereiche um die eingepreisten Werte legen: ein festes Raster von 0-16 %
    # zeigt bei einem Titel, der 28 % verlangt, nur rote Felder und keine
    # Iso-Linie - also gar nichts.
    if g_bereich is None:
        obergrenze = max(0.16, (g_imp or 0.0) * 1.15, (b["g1_modell"] or 0) * 2)
        g_bereich = (0.00, min(obergrenze, 0.45))
    if cash_bereich is None:
        cash_bereich = (0.7, max(1.6, (cash_imp or 1.0) * 1.15))

    gs = [g_bereich[0] + (g_bereich[1] - g_bereich[0]) * i / (schritte - 1)
          for i in range(schritte)]
    cs = [cash_bereich[0] + (cash_bereich[1] - cash_bereich[0]) * i / (schritte - 1)
          for i in range(schritte)]

    werte, iso = [], []
    for c in cs:
        reihe = [_wert_je_aktie(b["fcf"] * c, b["shares"], b["net_debt"], g,
                                b["g_term"], b["r"], b["years"]) for g in gs]
        werte.append(reihe)
        fn = lambda g, _c=c: _wert_roh(b["fcf"] * _c, b["shares"],  # noqa: E731
                                       b["net_debt"], g, b["g_term"],
                                       b["r"], b["years"])
        iso.append(_loese(fn, b["price"], -0.30, 0.90))

    return {"wachstum": gs, "cash_basis": cs, "werte": werte,
            "iso_wachstum": iso, "preis": b["price"]}


# ---------------------------------------------------------------------------
# Hauptfunktion
# ---------------------------------------------------------------------------

def reverse_dcf_analyse(fund, anker: Dict[str, Optional[float]],
                preset: str = "quality", mit_gitter: bool = True) -> Optional[dict]:
    """Vollstaendiger Reverse DCF mit Urteil.

    fund    bestehendes fund-Dict aus providers.get_fundamentals
    anker   {"cagr_3j":.., "cagr_5j":.., "cagr_10j":.., "konsens":..}
            (siehe anker_aus_fund)
    preset  quality | cyclical | inflection | financial
    """
    b = _basis(fund, preset)
    if not b:
        return None
    kor = rd_korridor(anker, preset)
    if not kor:
        return None

    g_imp = impliziertes_wachstum(fund, preset)
    cash_imp = implizierte_cash_basis(fund, preset)
    # ------------------------------------------------------------------
    # GEDRUECKTE BASIS von UEBERBEWERTUNG unterscheiden.
    #
    # Der Loeser sucht das Wachstum, das den Kurs rechtfertigt - ausgehend vom
    # HEUTIGEN Cashflow. Ist der zyklisch gedrueckt, braucht er absurde Raten.
    # Im 30-Titel-Lauf: Dow Chemical 69 %, Estee Lauder 67 %, Steel Dynamics
    # 48 % Umsatzwachstum pro Jahr ueber zehn Jahre. Kein Markt preist das ein.
    #
    # Die Aussage ist dann nicht "der Kurs ist absurd", sondern "die Basis
    # taugt nicht als Ausgangspunkt". Beides als "zu teuer" zu melden ist
    # falsch - und trifft ausgerechnet die Titel, die ein Value-Filter finden
    # soll: solche mit voruebergehend gedruecktem Ergebnis.
    #
    # Faustregel: Verlangt der Kurs mehr als das Dreifache der Korridor-
    # obergrenze, ist die Basis die wahrscheinlichere Erklaerung.
    # Achtung bei schrumpfenden Firmen: Dort ist die Korridorobergrenze negativ
    # (Dow: -1,9 %). Eine Bedingung "hoch > 0" wuerde genau die Faelle
    # ausschliessen, um die es geht. Deshalb wird die Obergrenze bei 2 %
    # gebodet, bevor sie verdreifacht wird.
    _obergrenze = max(kor.hoch, 0.02)
    _weit_drueber = bool(g_imp is not None
                         and g_imp > max(3.0 * _obergrenze, 0.25))

    # Hohes eingepreistes Wachstum entsteht auf ZWEI Wegen, und die Hoehe
    # allein trennt sie nicht:
    #   a) der Kurs ist teuer      -> Costco, Marge normal, FCF-Rendite 1,7 %
    #   b) die Basis ist gedrueckt -> Dow, Marge eingebrochen
    # Der Unterscheider ist die MARGE, nicht die implizierte Rate. Liegt die
    # aktuelle Marge deutlich unter dem eigenen Mehrjahresschnitt, ist der
    # Ausgangspunkt gedrueckt; liegt sie normal, ist der Kurs schlicht hoch.
    #
    # Die Zahlen dafuer liegen bereits vor: providers legt _zyklus_diagnose an
    # (Schnitt- und aktuelle Marge). Ohne diese Angabe wird NICHT auf
    # "gedrueckt" erkannt - im Zweifel bleibt es bei "zu optimistisch", weil
    # das die vorsichtigere Aussage ist.
    _zd = fund.get("_zyklus_diagnose") or {}
    _akt, _schnitt = _zd.get("aktuelle_marge"), _zd.get("schnitt_marge")
    _marge_gedrueckt = bool(_akt is not None and _schnitt
                            and _schnitt > 0 and _akt < 0.75 * _schnitt)
    basis_gedrueckt = bool(_weit_drueber and _marge_gedrueckt)

    urteil = kor.position(g_imp)
    if basis_gedrueckt:
        urteil = "basis_unklar"
    elif g_imp is not None and g_imp > IMPLIZIT_ABSURD:
        # Ueber 40 % p. a. ueber zehn Jahre hat kein Unternehmen der Groesse
        # je geliefert. Dass die Historie zufaellig noch hoeher liegt (drei
        # Boomjahre), macht den Kurs nicht konservativ - es macht den
        # Korridor unbrauchbar.
        urteil = "zu_optimistisch"
    titel, unter = URTEIL_TEXT[urteil]

    hinweise: List[str] = []
    if g_imp is not None and g_imp > kor.hoch:
        hinweise.append(
            f"Eingepreist sind {g_imp * 100:.1f} % Startwachstum. Der realistische "
            f"Korridor ({kor.tief * 100:.1f}-{kor.hoch * 100:.1f} %) endet darunter.")
    _spanne = (anker or {}).get("_spanne_jahre") or 0
    if preset in ("cyclical", "financial") and _spanne < 8:
        hinweise.append(
            f"Playbook {preset}, aber nur {_spanne} Jahre Umsatzhistorie. Der "
            f"Korridor deckt keinen vollen Zyklus ab - fuer einen Zykliker ist "
            f"das die schwaechste Stelle des Urteils.")
    beide = bool(g_imp is not None and g_imp > kor.mitte
                 and cash_imp is not None and cash_imp > 1.10)
    if beide:
        hinweise.append(
            "Wachstum und Cash-Basis sind gleichzeitig gestreckt. Einzelne Treiber "
            "zu testen unterschaetzt hier, wie viel der Kurs verlangt.")
    if g_imp is None:
        hinweise.append("Der Kurs liegt ausserhalb des loesbaren Wachstumsbereichs - "
                        "das Modell traegt diesen Titel nicht.")
    if basis_gedrueckt:
        hinweise.append(
            f"Der Kurs verlangt rechnerisch {g_imp * 100:.0f} % Wachstum, und "
            f"die Marge liegt mit {_akt:.1%} deutlich unter dem Schnitt von "
            f"{_schnitt:.1%}. Der heutige Cashflow ({b['fcf'] / 1e9:.2f} Mrd) "
            f"taugt damit nicht als Ausgangspunkt - das ist keine Aussage "
            f"ueber den Kurs.")
    elif _weit_drueber and not _marge_gedrueckt:
        hinweise.append(
            f"Der Kurs verlangt {g_imp * 100:.0f} % Wachstum bei normaler Marge. "
            f"Hier ist der Kurs hoch, nicht die Basis niedrig.")
    elif g_imp is not None and g_imp > IMPLIZIT_ABSURD:
        hinweise.append(
            f"Eingepreist sind {g_imp * 100:.0f} % Startwachstum ueber "
            f"{b['years']} Jahre. Das hat kein Unternehmen dieser Groesse je "
            f"geliefert - unabhaengig davon, wo die kurze Historie liegt.")
    _n = (anker or {}).get("_jahre")
    if _n and _n < MIN_ANKER_JAHRE:
        hinweise.append(
            f"Nur {_n} Jahre Umsatzhistorie verfuegbar. Ein Korridor daraus "
            f"beschreibt die letzte Phase, nicht den Zyklus - das Urteil ist "
            f"entsprechend schwach.")

    return {
        "preis": b["price"],
        "playbook": preset,
        "impliziertes_wachstum": round(g_imp, 4) if g_imp is not None else None,
        "implizierte_cash_basis": round(cash_imp, 3) if cash_imp is not None else None,
        "korridor": kor.as_dict(),
        "urteil": urteil,
        "urteil_titel": titel,
        "urteil_text": unter,
        "urteil_ton": URTEIL_TON[urteil],
        "beide_gestreckt": beide,
        "basis_gedrueckt": basis_gedrueckt,
        "weit_ueber_korridor": _weit_drueber,
        "marge_gedrueckt": _marge_gedrueckt,
        "anker_anzahl": len(kor.anker),
        "konsens_quelle": (anker or {}).get("_konsens_quelle"),
        "historie_jahre": (anker or {}).get("_jahre"),
        # Wie viele Jahre deckt der laengste Anker ab? Bei vier Jahren ist der
        # Korridor eine Momentaufnahme, kein Zyklusvergleich - bei einem
        # Zykliker ist das eine echte Einschraenkung des Urteils.
        "spanne_jahre": (anker or {}).get("_spanne_jahre"),
        # Zwei Anker sind das Minimum, aber kein Korridor im gemeinten Sinn:
        # Der regime-gewichtete Vergleich ueber 3/5/10 Jahre braucht mehr als
        # eine Historienrate plus einen Konsenswert. Mit weniger als drei
        # Ankern taugt das Urteil als Hinweis, nicht als Ausschlussgrund.
        "belastbar": len(kor.anker) >= 3,
        "zeilen": _benchmark(b, kor, g_imp, b["g1_modell"]),
        "gitter": (rd_gitter(b, g_imp=g_imp, cash_imp=cash_imp)
                   if mit_gitter else None),
        "hinweise": hinweise,
        "modell": {"wacc": round(b["r"], 4), "jahre": b["years"],
                   "terminal_growth": b["g_term"],
                   "g1_modell": round(b["g1_modell"], 4)},
    }
