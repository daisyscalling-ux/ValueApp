import datetime as dt
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import import_intl_banks as intl

NOW = dt.datetime(2026, 11, 9, tzinfo=dt.timezone.utc)
MAPPING = {'review_expires': '2027-05-08', 'issuers': [
    {'isin': 'AU000000CBA7', 'issuer': 'Commonwealth Bank of Australia', 'jurisdiction': 'AU', 'regulator': 'APRA', 'source': 'apra_adi_centralised_publication', 'sourceEntity': 'Commonwealth Bank of Australia'}],
    'open': {'AU000000ANZ3': 'non-operating holding'}}


class IntlBankImportTests(unittest.TestCase):
    def run_build(self, values):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'apra.xlsx'
            path.write_bytes(b'x')
            with mock.patch.object(intl, 'apra', return_value=values):
                return intl.build(path, MAPPING, NOW)

    def test_capital_lcr_and_open_holding(self):
        r = self.run_build({'Commonwealth Bank of Australia': {'period': '2026-06-30', 'metrics': {'cet1_ratio': .12, 'tier1_ratio': .135, 'total_capital_ratio': .208}, 'lcr': 1.32, 'nsfr': 1.151}})
        i = r['issuers']['AU000000CBA7']
        self.assertEqual((i['period'], i['metrics']['cet1_ratio'], i['lcr'], i['cet1Requirement']), ('2026-06-30', .12, 1.32, None))
        self.assertEqual(i['source']['type'], 'apra_adi_centralised_publication')
        self.assertIn('AU000000ANZ3', r['open'])
        self.assertEqual(r['scoreContribution'], 0)

    def test_missing_or_inconsistent_capital_is_rejected(self):
        self.assertEqual(self.run_build({})['rejected'], {'AU000000CBA7': 'capital_missing_or_inconsistent'})
        r = self.run_build({'Commonwealth Bank of Australia': {'period': '2026-06-30', 'metrics': {'cet1_ratio': .14, 'tier1_ratio': .13, 'total_capital_ratio': None}, 'lcr': 1.3, 'nsfr': None}})
        self.assertEqual(r['issuers'], {})

    def test_reviewed_km1_entries_are_checked(self):
        ok = {'isin': 'GB0005405286', 'issuer': 'HSBC Holdings plc', 'jurisdiction': 'GB', 'regulator': 'PRA', 'period': '2026-09-30',
              'cet1_ratio': .139, 'tier1_ratio': .163, 'total_capital_ratio': .192, 'cet1Requirement': .112, 'cet1RequirementDefinition': 'x',
              'requirementComponents': {'minimum': .045, 'km1RowUK7a': .014, 'km1Row11': .053}, 'lcr': 1.32, 'nsfr': 1.39,
              'defaultedLoans': 10, 'nonDefaultedLoans': 990, 'source': {'type': 'basel_pillar3_km1', 'url': 'https://example.org/p3.pdf', 'sha256': 'a' * 64}}
        bad_sum = {**ok, 'isin': 'GB0000000001', 'cet1Requirement': .12}
        bad_chain = {**ok, 'isin': 'GB0000000002', 'tier1_ratio': .13}
        bad_src = {**ok, 'isin': 'GB0000000003', 'source': {**ok['source'], 'sha256': 'x'}}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'apra.xlsx'
            path.write_bytes(b'x')
            with mock.patch.object(intl, 'apra', return_value={}):
                r = intl.build(path, {**MAPPING, 'issuers': []}, NOW, reviewed={'review_expires': '2027-01-01', 'entries': [ok, bad_sum, bad_chain, bad_src], 'open': {'X': 'y'}})
        i = r['issuers']['GB0005405286']
        self.assertEqual((i['cet1Requirement'], i['lcr'], i['defaultedLoanRatio']), (.112, 1.32, .01))
        self.assertEqual(r['rejected'], {'GB0000000001': 'requirement_components_mismatch', 'GB0000000002': 'capital_missing_or_inconsistent', 'GB0000000003': 'source_unverified'})
        self.assertEqual(r['mappingReviewExpires'], '2027-01-01')
        self.assertIn('X', r['open'])

    def test_entry_without_disclosed_requirement_keeps_capital_only(self):
        e = {'isin': 'JP3351500008', 'issuer': 'Shizuoka Financial Group, Inc.', 'jurisdiction': 'JP', 'regulator': 'JFSA', 'period': '2026-06-30',
             'cet1_ratio': .1624, 'tier1_ratio': .1624, 'total_capital_ratio': .1624, 'cet1Requirement': None, 'lcr': None,
             'source': {'type': 'basel_pillar3_km1', 'url': 'https://example.org/r.pdf', 'sha256': 'b' * 64}}
        self.assertEqual(intl.reviewed_problem(e), '')
        self.assertEqual(intl.reviewed_problem({**e, 'cet1Requirement': .08, 'requirementComponents': {'minimum': .045}}), 'requirement_components_mismatch')

    def test_report_source_type_is_accepted_unknown_is_not(self):
        e = {'isin': 'CH0225173167', 'issuer': 'Cembra Money Bank AG', 'jurisdiction': 'CH', 'regulator': 'FINMA', 'period': '2026-06-30',
             'cet1_ratio': .153, 'tier1_ratio': .177, 'total_capital_ratio': .177, 'cet1Requirement': None,
             'source': {'type': 'bank_capital_release', 'url': 'https://example.org/h1.pdf', 'sha256': 'c' * 64}}
        self.assertEqual(intl.reviewed_problem(e), '')
        self.assertEqual(intl.reviewed_problem({**e, 'source': {**e['source'], 'type': 'press_article'}}), 'source_unverified')

    def test_reviewed_file_is_consistent(self):
        d = json.loads((Path(intl.__file__).parent / 'reviewed-key-metrics.json').read_text(encoding='utf-8'))
        for e in d['entries']:
            self.assertEqual(intl.reviewed_problem(e), '', e['issuer'])

    def test_fraction_guard(self):
        self.assertEqual((intl.fraction(.12), intl.fraction(float('nan')), intl.fraction('1.2'), intl.fraction(True)), (.12, None, None, None))

    def test_mapping_is_consistent(self):
        m = json.loads((Path(intl.__file__).parent / 'intl-bank-map.json').read_text(encoding='utf-8'))
        isins = [i['isin'] for i in m['issuers']]
        self.assertEqual(len(isins), len(set(isins)))
        self.assertFalse(set(isins) & set(m['open']))
        for i in m['issuers']:
            self.assertRegex(i['isin'], r'^[A-Z]{2}[A-Z0-9]{9}[0-9]$')


if __name__ == '__main__':
    unittest.main()
