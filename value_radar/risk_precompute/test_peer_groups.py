import copy
import datetime as dt
import json
from pathlib import Path
import unittest
from peer_groups import build, classify, name_key
NOW=dt.datetime(2026,10,21,12,tzinfo=dt.timezone.utc)
RULES={'aliases':{'banks - diversified':'major banks'},'reviewed':[]}
def row(symbol='NYSE:A', name='Company A', isin='US5949181045', **kwargs):
    return dict(listing_symbol=symbol,name=name,isin=isin,industry='Major banks',
                security_type='stock',metadata_asof='2026-10-20T00:00:00Z',currency='USD',**kwargs)
class PeerGroupsTests(unittest.TestCase):
    def run_rows(self, rows):return build({'kandidaten':rows},NOW,RULES)
    def test_bank_not_insurer_or_asset_manager(self):
        rows=[row(),row('NYSE:B','Bank B','US1729674242'),row('NYSE:C','Insurer','US00724F1012')]
        rows[1]['industry']='Banks - Diversified';rows[2]['industry']='Investment managers'
        self.assertEqual(self.run_rows(rows)['listings']['NYSE:A']['peerSymbols'],['NYSE:B'])
    def test_same_isin_and_share_classes_one_issuer(self):
        rows=[row(),row('XETR:A','Company A'),row('NYSE:B','Company B','US1729674242')]
        result=self.run_rows(rows)
        self.assertEqual(result['summary']['uniqueIssuers'],2)
        self.assertEqual(result['listings']['NYSE:B']['peerIssuerCount'],1)
        self.assertEqual(result['listings']['NYSE:A']['peerSymbols'],['NYSE:B'])
    def test_name_links_different_isins_classes(self):
        a=row(name='Company A Class A');b=row('NYSE:B','Company A Class B','US1729674242')
        self.assertEqual(self.run_rows([a,b])['summary']['uniqueIssuers'],1)
    def test_cik_normalization(self):
        a=row(cik='0000123');b=row('NYSE:B','Other name','US1729674242',cik=123)
        self.assertEqual(self.run_rows([a,b])['summary']['uniqueIssuers'],1)
    def test_conflicting_ciks_quarantined(self):
        a=row(cik='123');b=row('NYSE:B','Company A','US1729674242',cik='456')
        self.assertEqual(self.run_rows([a,b])['summary']['reviewListings'],2)
    def test_conflicting_classification_quarantined(self):
        a=row();b=row('NYSE:B');b['industry']='Insurance'
        self.assertEqual(self.run_rows([a,b])['summary']['reviewListings'],2)
    def test_duplicate_listing_excluded(self):
        self.assertEqual(self.run_rows([row(),row()])['summary']['excludedListings'],2)
    def test_stale_unknown_and_non_equity(self):
        for field,value in [('metadata_asof','2020-01-01'),('isin',None),('security_type','preferred')]:
            r=row();r[field]=value
            self.assertEqual(self.run_rows([r])['summary']['excludedListings'],1)
    def test_primary_preferred_and_no_self(self):
        rows=[row(is_primary=False),row('XETR:A',is_primary=True)]
        result=self.run_rows(rows)
        self.assertEqual(result['issuers'][0]['representative'],'XETR:A')
        self.assertEqual(result['listings']['NYSE:A']['peerSymbols'],[])
    def test_order_invariant(self):
        rows=[row(),row('NYSE:B','Bank B','US1729674242')]
        a=self.run_rows(rows);b=self.run_rows(list(reversed(rows)))
        self.assertEqual(a['listings'],b['listings']);self.assertEqual(a['issuers'],b['issuers'])
    def test_exchange_adr_preferred_to_otc_when_no_primary(self):
        a=row('OTC:A');b=row('NYSE:A');b['security_type']='adr'
        self.assertEqual(self.run_rows([a,b])['issuers'][0]['representative'],'NYSE:A')
    def test_subindustry_separates_without_sector_fallback(self):
        a=row();a['sub_industry']='Retail banks';b=row('NYSE:B','Bank B','US1729674242');b['sub_industry']='Investment banks'
        self.assertEqual(self.run_rows([a,b])['listings']['NYSE:A']['peerIssuerCount'],0)
    def test_cross_currency_membership_explicit(self):
        a=row();b=row('NYSE:B','Bank B','US1729674242');b['currency']='EUR'
        result=self.run_rows([a,b]);self.assertEqual(result['listings']['NYSE:A']['peerIssuerCount'],1)
        self.assertTrue(any('currencies' in s for s in result['limitations']))
    def test_guarded_business_rule(self):
        r=row();rules=copy.deepcopy(RULES)
        rules['reviewed']=[{'isins':[r['isin']],'names':[name_key(r)],'group':'test','label':'Test',
                            'source':'https://example.com','reviewedAt':'2026-01-01','validUntil':'2026-12-31'}]
        self.assertEqual(classify(r,rules,NOW)['level'],'reviewed_business_model')
        self.assertEqual(classify({**r,'name':'Wrong'},rules,NOW)['state'],'review')
        self.assertEqual(classify(r,rules,NOW.replace(year=2027))['state'],'review')
    def test_no_financial_data_modified(self):
        r=row();r['fair_value']=123;before=copy.deepcopy(r)
        self.run_rows([r]);self.assertEqual(r,before)
    def test_checked_rules_have_sources(self):
        rules=json.loads((Path(__file__).parent/'peer-group-rules.json').read_text(encoding='utf8'))
        for rule in rules['reviewed']:
            self.assertTrue(rule['source'].startswith('https://'));self.assertTrue(rule['names'])
    def test_group_size_distinguishes_business_and_currency_limits(self):
        isins=['US5949181045','US0378331005','US1729674242','US67066G1040','US0231351067','US02079K3059']
        rows=[row('NYSE:X'+str(i),'Company '+str(i),isin) for i,isin in enumerate(isins)]
        r=self.run_rows(rows)['listings']['NYSE:X0']
        self.assertEqual(r['sameCurrencyPeerIssuerCount'],5)
        self.assertEqual(r['groupSizeReason'],'enough_issuers_before_history_check')
        rows[-1]['currency']='EUR'
        self.assertEqual(self.run_rows(rows)['listings']['NYSE:X0']['groupSizeReason'],'small_currency_cohort')
        self.assertEqual(self.run_rows(rows[:3])['listings']['NYSE:X0']['groupSizeReason'],'small_business_group')
if __name__=='__main__':unittest.main()


