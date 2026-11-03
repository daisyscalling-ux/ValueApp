"""Bind published risk results to the universe actually processed by this run."""
import datetime as dt
import hashlib
import json
import os
import re
from pathlib import Path
import subprocess
import sys

TARGET='value_radar/daten/cf_universum.json'


def describe(raw):
    doc=json.loads(raw)
    rows=doc.get('kandidaten')
    if not isinstance(rows,list) or not rows or doc.get('anzahl')!=len(rows):
        raise ValueError('invalid_universe_count')
    symbols=[r.get('listing_symbol') or r.get('ticker') for r in rows]
    if any(not isinstance(s,str) or not s for s in symbols) or len(set(symbols))!=len(symbols):
        raise ValueError('invalid_or_duplicate_universe_listing')
    return {'sha256':hashlib.sha256(raw).hexdigest(),'listings':len(symbols),'stand':doc.get('stand'),'symbols':sorted(symbols),'scan':doc.get('scan')}


def capture(folder,record):
    d=describe((Path(folder)/'cf_universum.json').read_bytes())
    d.update(schema=1,capturedAt=dt.datetime.now(dt.timezone.utc).isoformat(),runId=os.getenv('GITHUB_RUN_ID'),commit=os.getenv('GITHUB_SHA'))
    Path(record).write_text(json.dumps(d),encoding='utf-8')
    return d


def seal(folder,record):
    folder=Path(folder)
    original=json.loads(Path(record).read_text(encoding='utf-8'))
    current=describe((folder/'cf_universum.json').read_bytes())
    manifest_path=folder/'cf_risk_app_manifest.json'
    manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    coverage=json.loads((folder/'cf_risk_coverage.json').read_text(encoding='utf-8'))
    symbols=sorted(r['symbol'] for r in coverage['stocks'])
    if symbols!=current['symbols'] or sorted(manifest['listings'])!=symbols:
        raise ValueError('risk_universe_listing_mismatch')
    if manifest['generatedAt']!=coverage['generatedAt'] or manifest['sourceListings']!=len(symbols):
        raise ValueError('risk_manifest_coverage_mismatch')
    published=[]
    for bucket,digest in manifest['shards'].items():
        if not re.fullmatch('[a-f0-9]{64}',digest):raise ValueError('invalid_shard_digest')
        raw=(folder/'risk_app'/(digest+'.json')).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=digest:raise ValueError('shard_hash_mismatch')
        shard=json.loads(raw)
        if shard['generatedAt']!=manifest['generatedAt']:raise ValueError('shard_date_mismatch')
        if any(manifest['listings'].get(r['symbol'])!=bucket for r in shard['stocks']):raise ValueError('shard_index_mismatch')
        published.extend(shard['stocks'])
    if sorted(published,key=lambda r:r['symbol'])!=sorted(coverage['stocks'],key=lambda r:r['symbol']):
        raise ValueError('shard_coverage_values_mismatch')
    generated=dt.datetime.fromisoformat(manifest['generatedAt'].replace('Z','+00:00'))
    captured=dt.datetime.fromisoformat(original['capturedAt'])
    if generated<captured:raise ValueError('risk_results_predate_run')
    report={'schema':1,'state':'verified','runId':original.get('runId'),'capturedAt':original['capturedAt'],'generatedAt':manifest['generatedAt'],
        'inputSha256':original['sha256'],'processedSha256':current['sha256'],'inputListings':original['listings'],'publishedListings':len(symbols),
        'universeStand':current['stand'],'scan':current['scan']}
    manifest['inputUniverse']=report
    manifest_path.write_text(json.dumps(manifest,ensure_ascii=False),encoding='utf-8')
    (folder/'cf_risk_run_integrity.json').write_text(json.dumps(report,ensure_ascii=False),encoding='utf-8')
    return report


def verify_remote(record,raw):
    original=json.loads(Path(record).read_text(encoding='utf-8'))
    if hashlib.sha256(raw).hexdigest()!=original['sha256']:
        raise ValueError('universe_changed_during_run: results retained as artifact; rerun daily-risk on current main')


def main():
    mode,folder,record=sys.argv[1:4]
    if mode=='capture':result=capture(folder,record)
    elif mode=='seal':result=seal(folder,record)
    elif mode=='remote':
        raw=subprocess.run(['git','show','origin/main:'+TARGET],check=True,capture_output=True,timeout=30).stdout
        verify_remote(record,raw);result={'remoteUniverse':'unchanged'}
    else:raise ValueError('unknown_mode')
    print(json.dumps({k:v for k,v in result.items() if k!='symbols'}))

if __name__=='__main__':main()
