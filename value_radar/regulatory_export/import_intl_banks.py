"""Kapital- und Liquiditaetskennzahlen von Banken ausserhalb von EU/EWR und USA.

Quelle 1: APRA "Authorised deposit-taking institution centralised publication" (hoechste Konsolidierungsebene,
Tabelle 1 Kapital, Tabelle 3 LCR/NSFR). Weitere Quellen (Basel-Offenlegung KM1) kommen ueber
reviewed-key-metrics.json in dasselbe Format. Nur Emittenten aus intl-bank-map.json. Keine Scores.

Aufruf: import_intl_banks.py APRA.xlsx AUSGABE.json
"""
import datetime as dt
import hashlib
import json
import math
import re
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
APRA_PAGE = 'https://www.apra.gov.au/quarterly-authorised-deposit-taking-institution-statistics'


def fraction(v):
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and 0 <= v <= 10 else None


def table(wb, prefix):
    name = next(n for n in wb.sheetnames if n.strip() == prefix)
    rows = list(wb[name].iter_rows(values_only=True))
    header_at = next(i for i, r in enumerate(rows) if r and r[0] == 'Entity quarter end')
    header = [str(h or '').strip() for h in rows[header_at]]
    return [dict(zip(header, r)) for r in rows[header_at + 1:] if r and isinstance(r[0], dt.datetime) and r[1]]


def latest(rows, entity):
    mine = [r for r in rows if str(r['Entity']).strip() == entity]
    return max(mine, key=lambda r: r['Entity quarter end']) if mine else None


def apra(path, entities):
    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    capital, liquidity = table(wb, 'Table 1'), table(wb, 'Table 3')
    out = {}
    for entity in entities:
        c = latest(capital, entity)
        if not c:
            continue
        period = c['Entity quarter end'].date().isoformat()
        l = next((r for r in liquidity if str(r['Entity']).strip() == entity and r['Entity quarter end'] == c['Entity quarter end']), None)
        out[entity] = {'period': period,
                       'metrics': {k: fraction(c.get(col)) for k, col in (('cet1_ratio', 'Common Equity Tier 1 capital ratio'), ('tier1_ratio', 'Tier 1 capital ratio'), ('total_capital_ratio', 'Total capital ratio'))},
                       'lcr': fraction((l or {}).get('Mean Liquidity coverage ratio (LCR)')), 'nsfr': fraction((l or {}).get('Net stable funding ratio (NSFR)'))}
    return out


def build(apra_path, mapping, now, apra_url=APRA_PAGE, reviewed=None):
    raw = Path(apra_path).read_bytes()
    entities = [i['sourceEntity'] for i in mapping['issuers'] if i['source'] == 'apra_adi_centralised_publication']
    values = apra(apra_path, entities)
    issuers, rejected = {}, {}
    for i in mapping['issuers']:
        v = values.get(i['sourceEntity'])
        m = (v or {}).get('metrics') or {}
        chain = [m.get(k) for k in ('cet1_ratio', 'tier1_ratio', 'total_capital_ratio')]
        if not v or m.get('cet1_ratio') is None or any(a is not None and b is not None and a > b + 1e-6 for a, b in zip(chain, chain[1:])):
            rejected[i['isin']] = 'capital_missing_or_inconsistent'
            continue
        issuers[i['isin']] = {'issuer': i['issuer'], 'jurisdiction': i['jurisdiction'], 'regulator': i['regulator'], 'scope': 'highest_consolidation_level',
                              'period': v['period'], 'metrics': {k: x for k, x in m.items() if x is not None}, 'lcr': v['lcr'], 'nsfr': v['nsfr'],
                              'cet1Requirement': None,
                              'source': {'type': i['source'], 'entity': i['sourceEntity'], 'url': apra_url, 'sha256': hashlib.sha256(raw).hexdigest(),
                                         'tables': 'Table 1 Regulatory capital; Table 3 Liquidity ratios (mean LCR over the quarter)'}}
    for e in (reviewed or {}).get('entries', []):
        reason = reviewed_problem(e)
        if reason:
            rejected[e.get('isin', '?')] = reason
            continue
        dl, nd = e.get('defaultedLoans'), e.get('nonDefaultedLoans')
        issuers[e['isin']] = {'issuer': e['issuer'], 'jurisdiction': e['jurisdiction'], 'regulator': e['regulator'], 'scope': 'consolidated_group',
                              'period': e['period'], 'metrics': {k: e[k] for k in ('cet1_ratio', 'tier1_ratio', 'total_capital_ratio', 'leverage_ratio') if fraction(e.get(k)) is not None},
                              'lcr': fraction(e.get('lcr')), 'nsfr': fraction(e.get('nsfr')),
                              'cet1Requirement': e['cet1Requirement'], 'cet1RequirementDefinition': e['cet1RequirementDefinition'],
                              'requirementComponents': e.get('requirementComponents'), 'requirementSourceUrl': e.get('requirementSourceUrl'),
                              'defaultedLoanRatio': dl / (dl + nd) if isinstance(dl, (int, float)) and isinstance(nd, (int, float)) and dl >= 0 and nd > 0 else None,
                              'source': e['source']}
    return {'schema': 1, 'method': 'intl-bank-metrics-v1', 'importedAt': now.isoformat(),
            'mappingReviewExpires': min(mapping['review_expires'], (reviewed or {}).get('review_expires', mapping['review_expires'])),
            'issuers': issuers, 'rejected': rejected, 'open': {**mapping.get('open', {}), **(reviewed or {}).get('open', {})}, 'scoreContribution': 0}


def reviewed_problem(e):
    """Geprueft abgelegte KM1-Werte: Pflichtfelder, Kapitalhierarchie, Anforderung = Summe der Bestandteile."""
    if not all(k in e for k in ('isin', 'issuer', 'period', 'cet1_ratio', 'cet1Requirement', 'source')) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', str(e['period'])):
        return 'reviewed_entry_incomplete'
    chain = [fraction(e.get(k)) for k in ('cet1_ratio', 'tier1_ratio', 'total_capital_ratio')]
    if chain[0] is None or chain[0] > 1 or any(a is not None and b is not None and a > b + 1e-6 for a, b in zip(chain, chain[1:])):
        return 'capital_missing_or_inconsistent'
    parts = (e.get('requirementComponents') or {}).values()
    if not 0 < e['cet1Requirement'] < .3 or abs(sum(parts) - e['cet1Requirement']) > 1e-6:
        return 'requirement_components_mismatch'
    if e['source'].get('type') != 'basel_pillar3_km1' or not re.fullmatch(r'[0-9a-f]{64}', e['source'].get('sha256', '')) or not str(e['source'].get('url', '')).startswith('https://'):
        return 'source_unverified'
    return ''


def main():
    mapping = json.loads((ROOT / 'intl-bank-map.json').read_text(encoding='utf-8'))
    reviewed = json.loads((ROOT / 'reviewed-key-metrics.json').read_text(encoding='utf-8'))
    result = build(sys.argv[1], mapping, dt.datetime.now(dt.timezone.utc), reviewed=reviewed)
    out = Path(sys.argv[2])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=1, ensure_ascii=False), encoding='utf-8')
    print(json.dumps({'issuers': {k: (v['issuer'], v['period'], v['metrics'].get('cet1_ratio'), v['lcr'], v['cet1Requirement']) for k, v in result['issuers'].items()}, 'rejected': result['rejected']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
