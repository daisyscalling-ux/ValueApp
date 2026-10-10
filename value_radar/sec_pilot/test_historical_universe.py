import datetime as dt
import unittest
from historical_universe import audit

class HistoricalUniverseTests(unittest.TestCase):
    def fixture(self):
        day=dt.date(2020,1,2);sessions=[]
        while len(sessions)<130:
            if day.weekday()<5:sessions.append(day.isoformat())
            day+=dt.timedelta(days=1)
        url='https://example.org/synthetic-test-only'
        return {'schema':1,'coverage':{'start':sessions[0],'end':sessions[-1],'source':url,
                'membership_completeness':'provider_attested','return_basis':'total_return_including_delisting'},
                'securities':{'old-id':{'symbol':'SAME','source':url},'new-id':{'symbol':'SAME','source':url}},
                'memberships':[{'security_id':'old-id','start':sessions[0],'end':sessions[10],'source':url},
                               {'security_id':'new-id','start':sessions[10],'end':sessions[-1],'source':url}],
                'sessions':sessions,'decisions':[sessions[0]],
                'returns':[{'security_id':'old-id','date':d,'total_return':0.0,'source':url} for d in sessions]}
    def test_removed_member_remains_in_outcome_and_ticker_not_reused(self):
        r=audit(self.fixture());self.assertEqual(r['status'],'ready_for_feature_join')
        self.assertEqual(r['expected_windows'],3);self.assertEqual({x['security_id'] for x in r['observations']},{'old-id'})
    def test_missing_dead_company_is_not_dropped_or_flatfilled(self):
        d=self.fixture();d['returns']=d['returns'][:10]
        r=audit(d);self.assertEqual(r['status'],'incomplete');self.assertEqual(r['expected_windows'],3);self.assertEqual(r['usable_windows'],0)
    def test_zero_recovery_keeps_full_loss(self):
        d=self.fixture();d['returns'][5]['total_return']=-1
        s=d['securities']['old-id'];s.update(termination_date=d['sessions'][5],terminal_source=s['source'],terminal_adjustment='included_in_total_return')
        r=audit(d);self.assertEqual(r['observations'][0]['loss'],1);self.assertEqual(r['observations'][0]['return'],-1)
    def test_unverified_terminal_event_blocks_outcomes(self):
        d=self.fixture();d['securities']['old-id']['termination_date']=d['sessions'][5]
        self.assertEqual(audit(d)['usable_windows'],0)
    def test_missing_attestation_and_empty_members_never_pass(self):
        d=self.fixture();d['coverage']['membership_completeness']='unknown';self.assertEqual(audit(d)['status'],'incomplete')
        d['memberships']=[]
        with self.assertRaises(ValueError):audit(d)
    def test_conflicting_return_and_membership_rejected(self):
        d=self.fixture();d['returns'].append(dict(d['returns'][1],total_return=.5))
        with self.assertRaises(ValueError):audit(d)
        d=self.fixture();d['memberships'].append(dict(d['memberships'][0]))
        with self.assertRaises(ValueError):audit(d)
    def test_future_membership_not_in_earlier_selection(self):
        d=self.fixture();d['decisions']=[d['sessions'][10]]
        r=audit(d);self.assertEqual(r['usable_windows'],0)
        self.assertTrue(all(x.get('security_id')=='new-id' for x in r['gaps']))

if __name__=='__main__':unittest.main()
