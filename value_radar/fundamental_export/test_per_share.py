import unittest
from export_fundamentals import kennzahlen_jahre, per_share_archivieren, PER_SHARE_METHOD, PER_SHARE_ARCHIVE_METHOD

FR = {'income': {'2025-10-31T00:00:00.000': {'Diluted EPS': 10.21, 'Net Income': 5.0e9}, '2024-10-31T00:00:00.000': {'Diluted EPS': 4.56, 'Net Income': 2.27e9}},
      'balance': {'2025-10-31T00:00:00.000': {'Stockholders Equity': 35e9, 'Ordinary Shares Number': 4.9e8}},
      'cashflow': {'2025-10-31T00:00:00.000': {'Cash Dividends Paid': -1.9e9}}}
INFO = {'financialCurrency': 'USD', 'currency': 'USD', 'symbol': 'ADI'}
KURSE = [('2024-10-30', 220.0, 0.0), ('2024-12-02', 210.0, 0.92), ('2025-03-03', 230.0, 0.99), ('2025-10-31', 300.0, 0.0), ('2025-11-03', 305.0, 0.99)]


class PerShare(unittest.TestCase):
    def test_jahre_mit_kurs_und_dividende(self):
        b = kennzahlen_jahre(FR, INFO, KURSE)
        self.assertEqual(b['method'], PER_SHARE_METHOD)
        j = {x['end']: x for x in b['jahre']}
        self.assertEqual(list(j), ['2024-10-31', '2025-10-31'], 'aufsteigend')
        n = j['2025-10-31']
        self.assertEqual((n['fields']['eps_diluted'], n['fields']['equity'], n['fields']['shares'], n['fields']['dividends_paid']), (10.21, 35e9, 4.9e8, 1.9e9))
        self.assertEqual((n['kurs']['datum'], n['kurs']['schluss']), ('2025-10-31', 300.0))
        self.assertAlmostEqual(n['kurs']['dividende_je_aktie'], 0.92 + 0.99, msg='nur Dividenden im Geschäftsjahr, nicht danach')
        a = j['2024-10-31']
        self.assertEqual((a['kurs']['datum'], a['fields']['equity']), ('2024-10-30', None), 'Kurs bis zum Stichtag, fehlende Bilanz bleibt None')

    def test_kein_kurs_nahe_stichtag(self):
        b = kennzahlen_jahre(FR, INFO, [('2025-09-01', 280.0, 0.0)])
        n = [x for x in b['jahre'] if x['end'] == '2025-10-31'][0]
        self.assertIsNone(n['kurs']['schluss'], 'letzter Kurs mehr als 7 Tage vor dem Stichtag')
        self.assertIsNone(kennzahlen_jahre(FR, INFO, [])['jahre'][0]['kurs']['dividende_je_aktie'], 'ohne Kurshistorie keine Dividende 0')


def _datei(jahre, sym='NASDAQ:ADI', ys='ADI', stand='2026-11-26T05:00:00Z', method=PER_SHARE_METHOD):
    return {'symbol': sym, 'yahoo_symbol': ys, 'retrieved_at': stand, 'issues': [],
            'per_share': None if jahre is None else {'method': method, 'jahre': [{'end': e, 'fields': {'eps_diluted': v}} for e, v in jahre]}}


class Archiv(unittest.TestCase):
    def test_altes_jahr_bleibt_gekennzeichnet(self):
        alt = _datei([('2021-10-31', 3.0), ('2022-10-31', 5.0), ('2023-10-31', 6.0)], stand='2026-01-10T05:00:00Z')
        neu = per_share_archivieren(_datei([('2022-10-31', 5.1), ('2023-10-31', 6.0), ('2024-10-31', 4.56)]), alt)
        j = {x['end']: x for x in neu['per_share']['jahre']}
        self.assertEqual(list(j), ['2021-10-31', '2022-10-31', '2023-10-31', '2024-10-31'], 'aufsteigend, nichts gelöscht')
        self.assertEqual((j['2021-10-31']['herkunft'], j['2021-10-31']['zuletzt_geliefert']), ('archiv', '2026-01-10T05:00:00Z'))
        self.assertEqual((j['2022-10-31']['herkunft'], j['2022-10-31']['fields']['eps_diluted']), ('yahoo', 5.1), 'neue Lieferung gilt')
        self.assertEqual(neu['per_share']['archiv'], {'method': PER_SHARE_ARCHIVE_METHOD, 'jahre': 1})

    def test_archiv_wird_weitergereicht_mit_erstem_datum(self):
        erst = per_share_archivieren(_datei([('2022-10-31', 5.0)], stand='2026-02-01T00:00:00Z'), _datei([('2021-10-31', 3.0)], stand='2026-01-01T00:00:00Z'))
        zweit = per_share_archivieren(_datei([('2023-10-31', 6.0)], stand='2026-03-01T00:00:00Z'), erst)
        j = {x['end']: x for x in zweit['per_share']['jahre']}
        self.assertEqual(j['2021-10-31']['zuletzt_geliefert'], '2026-01-01T00:00:00Z', 'Datum der letzten echten Lieferung bleibt')
        self.assertEqual(j['2022-10-31']['zuletzt_geliefert'], '2026-02-01T00:00:00Z')
        self.assertEqual(zweit['per_share']['archiv']['jahre'], 2)

    def test_andere_notierung_oder_methode_verwirft(self):
        alt = _datei([('2021-10-31', 3.0)])
        neu = per_share_archivieren(_datei([('2024-10-31', 4.0)], ys='ADI.DE'), alt)
        self.assertEqual([x['end'] for x in neu['per_share']['jahre']], ['2024-10-31'])
        self.assertIn('Notierung abweichend', ' '.join(neu['issues']))
        anders = per_share_archivieren(_datei([('2024-10-31', 4.0)]), _datei([('2021-10-31', 3.0)], method='x'))
        self.assertEqual(len(anders['per_share']['jahre']), 1)

    def test_fehlender_abruf_behaelt_block_und_ohne_alt_nur_kennzeichnung(self):
        alt = _datei([('2021-10-31', 3.0)])
        neu = per_share_archivieren(_datei(None), alt)
        self.assertEqual(neu['per_share']['jahre'][0]['end'], '2021-10-31')
        self.assertIn('bisheriger Block behalten', ' '.join(neu['issues']))
        erst = per_share_archivieren(_datei([('2024-10-31', 4.0)]), None)
        self.assertEqual((erst['per_share']['jahre'][0]['herkunft'], 'archiv' in erst['per_share']), ('yahoo', False))


if __name__ == '__main__':
    unittest.main()
