import json, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import fv_verlauf as fl


def z(sym='NYSE:A', fv=80.0, p=100.0, isin='US0000000001', cur='USD', **o):
    return {'listing_symbol': sym, 'fair_value': fv, 'price': p, 'isin': isin, 'currency': cur, 'fv_reliable': True, 'playbook': 'quality', 'name': 'A', **o}


class Verlauf(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.o = Path(self.t.name)

    def tearDown(self):
        self.t.cleanup()

    def lauf(self, stand, rows, m='abc'):
        p, q = {}, {}
        r = fl.eintragen({'stand': stand, 'kandidaten': rows}, {'pfad': 'x'}, m, self.o, p, q)
        fl.schreiben(p, self.o, q)
        return r

    def datei(self, sym='NYSE:A'):
        return json.loads((self.o / fl.dateiname(sym)).read_text())

    def test_ein_punkt_je_tag_mit_wert_und_methode(self):
        self.assertEqual(self.lauf('2026-11-19 13:04 UTC', [z()])['neu'], 1)
        self.assertEqual(self.lauf('2026-11-19 17:44 UTC', [z(fv=90)])['tag_vorhanden'], 1, 'spaeterer Lauf am selben Tag ersetzt nichts')
        self.lauf('2026-11-20 01:42 UTC', [z(fv=84)], m='neu')
        d = self.datei()
        self.assertEqual([(p['d'], p['fv'], p['m']) for p in d['punkte']], [('2026-11-19', 80.0, 'abc'), ('2026-11-20', 84.0, 'neu')])
        self.assertEqual(d['inputIdentity'], {'listing_symbol': 'NYSE:A', 'isin': 'US0000000001', 'currency': 'USD'})
        self.assertEqual((d['method'], d['punkte'][0]['verl'], d['punkte'][0]['modell']), ('fv_daily_log_v1', True, 'quality'))
        q = json.loads((self.o / '_quellen.json').read_text())['tage']
        self.assertEqual(q['2026-11-19'], {'pfad': 'x', 'm': 'abc'}, 'erster Stand des Tages bleibt')
        self.assertNotIn('quelle', d['punkte'][0], 'Herkunft je Tag, nicht je Punkt')

    def test_offener_fv_mit_grund_nie_null_als_wert(self):
        self.lauf('2026-11-19 13:04 UTC', [z(fv=None, kauf_urteil='Daten prüfen'), z(sym='NYSE:B', fv=0)])
        self.assertEqual((self.datei()['punkte'][0]['fv'], self.datei()['punkte'][0]['grund']), (None, 'Daten prüfen'))
        self.assertEqual(self.datei('NYSE:B')['punkte'][0]['grund'], 'Fair Value offen')

    def test_identitaet_und_kurs(self):
        self.lauf('2026-11-19 13:04 UTC', [z()])
        r = self.lauf('2026-11-20 01:42 UTC', [z(isin='US9999999999'), z(sym='NYSE:B', p=None), {'listing_symbol': None}])
        self.assertEqual((r['identitaet_abweichend'], r['ohne_kurs'], r['neu']), (1, 1, 0))
        r = self.lauf('2026-11-21 01:42 UTC', [z(cur='EUR')])
        self.assertEqual(r['identitaet_abweichend'], 1)
        self.assertEqual(len(self.datei()['punkte']), 1)

    def test_stand_und_methodenstand(self):
        with self.assertRaises(ValueError):
            self.lauf('kaputt', [z()])
        self.assertEqual(fl.methodenstand(None), 'python')
        self.assertEqual(len(fl.methodenstand(b'x')), 12)
        self.assertEqual(fl.dateiname('XETR:VOW3'), 'XETR_VOW3.json')


if __name__ == '__main__':
    unittest.main()
