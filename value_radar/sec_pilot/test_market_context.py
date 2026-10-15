import unittest
from review_market_context import normalize_market

class MarketTests(unittest.TestCase):
    def setUp(self):
        self.days=['2020-01-02','2020-01-03','2020-01-06']
        self.rows=[dict(Date=d,Close='100',Volume='10',**{'Adj Close':'90'}) for d in self.days]
    def test_indicators_are_not_investment_returns(self):
        rows,_=normalize_market(self.rows,self.days,'volatility_index_level')
        self.assertTrue(all(r['daily_return']=='' for r in rows))
        self.assertEqual(rows[0]['level'],'100.0')
    def test_etf_uses_adjusted_close(self):
        self.rows[1]['Adj Close']='99'
        rows,_=normalize_market(self.rows,self.days,'adjusted_price_proxy')
        self.assertAlmostEqual(float(rows[1]['daily_return']),.1)
    def test_missing_day_is_not_filled(self):
        self.rows.pop(1)
        rows,c=normalize_market(self.rows,self.days,'adjusted_price_proxy')
        self.assertEqual(c['missing_reference_sessions'],[self.days[1]])
        self.assertEqual(rows[-1]['daily_return'],'')
    def test_duplicate_fails(self):
        self.rows.append(self.rows[0])
        with self.assertRaises(ValueError):normalize_market(self.rows,self.days,'adjusted_price_proxy')
    def test_nontrading_row_is_not_zero_return(self):
        self.rows[1]['Volume']='0'
        rows,c=normalize_market(self.rows,self.days,'adjusted_price_proxy')
        self.assertEqual(c['invalid_observations'],[self.days[1]])
        self.assertEqual(rows[-1]['daily_return'],'')
    def test_zero_yield_is_valid_but_not_return(self):
        self.rows[0]['Close']='0'
        rows,_=normalize_market(self.rows,self.days,'ten_year_yield_indicator_percent')
        self.assertEqual(rows[0]['level'],'0.0');self.assertEqual(rows[0]['daily_return'],'')
    def test_outside_reference_calendar_reported(self):
        self.rows.append(dict(Date='2020-01-04',Close='100',Volume='10',**{'Adj Close':'90'}))
        rows,c=normalize_market(self.rows,self.days,'adjusted_price_proxy')
        self.assertEqual(len(rows),3);self.assertEqual(c['outside_reference_sessions'],['2020-01-04'])

if __name__=='__main__':unittest.main()
