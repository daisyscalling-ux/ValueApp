"""Offline review of a saved public issuer table. Never changes the raw archive."""
import argparse
import csv
import datetime as dt
import hashlib
import io
import json
import math
from pathlib import Path
from urllib.parse import urlparse
import zipfile

from free_sources import research_id, write_csv
from session_coverage import inspect_rows
from window_coverage import inspect_windows


def normalize_capture(capture, sessions):
    if capture['adjustment'] != 'Adjusted: Splits and Dividends' or capture['currency']!='USD':
        raise ValueError('Unsupported or unconfirmed adjustment/currency')
    source = urlparse(capture['source'])
    if source.scheme!='https' or not source.hostname or source.username or source.password:
        raise ValueError('Public HTTPS source required')
    previous_session = dict(zip(sessions[1:],sessions))
    rows=[];seen=set();previous=None
    for item in sorted(capture['rows'],key=lambda r:r['date']):
        day=item['date'];price=float(item['close']);volume=float(item['volume'])
        if dt.date.fromisoformat(day).isoformat()!=day or day in seen or day not in sessions:
            raise ValueError('Duplicate or non-session date')
        if not math.isfinite(price) or price<=0 or not math.isfinite(volume) or volume<=0:
            raise ValueError('Invalid price or non-trading observation')
        seen.add(day)
        value = price/previous[1]-1 if previous and previous[0]==previous_session.get(day) else None
        rows.append(dict(Research_ID=research_id(capture['symbol']),Symbol=capture['symbol'],
                         Datum=day,Adjusted_Close=str(price),
                         Tagesrendite=str(value) if value is not None else '',
                         Quelle=capture['source'],Anbieter=capture['provider'],
                         Identitaet='issuer_table_candidate_not_independently_verified',
                         Abwicklung_bestaetigt=False))
        previous=(day,price)
    if len(rows)<2:raise ValueError('Insufficient observations')
    return rows


def review(capture_path, archive_path, output):
    capture_path, output=Path(capture_path),Path(output)
    raw=capture_path.read_bytes();capture=json.loads(raw)
    with zipfile.ZipFile(archive_path) as archive:
        def table(name):return list(csv.DictReader(io.StringIO(archive.read(name).decode('utf-8-sig'))))
        coverage=json.loads(archive.read('coverage.json'))
        sessions=[r['date'] for r in table('session-review/handelskalender.csv')]
        if not sessions or sessions!=sorted(set(sessions)):raise ValueError('Invalid reference calendar')
        identities=table('identity-review/identitaetspruefung.csv')
        identity=next((r for r in identities if r['identity']==capture['symbol']),None)
        if not identity or identity['status'].startswith('blocked'):
            raise ValueError('Identity requires separate review')
        spans=[(r['start'],r['end']) for r in table('identity-review/mitglieder_korrigiert_vorlaeufig.csv')
               if r['symbol']==capture['symbol']]
        original=table(identity['price_file']) if identity['price_file'] else []
        end=dt.date.fromisoformat(coverage['requested_end_exclusive'])
        try:start=end.replace(year=end.year-6).isoformat()
        except ValueError:start=end.replace(year=end.year-6,day=28).isoformat()
        start=max(start,coverage['requested_start'])
        rows=normalize_capture(capture,sessions)
        expected=[d for d in sessions if rows[0]['Datum']<=d<=rows[-1]['Datum']]
        checks,missing,bad_returns=inspect_rows(sessions,expected,rows)
        before,_=inspect_windows(sessions,spans,original,start)
        after,_=inspect_windows(sessions,spans,rows,start)
        report=dict(symbol=capture['symbol'],source=capture['source'],provider=capture['provider'],
                    captured_at=capture['captured_at'],capture_sha256=hashlib.sha256(raw).hexdigest(),
                    rows=len(rows),first=rows[0]['Datum'],last=rows[-1]['Datum'],
                    series_checks=checks,missing_prices=missing,missing_or_invalid_returns=bad_returns,
                    baseline_windows=before,candidate_windows=after,production_eligible=False,
                    automatically_imported=False,
                    limitations=['Candidate replaces, never stitches, the baseline in this comparison only.',
                                 'Issuer widget declares split/dividend adjustment; not independently certified.',
                                 'No terminal proceeds or successor returns have been added.',
                                 'Public browser availability does not establish an automated API entitlement.'])
        output.mkdir(parents=True,exist_ok=True)
        write_csv(output/'candidate_prices.csv',rows,list(rows[0]))
        (output/'capture_review.json').write_text(json.dumps(report,indent=2),encoding='utf8')
        return report


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('capture');p.add_argument('archive');p.add_argument('output')
    a=p.parse_args();print(json.dumps(review(a.capture,a.archive,a.output),indent=2))

