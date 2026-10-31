import copy,datetime as dt,unittest,urllib.error
from history_backfill import normalize_years,run
from test_roic_risk_annual import payloads,ROW,NOW
class BackfillTests(unittest.TestCase):
 def setUp(self):
  self.p=payloads()
  for table in self.p.values():
   original=copy.deepcopy(table['data'][0]);table['data']=[{**original,'period_end_date':str(y)+'-06-30'} for y in range(2020,2027)]
  self.u={'kandidaten':[ROW]};self.c={'generatedAt':NOW.isoformat(),'stocks':[{'symbol':ROW['listing_symbol'],'domains':{'identity':{'state':'available'}}}]}
  self.calls=[]
 def fetch(self,s,e,t):self.calls.append((s,e));return self.p[{'balance-sheet':'balance','cash-flow':'cashflow','income-statement':'income'}[e]]
 def test_all_years_same_period_no_current_default_change(self):
  years=normalize_years(ROW,self.p,NOW);self.assertEqual(len(years),7);self.assertEqual(years[0]['end'],'2020-06-30')
  from roic_risk_annual import normalize
  self.assertEqual(normalize(ROW,self.p,NOW)['end'],'2026-06-30')
 def test_cross_currency_and_missing_fields_remain_partial(self):
  self.p['cashflow']['data'][0]['currency']='EUR';years=normalize_years(ROW,self.p,NOW);self.assertIsNone(years[0]['fields']['capex']);self.assertEqual(years[-1]['fields']['capex'],3)
 def test_future_fx_other_issuer_and_conflicts(self):
  original=copy.deepcopy(self.p)
  for patch in [{'period_end_date':'2027-06-30'},{'fx_applied':True},{'symbol':'NYSE:OTHER'}]:
   self.p=copy.deepcopy(original);self.p['balance']['data'][0].update(patch);self.assertEqual(len(normalize_years(ROW,self.p,NOW)),6)
  self.p=original;self.p['balance']['data'].append({**self.p['balance']['data'][0],'bs_tot_asset':999})
  with self.assertRaisesRegex(ValueError,'conflicting_statement_period'):normalize_years(ROW,self.p,NOW)
 def test_cache_and_no_valuation_mutation(self):
  before=copy.deepcopy(self.c);s=run(self.u,self.c,{},self.fetch,NOW);self.assertEqual(len(self.calls),3);self.assertEqual(self.c,before)
  r=run(self.u,self.c,s,self.fetch,NOW);self.assertEqual(len(self.calls),3);self.assertEqual(r['report']['cached'],1)
 def test_budget_and_checkpoint(self):
  calls=[];s=run(self.u,self.c,{},self.fetch,NOW,budget=0,checkpoint=lambda x:calls.append(1));self.assertEqual(len(self.calls),0);self.assertEqual(s['report']['remainingCandidates'],1)
  s=run(self.u,self.c,{},self.fetch,NOW,checkpoint=lambda x:calls.append(1));self.assertEqual(calls,[1])
 def test_duplicate_and_changed_identity(self):
  s=run(self.u,self.c,{},self.fetch,NOW);self.u['kandidaten']=[{**ROW,'isin':'US0378331005'}];run(self.u,self.c,s,self.fetch,NOW);self.assertEqual(len(self.calls),6)
  self.u['kandidaten']*=2;r=run(self.u,self.c,{},self.fetch,NOW);self.assertEqual(r['report']['identityBlocked'],1)
 def test_error_retains_prior_data_and_stops_on_rate_limit_without_key_in_logs(self):
  s=run(self.u,self.c,{},self.fetch,NOW);old=copy.deepcopy(s['stocks']);later=NOW+dt.timedelta(days=31);self.c['generatedAt']=later.isoformat()
  def fail(*args):raise urllib.error.HTTPError('https://example.com?apikey=secret',429,'secret',None,None)
  r=run(self.u,self.c,s,fail,later);self.assertEqual(r['stocks'],old);self.assertEqual(r['report']['http_429'],1);self.assertNotIn('secret',str(r['report']))
if __name__=='__main__':unittest.main()
