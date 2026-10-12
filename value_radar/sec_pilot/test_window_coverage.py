import unittest
from window_coverage import inspect_windows, recovery_priorities


class WindowCoverageTests(unittest.TestCase):
    def setUp(self):
        self.days=['2020-01-02','2020-01-03','2020-01-06','2020-01-07','2020-01-08']
        self.rows=[dict(Datum=d,Adjusted_Close='100',Tagesrendite='' if i==0 else '0')
                   for i,d in enumerate(self.days)]
    def check(self,rows=None,end='2020-01-03'):
        return inspect_windows(self.days,[('2020-01-02',end)],self.rows if rows is None else rows,
                               '2020-01-02',horizons=(2,))[0][2]
    def test_exit_does_not_end_holding_window(self):
        r=self.check();self.assertEqual(r['covered_windows'],1)
        self.assertEqual(r['post_exit_covered_windows'],1)
    def test_missing_after_exit_is_not_dropped(self):
        r=self.check(self.rows[:2]);self.assertEqual(r['incomplete_windows'],1)
        self.assertEqual(r['expected_windows'],1)
    def test_entry_return_is_excluded_but_entry_price_required(self):
        rows=[dict(r) for r in self.rows];rows[1]['Tagesrendite']=''
        self.assertEqual(self.check(rows)['covered_windows'],1)
        self.assertEqual(self.check(rows[:1]+rows[2:])['missing_entry_windows'],1)
    def test_pending_distinct_from_missing(self):
        r=self.check([],end='2020-01-09')
        self.assertEqual(r['expected_windows'],5)
        self.assertEqual(r['pending_windows'],3)
        self.assertEqual(r['incomplete_windows'],2)
    def test_membership_end_exclusive_and_reentry(self):
        counts,_=inspect_windows(self.days,[('2020-01-02','2020-01-03'),('2020-01-07','2020-01-09')],
                                self.rows,'2020-01-02',horizons=(2,))
        self.assertEqual(counts[2]['expected_windows'],3)
    def test_duplicate_and_missing_session_never_valid(self):
        self.assertEqual(self.check(self.rows[:3]+[self.rows[2]]+self.rows[3:])['incomplete_windows'],1)
        self.assertEqual(self.check(self.rows[:2]+self.rows[3:])['incomplete_windows'],1)
    def test_priority_includes_long_only_gaps_and_sorts_primary_first(self):
        details=[dict(identity=sid,sessions=n,incomplete_windows=(count if n==126 or sid=='A' else 0),
                      post_exit_mature_windows=2,post_exit_covered_windows=1)
                 for sid,count in [('A',3),('B',20)] for n in (21,63,126)]
        identities=[dict(identity='A',status='missing_prices'),dict(identity='B',status='blocked_known_ticker_reuse')]
        r=recovery_priorities(details,identities)
        self.assertEqual([x['identity'] for x in r],['A','B'])
        self.assertIn('Verify security identity',r[1]['next_data_step'])
        self.assertEqual(r[0]['incomplete_post_exit_63'],1)


if __name__=='__main__':unittest.main()

