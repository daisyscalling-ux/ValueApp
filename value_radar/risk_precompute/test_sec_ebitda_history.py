"""EBITDA aus SEC companyfacts (sec-annual-ebitda-v1, seit 27.11.2026)."""
import datetime as dt, sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import sec_ebitda_history as eb
import sec_jahre_export as ex

NOW = dt.datetime(2026, 11, 27, tzinfo=dt.timezone.utc)


def fact(end, val, accn=None, filed=None, form='10-K', start=None):
    e = dt.date.fromisoformat(end)
    return {'end': end, 'start': start or str(e - dt.timedelta(days=364)), 'val': val, 'filed': filed or str(e + dt.timedelta(days=40)),
            'form': form, 'accn': accn or f'0000000001-{int(end[2:4]) + 1:02d}-000001'}


def data(**tags):
    return {'cik': '1', 'facts': {'us-gaap': {t: {'units': {'USD': v}} for t, v in tags.items()}}}


JAHRE = range(2018, 2026)


class Ebitda(unittest.TestCase):
    def test_operativ_plus_abschreibungen_acht_jahre(self):
        d = data(OperatingIncomeLoss=[fact(f'{y}-12-31', 100 + y - 2018) for y in range(2016, 2026)],
                 DepreciationDepletionAndAmortization=[fact(f'{y}-12-31', 20) for y in range(2016, 2026)],
                 DepreciationAndAmortization=[fact(f'{y}-12-31', 999) for y in JAHRE])
        r = eb.normalize(d, '1', NOW)
        self.assertEqual([x['end'][:4] for x in r], [str(y) for y in JAHRE], 'höchstens 8 Jahre')
        self.assertEqual((r[-1]['value'], r[-1]['operatingIncome'], r[-1]['da'], r[-1]['daConcept']), (127, 107, 20, 'DepreciationDepletionAndAmortization'))
        self.assertTrue(r[0]['sourceUrl'].startswith('https://www.sec.gov/Archives/edgar/data/1/'))

    def test_bestandteile_aus_demselben_bericht(self):
        d = data(OperatingIncomeLoss=[fact('2024-12-31', 100), fact('2025-12-31', 110)],
                 DepreciationDepletionAndAmortization=[fact('2024-12-31', 20, accn='0000000001-99-000009'), fact('2025-12-31', 22)])
        self.assertEqual([x['end'] for x in eb.normalize(d, '1', NOW)], ['2025-12-31'], '2024: Abschreibungen aus anderem Bericht')

    def test_neuester_bericht_gilt_widerspruch_verwirft(self):
        neu = '0000000001-26-000002'
        d = data(OperatingIncomeLoss=[fact('2024-12-31', 100), fact('2024-12-31', 95, accn=neu, filed='2026-02-10'),
                                      fact('2025-12-31', 110, accn=neu, filed='2026-02-10'), fact('2025-12-31', 111, accn=neu, filed='2026-02-10')],
                 DepreciationDepletionAndAmortization=[fact('2024-12-31', 20), fact('2024-12-31', 21, accn=neu, filed='2026-02-10'),
                                                       fact('2025-12-31', 22, accn=neu, filed='2026-02-10')])
        r = {x['end']: x for x in eb.normalize(d, '1', NOW)}
        self.assertEqual(r['2024-12-31']['value'], 116, 'angepasste Zahl aus dem neuesten 10-K')
        self.assertNotIn('2025-12-31', r, 'Widerspruch im neuesten Bericht: kein Rückfall')

    def test_negative_abschreibung_quartal_falsche_cik(self):
        d = data(OperatingIncomeLoss=[fact('2025-12-31', 110), fact('2025-09-30', 30, form='10-Q', start='2025-07-01')],
                 DepreciationDepletionAndAmortization=[fact('2025-12-31', -5), fact('2025-09-30', 5, form='10-Q', start='2025-07-01')])
        self.assertEqual(eb.normalize(d, '1', NOW), [])
        with self.assertRaisesRegex(ValueError, 'cik_mismatch'):
            eb.normalize(d, '2', NOW)

    def test_ohne_abschreibungen_zum_juengsten_jahr_naechstes_konzept(self):
        d = data(OperatingIncomeLoss=[fact(f'{y}-12-31', 100) for y in (2024, 2025)],
                 DepreciationDepletionAndAmortization=[fact('2024-12-31', 20)],
                 DepreciationAndAmortization=[fact(f'{y}-12-31', 30) for y in (2024, 2025)])
        r = eb.normalize(d, '1', NOW)
        self.assertEqual(({x['daConcept'] for x in r}, [x['value'] for x in r]), ({'DepreciationAndAmortization'}, [130, 130]))


class Export(unittest.TestCase):
    def test_ebitda_in_der_jahresdatei_und_behalten(self):
        ident = {'listing_symbol': 'NYSE:X', 'ticker': 'X', 'isin': 'US0000000001', 'currency': 'USD', 'security_type': 'stock', 'share_class': None}
        row = {**ident, 'cik': '1'}
        import roic_risk_annual
        ident = roic_risk_annual.identity(row)
        per = [{'end': f'{y}-12-31', 'start': f'{y}-01-01', 'value': 120.0, 'operatingIncome': 100.0, 'da': 20.0, 'currency': 'USD',
                'daConcept': 'DepreciationDepletionAndAmortization', 'accession': f'0000000001-{y - 1999:02d}-000001', 'sourceUrl': 'https://www.sec.gov/Archives/edgar/data/1/x/'} for y in (2024, 2025)]
        from sec_cashflow_history import METHOD
        state = {'schema': 1, 'method': METHOD, 'stocks': {}, 'revenueStocks': {},
                 'ebitdaStocks': {'NYSE:X': {'inputIdentity': ident, 'cik': '1', 'retrievedAt': NOW.isoformat(), 'periods': per}}}
        out = ex.build(state, {'kandidaten': [row]}, NOW)
        d = out['NYSE:X']
        self.assertEqual([(e['ende'], e['wert'], e['operativ'], e['abschreibungen']) for e in d['ebitda']], [('2024-12-31', 120.0, 100.0, 20.0), ('2025-12-31', 120.0, 100.0, 20.0)])
        alt = {**d, 'ebitda': [{**d['ebitda'][0], 'ende': '2023-12-31'}] + d['ebitda']}
        neu, n = ex.behalten(d, alt)
        self.assertEqual((n, neu['ebitda'][0]['ende'], neu['ebitda'][0]['archiviert']), (1, '2023-12-31', True))


if __name__ == '__main__':
    unittest.main()
