"""Größere Änderungen im Universum (universe_changes_v1, seit 25.11.2026, Wunsch und Schwellen des Nutzers).

Nach jedem precompute-3tage vergleicht dieses Skript die Universumszeilen mit dem letzten gespeicherten Stand
(daten/aenderungen/stand.json) und schreibt die größeren Änderungen der letzten FENSTER_TAGE Tage nach
daten/cf_aenderungen.json. Die App zeigt sie auf der Startseite.

Schwellen (Entscheidung des Nutzers): Fair Value ±10 %, 12M-Ziel ±10 %, Composite ±10 Punkte, Quantum ±10 Punkte,
dazu Wechsel zwischen Wert und offen. Gemessen am 24./25.11.2026: 37 bzw. 55 Titel je Tag (am 24.11. mit Methodenänderungen).

Grund (automatisch, Entscheidung des Nutzers; mehrere möglich, nie geraten):
- neuer_abschluss: Jahresabschluss-Stichtag geändert; Quelle, Veröffentlichung und Accession aus der Ergänzungsdatei.
- neuer_konsens: Prognose-EPS ±5 % oder Status/Methode der Prognose geändert, oder Analystenziel ±5 %.
- phase / modell: Unternehmensphase oder Bewertungsmodell gewechselt.
- methode: Rechenweg geändert (Fingerabdruck der App-Kopien), mit Link auf den Vergleich der Commits.
- daten: Gewinn oder Buchwert je Aktie ±5 % ohne neuen Abschluss, oder Aktienbasis geändert (Korrektur, Nachlieferung).
- kernmethoden: andere Methoden im Kern des Fair Value (Plausibilitäts- und Median-Filter); sonst methodenwert: eine Methode ±10 %.
- ziel_teil: welcher Teil des 12M-Ziels sich um ±10 % bewegt hat; kategorie: Teilscores mit ±10 Punkten (Composite/Quantum).
- kurs: Kurs ±10 % (wirkt auf 12M-Ziel, Analysten-Anker und Deckel).
- Sonst „unbekannt“: Grund nicht erkannt.
Nur Kontext: scoreContribution 0, kein Kauf- oder Verkaufssignal.
"""
import datetime as dt
import hashlib
import json
import math
import os
import re
import sys
from pathlib import Path

METHOD = 'universe_changes_v1'
FENSTER_TAGE = 7
SCHWELLE_REL = 0.10           # Fair Value und 12M-Ziel
SCHWELLE_PUNKTE = 10          # Composite und Quantum
KONSENS_REL = 0.05
KURS_REL = 0.10
MAX_EINTRAEGE_TAG = 300
REPO = 'daisyscalling-ux/ValueApp'
FELDER = ('name', 'price', 'fair_value', 'target_12m', 'composite', 'quantum', 'kauf_urteil', 'lifecycle_phase', 'playbook',
          'supplement_annual_end', 'eps_forward', 'eps_forward_method', 'eps_forward_status', 'target_mean', 'isin', 'currency',
          'eps_trailing', 'book_value_ps', 'share_count_basis', 'market_cap')
KATEGORIEN = {'value': 'Bewertung', 'quality': 'Qualität', 'momentum': 'Momentum', 'growth': 'Wachstum', 'health': 'Bilanz', 'catalyst': 'Katalysator'}
ZIEL_TEILE = {'fundamental': 'fundamentaler Teil', 'analyst': 'Analystenteil', 'momentum': 'Momentumteil'}
DATEN_REL = 0.05              # Gewinn je Aktie, Buchwert je Aktie, Aktienzahl
NAMEN = {'dcf': 'DCF', 'justified_pe': 'begründetes KGV', 'ev_ebitda': 'EV/EBITDA', 'analyst': 'Analystenziel', 'pb': 'Kurs/Buchwert',
         'epv': 'Ertragskraft', 'fwd_pe': 'Forward-KGV', 'fwd_composite': 'Forward-Mix', 'hist_pe': 'historisches KGV', 'fallback': 'Ersatzwert'}
UTC = dt.timezone.utc


def _zahl(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _lies(p):
    try:
        return json.loads(Path(p).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None


def _datei(sym):
    return re.sub(r'[^A-Za-z0-9._-]', '_', sym) + '.json'


def methoden_fingerabdruck(app_copies):
    """sha256 über die Prüfsummen der App-Kopien (Rechenweg); None ohne Liste."""
    if not isinstance(app_copies, dict) or not isinstance(app_copies.get('files'), list):
        return None
    teile = sorted(f"{e.get('app')}:{e.get('sha256')}" for e in app_copies['files'])
    return hashlib.sha256('\n'.join(teile).encode()).hexdigest()


def schnappschuss(universum, fingerabdruck, commit, jetzt):
    zeilen = {}
    for r in (universum or {}).get('kandidaten', []):
        s = r.get('listing_symbol')
        if isinstance(s, str) and s:
            fm = ((r.get('score_diagnostics') or {}).get('fv_methods') or {})
            zeilen[s] = {**{k: r.get(k) for k in FELDER}, 'kern': sorted((fm.get('core') or {}).keys()), 'methoden': fm.get('values') or {},
                         'ziel': (r.get('score_diagnostics') or {}).get('target') or {}, 'kategorien': {k: r.get(k) for k in KATEGORIEN}}
    return {'schema': 1, 'method': METHOD, 'erstellt': jetzt.isoformat(), 'universumStand': (universum or {}).get('stand'),
            'methode': fingerabdruck, 'commit': commit, 'zeilen': zeilen}


def _rel(a, b):
    return b / a - 1 if _zahl(a) and _zahl(b) and a > 0 and b > 0 else None


def aenderungen_messen(alt, neu):
    """Liste der Kennzahlen, die die Schwellen überschreiten: [{kennzahl, alt, neu, rel|diff}]."""
    out = []
    for k in ('fair_value', 'target_12m'):
        a, b = alt.get(k), neu.get(k)
        r = _rel(a, b)
        if r is not None and abs(r) >= SCHWELLE_REL - 1e-9:   # Toleranz für Rundung (90/100 − 1)
            out.append({'kennzahl': k, 'alt': a, 'neu': b, 'rel': round(r, 4)})
        elif (_zahl(a) and a > 0) != (_zahl(b) and b > 0):
            out.append({'kennzahl': k, 'alt': a if _zahl(a) else None, 'neu': b if _zahl(b) else None, 'rel': None})
    for k in ('composite', 'quantum'):
        a, b = alt.get(k), neu.get(k)
        if _zahl(a) and _zahl(b) and abs(b - a) >= SCHWELLE_PUNKTE - 1e-9:
            out.append({'kennzahl': k, 'alt': a, 'neu': b, 'diff': round(b - a, 1)})
    return out


def gruende(sym, alt, neu, methode_alt, methode_neu, commit_alt, commit_neu, fundamentals):
    g = []
    if alt.get('supplement_annual_end') != neu.get('supplement_annual_end') and neu.get('supplement_annual_end'):
        a = (fundamentals or {}).get('annual') or {}
        quelle = None
        if a.get('end') and str(a['end'])[:10] == str(neu['supplement_annual_end'])[:10] and isinstance(a.get('source_url'), str) and a['source_url'].startswith('https://'):
            quelle = {'url': a['source_url'], 'name': str(a.get('source') or '')[:80], 'veroeffentlicht': a.get('published_at'), 'accession': a.get('accession')}
        g.append({'art': 'neuer_abschluss', 'text': f"Neuer Jahresabschluss: Geschäftsjahr bis {neu['supplement_annual_end']} (vorher {alt.get('supplement_annual_end') or 'keiner'})",
                  'quelle': quelle})
    ra, rt = _rel(alt.get('eps_forward'), neu.get('eps_forward')), _rel(alt.get('target_mean'), neu.get('target_mean'))
    konsens = (ra is not None and abs(ra) >= KONSENS_REL) or alt.get('eps_forward_status') != neu.get('eps_forward_status') \
        or alt.get('eps_forward_method') != neu.get('eps_forward_method') or (rt is not None and abs(rt) >= KONSENS_REL) \
        or (_zahl(alt.get('eps_forward')) != _zahl(neu.get('eps_forward')))
    if konsens:
        teile = []
        if _zahl(alt.get('eps_forward')) or _zahl(neu.get('eps_forward')):
            teile.append(f"Prognose-EPS {alt.get('eps_forward') if _zahl(alt.get('eps_forward')) else 'offen'} → {neu.get('eps_forward') if _zahl(neu.get('eps_forward')) else 'offen'}")
        if rt is not None and abs(rt) >= KONSENS_REL:
            teile.append(f"Analystenziel {alt['target_mean']} → {neu['target_mean']}")
        g.append({'art': 'neuer_konsens', 'text': 'Analystenkonsens geändert' + (': ' + '; '.join(teile) if teile else ''),
                  'quelle': {'url': f"https://finance.yahoo.com/quote/{sym.split(':')[-1]}/analysis/", 'name': 'Yahoo Finance · Analysten', 'veroeffentlicht': None, 'accession': None}})
    if alt.get('lifecycle_phase') != neu.get('lifecycle_phase'):
        g.append({'art': 'phase', 'text': f"Unternehmensphase {alt.get('lifecycle_phase') or 'offen'} → {neu.get('lifecycle_phase') or 'offen'}", 'quelle': None})
    if alt.get('playbook') != neu.get('playbook'):
        g.append({'art': 'modell', 'text': f"Bewertungsmodell {alt.get('playbook')} → {neu.get('playbook')}", 'quelle': None})
    if methode_alt and methode_neu and methode_alt != methode_neu:
        url = f'https://github.com/{REPO}/compare/{commit_alt}...{commit_neu}' if commit_alt and commit_neu else None
        g.append({'art': 'methode', 'text': 'Rechenweg geändert (neue Bewertungsregeln in der Pipeline)',
                  'quelle': {'url': url, 'name': 'Änderungen im Code', 'veroeffentlicht': None, 'accession': None} if url else None})
    # Rohdaten des Abschlusses oder der Aktienbasis geändert (ohne neuen Stichtag): Korrektur oder Nachlieferung.
    daten = []
    for k, name in (('eps_trailing', 'Gewinn je Aktie'), ('book_value_ps', 'Buchwert je Aktie')):
        r = _rel(alt.get(k), neu.get(k))
        if r is not None and abs(r) >= DATEN_REL and alt.get('supplement_annual_end') == neu.get('supplement_annual_end'):
            daten.append(f"{name} {alt[k]} → {neu[k]}")
    if alt.get('share_count_basis') != neu.get('share_count_basis'):
        daten.append(f"Aktienbasis {alt.get('share_count_basis') or 'Notierung'} → {neu.get('share_count_basis') or 'Notierung'}")
    if daten:
        g.append({'art': 'daten', 'text': 'Daten geändert: ' + '; '.join(daten), 'quelle': None})
    # Kernmethoden des Fair Value gewechselt (Plausibilitäts- und Median-Filter): häufigste Ursache bei kleinen Kursbewegungen.
    ka, kn = set(alt.get('kern') or []), set(neu.get('kern') or [])
    if ka and kn and ka != kn:
        teile = [f"+ {NAMEN.get(m, m)}" for m in sorted(kn - ka)] + [f"− {NAMEN.get(m, m)}" for m in sorted(ka - kn)]
        g.append({'art': 'kernmethoden', 'text': 'Methoden im Fair Value gewechselt: ' + ', '.join(teile) + ' (Werte mehr als Faktor 2 vom Median oder außerhalb 0,25–4 × Kurs zählen nicht)', 'quelle': None})
    else:
        ma, mn = alt.get('methoden') or {}, neu.get('methoden') or {}
        gross = [(m, ma[m], mn[m]) for m in sorted(set(ma) & set(mn)) if _rel(ma[m], mn[m]) is not None and abs(_rel(ma[m], mn[m])) >= SCHWELLE_REL]
        if gross:
            g.append({'art': 'methodenwert', 'text': 'Methodenwert geändert: ' + '; '.join(f"{NAMEN.get(m, m)} {a} → {b}" for m, a, b in gross), 'quelle': None})
    # 12M-Ziel: welcher Teil sich bewegt hat (fundamental = KGV-Band und Weg zum Fair Value, Analysten, Momentum).
    za, zn = alt.get('ziel') or {}, neu.get('ziel') or {}
    zt = [(k, za[k], zn[k]) for k in ZIEL_TEILE if _rel(za.get(k), zn.get(k)) is not None and abs(_rel(za[k], zn[k])) >= SCHWELLE_REL]
    if zt and any(w['kennzahl'] == 'target_12m' for w in aenderungen_messen(alt, neu)):
        g.append({'art': 'ziel_teil', 'text': '12M-Ziel: ' + '; '.join(f"{ZIEL_TEILE[k]} {round(a, 2)} → {round(b, 2)}" for k, a, b in zt), 'quelle': None})
    # Composite/Quantum: Kategorien mit der größten Bewegung.
    ca, cn = alt.get('kategorien') or {}, neu.get('kategorien') or {}
    kt = sorted(((k, ca[k], cn[k]) for k in KATEGORIEN if _zahl(ca.get(k)) and _zahl(cn.get(k)) and abs(cn[k] - ca[k]) >= SCHWELLE_PUNKTE), key=lambda x: -abs(x[2] - x[1]))
    if kt and any(w['kennzahl'] in ('composite', 'quantum') for w in aenderungen_messen(alt, neu)):
        g.append({'art': 'kategorie', 'text': 'Teilscores: ' + '; '.join(f"{KATEGORIEN[k]} {round(a)} → {round(b)}" for k, a, b in kt[:3]), 'quelle': None})
    rk = _rel(alt.get('price'), neu.get('price'))
    if rk is not None and abs(rk) >= KURS_REL:
        g.append({'art': 'kurs', 'text': f"Kurs {round(rk * 100, 1):+} % ({alt['price']} → {neu['price']})", 'quelle': None})
    if not g:
        g.append({'art': 'unbekannt', 'text': 'Grund nicht erkannt', 'quelle': None})
    return g


def vergleichen(stand_alt, stand_neu, fund_lesen, tag):
    eintraege = []
    za, zn = (stand_alt or {}).get('zeilen') or {}, stand_neu['zeilen']
    for s in sorted(zn):
        if s not in za:
            continue
        a, n = za[s], zn[s]
        if a.get('isin') != n.get('isin') or a.get('currency') != n.get('currency'):
            continue   # andere Notierung oder Währung: nicht vergleichbar
        werte = aenderungen_messen(a, n)
        if not werte:
            continue
        eintraege.append({'tag': tag, 'symbol': s, 'name': str(n.get('name') or s)[:80], 'kurs': n.get('price'), 'waehrung': n.get('currency'),
                          'urteil': {'alt': a.get('kauf_urteil'), 'neu': n.get('kauf_urteil')}, 'werte': werte,
                          'gruende': gruende(s, a, n, stand_alt.get('methode'), stand_neu.get('methode'), stand_alt.get('commit'), stand_neu.get('commit'), fund_lesen(s))})
    eintraege.sort(key=lambda e: -max(abs(w.get('rel') or 0) * 100 if 'rel' in w else abs(w.get('diff') or 0) for w in e['werte']))
    return eintraege[:MAX_EINTRAEGE_TAG]


def lauf(daten, jetzt=None, commit=None):
    jetzt = jetzt or dt.datetime.now(UTC)
    daten = Path(daten)
    universum = _lies(daten / 'cf_universum.json')
    if not universum or not universum.get('kandidaten'):
        print('Universum fehlt; nichts verglichen.')
        return 1
    fp = methoden_fingerabdruck(_lies(daten.parent / 'risk_precompute' / 'app-copies.json'))
    neu = schnappschuss(universum, fp, commit, jetzt)
    ordner = daten / 'aenderungen'
    alt = _lies(ordner / 'stand.json')
    doc = _lies(daten / 'cf_aenderungen.json') or {}
    liste = [e for e in doc.get('eintraege', []) if isinstance(e, dict) and isinstance(e.get('tag'), str)]
    tag = jetzt.date().isoformat()
    if alt and alt.get('universumStand') == neu['universumStand']:
        print('Universum unverändert seit dem letzten Vergleich; nichts zu tun.')
        return 0
    neue = []
    if alt and alt.get('method') == METHOD:
        neue = vergleichen(alt, neu, lambda s: _lies(daten / 'fundamentals' / _datei(s)), tag)
    grenze = (jetzt.date() - dt.timedelta(days=FENSTER_TAGE)).isoformat()
    liste = neue + [e for e in liste if e['tag'] > grenze and not (e['tag'] == tag and any(n['symbol'] == e['symbol'] for n in neue))]
    ergebnis = {'schema': 1, 'method': METHOD, 'generatedAt': jetzt.isoformat(), 'scoreContribution': 0,
                'vergleich': {'vorher': (alt or {}).get('universumStand'), 'nachher': neu['universumStand']},
                'schwellen': {'fair_value_rel': SCHWELLE_REL, 'target_12m_rel': SCHWELLE_REL, 'composite_punkte': SCHWELLE_PUNKTE, 'quantum_punkte': SCHWELLE_PUNKTE},
                'fensterTage': FENSTER_TAGE, 'eintraege': liste,
                'grenzen': ['Vergleich mit dem vorherigen Universumsstand; Kursbewegungen allein lösen keinen Eintrag aus, wirken aber auf 12M-Ziel und Analysten-Anker.',
                            'Grund automatisch aus den Daten bestimmt; „Grund nicht erkannt“, wenn keine Regel passt. Kein Kauf- oder Verkaufssignal.']}
    ordner.mkdir(parents=True, exist_ok=True)
    (daten / 'cf_aenderungen.json').write_text(json.dumps(ergebnis, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    (ordner / 'stand.json').write_text(json.dumps(neu, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    print(json.dumps({'neu': len(neue), 'gesamt': len(liste), 'erster_lauf': alt is None}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(lauf(Path(sys.argv[1]) if len(sys.argv) > 1 else Path('value_radar/daten'), commit=os.environ.get('GITHUB_SHA')))
