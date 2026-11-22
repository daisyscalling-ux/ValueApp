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
   self.assertTrue(KO.passt(p, '2026-11', 10_000, 8000))
   usd = KO.buchen(p, '2026-11', 'a', 10_000, 1000); KO.buchen(p, '2026-11', 'b', 10_000, 1000)
   self.assertAlmostEqual(usd, 10_000 * 0.1 / 1e6 + 1000 * 0.5 / 1e6)
   m = json.loads(p.read_text())['monate']['2026-11']
   self.assertEqual((m['laeufe'], m['tokens']['ein'], sorted(m['funktionen'])), (2, 20_000, ['a', 'b']))
   m['usd'] = 0.999; p.write_text(json.dumps({'schema': 1, 'monate': {'2026-11': m}}))
   self.assertFalse(KO.passt(p, '2026-11', 10_000, 8000)); self.assertTrue(KO.passt(p, '2026-12', 10_000, 8000))


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
   (d / 'ki_kosten.json').write_text(json.dumps({'schema': 1, 'monate': {'2026-11': {'usd': 0.9999, 'laeufe': 1, 'funktionen': {}, 'tokens': {'ein': 0, 'aus': 0}}}}))
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
