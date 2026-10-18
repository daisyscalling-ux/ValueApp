import datetime as dt
import unittest
from point_in_time import select_annual, field
from balance_evidence import reviewed_balance


class BalanceEvidenceTests(unittest.TestCase):
    def test_earlier_ansys_debt_has_separate_filing_evidence(self):
        selected = dict(start='2022-01-01', end='2022-12-31',
                        accession='0001013462-23-000013', filed='2023-02-22', form='10-K')
        row = dict(end=selected['end'], accn=selected['accession'], filed=selected['filed'],
                   form='10-K', val=753574000)
        facts = {'cik': 1013462, 'facts': {'us-gaap': {
            'LongTermDebtNoncurrent': {'units': {'USD': [row]}}}}}
        result = reviewed_balance(facts, selected, 'debt', field)
        self.assertEqual(result['value'], 753574000)
        self.assertIn('000101346223000013', result['source'])
        row['accn'] = '0001013462-24-000007'
        self.assertIsNone(reviewed_balance(facts, selected, 'debt', field)['value'])

    def fixture(self):
        s = dict(start='2023-01-01', end='2023-12-31', accession='0000101778-24-000023',
                 filed='2024-02-22', form='10-K')
        def row(v, duration=False):
            r = dict(end=s['end'], accn=s['accession'], filed=s['filed'], form=s['form'], val=v)
            if duration: r['start'] = s['start']
            return {'units': {'USD': [r]}}
        f = {'cik': 101778, 'facts': {'us-gaap': {
            'LongTermDebt': row(4978000000), 'CommercialPaper': row(450000000),
            'CashAndCashEquivalentsAtCarryingValue': row(155000000),
            'NetCashProvidedByUsedInOperatingActivities': row(1000000000, True)}}}
        filings = {s['accession']: {'form': '10-K', 'filingDate': s['filed']}}
        return f, s, filings

    def test_commercial_paper_added_to_carrying_debt(self):
        f, s, filings = self.fixture()
        r = select_annual(f, filings, dt.date(2024, 4, 12))['latest_annual']
        self.assertEqual(r['debt'], 5428000000)
        self.assertEqual(r['net_debt'], 5273000000)

    def test_missing_short_term_component_not_zero(self):
        f, s, filings = self.fixture()
        del f['facts']['us-gaap']['CommercialPaper']
        self.assertIsNone(select_annual(f, filings, dt.date(2024, 4, 12))['latest_annual']['debt'])

    def test_conflicting_standard_not_overwritten(self):
        f, s, filings = self.fixture()
        base = f['facts']['us-gaap']['LongTermDebt']['units']['USD'][0]
        f['facts']['us-gaap']['DebtLongtermAndShorttermCombinedAmount'] = {'units': {'USD': [base, dict(base, val=1)]}}
        self.assertIsNone(select_annual(f, filings, dt.date(2024, 4, 12))['latest_annual']['debt'])

    def test_wrong_issuer_and_filing_not_used(self):
        f, s, _ = self.fixture()
        self.assertIsNone(reviewed_balance(dict(f, cik=1), s, 'debt', field))
        self.assertIsNone(reviewed_balance(f, dict(s, accession='other'), 'debt', field))

    def test_wrong_currency_not_used(self):
        f, s, _ = self.fixture()
        unit = f['facts']['us-gaap']['CommercialPaper']['units']
        unit['EUR'] = unit.pop('USD')
        self.assertEqual(reviewed_balance(f, s, 'debt', field)['status'], 'evidence_mismatch')

    def test_future_information_excluded(self):
        f, s, filings = self.fixture()
        self.assertIsNone(select_annual(f, filings, dt.date(2024, 2, 22))['latest_annual'])

    def test_reviewed_cash_is_not_short_term_investments(self):
        f, s, filings = self.fixture()
        s.update(accession='0001013462-25-000009', start='2024-01-01', end='2024-12-31', filed='2025-02-19')
        f = {'cik': 1013462, 'facts': {'us-gaap': {}}}
        for tag, value in [('LongTermDebtNoncurrent', 754208000),
                           ('CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents', 1446743000)]:
            f['facts']['us-gaap'][tag] = {'units': {'USD': [dict(end=s['end'], accn=s['accession'],
                filed=s['filed'], form='10-K', val=value)]}}
        self.assertEqual(reviewed_balance(f, s, 'cash', field)['value'], 1446743000)
        row = f['facts']['us-gaap']['CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents']['units']['USD'][0]
        row['val'] = 1497517000  # Cash plus investments must not pass the cash-only evidence.
        self.assertIsNone(reviewed_balance(f, s, 'cash', field)['value'])


if __name__ == '__main__':
    unittest.main()
