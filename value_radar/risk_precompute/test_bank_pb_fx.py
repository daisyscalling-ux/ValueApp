import datetime as dt,unittest
import risk_construct_coverage as cc
STATS={'observations':600,'error':'','es':.03,'vol':.3,'dd':.4}
FX={'base':'EUR','rates':{'EUR':1,'USD':1.1,'JPY':170}}
B={'kind':'ordinary','ordinary_shares_per_unit':1,'annual_eps_basis':'ordinary','report_currency':'JPY','quote_currency':'USD','reviewed_at':'2026-11-10','source_url':'https://x'}
NOW=dt.datetime(2026,11,10,12,tzinfo=dt.timezone.utc)
def run(pb,basis=B,quote=None,equity=1.7e12):
 uni={'kandidaten':[{'listing_symbol':'OTC:JBANK','ticker':'JBANK','name':'Japan Bank','industry':'Major banks','pb':pb,'roe':10.0}]}
 sh={'OTC:JBANK':{'balance':{'profile':'bank'},'market':{'state':'available'}}}
 ann={'OTC:JBANK':({'currency':'JPY','fields':{'equity':equity,'net_income':1e11,'revenue':5e11}},'USD',basis,FX,quote if quote is not None else {'price':15.0,'shares_out':1e9})}
 g={(x['profile'],x['metric']):x for x in cc.build(uni,sh,{'OTC:JBANK':{'statistics':STATS}},ann,NOW)['largestGaps']}
 return g.get(('bank','Erwartungslücke Eigenkapitalrendite'))
class BankPbFx(unittest.TestCase):
 def test_fx_converted_pb_like_app(self):
  # Eigenkapital 1,7 Bio. JPY = 11 Mrd. USD; 1 Mrd. Aktien -> 11 USD je Aktie; Kurs 15 -> KBV 1,36
  self.assertIsNone(run(.01),'currency-mixed universe pb no longer creates a false gap')
 def test_without_verified_basis_or_quote_falls_back_to_universe_pb(self):
  self.assertIsNotNone(run(.01,basis=None))   # Waehrungskonflikt bleibt offen
  self.assertEqual(run(.01,quote={})['reasons'],{'KBV fehlt oder unplausibel':1})
  self.assertEqual(run(.01,equity=-5)['reasons'],{'KBV fehlt oder unplausibel':1})
if __name__=='__main__':unittest.main()
