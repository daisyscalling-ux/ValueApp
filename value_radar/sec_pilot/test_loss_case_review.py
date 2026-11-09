import json
from pathlib import Path
import tempfile
import unittest

from loss_case_review import CANDIDATES, case_status, review, sec_filings, sec_identity, series_check

SUBMISSIONS = {
    'name': 'SVB FINANCIAL GROUP', 'formerNames': [{'name': 'SILICON VALLEY BANCSHARES'}],
    'tickers': ['SIVBQ'], 'exchanges': ['OTC'],
    'filings': {'recent': {
        'form': ['8-K', '8-K', '25-NSE', '10-Q'],
        'filingDate': ['2023-03-17', '2023-01-19', '2023-03-28', '2022-11-07'],
        'accessionNumber': ['0000719739-23-000012', '0000719739-23-000002', '0000876661-23-000301', '0000719739-22-000099'],
        'primaryDocument': ['a.htm', 'b.htm', 'c.xml', 'd.htm'],
        'items': ['1.03,8.01', '2.02,9.01', '', '']}}}


class LossCaseReviewTests(unittest.TestCase):
    def test_candidate_file_is_consistent(self):
        data = json.loads(CANDIDATES.read_text(encoding='utf8'))
        ids = [c['identity'] for c in data['cases']]
        self.assertEqual(len(ids), len(set(ids)))
        for c in data['cases']:
            self.assertIn(c['group'], {'failure', 'index_drop'})
            self.assertTrue(c['yahoo_candidates'])
            self.assertTrue(c['cik'] is None or (len(c['cik']) == 10 and c['cik'].isdigit()))

    def test_only_status_filings_are_kept(self):
        rows = sec_filings(SUBMISSIONS, '0000719739')
        self.assertEqual([r['form'] for r in rows], ['8-K', '25-NSE'])
        self.assertEqual(rows[0]['meaning'], 'bankruptcy_or_receivership')
        self.assertIn('/719739/000071973923000012/a.htm', rows[0]['url'])

    def test_former_names_count_for_identity(self):
        self.assertTrue(sec_identity(SUBMISSIONS, 'Silicon Valley')['sec_name_match'])
        self.assertFalse(sec_identity(SUBMISSIONS, 'Signature')['sec_name_match'])

    def meta(self, name='First Republic Bank'):
        return dict(symbol='FRCB', longName=name, instrumentType='EQUITY', currency='USD', exchangeName='PNK')

    def test_series_with_gap_and_post_exit_rows(self):
        rows = [('2020-10-09', 100.0), ('2020-10-12', 101.0), ('2023-05-01', 3.0), ('2023-05-20', 0.5)]
        r = series_check(rows, self.meta(), 'First Republic', '2020-10-12', '2023-05-04')
        self.assertTrue(r['basic_checks_passed'])
        self.assertEqual(r['rows_before_exit'], 2)
        self.assertEqual(r['rows_after_exit'], 1)
        self.assertEqual(r['gaps_over_7_days'], 2)
        self.assertEqual(r['largest_gap'], '2020-10-12..2023-05-01')

    def test_reused_ticker_name_is_rejected(self):
        rows = [('2020-10-01', 10.0), ('2021-01-04', 11.0)]
        r = series_check(rows, self.meta('Strive, Inc.'), 'DISH', '2020-10-12', '2023-06-20')
        self.assertFalse(r['name_match'])
        self.assertFalse(r['basic_checks_passed'])

    def test_late_starting_series_does_not_pass(self):
        r = series_check([('2024-08-15', 1.0)], self.meta('Signature Bank'), 'Signature', '2020-10-12', '2023-03-15')
        self.assertFalse(r['basic_checks_passed'])

    def test_status_never_admits_and_flags_sec_mismatch(self):
        good = dict(basic_checks_passed=True, gaps_over_7_days=0)
        self.assertEqual(case_status({'cik': '1'}, None, [good]), 'sec_unavailable_retry')
        self.assertEqual(case_status({'cik': '1'}, {'sec_name_match': False}, [good]), 'sec_identity_mismatch_review_cik')
        self.assertEqual(case_status({'cik': None}, None, [good]), 'series_found_review_required')
        self.assertEqual(case_status({'cik': None}, None, [dict(good, gaps_over_7_days=1)]), 'series_found_with_gaps_review_required')
        self.assertEqual(case_status({'cik': None}, None, []), 'no_matching_series')

    def test_review_records_failures_without_network(self):
        candidates = dict(decision_start='2020-10-12', cases=[
            dict(identity='SIVB', group='failure', last_index_exit='2023-03-15', name_pattern='SVB', cik='0000719739',
                 yahoo_candidates=['SIVB', 'SIVBQ'])])
        def yahoo(symbol, start, raw):
            if symbol == 'SIVB':
                raise ValueError('delisted')
            return [('2020-10-09', 300.0), ('2023-03-09', 100.0)], dict(symbol='SIVBQ', longName='SVB Financial Group',
                                                                     instrumentType='EQUITY', currency='USD')
        with tempfile.TemporaryDirectory() as tmp:
            report, cases = review(candidates, tmp, lambda cik, raw: (SUBMISSIONS, 'abc', ''), yahoo, pause=0)
            self.assertEqual(report['admitted_automatically'], 0)
            self.assertEqual(cases[0]['usable_series'], 'SIVBQ')
            self.assertEqual(cases[0]['status_filings'], 2)
            self.assertTrue((Path(tmp) / 'kursreihen_kandidaten.csv').read_text(encoding='utf-8-sig').count('ValueError') == 1)


if __name__ == '__main__':
    unittest.main()
