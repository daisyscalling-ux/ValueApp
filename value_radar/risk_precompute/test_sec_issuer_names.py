import unittest
from sec_issuer_names import same_issuer
from sec_cashflow_history import diagnostics
class Names(unittest.TestCase):
 def test_format_only_names(self):
  for a,b in [('Applied Materials, Inc.','APPLIED MATERIALS INC /DE/'),('Costco Wholesale Corporation','COSTCO WHOLESALE CORP /NEW/'),('Booking Holdings Inc. Common Stock','Booking Holdings Inc.'),('Walt Disney Company (The)','The Walt Disney Company'),('3M Company','3M CO'),('BP PLC','BP plc'),('Aon plc','AON PLC'),("Lowe's Companies, Inc.",'LOWES COMPANIES INC'),('American Tower Corporation (REIT)','American Tower Corp'),('Duke Energy Corporation (Holding Company)','Duke Energy Corp')]:
   with self.subTest(a=a):self.assertTrue(same_issuer(a,b))
 def test_names_are_not_fuzzy_or_subsidiaries(self):
  for a,b in [('GE Aerospace','General Electric Company'),('Marsh','Marsh & McLennan Companies'),('Example Holdings','Example'),('Example Bank','Example Bank National Association'),('Example Class A','Example Class B'),('ABC','ABD'),('',''),('Alpha / Beta','Alpha')]:
   with self.subTest(a=a):self.assertFalse(same_issuer(a,b))
 def test_diagnostics_distinguish_source_definitions(self):
  self.assertEqual(diagnostics({'facts':{'ifrs-full':{}}})['reason'],'us_gaap_missing')
  self.assertEqual(diagnostics({'facts':{'us-gaap':{'Assets':{}}}})['reason'],'cash_ppe_concept_missing')
  d={'facts':{'us-gaap':{'PaymentsToAcquirePropertyPlantAndEquipment':{'units':{'USD':[{'form':'20-F','val':1}]}}}}}
  self.assertEqual(diagnostics(d)['reason'],'supported_annual_form_missing')
  d['facts']['us-gaap']['PaymentsToAcquirePropertyPlantAndEquipment']['units']['USD']=[{'form':'10-K','val':-1}]
  self.assertEqual(diagnostics(d)['reason'],'negative_cash_ppe_requires_review')
if __name__=='__main__':unittest.main()
