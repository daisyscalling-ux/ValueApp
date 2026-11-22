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
   m['usd'] = 1.5999; p.write_text(json.dumps({'schema': 1, 'monate': {'2026-11': m}}))
   self.assertFalse(KO.passt(p, '2026-11', 10_000, 8000, 'ki_portfolio'), 'Summe erschöpft')
   self.assertAlmostEqual(KO.KI_BUDGET_USD, 1.60)


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


import themen_des_tages as TD


def tag_daten(tmp, n_markt=8, n_welt=8, n_akt=8):
 d = Path(tmp)
 def feed(prefix, n):
  return {'version': 1, 'sources': {'q': {'name': 'Q', 'items': [{'title': f'{prefix} story {i}', 'url': f'https://x.com/{prefix}{i}', 'publisher': 'Q',
                                                                  'publishedAt': (JETZT - dt.timedelta(hours=1, minutes=i)).isoformat()} for i in range(n)]
                                          + [{'title': 'alt', 'url': 'https://x.com/alt', 'publishedAt': (JETZT - dt.timedelta(hours=30)).isoformat()}]}}}
 (d / 'cf_news.json').write_text(json.dumps(feed('Markt', n_markt)))
 (d / 'cf_world_news.json').write_text(json.dumps(feed('Welt', n_welt)))
 items = [{'title': f'Acme news {i}', 'url': f'https://ex.com/a{i}', 'publisher': 'X', 'publishedAt': (JETZT - dt.timedelta(hours=2, minutes=i)).isoformat()} for i in range(n_akt)]
 items.append({'title': 'Acme Shares Sold by Big Fund LLC', 'url': 'https://ex.com/r', 'publisher': 'X', 'publishedAt': (JETZT - dt.timedelta(hours=1)).isoformat()})
 weitere = {f'NYSE:X{k}': {'items': [{**items[k % len(items)], 'title': f'X{k} meldet {j}', 'url': f'https://ex.com/x{k}{j}', 'publishedAt': (JETZT - dt.timedelta(hours=5, minutes=k)).isoformat()} for j in range(2)]} for k in range(3 if n_akt >= 5 else 0)}
 (d / 'cf_company_news.json').write_text(json.dumps({'schema': 1, 'stocks': {'NYSE:ACME': {'items': items}, **weitere}}))
 return d


def tag_antwort(text):
 return {'markt': {'lage': 'Ruhig.', 'punkte': [{'text': 'Zinsen.', 'belege': ['m1', 'm2', 'a1', 'm999'], 'aktien': ['NYSE:ACME']}, {'text': 'ohne Beleg', 'belege': ['m999'], 'aktien': []}]},
         'aktien': {'lage': 'Acme im Fokus.', 'punkte': [{'text': 'Acme meldet.', 'belege': ['a1'], 'aktien': ['NYSE:ACME', 'NYSE:FAKE']}]},
         'welt': {'lage': 'Wahl.', 'punkte': [{'text': 'Wahl.', 'belege': ['w3'], 'aktien': []}]}}


class ThemenDesTages(unittest.TestCase):
 def test_eingabe(self):
  with tempfile.TemporaryDirectory() as tmp:
   e = TD.eingabe(tag_daten(tmp), JETZT)
   self.assertEqual((len(e['markt']), len(e['welt'])), (8, 8), 'älter als 24 h fällt weg')
   self.assertEqual(sum(1 for z in e['aktien'] if z['symbol'] == 'NYSE:ACME'), 2, 'höchstens 2 je Titel')
   self.assertFalse(any('Sold by' in z['title'] for z in e['aktien']), 'keine Routine-Meldungen')
   self.assertEqual(e['markt'][0]['id'], 'm1'); self.assertEqual(e['welt'][0]['id'], 'w1')

 def test_ablauf_belege_je_abschnitt(self):
  with tempfile.TemporaryDirectory() as tmp:
   d = tag_daten(tmp)
   c = FakeClient(tag_antwort)
   r, g = TD.ausfuehren(d, c, JETZT)
   self.assertEqual(g, ''); ab = r['abschnitte']
   self.assertEqual([len(b['belege']) for b in ab['markt']['punkte']], [2], 'a1 gehört nicht zum Markt, m999 gibt es nicht')
   self.assertEqual(ab['markt']['punkte'][0]['aktien'], [], 'Symbol ohne zitierte Aktien-Schlagzeile fällt weg')
   self.assertEqual(ab['aktien']['punkte'][0]['aktien'], ['NYSE:ACME'])
   self.assertEqual(r['verworfen'], 1 + 1 + 1)
   self.assertEqual((r['method'], r['scoreContribution']), ('daily_topics_ki_v1', 0)); self.assertIn('nicht geprüft', r['kennzeichnung'])
   self.assertEqual(c.aufrufe[0]['output_config']['format']['type'], 'json_schema')
   self.assertIn('themen_des_tages', json.loads((d / 'ki_kosten.json').read_text())['monate']['2026-11']['funktionen'])

 def test_offene_abschnitte_und_abbrueche(self):
  with tempfile.TemporaryDirectory() as tmp:
   d = tag_daten(tmp, n_welt=2)
   r, g = TD.ausfuehren(d, FakeClient(tag_antwort), JETZT)
   self.assertEqual(r['abschnitte']['welt']['status'], 'offen'); self.assertIn('Zu wenige', r['abschnitte']['welt']['grund'])
   self.assertIn('<welt>\n\n</welt>', TD.nachricht(TD.eingabe(d, JETZT)), 'zu kleiner Abschnitt geht leer an die KI')
  with tempfile.TemporaryDirectory() as tmp:
   d = tag_daten(tmp, 1, 1, 1)
   self.assertIn('Zu wenige', TD.ausfuehren(d, FakeClient(tag_antwort), JETZT)[1])
  with tempfile.TemporaryDirectory() as tmp:
   d = tag_daten(tmp)
   self.assertIn('max_tokens', TD.ausfuehren(d, FakeClient(tag_antwort, stop='max_tokens'), JETZT)[1])
   KO.buchen(d / 'ki_kosten.json', '2026-11', 'themen_des_tages', 1_999_000, 0)
   c = FakeClient(tag_antwort); self.assertIn('Monatsbudget', TD.ausfuehren(d, c, JETZT)[1]); self.assertEqual(c.aufrufe, [])
