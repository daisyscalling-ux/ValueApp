import datetime as dt
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import laufwache as LW

UTC = dt.timezone.utc


class Laufwache(unittest.TestCase):
 def datei(self, tmp, t):
  p = Path(tmp) / 'x.json'
  p.write_text(json.dumps({'generatedAt': t}))
  return p

 def test_nur_geplante_laeufe(self):
  with tempfile.TemporaryDirectory() as tmp:
   p = self.datei(tmp, '2026-11-23T08:05:00+00:00')
   jetzt = dt.datetime(2026, 11, 23, 9, 0, tzinfo=UTC)
   self.assertIsNone(LW.schon_frisch(p, jetzt, 'workflow_dispatch', gleicher_tag=True))
   self.assertIsNone(LW.schon_frisch(p, jetzt, '', stunden=4))
   self.assertIn('heute', LW.schon_frisch(p, jetzt, 'schedule', gleicher_tag=True))
   self.assertIn('4 h', LW.schon_frisch(p, jetzt, 'schedule', stunden=4))

 def test_berliner_datum(self):
  with tempfile.TemporaryDirectory() as tmp:
   # 23:30 UTC am 22.11. = 00:30 Berlin am 23.11.: gleicher Berliner Tag wie 09:00 Berlin am 23.11.
   p = self.datei(tmp, '2026-11-22T23:30:00+00:00')
   self.assertIsNotNone(LW.schon_frisch(p, dt.datetime(2026, 11, 23, 8, 0, tzinfo=UTC), 'schedule', gleicher_tag=True))
   # 22:30 UTC am 22.11. = 23:30 Berlin am 22.11.: Vortag -> nicht frisch
   p = self.datei(tmp, '2026-11-22T22:30:00+00:00')
   self.assertIsNone(LW.schon_frisch(p, dt.datetime(2026, 11, 23, 8, 0, tzinfo=UTC), 'schedule', gleicher_tag=True))

 def test_alt_fehlend_kaputt_zukunft(self):
  jetzt = dt.datetime(2026, 11, 23, 9, 0, tzinfo=UTC)
  with tempfile.TemporaryDirectory() as tmp:
   self.assertIsNone(LW.schon_frisch(self.datei(tmp, '2026-11-23T04:00:00+00:00'), jetzt, 'schedule', stunden=4))
   self.assertIsNone(LW.schon_frisch(Path(tmp) / 'fehlt.json', jetzt, 'schedule', stunden=4))
   self.assertIsNone(LW.schon_frisch(self.datei(tmp, 'kein Datum'), jetzt, 'schedule', stunden=4))
   self.assertIsNone(LW.schon_frisch(self.datei(tmp, '2026-11-23T08:00:00'), jetzt, 'schedule', stunden=4), 'ohne Zeitzone')
   self.assertIsNone(LW.schon_frisch(self.datei(tmp, '2026-11-23T10:00:00+00:00'), jetzt, 'schedule', stunden=4), 'Zukunft')


if __name__ == '__main__':
 unittest.main()
