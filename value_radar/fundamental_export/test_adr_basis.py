import datetime as dt,json,tempfile,unittest
from pathlib import Path
from adr_basis import adr_basis,apply,METHOD
D=dt.date(2026,11,10);FX={'base':'EUR','observed_at':'2026-11-09','rates':{'EUR':1,'USD':1.12,'GBP':.83}}
def files(ratio_shares=2.0,adr_price=None):
 home={'market':{'currency':'EUR','fields':{'price':30.0,'shares_out':2000.0},'quote_at':'2026-11-09'}}
 adr={'annual':{'currency':'EUR'},'fx':FX,'market':{'currency':'USD','source_url':'https://finance.yahoo.com/quote/SHEL/','quote_at':'2026-11-09','fields':{'price':adr_price or 30*1.12*2,'shares_out':2000.0/ratio_shares}}}
 return adr,home
DR={'listing_symbol':'NYSE:SHEL','security_type':'dr','isin':'GB00BP6MXD84'};HOME={'listing_symbol':'EURONEXT:SHELL','security_type':'stock','isin':'GB00BP6MXD84'}
class AdrBasis(unittest.TestCase):
 def test_share_count_and_price_agree(self):
  adr,home=files();e,r=adr_basis(DR,adr,HOME,home,D)
  self.assertEqual((e['ordinary_shares_per_unit'],e['kind'],e['method'],e['report_currency'],e['quote_currency']),(2,'ADR',METHOD,'EUR','USD'))
  self.assertEqual(e['evidence']['homeListing'],'EURONEXT:SHELL')
 def test_disagreement_or_odd_ratio_rejected(self):
  adr,home=files(adr_price=30*1.12*2.5);self.assertEqual(adr_basis(DR,adr,HOME,home,D)[1],'price_disagrees_with_share_count')
  adr,home=files(ratio_shares=2.7);self.assertEqual(adr_basis(DR,adr,HOME,home,D)[1],'share_count_not_standard_ratio')
  adr,home=files();adr['fx']={'rates':{'EUR':1}};self.assertEqual(adr_basis(DR,adr,HOME,home,D)[1],'price_shares_or_fx_missing')
 def test_apply_writes_and_withdraws(self):
  with tempfile.TemporaryDirectory() as d:
   d=Path(d);adr,home=files()
   (d/'NYSE_SHEL.json').write_text(json.dumps(adr));(d/'EURONEXT_SHELL.json').write_text(json.dumps(home))
   uni={'kandidaten':[DR,HOME]}
   self.assertEqual(apply(d,uni,{},D)['ratio_set'],1);self.assertEqual(json.loads((d/'NYSE_SHEL.json').read_text())['share_basis']['ordinary_shares_per_unit'],2)
   self.assertEqual(apply(d,uni,{'NYSE:SHEL':{}},D),{},'manual entries take precedence')
   bad=json.loads((d/'NYSE_SHEL.json').read_text());bad['market']['fields']['price']=999;(d/'NYSE_SHEL.json').write_text(json.dumps(bad))
   apply(d,uni,{},D);self.assertNotIn('share_basis',json.loads((d/'NYSE_SHEL.json').read_text()),'unconfirmed ratio withdrawn')
 def test_outside_universe_home_used_only_with_fresh_quote_and_marked(self):
  with tempfile.TemporaryDirectory() as d:
   d=Path(d);adr,home=files()
   (d/'NYSE_SHEL.json').write_text(json.dumps(adr))
   out={'method':'roic_isin_primary_yahoo_quote_v1','homes':{'GB00BP6MXD84':{'roicSymbol':'EURONEXT:SHELL','yahooSymbol':'SHELL.AS','market':home['market']}}}
   self.assertEqual(apply(d,{'kandidaten':[DR]},{},D,outside=out)['ratio_set'],1)
   ev=json.loads((d/'NYSE_SHEL.json').read_text())['share_basis']['evidence']
   self.assertEqual((ev['homeListing'],ev['homeOutsideUniverse'],ev['homeYahooSymbol']),('EURONEXT:SHELL',True,'SHELL.AS'))
   stale={**out,'homes':{'GB00BP6MXD84':{**out['homes']['GB00BP6MXD84'],'market':{**home['market'],'quote_at':'2026-10-01'}}}}
   self.assertEqual(apply(d,{'kandidaten':[DR]},{},D,outside=stale),{'home_listing_missing':1})
   self.assertNotIn('share_basis',json.loads((d/'NYSE_SHEL.json').read_text()),'withdrawn when no longer confirmed')
   self.assertEqual(apply(d,{'kandidaten':[DR]},{},D,outside={**out,'method':'other'}),{'home_listing_missing':1})

if __name__=='__main__':unittest.main()
