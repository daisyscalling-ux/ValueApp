import unittest
from session_coverage import expected_sessions, inspect_rows, gap_ranges

class SessionTests(unittest.TestCase):
    def setUp(self):
        self.days=['2024-01-02','2024-01-03','2024-01-04','2024-01-05','2024-01-08']
    def test_missing_session_rejects_short_return_bridge(self):
        rows=[dict(Datum=self.days[0],Adjusted_Close=100,Tagesrendite=''),dict(Datum=self.days[2],Adjusted_Close=110,Tagesrendite='.1')]
        result,missing,returns=inspect_rows(self.days,self.days[:3],rows)
        self.assertEqual(missing,[self.days[1]])
        self.assertEqual(result['valid_return_sessions'],0)
        self.assertEqual(len(returns),2)
    def test_weekend_is_not_a_gap(self):
        rows=[dict(Datum=self.days[3],Adjusted_Close=100,Tagesrendite=''),dict(Datum=self.days[4],Adjusted_Close=101,Tagesrendite='.01')]
        r,m,mr=inspect_rows(self.days,[self.days[4]],rows)
        self.assertFalse(m);self.assertFalse(mr);self.assertEqual(r['valid_return_sessions'],1)
    def test_exclusive_exit_and_reentry(self):
        self.assertEqual(expected_sessions(self.days,[(self.days[0],self.days[1]),(self.days[3],'2024-01-09')]),[self.days[0],self.days[3],self.days[4]])
    def test_no_prices_still_counts_expected_sessions(self):
        r,m,mr=inspect_rows(self.days,self.days,[])
        self.assertEqual(r['expected_price_sessions'],5);self.assertEqual(len(m),5)
    def test_duplicate_or_invalid_price_cannot_support_return(self):
        rows=[dict(Datum=self.days[0],Adjusted_Close=100,Tagesrendite=''),dict(Datum=self.days[0],Adjusted_Close=100,Tagesrendite=''),dict(Datum=self.days[1],Adjusted_Close=101,Tagesrendite='.01')]
        r,m,mr=inspect_rows(self.days,self.days[:2],rows)
        self.assertEqual(r['duplicate_dates'],1);self.assertEqual(r['valid_return_sessions'],0)
    def test_compressed_gaps_preserve_session_count(self):
        gaps=gap_ranges(self.days,[self.days[0],self.days[1],self.days[4]])
        self.assertEqual([g['sessions'] for g in gaps],[2,1])

if __name__=='__main__':unittest.main()
