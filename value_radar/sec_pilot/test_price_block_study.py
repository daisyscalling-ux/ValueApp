import datetime as dt
import unittest

import numpy as np

from price_block_study import auc, features, lin, outcome, quarter_ends


def business_days(n, start='2018-01-01'):
    d, out = dt.date.fromisoformat(start), []
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += dt.timedelta(days=1)
    return out


class PriceBlockStudyTests(unittest.TestCase):
    def test_features_match_app_scales_and_need_two_years(self):
        dates = business_days(600)
        prices = np.full(600, 100.0)
        self.assertIsNone(features(dates, prices, 400))
        f = features(dates, prices, 599)
        self.assertEqual((f['es'], f['dd'], f['worst'], f['score']), (0.0, 0.0, 0.0, 0.0))
        prices[-30:] = 50.0
        f = features(dates, prices, 599)
        self.assertAlmostEqual(f['dd'], 0.5)
        self.assertAlmostEqual(f['cur_dd'], 0.5)
        self.assertGreater(f['score'], 0)

    def test_gap_over_14_days_blocks_history(self):
        dates = business_days(600)
        dates = dates[:300] + [(dt.date.fromisoformat(d) + dt.timedelta(days=20)).isoformat() for d in dates[300:]]
        self.assertIsNone(features(dates, np.full(600, 100.0), 599))

    def test_outcome_starts_after_entry_and_needs_full_window(self):
        prices = np.array([100.0, 100.0, 80.0, 90.0])
        self.assertAlmostEqual(outcome(prices, 1, 2), 0.2)
        self.assertIsNone(outcome(prices, 1, 3))

    def test_quarter_ends_and_auc(self):
        self.assertEqual(quarter_ends(['2016-03-30', '2016-03-31', '2016-04-01', '2016-06-30', '2016-07-01']),
                         ['2016-03-31', '2016-06-30'])
        self.assertEqual(auc([1, 2, 3, 4], [0, 0, 1, 1]), 1.0)
        self.assertEqual(auc([1, 1], [0, 1]), 0.5)
        self.assertEqual(lin(0.5, 0, 1), 50.0)


if __name__ == '__main__':
    unittest.main()
