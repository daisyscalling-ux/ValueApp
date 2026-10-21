import datetime as dt
import json
from pathlib import Path
import sys
import unittest
import tempfile,os,time
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from listing_reference import apply_reference
from peer_metadata import metadata
from news_supply import yahoo_due,coverage_plan
from news_identity import prepare_universe,identity_fingerprint
from yahoo_company_news import verify_profile
NOW=dt.datetime(2026,10,21,12,tzinfo=dt.timezone.utc)
class SupplyTests(unittest.TestCase):
 def row(self):return {'ticker':'KESKOB.HE','listing_symbol':'HEL:KESKOB','exchange':'HEL','currency':'EUR','isin':'FI0009007900','name_full':'Kesko Oyj Class A','price':21.5,'fair_value':30}
 def test_reference_changes_only_identity(self):
  r=apply_reference(self.row(),NOW.date())
  self.assertEqual(r['isin'],'FI0009000202');self.assertEqual(r['share_class'],'B')
  self.assertEqual(r['price'],21.5);self.assertEqual(r['fair_value'],30)
  self.assertEqual(r['listing_reference_original']['isin'],'FI0009007900')
  self.assertEqual(apply_reference(r,NOW.date()),r)
  prepare_universe([r]);self.assertEqual(verify_profile(r,{'symbol':'KESKOB.HE','currency':'EUR','quoteType':'EQUITY','longName':'Kesko Oyj','shortName':'Kesko Corporation B'})['nameMatch'],'exact')
 def test_reference_fails_closed(self):
  for changes in [{'ticker':'KESKOA.HE'},{'currency':'USD'},{'isin':'wrong'}]:
   r=apply_reference({**self.row(),**changes},NOW.date());self.assertEqual(r['listing_reference_status'],'input_mismatch');prepare_universe([r]);self.assertTrue(r['_newsIdentityBlocked'])
  self.assertEqual(apply_reference(self.row(),dt.date(2028,1,1))['listing_reference_status'],'expired')
 def test_listing_isin_has_priority(self):
  r=metadata({'isin':'FI0009007900','name':'Kesko Oyj Class A'},{'isin':'FI0009000202','name':'Kesko Oyj Class B','symbol':'HEL:KESKOB'})
  self.assertEqual(r['isin'],'FI0009000202');self.assertEqual(r['name_full'],'Kesko Oyj Class B')
  self.assertIn('profile_listing_isin_conflict',r['metadata_identity_issues'])
 def test_fingerprint_compatible_for_unchanged_rows(self):
  import hashlib
  r={'ticker':'TEST','name':'Test Company'}
  fields=['ticker','listing_symbol','exchange','isin','currency','name_full','name','_newsNameCollision','_newsIdentityBlocked']
  expected=hashlib.sha256(json.dumps({k:r.get(k) for k in fields},sort_keys=True).encode()).hexdigest()
  self.assertEqual(identity_fingerprint(r),expected)
 def test_retry_intervals_and_correction_override(self):
  old={'fallbackAttemptAt':(NOW-dt.timedelta(hours=24)).isoformat(),'yahooResult':{'acceptedArticles':0}}
  self.assertFalse(yahoo_due(old,NOW));self.assertTrue(yahoo_due(old,NOW,True))
  self.assertTrue(yahoo_due(old,NOW+dt.timedelta(days=3)))
  self.assertFalse(yahoo_due({**old,'fallbackError':'yahoo_share_class_conflict'},NOW+dt.timedelta(days=2)))
 def test_coverage_distinguishes_pending_error_empty(self):
  rows=[{'ticker':x} for x in ['A','B','C']]
  archive={'stocks':{'B':{'googleAttemptAt':NOW.isoformat(),'googleError':'http_503'},'C':{'googleAttemptAt':NOW.isoformat(),'googleResult':{'acceptedArticles':0}}}}
  summary=coverage_plan(rows,archive,NOW)['summary']
  self.assertEqual(summary,{'google_not_attempted':1,'google_fetch_failed':1,'google_checked_no_eligible_article':1})
 def test_google_recovery_avoids_unnecessary_yahoo_call(self):
  from company_news import main
  now=dt.datetime.now(dt.timezone.utc).isoformat()
  with tempfile.TemporaryDirectory() as folder:
   p=Path(folder)
   (p/'cf_universum.json').write_text(json.dumps({'kandidaten':[{'ticker':'TEST','name':'Test Company'}]}))
   article={'title':'Test Company raises outlook','article_url':'https://news.google.com/rss/articles/example','published_date':now,'site':'Publisher'}
   def delayed_google(row, observed_at):
    time.sleep(.02)
    return {'rows':[article],'rawArticleCount':1,'rejectedCandidates':0}
   with patch.dict(os.environ,{'RISK_DATA_DIR':folder,'ROIC_API_KEY':'test'}),patch('google_company_news.collect',side_effect=delayed_google) as google,patch('yahoo_company_news.collect') as yahoo:
    main();google.assert_called_once();yahoo.assert_not_called()
   result=json.loads((p/'cf_company_news.json').read_text(encoding='utf8'))
   self.assertEqual(result['report']['googleRecoveredListings'],1)
if __name__=='__main__':unittest.main()

