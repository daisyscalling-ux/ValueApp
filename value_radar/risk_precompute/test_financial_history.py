import copy,datetime as dt,unittest
from financial_history import build
class HistoryTests(unittest.TestCase):
 def setUp(self):
  self.now=dt.datetime(2026,10,31,tzinfo=dt.timezone.utc)
  self.u={'kandidaten':[{'listing_symbol':'NYSE:EX','ticker':'EX','isin':'US0378331005','currency':'USD','security_type':'common_stock'}]}
 def coverage(self,period='2025-12-31',value=.1,source='ROIC',now=None):
  now=now or self.now;ts=now.isoformat()
  m={'state':'available','value':value,'basis':{'period':period,'currency':'USD','retrievedAt':ts,'fields':{'total_assets':{'source':source,'end':period,'currency':'USD','retrievedAt':ts},'total_debt':{'source':source,'end':period,'currency':'USD','retrievedAt':ts}}}}
  return {'schema':1,'generatedAt':ts,'stocks':[{'symbol':'NYSE:EX','domains':{'identity':{'state':'available'},'balance':{'profile':'corporate','metrics':{'netDebtAssets':m}}}}]}
 def run_case(self,c,previous=None,now=None):return build(c,self.u,previous or {},now or self.now)
 def test_initial_period_not_a_trend_and_repeated_load_no_fake_period(self):
  c=self.coverage();a,r=self.run_case(c);self.assertEqual(r['stocks'][0]['domains']['balance']['history']['metrics'][0]['state'],'one_period')
  a2,r2=self.run_case(c,a);self.assertEqual(a['series'],a2['series']);self.assertNotIn('history',c['stocks'][0]['domains']['balance'])
 def test_distinct_annual_periods_and_percentage_points(self):
  earlier=self.now-dt.timedelta(days=360);a,_=self.run_case(self.coverage('2024-12-31',.2,now=earlier),now=earlier)
  _,r=self.run_case(self.coverage(),a);m=r['stocks'][0]['domains']['balance']['history']['metrics'][0]
  self.assertEqual(m['state'],'comparable');self.assertAlmostEqual(m['changePercentagePoints'],-10)
 def test_revision_is_preserved_not_a_second_period(self):
  a,_=self.run_case(self.coverage());tomorrow=self.now+dt.timedelta(days=1);a2,r=self.run_case(self.coverage(value=.2,now=tomorrow),a,tomorrow)
  m=r['stocks'][0]['domains']['balance']['history']['metrics'][0];self.assertEqual(m['periodCount'],1);self.assertEqual(m['revisionCount'],1)
  revisions=next(iter(a2['series'].values()))['periods']['2025-12-31']['revisions'];self.assertEqual([x['value'] for x in revisions],[.1,.2])
 def test_identity_or_source_change_never_borrow_prior_period(self):
  earlier=self.now-dt.timedelta(days=360);a,_=self.run_case(self.coverage('2024-12-31',.2,now=earlier),now=earlier)
  for source in ['Yahoo','ROIC']:
   if source=='ROIC':self.u['kandidaten'][0]['isin']='US5949181045'
   _,r=self.run_case(self.coverage(source=source),a);self.assertEqual(r['stocks'][0]['domains']['balance']['history']['metrics'][0]['state'],'one_period')
 def test_future_stale_missing_and_duplicate_inputs(self):
  for c in [self.coverage('2027-12-31'),self.coverage(value=float('nan')),self.coverage(value=True)]:
   _,r=self.run_case(c);self.assertEqual(r['stocks'][0]['domains']['balance']['history']['state'],'missing')
  self.u['kandidaten']*=2;a,r=self.run_case(self.coverage());self.assertFalse(a['series'])
 def test_period_gap_not_mislabelled_annual_change(self):
  earlier=self.now-dt.timedelta(days=720);a,_=self.run_case(self.coverage('2023-12-31',.2,now=earlier),now=earlier)
  _,r=self.run_case(self.coverage(),a);self.assertEqual(r['stocks'][0]['domains']['balance']['history']['metrics'][0]['state'],'period_gap')
 def test_changed_value_with_same_source_timestamp_is_quarantined(self):
  a,_=self.run_case(self.coverage());a2,r=self.run_case(self.coverage(value=.2),a);self.assertEqual(a2['summary']['conflictingOrOlderRevisions'],1);self.assertEqual(a['series'],a2['series'])
 def test_bad_archive_and_out_of_order_do_not_replace_history(self):
  with self.assertRaises(ValueError):self.run_case(self.coverage(),{'schema':2})
  a,_=self.run_case(self.coverage());earlier=self.now-dt.timedelta(days=1)
  with self.assertRaises(ValueError):self.run_case(self.coverage(now=earlier),a,earlier)
 def test_quarters_compare_only_same_regulatory_series(self):
  def quarter(period,value,now):
   c=self.coverage(now=now);c['stocks'][0]['domains']['balance']={'bankCapital':{'state':'available','period':period,'rssdId':'1','sourceImportedAt':now.isoformat(),'sourceUrl':'https://example.com','sourceFileSha256':'a'*64,'metrics':{'cet1_ratio':{'state':'available','unit':'fraction','value':value,'sourceField':'BHCAP793'}}}}
   return c
  earlier=dt.datetime(2026,7,1,tzinfo=dt.timezone.utc)
  a,_=self.run_case(quarter('2026-03-31',.1,earlier),now=earlier)
  _,r=self.run_case(quarter('2026-06-30',.11,self.now),a)
  m=r['stocks'][0]['domains']['balance']['history']['metrics'][0];self.assertEqual(m['frequency'],'quarterly');self.assertAlmostEqual(m['changePercentagePoints'],1)
 def test_corrupt_saved_history_is_rejected_not_overwritten(self):
  a,_=self.run_case(self.coverage());next(iter(a['series'].values()))['identity']['isin']='US5949181045'
  with self.assertRaises(ValueError):self.run_case(self.coverage(),a)
 def backfill(self):
  identity={k:self.u['kandidaten'][0].get(k) for k in ('listing_symbol','ticker','isin','currency','security_type','share_class')}
  balances=[self.coverage(str(y)+'-12-31',.1+(y-2020)*.01)['stocks'][0]['domains']['balance'] for y in range(2020,2026)]
  return {'schema':1,'method':'roic-history-balances-v1','generatedAt':self.now.isoformat(),'stocks':{'NYSE:EX':{'inputIdentity':identity,'balances':balances}}}
 def test_backfill_keeps_actual_observation_time_and_current_metrics(self):
  c=self.coverage(source='Yahoo');original=copy.deepcopy(c)
  a,r=build(c,self.u,{},self.now,self.backfill())
  m=r['stocks'][0]['domains']['balance']['history']['metrics'][0]
  self.assertEqual(m['state'],'comparable');self.assertEqual(m['sourceLabel'],'ROIC');self.assertEqual(len(m['points']),6)
  self.assertEqual(c,original);self.assertEqual(r['stocks'][0]['domains']['balance']['metrics'],original['stocks'][0]['domains']['balance']['metrics'])
  self.assertFalse(a['pointInTimeUsable'])
  for series in a['series'].values():
   for p in series['periods'].values():self.assertEqual(p['firstObservedAt'],self.now.isoformat())
  again,_=build(c,self.u,a,self.now,self.backfill());self.assertEqual(a['series'],again['series'])
 def test_stale_or_wrong_identity_backfill_is_not_borrowed(self):
  for kind in ('identity','timestamp','schema'):
   bf=self.backfill()
   if kind=='identity':bf['stocks']['NYSE:EX']['inputIdentity']['isin']='US5949181045'
   elif kind=='timestamp':bf['generatedAt']='2026-01-01T00:00:00+00:00'
   else:bf['schema']=2
   _,r=build(self.coverage(),self.u,{},self.now,bf)
   self.assertEqual(r['stocks'][0]['domains']['balance']['history']['metrics'][0]['periodCount'],1)
 def test_backfill_does_not_join_currency_changes_or_missing_years(self):
  bf=self.backfill();bs=bf['stocks']['NYSE:EX']['balances'];bs[:]=[bs[0],bs[-1]]
  b=bs[-1]['metrics']['netDebtAssets']['basis'];b['currency']='EUR'
  for field in b['fields'].values():field['currency']='EUR'
  _,r=build(self.coverage(source='Yahoo'),self.u,{},self.now,bf)
  self.assertFalse(any(m['state']=='comparable' for m in r['stocks'][0]['domains']['balance']['history']['metrics']))
 def test_annual_retention_is_twelve_periods(self):
  a={}
  for year in range(2011,2027):
   when=dt.datetime(year,10,31,tzinfo=dt.timezone.utc)
   a,_=self.run_case(self.coverage(str(year-1)+'-12-31',now=when),a,when)
  self.assertEqual(len(next(iter(a['series'].values()))['periods']),12)
if __name__=='__main__':unittest.main()
