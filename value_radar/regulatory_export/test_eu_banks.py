import csv
import datetime as dt
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import import_eu_banks as eu

HAS_OPENPYXL = importlib.util.find_spec('openpyxl') is not None
NOW = dt.datetime(2026, 11, 9, tzinfo=dt.timezone.utc)
LEI = 'TESTLEI0000000000001'


def write_csv(path, header, rows):
    with open(path, 'w', newline='', encoding='utf-8') as stream:
        w = csv.DictWriter(stream, fieldnames=header)
        w.writeheader()
        w.writerows(rows)


def fixture(folder, cet1='0.14', t1='0.15'):
    folder = Path(folder)
    oth = ['LEI_Code', 'NSA', 'Period', 'Item', 'Label', 'Amount']
    rows = [dict(LEI_Code=LEI, NSA='IT', Period=p, Item=i, Label='', Amount=v) for p in ('202412', '202506')
            for i, v in (('2520140', cet1), ('2520141', t1), ('2520142', '0.18'), ('2520905', '0.06'), ('2520102', '9999'))]
    rows.append(dict(LEI_Code='OTHERLEI000000000000', NSA='IT', Period='202506', Item='2520140', Label='', Amount='0.2'))
    write_csv(folder / 'tr_oth.csv', oth, rows)
    cre = ['LEI_Code', 'Period', 'Item', 'Portfolio', 'Country', 'Exposure', 'Status', 'Perf_Status', 'NACE_codes', 'Amount']
    base = dict(LEI_Code=LEI, Period='202506', Item='2520603', Portfolio='0', Country='0', Exposure='0', Status='0', NACE_codes='0')
    write_csv(folder / 'tr_cre.csv', cre, [{**base, 'Perf_Status': '0', 'Amount': '1000'}, {**base, 'Perf_Status': '2', 'Amount': '25'},
                                          {**base, 'Perf_Status': '2', 'Exposure': '101', 'Amount': '999'}])
    for name in ('TR_Metadata.xlsx', 'Pillar_2_requirement.en.xlsx'):
        (folder / name).write_bytes(b'placeholder')
    return folder


MAPPING = {'review_expires': '2027-05-08', 'banks': [{'lei': LEI, 'ebaName': 'Test Banca', 'ebaCountry': 'IT', 'ecbName': 'Test Banca S.p.A.', 'isins': ['IT0000000001']}]}


class EuBankImportTests(unittest.TestCase):
    def test_percent_and_period(self):
        self.assertEqual(eu.percent(0.0225), (0.0225, ''))
        self.assertEqual(eu.percent('2.25%\xa0'), (0.0225, ''))
        self.assertEqual(eu.percent('1.50%1'), (0.015, '1'))
        self.assertEqual(eu.percent('n.a.'), (None, ''))
        self.assertEqual(eu.period_end('202506'), '2025-06-30')
        self.assertEqual(eu.period_end('202412'), '2024-12-31')

    def test_latest_period_npl_and_partial_requirement(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(eu, 'read_p2r', return_value={'Test Banca S.p.A.': {2025: {'value': .02, 'footnote': ''}, 2026: {'value': .05, 'footnote': ''}}}):
                r = eu.build(fixture(tmp), MAPPING, NOW)
        b = r['banks'][LEI]
        self.assertEqual(b['period'], '2025-06-30')
        self.assertEqual(b['metrics'], {'cet1_ratio': .14, 'tier1_ratio': .15, 'total_capital_ratio': .18, 'leverage_ratio': .06})
        self.assertAlmostEqual(b['nplRatio'], .025)
        self.assertEqual(b['p2r']['year'], 2025, 'requirement of the capital period year, not the later one')
        self.assertAlmostEqual(b['cet1RequirementPartial'], .045 + .025 + .5625 * .02)
        self.assertNotIn('OTHERLEI000000000000', r['banks'])
        self.assertEqual(r['scoreContribution'], 0)

    def test_inconsistent_capital_and_missing_requirement_are_not_guessed(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(eu, 'read_p2r', return_value={}):
                r = eu.build(fixture(tmp, cet1='0.16', t1='0.15'), MAPPING, NOW)
        self.assertEqual(r['banks'], {})
        self.assertEqual(r['rejected'][LEI], 'capital_missing_or_inconsistent')
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(eu, 'read_p2r', return_value={}):
                r = eu.build(fixture(tmp), MAPPING, NOW)
        self.assertNotIn('cet1RequirementPartial', r['banks'][LEI])
        self.assertEqual(r['rejected'][LEI + ':p2r'], 'ecb_name_not_found')

    def test_reviewed_mapping_is_consistent(self):
        m = json.loads((Path(eu.__file__).parent / 'eu-bank-map.json').read_text(encoding='utf-8'))
        leis = [b['lei'] for b in m['banks']]
        self.assertEqual(len(leis), len(set(leis)))
        for b in m['banks']:
            self.assertRegex(b['lei'], r'^[A-Z0-9]{20}$')
            self.assertEqual(b['ecbName'] is None, b['ebaCountry'] in ('DK', 'SE', 'NO', 'PL'), b['ebaName'])
            self.assertTrue(b['isins'])

    @unittest.skipUnless(HAS_OPENPYXL, 'openpyxl not installed')
    def test_p2r_table_columns_per_year(self):
        import openpyxl
        with tempfile.TemporaryDirectory() as tmp:
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.append(['Name of institution', 'P2R applicable in 20243', 'P2R-LR applicable in 2024', 'P2R applicable in 20253', 'P2R-LR applicable in 2025', 'Currently applicable P2R in 20263', 'Currently applicable P2R-LR in 2026'])
            ws.append(['Test Banca S.p.A.', 0.02, 'n.a.', '1.50%1', 'n.a.', '2.40%\xa0', 0.001])
            ws.append(['3. Under Article 104a ...', None, None, None, None, None, None])
            path = Path(tmp) / 'p2r.xlsx'
            wb.save(path)
            p = eu.read_p2r(path)
        self.assertEqual(p, {'Test Banca S.p.A.': {2024: {'value': .02, 'footnote': ''}, 2025: {'value': .015, 'footnote': '1'}, 2026: {'value': .024, 'footnote': ''}}})


if __name__ == '__main__':
    unittest.main()
