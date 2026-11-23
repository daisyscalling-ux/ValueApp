"""Laufsperre für KI-Läufe (seit 23.11.2026, Entscheidung des Nutzers: Cloudflare startet die Läufe pünktlich).

Der Cloudflare-Worker stößt die Läufe zur geplanten Zeit an (workflow_dispatch). Der GitHub-Zeitplan bleibt als Rückfall,
falls der Worker ausfällt. Damit dabei kein zweiter, kostenpflichtiger KI-Aufruf entsteht, prüft ein geplanter Lauf
(LAUF_ANLASS=schedule), ob das Ergebnis schon frisch ist, und überspringt dann. Manuelle und vom Worker gestartete Läufe
(workflow_dispatch) laufen immer.
"""
import datetime as dt
import json
from pathlib import Path
from zoneinfo import ZoneInfo

BERLIN = ZoneInfo('Europe/Berlin')


def _zeit(pfad):
 try:
  t = dt.datetime.fromisoformat(json.loads(Path(pfad).read_text(encoding='utf8'))['generatedAt'])
  return t if t.tzinfo else None
 except (OSError, ValueError, KeyError, TypeError):
  return None


def schon_frisch(pfad, jetzt, anlass, *, stunden=None, gleicher_tag=False):
 """Grund zum Überspringen oder None. Nur bei anlass == 'schedule'; Zukunftsdaten zählen nicht als frisch."""
 if anlass != 'schedule':
  return None
 t = _zeit(pfad)
 if t is None or t > jetzt:
  return None
 if gleicher_tag and t.astimezone(BERLIN).date() == jetzt.astimezone(BERLIN).date():
  return f'heute ({t.astimezone(BERLIN):%d.%m. %H:%M}) schon erstellt'
 if stunden is not None and jetzt - t < dt.timedelta(hours=stunden):
  return f'vor weniger als {stunden} h ({t.astimezone(BERLIN):%d.%m. %H:%M}) erstellt'
 return None
