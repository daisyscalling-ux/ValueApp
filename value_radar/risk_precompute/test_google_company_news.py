import datetime as dt
import unittest
from xml.sax.saxutils import escape
from google_company_news import parse_feed,query_name,headline_rejection,clean_cached

class GoogleTests(unittest.TestCase):
 def feed(self,title='SAP SE cuts guidance',date='Tue, 20 Oct 2026 10:00:00 GMT',link='https://news.google.com/rss/articles/test'):
  return ('<rss><channel><item><title>'+escape(title)+'</title><link>'+escape(link)+'</link><pubDate>'+date+'</pubDate><source>Publisher</source></item></channel></rss>').encode()
 def parse(self,**kw):return parse_feed(self.feed(**kw),'SAP SE',dt.datetime(2026,10,20,12,tzinfo=dt.timezone.utc))
 def test_relevant_headline_and_no_body(self):
  self.assertEqual(len(self.parse()['rows']),1)
  self.assertNotIn('description',self.parse()['rows'][0])
 def test_unrelated_boundary_and_landing_pages(self):
  for title in ['Other firm cuts guidance','SAP SEcurities fund grows','SAP SE Stock Price, News, Quote & History','Common equity to total deposits of SAP SE','SAP SE market is going to boom']:
   self.assertEqual(self.parse(title=title)['rows'],[])
 def test_dates_urls_schema(self):
  for kw in [{'date':'bad'},{'date':'Tue, 20 Oct 2020 10:00:00 GMT'},{'date':'Wed, 21 Oct 2026 10:00:00 GMT'},{'link':'https://evil.example/rss/articles/x'}]:
   self.assertEqual(self.parse(**kw)['rows'],[])
  with self.assertRaises(ValueError):parse_feed(b'<html/>','SAP SE',dt.datetime.now(dt.timezone.utc))
 def test_bare_ticker_not_a_query(self):
  with self.assertRaises(ValueError):query_name({'name':'C'})
 def test_real_landing_pages_removed_but_events_kept(self):
  for title in ['SAP SE (SAP) options chain','SAP SE (SAP)','SAP SE','SAP SE Stock Forum & Discussion','SAP SE Analyst Insights, Price Targets & Recommendations']:
   self.assertIsNotNone(headline_rejection(title,'SAP SE'))
  for title in ['SAP SE cuts earnings outlook','SAP SE shares rise as analysts raise target price','SAP SE executes buyback']:
   self.assertIsNone(headline_rejection(title,'SAP SE'))
 def test_cached_items_cleaned_idempotently(self):
  a={'stocks':{'SAP':{'source':'Google News · Suchindex','items':[{'title':'SAP SE options chain'},{'title':'SAP SE cuts guidance'}]}}}
  rows={'SAP':[{'name':'SAP SE'}]}
  self.assertEqual(clean_cached(a,rows),1)
  self.assertEqual(clean_cached(a,rows),0)
  self.assertEqual(len(a['stocks']['SAP']['items']),1)
if __name__=='__main__':unittest.main()

