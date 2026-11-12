import datetime as dt
import unittest
from regulatory_context import build_intl

ISIN='JP3902900004'
SRC={'type':'basel_pillar3_cr1','url':'https://example.org/b3.pdf','sha256':'c'*64,'location':'PDF page 30, CR1 row 1'}
ISSUER={'issuer':'MUFG','jurisdiction':'JP','regulator':'JFSA','scope':'consolidated_group','period':'2026-06-30','metrics':{'cet1_ratio':.14},'lcr':1.5,'nsfr':None,
        'cet1Requirement':None,'defaultedLoanRatio':.0107,'creditPeriod':'2026-03-31','creditSource':SRC,
        'source':{'type':'basel_pillar3_km1','url':'https://example.org/km1.pdf','sha256':'b'*64}}
ROW={'listing_symbol':'NYSE:MUFG','ticker':'MUFG','isin':ISIN,'currency':'JPY','name':'MUFG','security_type':'stock'}
NOW=dt.datetime(2026,11,11,tzinfo=dt.timezone.utc)

def run(**change):
    data={'schema':1,'method':'intl-bank-metrics-v1','importedAt':'2026-11-11T00:00:00+00:00','mappingReviewExpires':'2027-05-08','issuers':{ISIN:{**ISSUER,**change}}}
    return build_intl({'kandidaten':[ROW]},data,NOW)['stocks']['NYSE:MUFG']

class SeparateCreditPeriodTests(unittest.TestCase):
    def test_own_period_and_source_are_carried(self):
        c=run()['creditQuality']
        self.assertEqual((c['period'],c['periodBasis'],c['sourceFileSha256'],c['sourceDetail']),('2026-03-31','separate_cr1','c'*64,'PDF page 30, CR1 row 1'))
        self.assertEqual(c['scoreContribution'],0)
    def test_same_period_without_block_unchanged(self):
        c=run(creditPeriod=None,creditSource=None)['creditQuality']
        self.assertEqual(c['period'],'2026-06-30');self.assertNotIn('periodBasis',c)
    def test_invalid_blocks_drop_only_credit(self):
        for change in ({'creditPeriod':'2026-01-30'},{'creditPeriod':'2026-09-30'},{'creditSource':{**SRC,'sha256':'x'}},{'creditSource':{**SRC,'type':'basel_pillar3_km1'}},
                       {'creditSource':{**SRC,'url':'http://example.org'}},{'creditSource':None},{'creditPeriod':None}):
            r=run(**change)
            self.assertIsNone(r['creditQuality'],change);self.assertEqual(r['metrics']['cet1_ratio']['value'],.14)

RULE={'url':'https://www.fsa.go.jp/x.pdf','sha256':'d'*64,'location':'Notice 62 Art. 2'}
DOM={'issuer':'Resona','jurisdiction':'JP','regulator':'JFSA','standard':'jp_domestic_core_capital','period':'2026-06-30','domesticCapitalRatio':.1265,
     'source':{'type':'bank_capital_release','url':'https://example.org/r.pdf','sha256':'e'*64,'location':'p. 1'},'lcrRule':RULE}
RROW={'listing_symbol':'TSE:8308','ticker':'8308.T','isin':'JP3500610005','currency':'JPY','name':'Resona','security_type':'stock'}
def run_dom(row=RROW,**change):
    data={'schema':1,'method':'intl-bank-metrics-v1','importedAt':'2026-11-12T00:00:00+00:00','mappingReviewExpires':'2027-05-08','issuers':{},'domesticStandard':{'JP3500610005':{**DOM,**change}}}
    return build_intl({'kandidaten':[row]},data,NOW)

class DomesticStandardTests(unittest.TestCase):
    def test_record_marks_not_applicable_with_proof(self):
        r=run_dom()['stocks']['TSE:8308']
        self.assertEqual((r['state'],r['scope'],r['standard'],r['domesticCapitalRatio']),('not_applicable','domestic_capital_standard','jp_domestic_core_capital',.1265))
        self.assertEqual(r['lcrRule'],RULE);self.assertEqual(r['metrics'],{});self.assertIsNone(r['creditQuality'])
    def test_identity_freshness_and_proof(self):
        self.assertEqual(run_dom(row={**RROW,'security_type':'preferred'})['rejected']['TSE:8308'],'listing_identity_unverified')
        self.assertEqual(run_dom(period='2026-01-30')['rejected']['TSE:8308'],'domestic_evidence_stale_or_unknown')
        self.assertEqual(run_dom(standard='other')['rejected']['TSE:8308'],'domestic_evidence_stale_or_unknown')
        self.assertEqual(run_dom(lcrRule={**RULE,'sha256':''})['rejected']['TSE:8308'],'domestic_evidence_unverified')
        self.assertEqual(run_dom(source={**DOM['source'],'url':'http://x'})['rejected']['TSE:8308'],'domestic_evidence_unverified')

if __name__=='__main__':unittest.main()
