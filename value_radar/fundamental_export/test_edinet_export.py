"""EDINET-Jahre für die Kennzahlen je Aktie im Export (edinet_per_share_export_v1, seit 27.11.2026)."""
import datetime as dt
import unittest
from export_fundamentals import edinet_jahre_je_aktie, per_share_archivieren, EDINET_PER_SHARE_METHOD, PER_SHARE_METHOD

HEUTE = dt.date(2026, 11, 27)
ROW = {'listing_symbol': 'TSE:4062', 'isin': 'JP3148800000'}
INFO = {'financialCurrency': 'JPY', 'currency': 'JPY'}
SPLITS = [{'date': '2025-12-29', 'ratio': 2.0}, {'date': '2026-09-29', 'ratio': 2.0}]


def jahr(end, eps, per, bvps=None, ni=1e9, diluted=False):
    return {'end': end, 'standard': 'jgaap', 'fields': {'eps_diluted': eps if diluted else None, 'eps_basic': None if diluted else eps,
                                                       'net_income': ni, 'bvps': bvps, 'per': per, 'dps': 50.0, 'shares_issued': 1e8}}


def eintrag(**o):
    neu = {'docID': 'S100NEU1', 'edinetCode': 'E01234', 'submitDateTime': '2026-06-20 10:00', 'fileSha256': 'a' * 64,
           # neuester Bericht: angepasst um den Split 12/2025 (Faktor 2 bleibt offen bis 09/2026)
           'jahre': [jahr('2024-03-31', 200.0, 20.0, 2000.0), jahr('2025-03-31', 220.0, 20.0), jahr('2026-03-31', 120.0, 25.0)]}
    alt = {'docID': 'S100ALT1', 'edinetCode': 'E01234', 'submitDateTime': '2022-06-20 10:00', 'fileSha256': 'b' * 64,
           # alter Bericht: vor beiden Splits, Faktor 4
           'jahre': [jahr('2019-03-31', 400.0, 15.0, 4000.0), jahr('2020-03-31', -50.0, None), jahr('2022-03-31', 360.0, 18.0)]}
    return {'inputIdentity': {'listing_symbol': 'TSE:4062', 'isin': 'JP3148800000', 'currency': 'JPY'}, 'retrievedAt': '2026-11-27T13:57:00+00:00',
            'berichte': [neu, alt], **o}


# Yahoo-Kurse split-bereinigt (heutige Basis): Kurs = KGV × EPS ÷ Faktor
KURSE = [('2019-03-29', 15 * 400 / 4, 0.0), ('2020-03-31', 1000.0, 0.0), ('2022-03-31', 18 * 360 / 4, 0.0), ('2024-03-29', 20 * 200 / 2, 0.0),
         ('2025-03-31', 20 * 220 / 2, 0.0), ('2026-03-31', 25 * 120 / 2, 0.0)]
YAHOO = [{'end': '2024-03-31', 'fields': {'eps_diluted': 100.0}}, {'end': '2025-03-31', 'fields': {'eps_diluted': 110.0}}, {'end': '2026-03-31', 'fields': {'eps_diluted': 60.0}}]


class EdinetExport(unittest.TestCase):
    def test_aktienbasis_aus_kgv_und_kennzeichnung(self):
        jahre, block, grund = edinet_jahre_je_aktie(eintrag(), ROW, KURSE, SPLITS, YAHOO, INFO, HEUTE)
        self.assertIsNone(grund)
        j = {x['end']: x for x in jahre}
        self.assertEqual(sorted(j), ['2019-03-31', '2020-03-31', '2022-03-31'], 'nur Jahre vor dem ältesten Yahoo-Jahr')
        a = j['2019-03-31']
        self.assertEqual((a['herkunft'], a['edinet']['split_faktor'], a['fields']['eps_diluted'], a['fields']['bvps']), ('edinet', 4.0, 100.0, 1000.0))
        self.assertEqual((a['edinet']['docID'], a['edinet']['eps_art'][:12]), ('S100ALT1', 'unverwässert'))
        self.assertEqual(j['2022-03-31']['fields']['eps_diluted'], 90.0)
        self.assertEqual((block['method'], block['abgleich']['jahre'], block['abgleich']['max_abweichung']), (EDINET_PER_SHARE_METHOD, 3, 0.0))

    def test_verlustjahr_ohne_kgv_bleibt_je_aktie_offen(self):
        jahre, block, _ = edinet_jahre_je_aktie(eintrag(), ROW, KURSE, SPLITS, YAHOO, INFO, HEUTE)
        v = [x for x in jahre if x['end'] == '2020-03-31'][0]
        self.assertEqual((v['fields']['eps_diluted'], v['fields']['net_income']), (None, 1e9), 'Gewinn bleibt, je Aktie offen')
        self.assertIn('GJ 2020: kein KGV im Bericht', ' '.join(block['offen']))

    def test_faktor_ausserhalb_toleranz(self):
        kurse = [k if k[0] != '2019-03-29' else ('2019-03-29', 15 * 400 / 3.0, 0.0) for k in KURSE]  # roh 3 statt 4
        jahre, block, _ = edinet_jahre_je_aktie(eintrag(), ROW, kurse, SPLITS, YAHOO, INFO, HEUTE)
        self.assertIsNone([x for x in jahre if x['end'] == '2019-03-31'][0]['fields']['eps_diluted'])
        self.assertIn('Aktienbasis nicht bestimmbar', ' '.join(block['offen']))

    def test_abgleich_identitaet_waehrung_alter(self):
        y = [{**YAHOO[0], 'fields': {'eps_diluted': 90.0}}] + YAHOO[1:]
        self.assertIn('GJ 2024 weicht ab', edinet_jahre_je_aktie(eintrag(), ROW, KURSE, SPLITS, y, INFO, HEUTE)[2])
        self.assertEqual(edinet_jahre_je_aktie(eintrag(), {**ROW, 'isin': 'JP3000000000'}, KURSE, SPLITS, YAHOO, INFO, HEUTE)[2], 'EDINET-Identität abweichend')
        self.assertEqual(edinet_jahre_je_aktie(eintrag(), ROW, KURSE, SPLITS, YAHOO, {'financialCurrency': 'USD', 'currency': 'JPY'}, HEUTE)[2], 'Abschluss oder Notierung nicht in JPY')
        self.assertIn('älter als 400', edinet_jahre_je_aktie(eintrag(retrievedAt='2025-01-01T00:00:00+00:00'), ROW, KURSE, SPLITS, YAHOO, INFO, HEUTE)[2])
        self.assertEqual(edinet_jahre_je_aktie(None, ROW, KURSE, SPLITS, YAHOO, INFO, HEUTE)[2], 'Keine EDINET-Fünfjahresübersicht')
        ohne_kurs = [k for k in KURSE if k[0] < '2024-01-01']
        self.assertEqual(edinet_jahre_je_aktie(eintrag(), ROW, ohne_kurs, SPLITS, YAHOO, INFO, HEUTE)[2], 'Kein Geschäftsjahr zum Abgleich mit Yahoo')

    def test_archiv_behaelt_edinet_samt_block(self):
        def datei(jahre, stand):
            return {'symbol': 'TSE:4062', 'yahoo_symbol': '4062.T', 'retrieved_at': stand, 'issues': [], 'per_share': {'method': PER_SHARE_METHOD, 'jahre': jahre}}
        alt = datei([{'end': '2019-03-31', 'herkunft': 'edinet', 'fields': {}}], '2026-11-01T00:00:00Z')
        alt['per_share']['edinet'] = {'method': EDINET_PER_SHARE_METHOD, 'jahre': 1}
        neu = per_share_archivieren(datei([{'end': '2024-03-31', 'fields': {}}], '2026-11-27T00:00:00Z'), alt)
        self.assertEqual([(x['end'], x['herkunft']) for x in neu['per_share']['jahre']], [('2019-03-31', 'edinet'), ('2024-03-31', 'yahoo')])
        self.assertEqual(neu['per_share']['edinet']['jahre'], 1)


if __name__ == '__main__':
    unittest.main()
