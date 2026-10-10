import datetime as dt
import unittest
import test_pilot
from point_in_time import select_annual

class SelectionTests(unittest.TestCase):
    def test_latest_known_version_once_per_period(self):
        facts, filings = test_pilot.AuditTests().fixture()
        for cutoff, expected in [('2023-12-31', 80), ('2024-12-31', 100)]:
            r = select_annual(facts, filings, dt.date.fromisoformat(cutoff))
            self.assertEqual(len(r['periods']), 1)
            self.assertEqual(r['latest_annual']['cfo_minus_capex'], expected)

    def test_new_conflict_never_restores_older_complete_value(self):
        facts, filings = test_pilot.AuditTests().fixture()
        rows = facts['facts']['us-gaap']['NetCashProvidedByUsedInOperatingActivities']['units']['USD']
        rows.append(dict(rows[-1], val=999))
        r = select_annual(facts, filings, dt.date(2024, 12, 31))['latest_annual']
        self.assertEqual(r['accession'], 'amended')
        self.assertIsNone(r['cfo_minus_capex'])

    def test_fields_do_not_cross_filing_and_missing_debt_is_not_zero(self):
        facts, filings = test_pilot.AuditTests().fixture()
        facts['facts']['us-gaap']['DebtLongtermAndShorttermCombinedAmount'] = {'units': {'USD': [dict(end='2022-12-31', accn='first', filed='2023-02-01', form='10-K', val=500)]}}
        early = select_annual(facts, filings, dt.date(2023, 12, 31))['latest_annual']
        late = select_annual(facts, filings, dt.date(2024, 12, 31))['latest_annual']
        self.assertEqual(early['debt'], 500)
        self.assertIsNone(late['debt'])
        self.assertIsNone(late['operating_income_plus_da_proxy'])

    def test_same_day_ambiguity_is_explicit(self):
        facts, filings = test_pilot.AuditTests().fixture()
        for block in facts['facts']['us-gaap'].values():
            block['units']['USD'][-1]['filed'] = '2023-02-01'
        filings['amended']['filingDate'] = '2023-02-01'
        self.assertEqual(select_annual(facts, filings, dt.date(2023, 12, 31))['latest_annual']['status'], 'ambiguous_filing')

if __name__ == '__main__':
    unittest.main()
