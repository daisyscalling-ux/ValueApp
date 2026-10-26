"""Consume risk coverage priorities without starving newly registered listings."""
import datetime as dt
import json
from pathlib import Path

def timestamp(value):
    try:
        parsed=dt.datetime.fromisoformat(value.replace('Z','+00:00'))
        return (parsed if parsed.tzinfo else parsed.replace(tzinfo=dt.timezone.utc)).timestamp()
    except (TypeError, ValueError, AttributeError):
        return 0

def order_rows(rows, index, queue_path, now):
    try:
        queue=json.loads(Path(queue_path).read_text(encoding='utf8'))
    except (OSError, ValueError):
        queue={}
    valid=queue.get('schema')==1 and 0<=now-timestamp(queue.get('generatedAt'))<7*86400
    priority={j['symbol']:i for i,j in enumerate(queue.get('jobs',[]) if valid else [])
              if j.get('kind')=='fundamentals' and j.get('state')=='queued'}
    def rank(row):
        key=row.get('listing_symbol') or row['ticker']
        last=timestamp(index.get('attempts',{}).get(key))
        return (0 if not last or now-last>7*86400 else 1,priority.get(key,10**9),last,key)
    return sorted(rows,key=rank)

def due(failure, now):
    t=timestamp((failure or {}).get('next_attempt_at'))
    return t<=now or t>now+8*86400

def failed(previous, reason, stamp, now):
    count=min(20,((previous or {}).get('count',0) if (previous or {}).get('reason')==reason else 0)+1)
    hours=168 if reason=='mapping' else min(72,2**count)
    return {'at':stamp,'reason':reason,'count':count,
            'next_attempt_at':dt.datetime.fromtimestamp(now+hours*3600,dt.timezone.utc).isoformat()}


def annual_supply_status(data, now):
    """A successful market-data request does not renew an older annual block."""
    annual=data.get('annual') or {}
    observed=data.get('annual_retrieved_at') or data.get('retrieved_at')
    retrieved=timestamp(observed);period=timestamp(annual.get('end'))
    field_dates={k:timestamp(v.get('retrieved_at')) for k,v in (annual.get('field_sources') or {}).items() if isinstance(v,dict) and v.get('retrieved_at')}
    expires=min([retrieved+7*86400,period+550*86400]+[v+7*86400 for v in field_dates.values() if v]) if retrieved and period else None
    retained=bool(retrieved and timestamp(data.get('retrieved_at'))>retrieved)
    fresh=bool(annual and expires and retrieved<=now and period<=now and now<=expires and all(0<v<=now for v in field_dates.values()))
    return {'state':'current' if fresh else 'retained_stale' if annual and retained else 'annual_invalid_or_stale' if annual else 'annual_missing',
            'annualObservedAt':observed if annual else None,'period':annual.get('end'),
            'expiresAt':dt.datetime.fromtimestamp(expires,dt.timezone.utc).isoformat() if expires else None,
            'retained':retained,'freshAnnualReturned':fresh and not retained and not any(v<retrieved for v in field_dates.values()),'retainedFields':sorted(k for k,v in field_dates.items() if v<retrieved)}
