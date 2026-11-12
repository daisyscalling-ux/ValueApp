import datetime as dt
import json
import unittest
from pathlib import Path
import regulatory_context as rc

NOW=dt.datetime(2026,11,12,20,tzinfo=dt.timezone.utc)
ROW={'listing_symbol':'NYSE:HSBC','ticker':'HSBC','isin':'GB0005405286','currency':'USD','name':'HSBC Holdings Plc','security_type':'dr'}
ENTRY={'listing_symbol':'NYSE:HSBC','isin':'GB0005405286','currency':'USD','security_type':'dr','issuerKey':{'issuerIsin':'GB0005405286'},'kind':'adr_without_ordinary_in_universe',
       'evidence':'ADR-Programm, 1 ADS = 5 Stammaktien','sourceUrl':'https://www.about.us.hsbc.com/investor-relations','sourceSha256':'a'*64,'reviewedOn':'2026-11-12','reviewExpires':'2027-05-11'}
REVIEW={'schema':1,'method':rc.DR_METHOD,'entries':[ENTRY]}
ISSUER={'issuer':'HSBC Holdings plc','jurisdiction':'GB','regulator':'PRA','scope':'consolidated_group','period':'2026-09-30','metrics':{'cet1_ratio':.139},'lcr':1.32,'nsfr':None,
        'cet1Requirement':None,'source':{'type':'basel_pillar3_km1','url':'https://example.org/km1.pdf','sha256':'b'*64}}
DATA={'schema':1,'method':'intl-bank-metrics-v1','importedAt':'2026-11-12T00:00:00+00:00','mappingReviewExpires':'2027-05-08','issuers':{'GB0005405286':ISSUER}}

class StandaloneDepositaryTests(unittest.TestCase):
    def run_intl(self,row=ROW,review=REVIEW):
        return rc.build_intl({'kandidaten':[row]},DATA,NOW,dr_review=review)
    def test_reviewed_adr_gets_group_ratios_with_marker(self):
        x=self.run_intl()['stocks']['NYSE:HSBC']
        self.assertEqual(x['metrics']['cet1_ratio']['value'],.139);self.assertEqual(x['inputIdentity']['security_type'],'dr')
        self.assertEqual(x['standaloneDepositary']['kind'],'adr_without_ordinary_in_universe');self.assertNotIn('depositaryOf',x)
    def test_without_review_the_dr_stays_open(self):
        self.assertEqual(self.run_intl(review=None)['rejected']['NYSE:HSBC'],'depositary_without_verified_ordinary')
    def test_any_identity_or_proof_deviation_keeps_it_open(self):
        for change in ({'isin':'GB0000000000'},{'currency':'GBP'},{'listing_symbol':'OTC:HBCYF'},{'security_type':'stock'}):
            out=self.run_intl(row={**ROW,**change})
            self.assertNotIn('standaloneDepositary',out['stocks'].get(ROW['listing_symbol'] if 'listing_symbol' not in change else change['listing_symbol'],{}),change)
        for change in ({'reviewExpires':'2026-11-01'},{'reviewedOn':'2026-12-01'},{'sourceSha256':'x'},{'sourceUrl':'http://x'},{'evidence':''},{'issuerKey':{'issuerIsin':'GB0000000000'}}):
            out=self.run_intl(review={**REVIEW,'entries':[{**ENTRY,**change}]})
            self.assertEqual(out['rejected'].get('NYSE:HSBC'),'depositary_without_verified_ordinary',change)
        self.assertIn('depositary_without_verified_ordinary',self.run_intl(review={**REVIEW,'method':'other'})['rejected'].values())
    def test_repository_registry_entries_are_valid(self):
        reg=json.loads((Path(__file__).resolve().parents[1]/'regulatory_export/reviewed-depositary-listings.json').read_text(encoding='utf-8'))
        self.assertEqual(reg['method'],rc.DR_METHOD)
        for e in reg['entries']:
            row={k:e[k] for k in ('listing_symbol','isin','currency','security_type')}
            self.assertIsNotNone(rc.standalone_dr(row,reg,NOW,e['issuerKey']),e['listing_symbol'])

if __name__=='__main__':unittest.main()
