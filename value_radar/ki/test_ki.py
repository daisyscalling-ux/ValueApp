import datetime as dt
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ereignisse as E
import kosten as KO

UTC = dt.timezone.utc
JETZT = dt.datetime(2026, 11, 22, 12, tzinfo=UTC)


class FakeClient:
 """Simulierte API: antwortet je Aufruf mit antworten[n] (Funktion des Stapeltexts). Kein Netz."""
 def __init__(self, antwort, stop='end_turn', tokens=3000):
  self.antwort, self.stop, self.tokens, self.aufrufe = antwort, stop, tokens, []
  self.messages = SimpleNamespace(count_tokens=lambda **kw: SimpleNamespace(input_tokens=self.tokens), create=self._create)
 def _create(self, **kw):
  self.aufrufe.append(kw)
  text = kw['messages'][0]['content']
  return SimpleNamespace(stop_reason=self.stop, usage=SimpleNamespace(input_tokens=self.tokens, output_tokens=400),
                         content=[SimpleNamespace(type='thinking'), SimpleNamespace(type='text', text=json.dumps(self.antwort(text)))])


def daten(tmp, n=3, tage=1):
 d = Path(tmp)
 items = [{'title': f'Acme cuts guidance {i}', 'url': f'https://ex.com/{i}', 'publisher': 'X', 'publishedAt': (JETZT - dt.timedelta(days=tage, minutes=i)).isoformat()} for i in range(n)]
 (d / 'cf_company_news.json').write_text(json.dumps({'schema': 1, 'stocks': {'NYSE:ACME': {'items': items}, 'NYSE:FREMD': {'items': items[:1]}}}))
 (d / 'cf_universum.json').write_text(json.dumps({'kandidaten': [{'listing_symbol': 'NYSE:ACME', 'name': 'Acme Corp'}]}))
 return d


def alle_negativ(text):
 ids = [z.split(' |')[0] for z in text.split('\n') if z.startswith('s')]
 return {'treffer': [{'id': i, 'einstufung': 'negatives_ereignis', 'kategorie': 'Ertrag/Prognose', 'begruendung': 'Prognose gesenkt.'} for i in ids]
                    + [{'id': 's999', 'einstufung': 'negatives_ereignis', 'kategorie': 'Ertrag/Prognose', 'begruendung': 'erfunden'},
                       {'id': ids[0], 'einstufung': 'negatives_ereignis', 'kategorie': 'Ertrag/Prognose', 'begruendung': 'doppelt'},
                       {'id': ids[0], 'einstufung': 'kaufen', 'kategorie': 'Ertrag/Prognose', 'begruendung': 'falsch'}]}


class Kosten(unittest.TestCase):
 def test_buchen_und_budget(self):
  with tempfile.TemporaryDirectory() as tmp:
   p = Path(tmp) / 'ki_kosten.json'
   self.assertTrue(KO.passt(p, '2026-11', 10_000, 8000, 'risiko_ereignisse'))
   self.assertFalse(KO.passt(p, '2026-11', 10_000, 8000, 'unbekannt'), 'unbekannte Funktion ohne Budget')
   usd = KO.buchen(p, '2026-11', 'risiko_ereignisse', 10_000, 1000); KO.buchen(p, '2026-11', 'ki_portfolio', 10_000, 1000)
   self.assertAlmostEqual(usd, 10_000 * 0.1 / 1e6 + 1000 * 0.5 / 1e6)
   m = json.loads(p.read_text())['monate']['2026-11']
   self.assertEqual((m['laeufe'], m['tokens']['ein'], sorted(m['funktionen'])), (2, 20_000, ['ki_portfolio', 'risiko_ereignisse']))
   # Anteil der Funktion erschöpft, die anderen laufen weiter
   m['funktionen']['risiko_ereignisse']['usd'] = 0.8999; m['usd'] = 0.9; p.write_text(json.dumps({'schema': 1, 'monate': {'2026-11': m}}))
   self.assertFalse(KO.passt(p, '2026-11', 10_000, 8000, 'risiko_ereignisse')); self.assertTrue(KO.passt(p, '2026-11', 10_000, 8000, 'ki_portfolio'))
   self.assertTrue(KO.passt(p, '2026-12', 10_000, 8000, 'risiko_ereignisse'), 'neuer Monat')
   m['usd'] = 2.3499; p.write_text(json.dumps({'schema': 1, 'monate': {'2026-11': m}}))
   self.assertFalse(KO.passt(p, '2026-11', 10_000, 8000, 'ki_portfolio'), 'Summe erschöpft')
   self.assertAlmostEqual(KO.KI_BUDGET_USD, 2.35)
   self.assertFalse(KO.passt(p, '2026-12', 1, 1, 'themen_des_tages'), 'abgelöste Funktion hat kein Budget mehr')


class Ereignisse(unittest.TestCase):
 def test_auswahl_nur_universum_fenster_dedupliziert(self):
  with tempfile.TemporaryDirectory() as tmp:
   d = daten(tmp, n=3)
   c = json.loads((d / 'cf_company_news.json').read_text()); u = json.loads((d / 'cf_universum.json').read_text())
   z = E.neue_schlagzeilen(c, u, set(), JETZT)
   self.assertEqual(len(z), 3); self.assertTrue(all(x['symbol'] == 'NYSE:ACME' and x['firma'] == 'Acme Corp' for x in z))
   self.assertEqual(len(E.neue_schlagzeilen(c, u, {z[0]['id']}, JETZT)), 2)
   self.assertEqual(E.neue_schlagzeilen(c, u, set(), JETZT + dt.timedelta(days=9)), [], 'außerhalb von 7 Tagen')

 def test_lauf_prueft_ids_und_merkt_sich_gepruefte(self):
  with tempfile.TemporaryDirectory() as tmp:
   d = daten(tmp, n=3)
   c = FakeClient(alle_negativ)
   e, g = E.ausfuehren(d, c, JETZT)
   self.assertEqual(g, ''); self.assertEqual(len(e['treffer']), 3); self.assertEqual(e['lauf']['verworfen'], 3, 'erfundene, doppelte, falsche Einstufung')
   self.assertEqual((e['scoreContribution'], e['method']), (0, 'risk_event_ki_v1')); self.assertIn('nicht geprüft', e['kennzeichnung'])
   kw = c.aufrufe[0]; self.assertEqual(kw['output_config']['effort'], 'low'); self.assertEqual(kw['model'], 'claude-haiku-5-5')
   (d / 'cf_risk_event_ki.json').write_text(json.dumps(e))
   c2 = FakeClient(alle_negativ)
   e2, g2 = E.ausfuehren(d, c2, JETZT + dt.timedelta(hours=1))
   self.assertEqual(c2.aufrufe, [], 'bereits geprüft: kein neuer Aufruf'); self.assertEqual(len(e2['treffer']), 3, 'Treffer bleiben')
   # Nach 8 Tagen fallen alte Treffer aus dem Fenster
   e3, _ = E.ausfuehren(d, FakeClient(alle_negativ), JETZT + dt.timedelta(days=8))
   self.assertEqual(e3['treffer'], [])

 def test_stapel_budget_abbruch(self):
  with tempfile.TemporaryDirectory() as tmp:
   d = daten(tmp, n=E.BATCH * E.MAX_AUFRUFE + 5)
   c = FakeClient(lambda t: {'treffer': []})
   e, g = E.ausfuehren(d, c, JETZT)
   self.assertEqual(len(c.aufrufe), E.MAX_AUFRUFE); self.assertIn('nächsten Lauf', g); self.assertEqual(len(e['geprueft']), E.BATCH * E.MAX_AUFRUFE)
  with tempfile.TemporaryDirectory() as tmp:
   d = daten(tmp, n=3)
   (d / 'ki_kosten.json').write_text(json.dumps({'schema': 1, 'monate': {'2026-11': {'usd': 0.9, 'laeufe': 1, 'funktionen': {'risiko_ereignisse': {'usd': 0.8999, 'laeufe': 1}}, 'tokens': {'ein': 0, 'aus': 0}}}}))
   c = FakeClient(alle_negativ); e, g = E.ausfuehren(d, c, JETZT)
   self.assertEqual(c.aufrufe, []); self.assertEqual(g, 'Monatsbudget erreicht'); self.assertEqual(e['treffer'], [], 'nichts geprüft, nichts behauptet')
  with tempfile.TemporaryDirectory() as tmp:
   d = daten(tmp, n=3)
   e, g = E.ausfuehren(d, FakeClient(alle_negativ, stop='max_tokens'), JETZT)
   self.assertIn('max_tokens', g); self.assertEqual(e['geprueft'], {}, 'unvollständiger Stapel wird wiederholt')
   self.assertEqual(json.loads((d / 'ki_kosten.json').read_text())['monate']['2026-11']['laeufe'], 1, 'trotzdem gebucht')
   e, g = E.ausfuehren(d, FakeClient(alle_negativ, tokens=200_000), JETZT)
   self.assertIn('zu groß', g)

 def test_ohne_schluessel_und_ohne_daten(self):
  alt = os.environ.pop('ANTHROPIC_API_KEY', None)
  try:
   with tempfile.TemporaryDirectory() as tmp:
    self.assertEqual(E.main(Path(tmp), JETZT), 0); self.assertFalse((Path(tmp) / 'cf_risk_event_ki.json').exists())
    self.assertEqual(E.ausfuehren(Path(tmp), FakeClient(alle_negativ), JETZT)[1], 'Nachrichten oder Universum fehlen')
  finally:
   if alt is not None:
    os.environ['ANTHROPIC_API_KEY'] = alt


if __name__ == '__main__':
 unittest.main()


import news_briefing as NB


def nb_daten(tmp, n_markt=8, n_europa=8, n_asien=8, n_welt=8):
 d = Path(tmp)
 def items(prefix, n, alt=True):
  out = [{'title': f'{prefix} story {i}', 'url': f'https://x.com/{prefix}{i}', 'publisher': 'Q', 'publishedAt': (JETZT - dt.timedelta(hours=1, minutes=i)).isoformat()} for i in range(n)]
  return out + ([{'title': 'alt', 'url': f'https://x.com/{prefix}alt', 'publishedAt': (JETZT - dt.timedelta(hours=30)).isoformat()}] if alt else [])
 (d / 'cf_news.json').write_text(json.dumps({'version': 1, 'sources': {'wsj': {'name': 'WSJ', 'items': items('US', n_markt)}, 'ft': {'name': 'FT', 'items': items('FT', 3)}}}))
 (d / 'cf_regional_news.json').write_text(json.dumps({'version': 1, 'sources': {'dw': {'name': 'DW', 'via': 'Europa · RSS', 'items': items('EU', n_europa)},
                                                                                'nikkei': {'name': 'Nikkei', 'via': 'Asien · RSS', 'items': items('AS', n_asien)}}}))
 (d / 'cf_world_news.json').write_text(json.dumps({'version': 1, 'sources': {'bbc': {'name': 'BBC', 'items': items('W', n_welt)}}}))
 akt = lambda s, n: [{'title': f'{s} meldet {i}', 'url': f'https://ex.com/{s}{i}', 'publisher': 'X', 'publishedAt': (JETZT - dt.timedelta(hours=3, minutes=i)).isoformat()} for i in range(n)]
 (d / 'cf_company_news.json').write_text(json.dumps({'schema': 1, 'stocks': {'NYSE:ACME': {'items': akt('ACME', 4) + [{'title': 'Acme Shares Sold by Big Fund LLC', 'url': 'https://ex.com/r', 'publishedAt': (JETZT - dt.timedelta(hours=1)).isoformat()}]},
                                                                             'XETR:SAP': {'items': akt('SAP', 3)}, 'TSE:7203': {'items': akt('TOYOTA', 3)}, 'NYSE:FREMD': {'items': akt('FREMD', 3)}}}))
 (d / 'cf_universum.json').write_text(json.dumps({'kandidaten': [{'listing_symbol': 'NYSE:ACME', 'country': 'US'}, {'listing_symbol': 'XETR:SAP', 'country': 'DE'}, {'listing_symbol': 'TSE:7203', 'country': 'JP'}]}))
 return d


def nb_antwort(text):
 # Flaches Format (seit 23.11.2026): aus der bisherigen Gliederung erzeugt, plus ein Punkt mit fremdem Abschnitt und eine doppelte Region.
 alt = nb_antwort_verschachtelt(text)
 regionen = [{'region': r, 'lage': v['lage'], 'punkte': [{**p, 'abschnitt': k} for k, ps in v.items() if k != 'lage' for p in ps]} for r, v in alt.items()]
 regionen[3]['punkte'].append({'abschnitt': 'maerkte', 'text': 'falscher Abschnitt', 'belege': ['w1'], 'aktien': []})
 regionen.append({'region': 'usa', 'lage': 'doppelt', 'punkte': []})
 return {'regionen': regionen}


def nb_antwort_verschachtelt(text):
 leer = {'maerkte': [], 'konjunktur': [], 'industrie': [], 'unternehmen': []}
 return {'usa': {**leer, 'lage': 'Ruhig.', 'maerkte': [{'text': 'Indizes.', 'belege': ['u1', 'u2', 'e1', 'u999'], 'aktien': ['NYSE:ACME']}],
                 'unternehmen': [{'text': 'Acme.', 'belege': ['u9'], 'aktien': ['NYSE:ACME', 'NYSE:FAKE']}, {'text': 'ohne', 'belege': [], 'aktien': []}]},
         'europa': {**leer, 'lage': 'EZB.', 'konjunktur': [{'text': 'Zinsen.', 'belege': ['e1'], 'aktien': []}]},
         'asien': {**leer, 'lage': 'Japan.', 'industrie': [{'text': 'Autos.', 'belege': ['a2'], 'aktien': []}]},
         'welt': {'lage': 'Wahl.', 'politik': [{'text': 'Wahl.', 'belege': ['w3'], 'aktien': []}], 'konjunktur': [], 'rohstoffe': []}}


class NewsBriefing(unittest.TestCase):
 def test_eingabe_regionen(self):
  with tempfile.TemporaryDirectory() as tmp:
   e = NB.eingabe(nb_daten(tmp), JETZT)
   self.assertEqual(len(e['usa']), 8 + 2, '8 WSJ (ohne FT, ohne alt) + ACME höchstens 2, ohne Routine')
   self.assertEqual(len(e['europa']), 8 + 3 + 2, 'DW + FT aus dem Marktfeed + SAP 2')
   self.assertEqual(len(e['asien']), 8 + 2); self.assertEqual(len(e['welt']), 8)
   self.assertFalse(any(z.get('symbol') == 'NYSE:FREMD' for v in e.values() for z in v), 'nicht im Universum')
   self.assertFalse(any('Sold by' in z['title'] for v in e.values() for z in v))
   self.assertEqual([e[r][0]['id'] for r in ('usa', 'europa', 'asien', 'welt')], ['u1', 'e1', 'a1', 'w1'])

 def test_ablauf_belege_je_region(self):
  with tempfile.TemporaryDirectory() as tmp:
   d = nb_daten(tmp); c = FakeClient(nb_antwort)
   r, g = NB.ausfuehren(d, c, JETZT)
   self.assertEqual(g, ''); us = r['regionen']['usa']['abschnitte']
   self.assertEqual(len(us['maerkte'][0]['belege']), 2, 'e1 gehört nicht zu USA, u999 gibt es nicht')
   self.assertEqual(us['maerkte'][0]['aktien'], [], 'Symbol ohne zitierte Aktien-Schlagzeile fällt weg')
   self.assertEqual(us['unternehmen'][0]['aktien'], ['NYSE:ACME'])
   self.assertEqual(r['verworfen'], 1 + 1 + 1 + 2, 'plus fremder Abschnitt (welt/maerkte) und doppelte Region')
   self.assertEqual(r['regionen']['welt']['abschnitte']['politik'][0]['text'], 'Wahl.')
   self.assertEqual((r['method'], r['scoreContribution']), ('news_briefing_ki_v1', 0)); self.assertIn('nicht geprüft', r['kennzeichnung'])
   self.assertEqual(r['gliederung']['welt']['abschnitte'][0], ['politik', 'Politik'])
   self.assertEqual(c.aufrufe[0]['output_config']['format']['type'], 'json_schema')
   self.assertEqual(list(c.aufrufe[0]['output_config']['format']['schema']['properties']), ['regionen'], 'flaches Schema')
   self.assertIn('news_briefing', json.loads((d / 'ki_kosten.json').read_text())['monate']['2026-11']['funktionen'])

 def test_offene_regionen_und_abbrueche(self):
  with tempfile.TemporaryDirectory() as tmp:
   d = nb_daten(tmp, n_asien=0)
   (d / 'cf_company_news.json').write_text(json.dumps({'schema': 1, 'stocks': {}}))
   r, g = NB.ausfuehren(d, FakeClient(nb_antwort), JETZT)
   self.assertEqual(r['regionen']['asien']['status'], 'offen'); self.assertIn('Zu wenige', r['regionen']['asien']['grund'])
   self.assertIn('<asien>\n\n</asien>', NB.nachricht(NB.eingabe(d, JETZT)))
  with tempfile.TemporaryDirectory() as tmp:
   d = nb_daten(tmp, 1, 1, 1, 1); (d / 'cf_company_news.json').write_text(json.dumps({'schema': 1, 'stocks': {}}))
   (d / 'cf_news.json').write_text(json.dumps({'version': 1, 'sources': {}}))
   self.assertIn('Zu wenige', NB.ausfuehren(d, FakeClient(nb_antwort), JETZT)[1])
  with tempfile.TemporaryDirectory() as tmp:
   d = nb_daten(tmp)
   self.assertIn('max_tokens', NB.ausfuehren(d, FakeClient(nb_antwort, stop='max_tokens'), JETZT)[1])
   KO.buchen(d / 'ki_kosten.json', '2026-11', 'news_briefing', 6_990_000, 0)
   c = FakeClient(nb_antwort); self.assertIn('Monatsbudget', NB.ausfuehren(d, c, JETZT)[1]); self.assertEqual(c.aufrufe, [])


class ApiFehler(unittest.TestCase):
 def test_meldung_der_api_im_protokoll(self):
  e = SimpleNamespace(status_code=400, body={'type': 'error', 'error': {'type': 'invalid_request_error', 'message': 'output_config.format.schema: too   complex'}})
  self.assertEqual(KO.api_fehler(e), 'API-Fehler 400 (invalid_request_error): output_config.format.schema: too complex')
  self.assertEqual(KO.api_fehler(SimpleNamespace(status_code=500, body=None, message='')), 'API-Fehler 500')
  self.assertEqual(len(KO.api_fehler(SimpleNamespace(status_code=400, body={'error': {'message': 'x' * 999}}))), len('API-Fehler 400: ') + 300)
