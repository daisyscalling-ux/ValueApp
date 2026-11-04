"""Conservative fallback for explicitly reported annual PPE reconciliation tables.

This recovers cash purchases of PPE, not complete capex or valuation FCF.
The caller must first verify issuer, annual filing and inline-XBRL context.
"""
import copy
import math
import re
from html.parser import HTMLParser


class Tables(HTMLParser):
    def __init__(self):
        super().__init__();self.depth=0;self.cell=None;self.row=[];self.rows=[];self.tail='';self.tables=[];self.caption='';self.nested=False
    def handle_starttag(self,tag,attrs):
        tag=tag.split(':')[-1]
        if tag=='table':
            if not self.depth:self.rows=[];self.caption=self.tail[-700:];self.nested=False
            else:self.nested=True
            self.depth+=1
        if self.depth and tag=='tr':self.row=[]
        if self.depth and tag in ('td','th'):self.cell=[]
    def handle_data(self,data):
        self.tail=(self.tail+' '+data)[-1000:]
        if self.cell is not None:self.cell.append(data)
    def handle_endtag(self,tag):
        tag=tag.split(':')[-1]
        if self.depth and tag in ('td','th') and self.cell is not None:
            self.row.append(' '.join(''.join(self.cell).split()));self.cell=None
        if self.depth and tag=='tr':self.rows.append(self.row)
        if tag=='table' and self.depth:
            self.depth-=1
            if not self.depth and not self.nested and re.search(r'reconciliation',self.caption,re.I) and re.search(r'\bin millions\b',self.caption,re.I):self.tables.append((self.caption,self.rows))


def recover(raw,facts):
    gaap=facts.get('us-gaap',{});ocfs=gaap.get('NetCashProvidedByUsedInOperatingActivities',{}).get('units',{}).get('USD',[])
    if not ocfs:return []
    parser=Tables();parser.feed(raw.decode('utf-8-sig'))
    found=[]
    labels={'net cash provided by operating activities':'ocf','purchases of property and equipment':'ppe','fcf':'fcf','free cash flow':'fcf'}
    for caption,rows in parser.tables:
        # No scale inference from number magnitudes or a distant report heading.
        if not re.search(r'reconciliation',caption,re.I) or not re.search(r'\bin millions\b',caption,re.I):continue
        years=[];values={};invalid=False
        for row in rows:
            cells=[c.strip() for c in row if c.strip() and c.strip()!='$']
            if len(cells) in (2,3) and all(re.fullmatch(r'20\d{2}',c) for c in cells):
                if years:invalid=True
                years=[int(c) for c in cells];continue
            if not cells or cells[0].casefold() not in labels:continue
            key=labels[cells[0].casefold()]
            if key in values:invalid=True;continue
            nums=[]
            for c in cells[1:]:
                if not re.fullmatch(r'(?:-?\d[\d,]*(?:\.\d+)?|\(\d[\d,]*(?:\.\d+)?\))',c):invalid=True;break
                v=float(c.replace(',','').replace('(','-').replace(')',''))
                if not math.isfinite(v):invalid=True;break
                nums.append(v*1_000_000)
            values[key]=nums
        if invalid or len(set(years))!=len(years) or not years or set(values)!={'ocf','ppe','fcf'} or any(len(v)!=len(years) for v in values.values()):continue
        for i,year in enumerate(years):
            ocf,ppe,fcf=(values[k][i] for k in ('ocf','ppe','fcf'))
            # The table is a subtraction bridge; parentheses denote an outflow.
            if ppe>0 or abs(ocf+ppe-fcf)>1:continue
            matches=[f for f in ocfs if f.get('end')==f'{year}-12-31' and f.get('start')==f'{year}-01-01' and abs(f['val']-ocf)<=500_000]
            if len({(f['start'],f['end'],f['accn'],f['filed'],f['val']) for f in matches})!=1:continue
            f=copy.deepcopy(matches[0]);f['val']=-ppe
            f['reportedTableEvidence']={'method':'explicit-annual-ppe-reconciliation-v1','year':year,'scale':1_000_000,'operatingCashflow':ocf,'reportedFcf':fcf,'cashPpe':-ppe,'scope':'Reported PPE purchases only; not full capex or valuation FCF'}
            found.append(f)
    # Conflicting tables must not create a chosen arbitrary observation.
    result=[]
    for end in sorted({f['end'] for f in found}):
        same=[f for f in found if f['end']==end]
        if len({f['val'] for f in same})==1:result.append(same[0])
    return result
