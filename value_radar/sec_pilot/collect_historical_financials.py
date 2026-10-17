"""Archive exited issuers by reviewed SEC identity; research only, no score changes."""
import datetime as dt
import json
import os
from pathlib import Path
import re
from pilot import Client, filing_index
from point_in_time import select_annual

# Issuer 10-Ks, not acquirers' merger announcements. Keep scope explicit.
ISSUERS = [
    ('HES', '0000004447', '0001628280-25-008716', '2024-12-31', 'hes-20241231.htm'),
    ('MRO', '0000101778', '0000101778-24-000023', '2023-12-31', 'mro-20231231.htm'),
    ('PXD', '0001038357', '0001038357-24-000020', '2023-12-31', 'pxd-20231231.htm'),
    ('ANSS', '0001013462', '0001013462-25-000009', '2024-12-31', 'anss-20241231.htm'),
]


def collect_issuer(client, issuer):
    symbol, cik, accession, report_date, document = issuer
    submissions = client.get('/submissions/CIK' + cik + '.json')
    facts = client.get('/api/xbrl/companyfacts/CIK' + cik + '.json')
    if int(submissions['cik']) != int(cik) or int(facts['cik']) != int(cik):
        raise ValueError('CIK mismatch')
    blocks = [submissions['filings']['recent']]
    archives = submissions['filings'].get('files', [])
    if len(archives) > 30:
        raise ValueError('Archive bound exceeded')
    for archive in archives:
        name = archive['name']
        if not re.fullmatch(r'CIK' + cik + r'-submissions-\d+\.json', name):
            raise ValueError('Unexpected submissions archive')
        blocks.append(client.get('/submissions/' + name))
    filings = filing_index(blocks)
    evidence = filings.get(accession, {})
    if (evidence.get('form') != '10-K' or evidence.get('reportDate') != report_date
            or evidence.get('primaryDocument') != document):
        raise ValueError('Reviewed issuer filing not confirmed')
    # Empty current ticker lists are normal for exited issuers. CIK and the
    # reviewed historical filing above are mandatory instead.
    snapshots = []
    for year in range(2020, 2027):
        for month in (1, 4, 7, 10):
            cutoff = dt.date(year, month, 12)
            if dt.date(2020, 10, 12) <= cutoff <= dt.date(2026, 10, 12):
                annual = select_annual(facts, filings, cutoff)['latest_annual']
                age = (cutoff - dt.date.fromisoformat(annual['end'])).days if annual else None
                snapshots.append({'cutoff_exclusive': cutoff.isoformat(), 'annual': annual,
                                  'annual_age_days': age,
                                  'status': 'missing' if annual is None else
                                  'ambiguous' if annual['status'] != 'selected' else
                                  'stale' if age > 550 else 'available'})
    return {'symbol': symbol, 'cik': cik, 'name': submissions.get('name'),
            'status': 'archived', 'filings_count': len(filings),
            'identity_source': 'https://www.sec.gov/Archives/edgar/data/' + str(int(cik))
                + '/' + accession.replace('-', '') + '/' + document,
            'snapshots': snapshots}


def run(output, user_agent, client_factory=Client):
    output.mkdir(parents=True, exist_ok=True)
    report = {'schema': 1, 'production_eligible': False, 'complete': False,
              'cutoff_exclusive': '2026-10-12', 'companies': [], 'sources': [],
              'limitations': ['Four reviewed exited issuers only; not a representative universe.',
                 'Quarterly research snapshots, annual USD standard tags only; missing fields stay missing.',
                 'Membership, prices, settlement and financial statements still need joining.',
                 'Same-day filings excluded; amendments without CFO are not reconstructed.',
                 'No risk probability, calibration or production score change.']}
    def save():
        target = output / 'manifest.json'
        temporary = output / 'manifest.tmp'
        temporary.write_text(json.dumps(report, indent=2), encoding='utf-8')
        temporary.replace(target)
    save()
    if not re.search(r'[^\s@]+@[^\s@]+\.[^\s@]+', user_agent):
        report['error'] = 'SEC_USER_AGENT operator contact missing'
        save()
        return report
    client = client_factory(user_agent, output)
    for issuer in ISSUERS:
        try:
            result = collect_issuer(client, issuer)
        except Exception as exc:
            # Do not leak request headers/operator contact in an artifact or log.
            result = {'symbol': issuer[0], 'cik': issuer[1], 'status': 'failed',
                      'error_type': type(exc).__name__}
        report['companies'].append(result)
        report['sources'] = client.manifest
        save()
    report['complete'] = all(row['status'] == 'archived' for row in report['companies'])
    save()
    return report


if __name__ == '__main__':
    result = run(Path(os.environ.get('HISTORICAL_SEC_OUTPUT', 'historical-sec-output')),
                 os.environ.get('SEC_USER_AGENT', ''))
    print(json.dumps({'complete': result['complete'], 'companies': [
        {'symbol': r['symbol'], 'status': r['status']} for r in result['companies']]}))
    raise SystemExit(0 if result['complete'] else 1)
