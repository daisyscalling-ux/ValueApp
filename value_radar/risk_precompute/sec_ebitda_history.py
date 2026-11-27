"""EBITDA aus SEC companyfacts (seit 27.11.2026, Entscheidung des Nutzers: nur EBITDA vor den ROIC-Jahren ableiten).

EBITDA = operativer Gewinn (OperatingIncomeLoss) + Abschreibungen (erstes vorhandenes Konzept aus DA_KONZEPTE). Gleicher
Abruf wie sec_cashflow_history (keine zusätzliche SEC-Anfrage). Regeln wie sec_revenue_history: nur Jahresberichte, Dauer
330-400 Tage, höchstens 8 Jahre alt, je Stichtag der neueste Bericht. Zusätzlich müssen beide Bestandteile aus DEMSELBEN
Bericht (Accession) und demselben Zeitraum stammen; Abschreibungen dürfen nicht negativ sein. Ein Konzept für Abschreibungen
je Titel (das erste, das den jüngsten Stichtag abdeckt), damit die Reihe nicht zwischen Abgrenzungen springt. Nur Anzeige;
die App übernimmt die Werte nur bei Übereinstimmung mit ROIC (sec-years.ts). Zählt in keinem Score.
"""
import math
from sec_source_evidence import observation

METHOD = 'sec-annual-ebitda-v1'
OI = ('us-gaap', 'OperatingIncomeLoss')
DA_KONZEPTE = [('us-gaap', 'DepreciationDepletionAndAmortization'), ('us-gaap', 'DepreciationAndAmortization'),
               ('us-gaap', 'DepreciationAmortizationAndAccretionNet')]


def _werte(data, now, ns, tag):
    """({(ende, start, waehrung, accession): wert}, {gleicher Schlüssel: (filed, form)}); nur Jahresdauer.
    Widersprüchliche Werte im selben Bericht ergeben None."""
    werte, meta = {}, {}
    for currency, items in data.get('facts', {}).get(ns, {}).get(tag, {}).get('units', {}).items():
        for fact in items:
            r = observation(fact, currency, now)
            if r is None or r['durationDays'] is None or not 330 <= r['durationDays'] <= 400:
                continue
            k = (r['end'], r['start'], currency, r['accession'])
            werte[k] = r['value'] if k not in werte or werte[k] == r['value'] else None
            meta.setdefault(k, (r['filed'], r['form']))
    return werte, meta


def normalize(data, cik, now):
    if str(data.get('cik', '')).lstrip('0') != str(cik).lstrip('0'):
        raise ValueError('cik_mismatch')
    oi, oi_meta = _werte(data, now, *OI)
    if not oi:
        return []
    juengstes = max(k[0] for k in oi)
    for ns, tag in DA_KONZEPTE:
        da, _ = _werte(data, now, ns, tag)
        if not any(k[0] == juengstes for k in da):
            continue
        je_ende = {}
        for k, v_oi in oi.items():
            if k not in da:
                continue
            filed, form = oi_meta[k]
            je_ende.setdefault((k[0], k[2]), []).append((filed, k, v_oi, da[k], form))
        reihe = []
        for (end, currency), versionen in je_ende.items():
            neu = max(v[0] for v in versionen)
            letzte = [v for v in versionen if v[0] == neu]
            # Widerspruch oder negative Abschreibung im neuesten Bericht verwirft den Stichtag (kein Rückfall auf ältere).
            if len({(v[1][1], v[2], v[3]) for v in letzte}) != 1 or any(v[2] is None or v[3] is None or v[3] < 0 for v in letzte):
                continue
            filed, k, v_oi, v_da, form = max(letzte, key=lambda v: v[1][3])
            wert = v_oi + v_da
            if not math.isfinite(wert):
                continue
            reihe.append({'end': end, 'start': k[1], 'filed': filed, 'accession': k[3], 'form': form, 'currency': currency,
                          'operatingIncome': v_oi, 'da': v_da, 'value': wert, 'daConcept': tag, 'namespace': ns,
                          'sourceUrl': f'https://www.sec.gov/Archives/edgar/data/{int(cik)}/{k[3].replace("-", "")}/'})
        reihe.sort(key=lambda r: r['end'])
        if len({r['currency'] for r in reihe}) > 1:
            return []
        return reihe[-8:]
    return []
