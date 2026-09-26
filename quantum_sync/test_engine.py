import unittest,sys,math
from pathlib import Path
from datetime import date,timedelta
sys.path.insert(0,str(Path(__file__).parent/'engine'))
from bridge import forward_view
class Outlook(unittest.TestCase):
 def test_bands_and_target(self):
  fund={'price':100,'eps_trailing':5,'earnings_growth':.1}
  stock={'priceDate':'2026-09-25','history':[{'date':(date(2026,9,25)-timedelta(days=i)).isoformat(),'close':100*math.exp(.001*i+.02*math.sin(i))} for i in range(100)]}
  r=forward_view(stock,fund,'quality',False)
  self.assertEqual(len(r['bands']),4)
  self.assertTrue(all(0<p['low']<=p['center']<=p['high'] for p in r['bands']))
  self.assertAlmostEqual(r['target']['ziel'],r['target']['eps_annahme']*r['target']['kgv_annahme'],places=1)
  self.assertEqual(forward_view({},fund,'quality',False)['bands'],[])
  self.assertIsNone(forward_view(stock,fund,'quality',True)['target'])
if __name__=='__main__':unittest.main()

