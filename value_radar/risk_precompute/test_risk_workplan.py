import datetime as dt
import unittest
from risk_workplan import build
NOW=dt.datetime(2026,10,25,20,tzinfo=dt.timezone.utc)
def coverage(rows):return {'generatedAt':NOW.isoformat(),'stocks':rows}
def row(symbol='NYSE:A',state='partial'):
 return {'symbol':symbol,'domains':{'quote':{'state':'available'},'price':{'state':'available'},'market':{'state':'available'},'identity':{'state':'available'},'historical':{'state':'available'},'sector':{'state':'available'},'balance':{'profile':'corporate','state':state,'reason':'missing_capex','sectorRequirements':[]}}}
class Workplan(unittest.TestCase):
 def test_groups_not_individual_jobs(self):
  r=build(coverage([row(),row('NYSE:B')]),NOW);self.assertEqual(len(r['batches']),1);self.assertEqual(r['batches'][0]['listings'],2)
 def test_sector_pending_survives_context_only(self):
  a=row(state='context_only');a['domains']['balance']['sectorRequirements']=['CET1']
  r=build(coverage([a]),NOW);self.assertEqual(r['batches'][0]['kind'],'sector_framework');self.assertNotIn('score',r)
 def test_source_conflicts_and_auxiliary_values_are_separate(self):
  a=row(state='available');b=a['domains']['balance'];b['edinetReconciliation']={'state':'not_aligned','reasons':['cash_mismatch']};b['supplementalMetrics']={'cashAssets':{'state':'available','value':.2}}
  r=build(coverage([a]),NOW);self.assertEqual(r['batches'][0]['kind'],'source_reconciliation');self.assertEqual(r['summary']['supplementalObservations'],{'cashAssets':1})
 def test_smaller_markets_kept_last(self):
  r=build(coverage([row('GPW:A'),row('LSE:B'),row('TSE:1234')]),NOW);self.assertEqual([g['marketTier'] for g in r['batches']],[0,1,2])
 def test_duplicate_and_stale_reports_blocked(self):
  self.assertEqual(build(coverage([row(),row()]),NOW)['state'],'blocked')
  c=coverage([row()]);c['generatedAt']='2020-01-01';self.assertEqual(build(c,NOW)['state'],'blocked')
 def test_multiple_reasons_not_double_counted_as_companies(self):
  a=row();a['domains']['balance']['reason']='missing_capex,missing_total_debt,missing_capex';r=build(coverage([a]),NOW)
  self.assertEqual(r['summary']['listingsWithOpenWork'],1);self.assertEqual(len(r['batches']),2)
 def test_broad_and_industry_context_do_not_upgrade_strict_peer_count(self):
  a=row(state='available');a['domains']['sector']={'state':'missing','reason':'few_peers','industryContext':{'state':'available'},'broaderContext':{'state':'available'}}
  r=build(coverage([a]),NOW);counts=r['summary']['peerContextCoverage']
  self.assertEqual(counts['any_context'],1);self.assertNotIn('strict',counts);self.assertTrue(any(g['kind']=='sector' for g in r['batches']))
 def test_replaced_unavailable_source_is_not_an_unresolved_conflict(self):
  a=row(state='available');a['domains']['balance']['edinetReconciliation']={'state':'not_comparable','reasons':['previous_primary_statement_unavailable']}
  r=build(coverage([a]),NOW);self.assertEqual(r['summary']['listingsWithOpenWork'],0)
 def test_progress_never_claims_total_completion(self):
  r=build(coverage([row(state='available')]),NOW)['progress']
  self.assertIsNone(r['completionPercent']);self.assertEqual(len(r['unverifiedCompletionGates']),4)
 def test_context_only_not_full_financial_coverage(self):
  a=row(state='context_only');a['domains']['balance']['sectorRequirements']=['CET1']
  r=build(coverage([a]),NOW)['progress']['scopes']['all']
  self.assertEqual(r['balance_complete']['available'],0);self.assertEqual(r['balance_basic_or_context']['percent'],100)
 def test_joint_coverage_requires_every_domain_and_identity(self):
  a=row(state='available');a['domains'].update(quote={'state':'available'},market={'state':'available'})
  b=row('NYSE:B','available');b['domains'].update(quote={'state':'available'},market={'state':'available'},identity={'state':'blocked'})
  r=build(coverage([a,b]),NOW)['progress']['scopes']['all'];self.assertEqual(r['core_data_together']['percent'],50)
 def test_blocks_deduplicate_reasons_and_keep_deferred_markets(self):
  a=row();a['domains']['balance']['reason']='missing_capex,missing_total_debt'
  r=build(coverage([a,row('GPW:B')]),NOW)['progress'];b=r['remainingBlocks'][0]
  self.assertEqual(b['mainMarketListings'],1);self.assertEqual(b['deferredMarketListings'],1)
  self.assertEqual(r['scopes']['mainMarkets']['identity']['total'],1)
 def test_empty_scope_has_no_percentage(self):
  r=build(coverage([row('GPW:B')]),NOW)['progress']['scopes']['mainMarkets']
  self.assertIsNone(r['identity']['percent'])
 def test_news_not_counted_as_verified_and_context_not_strict(self):
  a=row();a['domains']['news']={'state':'review_required'};a['domains']['sector']={'state':'missing','broaderContext':{'state':'available'},'industryContext':{'state':'available'}}
  r=build(coverage([a]),NOW)['progress']['scopes']['all'];self.assertEqual(r['sector']['available'],0)
  self.assertEqual(r['any_peer_context']['available'],1);self.assertEqual(r['newsStates'],{'review_required':1})
 def test_fx_context_counts_as_context_not_strict_peer_completion(self):
  a=row(state='available');a['domains']['sector']={'state':'missing','currencyAdjustedContext':{'state':'available'}}
  r=build(coverage([a]),NOW);p=r['progress']['scopes']['all']
  self.assertEqual(p['currency_adjusted_context']['available'],1);self.assertEqual(p['any_peer_context']['available'],1)
  self.assertEqual(p['sector']['available'],0);self.assertTrue(any(b['kind']=='sector' for b in r['batches']))
 def test_missing_quotes_and_market_proxies_are_actionable_blocks(self):
  a=row(state='available');a['domains']['quote']={'state':'missing'};a['domains']['market']={'state':'unsupported'}
  r=build(coverage([a]),NOW);self.assertEqual({b['kind'] for b in r['batches']},{'quote','market'})
 def test_summary_contains_denominators_and_limits(self):
  from risk_progress import markdown
  text=markdown(build(coverage([row()]),NOW)['progress'])
  self.assertIn('1/1',text);self.assertIn('kein Fertigstellungsgrad',text);self.assertIn('Endabnahme',text)
if __name__=='__main__':unittest.main()
