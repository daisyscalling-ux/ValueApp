import copy
import datetime as dt
import unittest
from yahoo_sector import profile, normalize_prices, run, identity, merge_recovered_series
from peer_groups import build

NOW=dt.datetime(2026,10,22,12,tzinfo=dt.timezone.utc)
ROW={'ticker':'MSFT','listing_symbol':'NASDAQ:MSFT','exchange':'NASDAQ','isin':'US5949181045',
 'currency':'USD','name_full':'Microsoft Corporation','security_type':'stock',
 'industry':'Packaged software','metadata_asof':NOW.isoformat()}
INFO={'symbol':'MSFT','longName':'Microsoft Corporation','currency':'USD','quoteType':'EQUITY','exchange':'NMS',
 'sectorKey':'technology','industryKey':'software-infrastructure','industry':'Software - Infrastructure'}
META={'symbol':'MSFT','currency':'USD','instrumentType':'EQUITY','exchangeName':'NMS'}
PRICES=[((NOW-dt.timedelta(days=i)).date().isoformat(),100+i/100) for i in range(550,0,-1)
        if (NOW-dt.timedelta(days=i)).weekday()<5]
RULES={'aliases':{},'reviewed':[]}

class YahooSectorTests(unittest.TestCase):
 def test_new_venue_mapping_retries_old_venue_failure_only_once(self):
  row={**ROW,'ticker':'PKO.WA','listing_symbol':'GPW:PKO','exchange':'GPW',
       'isin':'PLPKO0000016','currency':'PLN','name_full':'PKO Bank Polski SA'}
  def archive(error):return {'schema':1,'profiles':{},'attempts':{'GPW:PKO':
     {'at':NOW.isoformat(),'inputIdentity':identity(row),'error':error}}}
  calls=[]
  def fail(req,timeout):
   calls.append(req);raise ValueError('yahoo_ambiguous_listing')
  a,c=run({'kandidaten':[row]},archive('yahoo_ambiguous_listing'),{},NOW,fail)
  self.assertEqual(len(calls),1)
  self.assertEqual(a['attempts']['GPW:PKO']['venueCodes'],['WSE'])
  run({'kandidaten':[row]},a,c,NOW,lambda *_:self.fail('second mapping retry'))
  for error in ('yahoo_issuer_name_mismatch','yahoo_rate_limited','yahoo_timeout'):
   run({'kandidaten':[row]},archive(error),{},NOW,lambda *_:self.fail('unrelated cooldown bypassed'))
 def test_polish_and_greek_profiles_and_prices_require_exact_listing(self):
  cases=[('PKO.WA','GPW:PKO','PLPKO0000016','PLN','PKO Bank Polski SA','WSE'),
         ('ETE.AT','ATHEX:ETE','GRS003003035','EUR','National Bank of Greece S.A.','ATH')]
  for ticker,listing,isin,ccy,name,venue in cases:
   with self.subTest(listing=listing):
    row={**ROW,'ticker':ticker,'listing_symbol':listing,'exchange':listing.split(':')[0],
         'isin':isin,'currency':ccy,'name_full':name}
    info={**INFO,'symbol':ticker,'currency':ccy,'longName':name,'exchange':venue}
    meta={**META,'symbol':ticker,'currency':ccy,'exchangeName':venue}
    self.assertEqual(profile(row,info,now=NOW)['inputIdentity'],identity(row))
    self.assertEqual(normalize_prices(row,meta,PRICES,NOW)['symbol'],listing)
    for change in [{'exchange':'NYQ'},{'exchange':'ATH' if venue=='WSE' else 'WSE'},
                   {'symbol':'OTHER'},{'currency':'USD'},{'quoteType':'ETF'},{'longName':'Unrelated Corporation'}]:
     with self.assertRaises(ValueError):profile(row,{**info,**change},now=NOW)
    for change in [{'exchangeName':'NYQ'},{'exchangeName':'ATH' if venue=='WSE' else 'WSE'},
                   {'symbol':'OTHER'},{'currency':'USD'},{'instrumentType':'ETF'}]:
     with self.assertRaises(ValueError):normalize_prices(row,{**meta,**change},PRICES,NOW)
    with self.assertRaises(ValueError):profile({**row,'isin':'invalid'},info,now=NOW)
    with self.assertRaises(ValueError):profile({**row,'ticker':ticker.split('.')[0]+'.DE'},info,now=NOW)
    with self.assertRaises(ValueError):normalize_prices(row,meta,PRICES[-20:],NOW)
 def test_recovery_keeps_observation_date_and_rejects_stale_changed_or_bad_series(self):
  h=normalize_prices(ROW,META,PRICES,NOW);h['inputIdentity']=identity(ROW)
  u={'kandidaten':[ROW]}
  def merge(v):return merge_recovered_series(u,{}, {'schema':1,'series':{'NASDAQ:MSFT':v}},NOW)['series']
  self.assertEqual(merge(h)['NASDAQ:MSFT'],h)
  for change in [{'retrievedAt':(NOW-dt.timedelta(days=2)).isoformat()},{'inputIdentity':{}},{'currency':'EUR'},{'points':PRICES[-10:]},{'points':PRICES+[(PRICES[-1][0],-5)]}]:
   self.assertEqual(merge({**h,**change}),{})
  newer={**h,'retrievedAt':(NOW+dt.timedelta(minutes=5)).isoformat()}
  cache={'schema':1,'series':{'NASDAQ:MSFT':newer}}
  out=merge_recovered_series(u,cache,{'schema':1,'series':{'NASDAQ:MSFT':h}},NOW+dt.timedelta(minutes=10))
  self.assertEqual(out['series']['NASDAQ:MSFT'],newer)
 def test_profile_exact_venue_and_identity(self):
  p=profile(ROW,INFO,now=NOW);self.assertEqual(p['industryKey'],'software-infrastructure')
  for change in [{'exchange':'NYQ'},{'currency':'EUR'},{'longName':'Other Company'},{'symbol':'OTHER'},{'quoteType':'ETF'}]:
   with self.assertRaises(ValueError):profile(ROW,{**INFO,**change},now=NOW)
 def test_unknown_industry_is_not_guessed(self):
  p=profile(ROW,{**INFO,'industryKey':None},now=NOW);self.assertIsNone(p['industryKey'])
 def test_bad_isin_and_venue_mapping_rejected(self):
  for change in [{'isin':'bad'},{'ticker':'MSFT.DE'},{'listing_symbol':'UNKNOWN:MSFT'}]:
   with self.assertRaises(ValueError):profile({**ROW,**change},INFO,now=NOW)
 def test_adjusted_history_validation(self):
  s=normalize_prices(ROW,META,PRICES,NOW);self.assertLessEqual(len(s['points']),400)
  for prices in [PRICES[-100:],PRICES+[(PRICES[-1][0],-1)],PRICES+[(PRICES[-1][0],999)],PRICES[:-100]]:
   with self.assertRaises(ValueError):normalize_prices(ROW,META,prices,NOW)
  with self.assertRaises(ValueError):normalize_prices(ROW,{**META,'exchangeName':'NYQ'},PRICES,NOW)
 def test_refresh_only_missing_history_and_keep_roic(self):
  existing=normalize_prices(ROW,META,PRICES,NOW);existing['provider']='ROIC'
  calls=[]
  def fetch(req,timeout):
   calls.append(req);return {'profile':profile(req['row'],INFO,req['original'],NOW)}
  a,c=run({'kandidaten':[ROW]}, {}, {'schema':1,'series':{'NASDAQ:MSFT':existing}},NOW,fetch)
  self.assertFalse(calls[0]['history']);self.assertEqual(c['series']['NASDAQ:MSFT']['provider'],'ROIC')
  run({'kandidaten':[ROW]},a,c,NOW,lambda *_:self.fail('fresh profile fetched again'))
 def test_fallback_preserves_profile_when_history_fails(self):
  def fetch(req,t):return {'profile':profile(req['row'],INFO,req['original'],NOW),'historyError':'insufficient_history'}
  a,c=run({'kandidaten':[ROW]}, {}, {},NOW,fetch)
  self.assertIn('NASDAQ:MSFT',a['profiles']);self.assertFalse(c['series'])
  self.assertEqual(a['report']['errors']['insufficient_history'],1)
  run({'kandidaten':[ROW]},a,c,NOW,lambda *_:self.fail('cooldown ignored'))
 def test_failed_or_changed_identity_not_reused(self):
  a,_=run({'kandidaten':[ROW]}, {}, {},NOW,lambda *_:(_ for _ in ()).throw(ValueError('yahoo_issuer_name_mismatch')))
  self.assertFalse(a['profiles']);self.assertEqual(a['report']['errors']['yahoo_issuer_name_mismatch'],1)
 def test_provider_classification_identity_and_age(self):
  p=profile(ROW,INFO,now=NOW);supp={'profiles':{'NASDAQ:MSFT':p}}
  r=build({'kandidaten':[ROW]},NOW,RULES,supp);self.assertEqual(r['issuers'][0]['classification']['level'],'provider_subindustry')
  for change in [{'retrievedAt':'2020-01-01T00:00:00Z'},{'inputIdentity':{}},{'source':'unknown'}]:
   bad={'profiles':{'NASDAQ:MSFT':{**p,**change}}}
   self.assertEqual(build({'kandidaten':[ROW]},NOW,RULES,bad)['issuers'][0]['classification']['level'],'industry_context')
 def test_conflicting_provider_classifications_quarantined(self):
  second={**ROW,'listing_symbol':'NYSE:MSFT','exchange':'NYSE'}
  p=profile(ROW,INFO,now=NOW);q={**p,'inputIdentity':identity(second),'industryKey':'banks'}
  r=build({'kandidaten':[ROW,second]},NOW,RULES,{'profiles':{'NASDAQ:MSFT':p,'NYSE:MSFT':q}})
  self.assertEqual(r['summary']['reviewListings'],2)
 def test_partial_progress_rotates_and_rate_limit_stops(self):
  second={**ROW,'ticker':'AAPL','listing_symbol':'NASDAQ:AAPL','name_full':'Apple Inc.','isin':'US0378331005'}
  a,_=run({'kandidaten':[ROW,second]}, {}, {},NOW,lambda *_:(_ for _ in ()).throw(ValueError('yahoo_rate_limited')))
  self.assertEqual(a['report']['attempted'],1);self.assertEqual(a['report']['pending'],1)
 def test_invalid_duplicates_do_not_trigger_provider(self):
  a,_=run({'kandidaten':[ROW,ROW]}, {}, {},NOW,lambda *_:self.fail('duplicate fetched'))
  self.assertEqual(a['report']['identityBlocked'],2)
 def test_empty_input_does_not_clear_saved_data(self):
  with self.assertRaises(ValueError):run({}, {}, {},NOW)
 def test_reviewed_business_model_keeps_precedence(self):
  from peer_groups import name_key
  rules=copy.deepcopy(RULES)
  rules['reviewed']=[{'isins':[ROW['isin']],'names':[name_key(ROW)],'group':'reviewed',
   'label':'Reviewed','source':'https://example.com','reviewedAt':'2026-01-01','validUntil':'2026-12-31'}]
  r=build({'kandidaten':[ROW]},NOW,rules,{'profiles':{'NASDAQ:MSFT':profile(ROW,INFO,now=NOW)}})
  self.assertEqual(r['issuers'][0]['classification']['group'],'model:reviewed')
 def test_progress_saved_for_every_attempt(self):
  saved=[]
  a,_=run({'kandidaten':[ROW]}, {}, {},NOW,lambda *_:(_ for _ in ()).throw(ValueError('yahoo_issuer_name_mismatch')),
   checkpoint=lambda a,c:saved.append(copy.deepcopy(a)))
  self.assertEqual(saved[0]['report']['attempted'],1)
  self.assertEqual(saved[0]['attempts'],a['attempts'])
 def test_fresh_but_calendar_defective_history_gets_fallback(self):
  existing=normalize_prices(ROW,META,PRICES,NOW)
  saved={'schema':1,'profiles':{'NASDAQ:MSFT':profile(ROW,INFO,now=NOW)},'attempts':{}}
  calls=[]
  def fetch(req,t):calls.append(req);return {'profile':profile(req['row'],INFO,req['original'],NOW),'series':existing}
  run({'kandidaten':[ROW]},saved,{'schema':1,'series':{'NASDAQ:MSFT':existing}},NOW,fetch,calendar_retry={'NASDAQ:MSFT'})
  self.assertTrue(calls[0]['history'])
 def test_metadata_only_never_requests_history(self):
  calls=[]
  def fetch(req,t):calls.append(req);return {'profile':profile(req['row'],INFO,req['original'],NOW)}
  a,c=run({'kandidaten':[ROW]}, {}, {},NOW,fetch,metadata_only=True,calendar_retry={'NASDAQ:MSFT'})
  self.assertFalse(calls[0]['history']);self.assertFalse(c['series'])
  run({'kandidaten':[ROW]},a,{},NOW,lambda *_:self.fail('profile unnecessarily fetched'),metadata_only=True)

if __name__=='__main__':unittest.main()


