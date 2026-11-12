"""Laedt ausgewaehlte SEC-Einreichungen (6-K, 40-F, 20-F) auslaendischer Banken fuer die KM1-Pruefung.

Nur Archive unter https://www.sec.gov/Archives/edgar/data/. Die Zugangsnummern stehen in
sec-bank-filings.json; Eintraege mit form + reportDate statt accession werden ueber data.sec.gov/submissions
eindeutig aufgeloest (12.11.2026). Der User-Agent kommt aus SEC_USER_AGENT (Anwendung + Kontakt) und wird nie ausgegeben.
Ergebnis: Ordner mit den Dokumenten und manifest.json (URL, Groesse, SHA-256).
"""
import hashlib, json, os, re, sys, time, urllib.error, urllib.request
from pathlib import Path

ARCHIVE = 'https://www.sec.gov/Archives/edgar/data/'
KEEP = re.compile(r'\.(htm|html|pdf|xlsx)$', re.I)
# XBRL-Ansichtsseiten (R1.htm ...) und die komplette Einreichung (.txt) sind Kopien; sie werden nicht geladen.
SKIP = re.compile(r'^R\d+\.htm$|-index(-headers)?\.html?$', re.I)


def accession_ok(a):
    return bool(re.fullmatch(r'\d{10}-\d{2}-\d{6}', a))


SUBMISSIONS = 'https://data.sec.gov/submissions/CIK{:010d}.json'


def resolve(submissions, form, report_date):
    """Eindeutige Zugangsnummer fuer Formular und Berichtsstichtag aus data.sec.gov/submissions (filings.recent).
    Mehrere Treffer (z. B. Original und Berichtigung) oder keiner: Abbruch statt Raten."""
    r = submissions['filings']['recent']
    hits = [r['accessionNumber'][i] for i in range(len(r['form'])) if r['form'][i] == form and r['reportDate'][i] == report_date]
    if len(hits) != 1:
        raise SystemExit(f'{form} {report_date}: {len(hits)} Treffer, keine eindeutige Zugangsnummer')
    return hits[0]


def get(url, ua, attempts=4):
    for attempt in range(attempts):
        req = urllib.request.Request(url, headers={'User-Agent': ua, 'Accept-Encoding': 'identity'})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            # SEC drosselt bei mehr als 10 Abrufen je Sekunde; dann warten und erneut versuchen.
            if e.code not in (403, 429, 503) or attempt == attempts - 1:
                raise
            time.sleep(5 * (attempt + 1))


def main(config, out):
    ua = os.environ.get('SEC_USER_AGENT', '')
    if '@' not in ua:
        raise SystemExit('SEC_USER_AGENT missing; never print its value')
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    manifest = []
    for f in json.loads(Path(config).read_text(encoding='utf-8'))['filings']:
        cik = str(int(f['cik']))
        acc = f.get('accession')
        if acc is None and f.get('form') and f.get('reportDate'):
            # Zugangsnummer im Workflow mit SEC_USER_AGENT ermitteln (Formular + Berichtsstichtag, eindeutig).
            acc = resolve(json.loads(get(SUBMISSIONS.format(int(cik)), ua)), f['form'], f['reportDate'])
            time.sleep(.5)
        if not accession_ok(acc or ''):
            raise SystemExit(f'bad accession {acc}')
        base = f'{ARCHIVE}{cik}/{acc.replace("-", "")}/'
        index = json.loads(get(base + 'index.json', ua))
        time.sleep(.5)
        for item in index['directory']['item']:
            name = item['name']
            if not KEEP.search(name) or SKIP.search(name):
                continue
            body = get(base + name, ua)
            time.sleep(.5)
            target = out / f'{f["label"]}__{acc}__{name}'
            target.write_bytes(body)
            manifest.append({'label': f['label'], 'accession': acc, 'url': base + name, 'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()})
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=1), encoding='utf-8')
    print(json.dumps({'documents': len(manifest)}))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
