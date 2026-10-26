import datetime as dt
import unittest
from risk_workplan import build
NOW=dt.datetime(2026,10,25,20,tzinfo=dt.timezone.utc)
def coverage(rows):return {'generatedAt':NOW.isoformat(),'stocks':rows}
def row(symbol='NYSE:A',state='partial'):
 return {'symbol':symbol,'domains':{'identity':{'state':'available'},'historical':{'state':'available'},'sector':{'state':'available'},'balance':{'profile':'corporate','state':state,'reason':'missing_capex','sectorRequirements':[]}}}
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
if __name__=='__main__':unittest.main()
