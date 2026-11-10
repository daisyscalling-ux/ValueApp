import json,tempfile,unittest
from pathlib import Path
import risk_construct_coverage as cc

STATS={'observations':600,'error':'','es':.03,'vol':.3,'dd':.4}
def annual(cur='USD',**f):return {'currency':cur,'fields':{'revenue':100,'operating_cashflow':30,'capex':10,'ebitda':25,'total_debt':50,'cash':10,'equity':80,'total_assets':200,'net_income':12,'revenue_growth':.05,**f}}
UNI={'kandidaten':[{'listing_symbol':'NYSE:C1','industry':'Software','ebitda_margin':20},*[{'listing_symbol':f'NYSE:P{i}','industry':'Software','ebitda_margin':10+i} for i in range(3)],
 {'listing_symbol':'NYSE:B1','pb':1.2,'roe':11.0},{'listing_symbol':'OTC:ADR','industry':'Software','ebitda_margin':5}]}
def shards():
 return {'NYSE:C1':{'balance':{'profile':'corporate'},'market':{'state':'available'},'sector':{'state':'available'}},
  'NYSE:B1':{'balance':{'profile':'bank','bankCapital':{'state':'available','capitalRequirement':{'state':'available'},'liquidity':None,'creditQuality':{'state':'available'}}},'market':{'state':'available'},'sector':{'state':'missing'}},
  'OTC:ADR':{'balance':{'profile':'corporate'},'market':{'state':'available'},'sector':{'state':'missing'}},
  'NYSE:GS':{'balance':{'profile':'specialist_financial','bankCapital':{'state':'available','capitalRequirement':{'state':'available'},'liquidity':{'state':'available'}}},'market':{'state':'available'}}}

class CoverageTests(unittest.TestCase):
 def run_build(self):
  ann={'NYSE:C1':(annual(),'USD'),'NYSE:B1':(annual(),'USD'),'OTC:ADR':(annual('EUR'),'USD'),'NYSE:GS':(annual(),'USD')}
  return cc.build(UNI,shards(),{s:{'statistics':STATS} for s in ('NYSE:C1','NYSE:B1','NYSE:GS')},ann)
 def test_weights_per_listing_add_up_to_100(self):
  r=self.run_build()
  for p in r['profiles'].values():self.assertAlmostEqual(sum(p['averageWeight'].values()),100,delta=.2)
 def test_corporate_fully_filled_except_app_only(self):
  c=self.run_build()['profiles']['corporate']['blocks']
  self.assertEqual(c['Finanzielle Verwundbarkeit']['filledShareOfMeasurable'],1.0)
  self.assertEqual(c['Bewertungsrisiko']['app_only'],5.0)
 def test_currency_conflict_and_missing_history_are_named(self):
  g={(x['profile'],x['metric']):x for x in self.run_build()['largestGaps']}
  self.assertIn('Währungskonflikt (Bericht und Handel verschieden)',g[('corporate','Erwartungslücke Reverse DCF')]['reasons'])
  self.assertEqual(g[('corporate','Expected Shortfall')]['reasons'],{'Keine Kurshistorie':1})
  self.assertNotIn(('corporate','EBITDA-Marge gegenüber Peers'),g,'own margin plus at least three industry peers with a margin')
 def test_bank_like_specialist_counts_as_bank_and_by_design_metrics(self):
  r=self.run_build()['profiles'];self.assertEqual(r['bank']['listings'],2);self.assertNotIn('specialist_financial',r)
  self.assertEqual(r['bank']['blocks']['Wettbewerbsanfälligkeit']['by_design'],10.0)
  g={(x['profile'],x['metric']):x for x in self.run_build()['largestGaps']};self.assertEqual(g[('bank','Liquiditätsdeckung (LCR)')]['missingListings'],1)
 def test_main_writes_file(self):
  with tempfile.TemporaryDirectory() as d:
   d=Path(d);(d/'risk_app').mkdir();(d/'fundamentals').mkdir()
   (d/'risk_app'/'h.json').write_text(json.dumps({'stocks':[{'symbol':s,'domains':v} for s,v in shards().items()]}))
   (d/'cf_risk_app_manifest.json').write_text(json.dumps({'shards':{'0':'h'}}));(d/'cf_universum.json').write_text(json.dumps(UNI))
   (d/'cf_risk.json').write_text(json.dumps({'stocks':{'NYSE:C1':{'statistics':STATS}}}))
   (d/'fundamentals'/'NYSE_C1.json').write_text(json.dumps({'annual':annual(),'market':{'currency':'USD'}}))
   cc.main(d);r=json.loads((d/'cf_risk_construct_coverage.json').read_text(encoding='utf-8'))
   self.assertEqual(r['listings'],4);self.assertEqual(r['constructVersion'],'0.8')

if __name__=='__main__':unittest.main()
