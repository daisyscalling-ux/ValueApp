"""Trends aus Nachrichten (news_trends_v1, seit 21.11.2026).

Regelbasiert, ohne KI: Schlagzeilen werden täglich archiviert (nie gelöscht) und ausgezählt.
- Nennungen je Aktie: letzte 7 Tage gegen den Grundwert der Wochen davor.
- Themen: feste Schlagwortliste (THEMEN), gleiche Rechnung.
- Kandidaten: Börsenkürzel in Schlagzeilen, die nicht im Universum sind (Identität ungeprüft).
Kein Ergebnis fließt in einen Score (scoreContribution 0). Nur Schlagzeilen und Links, keine Artikeltexte.
Doku: value_radar/NACHRICHTEN_TRENDS.md
"""
import datetime as dt
import gzip
import hashlib
import json
import re
import sys
import urllib.parse
from collections import Counter, defaultdict
from pathlib import Path

UTC = dt.timezone.utc
METHOD = 'news_trends_v1'
FENSTER_TAGE = 7            # aktuelles Fenster
BASIS_TAGE = 56             # Grundwert: bis zu 8 Wochen vor dem Fenster
BASIS_MIN_TAGE = 21         # weniger erfasste Tage: Verhältnis bleibt offen
MIN_NENNUNGEN = 5           # darunter kein Trendstatus (kleine Zahlen schwanken zufällig)
FAKTOR_STEIGEND = 2.0       # aktuell ≥ 2 × Grundwert je Woche
QUELLE_ANTEIL_MIN = 0.9     # Quelle muss an ≥ 90 % der Tage erfasst sein, sonst zählt sie nicht für Verhältnisse
MAX_AKTIEN = None           # seit 23.11.2026 alle Aktien (Wunsch des Nutzers; vorher 200 von 953)
SCHLAGZEILEN_VOLL = 200     # die ersten 200 Aktien mit 3 Schlagzeilen, alle weiteren mit 1 (Dateigröße)
MAX_BEISPIELE = 5

# Routine-Meldungen (Fondsbestände, Bestandsänderungen) sagen nichts über das Unternehmen; sie werden gezählt, aber getrennt.
ROUTINE = re.compile(r"\b(?:(?:stock|shares?) (?:newly )?(?:sold|bought|acquired|purchased) by|(?:buys|sells|acquires|purchases|trims|lifts|raises|lowers|boosts|cuts|reduces|increases|decreases|grows|adds to|takes) (?:a )?(?:new )?(?:position|stake|holdings)|(?:position|stake|holdings) in\b|sells [\d,]+ shares of|buys [\d,]+ shares of|has \$[\d.,]+ (?:million|billion|thousand) (?:position|stake|holdings))", re.I)

# Themenliste: (id, Name, Muster). Nur Begriffe, keine Firmennamen, damit ein Thema nicht an einer Firma hängt.
THEMEN = [
 ('ki', 'Künstliche Intelligenz', r'\bAI\b|\bA\.I\.|\bKI\b|\bLLMs?\b|\bGPUs?\b|(?i:artificial intelligence|generative|chatbot|data ?cent(?:er|re)s?|künstliche intelligenz|rechenzent)'),
 ('blase', 'Blase / Überbewertung', r'\bbubbles?\b|frothy|froth\b|mania\b|euphori|overvalu|over-valu|\bblase\b|überbewert'),
 ('halbleiter', 'Halbleiter', r'semiconductor|\bchips?\b|chipmaker|foundr(?:y|ies)|\bwafer|halbleiter'),
 ('zinsen', 'Zinsen / Notenbanken', r'\bfed\b|federal reserve|rate cuts?|rate hikes?|interest rates?|treasury yields?|bond yields?|\bECB\b|\bEZB\b|\bzins'),
 ('zoelle', 'Zölle / Handel', r'tariffs?|trade war|trade deal|export controls?|\bzöll|\bzoll'),
 ('ruestung', 'Rüstung / Verteidigung', r'\bdefen[cs]e\b|military|\bNATO\b|missiles?|rüstung|verteidigung'),
 ('energie', 'Öl / Gas', r'\boil\b|crude|\bOPEC|natural gas|\bLNG\b|ölpreis|erdgas'),
 ('kernkraft', 'Kernkraft / Uran', r'nuclear|uranium|\bSMRs?\b|reactor|kernkraft|atomkraft'),
 ('abnehmmittel', 'Abnehmmittel (GLP-1)', r'GLP-1|ozempic|wegovy|mounjaro|zepbound|obesity|weight[- ]loss|abnehm'),
 ('krypto', 'Krypto', r'bitcoin|crypto|ethereum|stablecoin|krypto'),
 ('quanten', 'Quantencomputer', r'quantum|quanten'),
 ('uebernahmen', 'Übernahmen / Fusionen', r'acquisition|\bacquire[sd]? (?!by)|merger|takeover|buyout|tender offer|übernahme|fusion'),
 ('rezession', 'Rezession / Abschwung', r'recession|slowdown|layoffs?|job cuts|stagflation|rezession|abschwung|stellenabbau'),
 ('abverkauf', 'Kurseinbruch / Abverkauf', r'sell-?off|plunges?|plummets?|crash(?:es|ed)?\b|tumbles?|rout\b|kurssturz|einbruch'),
]
# „AI“ und „KI“ nur in Großbuchstaben (sonst Treffer wie „Kai“), alle anderen Muster ohne Groß-/Kleinschreibung.
THEMEN_RE = [(i, n, re.compile(p) if i == 'ki' else re.compile(p, re.I)) for i, n, p in THEMEN]

BOERSEN = {'NYSE', 'NASDAQ', 'NYSEAMERICAN', 'NYSEARCA', 'AMEX', 'LSE', 'LON', 'TSX', 'TSXV', 'ASX', 'ETR', 'XTRA', 'FRA', 'TSE', 'TYO', 'HKEX', 'HKG', 'EPA', 'ENX', 'AMS', 'BIT', 'SWX', 'SIX', 'HLSE', 'STO', 'CPH', 'OSL', 'OTCMKTS', 'OTC', 'OTCQX', 'OTCQB', 'CVE', 'NEO', 'CSE', 'NZX', 'JSE', 'KRX', 'BME'}
TICKER = re.compile(r'\(\s*([A-Za-z ]{2,15})\s*:\s*([A-Z0-9][A-Z0-9.\-]{0,7})\s*\)')


def zeit(wert):
 try:
  d = dt.datetime.fromisoformat(str(wert).replace('Z', '+00:00'))
  return d.astimezone(UTC) if d.tzinfo else None
 except (ValueError, TypeError):
  return None


def host(url):
 try:
  return urllib.parse.urlsplit(url).netloc.lower()
 except ValueError:
  return ''


def artikel_id(art, symbol, publisher, url, titel):
 # Gleiche Schlagzeile desselben Verlags zählt einmal (wie company_news.normalize); bei Unternehmensnachrichten je Aktie.
 schluessel = '|'.join([art, symbol or '', (publisher or host(url)).casefold(), ' '.join(titel.split()).casefold()])
 return hashlib.sha256(schluessel.encode()).hexdigest()[:24]


def ist_routine(titel):
 return bool(ROUTINE.search(titel))


def themen_von(titel):
 if ist_routine(titel):
  return []
 return [i for i, _, p in THEMEN_RE if p.search(titel)]


FUELLWOERTER = {'the', 'shares', 'stock', 'inc', 'plc', 'ag', 'sa', 'nv', 'se', 'co', 'ltd', 'llc', 'corp', 'corporation', 'company', 'kgaa', 'spa', 'group', 'holdings', 'holding',
                'contrasting', 'analyzing', 'comparing', 'reviewing', 'head', 'contrast', 'survey', 'critical'}
NAME_ENDE = re.compile(r'\s\(|\s20\d\d\b|\s-\s|,\s|\s(?:Stock|Shares?|Share Price|Q[1-4])\b|\s\$|\s(?:Financial (?:Analysis|Review|Comparison)|Head to Head|Critical Survey)\b')


def name_vor(titel, boerse, kuerzel):
 """Firmenname zum Kürzel: Text zwischen der vorigen Klammer (oder dem Anfang) und „(BÖRSE:KÜRZEL)“."""
 m = re.search(r'\(\s*' + re.escape(boerse) + r'\s*:\s*' + re.escape(kuerzel) + r'\s*\)', titel)
 if not m:
  return ''
 vor = titel[:m.start()]
 vor = vor[vor.rfind(')') + 1:]
 vor = re.sub(r'^\W*(?:(?:&|and|vs\.?|versus|or)\s+)?', '', vor.split(':')[-1].strip())
 vor = re.sub(r'^(?:Contrasting|Analyzing|Comparing|Reviewing|Head to Head (?:Comparison|Contrast|Survey)|Critical Comparison)\s*:?\s+', '', vor, flags=re.I)
 return ' '.join(NAME_ENDE.split(' ' + vor)[0].split()[:6])


def namenskern(name):
 """Erste zwei kennzeichnende Wörter (nur zum Kennzeichnen möglicher Doppelungen, nie als Identitätsnachweis)."""
 w = [x.casefold() for x in re.findall(r"[A-Za-zÀ-ÿ0-9][A-Za-zÀ-ÿ0-9'\-]+", name or '') if x.casefold() not in FUELLWOERTER and len(x) >= 2]
 return tuple(w[:2])


def aehnlich(a, b):
 # Erstes Wort gleich und, wenn beide ein zweites haben, auch das zweite.
 return bool(a and b and a[0] == b[0] and (len(a) < 2 or len(b) < 2 or a[1] == b[1]))


def lies(pfad, standard):
 return json.loads(pfad.read_text(encoding='utf8')) if pfad.exists() else standard


def schreibe(pfad, daten):
 pfad.parent.mkdir(parents=True, exist_ok=True)
 tmp = pfad.with_suffix(pfad.suffix + '.tmp')
 tmp.write_text(json.dumps(daten, ensure_ascii=False, allow_nan=False, separators=(',', ':')), encoding='utf8')
 tmp.replace(pfad)


def eintraege(company, market, jetzt):
 """Aktuelle Exportdateien in Archivzeilen umwandeln. Liefert (zeilen, quellen_des_tages, gekappt)."""
 zeilen, quellen, gekappt = [], set(), []
 for symbol, s in sorted((company or {}).get('stocks', {}).items()):
  quelle = s.get('source')
  if not quelle or not s.get('items'):
   continue
  quellen.add('u:' + quelle)
  if s.get('truncated'):
   gekappt.append(symbol)
  for i in s['items']:
   t = zeit(i.get('publishedAt'))
   if not t or not isinstance(i.get('title'), str) or t > jetzt + dt.timedelta(hours=1):
    continue
   zeilen.append({'id': artikel_id('u', symbol, i.get('publisher'), i.get('url', ''), i['title']), 'art': 'u', 'symbol': symbol, 'quelle': 'u:' + quelle,
                  'publishedAt': t.isoformat(), 'title': i['title'][:500], 'url': str(i.get('url', ''))[:1000], 'publisher': str(i.get('publisher') or host(i.get('url', '')))[:150]})
 for key, s in sorted(((market or {}).get('sources') or {}).items()):
  if s.get('error') or not s.get('items'):
   continue
  quellen.add('m:' + key)
  for i in s['items']:
   t = zeit(i.get('publishedAt'))
   if not t or not isinstance(i.get('title'), str) or t > jetzt + dt.timedelta(hours=1):
    continue
   zeilen.append({'id': artikel_id('m', None, i.get('publisher'), i.get('url', ''), i['title']), 'art': 'm', 'symbol': None, 'quelle': 'm:' + key,
                  'publishedAt': t.isoformat(), 'title': i['title'][:500], 'url': str(i.get('url', ''))[:1000], 'publisher': str(i.get('publisher') or s.get('name') or '')[:150]})
 return zeilen, sorted(quellen), sorted(gekappt)


def tagesdatei(ordner, tag):
 # Eine Datei je Erfassungstag (gzip), einmal geschrieben: das Git-Archiv wächst nur um neue Zeilen.
 return ordner / tag[:4] / tag[5:7] / (tag + '.jsonl.gz')


def tagesdatei_lesen(pfad):
 if not pfad.exists():
  return []
 with gzip.open(pfad, 'rt', encoding='utf8') as f:
  return [json.loads(z) for z in f if z.strip()]


def archiv_lesen(ordner, ab=None):
 out = []
 for f in sorted(ordner.glob('20??/??/20??-??-??.jsonl.gz')):
  if ab and f.name[:10] < ab.date().isoformat():
   continue
  out.extend(tagesdatei_lesen(f))
 return out


def archivieren(ordner, company, market, jetzt):
 """Neue Schlagzeilen ablegen (nie überschreiben, nie löschen) und den Tag im Erfassungsprotokoll vermerken."""
 ordner.mkdir(parents=True, exist_ok=True)
 zeilen, quellen, gekappt = eintraege(company, market, jetzt)
 bekannt = {z['id'] for z in archiv_lesen(ordner, jetzt - dt.timedelta(days=31))}
 neu = []
 for z in zeilen:
  if z['id'] in bekannt:
   continue
  bekannt.add(z['id'])
  neu.append({**z, 'erfasst': jetzt.isoformat()})
 tag = jetzt.date().isoformat()
 if neu:
  datei = tagesdatei(ordner, tag)
  alle = tagesdatei_lesen(datei) + neu
  datei.parent.mkdir(parents=True, exist_ok=True)
  tmp = datei.with_name(datei.name + '.tmp')
  # mtime=0: gleicher Inhalt ergibt gleiche Bytes (kein Scheinunterschied in Git).
  with open(tmp, 'wb') as roh, gzip.GzipFile(fileobj=roh, mode='wb', mtime=0) as f:
   for z in alle:
    f.write((json.dumps(z, ensure_ascii=False, separators=(',', ':')) + '\n').encode('utf8'))
  tmp.replace(datei)
 protokoll = lies(ordner / 'erfassung.json', {'schema': 1, 'tage': {}})
 alt = protokoll['tage'].get(tag, {'quellen': [], 'gekappt': [], 'neu': 0, 'laeufe': 0})
 protokoll['tage'][tag] = {'quellen': sorted(set(alt['quellen']) | set(quellen)), 'gekappt': sorted(set(alt['gekappt']) | set(gekappt)),
                           'neu': alt['neu'] + len(neu), 'laeufe': alt['laeufe'] + 1}
 schreibe(ordner / 'erfassung.json', protokoll)
 return len(neu), protokoll


def verhaeltnis(aktuell, basis_woche):
 if basis_woche is None:
  return None
 if basis_woche == 0:
  return None
 return round(aktuell / basis_woche, 2)


def einstufen(aktuell, basis_woche, basis_tage, gekappt=False, quelle_fehlt=False):
 """Status je Zeile. Gründe sind Klartext für die App."""
 if basis_tage < BASIS_MIN_TAGE:
  return 'offen', f'Grundwert im Aufbau: {basis_tage} von {BASIS_MIN_TAGE} Tagen erfasst'
 if quelle_fehlt:
  return 'offen', 'Quelle der Nachrichten hat im Zeitraum gewechselt; kein fairer Vergleich'
 if aktuell < MIN_NENNUNGEN:
  return 'wenig', f'Weniger als {MIN_NENNUNGEN} Nennungen in {FENSTER_TAGE} Tagen'
 if basis_woche == 0:
  return 'neu', 'Im Grundwert keine Nennung'
 r = aktuell / basis_woche
 if r >= FAKTOR_STEIGEND:
  return 'steigend', f'{r:.1f}-mal so oft wie im Grundwert' + (' (Abruf gekappt, wahrer Wert eher höher)' if gekappt else '')
 if r <= 1 / FAKTOR_STEIGEND:
  return 'fallend', f'{r:.1f}-mal so oft wie im Grundwert'
 return 'normal', 'Im Bereich des Grundwerts'


def auswerten(ordner, universum, jetzt):
 protokoll = lies(ordner / 'erfassung.json', {'schema': 1, 'tage': {}})
 tage = sorted(protokoll['tage'])
 fenster_start = jetzt - dt.timedelta(days=FENSTER_TAGE)
 basis_start = fenster_start - dt.timedelta(days=BASIS_TAGE)
 basis_tage_liste = [t for t in tage if basis_start.date().isoformat() <= t < fenster_start.date().isoformat()]
 fenster_tage_liste = [t for t in tage if t >= fenster_start.date().isoformat()]
 basis_tage = len(basis_tage_liste)
 # Quellen, die fast durchgehend erfasst wurden; nur sie zählen für Verhältnisse (Verzerrung durch neue Feeds vermeiden).
 alle_tage = basis_tage_liste + fenster_tage_liste
 zaehl = Counter(q for t in alle_tage for q in protokoll['tage'][t]['quellen'])
 stabile = {q for q, n in zaehl.items() if alle_tage and n / len(alle_tage) >= QUELLE_ANTEIL_MIN}
 gekappt_fenster = {s for t in fenster_tage_liste for s in protokoll['tage'][t]['gekappt']}

 zeilen = archiv_lesen(ordner, basis_start - dt.timedelta(days=1))
 # Nach Erfassungszeit zuordnen: der Grundwert zählt nur, was in Grundwert-Tagen tatsächlich erfasst wurde.
 def im_fenster(z):
  return (zeit(z['publishedAt']) or jetzt) >= fenster_start
 def in_basis(z):
  e = zeit(z.get('erfasst')); p = zeit(z['publishedAt'])
  return bool(e and p and basis_start <= p < fenster_start and e.date().isoformat() in basis_tage_liste)
 basis_wochen = basis_tage / 7 if basis_tage else 0

 namen = {}
 for r in (universum or {}).get('kandidaten', []):
  s = str(r.get('listing_symbol') or r.get('ticker') or '').upper()
  if s:
   namen[s] = r.get('name') or s

 # Aktien
 pro_aktie = defaultdict(lambda: {'akt': [], 'routine': 0, 'basis': 0, 'quellen_f': set(), 'quellen_b': set()})
 for z in zeilen:
  if z['art'] != 'u' or not z.get('symbol'):
   continue
  a = pro_aktie[z['symbol']]
  if im_fenster(z):
   if ist_routine(z['title']):
    a['routine'] += 1
   else:
    a['akt'].append(z); a['quellen_f'].add(z['quelle'])
  elif in_basis(z) and not ist_routine(z['title']):
   a['basis'] += 1; a['quellen_b'].add(z['quelle'])
 aktien = []
 for s, a in pro_aktie.items():
  n = len(a['akt'])
  if not n and not a['routine']:
   continue
  quelle_fehlt = bool(a['quellen_b']) and a['quellen_f'] != a['quellen_b'] or bool(a['quellen_f'] - stabile)
  bw = round(a['basis'] / basis_wochen, 2) if basis_wochen else None
  status, grund = einstufen(n, bw, basis_tage, s in gekappt_fenster, quelle_fehlt)
  akt = sorted(a['akt'], key=lambda z: z['publishedAt'], reverse=True)
  aktien.append({'symbol': s, 'name': namen.get(s, s), 'nennungen': n, 'routine': a['routine'], 'basisProWoche': bw,
                 'verhaeltnis': verhaeltnis(n, bw) if status in ('steigend', 'fallend', 'normal') else None,
                 'status': status, 'grund': grund, 'gekappt': s in gekappt_fenster,
                 'themen': sorted({t for z in akt for t in themen_von(z['title'])}),
                 'schlagzeilen': [{k: z[k] for k in ('title', 'url', 'publisher', 'publishedAt')} for z in akt[:3]]})
 rang = {'steigend': 0, 'neu': 1, 'normal': 2, 'offen': 3, 'fallend': 4, 'wenig': 5}
 aktien.sort(key=lambda x: (rang[x['status']], -(x['verhaeltnis'] or 0), -x['nennungen'], x['symbol']))

 # Themen: über Unternehmens- und Marktnachrichten; Verhältnis nur über stabile Quellen.
 themen = []
 for tid, name, _ in THEMEN_RE:
  akt = [z for z in zeilen if im_fenster(z) and tid in themen_von(z['title'])]
  akt_stabil = [z for z in akt if z['quelle'] in stabile]
  basis = [z for z in zeilen if in_basis(z) and z['quelle'] in stabile and tid in themen_von(z['title'])]
  bw = round(len(basis) / basis_wochen, 2) if basis_wochen else None
  status, grund = einstufen(len(akt_stabil), bw, basis_tage)
  akt.sort(key=lambda z: z['publishedAt'], reverse=True)
  firmen = Counter(z['symbol'] for z in akt if z.get('symbol'))
  themen.append({'id': tid, 'name': name, 'nennungen': len(akt), 'nennungenVergleichbar': len(akt_stabil), 'basisProWoche': bw,
                 'verhaeltnis': verhaeltnis(len(akt_stabil), bw) if status in ('steigend', 'fallend', 'normal') else None,
                 'status': status, 'grund': grund,
                 'aktien': [{'symbol': s, 'name': namen.get(s, s), 'nennungen': n} for s, n in firmen.most_common(10)],
                 'beispiele': [{k: z[k] for k in ('title', 'url', 'publisher', 'publishedAt')} for z in akt[:MAX_BEISPIELE]]})
 themen.sort(key=lambda x: (rang[x['status']], -x['nennungen']))

 # Kandidaten außerhalb des Universums: Börsenkürzel in Schlagzeilen, Identität ungeprüft.
 basis_kuerzel = set()
 for s in namen:
  teil = s.split(':')[-1]
  basis_kuerzel.add(teil); basis_kuerzel.add(teil.split('.')[0])
 for r in (universum or {}).get('kandidaten', []):
  for k in ('ticker', 'yahoo_symbol', 'adr_ticker'):
   if r.get(k):
    basis_kuerzel.add(str(r[k]).upper().split('.')[0])
 kand = defaultdict(lambda: {'n': 0, 'tage': set(), 'verlage': set(), 'z': [], 'namen': set()})
 kerne = [(namenskern(n), s) for s, n in namen.items() if namenskern(n)]
 for z in zeilen:
  if not im_fenster(z) or ist_routine(z['title']):
   continue
  for boerse, kuerzel in TICKER.findall(z['title']):
   b = boerse.replace(' ', '').upper()
   if b not in BOERSEN or kuerzel in basis_kuerzel or kuerzel.split('.')[0] in basis_kuerzel:
    continue
   k = kand[(b, kuerzel)]
   k['namen'].add(name_vor(z['title'], boerse, kuerzel))
   k['n'] += 1; k['tage'].add(z['publishedAt'][:10]); k['verlage'].add(z['publisher']); k['z'].append(z)
 kandidaten = []
 for (b, kz), k in kand.items():
  z = sorted(k['z'], key=lambda x: x['publishedAt'], reverse=True)
  treffer = sorted({s for n in k['namen'] for kern, s in kerne if aehnlich(namenskern(n), kern)})
  kandidaten.append({'boerse': b, 'kuerzel': kz, 'name': max(k['namen'], key=len, default=''), 'nennungen': k['n'], 'tage': len(k['tage']), 'verlage': len(k['verlage']),
                     'identitaet': 'ungeprueft', 'otc': b.startswith('OTC'), 'aehnlichImUniversum': treffer[:3],
                     'schlagzeilen': [{x: y[x] for x in ('title', 'url', 'publisher', 'publishedAt')} for y in z[:3]]})
 kandidaten.sort(key=lambda x: (bool(x['aehnlichImUniversum']), x['otc'], -x['verlage'], -x['nennungen'], x['kuerzel']))

 return {'schema': 1, 'method': METHOD, 'generatedAt': jetzt.isoformat(), 'scoreContribution': 0,
         'konstanten': {'fensterTage': FENSTER_TAGE, 'basisTage': BASIS_TAGE, 'basisMinTage': BASIS_MIN_TAGE, 'minNennungen': MIN_NENNUNGEN,
                        'faktorSteigend': FAKTOR_STEIGEND, 'quelleAnteilMin': QUELLE_ANTEIL_MIN},
         'archiv': {'ersterTag': tage[0] if tage else None, 'erfassteTage': len(tage), 'basisTage': basis_tage, 'fensterTage': len(fenster_tage_liste),
                    'artikelFenster': sum(1 for z in zeilen if im_fenster(z)), 'stabileQuellen': sorted(stabile)},
         'themen': themen, 'aktien': [a if i < SCHLAGZEILEN_VOLL else {**a, 'schlagzeilen': a['schlagzeilen'][:1]} for i, a in enumerate(aktien[:MAX_AKTIEN])], 'aktienGesamt': len(aktien), 'kandidaten': kandidaten[:100],
         'grenzen': [
          'Nur Schlagzeilen, keine Artikeltexte; Schlagwörter erkennen keinen Zusammenhang und keine Ironie.',
          'Unternehmensnachrichten werden je Universumstitel abgefragt (höchstens 30 je Abruf); große Werte sind dadurch gekappt.',
          'Überwiegend englischsprachige Quellen; US-Werte sind stärker vertreten.',
          'Kandidaten außerhalb des Universums: Börsenkürzel aus Schlagzeilen, Identität nicht geprüft; OTC-Kürzel sind oft ADRs bekannter Firmen.',
          'Kein Kauf- oder Verkaufssignal; fließt in keinen Score ein.']}


def main(daten=Path('value_radar/daten'), jetzt=None):
 jetzt = jetzt or dt.datetime.now(UTC)
 ordner = daten / 'nachrichten_archiv'
 company = lies(daten / 'cf_company_news.json', None)
 market = lies(daten / 'cf_news.json', None)
 if company is None and market is None:
  raise SystemExit('Keine Nachrichtendateien gefunden')
 neu, _ = archivieren(ordner, company, market, jetzt)
 ergebnis = auswerten(ordner, lies(daten / 'cf_universum.json', None), jetzt)
 ergebnis['archiv']['neuInDiesemLauf'] = neu
 schreibe(daten / 'cf_trends.json', ergebnis)
 print(json.dumps({'neu': neu, **ergebnis['archiv'], 'themen': len(ergebnis['themen']), 'aktien': ergebnis['aktienGesamt'], 'kandidaten': len(ergebnis['kandidaten'])}, ensure_ascii=False))


if __name__ == '__main__':
 main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path('value_radar/daten'))
