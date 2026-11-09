"""Amtliche Kapital- und Kreditqualitaetsdaten europaeischer Banken importieren.

Quellen:
- EBA EU-wide Transparency Exercise (Full database): tr_oth.csv (Kapital, Leverage), tr_cre.csv (NPE), TR_Metadata.xlsx.
- EZB-Bankenaufsicht: Pillar_2_requirement.en.xlsx (bankspezifische P2R).
Nur Banken aus eu-bank-map.json (geprueft per LEI) werden uebernommen. Keine Scores.

Aufruf: import_eu_banks.py QUELLORDNER AUSGABE.json
"""
import csv
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent
EBA_BASE = 'https://www.eba.europa.eu/assets/TE2025/Full_database/883401/'
ECB_P2R = 'https://www.bankingsupervision.europa.eu/activities/srep/shared/Pillar_2_requirement.en.xlsx'
EXERCISE = 'EBA 2025 EU-wide Transparency Exercise'
# EBA-Positionen (SDD/TR_Metadata): Kapitalquoten im Blatt "Capital", Leverage im Blatt "Leverage".
CAPITAL_ITEMS = {'2520140': 'cet1_ratio', '2520141': 'tier1_ratio', '2520142': 'total_capital_ratio',
                 '2520146': 'cet1_ratio_fully_loaded', '2520905': 'leverage_ratio'}
LOANS_ITEM = '2520603'  # Gross carrying amount on loans and advances; Perf_Status 0 = gesamt, 2 = non-performing
MIN_CET1, CONSERVATION_BUFFER, P2R_CET1_SHARE = .045, .025, .5625


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def period_end(code):
    year, month = int(code[:4]), int(code[4:6])
    nxt = dt.date(year + (month == 12), month % 12 + 1, 1)
    return (nxt - dt.timedelta(days=1)).isoformat()


def number(v):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def percent(v):
    """EZB-Tabelle: Zahl als Anteil oder Text wie '2.25%' bzw. '1.50%1' (Fussnote 1). None bei 'n.a.'."""
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v), ''
    m = re.fullmatch(r'\s*(\d+(?:\.\d+)?)\s*%\s*(\d?)\s*', str(v or '').replace('\xa0', ' '))
    return (float(m.group(1)) / 100, m.group(2)) if m else (None, '')


def read_capital(path, leis):
    out = {}
    with open(path, encoding='utf-8') as stream:
        for r in csv.DictReader(stream):
            key = CAPITAL_ITEMS.get(r['Item'])
            if key and r['LEI_Code'] in leis:
                v = number(r['Amount'])
                if v is not None:
                    out.setdefault(r['LEI_Code'], {}).setdefault(r['Period'], {})[key] = v
    return out


def read_loans(path, leis):
    out = {}
    with open(path, encoding='utf-8') as stream:
        for r in csv.DictReader(stream):
            if (r['Item'] == LOANS_ITEM and r['LEI_Code'] in leis and r['Perf_Status'] in ('0', '2')
                    and all(r[k] == '0' for k in ('Portfolio', 'Country', 'Exposure', 'Status', 'NACE_codes'))):
                v = number(r['Amount'])
                if v is not None:
                    out.setdefault(r['LEI_Code'], {}).setdefault(r['Period'], {})['total' if r['Perf_Status'] == '0' else 'nonPerforming'] = v
    return out


def read_p2r(path):
    import openpyxl
    rows = list(openpyxl.load_workbook(path, read_only=True).active.iter_rows(values_only=True))
    header = [str(h or '') for h in rows[0]]
    # Spalten je Jahr: 'P2R applicable in 2025', 'Currently applicable P2R in 2026' (Fussnotenziffer direkt angehaengt), ohne P2R-LR.
    columns = {int(m.group(1)[:4]): i for i, h in enumerate(header) if 'LR' not in h and (m := re.search(r'P2R(?: applicable)? in (\d{4})', h))}
    out = {}
    for row in rows[1:]:
        if row and isinstance(row[0], str) and not re.match(r'\d+\.\s', row[0]):
            out[row[0].strip()] = {year: dict(zip(('value', 'footnote'), percent(row[i]))) for year, i in columns.items()}
    return out


def build(source, mapping, now):
    source = Path(source)
    files = {name: source / name for name in ('tr_oth.csv', 'tr_cre.csv', 'TR_Metadata.xlsx', 'Pillar_2_requirement.en.xlsx')}
    leis = {b['lei'] for b in mapping['banks']}
    capital, loans, p2r = read_capital(files['tr_oth.csv'], leis), read_loans(files['tr_cre.csv'], leis), read_p2r(files['Pillar_2_requirement.en.xlsx'])
    banks, rejected = {}, {}
    for b in mapping['banks']:
        periods = sorted(capital.get(b['lei'], {}))
        if not periods:
            rejected[b['lei']] = 'no_eba_capital'
            continue
        latest = periods[-1]
        metrics = {k: v for k, v in capital[b['lei']][latest].items() if 0 <= v <= 1}
        chain = [metrics.get(k) for k in ('cet1_ratio', 'tier1_ratio', 'total_capital_ratio')]
        if 'cet1_ratio' not in metrics or any(a is not None and c is not None and a > c + 1e-6 for a, c in zip(chain, chain[1:])):
            rejected[b['lei']] = 'capital_missing_or_inconsistent'
            continue
        entry = {'lei': b['lei'], 'ebaName': b['ebaName'], 'country': b['ebaCountry'], 'period': period_end(latest),
                 'metrics': metrics, 'sourceItems': {v: k for k, v in CAPITAL_ITEMS.items() if v in metrics}}
        loan = loans.get(b['lei'], {}).get(latest, {})
        if loan.get('total') and loan.get('nonPerforming') is not None and 0 <= loan['nonPerforming'] <= loan['total']:
            entry['nplRatio'] = loan['nonPerforming'] / loan['total']
            entry['loans'] = {'nonPerforming': loan['nonPerforming'], 'total': loan['total'], 'unit': 'EUR_million', 'item': LOANS_ITEM}
        if b.get('ecbName'):
            # Anforderung des Jahres, in dem der Kapitalstichtag liegt (nicht die spaeter geltende).
            year = int(entry['period'][:4])
            req = (p2r.get(b['ecbName']) or {}).get(year)
            if req and req['value'] is not None and 0 <= req['value'] <= .1:
                entry['p2r'] = {**req, 'year': year, 'ecbName': b['ecbName']}
                entry['cet1RequirementPartial'] = MIN_CET1 + CONSERVATION_BUFFER + P2R_CET1_SHARE * req['value']
            else:
                entry['p2r'] = None
                rejected.setdefault(b['lei'] + ':p2r', 'ecb_name_not_found')
        banks[b['lei']] = entry
    return {
        'schema': 1, 'method': 'eu-bank-capital-v1', 'importedAt': now.isoformat(), 'exercise': EXERCISE,
        'sources': {'eba': {name: {'url': EBA_BASE + name, 'sha256': sha256(files[name])} for name in ('tr_oth.csv', 'tr_cre.csv', 'TR_Metadata.xlsx')},
                    'ecb': {'url': ECB_P2R, 'sha256': sha256(files['Pillar_2_requirement.en.xlsx'])}},
        'mappingReviewExpires': mapping['review_expires'],
        'requirementDefinition': 'Partial CET1 requirement = 4.5 % minimum + 2.5 % capital conservation buffer + 56.25 % of P2R. '
                                 'Excludes countercyclical, systemic risk and O-SII/G-SII buffers; 56.25 % is the legal minimum CET1 share of P2R.',
        'nplDefinition': 'Non-performing / total gross carrying amount of loans and advances (EBA item 2520603), consolidated.',
        'banks': banks, 'rejected': rejected, 'scoreContribution': 0,
    }


def main():
    source, output = Path(sys.argv[1]), Path(sys.argv[2])
    mapping = json.loads((ROOT / 'eu-bank-map.json').read_text(encoding='utf-8'))
    result = build(source, mapping, dt.datetime.now(dt.timezone.utc))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=1, ensure_ascii=False), encoding='utf-8')
    print(json.dumps({'banks': len(result['banks']), 'rejected': result['rejected'],
                      'withRequirement': sum('cet1RequirementPartial' in b for b in result['banks'].values()),
                      'withNpl': sum('nplRatio' in b for b in result['banks'].values())}, indent=1))


if __name__ == '__main__':
    main()
