import unittest
import json
from pathlib import Path
from news_identity import canonical_names,valid_isin,prepare_universe,identity_fingerprint,audit_rows
from yahoo_company_news import verify_profile

class IdentityTests(unittest.TestCase):
 def row(self,name='Continental AG'):
  r={'name':name,'ticker':'CON.DE','listing_symbol':'XETR:CON','exchange':'XETR','isin':'DE0005439004','currency':'EUR'}
  prepare_universe([r]);return r
 def info(self,name='Continental Aktiengesellschaft'):
  return {'longName':name,'symbol':'CON.DE','currency':'EUR','quoteType':'EQUITY'}
 def test_legal_and_language_variants(self):
  for a,b in [('Continental AG','Continental Aktiengesellschaft'),('Orsted','Ørsted A/S'),('Konecranes Oyj','Konecranes Plc'),('Magnum Ice Cream Co. N.V.','The Magnum Ice Cream Company N.V.'),('Ringkjobing Landbobank A/S','Ringkjøbing Landbobank A/S'),('Deutsche Boerse AG','Deutsche Börse AG')]:
   self.assertTrue(canonical_names(a)&canonical_names(b),(a,b))
 def test_auto_match_records_method(self):
  e=verify_profile(self.row(),self.info())
  self.assertEqual(e['nameMatch'],'normalized_legal_name')
 def test_unchanged_hard_identity_checks(self):
  for change in [{'symbol':'OTHER'},{'currency':'USD'},{'quoteType':'ETF'},{'longName':'Continental Bank AG'}]:
   with self.assertRaises(ValueError):verify_profile(self.row(),{**self.info(),**change})
 def test_short_brands_subsidiaries_classes_not_collapsed(self):
  self.assertFalse(canonical_names('ABC AG'))
  for a,b in [('Continental Bank AG','Continental AG'),('Orion Oyj Class A','Orion Oyj'),('Alphabet Class A','Alphabet Class C'),('Roche Holding AG','Roche AG')]:
   self.assertFalse(canonical_names(a)&canonical_names(b))
 def test_class_conflict_blocks_even_exact_long_name(self):
  with self.assertRaisesRegex(ValueError,'share_class_conflict'):
   verify_profile(self.row('Orion Oyj Class A'),{**self.info('Orion Oyj Class A'),'shortName':'Orion Corporation B'})
 def test_isin_and_context_required_for_relaxation(self):
  self.assertTrue(valid_isin('DE0005439004'))
  self.assertFalse(valid_isin('DE0005439005'))
  for change in [{'isin':'DE0005439005'},{'exchange':None},{'_newsNameCollision':True}]:
   with self.assertRaises(ValueError):verify_profile({**self.row(),**change},self.info())
 def test_collision_and_duplicate_ticker_detected(self):
  a=self.row();b={**a,'ticker':'CONX','listing_symbol':'OTHER:CON','isin':'GB0005405286'}
  audit=prepare_universe([a,b]);self.assertEqual(audit['canonicalCollisionRows'],2)
  with self.assertRaises(ValueError):verify_profile(a,self.info())
  b['ticker']=a['ticker'];prepare_universe([a,b])
  with self.assertRaisesRegex(ValueError,'ambiguous_listing'):verify_profile(a,self.info('Continental AG'))
 def test_fingerprint_changes_when_symbol_reused(self):
  a=self.row();self.assertNotEqual(identity_fingerprint(a),identity_fingerprint({**a,'isin':'GB0005405286'}))
 def test_live_regression_fixtures(self):
  fixtures=json.loads(Path(__file__).with_name('news-identity-live-fixtures.json').read_text(encoding='utf8'))
  for f in fixtures:
   info={'symbol':f['yahooSymbol'],'longName':f['yahooLong'],'shortName':f['yahooShort'],'currency':f['yahooCurrency'],'quoteType':f['type']}
   with self.subTest(symbol=f['symbol']):
    if f['expectedResult'].startswith('yahoo_'):
     with self.assertRaisesRegex(ValueError,f['expectedResult']):verify_profile(f['row'],info)
    else:self.assertEqual(verify_profile(f['row'],info)['nameMatch'],f['expectedResult'])
 def test_audit_does_not_claim_old_evidence_is_current(self):
  row=self.row();archive={'stocks':{'XETR:CON':{'identityEvidence':{'nameMatch':'exact'}}}}
  self.assertEqual(audit_rows([row],archive)[0]['state'],'legacy_check')
  archive['stocks']['XETR:CON']['identityEvidence']=verify_profile(row,self.info())
  self.assertEqual(audit_rows([row],archive)[0]['state'],'accepted_current_policy')
if __name__=='__main__':unittest.main()

