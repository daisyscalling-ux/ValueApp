"""A single explicitly linked annual financial document, bound to a verified primary."""
import copy
import hashlib
import re
from html.parser import HTMLParser
from sec_original_filings import parse, parse_selected, selected_tree, X, IX, MAX_DOCUMENT_BYTES


def annual_link(raw):
    class Links(HTMLParser):
        def __init__(self):
            super().__init__(); self.href=None; self.words=[]; self.matches=set()
        def handle_starttag(self, tag, attrs):
            if tag=='a': self.href=dict(attrs).get('href'); self.words=[]
        def handle_data(self, data):
            if self.href: self.words.append(data)
        def handle_endtag(self, tag):
            if tag!='a': return
            label=' '.join(''.join(self.words).split()).casefold()
            if self.href and re.fullmatch(r'[A-Za-z0-9_.-]+\.html?',self.href) and label=='annual report to security holders':
                self.matches.add(self.href)
            self.href=None
    p=Links(); p.feed(raw.decode('utf-8'))
    return next(iter(p.matches)) if len(p.matches)==1 else None


def parse_linked(primary, companion, filename, cik, filing, source_url):
    verified=parse(primary,cik,filing,source_url)
    if verified['facts']: raise ValueError('primary_already_has_facts')
    if annual_link(primary)!=filename: raise ValueError('annual_link_mismatch')
    if len(companion)>MAX_DOCUMENT_BYTES: raise ValueError('filing_too_large')
    if b'\x00' in companion or re.search(br'<!\s*(DOCTYPE|ENTITY)',companion,re.I): raise ValueError('unsafe_linked_xml')
    root,ns=selected_tree(companion); parent,pns=selected_tree(primary)
    # Never replace conflicting DEI metadata in the financial document.
    names={'EntityCentralIndexKey','DocumentType','DocumentPeriodEndDate'}
    if any(e.get('name','').split(':')[-1] in names for e in root.iter('{'+IX+'}nonNumeric')):
        result=parse(companion,cik,filing,source_url)
    else:
        if any(k in ns and ns[k]!=v for k,v in pns.items()): raise ValueError('linked_namespace_conflict')
        ns.update(pns)
        metadata=[copy.deepcopy(e) for e in parent.iter('{'+IX+'}nonNumeric') if e.get('name','').split(':')[-1] in names]
        # Inline document sets may keep all shared contexts/units in the primary.
        existing={e.get('id') for e in root.iter() if e.get('id')}
        for tag in ('context','unit'):
            for e in parent.iter('{'+X+'}'+tag):
                if e.get('id') in existing: raise ValueError('linked_context_collision')
                root.append(copy.deepcopy(e))
        for e in metadata: root.append(e)
        result=parse_selected(companion,cik,filing,source_url,root,ns)
    if not result['facts']: raise ValueError('linked_financial_facts_missing')
    proof=verified['originalFiling']
    if result['originalFiling'].get('reportedTableRecoveries'):
        proof['reportedTableRecoveries']=result['originalFiling']['reportedTableRecoveries']
    proof['linkedAnnualDocument']={'method':'explicit-annual-link-v1','filename':filename,
        'sourceUrl':source_url.rsplit('/',1)[0]+'/'+filename,'sha256':hashlib.sha256(companion).hexdigest()}
    result['originalFiling']=proof
    return result
