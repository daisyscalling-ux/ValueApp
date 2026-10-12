"""Daily 21/63/126-session coverage, not verified investment outcomes."""
import argparse
import csv
import datetime as dt
import hashlib
import io
import json
from pathlib import Path
import zipfile

from free_sources import write_csv
from session_coverage import expected_sessions, inspect_rows

HORIZONS = (21, 63, 126)
COUNTS = ('expected_windows', 'pending_windows', 'mature_windows',
          'covered_windows', 'incomplete_windows', 'missing_entry_windows',
          'missing_path_windows', 'post_exit_mature_windows', 'post_exit_covered_windows',
          'nontradable_entry_windows')


def recovery_priorities(details, identities):
    """Rank gaps in the preselected primary horizon, not by observed performance."""
    metadata = {r['identity']:r for r in identities}
    groups = {}
    for row in details:
        groups.setdefault(row['identity'],{})[int(row['sessions'])] = row
    ranked = []
    for sid, horizons in groups.items():
        primary = horizons[63]
        if not any(int(r['incomplete_windows']) for r in horizons.values()):
            continue
        identity = metadata[sid]
        status = identity['status']
        if status.startswith('blocked'):
            action = 'Verify security identity before obtaining its historical series'
        elif status in ('missing_prices','insufficient_price_rows'):
            action = 'Obtain full historical adjusted series with identity and corporate-action evidence'
        else:
            action = 'Recover exact missing observations and verify adjacent daily returns'
        post_exit = int(primary['post_exit_mature_windows'])-int(primary['post_exit_covered_windows'])
        ranked.append(dict(identity=sid,identity_status=status,
                           incomplete_21=int(horizons[21]['incomplete_windows']),
                           incomplete_63=int(primary['incomplete_windows']),
                           incomplete_126=int(horizons[126]['incomplete_windows']),
                           incomplete_post_exit_63=post_exit,
                           last_index_exit=identity.get('last_index_exit',''),
                           exit_hint_unverified=identity.get('exit_reason',''),
                           next_data_step=action,
                           settlement_review_required=bool(post_exit),
                           # Index removal is not a delisting or a zero return.
                           settlement_note='Check continued trading or documented terminal proceeds; index exit alone proves neither' if post_exit else ''))
    ranked.sort(key=lambda r:(-r['incomplete_63'],-r['incomplete_126'],r['identity']))
    return [dict(priority=n,**r) for n,r in enumerate(ranked,1)]


def inspect_windows(sessions, spans, rows, start, horizons=HORIZONS, entry_before=None):
    """Next-close entry, then n returns. entry_before gates entries, not existing holdings."""
    _, missing_prices, missing_returns = inspect_rows(sessions, sessions, rows)
    bad_prices, bad_returns = set(missing_prices), set(missing_returns)
    prefix = [0]
    for day in sessions:
        prefix.append(prefix[-1] + (day in bad_returns))
    indices = {day:i for i,day in enumerate(sessions)}
    decisions = expected_sessions(sessions, [(max(a,start),b) for a,b in spans if b>start])
    totals = {n:dict.fromkeys(COUNTS,0) for n in horizons}
    examples = []
    for day in decisions:
        entry = indices[day]+1
        exit_day = next(b for a,b in spans if a<=day<b)
        for n in horizons:
            c = totals[n]; c['expected_windows'] += 1
            finish = entry+n
            if finish>=len(sessions):
                c['pending_windows'] += 1
                continue
            c['mature_windows'] += 1
            crossed = sessions[finish]>=exit_day
            c['post_exit_mature_windows'] += crossed
            missing_entry = sessions[entry] in bad_prices
            nontradable = entry_before is not None and sessions[entry]>=entry_before
            # entry+1 through finish inclusive, excluding entry-day return.
            missing_path = prefix[finish+1]-prefix[entry+1]>0
            c['missing_entry_windows'] += missing_entry
            c['missing_path_windows'] += missing_path
            c['nontradable_entry_windows'] += nontradable
            incomplete = missing_entry or missing_path or nontradable
            c['incomplete_windows'] += incomplete
            c['covered_windows'] += not incomplete
            c['post_exit_covered_windows'] += crossed and not incomplete
            if incomplete and len([e for e in examples if e['sessions']==n])<3:
                examples.append(dict(decision=day,entry=sessions[entry],end=sessions[finish],
                                     sessions=n,missing_entry=missing_entry,missing_path=missing_path,
                                     crosses_index_exit=crossed,nontradable_entry=nontradable))
    return totals, examples


def run(source, output):
    source, output = Path(source), Path(output)
    output.mkdir(parents=True,exist_ok=True)
    archive = zipfile.ZipFile(source) if source.is_file() else None
    def read(name):
        return archive.read(name).decode('utf-8-sig') if archive else (source/name).read_text(encoding='utf-8-sig')
    def table(name):
        return list(csv.DictReader(io.StringIO(read(name))))
    try:
        raw = json.loads(read('coverage.json'))
        end = dt.date.fromisoformat(raw['requested_end_exclusive'])
        try:
            start = end.replace(year=end.year-6).isoformat()
        except ValueError:
            start = end.replace(year=end.year-6,day=28).isoformat()
        start = max(start,raw['requested_start'])
        sessions = [r['date'] for r in table('session-review/handelskalender.csv')]
        if not sessions or sessions!=sorted(set(sessions)):
            raise ValueError('Missing or invalid session calendar')
        identities = table('identity-review/identitaetspruefung.csv')
        members = table('identity-review/mitglieder_korrigiert_vorlaeufig.csv')
        details, examples = [], []
        aggregate = {n:dict.fromkeys(COUNTS,0) for n in HORIZONS}
        for identity in identities:
            sid = identity['identity']
            spans = [(r['start'],r['end']) for r in members if r['symbol']==sid]
            # Prices after index deletion remain available; rejected identities do not.
            prices = table(identity['price_file']) if identity['price_file'] else []
            counts, gaps = inspect_windows(sessions,spans,prices,start)
            examples.extend(dict(identity=sid,**g) for g in gaps)
            for n,values in counts.items():
                details.append(dict(identity=sid,sessions=n,identity_status=identity['status'],**values))
                for k,v in values.items(): aggregate[n][k]+=v
        write_csv(output/'fenster_je_wertpapier.csv',details,list(details[0]))
        write_csv(output/'luecken_beispiele.csv',examples,
                  ['identity','decision','entry','end','sessions','missing_entry','missing_path','crosses_index_exit'])
        priorities = recovery_priorities(details,identities)
        write_csv(output/'datenbeschaffung_prioritaeten.csv',priorities,
                  list(priorities[0]) if priorities else ['priority','identity'])
        report = dict(decision_start_inclusive=start,end_exclusive=end.isoformat(),
                      decision_schedule='Every reference-calendar session during provisional membership',
                      entry_rule='Next session close; subsequent 21/63/126 daily returns',
                      source_generated_at=raw['generated_at'],horizons=aggregate,
                      identities_with_window_gaps=len(priorities),
                      priority_basis='Descending incomplete 63-session windows, then 126-session windows; no return-based selection',
                      identity_evidence_sha256=hashlib.sha256(read('identity-review/security_identity_evidence.json').encode()).hexdigest(),
                      production_eligible=False,complete_historical_universe_verified=False,
                      limitations=['Coverage only: no return estimates or calibrated risk probabilities.',
                                   'Pending windows have not matured; not provider failures.',
                                   'Memberships, identities, adjusted prices and terminal proceeds remain unverified.',
                                   'Overlapping daily windows are dependent, not independent observations.',
                                   'Missing-entry and missing-path counts can overlap.'])
        (output/'window_coverage.json').write_text(json.dumps(report,indent=2),encoding='utf8')
        return report
    finally:
        if archive: archive.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('source');parser.add_argument('output')
    args=parser.parse_args();print(json.dumps(run(args.source,args.output),indent=2))
