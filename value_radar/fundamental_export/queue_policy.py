"""Consume risk coverage priorities without starving newly registered listings."""
import datetime as dt
import json
from pathlib import Path

def timestamp(value):
    try:
        return dt.datetime.fromisoformat(value.replace('Z','+00:00')).timestamp()
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
