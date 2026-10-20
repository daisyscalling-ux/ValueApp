import unittest
from unittest.mock import patch
import subprocess
from yahoo_company_news import verify_profile,convert_news,collect

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
if __name__=='__main__':unittest.main()
