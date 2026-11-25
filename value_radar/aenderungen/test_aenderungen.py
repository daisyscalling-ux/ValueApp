import datetime as dt
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import aenderungen as A

UTC = dt.timezone.utc


def zeile(sym='NASDAQ:ADI', **o):
    r = {'listing_symbol': sym, 'name': 'Analog Devices', 'isin': 'US0326541051', 'currency': 'USD', 'price': 300.0, 'fair_value': 180.0,
         'target_12m': 370.0, 'composite': 50, 'quantum': 50, 'kauf_urteil': 'meiden', 'lifecycle_phase': 'mature', 'playbook': 'quality',
         'supplement_annual_end': '2025-11-01', 'eps_forward': None, 'eps_forward_status': 'abgelaufen', 'target_mean': 400.0,
         'eps_trailing': 4.56, 'book_value_ps': 70.0, 'value': 40, 'quality': 60, 'momentum': 50, 'growth': 50, 'health': 60, 'catalyst': 50,
         'score_diagnostics': {'fv_methods': {'core': {'dcf': 104, 'justified_pe': 106}, 'values': {'dcf': 104, 'justified_pe': 106}},
                               'target': {'fundamental': 250, 'analyst': 400, 'momentum': 300}}}
    for k, v in o.items():
        r[k] = v
    return r


def welt(tmp, zeilen, stand):
    d = Path(tmp) / 'daten'
    d.mkdir(exist_ok=True)
    (d / 'cf_universum.json').write_text(json.dumps({'stand': stand, 'kandidaten': zeilen}))
    return d


class Schwellen(unittest.TestCase):
    def test_grenzen(self):
        a = {'fair_value': 100, 'target_12m': 100, 'composite': 50, 'quantum': 50}
        self.assertEqual(A.aenderungen_messen(a, {**a, 'fair_value': 109.9}), [])
        self.assertEqual(A.aenderungen_messen(a, {**a, 'fair_value': 110})[0]['kennzahl'], 'fair_value')
        self.assertEqual(A.aenderungen_messen(a, {**a, 'target_12m': 90})[0]['rel'], -0.1)
        self.assertEqual(A.aenderungen_messen(a, {**a, 'composite': 59.9}), [])
        self.assertEqual(A.aenderungen_messen(a, {**a, 'quantum': 40})[0]['diff'], -10)
        self.assertEqual(A.aenderungen_messen(a, {**a, 'fair_value': None})[0], {'kennzahl': 'fair_value', 'alt': 100, 'neu': None, 'rel': None})
        self.assertEqual(A.aenderungen_messen({**a, 'composite': None}, {**a, 'composite': 90}), [], 'ohne Vorwert kein Sprung')


class Lauf(unittest.TestCase):
    def test_neuer_abschluss_mit_quelle_und_fenster(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = welt(tmp, [zeile(), zeile('NYSE:X', isin='US0000000001')], 'S1')
            (d / 'fundamentals').mkdir()
            (d / 'fundamentals' / 'NASDAQ_ADI.json').write_text(json.dumps({'annual': {'end': '2026-10-31', 'source': 'SEC companyfacts / US-GAAP',
                'source_url': 'https://www.sec.gov/Archives/edgar/data/6281/000000628126000089/', 'published_at': '2026-11-24', 'accession': '0000006281-26-000089'}}))
            self.assertEqual(A.lauf(d, dt.datetime(2026, 11, 25, 7, tzinfo=UTC), 'c1'), 0)
            self.assertEqual(json.loads((d / 'cf_aenderungen.json').read_text())['eintraege'], [], 'erster Lauf: nur Stand')
            neu = zeile(fair_value=504.0, eps_trailing=10.21, supplement_annual_end='2026-10-31', eps_forward=16.7, eps_forward_status=None)
            (d / 'cf_universum.json').write_text(json.dumps({'stand': 'S2', 'kandidaten': [neu, zeile('NYSE:X', isin='US0000000001')]}))
            A.lauf(d, dt.datetime(2026, 11, 26, 7, tzinfo=UTC), 'c2')
            e = json.loads((d / 'cf_aenderungen.json').read_text())
            self.assertEqual((e['method'], e['scoreContribution'], len(e['eintraege'])), (A.METHOD, 0, 1))
            x = e['eintraege'][0]
            self.assertEqual((x['symbol'], x['tag'], x['werte'][0]['kennzahl']), ('NASDAQ:ADI', '2026-11-26', 'fair_value'))
            arten = [g['art'] for g in x['gruende']]
            self.assertEqual(arten[:2], ['neuer_abschluss', 'neuer_konsens'])
            self.assertNotIn('daten', arten, 'Gewinn je Aktie gehört zum neuen Abschluss, keine Datenkorrektur')
            q = x['gruende'][0]['quelle']
            self.assertEqual((q['veroeffentlicht'], q['accession']), ('2026-11-24', '0000006281-26-000089'))
            # gleicher Universumsstand: nichts zu tun; nach 8 Tagen fällt der Eintrag aus dem Fenster
            self.assertEqual(A.lauf(d, dt.datetime(2026, 11, 26, 9, tzinfo=UTC), 'c2'), 0)
            (d / 'cf_universum.json').write_text(json.dumps({'stand': 'S3', 'kandidaten': [neu, zeile('NYSE:X', isin='US0000000001')]}))
            A.lauf(d, dt.datetime(2026, 12, 4, 7, tzinfo=UTC), 'c3')
            self.assertEqual(json.loads((d / 'cf_aenderungen.json').read_text())['eintraege'], [])

    def test_andere_notierung_und_gruende(self):
        alt = A.schnappschuss({'stand': 'a', 'kandidaten': [zeile()]}, 'm1', 'c1', dt.datetime(2026, 11, 24, tzinfo=UTC))
        # andere ISIN: nicht vergleichbar
        neu = A.schnappschuss({'stand': 'b', 'kandidaten': [zeile(isin='US9999999999', fair_value=500)]}, 'm1', 'c2', dt.datetime(2026, 11, 25, tzinfo=UTC))
        self.assertEqual(A.vergleichen(alt, neu, lambda s: None, '2026-11-25'), [])
        # Methode geändert + Kernmethoden gewechselt + Kurs
        neu = A.schnappschuss({'stand': 'b', 'kandidaten': [zeile(fair_value=250, price=340, score_diagnostics={'fv_methods': {'core': {'ev_ebitda': 250}, 'values': {'ev_ebitda': 250}}, 'target': {}})]},
                              'm2', 'c2', dt.datetime(2026, 11, 25, tzinfo=UTC))
        g = A.vergleichen(alt, neu, lambda s: None, '2026-11-25')[0]['gruende']
        arten = [x['art'] for x in g]
        self.assertIn('methode', arten); self.assertIn('kernmethoden', arten); self.assertIn('kurs', arten)
        self.assertTrue(g[arten.index('methode')]['quelle']['url'].endswith('/compare/c1...c2'))
        self.assertIn('+ EV/EBITDA', g[arten.index('kernmethoden')]['text'])
        # nichts erkennbar
        neu = A.schnappschuss({'stand': 'b', 'kandidaten': [zeile(fair_value=200)]}, 'm1', 'c2', dt.datetime(2026, 11, 25, tzinfo=UTC))
        self.assertEqual(A.vergleichen(alt, neu, lambda s: None, '2026-11-25')[0]['gruende'], [{'art': 'unbekannt', 'text': 'Grund nicht erkannt', 'quelle': None}])

    def test_datenkorrektur_und_quelle_nur_bei_passendem_stichtag(self):
        alt = A.schnappschuss({'stand': 'a', 'kandidaten': [zeile()]}, 'm', 'c', dt.datetime(2026, 11, 24, tzinfo=UTC))
        neu = A.schnappschuss({'stand': 'b', 'kandidaten': [zeile(fair_value=230, book_value_ps=97, share_count_basis='alle_gattungen')]}, 'm', 'c', dt.datetime(2026, 11, 25, tzinfo=UTC))
        t = A.vergleichen(alt, neu, lambda s: None, 'x')[0]['gruende'][0]
        self.assertEqual(t['art'], 'daten'); self.assertIn('Buchwert je Aktie 70.0 → 97', t['text']); self.assertIn('alle_gattungen', t['text'])
        g = A.gruende('NASDAQ:ADI', zeile(), zeile(supplement_annual_end='2026-10-31'), None, None, None, None, {'annual': {'end': '2025-11-01', 'source_url': 'https://x'}})
        self.assertIsNone(g[0]['quelle'], 'Quelle nur, wenn der Stichtag der Ergänzungsdatei passt')
        g = A.gruende('NASDAQ:ADI', zeile(), zeile(supplement_annual_end='2026-10-31'), None, None, None, None, {'annual': {'end': '2026-10-31', 'source_url': 'http://unsicher'}})
        self.assertIsNone(g[0]['quelle'], 'nur https')

    def test_ohne_universum(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(A.lauf(Path(tmp)), 1)


if __name__ == '__main__':
    unittest.main()
