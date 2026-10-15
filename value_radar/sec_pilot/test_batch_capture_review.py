import copy
import unittest
from batch_capture_review import prepare_capture,apply_candidate

class BatchTests(unittest.TestCase):
    def setUp(self):
        self.days=['2020-01-02','2020-01-03','2020-01-06']
        self.capture=dict(symbol='T',source='https://example.org/history',provider='Fixture',currency='USD',
                          adjustment='Adjusted: Splits and Dividends',
                          rows=[dict(date=d,close='100',volume='10') for d in self.days])
    def test_missing_volume_is_quarantined_without_return_bridge(self):
        self.capture['rows'][1]['volume']='-'
        rows,excluded,observed=prepare_capture(self.capture,self.days)
        self.assertEqual(len(rows),2);self.assertEqual(excluded[0]['date'],self.days[1])
        self.assertEqual(rows[-1]['Tagesrendite'],'');self.assertEqual(observed,self.days)
    def test_source_capture_is_not_mutated(self):
        original=copy.deepcopy(self.capture);prepare_capture(self.capture,self.days)
        self.assertEqual(original,self.capture)
    def test_duplicate_invalid_row_cannot_be_hidden(self):
        self.capture['rows'].append(dict(date=self.days[0],close='100',volume='-'))
        with self.assertRaises(ValueError):prepare_capture(self.capture,self.days)
    def test_bad_price_is_not_repaired(self):
        self.capture['rows'][1]['close']='-'
        with self.assertRaises(ValueError):prepare_capture(self.capture,self.days)
    def test_non_session_is_rejected(self):
        self.capture['rows'][1]['date']='2020-01-04'
        with self.assertRaises(ValueError):prepare_capture(self.capture,self.days)
    def test_zero_volume_is_not_a_flat_return(self):
        self.capture['rows'][-1]['volume']='0'
        rows,excluded,_=prepare_capture(self.capture,self.days)
        self.assertEqual(len(rows),2);self.assertEqual(len(excluded),1)
    def test_denominator_change_rejected(self):
        d=[dict(identity='T',sessions=n,expected_windows=10,pending_windows=2,mature_windows=8) for n in (21,63,126)]
        counts={n:dict(expected_windows=9,pending_windows=2,mature_windows=7) for n in (21,63,126)}
        with self.assertRaises(ValueError):apply_candidate(d,'T',counts)
    def test_missing_baseline_horizon_rejected(self):
        with self.assertRaises(ValueError):apply_candidate([], 'T', {})
    def test_failed_replacement_is_atomic(self):
        d=[dict(identity='T',sessions=n,expected_windows=10,pending_windows=2,mature_windows=8) for n in (21,63,126)]
        original=copy.deepcopy(d)
        counts={n:dict(expected_windows=10,pending_windows=2,mature_windows=8) for n in (21,63,126)}
        counts[126]['mature_windows']=7
        with self.assertRaises(ValueError):apply_candidate(d,'T',counts)
        self.assertEqual(d,original)

if __name__=='__main__':unittest.main()
