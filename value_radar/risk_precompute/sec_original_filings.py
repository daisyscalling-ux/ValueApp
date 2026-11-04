"""Read selected, dimension-free facts from an original annual inline-XBRL filing."""
import datetime as dt
import hashlib
import io
import math
import re
import xml.etree.ElementTree as ET

X='http://www.xbrl.org/2003/instance'
IX='http://www.xbrl.org/2013/inlineXBRL'
MAX_DOCUMENT_BYTES=40_000_000
PDD_CONCEPT='PaymentsToAcquirePropertyEquipmentAndSoftwareAndIntangibleAssets'
STANDARD={
    'us-gaap':{'Assets','NetCashProvidedByUsedInOperatingActivities','NetCashProvidedByUsedInOperatingActivitiesContinuingOperations','CashProvidedByUsedInOperatingActivitiesDiscontinuedOperations','PaymentsToAcquirePropertyPlantAndEquipment','PaymentsToAcquireProductiveAssets'},
    'ifrs-full':{'Assets','CashFlowsFromUsedInOperatingActivities','PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities'},
}


def qualified(qname, namespaces):
    parts=qname.split(':')
    return (namespaces.get(parts[0],''),parts[1]) if len(parts)==2 else ('','')


def family(uri):
    if re.fullmatch(r'https?://fasb.org/us-gaap/\d{4}',uri):return 'us-gaap'
    if re.fullmatch(r'https?://xbrl.ifrs.org/taxonomy/\d{4}-\d{2}-\d{2}/ifrs-full',uri):return 'ifrs-full'
    return None


def transform(qname,namespaces):
    uri,name=qualified(qname,namespaces)
    if not qname:return ''
    if not re.fullmatch(r'https?://www.xbrl.org/inlineXBRL/transformation/\d{4}-\d{2}-\d{2}',uri):return None
    return name


def selected_tree(raw):
    """Discard prose while parsing; retain contexts, units and selected fact subtrees."""
    root=ET.Element('selected'); namespaces={}; stack=[]; capture=None
    names=set().union(*STANDARD.values()) | {PDD_CONCEPT,'EntityCentralIndexKey','DocumentType','DocumentPeriodEndDate'}
    for event,item in ET.iterparse(io.BytesIO(raw),events=['start-ns','start','end']):
        if event=='start-ns':
            prefix,uri=item
            if prefix in namespaces and namespaces[prefix]!=uri:raise ValueError('ambiguous_namespace')
            namespaces[prefix]=uri
        elif event=='start':
            stack.append(item)
            if capture is None and (item.tag in ('{'+X+'}context','{'+X+'}unit') or
                (item.tag in ('{'+IX+'}nonNumeric','{'+IX+'}nonFraction') and item.get('name','').split(':')[-1] in names)):
                capture=item
        else:
            if item is capture:
                root.append(item); capture=None
                if len(stack)>1:stack[-2].remove(item)
            elif capture is None:
                if len(stack)>1:stack[-2].remove(item)
                item.clear()
            stack.pop()
    return root,namespaces


def document_date(text,fmt):
    months='January February March April May June July August September October November December'.split()
    if fmt in ('date-monthname-day-year-en','datemonthdayyearen'):
        m=re.fullmatch(r'([A-Za-z]+) (\d{1,2}),? (\d{4})',text)
        if not m:return None
        month,day,year=m.groups()
    elif fmt=='date-day-monthname-year-en':
        m=re.fullmatch(r'(\d{1,2}) ([A-Za-z]+) (\d{4})',text)
        if not m:return None
        day,month,year=m.groups()
    else:return None
    if month not in months:return None
    try:return dt.date(int(year),months.index(month)+1,int(day)).isoformat()
    except ValueError:return None


def parse(raw,cik,filing,source_url):
    if len(raw)>MAX_DOCUMENT_BYTES:raise ValueError('filing_too_large')
    if b'\x00' in raw:raise ValueError('unsupported_xml_encoding')
    if re.search(br'<!\s*(DOCTYPE|ENTITY)',raw,re.I):raise ValueError('xml_declaration_blocked')
    root,namespaces=selected_tree(raw)
    contexts={}
    for c in root.iter('{'+X+'}context'):
        # Segment/scenario can change entity, business, share class or consolidation scope.
        if any(n.tag in ('{'+X+'}segment','{'+X+'}scenario') or n.tag.endswith(('}explicitMember','}typedMember')) for n in c.iter()):continue
        identifiers=list(c.iter('{'+X+'}identifier'))
        if len(identifiers)!=1 or (identifiers[0].text or '').lstrip('0')!=str(cik).lstrip('0'):continue
        if identifiers[0].get('scheme') not in ('http://www.sec.gov/CIK','https://www.sec.gov/CIK'):continue
        p=c.find('{'+X+'}period')
        if p is None:continue
        vals={n.tag.rsplit('}',1)[-1]:n.text for n in p}
        if set(vals) not in ({'instant'},{'startDate','endDate'}):continue
        item={'end':vals.get('instant',vals.get('endDate'))}
        if 'startDate' in vals:item['start']=vals['startDate']
        try:
            for v in item.values():dt.date.fromisoformat(v)
        except (TypeError,ValueError):continue
        ident=c.get('id')
        if ident in contexts:raise ValueError('duplicate_context')
        contexts[ident]=item
    units={}
    for u in root.iter('{'+X+'}unit'):
        if len(u)!=1 or u[0].tag!='{'+X+'}measure':continue
        uri,code=qualified(u[0].text or '',namespaces)
        if uri!='http://www.xbrl.org/2003/iso4217' or not re.fullmatch('[A-Z]{3}',code):continue
        if u.get('id') in units:raise ValueError('duplicate_unit')
        units[u.get('id')]=code
    meta={}
    for e in root.iter('{'+IX+'}nonNumeric'):
        uri,name=qualified(e.get('name',''),namespaces)
        if not re.fullmatch(r'https?://xbrl.sec.gov/dei/\d{4}',uri) or e.get('contextRef') not in contexts:continue
        if name not in ('EntityCentralIndexKey','DocumentType','DocumentPeriodEndDate'):continue
        text=' '.join(''.join(e.itertext()).split())
        if name=='DocumentPeriodEndDate' and e.get('format'):
            text=document_date(text,transform(e.get('format'),namespaces))
            if text is None:continue
        meta.setdefault(name,set()).add(text)
    if meta.get('EntityCentralIndexKey')!={str(cik).zfill(10)} and meta.get('EntityCentralIndexKey')!={str(int(cik))}:raise ValueError('filing_cik_mismatch')
    if meta.get('DocumentType')!={filing['form']} or meta.get('DocumentPeriodEndDate')!={filing['reportDate']}:raise ValueError('filing_metadata_mismatch')
    facts={};pdd_units={}
    for e in root.iter('{'+IX+'}nonFraction'):
        uri,name=qualified(e.get('name',''),namespaces);ns=family(uri)
        custom=str(int(cik))=='1737806' and name==PDD_CONCEPT and re.fullmatch(r'https?://www.pinduoduo.com/\d{8}',uri)
        if not custom and (ns not in STANDARD or name not in STANDARD[ns]):continue
        context=contexts.get(e.get('contextRef'));currency=units.get(e.get('unitRef'))
        if context is None or currency is None or e.get('continuedAt') or e.get('{http://www.w3.org/2001/XMLSchema-instance}nil') in ('true','1'):continue
        fmt=transform(e.get('format',''),namespaces)
        if fmt not in ('','num-dot-decimal','numdotdecimal','zerodash','fixed-zero'):continue
        value_text=''.join(e.itertext()).strip().replace('\u00a0','').replace(' ','')
        if fmt in ('zerodash','fixed-zero'):value_text='0'
        if value_text.startswith('-') and e.get('sign')=='-':continue
        if not re.fullmatch(r'-?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?',value_text):continue
        try:
            scale=int(e.get('scale','0'))
            if not -12<=scale<=12 or e.get('sign','') not in ('','-'):continue
            value=float(value_text.replace(',',''))*10**scale*(-1 if e.get('sign')=='-' else 1)
            if not math.isfinite(value):continue
        except (ValueError,OverflowError):continue
        row={**context,'val':value,'accn':filing['accessionNumber'],'filed':filing['filingDate'],'form':filing['form']}
        if custom:pdd_units.setdefault(currency,[]).append(row)
        else:facts.setdefault(ns,{}).setdefault(name,{'units':{}})['units'].setdefault(currency,[]).append(row)
    if pdd_units:
        # Explicit issuer-scoped reviewed bundle; never generalize a similarly named extension.
        gaap=facts.get('us-gaap',{})
        facts['pdd-reviewed']={k:gaap[k] for k in ('Assets','NetCashProvidedByUsedInOperatingActivities') if k in gaap}
        facts['pdd-reviewed'][PDD_CONCEPT]={'units':pdd_units}
    from sec_reported_ppe import recover
    recovered=[]
    if facts.get('us-gaap') and not any(f.get('end')==filing['reportDate'] for f in facts['us-gaap'].get('PaymentsToAcquirePropertyPlantAndEquipment',{}).get('units',{}).get('USD',[])):
        for f in recover(raw,facts):
            units=facts['us-gaap'].setdefault('PaymentsToAcquirePropertyPlantAndEquipment',{'units':{}})['units'].setdefault('USD',[])
            # Preserve tagged facts even if an untagged table disagrees.
            if any(old.get('end')==f['end'] for old in units):continue
            units.append(f);recovered.append({'end':f['end'],**f['reportedTableEvidence']})
    return {'cik':int(cik),'facts':facts,'originalFiling':{'method':'annual-inline-xbrl-v1','sourceUrl':source_url,'sha256':hashlib.sha256(raw).hexdigest(),'accession':filing['accessionNumber'],'reportDate':filing['reportDate'],'form':filing['form'],'filed':filing['filingDate'],**({'reportedTableRecoveries':recovered} if recovered else {})}}


def latest_annual(submissions,cik,now):
    if str(submissions.get('cik','')).lstrip('0')!=str(cik).lstrip('0'):raise ValueError('submissions_cik_mismatch')
    recent=submissions.get('filings',{}).get('recent',{})
    keys=('accessionNumber','filingDate','reportDate','form','primaryDocument')
    if len({len(recent.get(k,[])) for k in keys})!=1:raise ValueError('submissions_array_mismatch')
    rows=[]
    for values in zip(*(recent.get(k,[]) for k in keys)):
        r=dict(zip(keys,values))
        try:
            if r['form'] not in ('10-K','10-K/A','20-F','20-F/A','40-F','40-F/A'):continue
            if not re.fullmatch(r'\d{10}-\d{2}-\d{6}',r['accessionNumber']) or not re.fullmatch(r'[A-Za-z0-9_.-]+\.html?',r['primaryDocument']):continue
            end=dt.date.fromisoformat(r['reportDate']);filed=dt.date.fromisoformat(r['filingDate'])
            if not end<=filed<=now.date() or not 0<=(now.date()-end).days<=800:continue
        except (ValueError,TypeError):continue
        rows.append(r)
    return max(rows,key=lambda r:(r['reportDate'],r['filingDate'],r['accessionNumber']),default=None)
