"""Bounded numeric statement evidence, reusable without redating provider observations."""
import hashlib,json,math,re
from yahoo_sector import recent
VERSION='risk-statement-evidence-v1'
META={'symbol','period_type','period_end_date','currency','fx_applied','id'}
def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)
def pack(payloads,symbol,retrieved_at):
 result={}
 for kind in ('balance','cashflow','income','credit'):
  source=payloads.get(kind,{});data=source.get('data') if isinstance(source,dict) else None
  if not isinstance(data,list):continue
  rows=[]
  for row in data[:4]:
   if not isinstance(row,dict) or row.get('symbol')!=symbol or row.get('period_type')!='annual':continue
   clean={k:v for k,v in row.items() if k in META and (v is None or isinstance(v,(str,bool,int)))}
   for k,v in row.items():
    if not re.fullmatch(r'(?:bs_|cf_|is_)[a-z0-9_]{1,100}|short_and_long_term_debt',k):continue
    if v is None or (isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v)):clean[k]=v
   if len(clean)>500:continue
   rows.append(clean)
  result[kind]={'data':rows}
 if not all(k in result for k in ('balance','cashflow','income')):return None
 raw=canonical(result)
 if len(raw)>150000:return None
 return {'schema':1,'version':VERSION,'symbol':symbol,'retrievedAt':retrieved_at,'sha256':hashlib.sha256(raw.encode()).hexdigest(),'payloads':result}

def unpack(record,symbol,now):
 evidence=record.get('statementEvidence') or {}
 if evidence.get('schema')!=1 or evidence.get('version')!=VERSION or evidence.get('symbol')!=symbol:return None
 if evidence.get('retrievedAt')!=record.get('retrievedAt') or not recent(evidence.get('retrievedAt'),now,7):return None
 try:
  payloads=evidence['payloads'];encoded=canonical(payloads)
  if len(encoded)>150000 or hashlib.sha256(encoded.encode()).hexdigest()!=evidence.get('sha256'):return None
  rebuilt=pack(payloads,symbol,evidence['retrievedAt'])
  return payloads if rebuilt and rebuilt['payloads']==payloads else None
 except (KeyError,TypeError,ValueError):return None
