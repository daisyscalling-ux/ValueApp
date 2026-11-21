import datetime as dt, json, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import sec_revenue_history as rv
import sec_jahre_export as ex

NOW = dt.datetime(2026, 11, 20, tzinfo=dt.timezone.utc)


def fact(end, val, filed=None, start=None, form='10-K', accn=None):
    e = dt.date.fromisoformat(end)
    return {'end': end, 'start': start or str(e - dt.timedelta(days=364)), 'val': val, 'filed': filed or str(e + dt.timedelta(days=40)),
            'form': form, 'accn': accn or f'0000000001-{end[2:4]}-000001'}


def data(**tags):
    return {'cik': '1', 'facts': {'us-gaap': {t: {'units': {'USD': v}} for t, v in tags.items()}}}


class Umsatz(unittest.TestCase):
    def test_gesamtumsatz_vor_asc606_ein_konzept(self):
        d = data(Revenues=[fact(f'{y}-12-31', 100 + y - 2018) for y in range(2018, 2026)],
                 RevenueFromContractWithCustomerExcludingAssessedTax=[fact(f'{y}-12-31', 50) for y in range(2018, 2026)])
        r = rv.normalize(d, '1', NOW)
        self.assertEqual([x['end'][:4] for x in r], [str(y) for y in range(2018, 2026)])
        self.assertEqual({x['concept'] for x in r}, {'Revenues'})
        self.assertEqual(r[-1]['value'], 107)
        self.assertTrue(r[0]['sourceUrl'].startswith('https://www.sec.gov/Archives/edgar/data/1/'))

    def test_juengstes_jahr_bestimmt_konzept(self):
        d = data(Revenues=[fact('2019-12-31', 90), fact('2020-12-31', 95)],
                 RevenueFromContractWithCustomerExcludingAssessedTax=[fact(f'{y}-12-31', 100) for y in range(2019, 2026)])
        self.assertEqual({x['concept'] for x in rv.normalize(d, '1', NOW)}, {'RevenueFromContractWithCustomerExcludingAssessedTax'})

    def test_quartale_widerspruch_neuester_bericht(self):
        d = data(Revenues=[fact('2024-12-31', 100), fact('2025-03-31', 25, start='2025-01-01', form='10-Q'),
                           fact('2025-12-31', 120, filed='2026-02-10', accn='0000000001-26-000001'),
                           fact('2025-12-31', 121, filed='2026-02-10', accn='0000000001-26-000002'),
                           fact('2023-12-31', 80), fact('2023-12-31', 82, filed='2025-02-10', accn='0000000001-25-000009')])
        r = rv.normalize(d, '1', NOW)
        self.assertEqual([(x['end'], x['value']) for x in r], [('2023-12-31', 82), ('2024-12-31', 100)], '2025 widersprüchlich, 2023 neuester Bericht')

    def test_negativfaelle(self):
        with self.assertRaises(ValueError):
            rv.normalize(data(Revenues=[fact('2024-12-31', 1)]), '2', NOW)
        self.assertEqual(rv.normalize(data(), '1', NOW), [])
        self.assertEqual(rv.normalize(data(Revenues=[fact('2010-12-31', 1)]), '1', NOW), [], 'älter als 8 Jahre')
        self.assertEqual(rv.normalize(data(Revenues=[fact('2024-12-31', -5)]), '1', NOW), [])


class Export(unittest.TestCase):
    def stand(self, abruf='2026-11-19T10:00:00+00:00', cik='1'):
        ident = {'listing_symbol': 'NYSE:A', 'ticker': 'A', 'isin': 'US0000000001', 'currency': 'USD', 'security_type': 'stock', 'share_class': None}
        per = lambda y: {'end': f'{y}-12-31', 'start': f'{y}-01-01', 'filed': f'{y+1}-02-10', 'accession': f'0000000001-{y%100:02d}-000001',
                         'currency': 'USD', 'sourceUrl': 'https://www.sec.gov/Archives/edgar/data/1/x/'}
        return ident, {'schema': 1, 'method': 'sec-cashflow-history-v1',
                'stocks': {'NYSE:A': {'inputIdentity': ident, 'cik': cik, 'retrievedAt': abruf, 'periods': [
                    {**per(y), 'operatingCashflow': 50, 'cashPpe': 10, 'namespace': 'us-gaap', 'concept': 'PaymentsToAcquirePropertyPlantAndEquipment'} for y in (2019, 2020)]
                    + [{**per(2021), 'operatingCashflow': 60, 'cashPpe': 5, 'namespace': 'us-gaap', 'concept': 'PaymentsToAcquireProductiveAssets'}]}},
                'revenueStocks': {'NYSE:A': {'inputIdentity': ident, 'cik': cik, 'retrievedAt': abruf, 'periods': [{**per(y), 'value': 100 + y, 'concept': 'Revenues'} for y in (2019, 2020)]}}}

    def test_reihen_je_titel(self):
        ident, st = self.stand()
        uni = {'kandidaten': [{'listing_symbol': 'NYSE:A', 'ticker': 'A', 'isin': 'US0000000001', 'currency': 'USD', 'security_type': 'stock', 'cik': '0000000001'}]}
        out = ex.build(st, uni, NOW)['NYSE:A']
        self.assertEqual((out['method'], len(out['umsatz']), len(out['ocf_capex'])), ('sec_annual_series_v1', 2, 2), 'anderes Capex-Konzept fällt weg')
        self.assertEqual(out['ocf_capex'][0]['wert'], 40)
        self.assertEqual(out['umsatz'][1]['wert'], 2120)

    def test_negativfaelle(self):
        uni = {'kandidaten': [{'listing_symbol': 'NYSE:A', 'ticker': 'A', 'isin': 'US0000000001', 'currency': 'USD', 'security_type': 'stock'}]}
        for st in (self.stand(abruf='2026-10-01T00:00:00+00:00')[1], self.stand(cik='2')[1]):
            u = {'kandidaten': [{**uni['kandidaten'][0], 'cik': '1'}]}
            self.assertEqual(ex.build(st, u, NOW), {})
        self.assertEqual(ex.build(self.stand()[1], {'kandidaten': [{**uni['kandidaten'][0], 'isin': 'US9999999999'}]}, NOW), {}, 'andere ISIN')
        self.assertEqual(ex.build({'schema': 1, 'method': 'x'}, uni, NOW), {})


class Behalten(unittest.TestCase):
    def test_aeltere_jahre_bleiben_nach_dem_rollen(self):
        ident = {'listing_symbol': 'NYSE:A'}
        r = lambda y, k='Revenues': {'ende': f'{y}-12-31', 'wert': y, 'konzept': k}
        alt = {'method': ex.METHOD, 'inputIdentity': ident, 'cik': '1', 'umsatz': [r(y) for y in range(2018, 2026)], 'ocf_capex': []}
        neu = {'method': ex.METHOD, 'inputIdentity': ident, 'cik': '1', 'umsatz': [r(y) for y in range(2019, 2027)], 'ocf_capex': []}
        d, n = ex.behalten(neu, alt)
        self.assertEqual([x['ende'][:4] for x in d['umsatz']], [str(y) for y in range(2018, 2027)]); self.assertEqual(n, 1)
        self.assertTrue(d['umsatz'][0]['archiviert']); self.assertNotIn('archiviert', d['umsatz'][1])
        for a in ({**alt, 'cik': '2'}, {**alt, 'inputIdentity': {'listing_symbol': 'NYSE:B'}}, {**alt, 'umsatz': [r(2018, 'SalesRevenueNet')]}, None):
            d, n = ex.behalten({**neu, 'umsatz': list(neu['umsatz'])}, a)
            self.assertEqual((d['umsatz'][0]['ende'][:4], n), ('2019', 0))


if __name__ == '__main__':
    unittest.main()
