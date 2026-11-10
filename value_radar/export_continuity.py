"""Keep dated observations across bounded scans, never turn cached data into fresh data."""
import datetime as dt
import json
import subprocess
from pathlib import Path
from listing_identity import listing_matches
from listing_reference import apply_reference


def stamp(value):
    try:
        return dt.datetime.strptime(value, '%Y-%m-%d %H:%M UTC').replace(tzinfo=dt.timezone.utc)
    except (ValueError, TypeError):
        return None


def snapshots(path):
    """Recent committed snapshots can recover rows lost by a previous partial export."""
    path=Path(path).resolve()
    result=[]
    if path.exists():
        result.append(json.loads(path.read_text(encoding='utf-8-sig')))
    try:
        root=subprocess.run(['git','rev-parse','--show-toplevel'],cwd=path.parent,capture_output=True,text=True,check=True,timeout=10).stdout.strip()
        rel=path.relative_to(Path(root).resolve()).as_posix()
        refs=subprocess.run(['git','log','-12','--format=%H','--',rel],cwd=root,capture_output=True,text=True,check=True,timeout=10).stdout.split()
        for ref in refs:
            raw=subprocess.run(['git','show',ref+':'+rel],cwd=root,capture_output=True,text=True,encoding='utf-8',check=True,timeout=15).stdout
            result.append(json.loads(raw))
    except (OSError, ValueError, subprocess.SubprocessError):
        # A shallow checkout still preserves its current snapshot.
        pass
    return result


def baseline(universe, documents, now):
    wanted=set(universe); saved={}; conflicts=set()
    for doc in documents:
        for row in doc.get('kandidaten',[]):
            # Gepruefte Notierungskorrekturen (z. B. H- statt A-ISIN) auch auf alte Snapshots anwenden,
            # sonst gilt die Korrektur selbst als Identitaetswechsel und die Notierung faellt heraus.
            row=apply_reference(dict(row),now.date())
            ticker=row.get('ticker')
            if ticker not in wanted or not row.get('isin') or not listing_matches(ticker,row.get('listing_symbol')):
                continue
            if row.get('listing_reference_status') in ('expired','input_mismatch'):
                continue
            observed=row.get('export_observed_at') or doc.get('stand')
            when=stamp(observed)
            if when is None or not 0 <= (now-when).total_seconds() <= 14*86400:
                continue
            old=saved.get(ticker)
            # Snapshots arrive newest first: never resurrect a changed security identity.
            if old and (old['isin'],old['listing_symbol'],old.get('currency')) != (row['isin'],row['listing_symbol'],row.get('currency')):
                conflicts.add(ticker);continue
            if old and stamp(old['export_observed_at'])>=when:continue
            saved[ticker]={**row,'export_observed_at':observed,'export_status':'retained'}
    for ticker in conflicts:saved.pop(ticker,None)
    return saved


def scan_order(universe, saved):
    return sorted(dict.fromkeys(universe),key=lambda t:(saved.get(t,{}).get('export_observed_at',''),t))


def combine(universe, saved, fresh, rejected, observed):
    rows={k:dict(v) for k,v in saved.items() if k not in rejected}
    for row in fresh:
        rows[row['ticker']]={**row,'export_observed_at':observed,'export_status':'refreshed'}
    return [rows[t] for t in dict.fromkeys(universe) if t in rows]


def guard(previous, incoming):
    """Refuse broad accidental deletion; individual removals remain possible."""
    def keys(doc):return {r.get('listing_symbol') or r.get('ticker') for r in doc.get('kandidaten',[])}-{None,''}
    old,new=keys(previous),keys(incoming)
    if len(old)>=100 and len(old-new)>max(25,len(old)*.1):
        raise ValueError('Universe coverage regression: refusing to remove more than 10% of established listings')
