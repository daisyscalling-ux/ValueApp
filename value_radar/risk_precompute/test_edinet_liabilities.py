import unittest
from edinet_cashflow import parse_xml
from test_edinet import xml,DOC,NOW


class LiabilityComponents(unittest.TestCase):
    def parsed(self,values,context='I'):
        extra=''.join(f'<j:{tag} contextRef="{context}" unitRef="JPY">{value}</j:{tag}>' for tag,value in values)
        return parse_xml(xml().replace('</xbrli:xbrl>',extra+'</xbrli:xbrl>').encode(),DOC,NOW)

    def test_both_maturities_and_leases_remain_separate(self):
        a=self.parsed([('BondsAndBorrowingsCLIFRS',100),('BondsAndBorrowingsNCLIFRS',300),('LeaseLiabilitiesCLIFRS',20),('LeaseLiabilitiesNCLIFRS',80)])
        self.assertEqual(a['fields']['bonds_borrowings'],400)
        self.assertEqual(a['fields']['lease_liabilities'],100)
        self.assertIsNone(a['fields']['interest_bearing_debt'])
        self.assertEqual(a['field_sources']['bonds_borrowings']['derivation'],'both_reported_category_maturities')
        self.assertEqual(a['field_sources']['lease_liabilities']['docID'],DOC['docID'])

    def test_missing_maturity_or_lease_is_not_zero(self):
        a=self.parsed([('BondsAndBorrowingsCLIFRS',100)])
        self.assertIsNone(a['fields']['bonds_borrowings'])
        self.assertIsNone(a['fields']['lease_liabilities'])
        self.assertEqual(a['liabilityEvidence']['bonds_borrowings']['missingComponents'],['noncurrent_bonds_borrowings'])

    def test_reported_total_and_explicit_zero(self):
        a=self.parsed([('BondsAndBorrowingsLiabilitiesIFRS',400),('LeaseLiabilitiesLiabilitiesIFRS',0)])
        self.assertEqual(a['fields']['bonds_borrowings'],400)
        self.assertEqual(a['fields']['lease_liabilities'],0)

    def test_total_must_agree_with_components(self):
        a=self.parsed([('BondsAndBorrowingsLiabilitiesIFRS',400),('BondsAndBorrowingsCLIFRS',100),('BondsAndBorrowingsNCLIFRS',350)])
        self.assertIsNone(a['fields']['bonds_borrowings'])
        self.assertIn('total_component_conflict',a['liabilityEvidence']['bonds_borrowings']['issues'])
        self.assertEqual(a['fcfAssets'],.06)

    def test_negative_and_conflicting_facts_rejected(self):
        for values in [[('LeaseLiabilitiesLiabilitiesIFRS',-5)],[('LeaseLiabilitiesCLIFRS',10),('LeaseLiabilitiesCLIFRS',20),('LeaseLiabilitiesNCLIFRS',40)]]:
            a=self.parsed(values)
            self.assertIsNone(a['fields']['lease_liabilities'])
            self.assertEqual(a['fcfAssets'],.06)

    def test_duration_cannot_supply_instant_liabilities(self):
        a=self.parsed([('BondsAndBorrowingsLiabilitiesIFRS',400)],context='D')
        self.assertIsNone(a['fields']['bonds_borrowings'])


if __name__=='__main__':unittest.main()
