"""SEC-Jahre für die Kennzahlen je Aktie (sec_annual_per_share_v1, seit 27.11.2026)."""
import datetime as dt
import unittest
from export_fundamentals import sec_jahre_je_aktie, per_share_archivieren, SEC_PER_SHARE_METHOD, PER_SHARE_METHOD

HEUTE = dt.date(2026, 11, 27)
INFO = {'financialCurrency': 'USD', 'currency': 'USD'}


def fakt(val, end, filed, accn, start=None):
    f = {'val': val, 'end': end, 'filed': filed, 'accn': accn, 'form': '10-K', 'fy': int(filed[:4]), 'fp': 'FY'}
    if start:
        f['start'] = start
    return f


def facts(eps, ni=(), eq=(), sh=()):
    u = lambda xs, unit: {'units': {unit: list(xs)}}
    return {'cik': 1045810, 'facts': {'us-gaap': {'EarningsPerShareDiluted': u(eps, 'USD/shares'), 'NetIncomeLoss': u(ni, 'USD'),
                                                  'StockholdersEquity': u(eq, 'USD'), 'CommonStockSharesOutstanding': u(sh, 'shares')}}}


A20, A23, A25 = '0001045810-20-000010', '0001045810-23-000017', '0001045810-25-000023'
# Wie NVDA: Split 10:1 am 10.06.2024. GJ 2020 nur im Original (vor dem Split eingereicht), GJ 2023 im Original und
# im 10-K 2025 angepasst (0,174). Yahoo liefert GJ 2023 (31.01.) mit 0,174.
EPS = [fakt(6.90, '2020-01-26', '2020-02-20', A20, '2019-01-28'), fakt(1.74, '2023-01-29', '2023-02-24', A23, '2022-01-31'),
       fakt(0.174, '2023-01-29', '2025-02-26', A25, '2022-01-31')]
NI = [fakt(2.796e9, '2020-01-26', '2020-02-20', A20, '2019-01-28')]
EQ = [fakt(12.204e9, '2020-01-26', '2020-02-20', A20)]
SH = [fakt(612e6, '2020-01-26', '2020-02-20', A20)]
SPLITS = [{'date': '2021-07-20', 'ratio': 4.0}, {'date': '2024-06-10', 'ratio': 10.0}]
KURSE = [('2019-01-25', 3.6, 0.0), ('2019-06-01', 4.0, 0.004), ('2019-12-01', 5.0, 0.004), ('2020-01-24', 6.1, 0.0),
         ('2023-01-31', 19.54, 0.0)]
YAHOO = [{'end': '2023-01-31', 'fields': {'eps_diluted': 0.174}}]


def lauf(daten=None, yahoo=YAHOO, info=INFO, splits=SPLITS, cik='1045810'):
    return sec_jahre_je_aktie(daten or facts(EPS, NI, EQ, SH), cik, KURSE, splits, yahoo, info, 'abc', '2026-11-27T05:00:00Z', HEUTE)


class SecJeAktie(unittest.TestCase):
    def test_split_umrechnung_und_kennzeichnung(self):
        jahre, block, grund = lauf()
        self.assertIsNone(grund)
        self.assertEqual([j['end'] for j in jahre], ['2020-01-26'], 'nur Jahre vor dem ältesten Yahoo-Jahr')
        j = jahre[0]
        self.assertAlmostEqual(j['fields']['eps_diluted'], 6.90 / 40, msg='beide Splits nach der Einreichung 2020')
        self.assertAlmostEqual(j['fields']['shares'], 612e6 * 40)
        self.assertEqual(j['fields']['net_income'], 2.796e9, 'Gewinn bleibt unverändert')
        self.assertEqual((j['herkunft'], j['sec']['accession'], j['sec']['split_faktor']), ('sec', A20, 40.0))
        self.assertIn('/1045810/000104581020000010/', j['sec']['source_url'])
        self.assertEqual((j['kurs']['datum'], j['kurs']['schluss']), ('2020-01-24', 6.1))
        self.assertAlmostEqual(j['kurs']['dividende_je_aktie'], 0.008)
        self.assertEqual((block['method'], block['sha256'], block['abgleich']['jahre'], block['abgleich']['max_abweichung']), (SEC_PER_SHARE_METHOD, 'abc', 1, 0.0))

    def test_angepasste_zahl_gilt_und_wird_nicht_doppelt_umgerechnet(self):
        _, block, _ = lauf()
        self.assertEqual(block['abgleich']['max_abweichung'], 0.0, '0,174 aus dem 10-K 2025, nach dem Split eingereicht: Faktor 1')

    def test_abweichung_verwirft_den_ganzen_block(self):
        jahre, block, grund = lauf(yahoo=[{'end': '2023-01-31', 'fields': {'eps_diluted': 0.19}}])
        self.assertEqual((jahre, block), ([], None))
        self.assertIn('GJ 2023 weicht ab', grund)

    def test_ohne_abgleichsjahr_keine_sec_jahre(self):
        self.assertEqual(lauf(yahoo=[])[2], 'Kein Geschäftsjahr zum Abgleich mit Yahoo')

    def test_fehlender_split_faellt_im_abgleich_auf(self):
        # Grenze: Fehlt die Split-Historie, bleibt ein Jahr ohne angepasste 10-K-Zahl auf alter Aktienbasis, während der
        # Yahoo-Kurs split-bereinigt ist; das KGV wäre dann um den Split-Faktor zu klein. Der Abgleich fängt das nur, wenn ein
        # Abgleichsjahr selbst betroffen ist. Deshalb kommen Splits und Kurse immer aus derselben Yahoo-Antwort.
        jahre, _, _ = lauf(splits=[])
        self.assertAlmostEqual(jahre[0]['fields']['eps_diluted'], 6.90, msg='ohne Splits keine Umrechnung')

    def test_identitaet_und_waehrung(self):
        self.assertEqual(lauf(cik='999')[2], 'SEC-Identität (CIK) abweichend')
        self.assertEqual(lauf(info={'financialCurrency': 'EUR', 'currency': 'USD'})[2], 'Abschluss oder Notierung nicht in USD')

    def test_nur_10k_mit_jahresdauer_und_gueltiger_accession(self):
        quartal = fakt(1.5, '2019-10-27', '2019-11-21', '0001045810-19-000099', '2019-07-29')
        q = {**fakt(9.9, '2018-01-28', '2018-03-01', '0001045810-18-000010', '2017-01-30'), 'form': '10-Q'}
        kaputt = fakt(5.0, '2017-01-29', '2017-03-01', 'xyz', '2016-02-01')
        jahre, _, _ = lauf(facts(EPS + [quartal, q, kaputt], NI, EQ, SH))
        self.assertEqual([j['end'] for j in jahre], ['2020-01-26'])

    def test_fehlende_bilanz_bleibt_offen_und_alte_dividende_ohne_kurshistorie(self):
        jahre, _, _ = lauf(facts(EPS + [fakt(1.0, '2010-01-31', '2010-03-18', '0001045810-10-000012', '2009-02-02')], NI, EQ, SH))
        alt = jahre[0]
        self.assertEqual(alt['end'], '2010-01-31')
        self.assertIsNone(alt['fields']['equity']); self.assertIsNone(alt['fields']['shares'])
        self.assertIsNone(alt['kurs']['schluss']); self.assertIsNone(alt['kurs']['dividende_je_aktie'], 'Kurshistorie beginnt später: keine Dividende 0')


class ArchivMitSec(unittest.TestCase):
    def datei(self, jahre, stand):
        return {'symbol': 'NASDAQ:NVDA', 'yahoo_symbol': 'NVDA', 'retrieved_at': stand, 'issues': [], 'per_share': {'method': PER_SHARE_METHOD, 'jahre': jahre}}

    def test_archivjahr_hat_vorrang_vor_sec_und_sec_bleibt_sec(self):
        alt = self.datei([{'end': '2022-01-30', 'fields': {'eps_diluted': 0.39}, 'herkunft': 'yahoo'},
                          {'end': '2020-01-26', 'fields': {'eps_diluted': 0.17}, 'herkunft': 'sec', 'sec': {'accession': A20}}], '2026-01-10T00:00:00Z')
        neu = self.datei([{'end': '2022-01-30', 'fields': {'eps_diluted': 0.38}, 'herkunft': 'sec', 'sec': {'accession': A23}},
                          {'end': '2023-01-31', 'fields': {'eps_diluted': 0.174}}], '2026-11-27T00:00:00Z')
        j = {x['end']: x for x in per_share_archivieren(neu, alt)['per_share']['jahre']}
        self.assertEqual((j['2022-01-30']['herkunft'], j['2022-01-30']['fields']['eps_diluted']), ('archiv', 0.39), 'eigene frühere Lieferung schlägt SEC')
        self.assertEqual(j['2020-01-26']['herkunft'], 'sec', 'SEC-Jahr aus dem Vorlauf bleibt SEC')
        self.assertEqual(j['2023-01-31']['herkunft'], 'yahoo')

    def test_sec_block_wandert_mit_wenn_sec_heute_fehlt(self):
        alt = self.datei([{'end': '2020-01-26', 'fields': {'eps_diluted': 0.17}, 'herkunft': 'sec', 'sec': {'accession': A20}}], '2026-01-10T00:00:00Z')
        alt['per_share']['sec'] = {'method': SEC_PER_SHARE_METHOD, 'sha256': 'abc'}
        neu = per_share_archivieren(self.datei([{'end': '2023-01-31', 'fields': {'eps_diluted': 0.174}}], '2026-11-27T00:00:00Z'), alt)
        self.assertEqual(neu['per_share']['sec']['sha256'], 'abc')
        self.assertEqual([x['herkunft'] for x in neu['per_share']['jahre']], ['sec', 'yahoo'])


if __name__ == '__main__':
    unittest.main()
