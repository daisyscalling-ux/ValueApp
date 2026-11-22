import datetime as dt
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ki_einordnung as K
import trends as T
import test_trends as TT

JETZT = TT.JETZT


class FakeClient:
 """Ersetzt die API: zählt Aufrufe, gibt eine vorgegebene Antwort zurück. Kein Netz."""
 def __init__(self, antwort, tokens=5000, stop='end_turn', ein=5000, aus=1500):
  self.antwort, self.tokens, self.stop, self.ein, self.aus, self.aufrufe = antwort, tokens, stop, ein, aus, []
  self.messages = SimpleNamespace(count_tokens=self._zaehlen, create=self._erstellen)
 def _zaehlen(self, **kw):
  return SimpleNamespace(input_tokens=self.tokens)
 def _erstellen(self, **kw):
  self.aufrufe.append(kw)
  return SimpleNamespace(stop_reason=self.stop, usage=SimpleNamespace(input_tokens=self.ein, output_tokens=self.aus),
                         content=[SimpleNamespace(type='thinking', thinking=''), SimpleNamespace(type='text', text=json.dumps(self.antwort))])


def daten_anlegen(tmp, n=30):
 daten = Path(tmp)
 weitere = {f'NYSE:S{k}': TT.stock([f'Firma {k} Meldung {i}' for i in range(3)], tage_zurueck=1) for k in range(n // 6)}
 c = TT.company({'NASDAQ:AAPL': TT.stock([f'Apple AI news {i}' for i in range(n)], tage_zurueck=1), 'XETR:SAP': TT.stock(['SAP cloud deal', 'SAP Shares Sold by Big Fund LLC'], tage_zurueck=1), **weitere})
 T.archivieren(daten / 'nachrichten_archiv', c, TT.market([f'Fed rate cut {i}' for i in range(10)]), JETZT)
 tr = T.auswerten(daten / 'nachrichten_archiv', TT.UNIVERSUM, JETZT)
 T.schreibe(daten / 'cf_trends.json', tr)
 return daten


GUT = {'themen': [{'titel': 'KI bei Apple', 'einordnung': 'Viele Meldungen zu KI.', 'tendenz': 'positiv', 'belege': ['h1', 'h11', 'h11', 'h999'], 'aktien': ['NASDAQ:AAPL', 'NYSE:FAKE', 'XETR:SAP']},
               {'titel': 'Erfunden', 'einordnung': 'ohne Beleg', 'tendenz': 'negativ', 'belege': ['h999'], 'aktien': []}],
       'neue_themen': [{'titel': 'Zinsen', 'einordnung': 'Fed', 'belege': ['h2']}], 'hinweis': 'ok'}


class Eingabe(unittest.TestCase):
 def test_auswahl_ohne_routine_deterministisch(self):
  with tempfile.TemporaryDirectory() as tmp:
   daten = daten_anlegen(tmp)
   tr = T.lies(daten / 'cf_trends.json', None)
   z1 = K.eingabe(daten / 'nachrichten_archiv', tr, JETZT); z2 = K.eingabe(daten / 'nachrichten_archiv', tr, JETZT)
   self.assertEqual(z1, z2)
   self.assertFalse(any('Sold by' in z['title'] for z in z1), 'Routine-Meldungen nicht an die KI')
   self.assertEqual(sum(1 for z in z1 if z.get('symbol') == 'NASDAQ:AAPL'), 3, 'höchstens 3 je Aktie')
   self.assertEqual([z['id'] for z in z1[:2]], ['h1', 'h2'])
   self.assertIn('<schlagzeilen>', K.nachricht(z1, tr))


class Pruefung(unittest.TestCase):
 def test_nur_belegte_aussagen(self):
  zeilen = [{'id': 'h1', 'title': 'Fed', 'url': 'https://x/1', 'publisher': 'FT', 'publishedAt': '2026-11-20', 'symbol': None},
            {'id': 'h2', 'title': 'Fed 2', 'url': 'https://x/2', 'publisher': 'FT', 'publishedAt': '2026-11-20', 'symbol': None},
            {'id': 'h11', 'title': 'Apple AI', 'url': 'https://x/11', 'publisher': 'Z', 'publishedAt': '2026-11-20', 'symbol': 'NASDAQ:AAPL'},
            {'id': 'h12', 'title': 'SAP', 'url': 'https://x/12', 'publisher': 'Z', 'publishedAt': '2026-11-20', 'symbol': 'XETR:SAP'}]
  themen, neue, hinweis, verworfen = K.pruefen(GUT, zeilen)
  self.assertEqual(len(themen), 1, 'Thema ohne gültigen Beleg fällt weg')
  self.assertEqual([b['url'] for b in themen[0]['belege']], ['https://x/1', 'https://x/11'], 'doppelte und unbekannte IDs fallen weg')
  self.assertEqual(themen[0]['aktien'], ['NASDAQ:AAPL'], 'erfundenes und nicht zitiertes Symbol fällt weg')
  self.assertEqual(verworfen, 1 + 2)
  self.assertEqual(len(neue), 1); self.assertEqual(hinweis, 'ok')
  lang = K.pruefen({'themen': [{'titel': 'x' * 500, 'einordnung': 'y' * 5000, 'tendenz': 'wild', 'belege': ['h1'], 'aktien': []}]}, zeilen)[0][0]
  self.assertEqual((len(lang['titel']), len(lang['einordnung']), lang['tendenz']), (80, 600, 'neutral'))


class Ablauf(unittest.TestCase):
 def test_erfolg_kosten_und_kennzeichnung(self):
  with tempfile.TemporaryDirectory() as tmp:
   daten = daten_anlegen(tmp)
   c = FakeClient(GUT)
   e, grund = K.ausfuehren(daten, c, JETZT)
   self.assertEqual(grund, '')
   self.assertEqual((e['method'], e['modell'], e['scoreContribution']), ('news_trends_ki_v1', 'claude-haiku-5-5', 0))
   self.assertIn('nicht geprüft', e['kennzeichnung'])
   self.assertAlmostEqual(e['kosten']['usd'], 5000 * 0.10 / 1e6 + 1500 * 0.50 / 1e6)
   kw = c.aufrufe[0]
   self.assertEqual(kw['model'], 'claude-haiku-5-5'); self.assertEqual(kw['output_config']['format']['type'], 'json_schema')
   self.assertNotIn('temperature', kw); self.assertNotIn('thinking', kw)
   k = json.loads((daten / 'ki_kosten.json').read_text())['monate']['2026-11']
   self.assertEqual((k['laeufe'], k['funktionen']['trends_einordnung']['laeufe']), (1, 1))

 def test_budget_alter_groesse_abbruch(self):
  with tempfile.TemporaryDirectory() as tmp:
   daten = daten_anlegen(tmp)
   T.schreibe(daten / 'ki_kosten.json', {'schema': 1, 'monate': {'2026-11': {'usd': 0.1, 'laeufe': 9, 'funktionen': {'trends_einordnung': {'usd': 0.0999, 'laeufe': 9}}, 'tokens': {'ein': 0, 'aus': 0}}}})
   c = FakeClient(GUT)
   self.assertIsNone(K.ausfuehren(daten, c, JETZT)[0]); self.assertEqual(c.aufrufe, [], 'kein Aufruf bei erschöpftem Budget')
   self.assertIn('Monatsbudget', K.ausfuehren(daten, c, JETZT)[1])
  with tempfile.TemporaryDirectory() as tmp:
   daten = daten_anlegen(tmp)
   self.assertIn('zu groß', K.ausfuehren(daten, FakeClient(GUT, tokens=200_000), JETZT)[1])
   self.assertIn('älter', K.ausfuehren(daten, FakeClient(GUT), JETZT + dt.timedelta(hours=40))[1])
   e, g = K.ausfuehren(daten, FakeClient(GUT, stop='refusal'), JETZT)
   self.assertIsNone(e); self.assertIn('refusal', g)
   self.assertEqual(json.loads((daten / 'ki_kosten.json').read_text())['monate']['2026-11']['laeufe'], 1, 'abgelehnte Antwort wird trotzdem gebucht')
   self.assertIn('Kein belegtes', K.ausfuehren(daten, FakeClient({'themen': [], 'neue_themen': [], 'hinweis': ''}), JETZT)[1])
  with tempfile.TemporaryDirectory() as tmp:
   daten = daten_anlegen(tmp, n=2)
   self.assertIn('Zu wenige', K.ausfuehren(daten, FakeClient(GUT), JETZT)[1])

 def test_ohne_schluessel_nichts(self):
  import os
  alt = os.environ.pop('ANTHROPIC_API_KEY', None)
  try:
   with tempfile.TemporaryDirectory() as tmp:
    self.assertEqual(K.main(Path(tmp), JETZT), 0); self.assertFalse((Path(tmp) / 'cf_trends_ki.json').exists())
  finally:
   if alt is not None:
    os.environ['ANTHROPIC_API_KEY'] = alt


if __name__ == '__main__':
 unittest.main()


class Kandidaten(unittest.TestCase):
 TR = {'kandidaten': [
  {'boerse': 'NYSE', 'kuerzel': 'KMT', 'name': 'Kennametal', 'identitaet': 'ungeprueft', 'aehnlichImUniversum': [], 'schlagzeilen': [{'title': 'Kennametal (NYSE:KMT) beats'}]},
  {'boerse': 'NYSE', 'kuerzel': 'BTI', 'name': 'BAT', 'identitaet': 'ungeprueft', 'aehnlichImUniversum': ['LSE:BATS'], 'schlagzeilen': [{'title': 'BAT (NYSE:BTI)'}]},
  {'boerse': 'NASDAQ', 'kuerzel': 'X', 'name': 'X', 'identitaet': 'geprueft', 'aehnlichImUniversum': [], 'schlagzeilen': [{'title': 'x'}]},
  {'boerse': 'NASDAQ', 'kuerzel': 'Y', 'name': 'Y', 'identitaet': 'ungeprueft', 'aehnlichImUniversum': [], 'schlagzeilen': []}]}

 def test_eingabe_nur_echte_kandidaten(self):
  k = K.kandidaten_eingabe(self.TR)
  self.assertEqual([(x['id'], x['kuerzel']) for x in k], [('k1', 'KMT')], 'ADR-Verdacht, falsche Kennzeichnung, ohne Schlagzeile: nicht an die KI')

 def test_pruefung(self):
  k = K.kandidaten_eingabe(self.TR)
  out, v = K.kandidaten_pruefen({'kandidaten': [{'id': 'k1', 'beschreibung': 'Werkzeughersteller.', 'anlass': 'Quartalszahlen.'},
                                                {'id': 'k1', 'beschreibung': 'doppelt', 'anlass': ''}, {'id': 'k9', 'beschreibung': 'erfunden', 'anlass': ''},
                                                {'id': 'k1', 'beschreibung': ' ', 'anlass': ''}]}, k)
  self.assertEqual(out, [{'boerse': 'NYSE', 'kuerzel': 'KMT', 'beschreibung': 'Werkzeughersteller.', 'anlass': 'Quartalszahlen.'}]); self.assertEqual(v, 3)

 def test_ablauf_mit_kandidaten(self):
  with tempfile.TemporaryDirectory() as tmp:
   daten = daten_anlegen(tmp)
   tr = T.lies(daten / 'cf_trends.json', None); tr['kandidaten'] = self.TR['kandidaten']; T.schreibe(daten / 'cf_trends.json', tr)
   c = FakeClient({**GUT, 'kandidaten': [{'id': 'k1', 'beschreibung': 'Werkzeughersteller.', 'anlass': 'Quartalszahlen.'}]})
   e, g = K.ausfuehren(daten, c, JETZT)
   self.assertEqual(g, ''); self.assertEqual(e['kandidaten'][0]['kuerzel'], 'KMT')
   self.assertIn('<kandidaten>', c.aufrufe[0]['messages'][0]['content']); self.assertIn('NYSE:KMT | Kennametal', c.aufrufe[0]['messages'][0]['content'])
   self.assertIn('kandidaten', K.SCHEMA['required'])
