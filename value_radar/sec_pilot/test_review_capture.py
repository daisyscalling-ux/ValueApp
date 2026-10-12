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

class PublicTableTests(unittest.TestCase):
    def setUp(self):
        self.days=['2020-01-02','2020-01-03']
        self.capture=dict(symbol='EA',source='https://stockanalysis.com/stocks/ea/history/',
            provider='Synthetic fixture',currency='USD',adjustment='Adj. Close',
            headers=['Date','Open','High','Low','Close','Adj. Close','Change','Volume'],
            rows=[['Jan 3, 2020','101','102','99','101','95.95','-90%','1,001'],
                  ['Jan 2, 2020','100','101','99','100','95','+90%','1,000']])
    def test_adjusted_column_drives_return_not_raw_or_change(self):
        rows=normalize_capture(self.capture,self.days)
        self.assertEqual(rows[0]['Datum'],'2020-01-02')
        self.assertEqual(rows[0]['Schlusskurs'],'100.0')
        self.assertEqual(rows[0]['Adjusted_Close'],'95.0')
        self.assertAlmostEqual(float(rows[1]['Tagesrendite']),.01)
    def test_wrong_security_source_rejected(self):
        self.capture['symbol']='MSFT'
        with self.assertRaises(ValueError):normalize_capture(self.capture,self.days)
    def test_reordered_headers_rejected(self):
        self.capture['headers'][4:6]=['Adj. Close','Close']
        with self.assertRaises(ValueError):normalize_capture(self.capture,self.days)
    def test_short_rows_rejected(self):
        self.capture['rows'][0].pop()
        with self.assertRaises(ValueError):normalize_capture(self.capture,self.days)
    def test_post_delisting_zero_volume_rejected(self):
        self.capture['rows'][0][-1]='0'
        with self.assertRaises(ValueError):normalize_capture(self.capture,self.days)

if __name__=='__main__':unittest.main()
