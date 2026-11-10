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
  self.assertTrue(any(k.startswith('Währungskonflikt') for k in g[('corporate','Erwartungslücke Reverse DCF')]['reasons']))
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

class PeerSelectionTests(unittest.TestCase):
 def test_listing_matches_like_app(self):
  for t,l,ok in [('ALV.DE','XETR:ALV',True),('AAPL','NASDAQ:AAPL',True),('BRK.B','NYSE:BRK-B',True),('ALV.DE','LSE:ALV',False),('XETR:ALV','XETR:ALV',True),('SAP','XETR:SAP',False)]:
   self.assertEqual(cc.listing_matches(t,l),ok,(t,l))
 def test_family_and_selection(self):
  rows=[{'listing_symbol':'NYSE:JPM','ticker':'JPM','name':'JPMorgan Chase','currency':'USD','market_cap':500,'is_primary':True},
        {'listing_symbol':'NYSE:C','ticker':'C','name':'Citigroup','currency':'USD','market_cap':100,'is_primary':True},
        {'listing_symbol':'NYSE:BAC','ticker':'BAC','name':'Bank of America','currency':'USD','market_cap':300,'is_primary':True},
        {'listing_symbol':'OTC:BACPR','ticker':'BAC-PL','name':'Bank of America preferred','currency':'USD','market_cap':1},
        {'listing_symbol':'NYSE:X','ticker':'X','name':'Other Co','industry':'Steel','currency':'USD'}]
  fam={id(r):cc.peer_family(r) for r in rows}
  self.assertEqual(cc.peer_family(rows[0]),'Universalbanken');self.assertEqual(cc.peer_family(rows[4]),'Branche: steel')
  self.assertEqual([p['listing_symbol'] for p in cc.select_peers(rows[0],rows,fam)],['NYSE:BAC','NYSE:C'],'closest size first, preferred share excluded')
 def test_peer_stress_needs_three_peers_with_drawdown(self):
  r=CoverageTests().run_build();g={(x['profile'],x['metric']):x for x in r['largestGaps']}
  self.assertIn('Keine Peers ausgewählt (keine Geschäftsfamilie oder Unterbranche)',g[('bank','Peer-Stress')]['reasons'])

class FxResolutionTests(unittest.TestCase):
 def test_reviewed_one_to_one_basis_resolves_currency_conflict(self):
  import datetime as dt
  fx={'base':'EUR','rates':{'EUR':1,'USD':1.1,'JPY':170,'GBP':.83}};today=dt.date(2026,11,10)
  b={'kind':'ordinary','ordinary_shares_per_unit':1,'annual_eps_basis':'ordinary','report_currency':'JPY','quote_currency':'USD','reviewed_at':'2026-11-10','source_url':'https://x'}
  self.assertTrue(cc.fx_resolved(b,fx,'JPY','USD',today))
  self.assertTrue(cc.fx_resolved({**b,'report_currency':'USD','quote_currency':'GBp'},fx,'USD','GBp',today))
  for patch in [{'ordinary_shares_per_unit':2},{'reviewed_at':'2026-01-01'},{'report_currency':'EUR'},{'kind':'GDR'}]:self.assertFalse(cc.fx_resolved({**b,**patch},fx,'JPY','USD',today))
  self.assertFalse(cc.fx_resolved(b,{'base':'EUR','rates':{'USD':1.1}},'JPY','USD',today),'missing ECB rate')
  ann={'NYSE:C1':(annual(),'USD'),'NYSE:B1':(annual(),'USD'),'OTC:ADR':(annual('JPY'),'USD',b,fx),'NYSE:GS':(annual(),'USD')}
  r=cc.build(UNI,shards(),{s:{'statistics':STATS} for s in ('NYSE:C1','NYSE:B1','NYSE:GS')},ann,dt.datetime(2026,11,10,12,tzinfo=dt.timezone.utc))
  g={(x['profile'],x['metric']):x for x in r['largestGaps']};self.assertNotIn(('corporate','Erwartungslücke Reverse DCF'),g)

if __name__=='__main__':unittest.main()
