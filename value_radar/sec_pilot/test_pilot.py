import datetime as dt
import unittest
from pilot import annual_pairs, filing_index, TAGS

class AuditTests(unittest.TestCase):
    def fixture(self):
        rows = [dict(start='2022-01-01', end='2022-12-31', accn='first', filed='2023-02-01', form='10-K', val=100),
                dict(start='2022-01-01', end='2022-12-31', accn='amended', filed='2024-02-01', form='10-K/A', val=120)]
        facts = {'facts': {'us-gaap': {TAGS[0]: {'units': {'USD': rows}}, TAGS[1]: {'units': {'USD': [dict(r, val=20) for r in rows]}}}}}
        filings = {r['accn']: {'filingDate': r['filed'], 'form': r['form']} for r in rows}
        return facts, filings

    def test_later_amendment_not_used_early(self):
        facts, filings = self.fixture()
        early = annual_pairs(facts, filings, dt.date(2023, 12, 31))
        self.assertEqual([r['cfo_minus_capex'] for r in early['pairs']], [80])
        self.assertEqual(len(annual_pairs(facts, filings, dt.date(2024, 12, 31))['pairs']), 2)
        self.assertEqual(annual_pairs(facts, filings, dt.date(2023, 2, 1))['pairs'], [])

    def test_missing_metadata_and_conflicts_are_excluded(self):
        facts, filings = self.fixture()
        self.assertEqual(annual_pairs(facts, {}, dt.date(2023, 12, 31))['pairs'], [])
        rows = facts['facts']['us-gaap'][TAGS[0]]['units']['USD']
        rows.append(dict(rows[0], val=999))
        r = annual_pairs(facts, filings, dt.date(2023, 12, 31))
        self.assertEqual(r['pairs'], [])
        self.assertEqual(r['issues']['conflicting_values'], 1)

    def test_no_quarter_or_cross_filing_pair(self):
        facts, filings = self.fixture()
        facts['facts']['us-gaap'][TAGS[1]]['units']['USD'][0]['start'] = '2022-10-01'
        self.assertEqual(annual_pairs(facts, filings, dt.date(2023, 12, 31))['pairs'], [])

    def test_filing_conflict_is_not_silently_overwritten(self):
        with self.assertRaises(ValueError):
            filing_index([{'accessionNumber': ['a'], 'filingDate': ['2023-01-01']}, {'accessionNumber': ['a'], 'filingDate': ['2024-01-01']}])

if __name__ == '__main__':
    unittest.main()
