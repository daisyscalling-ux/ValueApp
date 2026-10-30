import copy
import datetime as dt
import unittest
from regulatory_context import build

class RegulatoryContextTests(unittest.TestCase):
 def setUp(self):
  self.now=dt.datetime(2026,10,27,tzinfo=dt.timezone.utc)
  digest='a'*64
  self.u={'kandidaten':[{'listing_symbol':'NYSE:EX','name':'Example Inc.','isin':'US0378331005','security_type':'common_stock','currency':'USD'}]}
  self.h={'scope':'FR_Y9C_consolidated_reporting_entity','imported_at':'2026-10-19T12:00:00Z','reporting_period':'2026-06-30','files':[{'sha256':digest}],
   'definitions':{'BHCAP793':{'metric':'cet1_ratio','unit':'fraction','source_unit':'percent','valid_from':'2014-03-31','valid_to':'9999-12-31'}},
   'entities':{'1':{'name':'Example Inc.','metrics':{'BHCAP793':{'value':.14,'raw_value':'14','state':'reported'}}}}}
  self.reg={'schema':1,'reviewed_on':'2026-10-20','review_expires':'2027-04-18','entries':[{'symbol':'NYSE:EX','rssd_id':'1','holding_name':'Example Inc.','security_type':'common_stock','scope':'listed_consolidated_holding','listing_source_url':'https://example.com/ir','holding_evidence':{'source_file_sha256':digest}}]}
 def run_case(self):return build(self.u,self.h,self.reg,self.now)
 def test_valid_zero_and_identity_binding(self):
  r=self.run_case()['stocks']['NYSE:EX'];self.assertEqual(r['metrics']['cet1_ratio']['value'],.14);self.assertIsNone(r['score']);self.assertFalse(r['pointInTimeUsable']);self.assertEqual(r['inputIdentity']['isin'],'US0378331005')
  self.h['entities']['1']['metrics']['BHCAP793'].update(value=0,raw_value='0')
  self.assertEqual(self.run_case()['stocks']['NYSE:EX']['metrics']['cet1_ratio']['value'],0)
 def test_units_and_invalid_numbers_rejected(self):
  for value,raw in [(14,'14'),(.14,'.14'),(float('nan'),'14'),(True,'100'),(.14,'nan'),(-.1,'-10')]:
   with self.subTest(value=value,raw=raw):
    self.h['entities']['1']['metrics']['BHCAP793'].update(value=value,raw_value=raw)
    self.assertFalse(self.run_case()['stocks'])
 def test_digest_and_definition_dates(self):
  self.h['files']=[];self.assertFalse(self.run_case()['stocks'])
  self.h['files']=[{'sha256':'a'*64}]
  self.h['definitions']['BHCAP793']['valid_to']='2025-12-31';self.assertFalse(self.run_case()['stocks'])
 def test_source_and_review_dates(self):
  for date in ['2027-01-01T00:00:00Z','not-a-date','2026-10-01']:
   self.h['imported_at']=date;self.assertFalse(self.run_case()['stocks'])
  self.h['imported_at']='2026-10-19T12:00:00Z'
  self.reg['review_expires']='2026-10-26';self.assertFalse(self.run_case()['stocks'])
 def test_identity_and_scope(self):
  for key,value in [('name','Subsidiary'),('isin','bad'),('share_class','preferred'),('listing_reference_status','expired')]:
   old=copy.deepcopy(self.u)
   self.u['kandidaten'][0][key]=value;self.assertFalse(self.run_case()['stocks']);self.u=old
  self.u['kandidaten']*=2;self.assertFalse(self.run_case()['stocks'])
 def test_old_or_future_period(self):
  for period in ['2025-06-30','2027-06-30']:
   self.h['reporting_period']=period;self.assertFalse(self.run_case()['stocks'])
 def test_capital_hierarchy(self):
  self.h['definitions']['BHCA7206']={**self.h['definitions']['BHCAP793'],'metric':'tier1_ratio'}
  self.h['entities']['1']['metrics']['BHCA7206']={'state':'reported','value':.1,'raw_value':'10'}
  self.assertEqual(self.run_case()['rejected']['NYSE:EX'],'capital_hierarchy_inconsistent')

if __name__=='__main__':unittest.main()
