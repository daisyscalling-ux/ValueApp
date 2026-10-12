import unittest
from free_sources import reconstruct,research_id
from identity_audit import resolve, normalize, price_status, load_evidence

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

class IdentityTests(unittest.TestCase):
    def setUp(self):
        self.e=load_evidence()
    def test_reused_symbols_keep_old_issuers_separate(self):
        for symbol,day in [('DOW','2017-09-01'),('SNDK','2016-05-13')]:
            self.assertNotEqual(resolve(symbol,day,'',self.e)[0],symbol)
            self.assertEqual(resolve(symbol,'2026-01-01','',self.e)[0],symbol)
        for symbol in ['FOX','FOXA']:
            event=dict(date='2019-03-19',added=symbol,removed=symbol,
                       added_name='Fox Corporation',removed_name='21st Century Fox')
            cur,events,_=normalize({symbol:{}},[event],self.e)
            spans,issues=reconstruct(cur,events,'2014-01-01','2026-01-01')
            self.assertFalse(issues)
            self.assertEqual(len({s['symbol'] for s in spans}),2)
            self.assertEqual(next(s for s in spans if s['symbol']==symbol)['start'],'2019-03-19')
    def test_q_rename_preserves_iqvia_and_separate_qnity(self):
        events=[dict(date='2025-11-03',added='Q',removed=''),
                dict(date='2017-11-15',added='IQV',removed='Q'),
                dict(date='2017-08-29',added='Q',removed='')]
        cur,events,_=normalize({'Q':{},'IQV':{}},events,self.e)
        spans,issues=reconstruct(cur,events,'2014-01-01','2026-01-01')
        self.assertFalse(issues)
        self.assertEqual({s['symbol']:s['start'] for s in spans},
                         {'Q':'2025-11-03','IQV':'2017-08-29'})
    def test_ceridian_rename_is_not_an_exit_or_second_security(self):
        events=[dict(date='2026-02-09',added='',removed='DAY'),
                dict(date='2024-02-01',added='DAY',removed='CDAY'),
                dict(date='2021-09-20',added='CDAY',removed='')]
        cur,events,_=normalize({},events,self.e)
        spans,issues=reconstruct(cur,events,'2014-01-01','2026-10-12')
        self.assertFalse(issues)
        self.assertEqual(spans,[dict(symbol='DAY',start='2021-09-20',end='2026-02-09',left_censored=False)])
    def test_three_renames_repair_membership_without_extra_members(self):
        events=[dict(date='2018-06-20',added='FLT',removed='',added_name='FleetCor')]
        cur, corrected, changes=normalize({'CPAY':{}},events,self.e)
        r,issues=reconstruct(cur,corrected,'2014-01-01','2026-10-11')
        self.assertFalse(issues);self.assertEqual(len(r),1)
        self.assertEqual(r[0]['start'],'2018-06-20')
        self.assertEqual(changes[0]['original_symbol'],'FLT')
        self.assertEqual(resolve('SATS','2026-03-23','EchoStar',self.e)[0],'ECHO')
        self.assertEqual(resolve('RE','2017-06-19','Everest',self.e)[0],'EG')
    def test_under_armour_separate_classes(self):
        self.assertEqual(resolve('UA','2014-05-01','Under Armour',self.e)[0],'UAA')
        self.assertEqual(resolve('UA','2016-04-08','Under Armour (Class C)',self.e)[0],'UA')
        self.assertEqual(resolve('UA','2016-04-08','Under Armour',self.e)[0],'UA_CLASS_UNRESOLVED')
    def test_allergan_separate_issuers(self):
        old=resolve('AGN','2015-03-23','Allergan',self.e)[0]
        new=resolve('AGN','2020-05-12','Allergan',self.e)[0]
        self.assertNotEqual(old,new)
        self.assertEqual(resolve('ACT','2015-01-01','Actavis',self.e)[0],new)
        self.assertTrue(price_status(new,[],[],{},self.e)[0].startswith('blocked'))
    def test_suntrust_never_uses_solidion_or_truist_prices(self):
        self.assertEqual(resolve('STI','2019-12-09','SunTrust',self.e)[0],'STI')
        status,n=price_status('STI',[{'Datum':'2019-01-01'}],[{'start':'2014-01-01','end':'2020-01-01'}],{},self.e)
        self.assertEqual(status,'blocked_known_ticker_reuse');self.assertEqual(n,0)
    def test_nonoverlap_rejected_and_partial_coverage_not_certified(self):
        period=[{'start':'2014-01-01','end':'2019-01-01'}]
        status,n=price_status('BEAM',[{'Datum':'2020-01-01'}],period,{},self.e)
        self.assertEqual(status,'blocked_no_membership_overlap')
        status,n=price_status('X',[{'Datum':'2018-01-01'},{'Datum':'2018-01-02'}],period,{},self.e)
        self.assertEqual(status,'research_only_identity_and_returns_unverified')
    def test_rename_does_not_cover_reused_ticker_after_effective_date(self):
        self.assertEqual(resolve('FLT','2025-01-01','Other company',self.e)[0],'FLT')
    def test_explicit_rename_is_not_an_index_exit(self):
        events=[dict(date='2022-01-10',added='WTW',removed='WLTW'),dict(date='2016-01-05',added='WLTW',removed='')]
        current,corrected,changes=normalize({'WTW':{}},events,self.e)
        intervals,issues=reconstruct(current,corrected,'2014-01-01','2026-10-11')
        self.assertFalse(issues);self.assertEqual(len(intervals),1)
        self.assertEqual(intervals[0]['start'],'2016-01-05')
    def test_bread_rename_and_fortune_exact_event_override(self):
        self.assertEqual(resolve('ADS','2020-06-22','Alliance Data Systems',self.e)[0],'BFH')
        event=dict(date='2022-12-19',added='FSLR',removed='FBHS',removed_name='Fortune Brands Home & Security')
        _,fixed,_=normalize({},[event],self.e)
        self.assertEqual(fixed[0]['removed'],'FBIN')
        for key,value in [('date','2023-12-19'),('removed_name','Different company')]:
            changed=dict(event);changed[key]=value
            _,fixed,_=normalize({},[changed],self.e)
            self.assertEqual(fixed[0]['removed'],'FBHS')
        self.assertTrue(any(a['identity']=='FBIN' for a in self.e['capital_actions_review']))

if __name__=='__main__':unittest.main()

