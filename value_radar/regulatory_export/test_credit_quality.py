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


class CarriedCreditDefinitionTests(unittest.TestCase):
    def test_repository_credit_archive_covers_all_reviewed_holdings_with_carried_definitions(self):
        import json
        from pathlib import Path
        root = Path(__file__).resolve().parents[1]
        archive = json.loads((root / 'daten/regulatory/bhcf-credit-quality.json').read_text(encoding='utf-8'))
        capital = json.loads((root / 'daten/regulatory/bhcf-import.json').read_text(encoding='utf-8'))
        registry = json.loads((root / 'regulatory_export/holding-stock-map.json').read_text(encoding='utf-8-sig'))
        self.assertEqual(set(archive['entities']), {e['rssd_id'] for e in registry['entries']})
        self.assertEqual(archive['source_file_sha256'], capital['files'][0]['sha256'])
        self.assertEqual(archive['reporting_period'], capital['reporting_period'])
        self.assertTrue(all(e['holding_evidence']['source_file_sha256'] == archive['source_file_sha256'] for e in registry['entries']))
        self.assertEqual(archive['definitions_source']['kind'], 'previous_reviewed_import')
        self.assertTrue(all(d['unit'] == 'USD_thousands' for d in archive['definitions'].values()))
