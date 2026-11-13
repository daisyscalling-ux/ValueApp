"""Gleichlauf der App-Kopien (Arbeitsstandard: Kopien aus valueapp-cf muessen identisch bleiben).

app-copies.json listet jede Kopie mit Pfad in der App, Pfad in der Pipeline und SHA-256 des App-Originals.
- pruefen():   Pipeline-Kopien gegen die Liste (Test test_app_copies.py, Workflows daily-risk und precompute-3tage).
- abgleichen(): lokal mit einem valueapp-cf-Checkout: Kopien aktualisieren und Liste neu schreiben.
Die App prueft ihre Originale in npm test gegen dieselbe, oeffentlich abrufbare Liste (tests/pipeline-copies.test.mjs).
Erlaubte Abweichung je Eintrag: 'normalize' (Paare Pipeline-Text -> App-Text), nur fuer Importpfade.
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LISTE = Path(__file__).with_name('app-copies.json')


def _sha(b):
    return hashlib.sha256(b).hexdigest()


def _normalisiert(text, paare):
    for von, nach in paare or []:
        text = text.replace(von, nach)
    return text


def pruefen(liste=None):
    """Liste der Abweichungen (leer = alles identisch)."""
    daten = json.loads((liste or LISTE).read_text(encoding='utf-8'))
    fehler = []
    for e in daten['files']:
        p = ROOT / e['pipeline']
        if not p.exists():
            fehler.append(e['pipeline'] + ': fehlt')
            continue
        inhalt = _normalisiert(p.read_text(encoding='utf-8'), e.get('normalize'))
        if _sha(inhalt.encode('utf-8')) != e['sha256']:
            fehler.append(e['pipeline'] + ': weicht von ' + e['app'] + ' ab')
    return fehler


def abgleichen(cf_root):
    """Kopien aus einem valueapp-cf-Checkout uebernehmen und die Liste neu schreiben."""
    cf_root = Path(cf_root)
    daten = json.loads(LISTE.read_text(encoding='utf-8'))
    for e in daten['files']:
        app = (cf_root / e['app']).read_text(encoding='utf-8')
        rueck = app
        for von, nach in e.get('normalize') or []:
            rueck = rueck.replace(nach, von)
        (ROOT / e['pipeline']).write_text(rueck, encoding='utf-8')
        e['sha256'] = _sha(app.encode('utf-8'))
    LISTE.write_text(json.dumps(daten, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    return len(daten['files'])


if __name__ == '__main__':
    if len(sys.argv) > 2 and sys.argv[1] == 'abgleichen':
        print(abgleichen(sys.argv[2]), 'Dateien abgeglichen')
    else:
        f = pruefen()
        print('\n'.join(f) or 'Alle App-Kopien identisch')
        sys.exit(1 if f else 0)
