import copy,datetime as dt,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'regulatory_export'))
from regulatory_credit import credit_context,CODES
class CreditContextTests(unittest.TestCase):
 def setUp(self):
  self.now=dt.datetime(2026,10,30,tzinfo=dt.timezone.utc)
  self.cap={'period':'2026-06-30','sourceFileSha256':'a'*64,'rssdId':'1','holdingName':'Example'}
  vals={'nonaccrual':10,'past_due_30_89':5,'past_due_90':2,'held_for_investment':900,'held_for_sale':100}
  self.a={'schema':1,'source':'FFIEC_BHCF_loan_quality','scope':'FR_Y9C_consolidated_reporting_entity','imported_at':'2026-10-29T10:00:00Z','reporting_period':'2026-06-30','source_file_sha256':'a'*64,'source_url':'https://example.com','definitions':{code:{'metric':name,'unit':'USD_thousands','valid_from':'2018-03-31','valid_to':'9999-12-31'} for name,code in CODES.items()},'entities':{'1':{'name':'Example','fields':{code:{'state':'reported','value':vals[name],'raw_value':str(vals[name])} for name,code in CODES.items()}}}}
 def run_case(self):return credit_context(self.a,self.cap,self.now)
 def test_calculation_and_scope(self):
  r=self.run_case();self.assertEqual(r['totalLoans'],1000);self.assertEqual(r['ratios']['nonaccrual_or_90_past_due'],.012);self.assertIsNone(r['score']);self.assertFalse(r['pointInTimeUsable'])
 def test_missing_is_not_zero(self):
  f=self.a['entities']['1']['fields']['BHCK1403'];f.update(value=0,raw_value='0');self.assertEqual(self.run_case()['state'],'available')
  f.update(value=None,raw_value=None,state='missing');self.assertEqual(self.run_case()['state'],'missing')
 def test_source_period_identity_and_import_guards(self):
  for key,v in [('reporting_period','2026-09-30'),('source_file_sha256','b'*64),('imported_at','2027-01-01T00:00:00Z'),('scope','parent_only')]:
   old=copy.deepcopy(self.a);self.a[key]=v;self.assertEqual(self.run_case()['state'],'missing');self.a=old
  self.a['entities']['1']['name']='Subsidiary';self.assertEqual(self.run_case()['state'],'missing')
 def test_units_definition_and_invalid_amounts(self):
  for v in [-1,True,1.5,float('nan')]:
   self.a['entities']['1']['fields']['BHCK1403'].update(value=v,raw_value=str(v));self.assertEqual(self.run_case()['state'],'missing')
  self.setUp();self.a['definitions']['BHCK1403']['unit']='USD';self.assertEqual(self.run_case()['state'],'missing')
 def test_inconsistent_totals(self):
  self.a['entities']['1']['fields']['BHCK1403'].update(value=1001,raw_value='1001');self.assertEqual(self.run_case()['reason'],'credit_totals_inconsistent')
if __name__=='__main__':unittest.main()
