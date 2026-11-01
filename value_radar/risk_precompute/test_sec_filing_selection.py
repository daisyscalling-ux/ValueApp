import copy
import unittest
from collections import Counter
from sec_cashflow_history import normalize, run, COLLECTION_POLICY
from test_sec_currency_concordance import translated, coverage
from test_sec_cashflow_history import ROW, NOW


def newer(data, currencies=('TWD',), bad=False):
    for tag, info in data['facts']['us-gaap'].items():
        for currency in currencies:
            fact = copy.deepcopy(info['units'][currency][-1])
            fact.update(filed='2026-03-01', accn='0000000001-26-000002')
            if bad and currency == 'USD' and tag == 'Assets':
                fact['val'] *= 2
            info['units'][currency].append(fact)


class FilingSelection(unittest.TestCase):
    def test_old_translation_does_not_block_new_complete_statement(self):
        data = translated()
        newer(data)
        audit = Counter()
        rows = normalize(data, 1, NOW, audit)
        latest = [p for p in rows if p['end'] == '2025-12-31']
        self.assertEqual(len(latest), 1)
        self.assertEqual(latest[0]['currency'], 'TWD')
        self.assertEqual(latest[0]['filed'], '2026-03-01')
        self.assertNotIn('currencyCheck', latest[0])
        self.assertEqual(audit['older_filing_observations_superseded'], 2)

    def test_new_dual_statement_keeps_concordant_pair(self):
        data = translated()
        newer(data, ('TWD', 'USD'))
        rows = normalize(data, 1, NOW)
        latest = [p for p in rows if p['end'] == '2025-12-31']
        self.assertEqual(len(latest), 2)
        self.assertEqual({p['filed'] for p in latest}, {'2026-03-01'})
        self.assertTrue(all('currencyCheck' in p for p in latest))

    def test_new_conflict_does_not_fall_back_to_old_agreement(self):
        data = translated()
        newer(data, ('TWD', 'USD'), bad=True)
        self.assertFalse(any(p['end'] == '2025-12-31' for p in normalize(data, 1, NOW)))

    def test_same_day_conflicting_accessions_block_period(self):
        data = translated()
        for tag, info in data['facts']['us-gaap'].items():
            fact = copy.deepcopy(info['units']['TWD'][-1])
            fact['accn'] = '0000000001-26-000002'
            if tag == 'Assets':fact['val'] *= 2
            info['units']['TWD'].append(fact)
        self.assertFalse(any(p['end'] == '2025-12-31' for p in normalize(data, 1, NOW)))

    def test_partial_success_retries_once_under_new_policy(self):
        universe = {'kandidaten': [ROW]}
        state = run(universe, coverage(), {}, {'NASDAQ:EX': '1'}, lambda *a: translated(), NOW)
        attempt = state['attempts']['NASDAQ:EX']
        attempt.update(policy='old', normalization={'currency_conflict_periods': 7})
        calls = []
        def fetch(*args):
            calls.append(1)
            return translated()
        updated = run(universe, coverage(), state, {'NASDAQ:EX': '1'}, fetch, NOW)
        self.assertEqual(calls, [1])
        self.assertEqual(updated['attempts']['NASDAQ:EX']['policy'], COLLECTION_POLICY)
        run(universe, coverage(), updated, {'NASDAQ:EX': '1'}, fetch, NOW)
        self.assertEqual(calls, [1])


if __name__ == '__main__':unittest.main()
