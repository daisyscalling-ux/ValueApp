"""Recover and verify observed inputs from their original Git revision, offline."""
import gzip
import json
from pathlib import Path
import re
import subprocess
import sys
from risk_evidence import resolve_inputs


def resolve(repo,date):
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',date):raise ValueError('invalid_observation_date')
    path='value_radar/daten/risk_observations/'+date+'.json.gz'
    def git(*args):return subprocess.run(['git','-C',str(repo),*args],check=True,capture_output=True,timeout=30).stdout
    revisions=git('log','--diff-filter=A','--format=%H','--',path).decode().splitlines()
    if len(revisions)!=1:raise ValueError('observation_original_revision_missing_or_ambiguous')
    revision=revisions[0]
    snapshot=json.loads(gzip.decompress(git('show',revision+':'+path)))
    inputs=resolve_inputs(snapshot,lambda name:git('show',revision+':value_radar/daten/'+name))
    return {'revision':revision,'observation':snapshot,'inputs':inputs}


if __name__=='__main__':
    result=resolve(Path(sys.argv[1]),sys.argv[2])
    if len(sys.argv)>3:
        Path(sys.argv[3]).write_text(json.dumps(result,ensure_ascii=False,allow_nan=False),encoding='utf-8')
    print(json.dumps({'revision':result['revision'],'observedAt':result['observation']['observedAt'],'verifiedSources':len(result['inputs'])}))
