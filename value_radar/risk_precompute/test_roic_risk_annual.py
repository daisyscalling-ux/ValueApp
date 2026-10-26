import copy
import datetime as dt
import unittest
import urllib.error
from roic_risk_annual import identity,normalize,run,safe_error

NOW=dt.datetime(2026,10,24,12,tzinfo=dt.timezone.utc)
ROW={'listing_symbol':'NASDAQ:MSFT','ticker':'MSFT','isin':'US5949181045','currency':'USD'}
def payloads():
 base={'symbol':ROW['listing_symbol'],'period_type':'annual','period_end_date':'2026-06-30','currency':'USD','fx_applied':False}
 return {k:{'data':[{**base,**fields}]} for k,fields in {
  'balance':{'bs_tot_asset':100,'bs_cash_near_cash_item':20,'bs_eqty_bef_minority_int_detailed':40,'bs_st_borrow':0,'bs_lt_borrow':30},
  'cashflow':{'cf_cash_from_oper':10,'cf_cap_expenditures':-3},'income':{'is_net_income':8}}.items()}
def coverage(now=NOW):return {'generatedAt':now.isoformat(),'stocks':[{'symbol':ROW['listing_symbol'],'domains':{'balance':{'state':'partial'}}}]}
def fetch(symbol,endpoint,timeout):return payloads()[{'balance-sheet':'balance','cash-flow':'cashflow','income-statement':'income'}[endpoint]]
class Tests(unittest.TestCase):
 def test_migration_of_cached_empty_record_runs_despite_yesterdays_success(self):
  s=run({'kandidaten':[ROW]},coverage(),{},fetch,NOW)
  s['stocks'][ROW['listing_symbol']]['annual']['fields']={k:None for k in s['stocks'][ROW['listing_symbol']]['annual']['fields']}
  s['attempts'][ROW['listing_symbol']].pop('normalizationVersion',None)
  result=run({'kandidaten':[ROW]},coverage(),s,fetch,NOW)
  self.assertEqual(result['report']['updated'],1);self.assertEqual(result['stocks'][ROW['listing_symbol']]['annual']['fields']['total_assets'],100)
  self.assertEqual(result['attempts'][ROW['listing_symbol']]['normalizationVersion'],'nonempty-annual-v1')

 def test_empty_new_year_selects_actually_returned_older_period(self):
  p=payloads();p['balance']['data'].insert(0,{'symbol':ROW['listing_symbol'],'period_type':'annual','period_end_date':'2026-09-30','currency':'USD','fx_applied':False})
  a=normalize(ROW,p,NOW);self.assertEqual(a['end'],'2026-06-30');self.assertEqual(a['fields']['total_assets'],100);self.assertEqual(a['skippedEmptyPeriods'],['2026-09-30'])
 def test_empty_only_response_retains_old_record_without_redating(self):
  first=run({'kandidaten':[ROW]},coverage(),{},fetch,NOW)
  before=copy.deepcopy(first['stocks'][ROW['listing_symbol']])
  later=NOW+dt.timedelta(days=8)
  def empty(symbol,endpoint,timeout):return {'data':[{'symbol':symbol,'period_type':'annual','period_end_date':'2026-09-30','currency':'USD','fx_applied':False}]}
  r=run({'kandidaten':[ROW]},coverage(later),first,empty,later)
  self.assertEqual(r['stocks'][ROW['listing_symbol']],before);self.assertEqual(r['attempts'][ROW['listing_symbol']]['error'],'empty_statement_values')
 def test_real_partial_new_period_not_hidden_by_old_complete_statement(self):
  p=payloads();p['balance']['data'].insert(0,{'symbol':ROW['listing_symbol'],'period_type':'annual','period_end_date':'2026-09-30','currency':'USD','fx_applied':False,'bs_tot_asset':120})
  a=normalize(ROW,p,NOW);self.assertEqual(a['end'],'2026-09-30');self.assertIsNone(a['fields']['capex']);self.assertEqual(a['fields']['total_assets'],120)

 def test_preventive_target_is_downloaded_and_daily_cooldown_applies(self):
  c=coverage();c['stocks'][0]['domains']['balance'].update(state='available',source='Yahoo annual statements',refreshDue=True)
  state=run({'kandidaten':[ROW]},c,{},fetch,NOW)
  self.assertEqual(state['report']['updated'],1)
  second=run({'kandidaten':[ROW]},c,state,lambda *a:self.fail('cooldown'),NOW)
  self.assertEqual(second['report'].get('updated',0),0)

 def test_values_and_provenance(self):
  a=normalize(ROW,payloads(),NOW)
  self.assertEqual(a['fields'],{'total_assets':100,'cash':20,'equity':40,'net_income':8,'operating_cashflow':10,'total_debt':30,'capex':3})
  self.assertEqual(a['field_sources']['total_debt']['components']['bs_st_borrow'],0)
  for s in a['field_sources'].values():self.assertEqual((s['end'],s['currency']),('2026-06-30','USD'))
 def test_debt_requires_both_and_no_inferred_zero(self):
  for v in [None,-1,'0',True,float('nan')]:
   p=payloads();p['balance']['data'][0]['bs_st_borrow']=v
   self.assertIsNone(normalize(ROW,p,NOW)['fields']['total_debt'])
 def test_capex_aggregates_and_components(self):
  for extra,expected in [({'cf_acquis_fxd_and_intang_detailed':-4},4),({'cf_purchase_of_fixed_prod_assets':-4,'cf_acquisition_of_intang_assets':0},4),({'cf_purchase_of_fixed_prod_assets':-4},None),({'cf_cash_from_inv':-4},None),({'cf_purchase_of_fixed_prod_assets':-4,'cf_acquisition_of_intang_assets':1},None)]:
   p=payloads();r=p['cashflow']['data'][0];r.pop('cf_cap_expenditures');r.update(extra)
   self.assertEqual(normalize(ROW,p,NOW)['fields']['capex'],expected)
 def test_capex_invalid_positive_is_not_abs(self):
  p=payloads();p['cashflow']['data'][0].update(cf_cap_expenditures=3,cf_acquis_fxd_and_intang_detailed=-4)
  self.assertIsNone(normalize(ROW,p,NOW)['fields']['capex'])
 def test_explicit_zero_is_preserved(self):
  p=payloads();p['cashflow']['data'][0]['cf_cap_expenditures']=0
  self.assertEqual(normalize(ROW,p,NOW)['fields']['capex'],0)
 def test_reject_wrong_balance_identity_period_currency_or_conversion(self):
  for change in [{'symbol':'NYSE:OTHER'},{'period_type':'quarterly'},{'fx_applied':True},{'fx_applied':None},{'currency':'US'},{'period_end_date':'2027-01-01'},{'period_end_date':'2024-01-01'}]:
   p=payloads();p['balance']['data'][0].update(change)
   with self.assertRaisesRegex(ValueError,'eligible_balance_missing'):normalize(ROW,p,NOW)
 def test_cashflow_must_match_period_and_reporting_currency(self):
  for change in [{'period_end_date':'2025-06-30'},{'currency':'EUR'},{'symbol':'NYSE:OTHER'}]:
   p=payloads();p['cashflow']['data'][0].update(change)
   self.assertIsNone(normalize(ROW,p,NOW)['fields']['operating_cashflow'])
 def test_newest_balance_not_older_complete_period(self):
  p=payloads();p['balance']['data'].append({**p['balance']['data'][0],'period_end_date':'2026-09-30'})
  a=normalize(ROW,p,NOW);self.assertEqual(a['end'],'2026-09-30');self.assertIsNone(a['fields']['capex'])
 def test_conflicting_same_period_rejected(self):
  p=payloads();p['balance']['data'].append({**p['balance']['data'][0],'bs_tot_asset':999})
  with self.assertRaisesRegex(ValueError,'conflicting_statement_period'):normalize(ROW,p,NOW)
 def test_run_checkpoint_and_cooldown(self):
  saves=[];s=run({'kandidaten':[ROW]},coverage(),{},fetch,NOW,checkpoint=lambda s:saves.append(copy.deepcopy(s)))
  self.assertEqual(len(saves),1);self.assertEqual(s['report']['updated'],1)
  s=run({'kandidaten':[ROW]},coverage(),s,lambda *a:self.fail('cooldown'),NOW)
  self.assertEqual(s['report']['cooldown'],1)
 def test_refresh_success_even_if_coverage_complete(self):
  s=run({'kandidaten':[ROW]},coverage(),{},fetch,NOW);later=NOW+dt.timedelta(days=8)
  s=run({'kandidaten':[ROW]},{'generatedAt':later.isoformat(),'stocks':[]},s,fetch,later)
  self.assertEqual(s['report']['updated'],1)
 def test_identity_change_purges_previous_and_duplicate_conflicts_block(self):
  s=run({'kandidaten':[ROW]},coverage(),{},fetch,NOW)
  changed={**ROW,'isin':'invalid'}
  s=run({'kandidaten':[changed]},coverage(),s,lambda *a:self.fail('identity'),NOW)
  self.assertFalse(s['stocks']);self.assertEqual(s['report']['identity_blocked'],1)
  s=run({'kandidaten':[ROW,changed]},coverage(),{},lambda *a:self.fail('duplicate'),NOW)
  self.assertEqual(s['report']['conflicting_listings'],1);self.assertFalse(s['stocks'])
 def test_other_markets_deferred_and_expired_reference_blocked(self):
  for row in [{**ROW,'listing_symbol':'GPW:MSFT'},{**ROW,'listing_reference_status':'expired'}]:
   c=coverage();c['stocks'][0]['symbol']=row['listing_symbol']
   s=run({'kandidaten':[row]},c,{},lambda *a:self.fail('blocked'),NOW)
   self.assertNotIn('attempted',s['report'])
 def test_stale_coverage_no_fetch(self):
  s=run({'kandidaten':[ROW]},coverage(NOW-dt.timedelta(days=3)),{},lambda *a:self.fail('stale'),NOW)
  self.assertEqual(s['report']['stopped'],'coverage_missing_or_stale')
 def test_failure_preserves_old_date_and_redacts(self):
  s=run({'kandidaten':[ROW]},coverage(),{},fetch,NOW);later=NOW+dt.timedelta(days=8)
  def fail(*a):raise TimeoutError('secret-token-must-not-appear')
  s=run({'kandidaten':[ROW]},coverage(later),s,fail,later)
  self.assertEqual(s['stocks'][ROW['listing_symbol']]['retrievedAt'],NOW.isoformat())
  self.assertEqual(s['attempts'][ROW['listing_symbol']]['error'],'provider_unavailable')
  self.assertNotIn('secret-token',str(s))
 def test_auth_and_rate_errors_stop_remaining_requests(self):
  for code in [401,402,403,429]:
   calls=[]
   def fail(*a):calls.append(a);raise urllib.error.HTTPError('https://example/?apikey=secret',code,'secret',{},None)
   s=run({'kandidaten':[ROW]},coverage(),{},fail,NOW)
   self.assertEqual(len(calls),1);self.assertEqual(s['report']['http_'+str(code)],1);self.assertNotIn('secret',str(s))
 def test_budget_no_requests(self):
  s=run({'kandidaten':[ROW]},coverage(),{},lambda *a:self.fail('budget'),NOW,budget=0)
  self.assertEqual(s['report']['budget_reached'],1)
if __name__=='__main__':unittest.main()
