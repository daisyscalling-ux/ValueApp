import datetime as dt
import unittest
import json,os,tempfile
from pathlib import Path
from unittest.mock import patch
from company_news import normalize,identifier
NOW=dt.datetime(2026,10,20,12,tzinfo=dt.timezone.utc)
class NewsTests(unittest.TestCase):
 def row(self,**changes):return dict({'title':'Example cuts outlook','article_url':'https://example.com/news?a=1&utm_source=x','published_date':'2026-10-20T10:00:00Z','site':'Example','article_text':'Do not publish'},**changes)
 def test_dedup_tags_no_body(self):
  r=normalize([self.row(),self.row(article_url='https://example.com/news?a=1&utm_source=y')],NOW)
  self.assertEqual(len(r['items']),1);i=r['items'][0]
  self.assertEqual(i['eventCandidates'],['earnings_warning']);self.assertNotIn('article_text',i)
  self.assertFalse(i['verified']);self.assertNotIn('utm_',i['url'])
 def test_old_future_undated_unsafe_rejected(self):
  r=normalize([self.row(published_date=d) for d in ['2020-01-01T00:00:00Z','2027-01-01T00:00:00Z','bad','2026-10-20T10:00:00']]+[self.row(article_url='javascript:alert(1)')],NOW)
  self.assertEqual(r['items'],[]);self.assertEqual(r['rejectedArticles'],5)
 def test_errors_not_successful_empty(self):
  with self.assertRaises(ValueError):normalize({'error':'quota'},NOW)
  self.assertEqual(normalize([],NOW)['items'],[])
 def test_no_ambiguous_ticker_fallback(self):
  self.assertIsNone(identifier({'ticker':'C'}))
  self.assertEqual(identifier({'cik':831001}),'0000831001')
  self.assertEqual(identifier({'isin':'US1729674242'}),'US1729674242')
 def test_cached_google_news_without_roic_id_survives_next_run(self):
  from company_news import main
  now=dt.datetime.now(dt.timezone.utc).isoformat()
  with tempfile.TemporaryDirectory() as folder:
   p=Path(folder)
   (p/'cf_universum.json').write_text(json.dumps({'kandidaten':[{'ticker':'RR.L','name':'Rolls-Royce Holdings plc'},{'ticker':'TEST','name':'Test Company'}]}))
   (p/'cf_company_news.json').write_text(json.dumps({'schema':1,'stocks':{'RR.L':{'source':'Google News · Suchindex','successAt':now,'items':[{'publishedAt':now,'title':'Rolls-Royce Holdings plc update'}]},'TEST':{'identifier':None,'items':[],'successAt':None,'fallbackAttemptAt':now,'googleAttemptAt':now,'googleError':'HTTPError'}}}),encoding='utf8')
   with patch.dict(os.environ,{'RISK_DATA_DIR':folder,'ROIC_API_KEY':'test'}),patch('google_company_news.collect') as google,patch('yahoo_company_news.collect') as yahoo:
    main();google.assert_not_called();yahoo.assert_not_called()
   result=json.loads((p/'cf_company_news.json').read_text(encoding='utf8'))
   self.assertEqual(len(result['stocks']['RR.L']['items']),1)
   self.assertEqual(result['stocks']['TEST']['googleAttemptAt'],now)
 def test_changed_identity_discards_old_news_and_forces_refresh(self):
  from company_news import main
  now=dt.datetime.now(dt.timezone.utc).isoformat()
  with tempfile.TemporaryDirectory() as folder:
   p=Path(folder)
   (p/'cf_universum.json').write_text(json.dumps({'kandidaten':[{'ticker':'RR.L','name':'New Company plc','currency':'GBP'}]}))
   (p/'cf_company_news.json').write_text(json.dumps({'schema':1,'stocks':{'RR.L':{'inputFingerprint':'previous-company','successAt':now,'items':[{'title':'OLD COMPANY','publishedAt':now}],'fallbackAttemptAt':now}}}))
   with patch.dict(os.environ,{'RISK_DATA_DIR':folder,'ROIC_API_KEY':'test'}),patch('google_company_news.collect',return_value={'rows':[],'rawArticleCount':0,'rejectedCandidates':0}),patch('yahoo_company_news.collect',side_effect=ValueError('yahoo_issuer_name_mismatch')) as yahoo:
    main();yahoo.assert_called_once()
   result=json.loads((p/'cf_company_news.json').read_text(encoding='utf8'))
   self.assertEqual(result['stocks']['RR.L']['items'],[])
   audit=json.loads((p/'cf_news_identity_audit.json').read_text(encoding='utf8'))
   self.assertEqual(audit['rows'][0]['state'],'rejected')
if __name__=='__main__':unittest.main()

