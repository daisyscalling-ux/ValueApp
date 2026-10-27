"""Publish bounded, content-addressed app shards without changing audit values."""
import datetime as dt,hashlib,json,os,re
from pathlib import Path
from yahoo_sector import load,save,recent
HASH=re.compile(r'^[0-9a-f]{64}$')
def build(coverage,now=None):
 now=now or dt.datetime.now(dt.timezone.utc)
 if coverage.get('schema')!=1 or not recent(coverage.get('generatedAt'),now,1.5):raise ValueError('coverage_stale_or_invalid')
 rows=coverage.get('stocks');seen=set();buckets={};index={}
 if not isinstance(rows,list) or not rows:raise ValueError('coverage_empty')
 for row in rows:
  symbol=row.get('symbol')
  if not isinstance(symbol,str) or not re.fullmatch(r'[A-Z0-9._:-]{1,100}',symbol) or symbol in seen:raise ValueError('duplicate_or_invalid_symbol')
  seen.add(symbol);bucket=str(int(hashlib.sha256(symbol.encode()).hexdigest()[:2],16)%32)
  buckets.setdefault(bucket,[]).append(row);index[symbol]=bucket
 shards={};payloads={}
 for bucket,items in sorted(buckets.items()):
  payload=json.dumps({'schema':1,'generatedAt':coverage['generatedAt'],'stocks':sorted(items,key=lambda x:x['symbol'])},ensure_ascii=False,allow_nan=False,separators=(',',':')).encode('utf8')
  if len(payload)>2_000_000:raise ValueError('app_shard_too_large')
  digest=hashlib.sha256(payload).hexdigest();shards[bucket]=digest;payloads[digest]=payload
 manifest={'schema':1,'format':'risk-app-shards-v1','generatedAt':coverage['generatedAt'],'listings':dict(sorted(index.items())),'shards':shards,'sourceListings':len(rows)}
 return manifest,payloads

def publish(folder,coverage,now=None):
 folder=Path(folder);manifest,payloads=build(coverage,now);target=folder/'risk_app';target.mkdir(parents=True,exist_ok=True)
 previous=load(folder/'cf_risk_app_manifest.json',{});keep=set(payloads)|{v for v in previous.get('shards',{}).values() if isinstance(v,str) and HASH.fullmatch(v)}
 for digest,payload in payloads.items():(target/(digest+'.json')).write_bytes(payload)
 # Manifest last. Content-addressed previous shards survive one full generation
 # so a cached manifest can still resolve during deployment or CDN propagation.
 save(folder/'cf_risk_app_manifest.json',manifest)
 root=target.resolve()
 for p in target.glob('*.json'):
  if HASH.fullmatch(p.stem) and p.stem not in keep and not p.is_symlink() and p.resolve().parent==root:p.unlink()
 return {'listings':manifest['sourceListings'],'shards':len(payloads),'maxBytes':max(map(len,payloads.values())),'totalBytes':sum(map(len,payloads.values()))}

def main():
 folder=Path(os.getenv('RISK_DATA_DIR',str(Path(__file__).resolve().parents[1]/'daten')))
 report=publish(folder,load(folder/'cf_risk_coverage.json',{}));print(json.dumps(report))
 if os.getenv('GITHUB_STEP_SUMMARY'):
  with open(os.environ['GITHUB_STEP_SUMMARY'],'a',encoding='utf8') as f:f.write('\n## App-Datenabruf\n\n'+str(report['listings'])+' Notierungen in '+str(report['shards'])+' Teilpaketen; groesstes Paket '+str(report['maxBytes'])+' Bytes. Originalwerte unveraendert.\n')
if __name__=='__main__':main()
