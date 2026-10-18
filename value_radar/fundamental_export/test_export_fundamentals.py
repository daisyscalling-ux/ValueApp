import unittest,datetime as dt
from export_fundamentals import yahoo_annual,sec_annual,yahoo_symbol,preserve_annual,enrich_matching_annual,select_registered_rows,annual_diagnostics
NOW=dt.date(2026,10,15)
class Tests(unittest.TestCase):
 def test_statement_isolation_and_component_provenance(self):
  date='2026-06-30'
  frames={'income':{date:{'Total Revenue':100,'Operating Cash Flow':None}},'balance':{date:{'Current Debt And Capital Lease Obligation':3,'Long Term Debt And Capital Lease Obligation':7,'Operating Cash Flow':None}},'cashflow':{date:{'Operating Cash Flow':15,'Purchase Of PPE':-4,'Purchase Of Intangibles':-2,'Total Revenue':None}}}
  a=yahoo_annual(frames,{'symbol':'TEST','financialCurrency':'USD'},NOW)
  self.assertEqual(a['fields']['revenue'],100)
  self.assertEqual(a['fields']['operating_cashflow'],15)
  self.assertEqual(a['fields']['total_debt'],10)
  self.assertEqual(a['fields']['capex'],-6)
  self.assertEqual(a['field_sources']['capex']['end'],date)
  self.assertEqual(len(a['field_sources']['capex']['components']),2)
  frames['balance'][date]['Total Debt']=0
  frames['cashflow'][date]['Capital Expenditure']=-9
  a=yahoo_annual(frames,{'symbol':'TEST','financialCurrency':'USD'},NOW)
  self.assertEqual(a['fields']['total_debt'],0)
  self.assertEqual(a['fields']['capex'],-9)
  self.assertEqual(a['field_sources'],{})
 def test_components_require_complete_same_date_and_valid_signs(self):
  date='2026-06-30'
  for missing in [None,float('nan'),4]:
   frames={'income':{date:{'Total Revenue':100}},'cashflow':{date:{'Purchase Of PPE':-4,'Purchase Of Intangibles':missing,'Free Cash Flow':10,'Operating Cash Flow':10}}}
   self.assertIsNone(yahoo_annual(frames,{'symbol':'TEST'},NOW)['fields']['capex'])
  frames={'income':{date:{'Total Revenue':100}},'balance':{date:{'Current Debt And Capital Lease Obligation':3},'2025-06-30':{'Long Term Debt And Capital Lease Obligation':7}},'cashflow':{date:{'Purchase Of PPE':-4},'2025-06-30':{'Purchase Of Intangibles':-2}}}
  a=yahoo_annual(frames,{'symbol':'TEST'},NOW)
  self.assertIsNone(a['fields']['total_debt']);self.assertIsNone(a['fields']['capex'])
 def test_diagnostics_distinguish_missing_revenue_and_fiscal_period(self):
  frames={'income':{'2025-09-30':{'Total Revenue':None}}}
  info={'lastFiscalYearEnd':int(dt.datetime(2026,9,30,tzinfo=dt.timezone.utc).timestamp())}
  result=annual_diagnostics(None,frames,info,NOW)
  self.assertIn('latest_income_revenue_missing',result['reason_codes'])
  self.assertIn('table_behind_provider_fiscal_end',result['reason_codes'])
  self.assertEqual(result['selected_annual_end'],None)
 def test_diagnostics_do_not_label_missing_cashflow_as_complete(self):
  annual={'end':'2026-06-30','fields':{'eps_trailing':5,'total_debt':0,'cash':0,'operating_cashflow':50}}
  result=annual_diagnostics(annual,{}, {},NOW)
  self.assertEqual(result['state'],'partial');self.assertEqual(result['missing_fields'],['capex'])
  annual['fields']['capex']=0
  self.assertEqual(annual_diagnostics(annual,{}, {},NOW)['state'],'available')
  self.assertEqual(annual_diagnostics(None,{}, {},NOW)['reason_codes'],['income_table_empty'])
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
 def test_new_request_persists_after_failure_and_returns_in_daily_run(self):
  index={'listings':{},'attempts':{}}
  requested=select_registered_rows([],index,' nasdaq:new ')
  self.assertEqual(requested[0]['listing_symbol'],'NASDAQ:NEW')
  # No successful snapshot is needed for enrollment to survive.
  self.assertEqual(select_registered_rows([],index,'')[0]['listing_symbol'],'NASDAQ:NEW')
 def test_missing_secondary_eps_allows_verified_balance_not_share_fields(self):
  a={'end':'2026-06-30','period_type':'annual','currency':'USD','fields':{'revenue':100,'net_income':20,'eps_trailing':5}}
  b={**a,'source':'Yahoo annual statements','fields':{'revenue':100,'net_income':20,'eps_trailing':None,'total_debt':30,'weighted_shares':999,'capex':-8}}
  result=enrich_matching_annual(a,b)
  self.assertEqual(result['fields']['total_debt'],30)
  self.assertEqual(result['fields']['capex'],-8)
  self.assertEqual(result['fields']['eps_trailing'],5)
  self.assertNotIn('weighted_shares',result['fields'])
  self.assertEqual(result['field_sources']['total_debt']['matched_fields'],['revenue','net_income'])
  self.assertNotIn('total_debt',result['missing_fields'])
 def test_income_anchor_does_not_transfer_eps_or_accept_conflicting_anchors(self):
  import copy
  a={'end':'2026-06-30','period_type':'annual','currency':'USD','fields':{'revenue':100,'net_income':20}}
  b={**a,'fields':{'revenue':100,'net_income':20,'eps_trailing':5,'total_debt':30}}
  result=enrich_matching_annual(copy.deepcopy(a),b)
  self.assertNotIn('eps_trailing',result['fields'])
  self.assertEqual(result['fields']['total_debt'],30)
  for changes in [{'net_income':25},{'net_income':None},{'revenue':101}]:
   bad={**b,'fields':{**b['fields'],**changes}}
   self.assertNotIn('total_debt',enrich_matching_annual(copy.deepcopy(a),bad)['fields'])
  a['fields']['eps_trailing']=4
  self.assertNotIn('total_debt',enrich_matching_annual(a,b)['fields'])
 def test_enrichment_preserves_existing_debt_and_rejects_negative_debt(self):
  import copy
  a={'end':'2026-06-30','period_type':'annual','currency':'USD','fields':{'revenue':100,'net_income':20,'total_debt':0}}
  b={**a,'fields':{'revenue':100,'net_income':20,'total_debt':30}}
  self.assertEqual(enrich_matching_annual(copy.deepcopy(a),b)['fields']['total_debt'],0)
  del a['fields']['total_debt'];b['fields']['total_debt']=-1
  self.assertNotIn('total_debt',enrich_matching_annual(a,b)['fields'])
 def test_registry_migration_dedup_and_new_universe_precedence(self):
  index={'listings':{'NASDAQ:OLD':'NASDAQ_OLD.json'},'registered':{'EURONEXT:SHELL':{'listing_symbol':'EURONEXT:SHELL','ticker':'SHELL'}}}
  rows=select_registered_rows([{'listing_symbol':'EURONEXT:SHELL','ticker':'SHELL.AS'}],index,'')
  self.assertEqual(len(rows),2)
  self.assertEqual(next(r for r in rows if r['listing_symbol']=='EURONEXT:SHELL')['ticker'],'SHELL.AS')
  with self.assertRaises(ValueError):select_registered_rows([],index,'Unknown Company')
 def test_missing_eps_keeps_current_financial_statements(self):
  a=yahoo_annual({'income':{'2026-03-31':{'Total Revenue':100,'Net Income':20}}},{'symbol':'TEST','financialCurrency':'GBP'},NOW)
  self.assertEqual(a['fields']['revenue'],100)
  self.assertIsNone(a['fields']['eps_trailing'])
  self.assertIn('eps_trailing',a['missing_fields'])
 def test_sec_requires_same_accession_and_annual_duration(self):
  def fact(v,acc='A',start='2025-09-01'):return {'val':v,'start':start,'end':'2026-08-31','filed':'2026-10-01','form':'10-K','accn':acc}
  data={'cik':123,'facts':{'us-gaap':{'Revenues':{'units':{'USD':[fact(100)]}},'EarningsPerShareDiluted':{'units':{'USD/shares':[fact(5)]}},'NetIncomeLoss':{'units':{'USD':[fact(10,'B')]}}}}}
  self.assertIsNone(sec_annual(data,'123',NOW))
  data['facts']['us-gaap']['NetIncomeLoss']['units']['USD'][0]['accn']='A'
  self.assertEqual(sec_annual(data,'123',NOW)['fields']['eps_trailing'],5)
  self.assertIsNone(sec_annual(data,'999',NOW))
  data['facts']['us-gaap']['Revenues']['units']['USD'][0]['start']='2026-06-01'
  self.assertIsNone(sec_annual(data,'123',NOW))


class ReferenceTests(unittest.TestCase):
 def test_ecb_cross_rates_and_dates(self):
  from reference_data import parse_ecb
  xml='<Envelope><Cube time="2026-10-15"><Cube currency="USD" rate="1.2"/><Cube currency="GBP" rate="0.8"/></Cube></Envelope>'
  result=parse_ecb(xml,NOW)
  self.assertAlmostEqual(result['rates']['GBP']/result['rates']['USD'],2/3)
  for bad in [xml.replace('2026-10-15','2027-10-15'),xml.replace('2026-10-15','2025-10-15'),xml.replace('1.2','NaN'),xml.replace('1.2','-1')]:
   with self.assertRaises(ValueError):parse_ecb(bad,NOW)
 def test_sec_mapping_exact_exchange_and_ambiguous_identity(self):
  from reference_data import sec_listing_map
  m=sec_listing_map({'fields':['cik','ticker','exchange'],'data':[[1,'ABC','Nasdaq'],[2,'ABC','NYSE'],[3,'BAD','NYSE'],[4,'BAD','NYSE']]})
  self.assertEqual(m,{'NASDAQ:ABC':'1','NYSE:ABC':'2'})



class IdentityTests(unittest.TestCase):
 def test_exact_venue_and_share_class(self):
  from listing_identity import listing_matches,select_listing
  for query,bad in [('PKO.WA','NYSE:PKO'),('MBK.WA','ASX:MBK'),('SSNLF','NYSE:SSNI'),('BRK-B','NYSE:BRK.A'),('PBR-A','NYSE:ABR-PB'),('ALPHA.AT','MYX:ALPHA'),('UNKNOWN.ZZ','NYSE:UNKNOWN')]:
   self.assertFalse(listing_matches(query,bad))
   self.assertIsNone(select_listing(query,[{'symbol':bad,'is_primary':True}]))
  for query,good in [('PKO.WA','GPW:PKO'),('A5G.IR','EURONEXT:A5G'),('BRK-B','NYSE:BRK.B'),('SSNLF','OTC:SSNLF')]:self.assertTrue(listing_matches(query,good))
 def test_repaired_listing_does_not_inherit_wrong_company_metadata(self):
  index={}
  rows=select_registered_rows([{'ticker':'PKO.WA','listing_symbol':'NYSE:PKO','cik':'999','isin':'USWRONG','name':'Wrong company'}],index,'')
  self.assertEqual(rows,[{'ticker':'PKO.WA','listing_symbol':'GPW:PKO'}])
  self.assertEqual(index['identity_rejected']['PKO.WA']['rejected_listing'],'NYSE:PKO')

if __name__=='__main__':unittest.main()
