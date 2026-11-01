import copy
import datetime as dt
import unittest
from collections import Counter
from sec_cashflow_history import normalize, diagnostics, run, balances, COLLECTION_POLICY
from test_sec_cashflow_history import fixture, ROW, NOW
from financial_history import build


def translated():
    data = fixture()
    for tag in data['facts']['us-gaap'].values():
        tag['units']['TWD'] = copy.deepcopy(tag['units']['USD'])
        for fact in tag['units']['TWD']:
            fact['val'] *= 31.37
    return data


def coverage():
    return {'schema': 1, 'generatedAt': NOW.isoformat(), 'stocks': [
        {'symbol': ROW['listing_symbol'], 'domains': {
            'identity': {'state': 'available'},
            'balance': {'profile': 'corporate', 'metrics': {}}}}]}


class CurrencyConcordance(unittest.TestCase):
    def test_translated_series_retained_without_converting_values(self):
        audit = Counter()
        periods = normalize(translated(), 1, NOW, audit)
        self.assertEqual(len(periods), 12)
        self.assertEqual(audit['currency_concordant_periods'], 6)
        self.assertEqual({p['currency'] for p in periods}, {'TWD', 'USD'})
        for p in periods:
            self.assertAlmostEqual(p['value'], .15)
            self.assertEqual(p['assets'], 3137 if p['currency'] == 'TWD' else 100)
            self.assertEqual(p['currencyCheck']['currencies'], ['TWD', 'USD'])

    def test_component_errors_cannot_cancel_out(self):
        data = translated()
        for name in ('NetCashProvidedByUsedInOperatingActivities', 'PaymentsToAcquirePropertyPlantAndEquipment'):
            for fact in data['facts']['us-gaap'][name]['units']['USD']:
                fact['val'] += 2
        audit = Counter()
        self.assertEqual(normalize(data, 1, NOW, audit), [])
        self.assertEqual(audit['currency_conflict_periods'], 6)
        self.assertEqual(diagnostics(data, audit)['reason'], 'multiple_currency_conflict')

    def test_other_filing_or_duration_never_corroborates(self):
        for patch, expected in (({'accn': '0000000001-26-000002'}, 10), ({'filed': '2026-03-01'}, 11)):
            data = translated()
            for tag in data['facts']['us-gaap'].values():
                tag['units']['TWD'][-1].update(patch)
            self.assertEqual(len(normalize(data, 1, NOW)), expected)
        data = translated()
        for name in ('NetCashProvidedByUsedInOperatingActivities', 'PaymentsToAcquirePropertyPlantAndEquipment'):
            data['facts']['us-gaap'][name]['units']['TWD'][-1]['start'] = '2025-01-02'
        self.assertEqual(len(normalize(data, 1, NOW)), 10)

    def test_small_rounding_allowed_but_material_disagreement_blocked(self):
        for delta, expected in ((.000001, 12), (.01, 10)):
            data = translated()
            data['facts']['us-gaap']['NetCashProvidedByUsedInOperatingActivities']['units']['USD'][-1]['val'] += delta
            self.assertEqual(len(normalize(data, 1, NOW)), expected)

    def test_incomplete_translation_does_not_fill_native_fields(self):
        data = translated()
        del data['facts']['us-gaap']['Assets']['units']['TWD']
        periods = normalize(data, 1, NOW)
        self.assertEqual(len(periods), 6)
        self.assertEqual({p['currency'] for p in periods}, {'USD'})

    def test_history_has_two_six_year_series_not_one_twelve_year_series(self):
        universe = {'kandidaten': [ROW]}
        cov = coverage()
        state = run(universe, cov, {}, {'NASDAQ:EX': '1'}, lambda *args: translated(), NOW)
        backfill = {'schema': 1, 'method': 'roic-history-balances-v1', 'generatedAt': NOW.isoformat(),
                    'stocks': balances(state, universe, NOW)}
        archive, result = build(cov, universe, {}, NOW, backfill)
        self.assertEqual(len(archive['series']), 2)
        self.assertEqual({s['currency'] for s in archive['series'].values()}, {'TWD', 'USD'})
        self.assertTrue(all(len(s['periods']) == 6 for s in archive['series'].values()))
        self.assertEqual(cov['stocks'][0]['domains']['balance']['metrics'], {})
        self.assertFalse(archive['pointInTimeUsable'])

    def test_failed_old_policy_retried_and_success_cache_preserved(self):
        universe = {'kandidaten': [ROW]}
        state = run(universe, coverage(), {}, {'NASDAQ:EX': '1'}, lambda *args: translated(), NOW)
        state['attempts']['NASDAQ:EX']['policy'] = 'old'
        state['attempts']['NASDAQ:EX']['error'] = 'matching_annual_filing_missing'
        retained = copy.deepcopy(state)
        self.assertEqual(run(universe, coverage(), retained, {'NASDAQ:EX': '1'}, lambda *args: self.fail('cached'), NOW)['report']['cached'], 1)
        state['stocks'] = {}
        updated = run(universe, coverage(), state, {'NASDAQ:EX': '1'}, lambda *args: translated(), NOW)
        self.assertEqual(updated['report']['updated'], 1)
        self.assertEqual(updated['attempts']['NASDAQ:EX']['policy'], COLLECTION_POLICY)


class StageDiagnostics(unittest.TestCase):
    def test_rejection_reasons_identify_alignment_duration_and_sign(self):
        for patch, key in [({'start': '2025-04-01'}, 'fact_nonannual_duration'),
                           ({'accn': '0000000001-26-000002'}, 'group_missing_same_filing_fields'),
                           ({'val': -5}, 'group_negative_investment'),
                           ({'val': float('nan')}, 'fact_invalid_value'),
                           ({'form': '10-Q'}, 'fact_nonannual_form')]:
            data = fixture()
            data['facts']['us-gaap']['PaymentsToAcquirePropertyPlantAndEquipment']['units']['USD'][-1].update(patch)
            audit = Counter()
            self.assertEqual(len(normalize(data, 1, NOW, audit)), 5)
            self.assertGreater(audit[key], 0)
            self.assertGreater(diagnostics(data, audit)['stageCounts'][key], 0)

    def test_balance_sheet_duration_not_accepted_as_instant(self):
        data = fixture()
        data['facts']['us-gaap']['Assets']['units']['USD'][-1]['start'] = '2025-01-01'
        audit = Counter()
        self.assertEqual(len(normalize(data, 1, NOW, audit)), 5)
        self.assertEqual(audit['fact_assets_not_instant'], 1)

    def test_ifrs_not_misreported_as_missing_us_gaap(self):
        data = {'facts': {'ifrs-full': {'Assets': {'units': {'EUR': [{'val': 1}]}}}}}
        self.assertEqual(diagnostics(data)['reason'], 'cash_ppe_concept_missing')
        variants = diagnostics(data)['variants']
        self.assertEqual(variants[-1]['currenciesByField']['assets'], ['EUR'])


if __name__ == '__main__':
    unittest.main()
