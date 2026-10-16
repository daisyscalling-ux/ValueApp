import ast,pathlib,unittest
from listing_identity import listing_matches,select_listing
class IdentityTests(unittest.TestCase):
 def test_wrong_issuer_and_class_rejected(self):
  for ticker,listing in [('PKO.WA','NYSE:PKO'),('MBK.WA','ASX:MBK'),('SSNLF','NYSE:SSNI'),('BRK-B','NYSE:BRK.A')]:
   self.assertFalse(listing_matches(ticker,listing))
   self.assertIsNone(select_listing(ticker,[{'symbol':listing,'is_primary':True}]))
 def test_actual_roic_resolver_never_falls_back_to_another_primary_issuer(self):
  # Exercise the production function with a deterministic search response,
  # without importing optional UI/network dependencies from roic.py.
  tree=ast.parse((pathlib.Path(__file__).parents[1]/'roic.py').read_text(encoding='utf-8'))
  fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='aufloesen')
  for ticker,hits,expected in [
   ('SSNLF',[{'symbol':'NYSE:SSNI','is_primary':True}],None),
   ('PKO.WA',[{'symbol':'NYSE:PKO','is_primary':True},{'symbol':'GPW:PKO','exchange':'GPW'}],'GPW:PKO'),
   ('BRK-B',[{'symbol':'NYSE:BRK.A','is_primary':True},{'symbol':'NYSE:BRK.B','exchange':'NYSE'}],'NYSE:BRK.B')]:
   env={'_RESOLVE_CACHE':{},'_SUFFIX_ROIC_EXCH':{},'_SUFFIX_LAND':{},'_EXCH_LAND':{},'_such_roh':lambda q:hits}
   exec(compile(ast.Module(body=[fn],type_ignores=[]),'roic.py','exec'),env)
   result=env['aufloesen'](ticker)
   self.assertEqual(result and result['symbol'],expected)
if __name__=='__main__':unittest.main()

