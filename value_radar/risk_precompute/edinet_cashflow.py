"""Strict EDINET annual consolidated cash-flow observations; no valuation inputs."""
import datetime as dt
import io
import math
import re
import xml.etree.ElementTree as ET
import zipfile

X='http://www.xbrl.org/2003/instance'
D='http://xbrl.org/2006/xbrldi'
SOURCE='EDINET annual XBRL'
# Verified against the FSA 2026 sample instances (ESE140116.zip).
TAGS={
 'jppfs':{'total_assets':['Assets'],'cash':['CashAndCashEquivalents'],
  'operating_cashflow':['NetCashProvidedByUsedInOperatingActivities'],
  'ppe':['PurchaseOfPropertyPlantAndEquipmentInvCF'],'intangibles':['PurchaseOfIntangibleAssetsInvCF']},
 'jpigp':{'total_assets':['AssetsIFRS'],'cash':['CashAndCashEquivalentsIFRS'],
  'operating_cashflow':['NetCashProvidedByUsedInOperatingActivitiesIFRS'],
  'ppe':['PurchaseOfPropertyPlantAndEquipmentInvCFIFRS'],'intangibles':['PurchaseOfIntangibleAssetsInvCFIFRS']}}

def parse_xml(raw,doc,now):
 if len(raw)>30_000_000 or b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():raise ValueError('unsafe_xml')
 namespaces={}
 for _,(prefix,uri) in ET.iterparse(io.BytesIO(raw),events=['start-ns']):
  if prefix in namespaces and namespaces[prefix]!=uri:raise ValueError('conflicting_namespace')
  namespaces[prefix]=uri
 root=ET.fromstring(raw)
 if root.tag!='{'+X+'}xbrl':raise ValueError('not_xbrl_instance')
 dei={}
 for e in root:
  if not re.fullmatch(r'\{http://disclosure\.edinet-fsa\.go\.jp/taxonomy/jpdei/\d{4}-\d{2}-\d{2}/jpdei_cor\}.+',e.tag):continue
  key=e.tag.split('}')[-1]
  if key in dei and dei[key]!=e.text:raise ValueError('issuer_unconfirmed')
  dei[key]=e.text
 if dei.get('WhetherConsolidatedFinancialStatementsArePreparedDEI') not in ('true','1'):raise ValueError('consolidation_unconfirmed')
 if dei.get('EDINETCodeDEI')!=doc['edinetCode']:raise ValueError('issuer_unconfirmed')
 start=dt.date.fromisoformat(doc['periodStart']);end=dt.date.fromisoformat(doc['periodEnd'])
 if not 330<=(end-start).days<=380 or not 0<=(now.date()-end).days<=550:raise ValueError('invalid_annual_period')
 contexts={};units={};context_ids=set();unit_ids=set()
 for e in root.findall('{'+X+'}context'):
  if not e.get('id') or e.get('id') in context_ids:raise ValueError('duplicate_context')
  context_ids.add(e.get('id'))
  ident=e.find('{'+X+'}entity/{'+X+'}identifier');period=e.find('{'+X+'}period')
  if ident is None or ident.get('scheme')!='http://disclosure.edinet-fsa.go.jp' or (ident.text or '').split('-')[0]!=doc['edinetCode']:continue
  # A dimension-free context means consolidated by default in EDINET filings.
  # Reject all dimensions (including nonconsolidated, segments and restatements).
  if e.find('.//{'+D+'}explicitMember') is not None or e.find('.//{'+D+'}typedMember') is not None:continue
  if period is None:continue
  instant=period.findtext('{'+X+'}instant');ps=period.findtext('{'+X+'}startDate');pe=period.findtext('{'+X+'}endDate')
  kind='instant' if instant==str(end) else 'duration' if ps==str(start) and pe==str(end) else None
  if kind:
   if e.get('id') in contexts:raise ValueError('duplicate_context')
   contexts[e.get('id')]=kind
 for u in root.findall('{'+X+'}unit'):
  if not u.get('id') or u.get('id') in unit_ids:raise ValueError('duplicate_unit')
  unit_ids.add(u.get('id'))
  measures=u.findall('{'+X+'}measure')
  if len(measures)==1 and len(u)==1:
   unit=(measures[0].text or '').split(':')
   if len(unit)==2 and unit[1]=='JPY' and namespaces.get(unit[0])=='http://www.xbrl.org/2003/iso4217':units[u.get('id')]='JPY'
 facts={}
 for e in root:
  if e.get('contextRef') not in contexts or e.get('unitRef') not in units or e.get('{http://www.w3.org/2001/XMLSchema-instance}nil') in ('true','1'):continue
  match=re.fullmatch(r'\{http://disclosure\.edinet-fsa\.go\.jp/taxonomy/(jppfs|jpigp)/\d{4}-\d{2}-\d{2}/\1_cor\}(.+)',e.tag)
  if not match:continue
  family,tag=match.groups()
  try:value=float(e.text)
  except (TypeError,ValueError):continue
  if not math.isfinite(value):continue
  # XBRL instance facts are already scaled currency amounts. decimals is
  # precision, not a multiplier (unlike inline-XBRL scale).
  key=(family,tag,contexts[e.get('contextRef')]);facts.setdefault(key,[]).append((value,e.get('contextRef')))
 candidates=[]
 for family,mapping in TAGS.items():
  fields={};sources={};conflicts=[]
  for key,tags in mapping.items():
   kind='instant' if key in ('total_assets','cash') else 'duration'
   values=[(v,c,tag) for tag in tags for v,c in facts.get((family,tag,kind),[])]
   if len({v for v,c,t in values})>1:conflicts.append(key);continue
   if values:
    value,context,tag=values[0];fields[key]=value
    sources[key]={'source':SOURCE,'end':str(end),'start':str(start) if kind=='duration' else None,'currency':'JPY','taxonomy':family,'tag':tag,'context':context,'docID':doc['docID']}
  if not fields:continue
  capex=None
  if all(k in fields and fields[k]<=0 for k in ('ppe','intangibles')):capex=-fields['ppe']-fields['intangibles']
  fields['capex']=capex
  if capex is not None:sources['capex']={'source':SOURCE,'end':str(end),'start':str(start),'currency':'JPY','docID':doc['docID'],'derivation':'gross_ppe_plus_intangibles','components':{k:{'value':fields[k],**sources[k]} for k in ('ppe','intangibles')}}
  missing=[k for k in ('total_assets','cash','operating_cashflow','capex') if fields.get(k) is None]
  invalid=fields.get('total_assets',1)<=0 or fields.get('cash',0)<0
  complete=not missing and not conflicts and not invalid
  candidates.append({'source':SOURCE,'period_type':'annual','start':str(start),'end':str(end),'currency':'JPY','taxonomy':family,'fields':fields,'field_sources':sources,'missing_fields':missing,'conflicts':conflicts,'state':'available' if complete else 'partial',
   'fcfAssets':(fields['operating_cashflow']-capex)/fields['total_assets'] if complete else None})
 if len(candidates)!=1:raise ValueError('ambiguous_or_unsupported_taxonomy')
 return candidates[0]

def parse_zip(raw,doc,now):
 if len(raw)>30_000_000:raise ValueError('archive_too_large')
 with zipfile.ZipFile(io.BytesIO(raw)) as archive:
  names=[x for x in archive.infolist() if '/PublicDoc/' in '/'+x.filename and x.filename.endswith('.xbrl')]
  if len(names)!=1:raise ValueError('ambiguous_public_instance')
  entry=names[0]
  if entry.file_size>30_000_000 or entry.file_size>max(entry.compress_size,1)*300:raise ValueError('archive_too_large')
  return parse_xml(archive.read(entry),doc,now)
