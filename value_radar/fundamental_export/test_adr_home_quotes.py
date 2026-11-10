import datetime as dt,json,tempfile,unittest
from pathlib import Path
import adr_home_quotes as a
NOW=dt.datetime(2026,11,10,12,tzinfo=dt.timezone.utc)
UNI={'kandidaten':[{'listing_symbol':'NASDAQ:ASML','security_type':'dr','isin':'NL0010273215','name':'ASML Holding NV'},
 {'listing_symbol':'NYSE:SHEL','security_type':'dr','isin':'GB00BP6MXD84','name':'Shell plc'},{'listing_symbol':'EURONEXT:SHELL','security_type':'stock','isin':'GB00BP6MXD84'},
 {'listing_symbol':'NYSE:BABA','security_type':'dr','isin':'US01609W1027','name':'Alibaba'}]}
DRFILE={'annual':{'currency':'EUR'},'market':{'currency':'USD'}}
HIT={'symbol':'EURONEXT:ASML','isin':'NL0010273215','type':'stock','is_primary':True,'listing_country_code':'NL'}
Q={'price':1300.0,'shares_out':385e6,'currency':'EUR','name':'ASML Holding N.V.','quote_at':'2026-11-10T16:00:00+00:00'}
class Homes(unittest.TestCase):
 def folder(self):
  d=Path(tempfile.mkdtemp())
  for s in ('NASDAQ_ASML','NYSE_SHEL','NYSE_BABA'):(d/(s+'.json')).write_text(json.dumps(DRFILE))
  return d
 def test_targets_only_dr_without_home_and_non_us_isin(self):
  self.assertEqual([t['isin'] for t in a.targets(UNI,self.folder())],['NL0010273215'])
 def test_resolve_quote_and_cache(self):
  calls=[];out=a.run(UNI,self.folder(),{},lambda q:(calls.append(q),[HIT])[1],lambda s:Q,NOW)
  h=out['homes']['NL0010273215']
  self.assertEqual((h['roicSymbol'],h['yahooSymbol'],h['market']['fields']['price'],h['drs']),('EURONEXT:ASML','ASML.AS',1300.0,['NASDAQ:ASML']))
  again=a.run(UNI,self.folder(),out,lambda q:(calls.append(q),[HIT])[1],lambda s:Q,NOW+dt.timedelta(days=3))
  self.assertEqual(len(calls),1,'resolution cached for 30 days');self.assertEqual(again['report']['quoted'],1)
 def test_unclear_cases_stay_open(self):
  f=self.folder()
  for hits,why in [([],'no_unique_primary_listing'),([{**HIT,'is_primary':False}],'no_unique_primary_listing'),([{**HIT,'symbol':'OTC:ASMLF'}],'no_unique_primary_listing'),
                   ([HIT,{**HIT,'symbol':'XETR:ASME'}],'no_unique_primary_listing'),([{**HIT,'isin':'NL0000000000'}],'no_unique_primary_listing'),([{**HIT,'listing_country_code':'XX'}],'yahoo_mapping_unclear')]:
   out=a.run(UNI,f,{},lambda q:hits,lambda s:Q,NOW);self.assertEqual(out['report']['unresolved'],{why:1},hits)
  for q,why in [({**Q,'name':'Advanced Semiconductor Materials Lithography'},'issuer_name_mismatch'),({**Q,'shares_out':None},'price_or_shares_missing'),(None,'quote_missing')]:
   out=a.run(UNI,f,{},lambda x:[HIT],lambda s:q,NOW);self.assertEqual(out['report']['quoteFailed'],{why:1});self.assertNotIn('market',out['homes']['NL0010273215'])
 def test_short_names(self):
  self.assertTrue(a.name_matches('GSK plc','GSK plc'));self.assertTrue(a.name_matches('BAE Systems plc','BAE Systems plc'))
  self.assertFalse(a.name_matches('GSK plc','GSL Ltd'));self.assertFalse(a.name_matches('GSK plc',None))
 def test_yahoo_symbols(self):
  for s,c,y in [('EURONEXT:ASML','NL','ASML.AS'),('HKEX:939','HK','0939.HK'),('NSE:HDFCBANK','IN','HDFCBANK.NS'),('LSE:RR.','GB','RR.L'),('STO:VOLV_B','SE','VOLV-B.ST'),('BMV:AMX/B','MX',None),('EURONEXT:X',None,None),('XYZ:A','US',None)]:
   self.assertEqual(a.yahoo_home_symbol(s,c),y,s)
if __name__=='__main__':unittest.main()
