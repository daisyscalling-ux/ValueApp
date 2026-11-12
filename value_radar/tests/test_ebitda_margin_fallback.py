import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path

import ebitda_margin_fallback as e

TODAY = dt.date(2026, 11, 12)


def annual(end='2026-09-30', ebitda=5405e6, revenue=18982e6, period_type='annual'):
    return {'end': end, 'period_type': period_type, 'currency': 'USD', 'source': 'SEC companyfacts / US-GAAP', 'fields': {'ebitda': ebitda, 'revenue': revenue}}


class FallbackTests(unittest.TestCase):
    def run_apply(self, rows, files):
        with tempfile.TemporaryDirectory() as tmp:
            for name, data in files.items():
                (Path(tmp) / name).write_text(json.dumps(data), encoding='utf-8')
            n = e.apply(rows, Path(tmp), TODAY)
        return n, rows

    def test_fills_missing_margin_with_marker(self):
        n, rows = self.run_apply([{'listing_symbol': 'NYSE:EMR', 'ticker': 'EMR', 'ebitda_margin': None}], {'NYSE_EMR.json': {'symbol': 'NYSE:EMR', 'annual': annual()}})
        self.assertEqual(n, 1)
        self.assertEqual(rows[0]['ebitda_margin'], 28.5)
        self.assertEqual(rows[0]['ebitda_margin_source'], {'method': e.METHOD, 'end': '2026-09-30', 'source': 'SEC companyfacts / US-GAAP', 'currency': 'USD'})

    def test_never_overwrites_provider_margin_and_drops_stale_marker(self):
        n, rows = self.run_apply([{'listing_symbol': 'NYSE:EMR', 'ebitda_margin': 26.1, 'ebitda_margin_source': {'method': 'x'}}], {'NYSE_EMR.json': {'symbol': 'NYSE:EMR', 'annual': annual()}})
        self.assertEqual((n, rows[0]['ebitda_margin']), (0, 26.1))
        self.assertNotIn('ebitda_margin_source', rows[0])

    def test_rejections(self):
        cases = {
            'stale': ({'symbol': 'NYSE:X', 'annual': annual(end='2025-07-31')}, 'annual_stale_or_not_annual'),
            'quarter': ({'symbol': 'NYSE:X', 'annual': annual(period_type='quarter')}, 'annual_stale_or_not_annual'),
            'no revenue': ({'symbol': 'NYSE:X', 'annual': annual(revenue=0)}, 'ebitda_or_revenue_missing'),
            'no ebitda': ({'symbol': 'NYSE:X', 'annual': annual(ebitda=None)}, 'ebitda_or_revenue_missing'),
            'out of range': ({'symbol': 'NYSE:X', 'annual': annual(ebitda=3e10, revenue=1e10)}, 'margin_out_of_range'),
            'other listing': ({'symbol': 'NASDAQ:X', 'annual': annual()}, 'no_annual_statement'),
        }
        for label, (data, reason) in cases.items():
            with tempfile.TemporaryDirectory() as tmp:
                (Path(tmp) / 'NYSE_X.json').write_text(json.dumps(data), encoding='utf-8')
                margin, why = e.annual_margin({'listing_symbol': 'NYSE:X', 'ticker': 'X'}, Path(tmp), TODAY)
            self.assertEqual((margin, why), (None, reason), label)

    def test_row_without_listing_symbol_is_not_filled(self):
        n, rows = self.run_apply([{'listing_symbol': None, 'ticker': 'CBOE', 'ebitda_margin': None}], {'CBOE.json': {'symbol': 'CBOE', 'annual': annual()}})
        self.assertEqual(n, 0)
        self.assertIsNone(rows[0]['ebitda_margin'])

    def test_negative_margin_is_kept(self):
        n, rows = self.run_apply([{'listing_symbol': 'NYSE:KHC', 'ebitda_margin': None}], {'NYSE_KHC.json': {'symbol': 'NYSE:KHC', 'annual': annual(end='2025-12-31', ebitda=-3.53e9, revenue=24.942e9)}})
        self.assertEqual(rows[0]['ebitda_margin'], -14.2)


if __name__ == '__main__':
    unittest.main()
