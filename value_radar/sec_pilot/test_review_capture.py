import unittest
from review_capture import normalize_capture

class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.days=['2020-01-02','2020-01-03','2020-01-06']
        self.capture=dict(symbol='TEST',source='https://example.org/history',provider='Synthetic test',
                          currency='USD',adjustment='Adjusted: Splits and Dividends',
                          rows=[dict(date=d,close='100',volume='10') for d in self.days])
    def test_zero_return_is_preserved(self):
        r=normalize_capture(self.capture,self.days)
        self.assertEqual(r[1]['Tagesrendite'],'0.0')
        self.assertEqual(r[0]['Tagesrendite'],'')
    def test_no_bridge_over_missing_session(self):
        self.capture['rows'].pop(1)
        self.assertEqual(normalize_capture(self.capture,self.days)[1]['Tagesrendite'],'')
    def test_duplicate_rejected(self):
        self.capture['rows'].append(self.capture['rows'][0])
        with self.assertRaises(ValueError):normalize_capture(self.capture,self.days)
    def test_no_unadjusted_substitution(self):
        self.capture['adjustment']='Unadjusted'
        with self.assertRaises(ValueError):normalize_capture(self.capture,self.days)
    def test_nontrading_prices_rejected(self):
        self.capture['rows'][0]['volume']='0'
        with self.assertRaises(ValueError):normalize_capture(self.capture,self.days)

if __name__=='__main__':unittest.main()

