import json, os, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import roic_archiv as ra


def ev(j, u, e=None, **o):
    return {'fiscal_year': j, 'period_end_date': f'{j}-12-31', 'period_type': 'annual', 'currency': 'USD', 'ttm_net_sales': u, 'ttm_ebitda': e, 'ttm_free_cash_flow_firm': 1.0, **o}


def zeile(sym='NYSE:A', jahre=(2021, 2022, 2023, 2024, 2025), isin='US0000000001', cur='USD', **roh):
    return {'listing_symbol': sym, 'isin': isin, 'currency': cur,
            '_ts_input': {'_roic_raw': {'method': 'roic_raw_blocks_v1', 'symbol': sym, 'enterprise_value': [ev(j, 100.0 + j) for j in jahre], **roh}}}


class Archiv(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory(); self.o = Path(self.t.name)

    def tearDown(self):
        self.t.cleanup()

    def doc(self, sym='NYSE:A'):
        return json.loads((self.o / ra.dateiname(sym)).read_text())

    def test_jahreswechsel_aeltestes_jahr_bleibt(self):
        ra.einarbeiten([zeile()], self.o, '2026-11-21')
        z = ra.einarbeiten([zeile(jahre=(2022, 2023, 2024, 2025, 2026))], self.o, '2027-03-01')
        d = self.doc()
        self.assertEqual(list(d['jahre']), [f'{j}-12-31' for j in range(2021, 2027)], '2021 bleibt nach dem Jahreswechsel')
        self.assertEqual(d['jahre']['2021-12-31']['zuletzt'], '2026-11-21')
        self.assertEqual(d['jahre']['2026-12-31']['erstmals'], '2027-03-01')
        self.assertEqual(z['neue_jahre'], 1)
        self.assertEqual(d['method'], 'roic_annual_archive_v1')

    def test_anpassung_behaelt_alten_wert(self):
        ra.einarbeiten([zeile()], self.o, '2026-11-21')
        r = zeile(); r['_ts_input']['_roic_raw']['enterprise_value'][0]['ttm_net_sales'] = 999.0
        z = ra.einarbeiten([r], self.o, '2026-12-01')
        e = self.doc()['jahre']['2021-12-31']
        self.assertEqual((e['werte']['ttm_net_sales'], e['frueher'][0]['werte']['ttm_net_sales'], e['frueher'][0]['bis'], z['angepasst']), (999.0, 2121.0, '2026-12-01', 1))

    def test_negativfaelle(self):
        ra.einarbeiten([zeile()], self.o, '2026-11-21')
        z = ra.einarbeiten([zeile(jahre=(2026,), isin='US9999999999')], self.o, '2027-03-01')
        self.assertEqual(z['identitaet_abweichend'], 1); self.assertNotIn('2026-12-31', self.doc()['jahre'])
        z = ra.einarbeiten([zeile(sym='NYSE:B', method='x')], self.o)
        self.assertEqual(z['ohne_bloecke'], 1)
        r = zeile(sym='NYSE:C'); r['_ts_input']['_roic_raw']['symbol'] = 'NYSE:X'
        self.assertEqual(ra.einarbeiten([r], self.o)['ohne_bloecke'], 1, 'Bloecke einer anderen Notierung')
        self.assertEqual(ra.einarbeiten([{'listing_symbol': 'NYSE:D'}], self.o)['titel'], 0, 'ohne Rohbloecke nichts')
        q = ra.jahre_aus_roh({'enterprise_value': [ev(2025, 1.0, period_type='quarterly'), {'period_end_date': 'kaputt', 'ttm_net_sales': 1},
                                                    {'period_end_date': '2023-12-31', 'period_type': 'annual', 'ttm_net_sales': None}, ev(2024, 5.0)]})
        self.assertEqual(list(q), ['2024-12-31'], 'Quartale, kaputte Stichtage und Zeilen ohne Werte fallen weg')


if __name__ == '__main__':
    unittest.main()
