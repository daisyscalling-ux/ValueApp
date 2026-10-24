import datetime as dt
import unittest
from market_priority import market_tier,fetch_priority
class MarketPriorityTests(unittest.TestCase):
 def test_main_markets_first_without_removing_other_markets(self):
  now=dt.datetime(2026,10,24,tzinfo=dt.timezone.utc)
  symbols=['GPW:PKO','LSE:AZN','NASDAQ:MSFT','TSE:7203','XETR:SAP','OTC:OTHER']
  ordered=sorted(symbols,key=lambda s:fetch_priority(s,None,now))
  self.assertEqual(set(ordered),set(symbols))
  self.assertEqual([market_tier(s) for s in ordered],[0,0,0,1,2,2])
 def test_weekly_rotation_and_invalid_dates(self):
  now=dt.datetime(2026,10,24,tzinfo=dt.timezone.utc)
  self.assertLess(fetch_priority('GPW:PKO','2026-10-16T00:00:00Z',now),fetch_priority('NASDAQ:MSFT',None,now))
  for bad in [None,'invalid','2027-01-01T00:00:00Z','2020-01-01']:
   self.assertGreater(fetch_priority('GPW:PKO',bad,now),fetch_priority('NASDAQ:MSFT',None,now))
