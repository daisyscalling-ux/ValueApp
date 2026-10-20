"""Import a manually downloaded FFIEC BHCF archive; never infer stock identity."""
import argparse
import csv
import datetime as dt
import hashlib
import io
import json
import math
from pathlib import Path
import re
import zipfile

FIELDS = {
    'BHCAP793': ('cet1_ratio', 'COMMON EQUITY TIER 1 CAPITAL RATIO'),
    'BHCA7206': ('tier1_ratio', 'TIER 1 CAPITAL RATIO'),
    'BHCA7205': ('total_capital_ratio', 'TOTAL CAPITAL RATIO'),
    'BHCA7204': ('tier1_leverage_ratio', 'TIER 1 LEVERAGE RATIO'),
}
SOURCE = 'https://www.ffiec.gov/npw/FinancialReport/FinancialDataDownload'
FORM = 'https://www.federalreserve.gov/reportforms/forms/FR_Y-9C20160331_f.pdf'

def ratio(raw):
    raw = '' if raw is None else str(raw).strip()
    if not raw:
        return {'value': None, 'state': 'missing', 'raw_value': None}
    try:
        value = float(raw)
    except ValueError:
        value = float('nan')
    if not math.isfinite(value) or not -100 <= value <= 1000:
        return {'value': None, 'state': 'invalid', 'raw_value': raw}
    return {'value': value / 100, 'state': 'reported', 'raw_value': raw}

def read_dictionary(path, period):
    # Only the offline import requires openpyxl. Daily publication uses stdlib.
    import openpyxl
    book = openpyxl.load_workbook(path, read_only=True, data_only=True)
    definitions = {}
    try:
        for number, row in enumerate(book['Financial'].iter_rows(values_only=True), 1):
            code, start, end, description = row
            if code not in FIELDS or not start.date() <= period <= end.date():
                continue
            if code in definitions or not description.upper().startswith(FIELDS[code][1]):
                raise ValueError('Ambiguous or changed dictionary definition: ' + code)
            definitions[code] = {'metric': FIELDS[code][0], 'description': description,
                'sheet': 'Financial', 'row': number, 'valid_from': start.date().isoformat(),
                'valid_to': end.date().isoformat(), 'source_unit': 'percent', 'unit': 'fraction'}
    finally:
        book.close()
    if set(definitions) != set(FIELDS):
        raise ValueError('Dictionary missing active definitions')
    return definitions

def parse_stream(stream, period, today):
    if period > today or (period.month, period.day) not in [(3,31),(6,30),(9,30),(12,31)]:
        raise ValueError('Invalid reporting period')
    reader = csv.DictReader(stream, delimiter='^')
    required = set(FIELDS) | {'RSSD9001','RSSD9999','RSSD9017'}
    if not reader.fieldnames or not required.issubset(reader.fieldnames) or len(set(reader.fieldnames)) != len(reader.fieldnames):
        raise ValueError('Invalid archive columns')
    seen = set(); records = {}; missing = 0
    for row in reader:
        if None in row or any(v is None for v in row.values()):
            raise ValueError('Malformed row')
        rssd = row['RSSD9001'].strip()
        if not re.fullmatch(r'[1-9][0-9]*', rssd) or rssd in seen:
            raise ValueError('Invalid or duplicate RSSD identity')
        seen.add(rssd)
        if row['RSSD9999'] != period.strftime('%Y%m%d'):
            raise ValueError('Mixed reporting periods')
        metrics = {code: ratio(row[code]) for code in FIELDS}
        if all(v['state'] == 'missing' for v in metrics.values()):
            missing += 1
            continue
        if not row['RSSD9017'].strip():
            raise ValueError('Missing entity name')
        records[rssd] = {'rssd_id': rssd, 'name': row['RSSD9017'].strip(),
            'country': row.get('RSSD9005'), 'metrics': metrics}
    if not seen or not records:
        raise ValueError('Empty archive')
    return records, len(seen), missing

def import_archive(archive, dictionary, today=None):
    archive = Path(archive); dictionary = Path(dictionary)
    with zipfile.ZipFile(archive) as z:
        entries = z.infolist()
        if len(entries) != 1 or not re.fullmatch(r'BHCF\d{8}\.txt', entries[0].filename, re.I):
            raise ValueError('Expected one BHCF text file')
        entry = entries[0]
        if entry.file_size > 100_000_000:
            raise ValueError('Archive too large')
        period = dt.datetime.strptime(entry.filename[4:12], '%Y%m%d').date()
        definitions = read_dictionary(dictionary, period)
        with z.open(entry) as raw:
            records, total, missing = parse_stream(io.TextIOWrapper(raw, encoding='cp1252'), period, today or dt.date.today())
    return {'schema': 1, 'source': 'FFIEC NIC BHCF manual download', 'source_url': SOURCE,
        'reporting_period': period.isoformat(), 'imported_at': dt.datetime.now(dt.timezone.utc).isoformat(),
        'scope': 'FR_Y9C_consolidated_reporting_entity', 'published_at': None,
        'historical_point_in_time_usable': False, 'unit_evidence_url': FORM,
        'files': [{'name': p.name, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in (archive,dictionary)],
        'definitions': definitions, 'source_row_count': total, 'rows_without_capital_ratios': missing,
        'entity_count': len(records), 'entities': records,
        'limitations': ['Manual quarterly snapshot; no automatic FFIEC download.',
            'Consolidated reporting entity may be an intermediate holding, not the listed ultimate parent.',
            'No stock mapping, score, LCR or harmonized credit-quality metric supplied.',
            'Import time is not original publication time; not suitable for point-in-time backtests.']}

def link_fdic(holdings, fdic, today=None):
    today = today or dt.date.today()
    period = dt.date.fromisoformat(holdings['reporting_period'])
    age = (today-period).days
    if holdings.get('scope') != 'FR_Y9C_consolidated_reporting_entity' or age < 0:
        raise ValueError('Invalid holding snapshot scope or date')
    links = []
    for cert, institution in fdic['institutions'].items():
        rssd = institution.get('holding_rssd_id')
        if rssd not in holdings['entities']:
            continue
        links.append({'fdic_cert': cert, 'holding_rssd_id': rssd,
            'holding_period': holdings['reporting_period'], 'fdic_period': institution['period'],
            'same_period': institution['period'] == holdings['reporting_period'],
            'stock_identity_verified': False})
    return {'schema': 1, 'reporting_period': holdings['reporting_period'], 'age_days': age,
        'freshness': 'stale' if age > 180 else 'within_180_days',
        'linked_institutions': len(links), 'linked_holding_entities': len({r['holding_rssd_id'] for r in links}),
        'links': links, 'score': None, 'stock_identity_verified': False}

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--archive', required=True); p.add_argument('--dictionary', required=True)
    p.add_argument('--output', required=True)
    args = p.parse_args()
    data = import_archive(args.archive, args.dictionary)
    path = Path(args.output); path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, allow_nan=False), encoding='utf8'); temp.replace(path)
    print(json.dumps({k: data[k] for k in ['reporting_period','source_row_count','entity_count','rows_without_capital_ratios']}))
