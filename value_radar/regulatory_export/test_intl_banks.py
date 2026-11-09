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
