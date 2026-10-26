import datetime as dt,unittest
from financial_supply_policy import decision,fingerprint,make_plan
NOW=dt.datetime(2026,10,25,12,tzinfo=dt.timezone.utc)
ROW={'listing_symbol':'NASDAQ:MSFT','ticker':'MSFT','isin':'US5949181045','currency':'USD'}
B={'state':'partial','period':'2026-06-30','currency':'USD','profile':'corporate','reason':'missing_capex'}
def identity():return {k:ROW.get(k) for k in ('listing_symbol','ticker','isin','currency','security_type','share_class')}
def attempt(days=1,**kw):return {'at':(NOW-dt.timedelta(days=days)).isoformat(),'inputIdentity':identity(),'coverageSignature':fingerprint(ROW,B),**kw}
class Tests(unittest.TestCase):
 def test_new_and_new_period_immediate(self):
  self.assertTrue(decision(ROW,B,{}, {},NOW)['due'])
  self.assertTrue(decision(ROW,{**B,'period':'2026-09-30'}, {},attempt(.01),NOW)['due'])
 def test_persistent_missing_fields_weekly(self):
  self.assertFalse(decision(ROW,B,{},attempt(2),NOW)['due'])
  self.assertTrue(decision(ROW,B,{},attempt(7),NOW)['due'])
 def test_transient_failure_bounded(self):
  self.assertTrue(decision(ROW,B,{},attempt(1,error='provider_unavailable',consecutiveFailures=1),NOW)['due'])
  self.assertFalse(decision(ROW,B,{},attempt(2,error='provider_unavailable',consecutiveFailures=3),NOW)['due'])
  self.assertTrue(decision(ROW,B,{},attempt(7,error='provider_unavailable',consecutiveFailures=7),NOW)['due'])
 def test_used_source_refreshed_before_expiry(self):
  b={**B,'state':'available','reason':'annual_book_ratios','source':'ROIC v3 annual statements'}
  rec={'inputIdentity':identity(),'retrievedAt':(NOW-dt.timedelta(days=6)).isoformat()}
  a=attempt(.1,error='provider_unavailable',consecutiveFailures=6);a['coverageSignature']=fingerprint(ROW,b)
  self.assertTrue(decision(ROW,b,rec,a,NOW)['due'])
 def test_other_sources_not_needlessly_refetched(self):
  b={**B,'state':'available','source':'Yahoo annual statements'}
  self.assertEqual(decision(ROW,b,{},attempt(20),NOW)['reason'],'covered_by_other_source')
 def test_changed_identity_ignores_old_attempt(self):
  a=attempt(.01);a['inputIdentity']['isin']='changed'
  self.assertTrue(decision(ROW,B,{},a,NOW)['due'])
 def test_secondary_markets_deferred_and_invalid_identity_blocked(self):
  self.assertEqual(decision({**ROW,'listing_symbol':'GPW:TEST'},B,{}, {},NOW)['reason'],'deferred_other_market')
  self.assertEqual(decision({**ROW,'isin':'bad'},B,{}, {},NOW)['reason'],'identity_blocked')
 def test_future_or_malformed_attempt_cannot_block(self):
  for at in ['bad',(NOW+dt.timedelta(days=20)).isoformat()]:self.assertTrue(decision(ROW,B,{},attempt(at=at),NOW)['due'])
 def test_plan_contains_period_conflict_and_new_listings(self):
  c={'generatedAt':NOW.isoformat(),'stocks':[{'symbol':ROW['listing_symbol'],'domains':{'balance':B}}]}
  r={'stocks':{ROW['listing_symbol']:{'annual':{'end':'2025-06-30','fields':{}}}}}
  p=make_plan({'kandidaten':[ROW]},c,r,{},NOW)
  self.assertTrue(p['stocks'][0]['roic']['periodMismatch']);self.assertEqual(p['summary']['openMainMarketBalances'],1)
  self.assertEqual(make_plan({'kandidaten':[ROW]},{'generatedAt':NOW.isoformat()}, {},{},NOW)['summary']['dueRoic'],1)
 def test_duplicate_identity_conflict_never_due(self):
  p=make_plan({'kandidaten':[ROW,{**ROW,'isin':'US0378331005'}]}, {'generatedAt':NOW.isoformat()}, {},{},NOW)
  self.assertEqual(p['stocks'][0]['roic']['reason'],'conflicting_listing_identity');self.assertFalse(p['stocks'][0]['roic']['due'])
 def test_source_conflicts_are_routed_for_reconciliation(self):
  b={**B,'edinetReconciliation':{'state':'not_aligned','reasons':['cash_mismatch']}}
  p=make_plan({'kandidaten':[ROW]},{'generatedAt':NOW.isoformat(),'stocks':[{'symbol':ROW['listing_symbol'],'domains':{'balance':b}}]}, {},{},NOW)
  self.assertEqual(p['stocks'][0]['nextSource'],'reconcile_sources')
  self.assertEqual(p['stocks'][0]['edinet']['reconciliation']['reasons'],['cash_mismatch'])
 def test_preventive_fallback_does_not_wait_for_missing_state(self):
  b={**B,'state':'available','source':'Yahoo annual statements','refreshDue':True}
  self.assertTrue(decision(ROW,b,{}, {},NOW)['due'])
  self.assertEqual(decision(ROW,b,{}, {},NOW)['reason'],'preventive_fallback_refresh')
  self.assertFalse(decision(ROW,b,{},attempt(.2),NOW)['due'])
  self.assertTrue(decision(ROW,b,{},attempt(1),NOW)['due'])
 def test_preventive_identity_block_and_market_deferral_remain(self):
  b={**B,'state':'available','refreshDue':True}
  self.assertFalse(decision({**ROW,'isin':'bad'},b,{}, {},NOW)['due'])
  self.assertFalse(decision({**ROW,'listing_symbol':'GPW:A'},b,{}, {},NOW)['due'])
 def test_empty_archive_gets_one_migration_retry_without_repeated_bypass(self):
  rec={'inputIdentity':identity(),'annual':{'fields':{'total_assets':None,'cash':None}}}
  a=attempt(.1)
  self.assertEqual(decision(ROW,B,rec,a,NOW)['reason'],'repair_empty_legacy_archive')
  a['normalizationVersion']='nonempty-annual-v1';a['error']='empty_statement_values'
  self.assertFalse(decision(ROW,B,rec,a,NOW)['due'])
 def test_explicit_zero_record_does_not_trigger_empty_migration(self):
  rec={'inputIdentity':identity(),'annual':{'fields':{'total_assets':None,'total_debt':0}}}
  self.assertNotEqual(decision(ROW,B,rec,attempt(.1),NOW)['reason'],'repair_empty_legacy_archive')
 def test_original_source_plan_distinguishes_debt_review_from_auto_fetch(self):
  b={**B,'source':'EDINET annual XBRL','sourceSelection':'edinet_standalone_original_filing','reason':'missing_total_debt','metrics':{'fcfAssets':{'state':'available','value':.1}},'edinetReconciliation':{'state':'not_comparable'}}
  p=make_plan({'kandidaten':[ROW]},{'generatedAt':NOW.isoformat(),'stocks':[{'symbol':ROW['listing_symbol'],'domains':{'balance':b}}]}, {},{},NOW)
  item=p['stocks'][0]
  self.assertEqual(item['nextSource'],'original_debt_scope_review')
  self.assertEqual(item['automaticNextSource'],'ROIC')
  self.assertEqual(item['availableMetrics'],['fcfAssets'])
if __name__=='__main__':unittest.main()
