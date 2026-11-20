"""Jahresumsatz aus SEC companyfacts (seit 20.11.2026, Kennzahlen-Tabelle der Einzelanalyse).

Gleicher Abruf wie sec_cashflow_history (keine zusaetzliche SEC-Anfrage). Ein Konzept je Titel: das erste aus CONCEPTS,
das den juengsten Jahreszeitraum abdeckt (Reihenfolge wie fundamental_export/SEC_UMSATZ.md: Gesamtumsatz vor ASC 606).
Nur Jahresberichte (10-K, 20-F, 40-F samt /A), Dauer 330-400 Tage, hoechstens 8 Jahre alt; je Stichtag der neueste Bericht,
widerspruechliche Werte im selben Bericht verwerfen den Stichtag. Nur Anzeige; zaehlt in keinem Score.
"""
import math
from sec_source_evidence import observation

CONCEPTS = [('us-gaap', 'Revenues'), ('us-gaap', 'RevenueFromContractWithCustomerExcludingAssessedTax'),
            ('us-gaap', 'SalesRevenueNet'), ('us-gaap', 'RevenueFromContractWithCustomerIncludingAssessedTax'), ('ifrs-full', 'Revenue')]
METHOD = 'sec-annual-revenue-v1'


def _reihe(data, cik, now, ns, tag):
    je_ende = {}
    for currency, items in data.get('facts', {}).get(ns, {}).get(tag, {}).get('units', {}).items():
        for fact in items:
            r = observation(fact, currency, now)
            if r is None or r['durationDays'] is None or not 330 <= r['durationDays'] <= 400 or r['value'] < 0:
                continue
            je_ende.setdefault((r['end'], currency), []).append(r)
    out = []
    for (end, currency), versions in je_ende.items():
        newest = max(v['filed'] for v in versions)
        latest = [v for v in versions if v['filed'] == newest]
        if len({(v['value'], v['start']) for v in latest}) != 1:
            continue
        v = max(latest, key=lambda x: x['accession'])
        out.append({'end': end, 'start': v['start'], 'filed': v['filed'], 'accession': v['accession'], 'form': v['form'],
                    'currency': currency, 'value': v['value'], 'namespace': ns, 'concept': tag,
                    'sourceUrl': f'https://www.sec.gov/Archives/edgar/data/{int(cik)}/{v["accession"].replace("-", "")}/'})
    return sorted(out, key=lambda r: r['end'])


def normalize(data, cik, now):
    if str(data.get('cik', '')).lstrip('0') != str(cik).lstrip('0'):
        raise ValueError('cik_mismatch')
    reihen = [(ns, tag, _reihe(data, cik, now, ns, tag)) for ns, tag in CONCEPTS]
    juengstes = max((r[-1]['end'] for _, _, r in reihen if r), default=None)
    if not juengstes:
        return []
    for ns, tag, r in reihen:
        if r and r[-1]['end'] == juengstes:
            waehrungen = {x['currency'] for x in r}
            if len(waehrungen) != 1:
                return []
            return [x for x in r if math.isfinite(x['value'])][-8:]
    return []
