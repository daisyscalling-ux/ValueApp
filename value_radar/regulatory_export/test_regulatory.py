import unittest,datetime as dt
from collect_regulatory import normalize_record,collect,coverage
TODAY=dt.date(2026,10,19)
ROW={'CERT':628,'RSSDID':852218,'NAME':'Bank NA','NAMEHCR':'Holding Inc','RSSDHCR':'1039502','REPDTE':'20260630','RBCT1CER':15.03,'RBC1RWAJ':16,'NCLNLSR':.78}
class Tests(unittest.TestCase):
 def test_units_scope_and_publication(self):
  r=normalize_record(ROW,'20260630',TODAY)
  self.assertAlmostEqual(r['metrics']['cet1_ratio']['value'],.1503)
  self.assertAlmostEqual(r['metrics']['noncurrent_loans_ratio']['value'],.0078)
  self.assertEqual(r['scope'],'fdic_insured_institution');self.assertIsNone(r['published_at'])
  self.assertEqual(r['lcr']['state'],'not_collected')
 def test_missing_and_invalid_are_not_zero(self):
  for v in [None,'15',True,float('nan'),1001]:
   self.assertIsNone(normalize_record({**ROW,'RBCT1CER':v},'20260630',TODAY)['metrics']['cet1_ratio']['value'])
  self.assertEqual(normalize_record({**ROW,'RBCT1CER':0},'20260630',TODAY)['metrics']['cet1_ratio']['value'],0)
 def test_wrong_period_future_and_missing_identity(self):
  for row in [{**ROW,'REPDTE':'20270331'},{**ROW,'CERT':None},{**ROW,'RSSDID':''}]:
   with self.assertRaises(ValueError):normalize_record(row,str(row['REPDTE']),TODAY)
  with self.assertRaises(ValueError):normalize_record(ROW,'20260331',TODAY)
 def test_complete_fetch_and_duplicate_rejection(self):
  def fetch(p):return {'data':[{'data':ROW}],'meta':{'total':1}}
  data=collect(fetch,TODAY);self.assertEqual(data['institution_count'],1)
  with self.assertRaises(ValueError):collect(lambda p:{'data':[{'data':ROW},{'data':ROW}],'meta':{'total':2}},TODAY)
 def test_name_candidate_is_never_a_group_metric(self):
  data=collect(lambda p:{'data':[{'data':ROW}],'meta':{'total':1}},TODAY)
  r=coverage({'kandidaten':[{'ticker':'HOLD','name':'Holding Inc','industry':'Major banks'}]},data)['stocks'][0]
  self.assertEqual(r['state'],'identity_review');self.assertEqual(r['fdic_name_candidates'],['628']);self.assertIsNone(r['group_metrics']);self.assertIsNone(r['score'])
if __name__=='__main__':unittest.main()
