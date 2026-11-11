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

if __name__=='__main__':unittest.main()
