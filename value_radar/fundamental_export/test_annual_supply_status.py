import unittest,datetime as dt
from queue_policy import annual_supply_status,timestamp
NOW=dt.datetime(2026,10,26,12,tzinfo=dt.timezone.utc).timestamp()
class Supply(unittest.TestCase):
 def test_market_success_does_not_rejuvenate_annual(self):
  data={'retrieved_at':'2026-10-26T11:00:00Z','annual_retrieved_at':'2026-10-16T10:00:00Z','annual':{'end':'2025-08-31'}}
  r=annual_supply_status(data,NOW);self.assertEqual(r['state'],'retained_stale');self.assertFalse(r['freshAnnualReturned'])
 def test_no_annual_is_explicit(self):self.assertEqual(annual_supply_status({'retrieved_at':'2026-10-26T11:00:00Z'},NOW)['state'],'annual_missing')
 def test_current_and_future(self):
  d={'retrieved_at':'2026-10-26T11:00:00Z','annual':{'end':'2026-06-30'}}
  self.assertTrue(annual_supply_status(d,NOW)['freshAnnualReturned']);d['annual']['end']='2027-06-30';self.assertNotEqual(annual_supply_status(d,NOW)['state'],'current')
 def test_retained_field_age_is_not_hidden(self):
  d={'retrieved_at':'2026-10-26T11:00:00Z','annual':{'end':'2026-06-30','field_sources':{'capex':{'retrieved_at':'2026-10-16T00:00:00Z'}}}}
  r=annual_supply_status(d,NOW);self.assertFalse(r['freshAnnualReturned']);self.assertEqual(r['retainedFields'],['capex']);self.assertNotEqual(r['state'],'current')
 def test_dates_use_utc(self):self.assertEqual(timestamp('2026-10-26'),timestamp('2026-10-26T00:00:00Z'))
if __name__=='__main__':unittest.main()
