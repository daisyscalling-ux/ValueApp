"""Review multiple public captures against one immutable universe archive."""
import argparse
import copy
import csv
import datetime as dt
import hashlib
import io
import json
import math
from pathlib import Path
import zipfile

from free_sources import write_csv
from review_capture import capture_items, normalize_capture
from session_coverage import inspect_rows
from window_coverage import inspect_windows, recovery_priorities, HORIZONS, COUNTS


def prepare_capture(capture, sessions):
    """Quarantine missing/nonpositive volume; never turn placeholders into prices."""
    items=capture_items(capture)
    seen=set();kept=[];excluded=[]
    for original,item in zip(capture['rows'],items):
        day=item['date']
        if day in seen or day not in sessions:raise ValueError('Duplicate or non-session date')
        seen.add(day)
        try:volume=float(item['volume'])
        except (ValueError,TypeError):volume=None
        if volume is None or not math.isfinite(volume) or volume<=0:
            excluded.append(dict(date=day,reason='volume_missing_or_nonpositive',raw_row=original))
        else:kept.append(original)
    candidate=copy.deepcopy(capture);candidate['rows']=kept
    rows=normalize_capture(candidate,sessions)
    return rows,excluded,sorted(seen)


def apply_candidate(details, symbol, counts):
    """Replace the identity's three rows exactly once; preserve denominators."""
    selected=[r for r in details if r['identity']==symbol]
    if sorted(int(r['sessions']) for r in selected)!=list(HORIZONS):
        raise ValueError('Missing or ambiguous baseline identity')
    for row in selected:
        n=int(row['sessions'])
        for key in ('expected_windows','pending_windows','mature_windows'):
            if int(row[key])!=counts[n][key]:raise ValueError('Denominator changed')
    for row in selected:
        n=int(row['sessions'])
        row.update(counts[n]);row['price_source_status']='public_capture_candidate'


def run(archive_path,capture_paths,output):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    paths=[Path(p) for p in capture_paths]
    captures=[json.loads(p.read_text(encoding='utf8')) for p in paths]
    symbols=[c['symbol'] for c in captures]
    if len(symbols)!=len(set(symbols)):raise ValueError('Duplicate capture identity')
    with zipfile.ZipFile(archive_path) as archive:
        def table(name):return list(csv.DictReader(io.StringIO(archive.read(name).decode('utf-8-sig'))))
        raw=json.loads(archive.read('coverage.json'))
        sessions=[r['date'] for r in table('session-review/handelskalender.csv')]
        if not sessions or sessions!=sorted(set(sessions)):raise ValueError('Invalid calendar')
        identities=table('identity-review/identitaetspruefung.csv')
        metadata={r['identity']:r for r in identities}
        members=table('identity-review/mitglieder_korrigiert_vorlaeufig.csv')
        end=dt.date.fromisoformat(raw['requested_end_exclusive'])
        try:start=end.replace(year=end.year-6).isoformat()
        except ValueError:start=end.replace(year=end.year-6,day=28).isoformat()
        start=max(start,raw['requested_start'])
        details=[];reports=[]
        for identity in identities:
            sid=identity['identity'];spans=[(r['start'],r['end']) for r in members if r['symbol']==sid]
            prices=table(identity['price_file']) if identity['price_file'] else []
            counts,_=inspect_windows(sessions,spans,prices,start)
            details.extend(dict(identity=sid,sessions=n,identity_status=identity['status'],
                                price_source_status='baseline',**c) for n,c in counts.items())
        baseline=copy.deepcopy(details)
        for path,capture in zip(paths,captures):
            sid=capture['symbol'];identity=metadata.get(sid)
            if not identity or identity['status'].startswith('blocked'):
                reports.append(dict(symbol=sid,status='rejected_identity',production_eligible=False));continue
            try:
                rows,excluded,observed=prepare_capture(capture,sessions)
                expected=[d for d in sessions if observed[0]<=d<=observed[-1]]
                checks,missing,invalid=inspect_rows(sessions,expected,rows)
                spans=[(r['start'],r['end']) for r in members if r['symbol']==sid]
                counts,_=inspect_windows(sessions,spans,rows,start)
                apply_candidate(details,sid,counts)
                folder=output/'candidates'/sid;folder.mkdir(parents=True,exist_ok=True)
                write_csv(folder/'prices.csv',rows,list(rows[0]))
                report=dict(symbol=sid,status='reviewed_candidate',rows=len(rows),
                    first=rows[0]['Datum'],last=rows[-1]['Datum'],checks=checks,
                    missing_prices=missing,invalid_returns=invalid,quarantined_rows=excluded,
                    source=capture['source'],captured_at=capture['captured_at'],
                    capture_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                    candidate_prices_sha256=hashlib.sha256((folder/'prices.csv').read_bytes()).hexdigest(),
                    horizons=counts,production_eligible=False)
                (folder/'review.json').write_text(json.dumps(report,indent=2),encoding='utf8')
                reports.append(report)
            except (ValueError,KeyError,TypeError) as exc:
                reports.append(dict(symbol=sid,status='rejected_capture',reason=str(exc),production_eligible=False))
        def aggregate(data):
            return {n:{key:sum(int(r[key]) for r in data if int(r['sessions'])==n) for key in COUNTS} for n in HORIZONS}
        before,after=aggregate(baseline),aggregate(details)
        priorities=recovery_priorities(details,identities)
        write_csv(output/'fenster_je_wertpapier.csv',details,list(details[0]))
        write_csv(output/'offene_datenluecken.csv',priorities,list(priorities[0]) if priorities else ['identity'])
        report=dict(schema=1,archive_sha256=hashlib.sha256(Path(archive_path).read_bytes()).hexdigest(),
            source_generated_at=raw['generated_at'],decision_start=start,end_exclusive=end.isoformat(),
            captures=reports,baseline=before,candidate=after,
            additional_covered_windows={n:after[n]['covered_windows']-before[n]['covered_windows'] for n in HORIZONS},
            production_eligible=False,raw_archive_modified=False,
            limitations=['Each complete candidate series replaces its baseline for this comparison only; no stitching.',
                         'Rounded provider-adjusted prices and security identities are not independently certified.',
                         'Missing companies and post-exit periods stay in the denominator.',
                         'No terminal proceeds or successor prices were inserted.',
                         'Overlapping windows are not independent samples; coverage is not model validation.'])
        (output/'batch_review.json').write_text(json.dumps(report,indent=2),encoding='utf8')
        return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('archive');p.add_argument('output');p.add_argument('captures',nargs='+')
    a=p.parse_args();r=run(a.archive,a.captures,a.output)
    print(json.dumps({k:r[k] for k in ('additional_covered_windows','production_eligible')}))
