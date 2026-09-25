import unittest
from quantum_peers import metrics, matched
class Mapping(unittest.TestCase):
 def test_fcff_is_not_fcf(self):
  result=metrics({'is_sales_revenue_turnover':100}, {}, {'cf_free_cash_flow_firm':90}, {})
  self.assertIsNone(result['fcfMargin'])
 def test_complete_capex_and_units(self):
  r=metrics({'is_sales_revenue_turnover':100}, {}, {'cf_cash_from_oper':30,'cf_purchase_of_fixed_prod_assets':-5,'cf_acquisition_of_intang_assets':-2}, {'gross_margin':81.7})
  self.assertEqual(r['fcfMargin'],23);self.assertEqual(r['grossMargin'],81.7)
 def test_partial_capex(self):
  self.assertIsNone(metrics({'is_sales_revenue_turnover':100},{},{'cf_cash_from_oper':30,'cf_purchase_of_fixed_prod_assets':-5},{})['fcfMargin'])
 def test_period_currency(self):
  i={'period_end_date':'2026-06-30','currency':'USD','symbol':'TEST'}
  self.assertEqual(matched({'data':[dict(i,period_type='annual',gross_margin=81)]},i),{})
  self.assertEqual(matched({'data':[dict(i,period_type='ttm',currency='EUR',gross_margin=81)]},i),{})
 def test_fx_and_splits(self):
  i={'currency':'USD','diluted_eps':5}
  self.assertIsNone(metrics(i,{},{},{},{'currency':'EUR','close':100},{'data':[]})['pe'])
  self.assertEqual(metrics(i,{},{},{},{'currency':'USD','close':100},{'data':[]})['pe'],20)
  self.assertIsNone(metrics(i,{},{},{},{'currency':'USD','close':100},None)['pe'])
if __name__=='__main__':unittest.main()
