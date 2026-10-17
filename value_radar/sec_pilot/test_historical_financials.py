import copy
import datetime as dt
import json
from pathlib import Path
import tempfile
import unittest
from collect_historical_financials import ISSUERS, collect_issuer, run


class FakeClient:
    def __init__(self, *args):
        self.manifest = []
        _, cik, accession, report, document = ISSUERS[0]
        self.submissions = {'cik': int(cik), 'tickers': [], 'name': 'Hess Corporation',
            'filings': {'recent': {'accessionNumber': [accession], 'form': ['10-K'],
                'reportDate': [report], 'primaryDocument': [document],
                'filingDate': ['2025-02-28'], 'acceptanceDateTime': ['2025-02-28T16:00:00']}, 'files': []}}
        self.facts = {'cik': int(cik), 'facts': {'us-gaap': {
            'NetCashProvidedByUsedInOperatingActivities': {'units': {'USD': [{
                'start': '2024-01-01', 'end': report, 'filed': '2025-02-28',
                'accn': accession, 'form': '10-K', 'val': 100}]}}}}}

    def get(self, path):
        return copy.deepcopy(self.facts if '/companyfacts/' in path else self.submissions)


class HistoricalFinancialsTests(unittest.TestCase):
    def test_delisted_ticker_not_required(self):
        result = collect_issuer(FakeClient(), ISSUERS[0])
        self.assertEqual(result['status'], 'archived')
        self.assertEqual(len(result['snapshots']), 25)

    def test_future_data_not_used_and_stale_flagged(self):
        rows = {r['cutoff_exclusive']: r for r in collect_issuer(FakeClient(), ISSUERS[0])['snapshots']}
        self.assertEqual(rows['2025-01-12']['status'], 'missing')
        self.assertEqual(rows['2025-04-12']['status'], 'available')
        self.assertEqual(rows['2026-10-12']['status'], 'stale')
        self.assertIsNone(rows['2025-04-12']['annual']['cfo_minus_capex'])

    def test_same_day_excluded(self):
        client = FakeClient()
        client.submissions['filings']['recent']['filingDate'] = ['2025-04-12']
        client.submissions['filings']['recent']['acceptanceDateTime'] = ['2025-04-12T16:00:00']
        client.facts['facts']['us-gaap']['NetCashProvidedByUsedInOperatingActivities']['units']['USD'][0]['filed'] = '2025-04-12'
        rows = {r['cutoff_exclusive']: r for r in collect_issuer(client, ISSUERS[0])['snapshots']}
        self.assertEqual(rows['2025-04-12']['status'], 'missing')
        self.assertEqual(rows['2025-07-12']['status'], 'available')

    def test_wrong_cik_rejected(self):
        client = FakeClient()
        client.facts['cik'] = 123
        with self.assertRaisesRegex(ValueError, 'CIK mismatch'):
            collect_issuer(client, ISSUERS[0])

    def test_unconfirmed_filing_rejected(self):
        client = FakeClient()
        client.submissions['filings']['recent']['primaryDocument'] = ['wrong.htm']
        with self.assertRaisesRegex(ValueError, 'not confirmed'):
            collect_issuer(client, ISSUERS[0])

    def test_archive_path_rejected(self):
        client = FakeClient()
        client.submissions['filings']['files'] = [{'name': '../other.json'}]
        with self.assertRaisesRegex(ValueError, 'Unexpected'):
            collect_issuer(client, ISSUERS[0])

    def test_partial_success_checkpointed(self):
        with tempfile.TemporaryDirectory() as folder:
            result = run(Path(folder), 'Test operator@example.com', FakeClient)
            self.assertFalse(result['complete'])
            self.assertEqual([r['status'] for r in result['companies']], ['archived', 'failed', 'failed', 'failed'])
            stored = json.loads((Path(folder) / 'manifest.json').read_text())
            self.assertEqual(stored, result)
            self.assertNotIn('operator@example.com', json.dumps(stored))

    def test_missing_contact_no_network(self):
        with tempfile.TemporaryDirectory() as folder:
            def forbidden(*args):
                self.fail('Network client must not be created')
            result = run(Path(folder), '', forbidden)
            self.assertFalse(result['complete'])


if __name__ == '__main__':
    unittest.main()
