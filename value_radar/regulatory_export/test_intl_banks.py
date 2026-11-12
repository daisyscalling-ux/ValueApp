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

    def test_separate_cr1_period(self):
        """Japan: CR1 nur jaehrlich; eigener Stichtag, eigene Quelle, Fehler verwerfen nur die Kreditqualitaet."""
        credit = {'period': '2026-03-31', 'defaultedLoans': 1315526, 'nonDefaultedLoans': 122176641, 'loanUnit': 'JPY_million', 'type': 'basel_pillar3_cr1',
                  'url': 'https://example.org/b3.pdf', 'sha256': 'c' * 64, 'location': 'PDF page 30, CR1 row 1'}
        e = {'isin': 'JP3902900004', 'issuer': 'MUFG', 'jurisdiction': 'JP', 'regulator': 'JFSA', 'period': '2026-06-30', 'cet1_ratio': .14, 'tier1_ratio': .15,
             'total_capital_ratio': .17, 'lcr': 1.5, 'credit': credit, 'source': {'type': 'basel_pillar3_km1', 'url': 'https://example.org/km1.pdf', 'sha256': 'b' * 64}}
        bad = {'credit_period_stale': {'period': '2026-01-30'}, 'credit_period_invalid': {'period': '2026-09-30'},
               'credit_values_invalid': {'defaultedLoans': 900, 'nonDefaultedLoans': 100}, 'credit_source_unverified': {'type': 'basel_pillar3_km1'}}
        cases = [e] + [{**e, 'isin': f'JP000000000{n}', 'credit': {**credit, **v}} for n, v in enumerate(bad.values())]
        cases.append({**e, 'isin': 'JP0000000009', 'defaultedLoans': 1, 'nonDefaultedLoans': 99})
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'apra.xlsx'
            path.write_bytes(b'x')
            with mock.patch.object(intl, 'apra', return_value={}):
                r = intl.build(path, {**MAPPING, 'issuers': []}, NOW, reviewed={'review_expires': '2027-01-01', 'entries': cases})
        i = r['issuers']['JP3902900004']
        self.assertAlmostEqual(i['defaultedLoanRatio'], 1315526 / (1315526 + 122176641))
        self.assertEqual((i['period'], i['creditPeriod'], i['creditSource']['location']), ('2026-06-30', '2026-03-31', 'PDF page 30, CR1 row 1'))
        expected = {f'JP000000000{n}': k for n, k in enumerate(bad)}
        expected['JP0000000009'] = 'credit_period_ambiguous'
        self.assertEqual(r['creditRejected'], expected)
        for isin in expected:
            self.assertIsNone(r['issuers'][isin]['defaultedLoanRatio'], isin)
            self.assertEqual(r['issuers'][isin]['metrics']['cet1_ratio'], .14, 'capital stays')
            self.assertNotIn('creditPeriod', r['issuers'][isin])
        self.assertEqual(r['rejected'], {})

    def test_repository_japan_cr1_blocks_are_valid(self):
        data = json.loads((intl.ROOT / 'reviewed-key-metrics.json').read_text(encoding='utf-8'))
        jp = [e for e in data['entries'] if e.get('credit') and e['credit']['type'] == 'basel_pillar3_cr1']
        self.assertEqual({e['isin'] for e in jp}, {'JP3902900004', 'JP3890350006', 'JP3885780001', 'JP3892100003', 'JP3511800009', 'JP3305990008', 'JP3351500008'})
        uk = [e for e in data['entries'] if e.get('credit') and e['credit']['type'] == 'uk_pillar3_cr1']
        self.assertEqual({e['isin'] for e in uk}, {'GB0005405286', 'GB00BM8PJY71', 'GB0004082847'})
        jp += uk
        for e in jp:
            self.assertEqual(intl.credit_problem(e, dt.datetime(2026, 11, 11, tzinfo=dt.timezone.utc)), '', e['isin'])

    def test_domestic_standard_entries(self):
        """Japan, Inlandsstandard: Beleg je Bank und LCR-Geltungsbereich; Fehler verwerfen nur den Eintrag."""
        rule = {'url': 'https://www.fsa.go.jp/x.pdf', 'sha256': 'd' * 64, 'location': 'Notice 62 Art. 2'}
        ok = {'isin': 'JP3500610005', 'issuer': 'Resona', 'jurisdiction': 'JP', 'regulator': 'JFSA', 'standard': 'jp_domestic_core_capital', 'period': '2026-06-30',
              'domesticCapitalRatio': .1265, 'source': {'type': 'bank_capital_release', 'url': 'https://example.org/r.pdf', 'sha256': 'e' * 64, 'location': 'p. 1'}}
        bad = {'domestic_evidence_stale': {'period': '2025-12-31'}, 'domestic_standard_unknown': {'standard': 'other'},
               'domestic_source_unverified': {'source': {**ok['source'], 'sha256': 'x'}}, 'domestic_ratio_invalid': {'domesticCapitalRatio': 4},
               'domestic_entry_incomplete': {'isin': 'JP123'}}
        entries = [ok] + [{**ok, 'isin': f'JP000000001{n}', **v} for n, v in enumerate(bad.values())]
        entries[-1]['isin'] = 'JP123'
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'apra.xlsx'
            path.write_bytes(b'x')
            with mock.patch.object(intl, 'apra', return_value={}):
                r = intl.build(path, {**MAPPING, 'issuers': []}, NOW, reviewed={'review_expires': '2027-01-01', 'entries': [], 'domesticStandard': entries, 'domesticStandardLcrRule': rule})
                no_rule = intl.build(path, {**MAPPING, 'issuers': []}, NOW, reviewed={'review_expires': '2027-01-01', 'entries': [], 'domesticStandard': [ok]})
        self.assertEqual(r['domesticStandard']['JP3500610005']['lcrRule'], rule)
        self.assertEqual(r['domesticRejected'], {**{f'JP000000001{n}': k for n, k in enumerate(bad) if k != 'domestic_entry_incomplete'}, 'JP123': 'domestic_entry_incomplete'})
        self.assertEqual(no_rule['domesticRejected'], {'JP3500610005': 'lcr_rule_unverified'})
        self.assertNotIn('JP3500610005', r['issuers'], 'no capital ratios are invented')

    def test_repository_domestic_entries_are_valid(self):
        data = json.loads((intl.ROOT / 'reviewed-key-metrics.json').read_text(encoding='utf-8'))
        isins = {e['isin'] for e in data['domesticStandard']}
        self.assertEqual(isins, {'JP3500610005', 'JP3805010000'})
        self.assertFalse(isins & {e['isin'] for e in data['entries']})
        for e in data['domesticStandard']:
            self.assertEqual(intl.domestic_problem(e, data['domesticStandardLcrRule'], dt.datetime(2026, 11, 12, tzinfo=dt.timezone.utc)), '', e['isin'])

    def test_uk_cr1_npl_block(self):
        """UK CR1 (EBA-Definition): eigene Methode uk-cr1-npl-v1, notleidend / (performing + non-performing)."""
        credit = {'period': '2026-06-30', 'nonPerformingLoans': 5036, 'performingLoans': 450574, 'loanUnit': 'GBP_million', 'type': 'uk_pillar3_cr1',
                  'url': 'https://example.org/p3.pdf', 'sha256': 'c' * 64, 'location': 'UK CR1 row 010'}
        e = {'isin': 'GB00BM8PJY71', 'issuer': 'NatWest', 'jurisdiction': 'GB', 'regulator': 'PRA', 'period': '2026-09-30', 'cet1_ratio': .14, 'tier1_ratio': .16,
             'total_capital_ratio': .19, 'credit': credit, 'source': {'type': 'basel_pillar3_km1', 'url': 'https://example.org/km1.pdf', 'sha256': 'b' * 64}}
        wrong_fields = {**e, 'isin': 'GB0000000001', 'credit': {**{k: v for k, v in credit.items() if k not in ('nonPerformingLoans', 'performingLoans')}, 'defaultedLoans': 5036, 'nonDefaultedLoans': 450574}}
        unknown = {**e, 'isin': 'GB0000000002', 'credit': {**credit, 'type': 'uk_guess'}}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'apra.xlsx'
            path.write_bytes(b'x')
            with mock.patch.object(intl, 'apra', return_value={}):
                r = intl.build(path, {**MAPPING, 'issuers': []}, NOW, reviewed={'review_expires': '2027-01-01', 'entries': [e, wrong_fields, unknown]})
        i = r['issuers']['GB00BM8PJY71']
        self.assertAlmostEqual(i['defaultedLoanRatio'], 5036 / (5036 + 450574))
        self.assertEqual((i['creditMethod'], i['creditPeriod']), ('uk-cr1-npl-v1', '2026-06-30'))
        self.assertEqual(r['creditRejected'], {'GB0000000001': 'credit_values_invalid', 'GB0000000002': 'credit_source_unverified'})

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
