"""Read-only, two-company SEC data audit. No risk scores or trading signals."""
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import time
import urllib.error
import urllib.request
from point_in_time import select_annual

COMPANIES = {'MSFT': '0000789019', 'ORCL': '0001341439'}
TAGS = ['NetCashProvidedByUsedInOperatingActivities', 'PaymentsToAcquirePropertyPlantAndEquipment',
        'CashAndCashEquivalentsAtCarryingValue', 'LongTermDebtCurrent', 'LongTermDebtNoncurrent',
        'OperatingIncomeLoss', 'DepreciationDepletionAndAmortization',
        'RevenueFromContractWithCustomerExcludingAssessedTax']

def day(value):
    try:
        return dt.date.fromisoformat(value)
    except (ValueError, TypeError):
        return None

def filing_index(blocks):
    out = {}
    for block in blocks:
        for i, accn in enumerate(block.get('accessionNumber', [])):
            row = {k: v[i] for k, v in block.items() if isinstance(v, list) and len(v) > i}
            if accn in out and out[accn] != row:
                raise ValueError('Conflicting submission metadata')
            out[accn] = row
    return out

def annual_pairs(facts, filings, cutoff):
    """Require same accession, unit and annual duration; future amendments stay excluded."""
    selected = {}
    problems = {'unmatched_filing': 0, 'conflicting_values': 0}
    for tag in TAGS[:2]:
        by_key = {}
        for row in facts.get('facts', {}).get('us-gaap', {}).get(tag, {}).get('units', {}).get('USD', []):
            start, end, filed = map(day, [row.get('start'), row.get('end'), row.get('filed')])
            if not start or not end or not filed or not 330 <= (end-start).days <= 380:
                continue
            if filed >= cutoff or end > cutoff or row.get('form') not in ('10-K', '10-K/A'):
                continue
            val = row.get('val')
            if isinstance(val, bool) or not isinstance(val, (float, int)) or not float('-inf') < val < float('inf'):
                continue
            accn = row.get('accn')
            submission = filings.get(accn)
            if not submission or submission.get('filingDate') != row['filed'] or submission.get('form') != row['form']:
                problems['unmatched_filing'] += 1
                continue
            accepted = submission.get('acceptanceDateTime')
            # A day-only cutoff is conservative: same-day filings are never used.
            if accepted and (not day(accepted[:10]) or day(accepted[:10]) >= cutoff):
                continue
            key = (row['start'], row['end'], accn, row['filed'])
            by_key.setdefault(key, set()).add(val)
        selected[tag] = {}
        for key, values in by_key.items():
            if len(values) != 1:
                problems['conflicting_values'] += 1
            else:
                selected[tag][key] = next(iter(values))
    pairs = []
    for key in sorted(selected[TAGS[0]].keys() & selected[TAGS[1]].keys()):
        cfo, capex = selected[TAGS[0]][key], selected[TAGS[1]][key]
        if capex < 0:
            continue
        start, end, accn, filed = key
        pairs.append(dict(start=start, end=end, accession=accn, filed=filed,
                          accepted=filings[accn].get('acceptanceDateTime'), currency='USD',
                          operating_cashflow=cfo, capex=capex, cfo_minus_capex=cfo-capex))
    return {'cutoff_exclusive': cutoff.isoformat(), 'pairs': pairs, 'issues': problems}

class Client:
    def __init__(self, user_agent, output):
        self.user_agent, self.output, self.manifest = user_agent, output, []

    def get(self, path):
        if not re.fullmatch(r'/[A-Za-z0-9/_.-]+\.json', path) or '..' in path:
            raise ValueError('Invalid SEC path')
        url = 'https://data.sec.gov' + path
        for attempt in range(3):
            time.sleep(.6)
            try:
                req = urllib.request.Request(url, headers={'User-Agent': self.user_agent, 'Accept': 'application/json'})
                with urllib.request.urlopen(req, timeout=20) as response:
                    if response.url != url:
                        raise ValueError('Unexpected redirect')
                    raw = response.read(50_000_001)
                if len(raw) > 50_000_000:
                    raise ValueError('Response too large')
                data = json.loads(raw)
                filename = path.replace('/', '_').lstrip('_')
                (self.output / filename).write_bytes(raw)
                self.manifest.append(dict(url=url, file=filename, retrieved_at=dt.datetime.now(dt.timezone.utc).isoformat(), sha256=hashlib.sha256(raw).hexdigest()))
                return data
            except urllib.error.HTTPError as exc:
                if exc.code not in (429, 500, 502, 503, 504) or attempt == 2:
                    raise RuntimeError('SEC HTTP ' + str(exc.code)) from None
                time.sleep(30)
        raise RuntimeError('SEC unavailable')

def run():
    output = Path(os.environ.get('SEC_PILOT_OUTPUT', 'sec-pilot-output'))
    output.mkdir(parents=True, exist_ok=True)
    ua = os.environ.get('SEC_USER_AGENT', '')
    report = {'schema': 1, 'generated_at': dt.datetime.now(dt.timezone.utc).isoformat(), 'status': 'audit_only',
              'companies': {}, 'limitations': ['No financial risk backtest or calibration.',
              'CFO minus capex is not ROIC FCFF. EBITDA and debt definitions require separate reconciliation.',
              'Only standard USD annual CFO/capex pairs audited; custom tags and interim TTM not reconstructed.',
              'All same-day filings excluded. Earlier earnings releases not reconstructed.']}
    client = Client(ua, output)
    if not re.search(r'[^\s@]+@[^\s@]+\.[^\s@]+', ua):
        report['status'] = 'configuration_missing'
        report['error'] = 'Set SEC_USER_AGENT to application name and real contact email.'
    else:
        for symbol, cik in COMPANIES.items():
            try:
                submissions = client.get('/submissions/CIK'+cik+'.json')
                facts = client.get('/api/xbrl/companyfacts/CIK'+cik+'.json')
                if int(submissions['cik']) != int(cik) or int(facts['cik']) != int(cik):
                    raise ValueError('CIK mismatch')
                blocks = [submissions['filings']['recent']]
                archives = submissions['filings'].get('files', [])
                if len(archives) > 30:
                    raise ValueError('Archive bound exceeded')
                for archive in archives:
                    name = archive['name']
                    if not re.fullmatch(r'CIK'+cik+r'-submissions-\d+\.json', name):
                        raise ValueError('Unexpected archive name')
                    blocks.append(client.get('/submissions/'+name))
                index = filing_index(blocks)
                coverage = {tag: len(facts.get('facts', {}).get('us-gaap', {}).get(tag, {}).get('units', {}).get('USD', [])) for tag in TAGS}
                cutoffs = [dt.date(year, 12, 31) for year in range(2020, dt.date.today().year)] + [dt.date.today()]
                audits = [annual_pairs(facts, index, cutoff) for cutoff in cutoffs]
                selection = [select_annual(facts, index, cutoff) for cutoff in cutoffs]
                report['companies'][symbol] = {'cik': cik, 'status': 'audited', 'submissions': len(index), 'tag_rows': coverage, 'annual_cashflow_checks': audits, 'point_in_time': selection}
            except Exception as exc:
                # Do not emit response bodies, request headers or contact details.
                message = str(exc) if isinstance(exc, (ValueError, RuntimeError)) else type(exc).__name__
                report['companies'][symbol] = {'cik': cik, 'status': 'failed', 'error': message}
    report['downloads'] = client.manifest
    (output/'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    lines = ['# SEC-Pilot', '', 'Datenprüfung, kein validierter Finanzscore.', '']
    for symbol, row in report['companies'].items():
        lines.append(f"- {symbol}: {row['status']}" + (f"; {row['error']}" if 'error' in row else f"; {len(row['annual_cashflow_checks'][-1]['pairs'])} datierte jährliche CFO/Capex-Paare (einschließlich Mehrfachmeldungen)."))
    if report.get('error'):
        lines.append(report['error'])
    lines += ['', 'Kennzahlendefinitionen und Versionszuordnung sind vor einer historischen Scoreprüfung weiter zu prüfen.']
    (output/'report.md').write_text('\n'.join(lines), encoding='utf-8')
    return 0 if len(report['companies']) == 2 and all(r['status'] == 'audited' for r in report['companies'].values()) else 1

if __name__ == '__main__':
    raise SystemExit(run())
