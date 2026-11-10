import datetime as dt,unittest
from share_basis_rule import ordinary_basis
D=dt.date(2026,11,10);Y='https://finance.yahoo.com/quote/X/'
class ShareBasisRule(unittest.TestCase):
 def row(self,**k):return {'listing_symbol':'OTC:KYCCF','ticker':'KYCCF','isin':'JP3236200006','security_type':'stock','share_class':None,**k}
 def test_foreign_ordinary_gets_one_to_one_basis(self):
  b=ordinary_basis(self.row(),{'currency':'JPY'},'USD',Y,D)
  self.assertEqual((b['kind'],b['ordinary_shares_per_unit'],b['report_currency'],b['quote_currency'],b['annual_eps_basis'],b['reviewed_at']),('ordinary',1,'JPY','USD','ordinary','2026-11-10'))
  self.assertEqual(ordinary_basis(self.row(listing_symbol='LSE:DGE',isin='GB0002374006'),{'currency':'USD'},'GBp',Y,D)['quote_currency'],'GBp')
 def test_depositary_receipts_and_unclear_cases_excluded(self):
  for row,ann,q in [(self.row(security_type='dr'),'JPY','USD'),(self.row(isin='US8740391003'),'TWD','USD'),(self.row(share_class='B'),'JPY','USD'),(self.row(isin='bad'),'JPY','USD'),
                    (self.row(),'USD','USD'),(self.row(),'GBP','GBp'),(self.row(),None,'USD'),(self.row(security_type=None),'JPY','USD')]:
   self.assertIsNone(ordinary_basis(row,{'currency':ann} if ann else None,q,Y,D),row)
  self.assertIsNone(ordinary_basis(self.row(),{'currency':'JPY'},'USD','http://x',D))
if __name__=='__main__':unittest.main()
