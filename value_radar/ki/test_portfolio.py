import datetime as dt
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))
import portfolio as P
import kosten as KO

UTC = dt.timezone.utc
T0 = dt.datetime(2026, 11, 24, 5, tzinfo=UTC)   # Dienstag, Kurse vom Montag


def zeile(sym, kurs, tag, waehrung='USD', sektor='Tech', **x):
 return {'listing_symbol': sym, 'name': sym.split(':')[1] + ' Inc', 'price': kurs, 'price_day': tag, 'price_kind': 'schluss', 'price_kind_method': 'exchange_close_v1',
         'currency': waehrung, 'sector': sektor, 'fair_value': kurs * 1.3, 'upside': 30, 'fv_reliable': True, 'composite': 70, 'momentum': 60, 'quality': 70, 'pe': 20,
         'revenue_growth': 8, 'kauf_urteil': 'kauf', **x}


class Welt:
 def __init__(self, tmp):
  self.d = Path(tmp)
  (self.d / 'cf_ecb_fx.json').write_text(json.dumps({'base': 'EUR', 'quoteConvention': 'currency_units_per_EUR', 'rates': {'2026-11-20': {'USD': 1.10, 'JPY': 170.0}, '2026-11-23': {'USD': 1.0, 'JPY': 160.0}}}))
  self.kurse('2026-11-23', {'NYSE:AAA': 100, 'NYSE:BBB': 50, 'TSE:7203': 3000, 'NYSE:CCC': 20})

 def kurse(self, tag, preise, sektoren=None):
  rows = [zeile(s, p, tag, 'JPY' if s.startswith('TSE') else 'USD', (sektoren or {}).get(s, 'Tech' if s != 'TSE:7203' else 'Auto')) for s, p in preise.items()]
  rows.append(zeile('NYSE:ALT', 10, '2026-11-01'))          # veraltet
  rows.append({**zeile('NYSE:UNG', 10, tag), 'price_kind': 'unbekannt'})   # ungeprüft
  (self.d / 'cf_universum.json').write_text(json.dumps({'kandidaten': rows}))

 def depot(self):
  return json.loads((self.d / 'ki_portfolio' / 'depot.json').read_text())

 def journal(self):
  p = self.d / 'ki_portfolio' / 'journal'
  return [json.loads(z) for f in sorted(p.glob('*.jsonl')) for z in f.read_text().splitlines()] if p.exists() else []


class FakeClient:
 """Simulierte API mit zwei Stufen: Auswahl (Schema mit „kandidaten“) und Entscheidung. Kein Netz."""
 def __init__(self, entscheidungen, stop='end_turn', tokens=70_000, roh=None, kandidaten=None):
  self.e, self.stop, self.tokens, self.roh, self.k, self.aufrufe = entscheidungen, stop, tokens, roh, kandidaten, []
  self.messages = SimpleNamespace(count_tokens=lambda **kw: SimpleNamespace(input_tokens=self.tokens), create=self._c)
 def _c(self, **kw):
  self.aufrufe.append(kw)
  auswahl = 'kandidaten' in kw['output_config']['format']['schema']['properties']
  if self.roh is not None:
   text = self.roh
  elif auswahl:
   text = json.dumps({'kandidaten': self.k if self.k is not None else [e['symbol'] for e in self.e if e.get('aktion') == 'kaufen']})
  else:
   text = json.dumps({'marktsicht': 'gemischt', 'entscheidungen': self.e})
  return SimpleNamespace(stop_reason=self.stop, usage=SimpleNamespace(input_tokens=self.tokens, output_tokens=3000), content=[SimpleNamespace(type='thinking'), SimpleNamespace(type='text', text=text)])


def kauf(s, anteil=0.10, aktion='kaufen'):
 return {'aktion': aktion, 'symbol': s, 'anteil': anteil, 'these': 'These ' + s, 'begruendung': 'Grund ' + s}


class Grundregeln(unittest.TestCase):
 def test_kauf_am_naechsten_schlusskurs_mit_gebuehr_und_ganzen_stueck(self):
  with tempfile.TemporaryDirectory() as tmp:
   w = Welt(tmp)
   r = P.lauf(w.d, FakeClient([kauf('NYSE:AAA'), kauf('TSE:7203', 0.05)]), T0)
   d = w.depot()
   self.assertEqual(d['cash_eur'], 50_000); self.assertEqual(len(d['auftraege']), 2, 'heute nur beschlossen')
   self.assertEqual(r['ki']['entscheidungen'], 2); self.assertIn('Simulation', d['stand']['kennzeichnung']); self.assertEqual(d['stand']['scoreContribution'], 0)
   # Gleicher Schlusskurs (Wochenende): keine Ausführung
   P.lauf(w.d, FakeClient([]), T0 + dt.timedelta(days=1))
   self.assertEqual(len(w.depot()['auftraege']), 2)
   # Neuer Schlusskurs: Ausführung zu 110 statt 100
   w.kurse('2026-11-25', {'NYSE:AAA': 110, 'NYSE:BBB': 50, 'TSE:7203': 3200, 'NYSE:CCC': 20})
   P.lauf(w.d, FakeClient([]), T0 + dt.timedelta(days=2))
   d = w.depot(); a = d['positionen']['NYSE:AAA']; t = d['positionen']['TSE:7203']
   self.assertEqual(a['stueck'], 45, '10 % von 50.000 € = 5.000 USD (Kurs 1,0) / 110 → 45 Stück')
   self.assertAlmostEqual(a['einstand_eur'], 110 * 1.001)
   self.assertEqual(t['stueck'], 124, 'Depotwert nach AAA-Kauf (−Gebühr) × 5 % × 160 / 3.200 = 124,98 → 124'); self.assertEqual(t['waehrung'], 'JPY')
   kosten = 45 * 110 * 1.001 + 124 * 3200 / 160 * 1.001
   self.assertAlmostEqual(d['cash_eur'], 50_000 - kosten, places=4)
   arten = [e['art'] for e in w.journal()]
   self.assertEqual(arten.count('kauf'), 2); self.assertEqual(arten.count('auftrag'), 2)

 def test_stop_loss_take_profit_und_einstand_stop_ohne_ki(self):
  with tempfile.TemporaryDirectory() as tmp:
   w = Welt(tmp)
   P.lauf(w.d, FakeClient([kauf('NYSE:AAA', 0.12), kauf('NYSE:BBB', 0.12)]), T0)
   w.kurse('2026-11-25', {'NYSE:AAA': 100, 'NYSE:BBB': 50, 'TSE:7203': 3000, 'NYSE:CCC': 20})
   P.lauf(w.d, None, T0 + dt.timedelta(days=2))
   self.assertEqual(sorted(w.depot()['positionen']), ['NYSE:AAA', 'NYSE:BBB'])
   # AAA −16 % → Stop-Loss; BBB +36 % → Hälfte verkauft, tp_erreicht
   w.kurse('2026-11-26', {'NYSE:AAA': 84, 'NYSE:BBB': 68, 'TSE:7203': 3000, 'NYSE:CCC': 20})
   P.lauf(w.d, None, T0 + dt.timedelta(days=3))
   d = w.depot()
   self.assertNotIn('NYSE:AAA', d['positionen']); self.assertTrue(d['positionen']['NYSE:BBB']['tp_erreicht']); self.assertEqual(d['positionen']['NYSE:BBB']['stueck'], 60)
   self.assertEqual(d['stand']['ki_grund'], 'Kein API-Schlüssel')
   # Rest fällt auf Einstand → verkauft
   w.kurse('2026-11-27', {'NYSE:AAA': 84, 'NYSE:BBB': 49.9, 'TSE:7203': 3000, 'NYSE:CCC': 20})
   P.lauf(w.d, None, T0 + dt.timedelta(days=4))
   self.assertEqual(w.depot()['positionen'], {})
   gruende = [e['grund'] for e in w.journal() if e['art'] == 'verkauf']
   self.assertTrue(gruende[0].startswith('Stop-Loss')); self.assertTrue(gruende[1].startswith('Take-Profit')); self.assertTrue(gruende[2].startswith('Stop beim Einstand'))
   self.assertEqual([v['datum'] for v in w.depot()['verlauf']], ['2026-11-24', '2026-11-26', '2026-11-27', '2026-11-28'])

 def test_nachkauf_nur_unter_einstand_und_durchschnitt(self):
  with tempfile.TemporaryDirectory() as tmp:
   w = Welt(tmp)
   P.lauf(w.d, FakeClient([kauf('NYSE:AAA', 0.05)]), T0)
   w.kurse('2026-11-25', {'NYSE:AAA': 100, 'NYSE:BBB': 50, 'TSE:7203': 3000, 'NYSE:CCC': 20})
   P.lauf(w.d, FakeClient([kauf('NYSE:AAA', 0.05, 'nachkaufen')]), T0 + dt.timedelta(days=2))   # beschlossen bei 100 = Einstand
   w.kurse('2026-11-26', {'NYSE:AAA': 101, 'NYSE:BBB': 50, 'TSE:7203': 3000, 'NYSE:CCC': 20})
   P.lauf(w.d, FakeClient([kauf('NYSE:AAA', 0.05, 'nachkaufen')]), T0 + dt.timedelta(days=3))
   self.assertEqual(w.depot()['positionen']['NYSE:AAA']['stueck'], 25, 'über Einstand: kein Nachkauf')
   self.assertIn('Nachkauf nur unter Einstand', [e.get('grund') for e in w.journal()])
   w.kurse('2026-11-27', {'NYSE:AAA': 90, 'NYSE:BBB': 50, 'TSE:7203': 3000, 'NYSE:CCC': 20})
   P.lauf(w.d, FakeClient([]), T0 + dt.timedelta(days=4))
   p = w.depot()['positionen']['NYSE:AAA']
   self.assertGreater(p['stueck'], 25); self.assertAlmostEqual(p['einstand_lokal'], (25 * 100 + (p['stueck'] - 25) * 90) / p['stueck'])

 def test_grenzen_titel_branche_cash_anzahl(self):
  with tempfile.TemporaryDirectory() as tmp:
   w = Welt(tmp)
   preise = {f'NYSE:T{i}': 10 for i in range(12)}
   w.kurse('2026-11-23', preise, {s: ('Bank' if i < 4 else f'S{i}') for i, s in enumerate(preise)})
   P.lauf(w.d, FakeClient([kauf(s, 0.12 if i < 4 else 0.05) for i, s in enumerate(preise)]), T0)
   w.kurse('2026-11-25', preise, {s: ('Bank' if i < 4 else f'S{i}') for i, s in enumerate(preise)})
   P.lauf(w.d, FakeClient([]), T0 + dt.timedelta(days=2))
   d = w.depot(); wert = d['verlauf'][-1]['wert_eur']
   self.assertLessEqual(len(d['positionen']), 10)
   bank = sum(p['stueck'] * 10 for p in d['positionen'].values() if p['branche'] == 'Bank')
   self.assertLessEqual(bank, 0.30 * 50_000 + 1, 'Branche höchstens 30 %')
   self.assertTrue(all(p['stueck'] * 10 <= 0.12 * 50_000 + 1 for p in d['positionen'].values()))
   self.assertGreaterEqual(d['cash_eur'], 0.05 * wert - 1, 'mindestens 5 % Cash')
   gruende = ' '.join(str(e.get('grund')) for e in w.journal())
   self.assertIn('Branchengrenze', gruende); self.assertIn('höchstens 10 Positionen', gruende)


class Wechselkurs(unittest.TestCase):
 def test_ohne_ezb_kurs_warten_dann_verfallen(self):
  with tempfile.TemporaryDirectory() as tmp:
   w = Welt(tmp)
   P.lauf(w.d, FakeClient([kauf('NYSE:AAA')]), T0)
   (w.d / 'cf_ecb_fx.json').write_text(json.dumps({'base': 'EUR', 'quoteConvention': 'currency_units_per_EUR', 'rates': {'2026-11-01': {'USD': 1.1}}}))
   for i, tag in enumerate(['2026-11-25', '2026-11-26', '2026-11-27']):
    w.kurse(tag, {'NYSE:AAA': 100, 'NYSE:BBB': 50, 'TSE:7203': 3000, 'NYSE:CCC': 20})
    P.lauf(w.d, None, T0 + dt.timedelta(days=2 + i))
    self.assertEqual(len(w.depot()['auftraege']), 0 if i == 2 else 1, 'wartet zwei Läufe, verfällt im dritten')
   self.assertEqual(w.depot()['positionen'], {}); self.assertIn('verfallen', [e['art'] for e in w.journal()])
   self.assertEqual(w.depot()['verlauf'][-1]['wert_eur'], 50_000, 'Cash in EUR braucht keinen Kurs')


class Waechter(unittest.TestCase):
 def test_zu_grosse_auswahl_wird_nach_composite_gekuerzt(self):
  # Seit 23.11.2026: Liste über PROMPT_MAX_TOKENS -> schwächste Viertel weg, statt den ganzen Lauf ausfallen zu lassen.
  with tempfile.TemporaryDirectory() as tmp:
   w = Welt(tmp)
   w.kurse('2026-11-20', {'NYSE:AAA': 100, 'NYSE:BBB': 50, 'TSE:7203': 3000, 'NYSE:CCC': 20})
   c = FakeClient([kauf('NYSE:AAA')])
   zaehl = []
   def count(**kw):
    t = kw['messages'][0]['content']; zaehl.append(t)
    return SimpleNamespace(input_tokens=95_000 if '<universum>' in t and t.count('NYSE:') + t.count('TSE:') > 3 else 60_000)
   c.messages.count_tokens = count
   P.lauf(w.d, c, dt.datetime(2026, 11, 24, 5, tzinfo=UTC))
   st = w.depot()['stand']
   self.assertIsNotNone(st['ki'], st.get('ki_grund'))
   self.assertEqual(st['ki']['auswahl_gekuerzt_auf'], 3)
   self.assertEqual(len(w.depot()['auftraege']), 1)

 def test_liste_ohne_kurs_und_fair_value(self):
  u = {'kandidaten': [{**zeile('NYSE:Z', 10, '2026-11-23'), 'composite': 80, 'kauf_urteil': 'beobachten', 'fair_value': 12.34}]}
  t = P.universum_text(u, P.kurse(u, T0.date()))
  self.assertNotIn('12.34', t); self.assertTrue(t.rstrip().endswith('|beob'))
  self.assertEqual(len(P.universum_text(u, P.kurse(u, T0.date()), max_zeilen=0).split('\n')), 1)


class Sortierung(unittest.TestCase):
 def test_nach_composite_mit_region(self):
  u = {'kandidaten': [{**zeile('ATHEX:A', 10, '2026-11-23', 'EUR'), 'composite': 50, 'country': 'GR'}, {**zeile('NYSE:Z', 10, '2026-11-23'), 'composite': 90, 'country': 'US'},
                      {**zeile('TSE:9', 10, '2026-11-23', 'JPY'), 'composite': None, 'country': 'JP'}, {**zeile('LSE:M', 10, '2026-11-23', 'GBP'), 'composite': 70, 'country': 'GB'}]}
  k = P.kurse(u, T0.date())
  zeilen = P.universum_text(u, k).split('\n')
  self.assertEqual([z.split('|')[0] for z in zeilen[1:]], ['NYSE:Z', 'LSE:M', 'ATHEX:A', 'TSE:9'], 'Composite absteigend, ohne Composite am Ende')
  self.assertEqual([z.split('|')[2] for z in zeilen[1:]], ['USA', 'GB', 'Europa', 'Japan'])
  self.assertIn('Region', zeilen[0])

 def test_zahlen_ohne_abgeschnittene_nullen(self):
  self.assertEqual([P._f(80, 0), P._f(100, 0), P._f(0, 0), P._f(20.0, 1), P._f(12.50, 2), P._f(100.0, 2), P._f(-30, 1), P._f(None), P._f(float('nan')), P._f(True)],
                   ['80', '100', '0', '20', '12.5', '100', '-30', '', '', ''])
  u = {'kandidaten': [{**zeile('NYSE:Z', 10, '2026-11-23'), 'composite': 80, 'momentum': 90, 'quality': 70}]}
  self.assertIn('|80|90|70|', P.universum_text(u, P.kurse(u, T0.date())))

 def test_storno_des_ersten_tages(self):
  with tempfile.TemporaryDirectory() as tmp:
   w = Welt(tmp)
   w.kurse('2026-11-20', {'NYSE:AAA': 100, 'NYSE:BBB': 50, 'TSE:7203': 3000, 'NYSE:CCC': 20})
   P.lauf(w.d, FakeClient([kauf('NYSE:AAA')]), dt.datetime(2026, 11, 22, 16, tzinfo=UTC))
   self.assertEqual(len(w.depot()['auftraege']), 1)
   w.kurse('2026-11-25', {'NYSE:AAA': 100, 'NYSE:BBB': 50, 'TSE:7203': 3000, 'NYSE:CCC': 20})
   P.lauf(w.d, FakeClient([]), T0 + dt.timedelta(days=2))
   self.assertEqual(w.depot()['positionen'], {}, 'stornierter Auftrag wird nicht ausgeführt')
   st = [e for e in w.journal() if e['art'] == 'storniert']
   self.assertEqual(len(st), 1); self.assertIn('Verzerrte Eingabe', st[0]['grund'])


class KiAntworten(unittest.TestCase):
 def test_pruefung_der_entscheidungen(self):
  with tempfile.TemporaryDirectory() as tmp:
   w = Welt(tmp)
   e = [kauf('NYSE:XXX'), kauf('NYSE:ALT'), kauf('NYSE:UNG'), kauf('NYSE:AAA', 0.5), kauf('NYSE:BBB', 0.1, 'verkaufen'), kauf('NYSE:CCC', 0.1, 'nachkaufen'),
        {**kauf('NYSE:AAA'), 'aktion': 'shorten'}, kauf('NYSE:CCC', 0.03), kauf('NYSE:CCC', 0.03)]
   r = P.lauf(w.d, FakeClient(e), T0)
   self.assertEqual(r['ki']['entscheidungen'], 1); self.assertEqual(r['ki']['verworfen'], 8)
   gruende = [x['grund'] for x in w.journal() if x['art'] == 'verworfen']
   for g in ('kein geprüfter Kurs im Universum', 'Anteil außerhalb 0,5–12 %', 'nicht im Depot', 'unbekannte Aktion', 'doppelt'):
    self.assertIn(g, gruende)

 def test_budget_groesse_unlesbar_unvollstaendig(self):
  with tempfile.TemporaryDirectory() as tmp:
   w = Welt(tmp)
   KO.buchen(w.d / 'ki_kosten.json', '2026-11', 'ki_portfolio', 5_490_000, 0)
   c = FakeClient([kauf('NYSE:AAA')]); r = P.lauf(w.d, c, T0)
   self.assertEqual(c.aufrufe, []); self.assertIn('Monatsbudget', r['ki_grund']); self.assertEqual(len(w.depot()['verlauf']), 1, 'Bewertung läuft trotzdem')
  for client, text in ((FakeClient([], tokens=95_000), 'zu groß'), (FakeClient([], roh='kein json'), 'nicht lesbar'), (FakeClient([kauf('NYSE:AAA')], stop='max_tokens'), 'unvollständig')):
   with tempfile.TemporaryDirectory() as tmp:
    w = Welt(tmp); r = P.lauf(w.d, client, T0)
    self.assertIn(text, r['ki_grund']); self.assertEqual(w.depot()['auftraege'], [])

 def test_eingabe_und_aufruf(self):
  with tempfile.TemporaryDirectory() as tmp:
   w = Welt(tmp); c = FakeClient([])
   P.lauf(w.d, c, T0)
   kw = c.aufrufe[0]; text = kw['messages'][0]['content']
   self.assertEqual(kw['model'], 'claude-haiku-5-5'); self.assertEqual(kw['output_config']['format']['type'], 'json_schema')
   self.assertIn('<universum>', text); self.assertIn('NYSE:AAA|AAA Inc', text); self.assertNotIn('NYSE:ALT', text, 'veralteter Kurs nicht im Angebot'); self.assertNotIn('NYSE:UNG', text)
   self.assertIn('Bilanz|Ziel12M%|VT|Vol%|Urteil', text); self.assertNotIn('FairValue', text)
   self.assertEqual(len(c.aufrufe), 1, 'ohne Kandidaten und Positionen keine zweite Stufe')
   self.assertEqual(P.lauf(w.d, c, T0)['grund'], 'Heute schon gelaufen'); self.assertEqual(len(c.aufrufe), 1)

 def test_zwei_stufen_datenblatt_und_vorauswahl(self):
  with tempfile.TemporaryDirectory() as tmp:
   w = Welt(tmp)
   (w.d / 'cf_risk.json').write_text(json.dumps({'stocks': {'NYSE:AAA': {'statistics': {'vol': 0.32, 'dd': 0.4, 'drawdown': 0.1}}}}))
   c = FakeClient([kauf('NYSE:AAA'), kauf('NYSE:BBB')], kandidaten=['NYSE:AAA', 'NYSE:XXX'])
   r = P.lauf(w.d, c, T0)
   self.assertEqual(len(c.aufrufe), 2); a1, a2 = c.aufrufe
   self.assertEqual((a1['output_config']['effort'], a2['output_config']['effort']), ('low', 'medium'))
   t2 = a2['messages'][0]['content']
   self.assertIn('<datenblaetter>', t2); self.assertIn('Scores: Composite 70', t2); self.assertIn('Volatilität 32 %', t2); self.assertIn('größter Rückgang 40 %', t2)
   self.assertNotIn('NYSE:BBB ·', t2, 'nur Kandidaten und Positionen im Datenblatt'); self.assertNotIn('<universum>', t2)
   self.assertEqual(r['ki']['kandidaten'], ['NYSE:AAA'], 'unbekanntes Symbol fällt aus der Vorauswahl')
   self.assertEqual(r['ki']['entscheidungen'], 1)
   self.assertIn('nicht in der Vorauswahl', [e.get('grund') for e in w.journal() if e['art'] == 'verworfen'])
   self.assertAlmostEqual(r['ki']['usd'], 2 * (70_000 * 0.1 / 1e6 + 3000 * 0.5 / 1e6))

 def test_fremdes_format_und_ohne_kurse(self):
  with tempfile.TemporaryDirectory() as tmp:
   w = Welt(tmp)
   (w.d / 'ki_portfolio').mkdir(); (w.d / 'ki_portfolio' / 'depot.json').write_text(json.dumps({'method': 'x'}))
   with self.assertRaises(ValueError):
    P.lauf(w.d, None, T0)
  with tempfile.TemporaryDirectory() as tmp:
   w = Welt(tmp)
   with self.assertRaises(ValueError):
    P.lauf(w.d, None, T0 + dt.timedelta(days=30))


if __name__ == '__main__':
 unittest.main()
