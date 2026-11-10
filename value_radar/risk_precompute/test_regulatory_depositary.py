import datetime as dt
import unittest
from regulatory_context import build_intl

ISIN='AU000000CBA7'
ISSUER={'issuer':'Commonwealth Bank of Australia','jurisdiction':'AU','regulator':'APRA','scope':'highest_consolidation_level','period':'2026-06-30',
        'metrics':{'cet1_ratio':.12,'tier1_ratio':.135,'total_capital_ratio':.208},'lcr':1.32,'nsfr':1.151,'cet1Requirement':None,
        'source':{'type':'apra_adi_centralised_publication','url':'https://example.org','sha256':'a'*64}}
DATA={'schema':1,'method':'intl-bank-metrics-v1','importedAt':'2026-11-09T21:52:35+00:00','mappingReviewExpires':'2027-05-08','issuers':{ISIN:ISSUER}}
ORD={'listing_symbol':'OTC:CBAUF','ticker':'CBAUF','isin':ISIN,'currency':'USD','name':'Commonwealth Bank of Australia','security_type':'stock'}
ADR={'listing_symbol':'OTC:CMWAY','ticker':'CMWAY','isin':ISIN,'currency':'USD','name':'Commonwealth Bank of Australia','security_type':'dr'}

class DepositaryTests(unittest.TestCase):
    now=dt.datetime(2026,11,10,tzinfo=dt.timezone.utc)
    def test_dr_adopts_verified_ordinary_with_own_identity(self):
        out=build_intl({'kandidaten':[ADR,ORD]},DATA,self.now)
        r=out['stocks']['OTC:CMWAY']
        self.assertEqual(r['depositaryOf'],'OTC:CBAUF')
        self.assertEqual(r['inputIdentity']['security_type'],'dr')
        self.assertEqual(r['inputIdentity']['listing_symbol'],'OTC:CMWAY')
        self.assertEqual(r['liquidity']['reportedRatio'],1.32)
        self.assertNotIn('depositaryOf',out['stocks']['OTC:CBAUF'])
    def test_dr_without_verified_ordinary_stays_open(self):
        out=build_intl({'kandidaten':[ADR]},DATA,self.now)
        self.assertNotIn('OTC:CMWAY',out['stocks'])
        self.assertEqual(out['rejected']['OTC:CMWAY'],'depositary_without_verified_ordinary')
    def test_dr_with_expired_reference_or_other_class_rejected(self):
        for change in ({'listing_reference_status':'expired'},{'share_class':'preferred'}):
            out=build_intl({'kandidaten':[{**ADR,**change},ORD]},DATA,self.now)
            self.assertEqual(out['rejected']['OTC:CMWAY'],'listing_identity_unverified')

if __name__=='__main__':unittest.main()
