"""Strict EDINET annual consolidated cash-flow observations; no valuation inputs."""
import datetime as dt
import io
import hashlib
import math
import re
import xml.etree.ElementTree as ET
import zipfile

X='http://www.xbrl.org/2003/instance'
D='http://xbrl.org/2006/xbrldi'
SOURCE='EDINET annual XBRL'
PARSER_VERSION='edinet-risk-v2'
# Verified against FSA 2026 taxonomy (1c_Taxonomy.zip, 2025-11-01)
# and sample instances (ESE140116.zip).
TAGS={
 'jppfs':{'total_assets':['Assets'],'cash':['CashAndCashEquivalents'],
  'operating_cashflow':['NetCashProvidedByUsedInOperatingActivities'],
  'ppe':['PurchaseOfPropertyPlantAndEquipmentInvCF'],'intangibles':['PurchaseOfIntangibleAssetsInvCF'],
  'gross_capex':['PurchaseOfPropertyPlantAndEquipmentAndIntangibleAssetsInvCF']},
 'jpigp':{'total_assets':['AssetsIFRS'],'cash':['CashAndCashEquivalentsIFRS'],
  'operating_cashflow':['NetCashProvidedByUsedInOperatingActivitiesIFRS'],
  'ppe':['PurchaseOfPropertyPlantAndEquipmentInvCFIFRS'],'intangibles':['PurchaseOfIntangibleAssetsInvCFIFRS'],
  'gross_capex':['PurchaseOfPropertyPlantAndEquipmentAndIntangibleAssetsInvCFIFRS'],
  'reported_interest_bearing_debt':['InterestBearingLiabilitiesLiabilitiesIFRS'],
  'current_interest_bearing_debt':['InterestBearingLiabilitiesCLIFRS'],
  'noncurrent_interest_bearing_debt':['InterestBearingLiabilitiesNCLIFRS']}}

def parse_xml(raw,doc,now):
 if len(raw)>30_000_000 or b'\x00' in raw or b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():raise ValueError('unsafe_xml')
 # Reject alternative encodings before XML parsing so DTD/entity checks also
 # cover UTF-16 payloads. EDINET instances use UTF-8.
 try:raw.decode('utf-8-sig')
 except UnicodeError:raise ValueError('unsafe_xml')
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
 facts={};diagnostic_facts=[]
 for e in root:
  if e.get('contextRef') not in contexts or e.get('unitRef') not in units or e.get('{http://www.w3.org/2001/XMLSchema-instance}nil') in ('true','1'):continue
  try:observed=float(e.text)
  except (TypeError,ValueError):continue
  if math.isfinite(observed) and any(x in e.tag for x in ('Purchase','Acquis','InterestBearing','Borrowing','Debt','OperatingActivities')):
   diagnostic_facts.append({'tag':e.tag[:300],'context':e.get('contextRef'),'value':observed,'periodKind':contexts[e.get('contextRef')],'decimals':e.get('decimals')})
  match=re.fullmatch(r'\{http://disclosure\.edinet-fsa\.go\.jp/taxonomy/(jppfs|jpigp)/\d{4}-\d{2}-\d{2}/\1_cor\}(.+)',e.tag)
  if not match:continue
  family,tag=match.groups()
  try:value=float(e.text)
  except (TypeError,ValueError):continue
  if not math.isfinite(value):continue
  # XBRL instance facts are already scaled currency amounts. decimals is
  # precision, not a multiplier (unlike inline-XBRL scale).
  key=(family,tag,contexts[e.get('contextRef')]);facts.setdefault(key,[]).append((value,e.get('contextRef'),e.get('decimals')))
 candidates=[]
 for family,mapping in TAGS.items():
  fields={};sources={};conflicts=[]
  for key,tags in mapping.items():
   kind='instant' if key in ('total_assets','cash','reported_interest_bearing_debt','current_interest_bearing_debt','noncurrent_interest_bearing_debt') else 'duration'
   values=[(v,c,tag,decimals) for tag in tags for v,c,decimals in facts.get((family,tag,kind),[])]
   if len({v for v,c,t,d in values})>1:conflicts.append(key);continue
   if values:
    value,context,tag,decimals=values[0];fields[key]=value
    sources[key]={'source':SOURCE,'end':str(end),'start':str(start) if kind=='duration' else None,'currency':'JPY','taxonomy':family,'tag':tag,'context':context,'docID':doc['docID'],'decimals':decimals}
  if not fields:continue
  def tolerance(keys):
   total=0
   for k in keys:
    dec=sources.get(k,{}).get('decimals')
    try:total+=.5*10**(-max(-12,min(12,int(dec))))
    except (ValueError,TypeError):pass
   return max(1,total)
  def derived(key,value,keys,method):
   fields[key]=value
   if value is not None:sources[key]={'source':SOURCE,'end':str(end),'currency':'JPY','docID':doc['docID'],
    'start':str(start) if key=='capex' else None,'derivation':method,'components':{k:{'value':fields[k],**sources[k]} for k in keys}}
  capex=None;parts=[];method='gross_ppe_plus_intangibles'
  if 'gross_capex' in fields:
   if fields['gross_capex']<=0:capex=-fields['gross_capex'];parts=['gross_capex'];method='reported_gross_ppe_and_intangibles_total'
   else:conflicts.append('positive_gross_capex')
   if capex is not None and any(k in fields and (fields[k]>0 or -fields[k]>capex+tolerance(['gross_capex',k])) for k in ('ppe','intangibles')):conflicts.append('capex_total_component_conflict');capex=None
   if all(k in fields for k in ('ppe','intangibles')) and (any(fields[k]>0 for k in ('ppe','intangibles')) or abs(fields['gross_capex']-fields['ppe']-fields['intangibles'])>tolerance(['gross_capex','ppe','intangibles'])):conflicts.append('capex_total_component_conflict');capex=None
  elif 'gross_capex' not in conflicts and all(k in fields and fields[k]<=0 for k in ('ppe','intangibles')):
   capex=-fields['ppe']-fields['intangibles'];parts=['ppe','intangibles']
  if any(k in conflicts for k in ('gross_capex','ppe','intangibles')) or (capex is not None and not math.isfinite(capex)):capex=None
  derived('capex',capex,parts,method)
  debt=None;parts=[];method='reported_interest_bearing_total'
  if 'reported_interest_bearing_debt' in fields:
   if fields['reported_interest_bearing_debt']>=0:debt=fields['reported_interest_bearing_debt'];parts=['reported_interest_bearing_debt']
   else:conflicts.append('negative_interest_bearing_debt')
   if debt is not None and any(k in fields and (fields[k]<0 or fields[k]>debt+tolerance(['reported_interest_bearing_debt',k])) for k in ('current_interest_bearing_debt','noncurrent_interest_bearing_debt')):conflicts.append('debt_total_component_conflict');debt=None
   if all(k in fields for k in ('current_interest_bearing_debt','noncurrent_interest_bearing_debt')) and (any(fields[k]<0 for k in ('current_interest_bearing_debt','noncurrent_interest_bearing_debt')) or abs(fields['reported_interest_bearing_debt']-fields['current_interest_bearing_debt']-fields['noncurrent_interest_bearing_debt'])>tolerance(['reported_interest_bearing_debt','current_interest_bearing_debt','noncurrent_interest_bearing_debt'])):conflicts.append('debt_total_component_conflict');debt=None
  elif 'reported_interest_bearing_debt' not in conflicts and all(k in fields and fields[k]>=0 for k in ('current_interest_bearing_debt','noncurrent_interest_bearing_debt')):
   debt=fields['current_interest_bearing_debt']+fields['noncurrent_interest_bearing_debt'];parts=['current_interest_bearing_debt','noncurrent_interest_bearing_debt'];method='both_reported_interest_bearing_maturities'
  if any(k in conflicts for k in ('reported_interest_bearing_debt','current_interest_bearing_debt','noncurrent_interest_bearing_debt')) or (debt is not None and not math.isfinite(debt)):debt=None
  derived('interest_bearing_debt',debt,parts,method)
  missing=[k for k in ('total_assets','cash','operating_cashflow','capex') if fields.get(k) is None]
  invalid=fields.get('total_assets',1)<=0 or fields.get('cash',0)<0
  complete=not missing and not conflicts and not invalid
  ratio=(fields['operating_cashflow']-capex)/fields['total_assets'] if complete else None
  if ratio is not None and not math.isfinite(ratio):ratio=None;complete=False;conflicts.append('nonfinite_fcf_ratio')
  candidates.append({'parserVersion':PARSER_VERSION,'fileSha256':hashlib.sha256(raw).hexdigest(),'source':SOURCE,'period_type':'annual','start':str(start),'end':str(end),'currency':'JPY','taxonomy':family,'fields':fields,'field_sources':sources,'missing_fields':missing,'conflicts':conflicts,'state':'available' if complete else 'partial',
   'fcfAssets':ratio,
   'diagnostics':{'monetaryCandidates':diagnostic_facts[:80],'candidateCount':len(diagnostic_facts),'truncated':len(diagnostic_facts)>80},
   'debtScope':'reported interest-bearing liabilities; lease coverage not separately reconciled' if debt is not None else None})
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
