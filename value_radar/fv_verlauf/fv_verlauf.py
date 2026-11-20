"""Taeglicher Fair-Value-Verlauf je Titel (seit 20.11.2026, Wunsch des Nutzers).

Vorher entstand der Verlauf nur, wenn die Einzelanalyse geoeffnet wurde (KV-Speicher der App). Jetzt legt die Pipeline
nach jedem precompute je Titel einen Tagespunkt ab: Fair Value, Kurs, Verlaesslichkeit, Modell und Methodenstand.

Datei je Notierung: daten/fv_verlauf/<listing_symbol, bereinigt>.json mit inputIdentity (listing_symbol, isin, currency).
- Ein Punkt je Kalendertag (Tag des Universumsstands); ein spaeterer Lauf am selben Tag ersetzt nichts.
- Herkunft je Tag (Universumsdatei, Commit, sha256, Methodenstand) in _quellen.json, nicht je Punkt.
- Passt ISIN oder Waehrung nicht zur Datei, wird der Punkt verworfen und gezaehlt (Identitaet vor Inhalt).
- Offener Fair Value (Bewertung gesperrt oder ohne Methode) wird als Punkt mit fv null und Grund abgelegt, nie als 0.
- Methodenstand m: sha256 (12 Zeichen) von risk_precompute/app-copies.json, also des Rechenwegs der App, den der Scanner
  ausfuehrt. Vor dem 13.11.2026 (Python-Scanner) "python". Die App markiert Punkte, an denen m wechselt: Eine Aenderung
  dort kann aus der Methode kommen, nicht aus dem Unternehmen.
"""
import argparse, datetime as dt, hashlib, json, re, subprocess
from pathlib import Path

METHODE = 'fv_daily_log_v1'
BASIS = Path(__file__).resolve().parents[1]
ORDNER = BASIS / 'daten' / 'fv_verlauf'
UNIVERSUM_REL = 'value_radar/daten/cf_universum.json'
KOPIEN_REL = 'value_radar/risk_precompute/app-copies.json'


def zahl(x):
    return x if isinstance(x, (int, float)) and not isinstance(x, bool) and x == x and abs(x) != float('inf') else None


def dateiname(sym):
    return re.sub(r'[^A-Za-z0-9._-]', '_', sym) + '.json'


def tag_von(stand):
    m = re.match(r'(\d{4}-\d{2}-\d{2})', str(stand or ''))
    return m.group(1) if m else None


def methodenstand(roh):
    return hashlib.sha256(roh).hexdigest()[:12] if roh else 'python'


def punkt(r, tag, m):
    fv, p = zahl(r.get('fair_value')), zahl(r.get('price'))
    if p is None or p <= 0:
        return None
    pk = {'d': tag, 'fv': round(fv, 4) if fv and fv > 0 else None, 'kurs': round(p, 4), 'm': m}
    if pk['fv'] is None:
        pk['grund'] = 'Daten prüfen' if r.get('kauf_urteil') == 'Daten prüfen' else 'Fair Value offen'
    if r.get('fv_reliable') is not None:
        pk['verl'] = bool(r.get('fv_reliable'))
    if r.get('playbook'):
        pk['modell'] = r.get('playbook')
    return pk


def eintragen(doc, quelle, m, ordner=ORDNER, puffer=None, quellen=None):
    """Universumsstand -> Punkte in die Titeldateien. Rueckgabe: Zaehler."""
    tag = tag_von(doc.get('stand'))
    if not tag:
        raise ValueError('Universum ohne gueltigen Stand')
    z = {'neu': 0, 'tag_vorhanden': 0, 'identitaet_abweichend': 0, 'ohne_kurs': 0}
    puffer = {} if puffer is None else puffer
    for r in doc.get('kandidaten') or []:
        sym = r.get('listing_symbol')
        if not isinstance(sym, str) or ':' not in sym:
            continue
        pk = punkt(r, tag, m)
        if pk is None:
            z['ohne_kurs'] += 1
            continue
        pfad = ordner / dateiname(sym)
        d = puffer.get(sym)
        if d is None:
            d = json.loads(pfad.read_text(encoding='utf-8')) if pfad.exists() else {
                'schema': 1, 'method': METHODE, 'inputIdentity': {'listing_symbol': sym, 'isin': r.get('isin'), 'currency': r.get('currency')},
                'name': r.get('name'), 'punkte': []}
            puffer[sym] = d
        ident = d['inputIdentity']
        if ident.get('isin') != r.get('isin') or ident.get('currency') != r.get('currency'):
            z['identitaet_abweichend'] += 1
            continue
        if any(x['d'] == tag for x in d['punkte']):
            z['tag_vorhanden'] += 1
            continue
        d['punkte'].append(pk)
        if quellen is not None:
            quellen.setdefault(tag, {**quelle, 'm': m})
        d['punkte'].sort(key=lambda x: x['d'])
        z['neu'] += 1
    return z


def schreiben(puffer, ordner=ORDNER, quellen=None):
    """Titeldateien und die Herkunft je Tag (_quellen.json: Universumsdatei, Commit, sha256, Methodenstand)."""
    ordner.mkdir(parents=True, exist_ok=True)
    if quellen:
        qp = ordner / '_quellen.json'
        alt = json.loads(qp.read_text(encoding='utf-8')) if qp.exists() else {'schema': 1, 'method': METHODE, 'tage': {}}
        for tag, q in quellen.items():
            alt['tage'].setdefault(tag, q)
        alt['tage'] = dict(sorted(alt['tage'].items()))
        qp.write_text(json.dumps(alt, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    for sym, d in puffer.items():
        d['aktualisiert'] = dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')
        (ordner / dateiname(sym)).write_text(json.dumps(d, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')


def git(*a, text=True):
    return subprocess.run(['git', *a], capture_output=True, text=text, check=True).stdout


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('befehl', choices=['eintragen', 'rekonstruieren'])
    a = ap.parse_args(argv)
    puffer, quellen = {}, {}
    if a.befehl == 'eintragen':
        roh = (BASIS / 'daten' / 'cf_universum.json').read_bytes()
        kop = BASIS / 'risk_precompute' / 'app-copies.json'
        z = eintragen(json.loads(roh), {'pfad': UNIVERSUM_REL, 'sha256': hashlib.sha256(roh).hexdigest()[:16]},
                      methodenstand(kop.read_bytes() if kop.exists() else None), puffer=puffer, quellen=quellen)
        schreiben(puffer, quellen=quellen)
        print(f'[fv-verlauf] {z}')
        return
    # Einmalig: Staende aus der Git-Historie, neuester zuerst. So gilt die Identitaet des neuesten Stands; aeltere Punkte
    # mit anderer ISIN oder Waehrung fallen weg (gezaehlt). Je Kalendertag zaehlt hier der letzte Stand des Tages.
    commits = git('log', '--format=%H', '--', UNIVERSUM_REL).split()
    gesamt = {'neu': 0, 'staende': 0, 'identitaet_abweichend': 0}
    for c in commits:
        try:
            roh = git('show', f'{c}:{UNIVERSUM_REL}', text=False)
            doc = json.loads(roh)
        except (subprocess.CalledProcessError, ValueError):
            continue
        try:
            kop = git('show', f'{c}:{KOPIEN_REL}', text=False)
        except subprocess.CalledProcessError:
            kop = None
        z = eintragen(doc, {'pfad': UNIVERSUM_REL, 'commit': c[:12], 'sha256': hashlib.sha256(roh).hexdigest()[:16]}, methodenstand(kop), puffer=puffer, quellen=quellen)
        gesamt['neu'] += z['neu']
        gesamt['identitaet_abweichend'] += z['identitaet_abweichend']
        gesamt['staende'] += 1 if z['neu'] else 0
    schreiben(puffer, quellen=quellen)
    print(f'[fv-verlauf] rekonstruiert: {gesamt} aus {len(commits)} Commits, {len(puffer)} Titel')


if __name__ == '__main__':
    main()
