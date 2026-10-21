import unittest
from unittest.mock import patch
import subprocess
from yahoo_company_news import verify_profile,convert_news,collect,error_code,alias_revision,corrected_alias_retry

class YahooNewsTests(unittest.TestCase):
 def setUp(self):
  self.row={'ticker':'RR.L','name':'Rolls-Royce Holdings plc','currency':'GBP'}
  self.info={'symbol':'RR.L','longName':'Rolls-Royce Holdings plc','currency':'GBp','quoteType':'EQUITY'}
 def test_exact_issuer_and_pence(self):
  self.assertEqual(verify_profile(self.row,self.info)['symbol'],'RR.L')
 def test_wrong_issuer_currency_symbol_type_blocked(self):
  for changes in [{'longName':'Rolls-Royce Fund'},{'currency':'USD'},{'symbol':'RR'},{'quoteType':'ETF'}]:
   with self.assertRaises(ValueError):verify_profile(self.row,{**self.info,**changes})
 def test_current_news_shape_and_no_article_body(self):
  rows=convert_news([{'content':{'title':'Example','canonicalUrl':{'url':'https://example.com'},'pubDate':'2026-10-20T00:00:00Z','provider':{'displayName':'Publisher'},'summary':'Not retained'}}])
  self.assertEqual(rows[0]['site'],'Publisher');self.assertNotIn('summary',rows[0])
 def test_child_timeout_and_failure_not_empty_success(self):
  with patch('yahoo_company_news.subprocess.run',side_effect=subprocess.TimeoutExpired('child',18)):
   with self.assertRaises(subprocess.TimeoutExpired):collect(self.row)
  with patch('yahoo_company_news.subprocess.run',return_value=subprocess.CompletedProcess([],1,'','')):
   with self.assertRaises(ValueError):collect(self.row)
 def test_error_codes_never_expose_provider_messages(self):
  self.assertEqual(error_code(ValueError('secret=https://host?apikey=hidden')),'yahoo_provider_failure')
  for code in ['yahoo_issuer_name_mismatch','yahoo_currency_mismatch','yahoo_rate_limited']:
   with patch('yahoo_company_news.subprocess.run',return_value=subprocess.CompletedProcess([],1,'{"error":"'+code+'"}','')):
    with self.assertRaisesRegex(ValueError,code):collect(self.row)
 def test_alias_requires_listing_isin_and_other_checks(self):
  row={'ticker':'AI.PA','name':'Air Liquide SA','listing_symbol':'EURONEXT:AI','isin':'FR0000120073','currency':'EUR'}
  info={'symbol':'AI.PA','longName':"L'Air Liquide S.A.",'currency':'EUR','quoteType':'EQUITY'}
  self.assertEqual(verify_profile(row,info)['nameMatch'],'reviewed_provider_alias')
  for changes in [{'isin':'wrong'},{'listing_symbol':'OTHER:AI'},{'currency':'USD'},{'ticker':'AI'}]:
   with self.assertRaises(ValueError):verify_profile({**row,**changes},info)
 def test_alias_correction_retries_once_not_every_run(self):
  row={'name':'Bayerische Motoren Werke AG','listing_symbol':'XETR:BMW','isin':'DE0005190003'}
  old={'fallbackError':'yahoo_issuer_name_mismatch'}
  self.assertTrue(corrected_alias_retry(row,old))
  self.assertFalse(corrected_alias_retry(row,{**old,'fallbackAliasRevision':alias_revision(row)}))
  self.assertFalse(corrected_alias_retry({**row,'isin':'wrong'},old))
if __name__=='__main__':unittest.main()

