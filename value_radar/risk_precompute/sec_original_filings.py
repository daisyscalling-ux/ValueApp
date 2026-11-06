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

def investment_candidate(name):
    return len(name)<=240 and any(x in name for x in ('Purchase','PaymentsToAcquire','CapitalExpenditure','AdditionsToProperty'))


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
            if capture is None and (item.tag in ('{'+X+'}context','{'+X+'}unit','{'+IX+'}continuation') or
                (item.tag in ('{'+IX+'}nonNumeric','{'+IX+'}nonFraction') and (item.get('name','').split(':')[-1] in names or investment_candidate(item.get('name','').split(':')[-1])))):
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
    if fmt in ('date-month-day-year','date-day-month-year'):
        # Order comes exclusively from the declared transform, never from a guess.
        m=re.fullmatch(r'(\d{1,2})[^0-9]+(\d{1,2})[^0-9]+(\d{4})',text)
        if not m:return None
        first,second,year=map(int,m.groups())
        month,day=(first,second) if fmt=='date-month-day-year' else (second,first)
        try:return dt.date(year,month,day).isoformat()
        except ValueError:return None
    if fmt in ('date-monthname-day-year-en','datemonthdayyearen'):
        m=re.fullmatch(r'([A-Za-z]+) (\d{1,2}),? (\d{4})',text)
        if not m:return None
        month,day,year=m.groups()
    elif fmt=='date-day-monthname-year-en':
        m=re.fullmatch(r'(\d{1,2}) ([A-Za-z]+) (\d{4})',text)
        if not m:return None
        day,month,year=m.groups()
    else:return None
    # Month-name transforms accept capitalization differences in issuer text.
    month=month.casefold();lookup=[m.casefold() for m in months]
    if month not in lookup:return None
    try:return dt.date(int(year),lookup.index(month)+1,int(day)).isoformat()
    except ValueError:return None


def metadata_text(element,continuations):
    """Resolve bounded DEI continuations; ix:exclude is not part of a fact value."""
    def visible(node):
        if node.tag=='{'+IX+'}exclude':return ''
        return (node.text or '')+''.join(visible(child)+(child.tail or '') for child in node)
    pieces=[];seen=set();current=element
    for _ in range(16):
        pieces.append(visible(current))
        if sum(map(len,pieces))>512:raise ValueError('invalid_metadata_continuation')
        target=current.get('continuedAt')
        if not target:return ' '.join(''.join(pieces).split())
        if target in seen or continuations.get(target) is None:raise ValueError('invalid_metadata_continuation')
        seen.add(target);current=continuations[target]
    raise ValueError('invalid_metadata_continuation')


def parse(raw,cik,filing,source_url):
    if len(raw)>MAX_DOCUMENT_BYTES:raise ValueError('filing_too_large')
    if b'\x00' in raw:raise ValueError('unsupported_xml_encoding')
    if re.search(br'<!\s*(DOCTYPE|ENTITY)',raw,re.I):raise ValueError('xml_declaration_blocked')
    root,namespaces=selected_tree(raw)
    return parse_selected(raw,cik,filing,source_url,root,namespaces)


def parse_selected(raw,cik,filing,source_url,root,namespaces):
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
    continuations={}
    for item in root.iter('{'+IX+'}continuation'):
        key=item.get('id')
        continuations[key]=item if key not in continuations else None
    for e in root.iter('{'+IX+'}nonNumeric'):
        uri,name=qualified(e.get('name',''),namespaces)
        if not re.fullmatch(r'https?://xbrl.sec.gov/dei/\d{4}',uri) or e.get('contextRef') not in contexts:continue
        if name not in ('EntityCentralIndexKey','DocumentType','DocumentPeriodEndDate'):continue
        text=metadata_text(e,continuations)
        if name=='DocumentPeriodEndDate' and e.get('format'):
            text=document_date(text,transform(e.get('format'),namespaces))
            if text is None:continue
        meta.setdefault(name,set()).add(text)
    if meta.get('EntityCentralIndexKey')!={str(cik).zfill(10)} and meta.get('EntityCentralIndexKey')!={str(int(cik))}:raise ValueError('filing_cik_mismatch')
    if meta.get('DocumentType')!={filing['form']} or meta.get('DocumentPeriodEndDate')!={filing['reportDate']}:raise ValueError('filing_metadata_mismatch')
    facts={};pdd_units={};investment_evidence=[];candidate_count=0
    for e in root.iter('{'+IX+'}nonFraction'):
        uri,name=qualified(e.get('name',''),namespaces);ns=family(uri)
        custom=str(int(cik))=='1737806' and name==PDD_CONCEPT and re.fullmatch(r'https?://www.pinduoduo.com/\d{8}',uri)
        accepted=custom or (ns in STANDARD and name in STANDARD[ns])
        if not accepted and not investment_candidate(name):continue
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
        if not accepted:
            # Diagnostics only: no inferred equivalence from tag names or amounts.
            try:annual=330<=(dt.date.fromisoformat(context['end'])-dt.date.fromisoformat(context['start'])).days<=400
            except (KeyError,ValueError):annual=False
            if annual and context['end']==filing['reportDate']:
                candidate_count+=1
                if len(investment_evidence)<100:investment_evidence.append({'namespace':uri[:400],'concept':name,'currency':currency,'context':e.get('contextRef'),**row})
            continue
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
    return {'cik':int(cik),'facts':facts,'originalFiling':{'method':'annual-inline-xbrl-v1','sourceUrl':source_url,'sha256':hashlib.sha256(raw).hexdigest(),'accession':filing['accessionNumber'],'reportDate':filing['reportDate'],'form':filing['form'],'filed':filing['filingDate'],'investmentEvidence':{'method':'unmapped-annual-investment-facts-v1','state':'review_required','scoreContribution':0,'candidates':investment_evidence,'candidateCount':candidate_count,'truncated':candidate_count>100},**({'reportedTableRecoveries':recovered} if recovered else {})}}


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
