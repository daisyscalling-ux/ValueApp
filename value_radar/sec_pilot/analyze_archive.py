import datetime as dt
import hashlib
import json
from pathlib import Path
import sys
import zipfile
from pilot import filing_index
from point_in_time import select_annual

def analyze(archive, destination):
    with zipfile.ZipFile(archive) as z:
        original = json.loads(z.read('report.json'))
        for entry in original['downloads']:
            if hashlib.sha256(z.read(entry['file'])).hexdigest() != entry['sha256']:
                raise ValueError('Checksum mismatch')
        out = {'source_generated_at': original['generated_at'], 'schema': 1, 'companies': {}}
        for symbol, company in original['companies'].items():
            cik = company['cik']
            subs = json.loads(z.read('submissions_CIK'+cik+'.json'))
            blocks = [subs['filings']['recent']]
            blocks += [json.loads(z.read('submissions_'+a['name'])) for a in subs['filings']['files']]
            facts = json.loads(z.read('api_xbrl_companyfacts_CIK'+cik+'.json'))
            if int(facts['cik']) != int(cik) or int(subs['cik']) != int(cik):
                raise ValueError('CIK mismatch')
            index = filing_index(blocks)
            cutoffs = [dt.date.fromisoformat(a['cutoff_exclusive']) for a in company['annual_cashflow_checks']]
            out['companies'][symbol] = [select_annual(facts, index, cutoff) for cutoff in cutoffs]
        Path(destination).write_text(json.dumps(out, indent=2), encoding='utf-8')
        return out

if __name__ == '__main__':
    result = analyze(sys.argv[1], sys.argv[2])
    for symbol, rows in result['companies'].items():
        latest = rows[-1]['latest_annual'] or {}
        print(symbol, json.dumps({k: latest.get(k) for k in ['end', 'filed', 'accession', 'cfo_minus_capex', 'debt', 'debt_method', 'net_debt', 'operating_income_plus_da_proxy']}))
