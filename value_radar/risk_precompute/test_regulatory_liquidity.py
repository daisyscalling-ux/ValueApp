import copy,datetime as dt,json,unittest
from pathlib import Path
from holding_liquidity import liquidity_for
class Tests(unittest.TestCase):
 def setUp(self):
  self.a=json.loads((Path(__file__).resolve().parents[1]/'regulatory_export/reviewed-liquidity.json').read_text())
  self.p={'rssdId':'1951350','holdingName':'CITIGROUP INC.','period':'2026-06-30'};self.now=dt.datetime(2026,11,1,tzinfo=dt.timezone.utc)
 def test_real_reviewed_consolidated_ratio(self):
  r=liquidity_for(self.p,self.a,self.now);self.assertEqual(r['reportedRatio'],1.13);self.assertEqual(r['scoreContribution'],0);self.assertFalse(r['pointInTimeUsable'])
 def test_jpm_firm_ratio_not_bank_subsidiary(self):
  p={'rssdId':'1039502','holdingName':'JPMORGAN CHASE & CO.','period':'2026-06-30'}
  r=liquidity_for(p,self.a,dt.datetime(2026,11,5,tzinfo=dt.timezone.utc))
  self.assertEqual(r['reportedRatio'],1.10);self.assertEqual(r['hqla'],975412000000);self.assertEqual(r['netOutflows'],885521000000)
  self.assertIsNone(liquidity_for({**p,'holdingName':'JPMORGAN CHASE BANK, N.A.'},self.a,dt.datetime(2026,11,5,tzinfo=dt.timezone.utc)))
 def test_mismatch_arithmetic_dates_and_units(self):
  for patch in [{'rssdId':'other'},{'holdingName':'CITIBANK N.A.'},{'period':'2026-03-31'},{'scope':'subsidiary'},{'unit':'percent'},{'reportedRatio':113},{'reportedRatio':True},{'netOutflows':0},{'hqla':1},{'averaging':'year_end'},{'reviewedOn':'2027-01-01'},{'reviewExpires':'2026-10-31'},{'sourceUrl':'https://example.com'},{'ratioRoundingTolerance':1}]:
   a=copy.deepcopy(self.a);a['records'][0].update(patch);self.assertIsNone(liquidity_for(self.p,a,self.now))
 def test_duplicate_and_expired_source(self):
  self.a['records']*=2;self.assertIsNone(liquidity_for(self.p,self.a,self.now));self.a['records']=self.a['records'][:1];self.assertIsNone(liquidity_for(self.p,self.a,self.now+dt.timedelta(days=90)))
if __name__=='__main__':unittest.main()


class RatioOnlyAndExemptionTests(unittest.TestCase):
 """Spiegel von test-holding-liquidity.ts (11.11.2026)."""
 def setUp(self):
  import datetime as dt
  self.now=dt.datetime(2026,11,1,12,tzinfo=dt.timezone.utc);self.p={'rssdId':'1','holdingName':'X CORP','period':'2026-06-30'}
  base={'rssdId':'1','holdingName':'X CORP','period':'2026-06-30','scope':'listed_consolidated_holding','reviewedOn':'2026-11-01','reviewExpires':'2026-12-27',
        'sourceUrl':'https://www.sec.gov/Archives/edgar/data/1/000000000126000001/x-20260630.htm','sourceSection':'Liquidity, page 1'}
  self.q={**base,'state':'available','averaging':'quarter_average','unit':'fraction','currency':'USD','basis':'ratio_only','hqla':684e9,'netOutflows':None,'ratioRoundingTolerance':None,'reportedRatio':1.12}
  self.e={**base,'reason':'us_category_iv_lcr_not_applicable','quote':'As a Category IV institution ... is not subject to the LCR.'}
 def arch(self,records=(),exemptions=()):return {'schema':1,'method':'reviewed-holding-lcr-v1','records':list(records),'exemptions':list(exemptions)}
 def test_ratio_only(self):
  from holding_liquidity import liquidity_for
  self.assertEqual(liquidity_for(self.p,self.arch([self.q]),self.now)['reportedRatio'],1.12)
  for patch in [{'netOutflows':6e11},{'reportedRatio':0},{'hqla':-1},{'basis':'estimate'},{'sourceSection':''}]:
   self.assertIsNone(liquidity_for(self.p,self.arch([{**self.q,**patch}]),self.now),patch)
 def test_exemption(self):
  from holding_liquidity import exemption_for
  self.assertEqual(exemption_for(self.p,self.arch(exemptions=[self.e]),self.now)['state'],'not_applicable')
  for patch in [{'reason':'x'},{'quote':'kurz'},{'period':'2026-03-31'},{'reviewExpires':'2026-10-31'},{'sourceUrl':'https://example.com/x.htm'}]:
   self.assertIsNone(exemption_for(self.p,self.arch(exemptions=[{**self.e,**patch}]),self.now),patch)
