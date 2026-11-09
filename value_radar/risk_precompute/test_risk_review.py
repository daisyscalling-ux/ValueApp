import copy
import datetime as dt
import unittest
from risk_review import review_news,bank_credit_comparison,CODES
from news_identity import identity_fingerprint,prepare_universe

NOW=dt.datetime(2026,11,5,20,tzinfo=dt.timezone.utc)

class NewsReview(unittest.TestCase):
    def setUp(self):
        self.u={'kandidaten':[{'listing_symbol':'NYSE:EX','ticker':'EX','name':'Example Corporation','isin':'US0378331005'}]};prepare_universe(self.u['kandidaten'])
        self.c={'id':'abc','headline':'Example cuts outlook','associatedSymbols':['NYSE:EX'],'categories':['earnings_warning'],'sources':[{'url':'https://example.com/news'}]}
        self.report={'candidates':[self.c],'summary':{},'limitations':[]}
        self.d={'candidateId':'abc','symbol':'NYSE:EX','inputFingerprint':identity_fingerprint(self.u['kandidaten'][0]),'state':'confirmed_event','reviewedAt':'2026-11-05T19:00:00+00:00','expiresAt':'2026-11-12T19:00:00+00:00','reviewer':'test','rationale':'Guidance change','sourceUrl':'https://example.com/news','sourceType':'issuer_primary','sourceLocator':'Outlook','eventDate':'2026-11-05','counterContext':'Revenue grew','sourceAccess':'direct'}
    def run_review(self,decisions=None):return review_news(self.report,self.u,{'schema':1,'decisions':decisions if decisions is not None else [self.d]},NOW)
    def test_confirmation_requires_explicit_review_and_keeps_zero_score(self):
        c=self.run_review()['candidates'][0]
        self.assertEqual(c['verifiedSymbols'],['NYSE:EX']);self.assertEqual(c['scoreContribution'],0)
        self.assertFalse(self.run_review([])['candidates'][0]['verified'])
    def test_stale_future_changed_identity_and_missing_evidence_rejected(self):
        for patch in [{'expiresAt':'2026-11-04T00:00:00+00:00'},{'reviewedAt':'2026-11-06T00:00:00+00:00'},{'inputFingerprint':'wrong'},{'sourceType':'publisher'},{'sourceLocator':''},{'counterContext':''},{'eventDate':'2026-11-06'},{'sourceAccess':'unknown'}]:
            with self.subTest(patch=patch):
                r=self.run_review([{**self.d,**patch}]);self.assertFalse(r['candidates'][0]['verified']);self.assertEqual(r['summary']['invalidReviewDecisions'],1)
    def test_conflicting_decisions_never_last_write_wins(self):
        self.assertFalse(self.run_review([self.d,self.d])['candidates'][0]['verified'])
    def test_solicitation_is_not_new_event_or_automatically_dismissed(self):
        self.c.update(headline='Investors have opportunity to lead securities fraud lawsuit',categories=['legal_regulatory'])
        c=self.run_review([])['candidates'][0]
        self.assertEqual(c['triage']['kind'],'legal_solicitation');self.assertEqual(c['state'],'review_required');self.assertFalse(c['verified'])
    def test_settlement_is_not_solicitation(self):
        self.c.update(headline='Company reaches settlement with claimants',categories=['legal_regulatory'])
        self.assertEqual(self.run_review([])['candidates'][0]['triage']['kind'],'event_candidate')
    def test_rejection_binds_exact_source_and_symbol(self):
        d={**self.d,'state':'not_subject_of_tagged_event'}
        self.assertEqual(self.run_review([d])['candidates'][0]['decisions'][0]['state'],'not_subject_of_tagged_event')
        self.assertEqual(self.run_review([{**d,'sourceUrl':'https://other.example/x'}])['summary']['invalidReviewDecisions'],1)
        self.c['associatedSymbols'].append('NYSE:OTHER')
        self.assertEqual(self.run_review()['candidates'][0]['verifiedSymbols'],['NYSE:EX'])


class BankCredit(unittest.TestCase):
    def rows(self):
        out=[]
        for i in range(7):
            parent={'state':'available','scope':'listed_consolidated_holding','period':'2026-06-30','rssdId':str(i+1),'sourceFileSha256':'a'*64}
            c={**parent,'method':'bhcf-loan-quality-v1','unit':'fraction','amountUnit':'USD_thousands','sourceImportedAt':'2026-10-29T00:00:00+00:00','components':{'nonaccrual':i,'past_due_30_89':1,'past_due_90':1,'held_for_investment':900,'held_for_sale':100},'totalLoans':1000,'sourceFields':CODES,'ratios':{'nonaccrual_or_90_past_due':(i+1)/1000}}
            out.append({'symbol':'NYSE:X'+str(i),'domains':{'identity':{'state':'available'},'balance':{'profile':'bank','bankCapital':{**parent,'creditQuality':c}}}})
        return out
    def compare(self,rows):return bank_credit_comparison({'stocks':rows},NOW)
    def test_same_period_comparison_excludes_self_and_deduplicates_holdings(self):
        rows=self.rows();r=self.compare(rows)['stocks']['NYSE:X0']
        self.assertEqual(r['peerCount'],6);self.assertAlmostEqual(r['peerMedian'],.0045);self.assertEqual(r['comparison'],'below_peer_median');self.assertEqual(r['scoreContribution'],0)
        duplicate=copy.deepcopy(rows[0]);duplicate['symbol']='OTC:ALIAS';rows.append(duplicate)
        self.assertEqual(self.compare(rows)['stocks']['NYSE:X1']['peerCount'],6)
    def test_invalid_credit_numbers_and_scope_not_admitted(self):
        for patch in [{'totalLoans':1001},{'ratios':{'nonaccrual_or_90_past_due':float('nan')}},{'rssdId':'wrong'},{'sourceImportedAt':'2027-01-01T00:00:00+00:00'}]:
            rows=self.rows();rows[0]['domains']['balance']['bankCapital']['creditQuality'].update(patch)
            self.assertNotIn('NYSE:X0',self.compare(rows)['stocks'])
        rows=self.rows();rows[0]['domains']['balance']['profile']='specialist_financial'
        self.assertIn('NYSE:X0',self.compare(rows)['stocks'],'specialist with verified US holding capital is a bank group')
        rows=self.rows();rows[0]['domains']['balance']['profile']='corporate'
        self.assertNotIn('NYSE:X0',self.compare(rows)['stocks'])
        rows=self.rows();rows[0]['domains']['balance']['profile']='specialist_financial';rows[0]['domains']['balance']['bankCapital']['scope']='eu_prudential_group'
        self.assertNotIn('NYSE:X0',self.compare(rows)['stocks'])
    def test_small_cohort_has_no_median_and_stale_has_no_rows(self):
        self.assertIsNone(self.compare(self.rows()[:5])['stocks']['NYSE:X0']['peerMedian'])
        self.assertFalse(bank_credit_comparison({'stocks':self.rows()},NOW+dt.timedelta(days=90))['stocks'])
    def test_conflicting_duplicate_excludes_whole_holding(self):
        rows=self.rows();d=copy.deepcopy(rows[0]);d['symbol']='OTC:ALIAS';p=d['domains']['balance']['bankCapital'];p['sourceFileSha256']='b'*64;p['creditQuality']['sourceFileSha256']='b'*64;rows.append(d)
        r=self.compare(rows);self.assertEqual(r['excludedConflictingHoldings'],['1']);self.assertNotIn('NYSE:X0',r['stocks'])

if __name__=='__main__':unittest.main()
