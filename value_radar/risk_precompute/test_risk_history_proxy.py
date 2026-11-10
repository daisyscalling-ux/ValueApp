import copy,datetime as dt,unittest
from risk_history_proxy import build
NOW=dt.datetime(2026,11,10,8,tzinfo=dt.timezone.utc)
def rec(sym,obs=1000,err='',cur='EUR',when='2026-11-10T07:00:00Z'):
 return {'format':'risk-summary','schema':1,'symbol':sym,'currency':cur,'retrievedAt':when,'statistics':{'observations':obs,'error':err,'es':.03 if obs>=505 and not err else None,'vol':.2,'dd':.3,'drawdown':.05}}
UNI={'kandidaten':[{'listing_symbol':'OTC:ALIZF','isin':'DE0008404005','security_type':'stock'},{'listing_symbol':'XETR:ALV','isin':'DE0008404005','security_type':'stock'},
 {'listing_symbol':'OTC:ALIZY','isin':'DE0008404005','security_type':'dr'},{'listing_symbol':'OTC:X','isin':'XX0000000001','security_type':'stock'}]}
class Proxy(unittest.TestCase):
 def test_missing_or_broken_own_history_gets_marked_home_history(self):
  r={'stocks':{'XETR:ALV':rec('XETR:ALV'),'OTC:ALIZY':rec('OTC:ALIZY',err='Kurshistorie enthält längere Lücken.',cur='USD')}}
  rep=build(r,UNI,NOW);self.assertEqual(rep,{'proxied':2})
  p=r['stocks']['OTC:ALIZF'];self.assertEqual((p['symbol'],p['historySource']['symbol'],p['historySource']['reason'],p['currency']),('OTC:ALIZF','XETR:ALV','own_history_missing','EUR'))
  self.assertIn('Heimatnotierung XETR:ALV',p['historyNote']);self.assertEqual(r['stocks']['OTC:ALIZY']['historySource']['reason'],'own_history_error')
  self.assertNotIn('OTC:X',r['stocks'])
 def test_own_complete_history_and_otc_homes_never_used_or_overwritten(self):
  r={'stocks':{'XETR:ALV':rec('XETR:ALV'),'OTC:ALIZF':rec('OTC:ALIZF',cur='USD')}}
  build(r,UNI,NOW);self.assertNotIn('historySource',r['stocks']['OTC:ALIZF']);self.assertNotIn('OTC:ALIZY',[k for k,v in r['stocks'].items() if v.get('historySource',{}).get('symbol','').startswith('OTC:')])
 def test_stale_home_withdraws_proxy(self):
  r={'stocks':{'XETR:ALV':rec('XETR:ALV')}};build(r,UNI,NOW);self.assertIn('OTC:ALIZF',r['stocks'])
  r['stocks']['XETR:ALV']=rec('XETR:ALV',when='2026-11-01T00:00:00Z');rep=build(r,UNI,NOW)
  self.assertNotIn('OTC:ALIZF',r['stocks']);self.assertEqual(rep['withdrawn'],2)
if __name__=='__main__':unittest.main()
