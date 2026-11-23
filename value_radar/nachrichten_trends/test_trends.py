import datetime as dt
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import trends as T

UTC = dt.timezone.utc
JETZT = dt.datetime(2026, 11, 21, 12, tzinfo=UTC)


def company(stocks):
 return {'schema': 1, 'stocks': stocks}


def stock(titel, tage_zurueck=1, quelle='ROIC', truncated=False, jetzt=JETZT, publisher='zacks.com'):
 return {'source': quelle, 'truncated': truncated, 'items': [
  {'title': t, 'url': f'https://ex.com/{i}-{abs(hash(t))}', 'publisher': publisher, 'publishedAt': (jetzt - dt.timedelta(days=tage_zurueck, minutes=i)).isoformat()}
  for i, t in enumerate(titel)]}


def market(titel, jetzt=JETZT, key='ft', error=None):
 return {'version': 1, 'sources': {key: {'name': 'FT', 'error': error, 'items': [
  {'title': t, 'url': f'https://ft.com/{i}', 'publisher': 'FT', 'publishedAt': (jetzt - dt.timedelta(hours=i + 1)).isoformat()} for i, t in enumerate(titel)]}}}


UNIVERSUM = {'kandidaten': [{'ticker': 'AAPL', 'listing_symbol': 'NASDAQ:AAPL', 'name': 'Apple Inc.'},
                            {'ticker': 'BATS', 'listing_symbol': 'LSE:BATS', 'name': 'British American Tobacco p.l.c.'},
                            {'ticker': 'SAP', 'listing_symbol': 'XETR:SAP', 'name': 'SAP SE'}]}


class Regeln(unittest.TestCase):
 def test_routine_und_themen(self):
  self.assertTrue(T.ist_routine('Shell PLC $SHEL Shares Sold by Cibc World Market Inc.'))
  self.assertTrue(T.ist_routine('First Eagle Investment Management LLC Sells 526,368 Shares of Diageo plc $DEO'))
  self.assertTrue(T.ist_routine('Relx Plc $RELX Stock Sold by First Eagle Investment Management LLC'))
  self.assertFalse(T.ist_routine('Apple beats earnings expectations'))
  self.assertEqual(T.themen_von('Nvidia rallies on AI demand'), ['ki'])
  self.assertEqual(T.themen_von('Kai Wang joins board'), [], 'KI/AI nur in Großbuchstaben')
  self.assertEqual(T.themen_von('Said Fund sells shares'), [])
  self.assertIn('blase', T.themen_von('Is the AI trade a bubble?'))
  self.assertIn('abnehmmittel', T.themen_von('Lilly GLP-1 sales surge'))
  self.assertEqual(T.themen_von('Big Fund Takes New Position in AI chip maker'), [], 'Routine zählt für kein Thema')

 def test_einstufen(self):
  self.assertEqual(T.einstufen(30, 5, 10)[0], 'offen')
  self.assertIn('10 von 21', T.einstufen(30, 5, 10)[1])
  self.assertEqual(T.einstufen(30, 5, 30, quelle_fehlt=True)[0], 'offen')
  self.assertEqual(T.einstufen(4, 1, 30)[0], 'wenig')
  self.assertEqual(T.einstufen(10, 0, 30)[0], 'neu')
  self.assertEqual(T.einstufen(10, 5, 30)[0], 'steigend')
  self.assertEqual(T.einstufen(10, 6, 30)[0], 'normal')
  self.assertEqual(T.einstufen(5, 10, 30)[0], 'fallend')
  self.assertIn('gekappt', T.einstufen(10, 5, 30, gekappt=True)[1])

 def test_name_und_aehnlichkeit(self):
  self.assertEqual(T.name_vor('Contrasting Kennametal (NYSE:KMT) & PACCAR (NASDAQ:PCAR)', 'NYSE', 'KMT'), 'Kennametal')
  self.assertEqual(T.name_vor('Contrasting Kennametal (NYSE:KMT) & PACCAR (NASDAQ:PCAR)', 'NASDAQ', 'PCAR'), 'PACCAR')
  self.assertEqual(T.name_vor('Burberry Group plc 2027 Q2 - Results - Earnings Call Presentation (OTCMKTS:BURBY) 2026-11-16', 'OTCMKTS', 'BURBY'), 'Burberry Group plc')
  self.assertTrue(T.aehnlich(T.namenskern('Merck KGaA'), T.namenskern('Merck & Co., Inc.')))
  self.assertFalse(T.aehnlich(T.namenskern('Johnson Matthey Plc'), T.namenskern('Johnson & Johnson')))


class Archiv(unittest.TestCase):
 def setUp(self):
  self.tmp = tempfile.TemporaryDirectory(); self.ordner = Path(self.tmp.name) / 'nachrichten_archiv'

 def tearDown(self):
  self.tmp.cleanup()

 def test_archiv_ergaenzt_nur_und_ist_deterministisch(self):
  c = company({'NASDAQ:AAPL': stock(['Apple A', 'Apple B'])})
  n1, _ = T.archivieren(self.ordner, c, market(['Fed holds rates']), JETZT)
  datei = T.tagesdatei(self.ordner, '2026-11-21'); roh = datei.read_bytes()
  n2, p = T.archivieren(self.ordner, c, market(['Fed holds rates']), JETZT)
  self.assertEqual((n1, n2), (3, 0)); self.assertEqual(datei.read_bytes(), roh, 'gleicher Inhalt → gleiche Bytes')
  self.assertEqual(p['tage']['2026-11-21']['laeufe'], 2)
  # Ein Tag später: neue Datei, alte bleibt unverändert, Duplikate werden nicht erneut abgelegt.
  c2 = company({'NASDAQ:AAPL': stock(['Apple A', 'Apple C'], jetzt=JETZT)})
  n3, _ = T.archivieren(self.ordner, c2, None, JETZT + dt.timedelta(days=1))
  self.assertEqual(n3, 1); self.assertEqual(datei.read_bytes(), roh)
  self.assertEqual(len(T.archiv_lesen(self.ordner)), 4)

 def test_zukunft_fehler_und_leere_quellen(self):
  c = company({'NASDAQ:AAPL': stock(['Zukunft'], tage_zurueck=-2), 'XETR:SAP': {'source': None, 'items': []}})
  n, p = T.archivieren(self.ordner, c, market(['x'], error='HTTP 403'), JETZT)
  self.assertEqual(n, 0); self.assertEqual(p['tage']['2026-11-21']['quellen'], ['u:ROIC'])

 def test_grundwert_im_aufbau_und_score_null(self):
  T.archivieren(self.ordner, company({'NASDAQ:AAPL': stock([f'Apple AI {i}' for i in range(8)], truncated=True)}), None, JETZT)
  e = T.auswerten(self.ordner, UNIVERSUM, JETZT)
  self.assertEqual(e['scoreContribution'], 0); self.assertEqual(e['method'], 'news_trends_v1')
  a = e['aktien'][0]
  self.assertEqual((a['symbol'], a['nennungen'], a['status'], a['verhaeltnis'], a['gekappt'], a['name']), ('NASDAQ:AAPL', 8, 'offen', None, True, 'Apple Inc.'))
  ki = next(t for t in e['themen'] if t['id'] == 'ki'); self.assertEqual((ki['nennungen'], ki['status']), (8, 'offen'))

 def _verlauf(self, tage, je_tag, quelle_spaet=None):
  """Simuliert tägliche Läufe: je Tag je_tag(tag) Schlagzeilen zu Apple, am Ende das Fenster."""
  for d in range(tage, -1, -1):
   jetzt = JETZT - dt.timedelta(days=d)
   n = je_tag(d)
   q = quelle_spaet if (quelle_spaet and d < 7) else 'ROIC'
   c = company({'NASDAQ:AAPL': stock([f'Apple AI news {d}-{i}' for i in range(n)], tage_zurueck=0.1, quelle=q, jetzt=jetzt)})
   T.archivieren(self.ordner, c, market([f'Markt {d}'], jetzt=jetzt), jetzt)

 def test_steigend_nach_grundwert(self):
  self._verlauf(40, lambda d: 4 if d < 7 else 1)   # Grundwert 7/Woche, Fenster 28
  e = T.auswerten(self.ordner, UNIVERSUM, JETZT)
  a = e['aktien'][0]
  self.assertGreaterEqual(e['archiv']['basisTage'], 21)
  self.assertEqual(a['status'], 'steigend'); self.assertAlmostEqual(a['verhaeltnis'], 4.0, delta=0.6)
  ki = next(t for t in e['themen'] if t['id'] == 'ki'); self.assertEqual(ki['status'], 'steigend')

 def test_quellenwechsel_bleibt_offen(self):
  self._verlauf(40, lambda d: 4 if d < 7 else 1, quelle_spaet='Google News · Suchindex')
  a = T.auswerten(self.ordner, UNIVERSUM, JETZT)['aktien'][0]
  self.assertEqual(a['status'], 'offen'); self.assertIn('Quelle', a['grund']); self.assertIsNone(a['verhaeltnis'])

 def test_neue_quelle_zaehlt_nicht_fuer_themenverhaeltnis(self):
  self._verlauf(40, lambda d: 1)
  T.archivieren(self.ordner, None, market([f'AI boom {i}' for i in range(20)], key='bloomberg'), JETZT)
  e = T.auswerten(self.ordner, UNIVERSUM, JETZT)
  self.assertNotIn('m:bloomberg', e['archiv']['stabileQuellen'])
  ki = next(t for t in e['themen'] if t['id'] == 'ki')
  self.assertEqual(ki['nennungen'] - ki['nennungenVergleichbar'], 20, 'neuer Feed sichtbar, aber nicht im Verhältnis')
  self.assertNotEqual(ki['status'], 'steigend')

 def test_kandidaten(self):
  titel = ['Contrasting Kennametal (NYSE:KMT) & Apple (NASDAQ:AAPL)',
           'British American Tobacco p.l.c. (NYSE:BTI) Stock Short Interest Rises',
           'Kennametal (NYSE:KMT) beats estimates',
           'Foo (XYZ:ABC) unbekannte Börse',
           'Kennametal (NYSE:KMT) Shares Sold by Big Fund LLC']
  T.archivieren(self.ordner, None, market(titel), JETZT)
  k = {x['kuerzel']: x for x in T.auswerten(self.ordner, UNIVERSUM, JETZT)['kandidaten']}
  self.assertNotIn('AAPL', k, 'Universumskürzel ist kein Kandidat'); self.assertNotIn('ABC', k, 'unbekannte Börse')
  self.assertEqual((k['KMT']['nennungen'], k['KMT']['identitaet'], k['KMT']['name'], k['KMT']['aehnlichImUniversum']), (2, 'ungeprueft', 'Kennametal', []), 'Routine zählt nicht')
  self.assertEqual(k['BTI']['aehnlichImUniversum'], ['LSE:BATS'])
  self.assertEqual(list(k)[0], 'KMT', 'mögliche Doppelungen stehen hinten')

 def test_main_schreibt_trends(self):
  daten = Path(self.tmp.name)
  (daten / 'cf_company_news.json').write_text(json.dumps(company({'NASDAQ:AAPL': stock(['Apple AI'])})))
  (daten / 'cf_universum.json').write_text(json.dumps(UNIVERSUM))
  T.main(daten, JETZT)
  e = json.loads((daten / 'cf_trends.json').read_text())
  self.assertEqual((e['schema'], e['archiv']['neuInDiesemLauf'], e['aktienGesamt']), (1, 1, 1))
  with self.assertRaises(SystemExit):
   T.main(Path(self.tmp.name) / 'leer', JETZT)

 def test_alle_aktien_ab_grenze_eine_schlagzeile(self):
  # Seit 23.11.2026 alle Aktien; ab SCHLAGZEILEN_VOLL nur noch die neueste Schlagzeile (Dateigröße).
  self.assertIsNone(T.MAX_AKTIEN)
  daten = Path(self.tmp.name)
  (daten / 'cf_company_news.json').write_text(json.dumps(company({'NASDAQ:AAPL': stock(['Apple AI one', 'Apple AI two', 'Apple AI three'])})))
  (daten / 'cf_universum.json').write_text(json.dumps(UNIVERSUM))
  alt = T.SCHLAGZEILEN_VOLL
  try:
   T.SCHLAGZEILEN_VOLL = 0
   T.main(daten, JETZT)
  finally:
   T.SCHLAGZEILEN_VOLL = alt
  e = json.loads((daten / 'cf_trends.json').read_text())
  self.assertEqual(len(e['aktien']), e['aktienGesamt'])
  self.assertTrue(all(len(a['schlagzeilen']) <= 1 for a in e['aktien']))


if __name__ == '__main__':
 unittest.main()
