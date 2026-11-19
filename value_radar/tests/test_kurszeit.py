import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import kurszeit as kz


class Einordnen(unittest.TestCase):
    def test_us_schluss_nach_abruf_am_abend(self):
        # 18.11. 21:00 UTC Schluss, Abruf 21:30 UTC; Quote 16:00 New York
        r = kz.einordnen('NYSE', '2026-11-18T21:00:00+00:00', None, '2026-11-18T21:30:00+00:00')
        self.assertEqual((r['kind'], r['date']), ('schluss', '2026-11-18'))

    def test_us_vor_eroeffnung_ist_schluss_des_vortags(self):
        r = kz.einordnen('NASDAQ', 1795035600, None, '2026-11-19T13:04:00+00:00')   # 18.11. 21:00 UTC als Epoch
        self.assertEqual((r['kind'], r['date']), ('schluss', '2026-11-18'))

    def test_us_waehrend_handel(self):
        r = kz.einordnen('NYSE', '2026-11-19T17:30:00+00:00', None, '2026-11-19T17:44:00+00:00')
        self.assertEqual((r['kind'], r['date']), ('handel', '2026-11-19'))

    def test_kurz_nach_schluss_noch_nachlauf(self):
        r = kz.einordnen('NYSE', '2026-11-19T21:00:00+00:00', None, '2026-11-19T21:10:00+00:00')
        self.assertEqual(r['kind'], 'handel', 'innerhalb von 15 Minuten nach Schluss noch nicht sicher')

    def test_tokio_um_0117_utc_laeuft_der_handel(self):
        r = kz.einordnen('TSE', '2026-11-20T01:10:00+00:00', None, '2026-11-20T01:17:00+00:00')
        self.assertEqual(r['kind'], 'handel')
        r = kz.einordnen('TSE', '2026-11-19T06:30:00+00:00', None, '2026-11-19T23:40:00+00:00')
        self.assertEqual((r['kind'], r['date']), ('schluss', '2026-11-19'), '08:40 Ortszeit am 20.11., vor Eröffnung')

    def test_sommerzeit(self):
        # Juli: New York UTC-4, Schluss 20:00 UTC
        self.assertEqual(kz.einordnen('NYSE', '2026-07-15T20:00:00+00:00', None, '2026-07-15T20:30:00+00:00')['kind'], 'schluss')

    def test_wochenende(self):
        r = kz.einordnen('XETR', '2026-11-20T16:35:00+00:00', None, '2026-11-21T09:00:00+00:00')
        self.assertEqual((r['kind'], r['date']), ('schluss', '2026-11-20'))

    def test_tagesbalken_ohne_uhrzeit(self):
        self.assertEqual(kz.einordnen('NYSE', None, '2026-11-18', '2026-11-19T13:00:00+00:00')['kind'], 'schluss')
        r = kz.einordnen('NYSE', None, '2026-11-19', '2026-11-19T17:00:00+00:00')
        self.assertEqual(r['kind'], 'unbekannt', 'Tagesbalken während der Sitzung kann unvollständig sein')
        self.assertEqual(kz.einordnen('NYSE', None, '2026-11-19', '2026-11-19T22:00:00+00:00')['kind'], 'schluss')

    def test_negativfaelle(self):
        self.assertEqual(kz.einordnen('XYZ', '2026-11-18T21:00:00+00:00', None, '2026-11-18T22:00:00+00:00')['reason'], 'Börse ohne hinterlegte Schlusszeit')
        self.assertEqual(kz.einordnen('NYSE', None, None, '2026-11-18T22:00:00+00:00')['reason'], 'Kurs ohne Zeitangabe')
        self.assertEqual(kz.einordnen('NYSE', '2026-11-18T21:00:00+00:00', None, None)['reason'], 'Abrufzeitpunkt fehlt')
        self.assertEqual(kz.einordnen('NYSE', '2026-11-19T21:00:00+00:00', None, '2026-11-18T22:00:00+00:00')['reason'], 'Kurszeit nach dem Abruf')
        self.assertEqual(kz.einordnen('NYSE', None, '2026-11-20', '2026-11-19T22:00:00+00:00')['reason'], 'Kursdatum nach dem Abruf')
        self.assertEqual(kz.einordnen('NYSE', 'kaputt', None, '2026-11-19T22:00:00+00:00')['kind'], 'unbekannt')
        self.assertIsNone(kz._zeit(True))
        self.assertIsNone(kz._zeit('2026-11-19T10:00:00'), 'ohne Zeitzone nicht verwendbar')


if __name__ == '__main__':
    unittest.main()


class Export(unittest.TestCase):
    def test_merge_nimmt_zeit_der_verwendeten_quelle(self):
        import providers
        m = providers._merge_sources('P', {'price': 111.7, '_price_time': 1795107600, 'currency': 'USD'}, {'price': 112.0, '_price_time': 1795546000}, {'price': 110.0})
        self.assertEqual((m['price'], m['price_source']), (111.7, 'yfinance'))
        self.assertEqual(m['price_time'], '2026-11-19T17:00:00+00:00')
        self.assertTrue(m['price_fetched_at'])
        m = providers._merge_sources('P', {}, {'price': 112.0, '_price_time': None}, {'price': 110.0})
        self.assertEqual((m['price'], m['price_source'], m['price_time']), (110.0, 'fmp', None), 'FMP ohne Zeitangabe')

    def test_zeile_mit_kursart(self):
        import precompute
        z = precompute._kurszeitpunkt({'exchange': 'NYSE', 'price_source': 'yfinance', 'price_time': '2026-11-19T17:00:00+00:00', 'price_fetched_at': '2026-11-19T17:05:00+00:00'})
        self.assertEqual((z['price_kind'], z['price_day'], z['price_kind_method']), ('handel', '2026-11-19', 'exchange_close_v1'))
        z = precompute._kurszeitpunkt({'listing_symbol': 'TSE:2802', 'price_source': 'roic_latest', 'price_date': '2026-11-19', 'price_fetched_at': '2026-11-19T22:00:00+00:00'})
        self.assertEqual((z['price_kind'], z['price_day']), ('schluss', '2026-11-19'))
        z = precompute._kurszeitpunkt({'exchange': 'NYSE'})
        self.assertEqual((z['price_kind'], z['price_kind_reason']), ('unbekannt', 'Abrufzeitpunkt fehlt'))
