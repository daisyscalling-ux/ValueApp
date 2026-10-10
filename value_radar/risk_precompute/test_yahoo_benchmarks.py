import datetime as dt
import unittest
from yahoo_benchmarks import normalize

class YahooTests(unittest.TestCase):
    def setUp(self):
        self.now=dt.datetime(2026,10,10,tzinfo=dt.timezone.utc)
        self.meta={'symbol':'SPY','instrumentType':'ETF','currency':'USD','exchangeName':'PCX'}
        self.prices=[((self.now-dt.timedelta(days=i)).date().isoformat(),100.0) for i in range(300,0,-1)]
    def test_identity_and_adjustment(self):
        r=normalize('SPY',self.meta,self.prices,self.now)
        self.assertEqual(r['symbol'],'YAHOO:SPY')
        self.assertEqual(r['adjustment'],'total_return')
        for change in [{'symbol':'EWG'},{'currency':'EUR'},{'instrumentType':'EQUITY'},{'exchangeName':'LSE'}]:
            with self.assertRaises(ValueError): normalize('SPY',{**self.meta,**change},self.prices,self.now)
    def test_missing_bad_stale_and_current_day(self):
        for prices in [self.prices[:100],self.prices[:-20],self.prices+[(self.prices[-1][0],0.0)]]:
            with self.assertRaises(ValueError): normalize('SPY',self.meta,prices,self.now)
        r=normalize('SPY',self.meta,self.prices+[('2026-10-10',200.0)],self.now)
        self.assertEqual(r['bars'][-1]['date'],'2026-10-09')
if __name__=='__main__': unittest.main()
