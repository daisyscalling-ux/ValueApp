import copy
import datetime as dt
import unittest
from capex_evidence import reviewed_capex
from point_in_time import field, select_annual


class CapexEvidenceTests(unittest.TestCase):
    def fixture(self):
        selected = dict(start='2024-01-01', end='2024-12-31', accession='0001013462-25-000009',
                        filed='2025-02-19', form='10-K')
        row = dict(start=selected['start'], end=selected['end'], accn=selected['accession'],
                   filed=selected['filed'], form='10-K', val=44045000)
        facts = {'cik': 1013462, 'facts': {'us-gaap': {
            'PaymentsToAcquireProductiveAssets': {'units': {'USD': [row]}},
            'NetCashProvidedByUsedInOperatingActivities': {'units': {'USD': [dict(row, val=795740000)]}}}}}
        filings = {selected['accession']: dict(filingDate=selected['filed'], form='10-K',
                    acceptanceDateTime='2025-02-19T16:34:10')}
        return facts, selected, filings

    def test_exact_filing_reconciles(self):
        facts, selected, filings = self.fixture()
        r = select_annual(facts, filings, dt.date(2025, 4, 12))['latest_annual']
        self.assertEqual(r['cfo_minus_capex'], 751695000)
        self.assertEqual(r['capex_method'], 'reviewed_filing_cashflow_components')
        self.assertEqual(r['fields']['capex']['status'], 'missing')

    def test_future_filing_still_excluded(self):
        facts, selected, filings = self.fixture()
        self.assertIsNone(select_annual(facts, filings, dt.date(2025, 2, 19))['latest_annual'])

    def test_no_transfer_to_other_issuer_or_accession(self):
        facts, selected, _ = self.fixture()
        for f, s in [(dict(facts, cik=123), selected), (facts, dict(selected, accession='other'))]:
            self.assertIsNone(reviewed_capex(f, s, field))

    def test_different_value_and_unit_blocked(self):
        facts, selected, _ = self.fixture()
        tag = facts['facts']['us-gaap']['PaymentsToAcquireProductiveAssets']
        tag['units']['USD'][0]['val'] = 999
        self.assertEqual(reviewed_capex(facts, selected, field)['status'], 'evidence_mismatch')
        tag['units']['EUR'] = tag['units'].pop('USD')
        self.assertIsNone(reviewed_capex(facts, selected, field)['value'])

    def test_no_partial_sum(self):
        facts, selected, _ = self.fixture()
        facts['cik'] = 4447
        selected['accession'] = '0001628280-25-008716'
        row = dict(start=selected['start'], end=selected['end'], filed=selected['filed'],
                   accn=selected['accession'], form='10-K', val=4640000000)
        facts['facts']['us-gaap'] = {'PaymentsToAcquireOilAndGasPropertyAndEquipment': {'units': {'USD': [row]}}}
        self.assertIsNone(reviewed_capex(facts, selected, field)['value'])
        facts['facts']['us-gaap']['PaymentsToAcquireMachineryAndEquipment'] = {'units': {'USD': [dict(row, val=306000000)]}}
        self.assertEqual(reviewed_capex(facts, selected, field)['value'], 4946000000)

    def test_standard_conflict_not_bypassed(self):
        facts, selected, filings = self.fixture()
        row = facts['facts']['us-gaap']['PaymentsToAcquireProductiveAssets']['units']['USD'][0]
        facts['facts']['us-gaap']['PaymentsToAcquirePropertyPlantAndEquipment'] = {'units': {'USD': [row, dict(row, val=1)]}}
        self.assertIsNone(select_annual(facts, filings, dt.date(2025, 4, 12))['latest_annual']['cfo_minus_capex'])


if __name__ == '__main__':
    unittest.main()
