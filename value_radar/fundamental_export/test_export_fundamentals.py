import unittest,datetime as dt
from export_fundamentals import yahoo_annual,sec_annual,yahoo_symbol,preserve_annual,enrich_matching_annual
NOW=dt.date(2026,10,15)
class Tests(unittest.TestCase):
 def test_failed_or_older_response_preserves_original_observation_age(self):
  old={'annual':{'end':'2026-06-30'},'retrieved_at':'2026-10-01'}
  for annual in [None,{'end':'2025-06-30'}]:
   d=preserve_annual({'annual':annual,'retrieved_at':'2026-10-15','issues':[]},old)
   self.assertEqual(d['annual']['end'],'2026-06-30');self.assertEqual(d['annual_retrieved_at'],'2026-10-01')
 def test_reject_old_tables_behind_info(self):
  frames={'income':{'2025-08-31':{'Total Revenue':37378,'Diluted EPS':7.59}}}
  self.assertIsNone(yahoo_annual(frames,{'symbol':'MU','lastFiscalYearEnd':1788393600},NOW))
 def test_currency_period_and_no_profile_eps_override(self):
  a=yahoo_annual({'income':{'2026-08-31':{'Total Revenue':100,'Diluted EPS':5},'2025-08-31':{'Total Revenue':80,'Diluted EPS':4}}},{'symbol':'MU','financialCurrency':'USD','trailingEps':500},NOW)
  self.assertEqual(a['fields']['eps_trailing'],5);self.assertEqual(a['fields']['revenue_growth'],.25);self.assertEqual(a['currency'],'USD')
 def test_listing_mapping(self):
  self.assertEqual(yahoo_symbol({'listing_symbol':'XETR:SAP'}),'SAP.DE')
  self.assertEqual(yahoo_symbol({'listing_symbol':'TSE:7203'}),'7203.T')
  with self.assertRaises(ValueError):yahoo_symbol({'listing_symbol':'UNKNOWN:SAP'})
 def test_new_exchange_mappings_and_ambiguous_venues(self):
  for listing,ticker,expected in [('OTC:TCEHY','TCEHY','TCEHY'),('BME:IBE','IBE.MC','IBE.MC'),('HEL:NOKIA','NOKIA.HE','NOKIA.HE'),('EURONEXT:SHELL','SHELL.AS','SHELL.AS'),('EURONEXT:MC','MC.PA','MC.PA')]:
   self.assertEqual(yahoo_symbol({'listing_symbol':listing,'ticker':ticker}),expected)
  for ticker in ['SHELL','OTHER.AS','SHELL.DE']:
   with self.assertRaises(ValueError):yahoo_symbol({'listing_symbol':'EURONEXT:SHELL','ticker':ticker})
 def test_enrichment_requires_exact_period_currency_and_matching_earnings(self):
  import copy
  a={'end':'2026-09-03','period_type':'annual','currency':'USD','fields':{'revenue':100,'eps_trailing':5}}
  b={**a,'source':'Issuer','source_url':'https://example.com/report','fields':{'revenue':100,'eps_trailing':5,'total_debt':30}}
  merged=enrich_matching_annual(copy.deepcopy(a),b)
  self.assertEqual(merged['fields']['total_debt'],30)
  self.assertEqual(merged['field_sources']['total_debt']['source'],'Issuer')
  for bad in [{**b,'end':'2025-09-03'},{**b,'currency':'EUR'},{**b,'fields':{**b['fields'],'eps_trailing':6}}]:
   self.assertNotIn('total_debt',enrich_matching_annual(copy.deepcopy(a),bad)['fields'])
 def test_sec_requires_same_accession_and_annual_duration(self):
  def fact(v,acc='A',start='2025-09-01'):return {'val':v,'start':start,'end':'2026-08-31','filed':'2026-10-01','form':'10-K','accn':acc}
  data={'cik':123,'facts':{'us-gaap':{'Revenues':{'units':{'USD':[fact(100)]}},'EarningsPerShareDiluted':{'units':{'USD/shares':[fact(5)]}},'NetIncomeLoss':{'units':{'USD':[fact(10,'B')]}}}}}
  self.assertIsNone(sec_annual(data,'123',NOW))
  data['facts']['us-gaap']['NetIncomeLoss']['units']['USD'][0]['accn']='A'
  self.assertEqual(sec_annual(data,'123',NOW)['fields']['eps_trailing'],5)
  self.assertIsNone(sec_annual(data,'999',NOW))
  data['facts']['us-gaap']['Revenues']['units']['USD'][0]['start']='2026-06-01'
  self.assertIsNone(sec_annual(data,'123',NOW))
if __name__=='__main__':unittest.main()

