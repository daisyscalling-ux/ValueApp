import copy,datetime as dt,json,unittest
from pathlib import Path
from holding_liquidity import liquidity_for
class Tests(unittest.TestCase):
 def setUp(self):
  self.a=json.loads((Path(__file__).resolve().parents[1]/'regulatory_export/reviewed-liquidity.json').read_text())
  self.p={'rssdId':'1951350','holdingName':'CITIGROUP INC.','period':'2026-06-30'};self.now=dt.datetime(2026,11,1,tzinfo=dt.timezone.utc)
 def test_real_reviewed_consolidated_ratio(self):
  r=liquidity_for(self.p,self.a,self.now);self.assertEqual(r['reportedRatio'],1.13);self.assertEqual(r['scoreContribution'],0);self.assertFalse(r['pointInTimeUsable'])
 def test_mismatch_arithmetic_dates_and_units(self):
  for patch in [{'rssdId':'other'},{'holdingName':'CITIBANK N.A.'},{'period':'2026-03-31'},{'scope':'subsidiary'},{'unit':'percent'},{'reportedRatio':113},{'reportedRatio':True},{'netOutflows':0},{'hqla':1},{'averaging':'year_end'},{'reviewedOn':'2027-01-01'},{'reviewExpires':'2026-10-31'},{'sourceUrl':'https://example.com'},{'ratioRoundingTolerance':1}]:
   a=copy.deepcopy(self.a);a['records'][0].update(patch);self.assertIsNone(liquidity_for(self.p,a,self.now))
 def test_duplicate_and_expired_source(self):
  self.a['records']*=2;self.assertIsNone(liquidity_for(self.p,self.a,self.now));self.a['records']=self.a['records'][:1];self.assertIsNone(liquidity_for(self.p,self.a,self.now+dt.timedelta(days=90)))
if __name__=='__main__':unittest.main()
