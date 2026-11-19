"""Vorwaertstest Fair Value gegen 12M-Ziel (seit 19.11.2026, Entscheidung des Nutzers).

Gespeichert werden nur Titel, bei denen Fair Value und 12M-Ziel in entgegengesetzte Richtungen zeigen (je mindestens
MIN_ABSTAND vom Kurs). Nach 1, 3, 6 und 12 Monaten wird gemessen, wohin der Kurs gegangen ist: split-bereinigt und
relativ zum Median der Region (Marktbewegung heraus). Steigt der Titel marktbereinigt um mehr als UNENTSCHIEDEN, hatte
das Modell recht, das nach oben zeigte; faellt er um mehr als UNENTSCHIEDEN, das Modell, das nach unten zeigte;
dazwischen unentschieden.

Je Universumsstand entsteht eine Datei daten/forward_test/staende/<stand>.json mit den Eintraegen (gegenlaeufige Titel)
und den Kursen aller Titel (fuer Ergebnis und Marktabgleich). Herkunft: Pfad, sha256 und bei Rekonstruktion der Commit.
Rekonstruierte Staende vor dem Start (aeltere Methoden) tragen kohorte "vorversion" und werden nie mit "aktuell" gemischt.
Kein Kurs, keine Prognose wird geschaetzt: fehlt ein spaeterer Kurs oder passt die Notierung nicht, entfaellt der Eintrag
fuer diesen Zeitraum mit Grund.
"""
import argparse, datetime as dt, hashlib, json, os, re, statistics, subprocess, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import kurszeit

METHODE = 'fv_vs_target_forward_v2'   # v2 seit 19.11.2026: nur geprueft Schlusskurse (kurszeit.py); v1-Staende = Vorversion
MIN_ABSTAND = 0.05
UNENTSCHIEDEN = 0.02
HORIZONTE = {'1M': 30, '3M': 91, '6M': 182, '12M': 365}
TOLERANZ_TAGE = 10          # spaeterer Stand hoechstens so viele Tage nach dem Zieldatum
START = '2026-11-19'        # Rekonstruktion nur vor diesem Tag; Kohorte "aktuell" nur mit Schema 2 (kohorte_von)
BASIS = Path(__file__).resolve().parents[1]
ORDNER = BASIS / 'daten' / 'forward_test'
STAENDE = ORDNER / 'staende'
REGION = {'US': 'USA', 'United States': 'USA', 'JP': 'Japan', 'GB': 'Grossbritannien'}
EUROPA = {'DE', 'FR', 'CH', 'SE', 'IT', 'NL', 'ES', 'DK', 'NO', 'PL', 'FI', 'BE', 'GR', 'AT', 'IE', 'PT', 'LU', 'CZ', 'HU'}
SPRUNG = (-0.5, 1.0)        # Kursaenderung ausserhalb dieses Bereichs ohne Splitnachweis: offen (moeglicher Split)
KURS_FELDER = ['price', 'currency', 'isin', 'region', 'kind', 'day']   # kompakte Kursliste je Titel
MIN_REGION = 20             # Marktabgleich nur mit mindestens so vielen Titeln der Region


def region(land):
    if land in REGION:
        return REGION[land]
    return 'Europa ohne GB' if land in EUROPA else 'sonstige'


def zahl(x):
    return x if isinstance(x, (int, float)) and not isinstance(x, bool) and x == x and abs(x) != float('inf') else None


def stand_zeit(stand):
    """'2026-11-19 13:04 UTC' -> datetime (UTC)."""
    m = re.match(r'(\d{4}-\d{2}-\d{2})[ T](\d{2}):(\d{2})', str(stand or ''))
    if not m:
        return None
    return dt.datetime.fromisoformat(f'{m.group(1)}T{m.group(2)}:{m.group(3)}:00+00:00')


def fingerabdruck(r):
    """Methodenstand der Zeile (Versionen und Kennzeichnungen der Regeln), damit spaeter nach Methode getrennt wird."""
    vi = r.get('value_inputs') if isinstance(r.get('value_inputs'), dict) else {}
    teile = {
        'scanner_method': r.get('scanner_method'),
        'value_inputs': vi.get('method'),
        'eps_basis': 'ja' if 'eps_basis' in r else 'nein',
        'terminal_growth': 'ja' if 'terminal_growth' in r else 'nein',
        'risk_free': 'ja' if 'risk_free' in r else 'nein',
        'roic_history': 'ja' if 'roic_history_status' in r else 'nein',
    }
    return teile, hashlib.sha256(json.dumps(teile, sort_keys=True).encode()).hexdigest()[:12]


def kursart(r):
    """Kursart der Zeile neu bestimmen (nicht ungeprueft uebernehmen) -> (kind, tag, grund)."""
    boerse = r.get('exchange') or str(r.get('listing_symbol') or '').split(':')[0]
    a = kurszeit.einordnen(boerse, r.get('price_time'), r.get('price_date'), r.get('price_fetched_at'))
    if r.get('price_kind_method') != kurszeit.METHODE:
        return 'unbekannt', None, 'Kurs ohne Zeitangabe im Export'
    if a['kind'] != r.get('price_kind') or a['date'] != r.get('price_day'):
        return 'unbekannt', None, 'Kursart im Export widerspricht der Nachpruefung'
    return a['kind'], a['date'], a['reason']


def kohorte_von(s):
    """Staende vor v2 (ohne geprueften Schlusskurs) zaehlen immer als Vorversion."""
    return s.get('kohorte') if s.get('schema') == 2 else 'vorversion'


def gegenlaeufig(r):
    p, fv, z = zahl(r.get('price')), zahl(r.get('fair_value')), zahl(r.get('target_12m'))
    if not (p and p > 0 and fv and fv > 0 and z and z > 0):
        return None
    a, b = fv / p - 1, z / p - 1
    if a * b < 0 and abs(a) >= MIN_ABSTAND and abs(b) >= MIN_ABSTAND:
        return a, b
    return None


def schnappschuss(doc, quelle, kohorte, commit=None, roh=None):
    """Universumsstand -> Stand-Datei (Eintraege der gegenlaeufigen Titel, Kurse aller Titel)."""
    stand = doc.get('stand')
    if stand_zeit(stand) is None:
        raise ValueError('Universum ohne gueltigen Stand')
    eintraege, kurse, methoden, ohne_schluss = [], {}, {}, {}
    for r in doc.get('kandidaten') or []:
        sym = r.get('listing_symbol')
        p = zahl(r.get('price'))
        if not isinstance(sym, str) or not p or p <= 0:
            continue
        art, tag, grund = kursart(r)
        kurse[sym] = [p, r.get('currency'), r.get('isin'), region(r.get('country')), art, tag]
        g = gegenlaeufig(r)
        if g is None:
            continue
        if art != 'schluss':
            k = grund or 'kein Schlusskurs'
            ohne_schluss[k] = ohne_schluss.get(k, 0) + 1
            continue
        teile, fp = fingerabdruck(r)
        methoden[fp] = teile
        eintraege.append({
            'listing_symbol': sym, 'isin': r.get('isin'), 'currency': r.get('currency'), 'region': region(r.get('country')),
            'name': r.get('name'), 'price': p, 'price_day': tag, 'fair_value': r['fair_value'], 'target_12m': r['target_12m'],
            'exchange': r.get('exchange'), 'price_time': r.get('price_time'), 'price_date': r.get('price_date'),
            'price_fetched_at': r.get('price_fetched_at'),
            'fv_pct': round(g[0] * 100, 2), 'target_pct': round(g[1] * 100, 2),
            'oben': 'fair_value' if g[0] > 0 else 'ziel_12m',
            'fv_reliable': r.get('fv_reliable'), 'kauf_urteil': r.get('kauf_urteil'), 'playbook': r.get('playbook'),
            'fingerabdruck': fp})
    return {'schema': 2, 'method': METHODE, 'stand': stand, 'kohorte': kohorte, 'min_abstand': MIN_ABSTAND,
            'kursart_methode': kurszeit.METHODE, 'gegenlaeufig_ohne_schlusskurs': ohne_schluss,
            'quelle': {'pfad': quelle, 'commit': commit, 'sha256': hashlib.sha256(roh).hexdigest() if roh else None},
            'erstellt': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
            'methoden': methoden, 'kurse_felder': KURS_FELDER, 'eintraege': eintraege, 'kurse': kurse}


def dateiname(stand):
    t = stand_zeit(stand)
    return t.strftime('%Y-%m-%dT%H%M') + '.json'


def speichern(snap, ordner=STAENDE):
    ordner.mkdir(parents=True, exist_ok=True)
    pfad = ordner / dateiname(snap['stand'])
    if any(ordner.glob(pfad.name[:10] + 'T*.json')):   # ein Stand je Kalendertag (Horizonte ab 30 Tagen)
        return None
    pfad.write_text(json.dumps(snap, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
    return pfad


def splitfaktor(splits, von, bis):
    """Produkt der Splitverhaeltnisse mit Datum in (von, bis]: so viele neue Aktien je alte."""
    f = 1.0
    for s in splits or []:
        try:
            d = dt.date.fromisoformat(str(s.get('date'))[:10])
            r = float(s.get('ratio'))
        except (TypeError, ValueError, AttributeError):
            continue
        if von < d <= bis and r > 0:
            f *= r
    return f


def splits_laden(sym, ordner=None):
    ordner = ordner or BASIS / 'daten' / 'fundamentals'
    try:
        d = json.loads((ordner / (re.sub(r'[^A-Za-z0-9._-]', '_', sym) + '.json')).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return []
    return d.get('splits') or [] if d.get('symbol') == sym else []


def rendite(k0, k1, t0, t1, splits):
    """Split-bereinigte Kursrendite -> (wert, grund). Wert None bei Identitaetsbruch oder unbelegtem Kurssprung."""
    for k in (k0, k1):
        if 'kind' in k and k['kind'] != 'schluss':
            return None, 'Kein Schlusskurs'
    if k0.get('currency') != k1.get('currency'):
        return None, 'Waehrung verschieden'
    if k0.get('isin') and k1.get('isin') and k0['isin'] != k1['isin']:
        return None, 'ISIN verschieden'
    f = splitfaktor(splits, t0.date(), t1.date())
    r = k1['price'] * f / k0['price'] - 1
    if f == 1.0 and not (SPRUNG[0] <= r <= SPRUNG[1]):
        return None, 'Kurssprung ohne Splitnachweis'
    return r, None


def auswerten(staende, jetzt=None, splits_von=splits_laden):
    """Alle Stand-Dateien -> Ergebnis je Kohorte und Zeitraum."""
    jetzt = jetzt or dt.datetime.now(dt.timezone.utc)
    staende = sorted(staende, key=lambda s: stand_zeit(s['stand']))
    for s in staende:
        s['kurse'] = {k: dict(zip(KURS_FELDER, v)) if isinstance(v, list) else v for k, v in s['kurse'].items()}
    zeiten = [stand_zeit(s['stand']) for s in staende]
    cache, ergebnis, gruende, methoden = {}, {}, {}, {}
    for i, s in enumerate(staende):
        t0 = zeiten[i]
        methoden.update(s.get('methoden') or {})
        for h, tage in HORIZONTE.items():
            ziel = t0 + dt.timedelta(days=tage)
            if ziel > jetzt:
                continue
            j = next((k for k in range(i + 1, len(staende)) if zeiten[k] >= ziel), None)
            if j is None or (zeiten[j] - ziel).days > TOLERANZ_TAGE:
                k = f"{kohorte_von(s)} {h}"
                gruende[k] = gruende.get(k, 0) + len(s['eintraege'])
                continue
            s1, t1 = staende[j], zeiten[j]
            # Marktbewegung: Median der split-bereinigten Renditen aller Titel derselben Region
            markt = {}
            for sym, k0 in s['kurse'].items():
                k1 = s1['kurse'].get(sym)
                if not k1:
                    continue
                sp = cache.setdefault(sym, splits_von(sym))
                r, _ = rendite(k0, k1, t0, t1, sp)
                if r is not None:
                    markt.setdefault(k0.get('region'), []).append(r)
            median = {reg: statistics.median(v) for reg, v in markt.items() if len(v) >= MIN_REGION}
            for e in s['eintraege']:
                sym = e['listing_symbol']
                k1 = s1['kurse'].get(sym)
                sp = cache.setdefault(sym, splits_von(sym))
                r, grund = rendite(s['kurse'][sym], k1, t0, t1, sp) if k1 else (None, 'kein spaeterer Kurs')
                m = median.get(e['region'])
                key = (kohorte_von(s), h)
                z = ergebnis.setdefault(key, {'n': 0, 'fair_value': 0, 'ziel_12m': 0, 'unentschieden': 0, 'offen': {},
                                              'rel': [], 'nach_oben': {'fair_value': [0, 0], 'ziel_12m': [0, 0]}, 'methode': {}, 'titel': set()})
                if r is None or m is None:
                    grund = grund or f'Region mit weniger als {MIN_REGION} Titeln'
                    z['offen'][grund] = z['offen'].get(grund, 0) + 1
                    continue
                rel = (1 + r) / (1 + m) - 1
                z['n'] += 1
                z['titel'].add(sym)
                z['rel'].append(rel)
                zm = z['methode'].setdefault(e.get('fingerabdruck'), {'fair_value': 0, 'ziel_12m': 0, 'unentschieden': 0})
                if abs(rel) <= UNENTSCHIEDEN:
                    z['unentschieden'] += 1
                    zm['unentschieden'] += 1
                    continue
                unten = 'ziel_12m' if e['oben'] == 'fair_value' else 'fair_value'
                sieger = e['oben'] if rel > 0 else unten
                z[sieger] += 1
                zm[sieger] += 1
                z['nach_oben'][e['oben']][0 if rel > 0 else 1] += 1
    out = []
    for (koh, h), z in sorted(ergebnis.items(), key=lambda x: (x[0][0] or '', HORIZONTE[x[0][1]])):
        entschieden = z['fair_value'] + z['ziel_12m']
        out.append({'kohorte': koh, 'zeitraum': h, 'n': z['n'], 'titel': len(z['titel']), 'fair_value_recht': z['fair_value'], 'ziel_12m_recht': z['ziel_12m'],
                    'unentschieden': z['unentschieden'],
                    'anteil_fair_value': round(z['fair_value'] / entschieden, 3) if entschieden else None,
                    'median_marktbereinigt_pct': round(statistics.median(z['rel']) * 100, 2) if z['rel'] else None,
                    'nach_oben_zeigte': {k: {'stieg': v[0], 'fiel': v[1]} for k, v in z['nach_oben'].items()},
                    'nach_methode': z['methode'], 'offen': z['offen']})
    return {'schema': 1, 'method': METHODE, 'ausgewertet': jetzt.isoformat(timespec='seconds'),
            'regeln': {'min_abstand': MIN_ABSTAND, 'unentschieden': UNENTSCHIEDEN, 'horizonte_tage': HORIZONTE,
                       'toleranz_tage': TOLERANZ_TAGE, 'markt': f'Median der split-bereinigten Kursrenditen aller Titel der Region (mindestens {MIN_REGION})', 'kurssprung_ohne_split': SPRUNG},
            'staende': len(staende), 'methoden': methoden, 'ergebnisse': out, 'ohne_passenden_spaeteren_stand': gruende}


def index_schreiben(ordner=ORDNER, splits_von=splits_laden):
    """Uebersicht der Staende und Splits seit dem aeltesten Stand fuer die App (Zwischenstand gegen den heutigen Kurs)."""
    staende = []
    for p in sorted((ordner / 'staende').glob('*.json')):
        roh = p.read_bytes()
        d = json.loads(roh)
        staende.append({'datei': p.name, 'stand': d['stand'], 'kohorte': kohorte_von(d), 'method': d.get('method'), 'eintraege': len(d['eintraege']),
                        'sha256': hashlib.sha256(roh).hexdigest()})
    ab = stand_zeit(staende[0]['stand']).date() if staende else None
    splits, symbole = {}, set()
    for p in (ordner / 'staende').glob('*.json'):
        symbole.update(json.loads(p.read_text(encoding='utf-8'))['kurse'])
    for sym in sorted(symbole):
        sp = [x for x in splits_von(sym) if ab and str(x.get('date', ''))[:10] > ab.isoformat()]
        if sp:
            splits[sym] = sp
    doc = {'schema': 1, 'method': METHODE, 'erstellt': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
           'regeln': {'min_abstand': MIN_ABSTAND, 'unentschieden': UNENTSCHIEDEN, 'min_region': MIN_REGION,
                      'kurssprung_ohne_split': SPRUNG, 'horizonte_tage': HORIZONTE},
           'staende': staende, 'splits_ab': ab.isoformat() if ab else None, 'splits': splits}
    (ordner / 'index.json').write_text(json.dumps(doc, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    return doc


def lade_staende(ordner=STAENDE):
    return [json.loads(p.read_text(encoding='utf-8')) for p in sorted(ordner.glob('*.json'))]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('befehl', choices=['schnappschuss', 'auswerten'])
    ap.add_argument('--universum', default=str(BASIS / 'daten' / 'cf_universum.json'))
    a = ap.parse_args(argv)
    if a.befehl == 'schnappschuss':
        roh = Path(a.universum).read_bytes()
        doc = json.loads(roh)
        snap = schnappschuss(doc, 'value_radar/daten/cf_universum.json', 'aktuell', roh=roh)
        if not snap['eintraege']:
            print(f"[forward] nicht gespeichert: keine gegenlaeufigen Titel mit geprueftem Schlusskurs {snap['gegenlaeufig_ohne_schlusskurs']}")
            return
        p = speichern(snap)
        if p:
            print(f"[forward] gespeichert: {p.name} ({len(snap['eintraege'])} Eintraege, ohne Schlusskurs {snap['gegenlaeufig_ohne_schlusskurs']})")
        else:
            print('[forward] Stand schon vorhanden')
    else:
        index_schreiben()
        erg = auswerten(lade_staende())
        (ORDNER / 'ergebnis.json').write_text(json.dumps(erg, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
        for z in erg['ergebnisse']:
            print(f"[forward] {z['kohorte']} {z['zeitraum']}: n={z['n']} FV recht {z['fair_value_recht']}, Ziel recht {z['ziel_12m_recht']}, unentschieden {z['unentschieden']}")
        print(f"[forward] {erg['staende']} Staende, ausgewertet {erg['ausgewertet']}")


if __name__ == '__main__':
    main()
