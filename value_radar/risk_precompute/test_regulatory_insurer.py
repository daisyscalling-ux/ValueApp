import copy,datetime as dt,json,unittest,tempfile,os
from unittest.mock import patch
from pathlib import Path
from regulatory_insurer import build_insurers,observation

class InsurerTests(unittest.TestCase):
 def setUp(self):
  self.reg=json.loads(Path(__file__).with_name('reviewed-insurer-solvency.json').read_text(encoding='utf-8'))
  self.u={'kandidaten':[copy.deepcopy(e['inputIdentity']) for e in self.reg['entries']]}
  self.now=dt.datetime(2026,11,6,12,tzinfo=dt.timezone.utc)
 def run_case(self):return build_insurers(self.u,self.reg,self.now)
 def test_original_amounts_and_bases(self):
  r=self.run_case()['stocks'];self.assertEqual(len(r),2)
  a=r['XETR:ALV'];self.assertEqual(a['primary']['ratio'],2.25);self.assertEqual(a['primary']['eligibleOwnFunds'],97000000000)
  self.assertFalse(a['observations'][1]['amountsVerified']);self.assertEqual(a['observations'][1]['ratio'],2.18)
  m=r['XETR:MUV2'];self.assertEqual(m['primary']['solvencyRequirement'],18230000000);self.assertEqual(m['primary']['ratio'],3)
  self.assertFalse(m['pointInTimeUsable']);self.assertEqual(m['scoreContribution'],0)
 def test_mixed_ratio_denominator_or_units_rejected(self):
  o=self.reg['entries'][0]['observations'][0]
  for patch in [{'ratio':2.18},{'solvencyRequirement':None},{'eligibleOwnFunds':True},{'eligibleOwnFunds':float('nan')},{'unit':'millions'},{'currency':'USD'},{'sourceUrl':'javascript:x'},{'period':'2026-02-30'},{'period':'2027-01-01'},{'basis':''}]:
   with self.subTest(patch=patch):self.assertIsNone(observation({**o,**patch},self.now.date(),self.now.date()))
 def test_identity_scope_expiry_duplicates(self):
  for key,value in [('isin','US0378331005'),('security_type','dr'),('listing_symbol','OTC:ALIZY'),('name','Allianz subsidiary')]:
   u=copy.deepcopy(self.u);u['kandidaten'][0][key]=value
   self.assertNotIn('XETR:ALV',build_insurers(u,self.reg,self.now)['stocks'])
  for patch in [{'reviewExpires':'2026-11-05'},{'reviewedOn':'2026-11-07'},{'source':'unreviewed'}]:self.assertFalse(build_insurers(self.u,{**self.reg,**patch},self.now)['stocks'])
  self.reg['entries'].append(copy.deepcopy(self.reg['entries'][0]));self.assertNotIn('XETR:ALV',self.run_case()['stocks'])
 def test_old_annual_not_refreshed_by_daily_job(self):
  self.reg['reviewExpires']='2028-01-01';self.now=dt.datetime(2027,8,1,tzinfo=dt.timezone.utc)
  self.assertFalse(self.run_case()['stocks'])
 def test_ambiguous_or_ratio_only_cannot_fill_amounts(self):
  e=self.reg['entries'][0];e['observations'].append(copy.deepcopy(e['observations'][0]));self.assertNotIn('XETR:ALV',self.run_case()['stocks'])
  e['observations']=e['observations'][1:2];self.assertNotIn('XETR:ALV',self.run_case()['stocks'])
 def test_group_scope_required(self):
  self.reg['entries'][0]['scope']='subsidiary';self.assertNotIn('XETR:ALV',self.run_case()['stocks'])
 def test_production_entrypoint_independent_of_bank_source(self):
  import regulatory_context
  with tempfile.TemporaryDirectory() as folder:
   Path(folder,'cf_universum.json').write_text(json.dumps(self.u),encoding='utf-8')
   with patch.dict(os.environ,{'RISK_DATA_DIR':folder}),patch.object(regulatory_context,'build_insurers',side_effect=lambda u,r:build_insurers(u,r,self.now)):
    regulatory_context.main()
   result=json.loads(Path(folder,'cf_regulatory_context.json').read_text(encoding='utf-8'))
   self.assertEqual(result['state'],'source_unavailable');self.assertEqual(len(result['insurers']['stocks']),2)
