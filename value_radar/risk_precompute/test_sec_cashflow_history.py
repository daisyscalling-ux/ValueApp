import copy,datetime as dt,unittest,urllib.error
from sec_cashflow_history import normalize,run,balances,TAGS,METHOD
from financial_history import build
NOW=dt.datetime(2026,10,31,tzinfo=dt.timezone.utc)
ROW={'listing_symbol':'NASDAQ:EX','ticker':'EX','isin':'US0378331005','currency':'USD','name':'Example Corporation'}
def fixture():
 facts={}
 for key,tag in TAGS.items():
  vals=[]
  for year in range(2020,2026):
   r={'end':f'{year}-12-31','filed':f'{year+1}-02-20','accn':f'0000000001-{str(year+1)[2:]}-000001','form':'10-K','val':{'assets':100,'ocf':20,'ppe':5}[key]}
   if key!='assets':r['start']=f'{year}-01-01'
   vals.append(r)
  facts[tag]={'units':{'USD':vals}}
 return {'cik':1,'entityName':'Example Corporation','facts':{'us-gaap':facts}}
class Tests(unittest.TestCase):
 def setUp(self):
  self.data=fixture();self.u={'kandidaten':[ROW]};self.c={'schema':1,'generatedAt':NOW.isoformat(),'stocks':[{'symbol':ROW['listing_symbol'],'domains':{'identity':{'state':'available'},'balance':{'profile':'corporate','metrics':{}}}}]}
 def fetch(self,*args):return self.data
 def collect(self,state=None,**kwargs):return run(self.u,self.c,state or {},{'NASDAQ:EX':'1'},self.fetch,NOW,**kwargs)
 def test_six_real_periods_same_filing_and_arithmetic(self):
  values=normalize(self.data,1,NOW);self.assertEqual(len(values),6);self.assertEqual(values[0]['value'],.15)
 def test_wrong_cik_rejected(self):
  with self.assertRaises(ValueError):normalize(self.data,2,NOW)
 def test_duration_accession_and_currency_are_not_mixed(self):
  original=copy.deepcopy(self.data)
  for patch in [{'start':'2025-04-01'},{'accn':'0000000001-26-000002'},{'filed':'2027-01-01'},{'val':-5},{'val':True},{'val':float('nan')}]:
   self.data=copy.deepcopy(original);self.data['facts']['us-gaap'][TAGS['ppe']]['units']['USD'][-1].update(patch)
   self.assertEqual(len(normalize(self.data,1,NOW)),5)
  self.data=original;self.data['facts']['us-gaap'][TAGS['ppe']]['units']['EUR']=self.data['facts']['us-gaap'][TAGS['ppe']]['units'].pop('USD');self.assertEqual(normalize(self.data,1,NOW),[])
 def test_conflicting_values_same_filing_rejected(self):
  vals=self.data['facts']['us-gaap'][TAGS['ppe']]['units']['USD'];vals.append({**vals[-1],'val':6});self.assertEqual(len(normalize(self.data,1,NOW)),5)
 def test_newer_filing_revision_preserved(self):
  for key in TAGS:
   vals=self.data['facts']['us-gaap'][TAGS[key]]['units']['USD'];r={**vals[-1],'filed':'2026-03-01','accn':'0000000001-26-000002','form':'10-K/A'}
   if key=='ppe':r['val']=6
   vals.append(r)
  self.assertEqual(normalize(self.data,1,NOW)[-1]['value'],.14)
 def test_queue_cache_checkpoint_and_budget(self):
  calls=[];s=self.collect(checkpoint=lambda x:calls.append(1));self.assertEqual(calls,[1]);self.assertEqual(self.collect(s)['report']['cached'],1);self.assertEqual(self.collect(budget=0)['report']['remainingCandidates'],1)
 def test_issuer_name_and_duplicate_listing_blocked(self):
  self.data['entityName']='Other Corporation';self.assertEqual(self.collect()['report']['issuer_name_mismatch'],1)
  self.u['kandidaten']*=2;self.assertEqual(self.collect()['report']['remainingCandidates'],0)
 def test_bank_and_unconfirmed_identity_not_eligible(self):
  self.c['stocks'][0]['domains']['balance']['profile']='bank';self.assertEqual(self.collect()['report']['remainingCandidates'],0)
  self.c['stocks'][0]['domains']['balance']['profile']='corporate';self.c['stocks'][0]['domains']['identity']['state']='missing';self.assertEqual(self.collect()['report']['remainingCandidates'],0)
 def test_archive_and_app_history_separate_from_full_fcf(self):
  s=self.collect();b=balances(s,self.u,NOW);bf={'schema':1,'method':'roic-history-balances-v1','generatedAt':NOW.isoformat(),'stocks':b}
  a,r=build(self.c,self.u,{},NOW,bf);m=r['stocks'][0]['domains']['balance']['history']['metrics'][0]
  self.assertEqual(m['metric'],'cashAfterPpeAssets');self.assertEqual(m['periodCount'],6);self.assertEqual(m['state'],'comparable');self.assertEqual(m['firstObservedAt'],NOW.isoformat());self.assertFalse(a['pointInTimeUsable']);self.assertEqual(self.c['stocks'][0]['domains']['balance']['metrics'],{})
 def test_changed_identity_and_stale_cache_are_not_displayed(self):
  s=self.collect();self.assertFalse(balances(s,self.u,NOW+dt.timedelta(days=15)));s['stocks']['NASDAQ:EX']['inputIdentity']['isin']='US5949181045';self.assertFalse(balances(s,self.u,NOW))
 def test_zero_ppe_is_valid_negative_cashflow_is_valid(self):
  self.data['facts']['us-gaap'][TAGS['ppe']]['units']['USD'][-1]['val']=0;self.data['facts']['us-gaap'][TAGS['ocf']]['units']['USD'][-1]['val']=-20;self.assertEqual(normalize(self.data,1,NOW)[-1]['value'],-.2)
if __name__=='__main__':unittest.main()

class NativeSeriesTests(unittest.TestCase):
 def convert(self,namespace='ifrs-full',currency='EUR',form='20-F',productive=False):
  from sec_cashflow_history import IFRS_TAGS
  d=fixture();old=d['facts'].pop('us-gaap');tags=IFRS_TAGS if namespace=='ifrs-full' else TAGS
  d['facts'][namespace]={}
  for key,tag in tags.items():
   vals=old[TAGS[key]]['units']['USD']
   for v in vals:v['form']=form
   name='PaymentsToAcquireProductiveAssets' if key=='ppe' and productive else tag
   d['facts'][namespace][name]={'units':{currency:vals}}
  return d
 def test_ifrs_native_currency_and_foreign_annual_forms(self):
  for form in ['20-F','20-F/A','40-F','40-F/A']:
   p=normalize(self.convert(form=form),1,NOW);self.assertEqual(len(p),6);self.assertEqual(p[0]['currency'],'EUR');self.assertEqual(p[0]['value'],.15);self.assertEqual(p[0]['namespace'],'ifrs-full')
 def test_nonannual_reports_and_missing_currency_not_accepted(self):
  self.assertEqual(normalize(self.convert(form='6-K'),1,NOW),[])
  d=self.convert();v=d['facts']['ifrs-full']['Assets']['units'];v['USD']=v.pop('EUR');self.assertEqual(normalize(d,1,NOW),[])
 def test_frameworks_never_combined(self):
  d=self.convert();d['facts']['us-gaap']={'Assets':d['facts']['ifrs-full'].pop('Assets')};self.assertEqual(normalize(d,1,NOW),[])
 def test_negative_investment_not_silently_flipped(self):
  d=self.convert();from sec_cashflow_history import IFRS_TAGS
  d['facts']['ifrs-full'][IFRS_TAGS['ppe']]['units']['EUR'][-1]['val']=-5;self.assertEqual(len(normalize(d,1,NOW)),5)
 def test_productive_assets_keeps_separate_metric(self):
  d=self.convert('us-gaap','USD','10-K',True);p=normalize(d,1,NOW);self.assertEqual(len(p),6);self.assertEqual(p[0]['metric'],'cashAfterProductiveAssets')
 def test_multiple_currencies_same_period_are_ambiguous(self):
  d=self.convert()
  for tag in d['facts']['ifrs-full'].values():tag['units']['USD']=copy.deepcopy(tag['units']['EUR'])
  self.assertEqual(normalize(d,1,NOW),[])
 def test_cached_ifrs_and_productive_scope_reaches_history(self):
  from roic_risk_annual import identity
  for ns,currency,form,productive in [('ifrs-full','EUR','20-F',False),('us-gaap','USD','10-K',True)]:
   periods=normalize(self.convert(ns,currency,form,productive),1,NOW)
   state={'schema':1,'method':METHOD,'stocks':{'NASDAQ:EX':{'inputIdentity':identity(ROW),'cik':'1','retrievedAt':NOW.isoformat(),'periods':periods}}}
   b=balances(state,{'kandidaten':[ROW]},NOW);metrics=b['NASDAQ:EX']['balances'][0]['metrics'];key='cashAfterProductiveAssets' if productive else 'cashAfterPpeAssets'
   self.assertIn(key,metrics);self.assertEqual(metrics[key]['basis']['currency'],currency)
