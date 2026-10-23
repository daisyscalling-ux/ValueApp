import datetime as dt
import unittest
from recover_listing_metadata import recover,run,validate
from listing_identity import listing_matches
NOW=dt.datetime(2026,10,23,tzinfo=dt.timezone.utc)
class Tests(unittest.TestCase):
 def row(self):return {'ticker':'INVE-B.ST','name_full':'Investor AB (publ)','currency':'SEK','price':410.4,'fair_value':403.32,'isin':None}
 def hit(self):return {'symbol':'STO:INVE.B','name':'Investor AB Class B','isin':'SE0015811963','type':'stock','currency':'SEK'}
 def test_class_notation_preserves_class_and_venue(self):
  self.assertTrue(listing_matches('INVE-B.ST','STO:INVE.B'))
  self.assertTrue(listing_matches('NOVO-B.CO','CPH:NOVO_B'))
  self.assertTrue(listing_matches('RR.L','LSE:RR.'))
  for t,s in [('INVE-A.ST','STO:INVE.B'),('INVE-B.ST','OTC:INVE.B'),('INVE-B.ST','STO:INVE'),('ABC.DE','XETR:ABC.B')]:self.assertFalse(listing_matches(t,s))
 def test_metadata_only_financials_never_overwritten(self):
  row=self.row();updated,report=recover(row,lambda q:[{**self.hit(),'price':999,'fair_value':999}],NOW)
  self.assertEqual(report['state'],'repaired');self.assertEqual(updated['listing_symbol'],'STO:INVE.B')
  self.assertEqual(updated['price'],410.4);self.assertEqual(updated['fair_value'],403.32)
  self.assertIsNone(row['isin'])
 def test_wrong_issuer_or_class_never_accepted(self):
  for changes in [{'name':'Unrelated Holdings AB'},{'name':'Investor AB Class A'},{'symbol':'STO:INVE.A'},{'currency':'USD'},{'isin':'BAD'},{'type':'preferred'}]:
   row,report=recover(self.row(),lambda q:[{**self.hit(),**changes}],NOW)
   self.assertEqual(report['state'],'review');self.assertIsNone(row['isin'])
 def test_conflicting_isins_and_existing_identity(self):
  h=self.hit();self.assertEqual(validate(self.row(),[h,{**h,'isin':'US0378331005'}])[1],'conflicting_listing_candidates')
  row={**self.row(),'isin':'US0378331005'}
  self.assertEqual(validate(row,[h])[1],'isin_conflict')
 def test_preferred_not_inherited(self):
  row={**self.row(),'ticker':'JPM-PC'}
  def no_call(q):raise AssertionError('must not query preferred')
  self.assertEqual(recover(row,no_call,NOW)[1]['reason'],'preferred_instrument_review')
 def test_retry_and_cache_do_not_mutate_changed_input(self):
  u={'kandidaten':[self.row()]};_,state=run(u,{},lambda q:[self.hit()],NOW)
  def no_call(q):raise AssertionError('cached')
  u={'kandidaten':[self.row()]};u,state=run(u,state,no_call,NOW+dt.timedelta(hours=2))
  self.assertEqual(u['kandidaten'][0]['listing_symbol'],'STO:INVE.B')
  u={'kandidaten':[{**self.row(),'name_full':'Different Company'}]}
  u,state=run(u,state,lambda q:[self.hit()],NOW+dt.timedelta(hours=3))
  self.assertNotIn('listing_symbol',u['kandidaten'][0]);self.assertEqual(state['stocks']['INVE-B.ST']['reason'],'issuer_name_mismatch')
 def test_request_failure_sanitized_and_checkpointed(self):
  def fail(q):raise ValueError('apikey=secret')
  calls=[];u,state=run({'kandidaten':[self.row()]},{},fail,NOW,checkpoint=lambda u,s:calls.append(1))
  self.assertEqual(calls,[1]);self.assertNotIn('secret',str(state));self.assertEqual(state['summary'],{'retry':1})
 def test_no_duplicate_listing_is_created(self):
  existing={**self.row(),'ticker':'STO:INVE.B','listing_symbol':'STO:INVE.B','isin':self.hit()['isin']}
  u,state=run({'kandidaten':[existing,self.row()]},{},lambda q:[self.hit()],NOW)
  self.assertNotIn('listing_symbol',u['kandidaten'][1]);self.assertEqual(state['stocks']['INVE-B.ST']['reason'],'duplicate_listing_target')
if __name__=='__main__':unittest.main()

