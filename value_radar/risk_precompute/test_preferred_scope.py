import unittest
import risk_construct_coverage as cc
STATS={'observations':600,'error':'','es':.03,'vol':.3,'dd':.4}
class PreferredScope(unittest.TestCase):
 def test_detection_like_app(self):
  for t in ['BAC-PB','JPM-PD','WFC-PY','GS-PA','NYSE:JPM.PRD']:self.assertTrue(cc.preferred_instrument({'ticker':t}),t)
  for t in ['BAC','BRK-B','SAN.PA','NOVO-B.CO','PBR.A']:self.assertFalse(cc.preferred_instrument({'ticker':t}),t)
 def test_preferred_counts_by_design_not_missing(self):
  uni={'kandidaten':[{'ticker':'BAC-PB','name':'Bank of America Corporation','industry':'Major banks'}]}
  sh={'BAC-PB':{'balance':{'profile':'bank'},'market':{'state':'available'}}}
  r=cc.build(uni,sh,{},{})
  self.assertEqual(r['largestGaps'],[])
  self.assertEqual(r['profiles']['bank']['averageWeight']['missing'],0)
  self.assertEqual(r['profiles']['bank']['averageWeight']['filled'],0)
if __name__=='__main__':unittest.main()
