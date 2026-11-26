import unittest
from export_fundamentals import kennzahlen_jahre, PER_SHARE_METHOD

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


if __name__ == '__main__':
    unittest.main()
