import copy,datetime as dt,json,tempfile,unittest
from pathlib import Path
from risk_app_export import build,publish
NOW=dt.datetime(2026,10,27,14,tzinfo=dt.timezone.utc)
def data():return {'schema':1,'generatedAt':NOW.isoformat(),'stocks':[{'symbol':'NYSE:A','domains':{'balance':{'metrics':{'fcf':{'value':.123}}},'sector':{'currencyAdjustedContext':{'value':.1}},'news':{'items':[]}}},{'symbol':'TSE:1234','domains':{}}]}
class Tests(unittest.TestCase):
 def test_exact_values_and_stable_hashes(self):
  d=data();original=copy.deepcopy(d);m,parts=build(d,NOW)
  rows=[r for b in parts.values() for r in json.loads(b)['stocks']]
  self.assertEqual(sorted(rows,key=lambda x:x['symbol']),d['stocks']);self.assertEqual(d,original)
  self.assertEqual(build({**d,'stocks':list(reversed(d['stocks']))},NOW),(m,parts))
 def test_stale_future_duplicate_and_invalid_fail(self):
  for d in [{**data(),'generatedAt':'2020-01-01'},{**data(),'generatedAt':'2027-01-01'}, {**data(),'stocks':data()['stocks']*2},{**data(),'stocks':[{'symbol':'../../escape'}]}]:
   with self.assertRaises(ValueError):build(d,NOW)
 def test_oversize_rejected_before_publication(self):
  d=data();d['stocks'][0]['large']='x'*2_000_000
  with self.assertRaises(ValueError):build(d,NOW)
 def test_publish_retains_previous_generation_only_and_unrelated_files(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp);d=data();publish(p,d,NOW);first=set((p/'risk_app').glob('*.json'))
   (p/'risk_app'/'notes.json').write_text('keep')
   for day in [1,2]:
    later=NOW+dt.timedelta(days=day);d['generatedAt']=later.isoformat();publish(p,d,later)
    if day==1:self.assertTrue(all(x.exists() for x in first))
   self.assertFalse(any(x.exists() for x in first));self.assertEqual((p/'risk_app'/'notes.json').read_text(),'keep')
 def test_failed_build_does_not_replace_previous_manifest(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp);publish(p,data(),NOW);old=(p/'cf_risk_app_manifest.json').read_bytes()
   with self.assertRaises(ValueError):publish(p,{'schema':1,'stocks':[]},NOW)
   self.assertEqual((p/'cf_risk_app_manifest.json').read_bytes(),old)
if __name__=='__main__':unittest.main()
