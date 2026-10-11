import unittest
from free_sources import reconstruct,research_id

class FreeSourceTests(unittest.TestCase):
    def test_removed_members_and_left_censoring(self):
        r,e=reconstruct({'NEW':{},'STAY':{}},[{'date':'2020-01-01','added':'NEW','removed':'OLD'}],'2014-01-01','2026-01-01')
        self.assertFalse(e);self.assertIn({'symbol':'OLD','start':'2014-01-01','end':'2020-01-01','left_censored':True},r)
    def test_reentry_has_separate_intervals(self):
        events=[{'date':'2022-01-01','added':'A','removed':'B'},{'date':'2020-01-01','added':'B','removed':'A'}]
        r,e=reconstruct({'A':{}},events,'2014-01-01','2026-01-01')
        self.assertFalse(e);self.assertEqual(sum(x['symbol']=='A' for x in r),2)
    def test_inconsistent_history_is_reported(self):
        r,e=reconstruct({'A':{}},[{'date':'2020-01-01','added':'MISSING','removed':'A'}],'2014-01-01','2026-01-01')
        self.assertEqual(len(e),2);self.assertTrue(research_id('A').startswith('UNVERIFIED_'))

if __name__=='__main__':unittest.main()
