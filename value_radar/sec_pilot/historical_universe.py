"""Audit a normalized historical provider export before any survivor-aware study.

This validates the declared dataset, not the provider's completeness claim.
No fabricated return paths, ticker joins, or automatic score changes.
"""
import argparse
import datetime as dt
import hashlib
import json
import math
from pathlib import Path

def date(value):
    parsed = dt.date.fromisoformat(value)
    if parsed.isoformat() != value:
        raise ValueError('Dates must use YYYY-MM-DD')
    return value

def finite(value):
    return not isinstance(value, bool) and isinstance(value, (float, int)) and math.isfinite(value)

def source(row):
    return isinstance(row.get('source'), str) and row['source'].startswith('https://')

def validate(data):
    if data.get('schema') != 1:
        raise ValueError('Unsupported schema')
    coverage = data['coverage']
    start, end = date(coverage['start']), date(coverage['end'])
    if start >= end or not source(coverage):
        raise ValueError('Coverage interval or source missing')
    securities = data['securities']
    if not securities or any(not isinstance(k, str) or not k or not source(v) for k,v in securities.items()):
        raise ValueError('Stable security IDs and security sources required')
    intervals = {}
    for row in data['memberships']:
        sid = row['security_id']; a = date(row['start']); b = date(row['end'])
        if sid not in securities or a >= b or not source(row):
            raise ValueError('Invalid membership interval')
        intervals.setdefault(sid, []).append((a,b))
    if not intervals:
        raise ValueError('No memberships: an empty universe is not complete')
    for spans in intervals.values():
        spans.sort()
        if any(b > next_a for (_,b),(next_a,_) in zip(spans,spans[1:])):
            raise ValueError('Overlapping or duplicate memberships')
    sessions = [date(x) for x in data['sessions']]
    if not sessions or sessions != sorted(set(sessions)):
        raise ValueError('Trading sessions must be unique and increasing')
    if any((dt.date.fromisoformat(b)-dt.date.fromisoformat(a)).days > 7 for a,b in zip(sessions,sessions[1:])):
        raise ValueError('Trading calendar gap requires review')
    decisions = [date(x) for x in data['decisions']]
    if not decisions or decisions != sorted(set(decisions)) or any(x not in sessions or not start <= x < end for x in decisions):
        raise ValueError('Invalid or empty decision schedule')
    paths = {}
    for row in data['returns']:
        sid, day, value = row['security_id'], date(row['date']), row['total_return']
        key = (sid,day)
        if sid not in securities or day not in sessions or key in paths or not finite(value) or value < -1 or not source(row):
            raise ValueError('Invalid, duplicate or unreferenced total return')
        paths[key] = value
    return intervals, sessions, decisions, paths

def audit(data):
    intervals, sessions, decisions, paths = validate(data)
    coverage=data['coverage']; securities=data['securities']; rows=[]; gaps=[]
    if coverage.get('membership_completeness') != 'provider_attested':
        gaps.append({'reason':'historical membership completeness not attested'})
    if coverage.get('return_basis') != 'total_return_including_delisting':
        gaps.append({'reason':'total-return and delisting adjustment basis unconfirmed'})
    expected=0
    for decision in decisions:
        i=sessions.index(decision)
        members=sorted(sid for sid,spans in intervals.items() if any(a <= decision < b for a,b in spans))
        if not members:gaps.append({'date':decision,'reason':'no members at decision'})
        for sid in members:
            # Membership is checked at decision, not at the outcome end.
            for horizon,n in [(1,21),(3,63),(6,126)]:
                expected+=1
                base={'security_id':sid,'date':decision,'horizon':horizon}
                entry=i+1; finish=entry+n
                if finish >= len(sessions):
                    gaps.append(dict(base,reason='outcome calendar incomplete'));continue
                base.update(entry=sessions[entry],end=sessions[finish])
                security=securities[sid]; termination=security.get('termination_date')
                if termination:
                    date(termination)
                    if termination <= sessions[entry]:
                        gaps.append(dict(base,reason='security terminated before entry'));continue
                    if termination <= sessions[finish] and (not security.get('terminal_source','').startswith('https://') or security.get('terminal_adjustment')!='included_in_total_return'):
                        gaps.append(dict(base,reason='terminal proceeds or successor treatment unconfirmed'));continue
                days=sessions[entry+1:finish+1]
                if any((sid,d) not in paths for d in days):
                    gaps.append(dict(base,reason='return path incomplete; never fill with zero'));continue
                wealth=peak=1.0;loss=drawdown=0.0
                for day in days:
                    wealth*=1+paths[(sid,day)]
                    peak=max(peak,wealth);loss=max(loss,1-wealth);drawdown=max(drawdown,1-wealth/peak)
                if not math.isfinite(wealth):
                    gaps.append(dict(base,reason='return path overflow'));continue
                rows.append(dict(base,loss=loss,drawdown=drawdown,**{'return':wealth-1}))
    return {'schema':1,'status':'incomplete' if gaps else 'ready_for_feature_join',
            'expected_windows':expected,'usable_windows':len(rows),'gaps':gaps,'observations':rows,
            'complete_historical_universe_verified':False,
            'limitations':['Technical validation of supplied evidence only; provider completeness needs independent review.',
                           'Requires subsequent point-in-time features and chronological out-of-sample evaluation.',
                           'Index deletion is not liquidation. No return imputation or successor-price stitching.']}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('input');parser.add_argument('--output',required=True)
    args=parser.parse_args();raw=Path(args.input).read_bytes()
    try:
        report=audit(json.loads(raw))
    except (KeyError,ValueError,TypeError) as exc:
        report={'status':'invalid_input','error':str(exc),'complete_historical_universe_verified':False}
    report['input_sha256']=hashlib.sha256(raw).hexdigest()
    Path(args.output).write_text(json.dumps(report,indent=2,allow_nan=False),encoding='utf8')
    print(report['status'])
    return 0 if report['status']=='ready_for_feature_join' else 2

if __name__=='__main__':raise SystemExit(main())
