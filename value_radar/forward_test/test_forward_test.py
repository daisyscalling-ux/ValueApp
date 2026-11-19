import datetime as dt, json, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import forward_test as ft


SCHLUSS = {'exchange': 'NYSE', 'price_time': '2026-11-18T21:00:00+00:00', 'price_fetched_at': '2026-11-19T13:00:00+00:00',
           'price_kind': 'schluss', 'price_day': '2026-11-18', 'price_kind_method': 'exchange_close_v1'}
HANDEL = {**SCHLUSS, 'price_time': '2026-11-19T17:00:00+00:00', 'price_fetched_at': '2026-11-19T17:05:00+00:00',
          'price_kind': 'handel', 'price_day': '2026-11-19'}


def zeile(sym, p, fv, z, land='US', isin=None, cur='USD', **o):
    return {'listing_symbol': sym, 'price': p, 'fair_value': fv, 'target_12m': z, 'country': land,
            'isin': isin or 'US' + sym.split(':')[-1].ljust(10, '0'), 'currency': cur, **SCHLUSS, **o}


def universum(stand, kurse, extra=()):
    """kurse: {sym: preis} fuer 25 Markttitel M0..M24 plus Sondertitel extra (fertige Zeilen)."""
    rows = [zeile(f'NYSE:M{i}', kurse.get(f'NYSE:M{i}', 100), None, None) for i in range(25)]
    return {'stand': stand, 'kandidaten': rows + list(extra)}


class Auswahl(unittest.TestCase):
    def test_nur_gegenlaeufig_je_mindestens_5_prozent(self):
        self.assertEqual(ft.gegenlaeufig(zeile('X:A', 100, 86, 112)), (-0.14, 0.12000000000000011))
        self.assertIsNone(ft.gegenlaeufig(zeile('X:A', 100, 96, 120)), 'FV nur -4 %')
        self.assertIsNone(ft.gegenlaeufig(zeile('X:A', 100, 80, 90)), 'gleiche Richtung')
        for fv, z in [(None, 120), (80, None), (0, 120), (80, float('nan')), (True, 120)]:
            self.assertIsNone(ft.gegenlaeufig(zeile('X:A', 100, fv, z)))
        self.assertIsNone(ft.gegenlaeufig(zeile('X:A', None, 80, 120)))

    def test_schnappschuss_mit_identitaet_und_herkunft(self):
        doc = universum('2026-11-19 13:04 UTC', {}, [zeile('XETR:SAP', 200, 172, 260, land='DE', isin='DE0007164600', cur='EUR', playbook='quality')])
        s = ft.schnappschuss(doc, 'value_radar/daten/cf_universum.json', 'aktuell', roh=b'x')
        self.assertEqual(len(s['eintraege']), 1)
        e = s['eintraege'][0]
        self.assertEqual((e['isin'], e['currency'], e['region'], e['oben']), ('DE0007164600', 'EUR', 'Europa ohne GB', 'ziel_12m'))
        self.assertEqual((e['fv_pct'], e['target_pct']), (-14.0, 30.0))
        self.assertEqual(len(s['kurse']), 26)
        self.assertEqual(len(s['quelle']['sha256']), 64)
        self.assertTrue(e['fingerabdruck'])
        with self.assertRaises(ValueError):
            ft.schnappschuss({'stand': 'kaputt', 'kandidaten': []}, 'x', 'aktuell')

    def test_regionen(self):
        self.assertEqual([ft.region(x) for x in ('US', 'United States', 'JP', 'GB', 'CH', 'AU', None)],
                         ['USA', 'USA', 'Japan', 'Grossbritannien', 'Europa ohne GB', 'sonstige', 'sonstige'])

    def test_speichern_einmal_je_stand(self):
        with tempfile.TemporaryDirectory() as d:
            s = ft.schnappschuss(universum('2026-11-19 13:04 UTC', {}), 'x', 'aktuell')
            self.assertEqual(ft.speichern(s, Path(d)).name, '2026-11-19T1304.json')
            self.assertIsNone(ft.speichern(s, Path(d)), 'vorhandener Stand wird nicht ueberschrieben')
            s2 = ft.schnappschuss(universum('2026-11-19 22:10 UTC', {}), 'x', 'aktuell')
            self.assertIsNone(ft.speichern(s2, Path(d)), 'ein Stand je Kalendertag')
            s3 = ft.schnappschuss(universum('2026-11-20 01:10 UTC', {}), 'x', 'aktuell')
            self.assertTrue(ft.speichern(s3, Path(d)))


def zwei_staende(p1, sonder1=None, markt=110, splits=None, tage=31, kohorte='aktuell', land='US'):
    a = zeile('NYSE:A', 100, 80, 120, land=land)  # FV unten, Ziel oben
    b = dict(sonder1 or zeile('NYSE:A', p1, 80, 120, land=land))
    s0 = ft.schnappschuss(universum('2026-11-19 13:04 UTC', {}, [a]), 'x', kohorte)
    t1 = (dt.datetime(2026, 11, 19, 13, 4) + dt.timedelta(days=tage)).strftime('%Y-%m-%d %H:%M UTC')
    s1 = ft.schnappschuss(universum(t1, {f'NYSE:M{i}': markt for i in range(25)}, [b]), 'x', kohorte)
    jetzt = dt.datetime(2027, 1, 1, tzinfo=dt.timezone.utc)
    return ft.auswerten([s1, s0], jetzt=jetzt, splits_von=lambda sym: (splits or {}).get(sym, []))


def einmonat(erg, kohorte='aktuell'):
    return next(z for z in erg['ergebnisse'] if z['zeitraum'] == '1M' and z['kohorte'] == kohorte)


class Auswertung(unittest.TestCase):
    def test_marktbereinigt_steigt_ziel_hat_recht(self):
        z = einmonat(zwei_staende(125))     # +25 % bei Markt +10 %: marktbereinigt +13,6 %
        self.assertEqual((z['n'], z['titel'], z['ziel_12m_recht'], z['fair_value_recht']), (1, 1, 1, 0))
        self.assertEqual(z['nach_oben_zeigte']['ziel_12m'], {'stieg': 1, 'fiel': 0})
        self.assertEqual(list(z['nach_methode'].values()), [{'fair_value': 0, 'ziel_12m': 1, 'unentschieden': 0}])

    def test_steigt_absolut_aber_schwaecher_als_markt_fv_hat_recht(self):
        z = einmonat(zwei_staende(104))     # +4 % bei Markt +10 %: marktbereinigt -5,5 %
        self.assertEqual((z['fair_value_recht'], z['ziel_12m_recht']), (1, 0))
        self.assertAlmostEqual(z['median_marktbereinigt_pct'], -5.45, places=2)

    def test_unentschieden_innerhalb_2_prozent(self):
        z = einmonat(zwei_staende(111.5))
        self.assertEqual((z['unentschieden'], z['fair_value_recht'], z['ziel_12m_recht'], z['anteil_fair_value']), (1, 0, 0, None))

    def test_split_bereinigt(self):
        z = einmonat(zwei_staende(25, markt=100, splits={'NYSE:A': [{'date': '2026-12-01', 'ratio': 4}]}))
        self.assertEqual((z['n'], z['unentschieden']), (1, 1), '25 x 4 = 100: keine Bewegung')
        z = einmonat(zwei_staende(25, markt=100, splits={'NYSE:A': [{'date': '2026-11-01', 'ratio': 4}]}))
        self.assertEqual(z['offen'], {'Kurssprung ohne Splitnachweis': 1}, 'Split vor dem Stand zaehlt nicht')

    def test_kurssprung_ohne_split_offen(self):
        self.assertEqual(einmonat(zwei_staende(45, markt=100))['offen'], {'Kurssprung ohne Splitnachweis': 1})

    def test_identitaetsbruch_offen(self):
        self.assertEqual(einmonat(zwei_staende(0, sonder1=zeile('NYSE:A', 110, 80, 120, cur='EUR')))['offen'], {'Waehrung verschieden': 1})
        self.assertEqual(einmonat(zwei_staende(0, sonder1=zeile('NYSE:A', 110, 80, 120, isin='US9999999999')))['offen'], {'ISIN verschieden': 1})
        self.assertEqual(einmonat(zwei_staende(0, sonder1=zeile('NYSE:Z', 110, 80, 120)))['offen'], {'kein spaeterer Kurs': 1})

    def test_region_zu_klein_offen(self):
        self.assertEqual(einmonat(zwei_staende(125, land='JP'))['offen'], {'Region mit weniger als 20 Titeln': 1})

    def test_spaeterer_stand_zu_weit_weg(self):
        erg = zwei_staende(125, tage=45)
        self.assertFalse([z for z in erg['ergebnisse'] if z['zeitraum'] == '1M'])
        self.assertEqual(erg['ohne_passenden_spaeteren_stand'], {'aktuell 1M': 1})

    def test_nicht_faellig_und_kohorten_getrennt(self):
        erg = zwei_staende(125, kohorte='vorversion')
        self.assertEqual({(z['kohorte'], z['zeitraum']) for z in erg['ergebnisse']}, {('vorversion', '1M')}, '3M noch nicht faellig')

    def test_splitfaktor_robust(self):
        sp = [{'date': '2026-12-01', 'ratio': 2}, {'date': 'kaputt', 'ratio': 3}, {'date': '2026-12-02', 'ratio': -1}, {'date': '2026-12-03'}]
        self.assertEqual(ft.splitfaktor(sp, dt.date(2026, 11, 19), dt.date(2026, 12, 31)), 2)

    def test_splits_nur_fuer_dieselbe_notierung(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, 'NYSE_A.json').write_text(json.dumps({'symbol': 'NASDAQ:A', 'splits': [{'date': '2026-12-01', 'ratio': 2}]}))
            self.assertEqual(ft.splits_laden('NYSE:A', Path(d)), [])
            Path(d, 'NYSE_A.json').write_text(json.dumps({'symbol': 'NYSE:A', 'splits': [{'date': '2026-12-01', 'ratio': 2}]}))
            self.assertEqual(len(ft.splits_laden('NYSE:A', Path(d))), 1)
            self.assertEqual(ft.splits_laden('NYSE:B', Path(d)), [])


class Index(unittest.TestCase):
    def test_index_mit_staenden_und_splits_nach_dem_ersten_stand(self):
        with tempfile.TemporaryDirectory() as d:
            ordner = Path(d)
            ft.speichern(ft.schnappschuss(universum('2026-11-19 13:04 UTC', {}, [zeile('NYSE:A', 100, 80, 120)]), 'x', 'aktuell'), ordner / 'staende')
            sp = {'NYSE:A': [{'date': '2026-11-01', 'ratio': 2}, {'date': '2026-12-01', 'ratio': 4}]}
            doc = ft.index_schreiben(ordner, splits_von=lambda s: sp.get(s, []))
            self.assertEqual([(x['datei'], x['kohorte'], x['eintraege']) for x in doc['staende']], [('2026-11-19T1304.json', 'aktuell', 1)])
            self.assertEqual(len(doc['staende'][0]['sha256']), 64)
            self.assertEqual(doc['splits'], {'NYSE:A': [{'date': '2026-12-01', 'ratio': 4}]}, 'Split vor dem ersten Stand entfaellt')
            self.assertTrue((ordner / 'index.json').exists())


class Schlusskurs(unittest.TestCase):
    def test_nur_geprueft_schlusskurse_als_eintrag(self):
        doc = universum('2026-11-19 17:44 UTC', {}, [zeile('NYSE:A', 100, 80, 120), zeile('NYSE:B', 100, 80, 120, **HANDEL),
                                                    zeile('NYSE:C', 100, 80, 120, price_kind='handel'),
                                                    zeile('NYSE:D', 100, 80, 120, price_kind_method=None)])
        s = ft.schnappschuss(doc, 'x', 'aktuell')
        self.assertEqual([e['listing_symbol'] for e in s['eintraege']], ['NYSE:A'])
        self.assertEqual(s['eintraege'][0]['price_day'], '2026-11-18')
        self.assertEqual(s['gegenlaeufig_ohne_schlusskurs'], {'Abruf während der Handelszeit': 1,
                         'Kursart im Export widerspricht der Nachpruefung': 1, 'Kurs ohne Zeitangabe im Export': 1})
        self.assertEqual(s['kurse']['NYSE:B'][4:], ['handel', '2026-11-19'])
        self.assertEqual((s['schema'], s['method']), (2, 'fv_vs_target_forward_v2'))

    def test_spaeterer_kurs_muss_schluss_sein(self):
        z = einmonat(zwei_staende(0, sonder1=zeile('NYSE:A', 125, 80, 120, **HANDEL)))
        self.assertEqual(z['offen'], {'Kein Schlusskurs': 1})

    def test_schema_1_ist_immer_vorversion(self):
        self.assertEqual(ft.kohorte_von({'schema': 1, 'kohorte': 'aktuell'}), 'vorversion')
        self.assertEqual(ft.kohorte_von({'schema': 2, 'kohorte': 'aktuell'}), 'aktuell')
        alt = ft.schnappschuss(universum('2026-11-19 13:04 UTC', {}, [zeile('NYSE:A', 100, 80, 120)]), 'x', 'aktuell')
        alt['schema'] = 1
        for k, v in alt['kurse'].items():
            alt['kurse'][k] = v[:4]
        neu = ft.schnappschuss(universum('2026-12-20 01:00 UTC', {f'NYSE:M{i}': 110 for i in range(25)}, [zeile('NYSE:A', 125, 80, 120)]), 'x', 'aktuell')
        erg = ft.auswerten([alt, neu], jetzt=dt.datetime(2027, 1, 1, tzinfo=dt.timezone.utc), splits_von=lambda s: [])
        self.assertEqual([(z['kohorte'], z['zeitraum'], z['ziel_12m_recht']) for z in erg['ergebnisse']], [('vorversion', '1M', 1)])


if __name__ == '__main__':
    unittest.main()
