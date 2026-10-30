import datetime as dt,io,csv,unittest
from import_credit_quality import parse,amount,FIELDS
class CreditImportTests(unittest.TestCase):
 def stream(self,overrides=None,duplicate=False):
  d={'RSSD9001':'1','RSSD9017':'Example','RSSD9999':'20260630',**{k:'0' for k in FIELDS},**(overrides or {})};s=io.StringIO();w=csv.DictWriter(s,fieldnames=list(d),delimiter='^');w.writeheader();w.writerow(d)
  if duplicate:w.writerow(d)
  s.seek(0);return s
 def test_missing_zero_and_bad_amounts(self):
  self.assertEqual(amount('0')['value'],0);self.assertIsNone(amount('')['value'])
  for v in ['-1','NaN','1.2','1e5','1,000','9007199254741']:self.assertEqual(amount(v)['state'],'invalid')
 def test_same_period_identity_and_columns(self):
  r=parse(self.stream(),dt.date(2026,6,30),{'1'});self.assertEqual(r['1']['fields']['BHCK1403']['value'],0)
  for s in [self.stream({'RSSD9999':'20260930'}),self.stream(duplicate=True),io.StringIO('RSSD9001\n1\n')]:
   with self.assertRaises(ValueError):parse(s,dt.date(2026,6,30),{'1'})
 def test_incomplete_new_quarter_cannot_replace_existing_holdings(self):
  with self.assertRaisesRegex(ValueError,'no_reviewed'):parse(self.stream(),dt.date(2026,6,30),{'2'})
if __name__=='__main__':unittest.main()
