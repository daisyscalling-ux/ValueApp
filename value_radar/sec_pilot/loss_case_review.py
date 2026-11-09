"""Evidence collection for index exits after price decline or failure.

Collects SEC identity/delisting filings and candidate Yahoo series for review.
Never edits security_identity_evidence.json and never admits a series automatically.
"""
import argparse
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import re
import time
import urllib.error
import urllib.request

from free_sources import write_csv

CANDIDATES = Path(__file__).with_name('loss_case_candidates.json')
# Filing types that can document listing status, ticker changes or the terminal path.
STATUS_FORMS = {'25', '25-NSE', '15-12B', '15-12G', '15-15D'}
STATUS_8K_ITEMS = {'1.03': 'bankruptcy_or_receivership', '2.01': 'acquisition_or_disposition_completed',
                   '3.01': 'delisting_or_listing_rule_notice', '3.03': 'material_modification_of_rights',
                   '5.03': 'charter_or_bylaw_amendment'}
MAX_GAP_DAYS = 7


def sec_filings(submissions, cik):
    """Status-relevant filings from an SEC submissions document, newest first."""
    recent = submissions.get('filings', {}).get('recent', {})
    keys = ('form', 'filingDate', 'accessionNumber', 'primaryDocument', 'items')
    columns = [recent.get(k, []) for k in keys]
    found = []
    for form, day, accession, document, items in zip(*[c + [''] * (len(columns[0]) - len(c)) for c in columns]):
        codes = [i.strip() for i in str(items or '').split(',') if i.strip()]
        relevant = [STATUS_8K_ITEMS[c] for c in codes if c in STATUS_8K_ITEMS] if form.startswith('8-K') else []
        if form in STATUS_FORMS or relevant:
            folder = accession.replace('-', '')
            found.append(dict(form=form, filing_date=day, accession=accession, items=';'.join(codes),
                              meaning=';'.join(relevant) or 'listing_or_registration_status',
                              url=f'https://www.sec.gov/Archives/edgar/data/{int(cik)}/{folder}/{document}'))
    return found


def sec_identity(submissions, pattern):
    names = [submissions.get('name', '')] + [n.get('name', '') for n in submissions.get('formerNames', [])]
    return dict(sec_name=submissions.get('name', ''), former_names=';'.join(n for n in names[1:] if n),
                sec_tickers=';'.join(submissions.get('tickers', [])),
                sec_exchanges=';'.join(e or '' for e in submissions.get('exchanges', [])),
                sec_name_match=any(re.search(pattern, n, re.I) for n in names if n))


def series_check(rows, metadata, pattern, start, exit_day):
    """Describe one provider series. rows: [(iso_date, adjusted_close)] ascending."""
    name = metadata.get('longName') or metadata.get('shortName') or ''
    out = dict(provider_symbol=metadata.get('symbol', ''), provider_name=name,
               instrument=metadata.get('instrumentType', ''), currency=metadata.get('currency', ''),
               exchange=metadata.get('exchangeName', ''), rows=len(rows),
               first=rows[0][0] if rows else '', last=rows[-1][0] if rows else '',
               name_match=bool(name) and bool(re.search(pattern, name, re.I)))
    valid = [(d, p) for d, p in rows if p is not None and math.isfinite(p) and p > 0]
    out['invalid_prices'] = len(rows) - len(valid)
    days = [dt.date.fromisoformat(d) for d, _ in valid]
    gaps = [(a, b) for a, b in zip(days, days[1:]) if (b - a).days > MAX_GAP_DAYS]
    out['gaps_over_7_days'] = len(gaps)
    widest = max(gaps, key=lambda g: (g[1] - g[0]).days, default=None)
    out['largest_gap'] = f'{widest[0]}..{widest[1]}' if widest else ''
    out['rows_before_exit'] = sum(start <= d < exit_day for d, _ in valid)
    out['rows_after_exit'] = sum(d >= exit_day for d, _ in valid)
    out['covers_decision_start'] = bool(valid) and valid[0][0] <= start
    out['last_price'] = valid[-1][1] if valid else None
    out['basic_checks_passed'] = (out['name_match'] and out['instrument'] == 'EQUITY' and out['currency'] == 'USD'
                                  and not out['invalid_prices'] and out['covers_decision_start'] and out['rows_before_exit'] > 0)
    return out


EXCERPT_TERMS = re.compile(r'converted into|right to receive|per share|in cash|exchange ratio|trading symbol|ticker symbol|'
                           r'symbol\s+[“"]|OTC|suspend|delist|receivership|chapter 11', re.I)


def terminal_filings(filings, decision_start, limit=3):
    """8-Ks documenting a delisting notice or bankruptcy since the decision start, newest first."""
    chosen = [f for f in filings if f['form'].startswith('8-K') and f['filing_date'] >= decision_start
              and ({'1.03', '3.01'} & set(f['items'].split(';')))]
    return chosen[:limit]


def excerpts(html, max_sentences=8, max_chars=400):
    """Plain-text sentences with settlement or listing terms; for reading, not for parsing amounts."""
    text = re.sub(r'(?is)<(script|style).*?</\1>', ' ', html)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'&nbsp;|&#160;|&#xa0;', ' ', text, flags=re.I)
    text = re.sub(r'&amp;', '&', re.sub(r'&#8217;|&rsquo;', "'", re.sub(r'&#822[01];|&[lr]dquo;', '"', text)))
    text = re.sub(r'\s+', ' ', text).strip()
    found = []
    for sentence in re.split(r'(?<=[.;])\s+(?=[A-Z(])', text):
        sentence = sentence.strip()[:max_chars]
        if EXCERPT_TERMS.search(sentence) and sentence not in found:
            found.append(sentence)
        if len(found) >= max_sentences:
            break
    return found


def fetch_document(url, user_agent, raw_dir):
    req = urllib.request.Request(url, headers={'User-Agent': user_agent})
    with urllib.request.urlopen(req, timeout=20) as response:
        raw = response.read(5_000_001)
    if len(raw) > 5_000_000:
        raise ValueError('SEC document too large')
    (raw_dir / ('sec-' + url.rstrip('/').split('/')[-2] + '-' + url.split('/')[-1])).write_bytes(raw)
    time.sleep(0.6)
    return raw.decode('utf-8', errors='replace'), hashlib.sha256(raw).hexdigest()


def case_status(case, sec, series):
    if case.get('cik') and sec is None:
        return 'sec_unavailable_retry'
    if sec is not None and not sec['sec_name_match']:
        return 'sec_identity_mismatch_review_cik'
    usable = [s for s in series if s.get('basic_checks_passed')]
    if not usable:
        return 'no_matching_series'
    if any(s['gaps_over_7_days'] for s in usable):
        return 'series_found_with_gaps_review_required'
    return 'series_found_review_required'


def fetch_sec(cik, user_agent, raw_dir):
    url = f'https://data.sec.gov/submissions/CIK{cik}.json'
    req = urllib.request.Request(url, headers={'User-Agent': user_agent, 'Accept': 'application/json'})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=20) as response:
                raw = response.read(20_000_001)
            break
        except urllib.error.HTTPError as exc:
            if exc.code in (429, 500, 502, 503) and attempt < 2:
                time.sleep(5 * (attempt + 1)); continue
            raise
    if len(raw) > 20_000_000:
        raise ValueError('SEC response too large')
    (raw_dir / f'sec-CIK{cik}.json').write_bytes(raw)
    time.sleep(0.6)
    return json.loads(raw), hashlib.sha256(raw).hexdigest(), url


def fetch_yahoo(symbol, start, raw_dir):
    import yfinance as yf
    ticker = yf.Ticker(symbol)
    frame = ticker.history(start=start, auto_adjust=False, repair=False, actions=True, timeout=15, raise_errors=True)
    metadata = ticker.get_history_metadata()
    rows = [(i.date().isoformat(), float(r['Adj Close'])) for i, r in frame.iterrows()] if 'Adj Close' in frame else []
    frame.to_csv(raw_dir / f'yahoo-{symbol}.csv')
    return rows, metadata


def review(candidates, output, sec_fetch, yahoo_fetch, pause=3.0, document_fetch=None):
    output = Path(output); raw = output / 'raw'; raw.mkdir(parents=True, exist_ok=True)
    start = candidates['decision_start']
    cases, series_rows, filing_rows, excerpt_rows = [], [], [], []
    for case in candidates['cases']:
        sec, sec_error, sec_hash = None, '', ''
        if case.get('cik'):
            try:
                submissions, sec_hash, _ = sec_fetch(case['cik'], raw)
                sec = sec_identity(submissions, case['name_pattern'])
                filings = sec_filings(submissions, case['cik'])
                for f in filings:
                    filing_rows.append(dict(identity=case['identity'], cik=case['cik'], **f))
                for f in terminal_filings(filings, start) if document_fetch else []:
                    try:
                        html, digest = document_fetch(f['url'], raw)
                        found, error = excerpts(html), ''
                    except Exception as exc:
                        found, digest, error = [], '', type(exc).__name__
                    for n, sentence in enumerate(found or [''], 1):
                        excerpt_rows.append(dict(identity=case['identity'], filing_date=f['filing_date'], items=f['items'],
                                                 url=f['url'], sha256=digest, n=n if found else 0, excerpt=sentence, error=error))
            except Exception as exc:
                sec_error = type(exc).__name__
        series = []
        for symbol in case['yahoo_candidates']:
            try:
                rows, metadata = yahoo_fetch(symbol, start, raw)
                result = series_check(rows, metadata, case['name_pattern'], start, case['last_index_exit'])
                result['error'] = ''
            except Exception as exc:
                result = dict(provider_symbol='', rows=0, basic_checks_passed=False, error=type(exc).__name__)
            result.update(identity=case['identity'], requested_symbol=symbol)
            series.append(result); series_rows.append(result)
            time.sleep(pause)
        status = case_status(case, sec, series)
        cases.append(dict(identity=case['identity'], group=case['group'], last_index_exit=case['last_index_exit'],
                          status=status, cik=case.get('cik') or '', sec_sha256=sec_hash, sec_error=sec_error,
                          status_filings=sum(r['identity'] == case['identity'] for r in filing_rows),
                          usable_series=';'.join(s['requested_symbol'] for s in series if s.get('basic_checks_passed')),
                          note=case.get('regulator_note') or case.get('successor_note') or '',
                          **(sec or {})))
    series_fields = ['identity', 'requested_symbol', 'provider_symbol', 'provider_name', 'instrument', 'currency', 'exchange',
                     'rows', 'first', 'last', 'rows_before_exit', 'rows_after_exit', 'covers_decision_start',
                     'gaps_over_7_days', 'largest_gap', 'invalid_prices', 'last_price', 'name_match', 'basic_checks_passed', 'error']
    write_csv(output / 'faelle.csv', cases, list(cases[0]) if cases else ['identity'])
    write_csv(output / 'kursreihen_kandidaten.csv', series_rows, series_fields)
    write_csv(output / 'sec_statusmeldungen.csv', filing_rows,
              ['identity', 'cik', 'form', 'filing_date', 'accession', 'items', 'meaning', 'url'])
    write_csv(output / 'abschlussmeldungen_auszuege.csv', excerpt_rows,
              ['identity', 'filing_date', 'items', 'url', 'sha256', 'n', 'excerpt', 'error'])
    report = dict(generated_at=dt.datetime.now(dt.timezone.utc).isoformat(), candidates_sha256=hashlib.sha256(
                      json.dumps(candidates, sort_keys=True).encode()).hexdigest(),
                  cases=len(cases), status_counts={s: sum(c['status'] == s for c in cases) for s in sorted({c['status'] for c in cases})},
                  admitted_automatically=0, production_eligible=False,
                  limitations=['Kandidatenreihen sind Anbieterwerte ohne archivierte Point-in-Time-Version.',
                               'Namensgleichheit belegt keine identische Aktiengattung; Uebernahme in security_identity_evidence.json erst nach Pruefung der verlinkten Meldungen.',
                               'OTC-Kurse nach einer Insolvenz koennen illiquide sein und sind keine Abwicklungserloese.',
                               'Fehlende Reihe bedeutet nicht Totalverlust; keine Nullfortschreibung.'])
    (output / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf8')
    return report, cases


def detail_markdown(output):
    """Series and filing tables, so the review is readable without the artifact."""
    import csv
    def table(name):
        with open(Path(output) / name, encoding='utf-8-sig') as stream:
            return list(csv.DictReader(stream))
    lines = ['', '### Kursreihen-Kandidaten', '',
             '| Angefragt | Anbietername | Boerse | Zeilen | Von | Bis | Vor Austritt | Nach Austritt | Luecken >7T | Groesste Luecke | Pruefung | Fehler |',
             '|---|---|---|---:|---|---|---:|---:|---:|---|---|---|']
    for r in table('kursreihen_kandidaten.csv'):
        lines.append('| ' + ' | '.join(str(r.get(k) or '-') for k in (
            'requested_symbol', 'provider_name', 'exchange', 'rows', 'first', 'last', 'rows_before_exit',
            'rows_after_exit', 'gaps_over_7_days', 'largest_gap', 'basic_checks_passed', 'error')) + ' |')
    lines += ['', '### SEC-Statusmeldungen', '', '| Wertpapier | Formular | Datum | Bedeutung | Beleg |', '|---|---|---|---|---|']
    for r in table('sec_statusmeldungen.csv'):
        lines.append(f"| {r['identity']} | {r['form']} | {r['filing_date']} | {r['meaning']} | {r['url']} |")
    excerpt_file = Path(output) / 'abschlussmeldungen_auszuege.csv'
    if excerpt_file.exists():
        lines += ['', '### Auszuege aus Delisting- und Insolvenzmeldungen (ungeprueft, nur zum Lesen)', '']
        current = None
        for r in table(excerpt_file.name):
            if r['url'] != current:
                current = r['url']
                lines += ['', f"**{r['identity']} · 8-K {r['filing_date']} · Items {r['items']}** {r['url']}" + (f" · Fehler: {r['error']}" if r['error'] else '')]
            if r['excerpt']:
                lines.append('- ' + r['excerpt'].replace('|', '/'))
    return '\n'.join(lines) + '\n'


def summary_markdown(report, cases):
    lines = ['## Pruefung Kursverfall- und Insolvenzfaelle', '',
             f"{report['cases']} Faelle, automatisch uebernommen: {report['admitted_automatically']}", '',
             '| Wertpapier | Gruppe | Status | Nutzbare Reihen | SEC-Name | Statusmeldungen |', '|---|---|---|---|---|---:|']
    for c in cases:
        lines.append(f"| {c['identity']} | {c['group']} | {c['status']} | {c['usable_series'] or '-'} | {c.get('sec_name') or c['note'] or '-'} | {c['status_filings']} |")
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('output', nargs='?', default='loss-case-output')
    args = parser.parse_args()
    user_agent = os.environ.get('SEC_USER_AGENT', '')
    if '@' not in user_agent:
        raise SystemExit('Set SEC_USER_AGENT to application name and real contact email.')
    candidates = json.loads(CANDIDATES.read_text(encoding='utf8'))
    report, cases = review(candidates, args.output, lambda cik, raw: fetch_sec(cik, user_agent, raw), fetch_yahoo,
                           document_fetch=lambda url, raw: fetch_document(url, user_agent, raw))
    markdown = summary_markdown(report, cases) + detail_markdown(args.output)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf8') as stream:
            stream.write(markdown)
    print(markdown)
    print(json.dumps(report['status_counts']))


if __name__ == '__main__':
    main()
