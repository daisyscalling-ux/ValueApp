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
  self.assertTrue(any(k.startswith('Währungskonflikt') or k.startswith('Kein positiver Cashflow') for k in g[('corporate','Erwartungslücke Reverse DCF')]['reasons']))
  self.assertEqual(g[('corporate','Expected Shortfall')]['reasons'],{'Keine Kurshistorie':1})
  # Wie die App: zaehlt nur ausgewaehlte Peers; diese Zeilen haben keine Ticker, also keine Peer-Auswahl.
  self.assertEqual(g[('corporate','EBITDA-Marge gegenüber Peers')]['reasons'],{'Eigene EBITDA-Marge oder mindestens drei Peers mit Marge fehlen':2})
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
  for t,l,ok in [('ALV.DE','XETR:ALV',True),('AAPL','NASDAQ:AAPL',True),('BRK.B','NYSE:BRK-B',True),('ALV.DE','LSE:ALV',False),('XETR:ALV','XETR:ALV',True),('SAP','XETR:SAP',False),
                 ('VOLV-B.ST','STO:VOLV_B',True),('VOLV-B.ST','STO:VOLV_A',False),('NOVO-B.CO','CPH:NOVO_B',True),('RR.L','LSE:RR.',True),('RR.L','LSE:RRX.',False)]:
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

class FcffMarginTests(unittest.TestCase):
 def test_universe_fcff_margin_preferred_over_proxy(self):
  uni={'kandidaten':[{'listing_symbol':'NYSE:F1','ticker':'F1','name':'F One','industry':'Steel','fcff_margin':None}]}
  sh={'NYSE:F1':{'balance':{'profile':'corporate'},'market':{'state':'available'}}}
  g={(x['profile'],x['metric']):x for x in cc.build(uni,sh,{'NYSE:F1':{'statistics':STATS}},{'NYSE:F1':(annual(),'USD')})['largestGaps']}
  self.assertEqual(g[('corporate','FCFF-Marge')]['reasons'],{'ROIC liefert keinen FCFF oder Umsatz (TTM)':1},'export field present but empty wins over the annual proxy')
  uni['kandidaten'][0]['fcff_margin']=8.5
  g={(x['profile'],x['metric']):x for x in cc.build(uni,sh,{'NYSE:F1':{'statistics':STATS}},{'NYSE:F1':(annual(operating_cashflow=None),'USD')})['largestGaps']}
  self.assertNotIn(('corporate','FCFF-Marge'),g)

class EvEbitdaFallbackTests(unittest.TestCase):
 def test_negative_fcf_uses_peer_ev_ebitda(self):
  uni={'kandidaten':[{'listing_symbol':'NYSE:N1','ticker':'N1','name':'Neg One','industry':'Steel','currency':'USD','ev_ebitda':20},
   *[{'listing_symbol':f'NYSE:Q{i}','ticker':f'Q{i}','name':f'Peer {i}','industry':'Steel','currency':'USD','ev_ebitda':10+i} for i in range(3)]]}
  sh={'NYSE:N1':{'balance':{'profile':'corporate'},'market':{'state':'available'}}}
  ann={'NYSE:N1':(annual(operating_cashflow=5,capex=10),'USD')}
  g={(x['profile'],x['metric']):x for x in cc.build(uni,sh,{'NYSE:N1':{'statistics':STATS}},ann)['largestGaps']}
  self.assertNotIn(('corporate','Erwartungslücke Reverse DCF'),g)
  uni['kandidaten'][0]['ev_ebitda']=-4
  g={(x['profile'],x['metric']):x for x in cc.build(uni,sh,{'NYSE:N1':{'statistics':STATS}},ann)['largestGaps']}
  self.assertEqual(g[('corporate','Erwartungslücke Reverse DCF')]['reasons'],{'Kein positiver Cashflow und kein positives EV/EBITDA':1})

class ShortHistoryTests(unittest.TestCase):
 def test_short_history_fills_es_and_vol_but_not_drawdown(self):
  uni={'kandidaten':[{'listing_symbol':'NASDAQ:Y1','ticker':'Y1','name':'Young One','industry':'Software'}]}
  sh={'NASDAQ:Y1':{'balance':{'profile':'corporate'},'market':{'state':'available'}}}
  short={'observations':300,'error':'','es':.04,'vol':.5,'dd':None,'shortHistory':True}
  g={(x['profile'],x['metric']):x for x in cc.build(uni,sh,{'NASDAQ:Y1':{'statistics':short}},{'NASDAQ:Y1':(annual(),'USD')})['largestGaps']}
  self.assertNotIn(('corporate','Expected Shortfall'),g);self.assertNotIn(('corporate','Volatilität'),g)
  self.assertEqual(g[('corporate','Größter Rückgang')]['reasons'],{'Verkürzte Historie: größter Rückgang erst ab zwei Handelsjahren':1})
  g={(x['profile'],x['metric']):x for x in cc.build(uni,sh,{'NASDAQ:Y1':{'statistics':{**short,'shortHistory':None}}},{'NASDAQ:Y1':(annual(),'USD')})['largestGaps']}
  self.assertIn(('corporate','Expected Shortfall'),g,'unflagged short values stay missing')

class IndustryGroupTests(unittest.TestCase):
 def test_group_fills_only_below_three_and_up_to_five(self):
  mk=lambda t,i:{'listing_symbol':'NYSE:'+t,'ticker':t,'name':'Co '+t,'industry':i}
  rows=[mk('GEN','Pharmaceuticals: generic'),mk('G2','Pharmaceuticals: generic'),*[mk('M'+str(i),'Pharmaceuticals: major') for i in range(5)],mk('BIO','Biotechnology'),mk('DRG','Drug Manufacturers - General')]
  fam={id(r):cc.peer_family(r) for r in rows};grp={id(r):cc.industry_group(r) for r in rows}
  p=[r['ticker'] for r in cc.select_peers(rows[0],rows,fam,groups=grp)]
  self.assertEqual(len(p),5);self.assertEqual(p[0],'G2');self.assertNotIn('BIO',p)
  self.assertEqual(cc.peer_family(rows[-1]),'Branche: pharmaceuticals major')
  steel=[mk(t,'Steel') for t in 'ABCD']+[mk('AL','Aluminum')]
  fam={id(r):cc.peer_family(r) for r in steel};grp={id(r):cc.industry_group(r) for r in steel}
  self.assertNotIn('AL',[r['ticker'] for r in cc.select_peers(steel[0],steel,fam,groups=grp)])

class ParisPeerTests(unittest.TestCase):
 def test_paris_suffix_not_preferred(self):
  self.assertFalse(cc._preferred({'ticker':'BNP.PA','listing_symbol':'EURONEXT:BNP'}))
  self.assertTrue(cc._preferred({'ticker':'BAC-PB'}));self.assertTrue(cc._preferred({'ticker':'XYZ.PA'}),'no listing proof keeps the old caution')

class EbitdaPeerTests(unittest.TestCase):
 def test_selected_peers_with_margin_like_app(self):
  mk=lambda t,ind,m=None:{'listing_symbol':'NYSE:'+t,'ticker':t,'name':'Co '+t,'industry':ind,**({'ebitda_margin':m} if m is not None else {})}
  sh=lambda s:{s:{'balance':{'profile':'corporate'},'market':{'state':'available'}}}
  # Branche zu klein (1 Peer), Gruppe fuellt auf: Peers aus verwandten Branchen zaehlen wie in der App.
  uni={'kandidaten':[mk('T','Pharmaceuticals: generic',20),mk('G2','Pharmaceuticals: generic',18),*[mk('M'+str(i),'Pharmaceuticals: major',25+i) for i in range(3)]]}
  g={(x['profile'],x['metric']) for x in cc.build(uni,sh('NYSE:T'),{'NYSE:T':{'statistics':STATS}},{'NYSE:T':(annual(),'USD')})['largestGaps']}
  self.assertNotIn(('corporate','EBITDA-Marge gegenüber Peers'),g)
  # Gleiche Branche gross genug, aber Peers ohne Marge: Luecke, auch wenn die Branche andere Firmen mit Marge haette.
  uni={'kandidaten':[mk('T','Steel',20),*[mk('S'+str(i),'Steel') for i in range(4)]]}
  g={(x['profile'],x['metric']):x for x in cc.build(uni,sh('NYSE:T'),{'NYSE:T':{'statistics':STATS}},{'NYSE:T':(annual(),'USD')})['largestGaps']}
  self.assertIn(('corporate','EBITDA-Marge gegenüber Peers'),g)

if __name__=='__main__':unittest.main()


class InsurerScopeTests(unittest.TestCase):
 def test_same_cases_as_app(self):
  import risk_construct_coverage as rc
  for isin in ['US1713401024','JP3910660004','CH0011075394','BMG4593F1389','GB0007099541']:
   self.assertFalse(rc.insurer_solvency_comparable({'isin':isin}),isin)
  for isin in ['DE0008404005','DK0060636678','GB00BPQY8M80','NO0010582521','kaputt',None]:
   self.assertTrue(rc.insurer_solvency_comparable({'isin':isin}),isin)
