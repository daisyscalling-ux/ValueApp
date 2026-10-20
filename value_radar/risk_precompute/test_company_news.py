import datetime as dt
import unittest
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
if __name__=='__main__':unittest.main()
