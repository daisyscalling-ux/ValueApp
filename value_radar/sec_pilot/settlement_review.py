"""Explicit stock-merger research scenario; never inserts successor stock quotes as old prices."""
import argparse
import csv
import datetime as dt
import hashlib
import io
import json
import math
from pathlib import Path
import zipfile

from free_sources import write_csv
from review_capture import normalize_capture
from window_coverage import inspect_windows


def positive(value):
    value=float(value)
    if not math.isfinite(value) or value<=0:raise ValueError('Positive finite observation required')
    return value


def stock_scenario(predecessor, successor, sessions, event, anchor, metadata):
    """Pro-rata successor ownership; adjusted-close dividend reinvestment AFTER transition.

    The first transition uses raw prices. Later adjusted-price ratios cannot reapply
    the exchange ratio. Fractional cash-in-lieu, costs and tax are NOT modelled.
    """
    ratio=positive(event['stock_ratio'])
    if event['cash_per_share']!=0:raise ValueError('Cash/mixed mergers require separate accounting')
    if not event.get('source') or not event.get('successor_identity_source'):
        raise ValueError('Merger and successor identity evidence required')
    if (metadata.get('symbol')!=event['successor'] or metadata.get('currency')!=event['currency']
            or metadata.get('instrumentType')!='EQUITY'):
        raise ValueError('Successor metadata mismatch')
    if event['effective']!=event['first_nontrading_session']:
        raise ValueError('Only pre-open stock mergers supported')
    boundary=event['effective'];index=sessions.index(boundary)
    if index==0 or not predecessor:raise ValueError('Missing pre-event observations')
    previous=sessions[index-1]
    if predecessor[-1]['Datum']!=previous or anchor['date']!=previous:
        raise ValueError('Exact immediately preceding session anchor required')
    if anchor['symbol']!=event['identity'] or anchor['currency']!=event['currency']:
        raise ValueError('Predecessor anchor identity/currency mismatch')
    if anchor['adjustment']!='Unadjusted' or not anchor.get('source'):
        raise ValueError('Separately sourced unadjusted predecessor price required')
    raw_before=positive(anchor['close'])
    selected={}
    for row in successor:
        day=row['Date'][:10]
        if day in selected or day not in sessions:raise ValueError('Duplicate or non-session successor row')
        selected[day]=row
    if boundary not in selected:raise ValueError('Missing successor transition observation')
    # Vendor may backfill its new ticker over its former ticker's history.
    if boundary<event['successor_symbol_effective'] and not event.get('successor_former_symbol'):
        raise ValueError('Pre-rename successor identity not documented')
    last=max(selected)
    post=[d for d in sessions if boundary<=d<=last]
    if any(d not in selected for d in post):raise ValueError('Missing successor session; no forward fill')
    first=selected[boundary]
    if float(first['Dividends'])!=0 or float(first['Stock Splits'])!=0:
        raise ValueError('Transition-day corporate action requires separate review')
    raw_after=positive(first['Close']);adj_start=positive(first['Adj Close'])
    level_start=positive(predecessor[-1]['Adjusted_Close'])*ratio*raw_after/raw_before
    rows=[dict(r) for r in predecessor]
    for day in post:
        item=selected[day]
        positive(item['Close']);positive(item['Volume'])
        # Later splits are not silently accepted; dividends use the provider's
        # adjustment ratio exactly once, without adding the cash a second time.
        if float(item['Stock Splits'])!=0:raise ValueError('Successor split requires separate review')
        level=level_start*positive(item['Adj Close'])/adj_start
        rows.append(dict(Datum=day,Adjusted_Close=str(level),
                         Tagesrendite=str(level/float(rows[-1]['Adjusted_Close'])-1),
                         Symbol=event['identity'],Underlying_Symbol=event['successor'],
                         Quelle=event['source'],Identitaet='synthetic_shareholder_wealth_scenario',
                         Abwicklung_bestaetigt=False))
    return rows


def run(capture_path, archive_path, successor_path, probe_path, anchor_path, evidence_path, output):
    paths=[Path(p) for p in (capture_path,archive_path,successor_path,probe_path,anchor_path,evidence_path)]
    capture=json.loads(paths[0].read_text(encoding='utf8'))
    events=json.loads(paths[5].read_text(encoding='utf8'))['settlement_evidence']
    event=next(e for e in events if e['identity']==capture['symbol'])
    anchor=json.loads(paths[4].read_text(encoding='utf8'))
    probe=json.loads(paths[3].read_text(encoding='utf8'))
    successor=list(csv.DictReader(io.StringIO(paths[2].read_text(encoding='utf8'))))
    with zipfile.ZipFile(paths[1]) as archive:
        def table(p):return list(csv.DictReader(io.StringIO(archive.read(p).decode('utf-8-sig'))))
        sessions=[r['date'] for r in table('session-review/handelskalender.csv')]
        if not sessions or sessions!=sorted(set(sessions)):raise ValueError('Invalid calendar')
        spans=[(r['start'],r['end']) for r in table('identity-review/mitglieder_korrigiert_vorlaeufig.csv')
               if r['symbol']==capture['symbol']]
        if not spans:raise ValueError('Missing membership history')
        end=dt.date.fromisoformat(json.loads(archive.read('coverage.json'))['requested_end_exclusive'])
        try:start=end.replace(year=end.year-6).isoformat()
        except ValueError:start=end.replace(year=end.year-6,day=28).isoformat()
    predecessor=normalize_capture(capture,sessions)
    rows=stock_scenario(predecessor,successor,sessions,event,anchor,probe['metadata'])
    before,_=inspect_windows(sessions,spans,predecessor,start)
    after,_=inspect_windows(sessions,spans,rows,start,entry_before=event['first_nontrading_session'])
    report=dict(symbol=capture['symbol'],event=event,anchor=anchor,baseline_windows=before,
                scenario_windows=after,production_eligible=False,automatically_imported=False,
                scenario='Fractional pro-rata successor ownership with provider-adjusted dividend reinvestment',
                limitations=['Synthetic wealth index, not historical AVB quotations.',
                             'Actual fractional-share cash settlement, costs and taxes are not replicated.',
                             'Provider dividend adjustments and boundary prices remain research inputs.',
                             'No calibration or improvement to the production risk score follows from coverage alone.'],
                input_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    fields=list(dict.fromkeys(k for row in rows for k in row))
    write_csv(output/'shareholder_wealth_scenario.csv',rows,fields)
    (output/'settlement_review.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('capture','archive','successor','probe','anchor','evidence','output'):p.add_argument(name)
    a=p.parse_args()
    r=run(a.capture,a.archive,a.successor,a.probe,a.anchor,a.evidence,a.output)
    print(json.dumps({k:r[k] for k in ('symbol','scenario_windows','production_eligible')},indent=2))
