"""Reviewed insurer group disclosures; no inference from IFRS equity or ratio-only data."""
import datetime as dt
import math
from collections import Counter
from urllib.parse import urlparse
from news_identity import valid_isin

FIELDS=('listing_symbol','ticker','isin','currency','name','name_full','security_type','share_class')
SOURCE='reviewed_insurer_original_reports'
def date(value):
 try:return dt.date.fromisoformat(value) if isinstance(value,str) and len(value)==10 else None
 except ValueError:return None
def number(value):return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)
def url(value):
 try:return urlparse(value).scheme=='https' and bool(urlparse(value).hostname)
 except (TypeError,ValueError):return False
def observation(o,today,reviewed):
 if not isinstance(o,dict):return None
 period=date(o.get('period'));limit={'annual':550,'interim':210}.get(o.get('reportKind'))
 if not period or limit is None or not 0<=(today-period).days<=limit or period>reviewed:return None
 if o.get('currency')!='EUR' or o.get('unit')!='currency_units' or not url(o.get('sourceUrl')):return None
 if not all(isinstance(o.get(k),str) and o[k].strip() for k in ('sourcePages','basis','basisNote')):return None
 ratio=o.get('ratio');own=o.get('eligibleOwnFunds');scr=o.get('solvencyRequirement')
 if not number(ratio) or not 0<=ratio<=20:return None
 complete=own is not None or scr is not None
 if complete and (not number(own) or own<0 or not number(scr) or scr<=0 or abs(own/scr-ratio)>.015):return None
 return {**o,'amountsVerified':complete}

def build_insurers(universe,registry,now=None):
 now=now or dt.datetime.now(dt.timezone.utc);today=now.date()
 out={'schema':1,'source':SOURCE,'generatedAt':now.isoformat(),'stocks':{},'rejected':{},'scoreContribution':0}
 reviewed=date(registry.get('reviewedOn'));expires=date(registry.get('reviewExpires'))
 if registry.get('schema')!=1 or registry.get('source')!=SOURCE or not reviewed or not expires or not reviewed<=today<=expires:
  out['state']='review_unavailable';return out
 entries=registry.get('entries',[]);counts=Counter(e.get('inputIdentity',{}).get('listing_symbol') for e in entries)
 rows=universe.get('kandidaten',[]);rowcounts=Counter(r.get('listing_symbol') for r in rows)
 for row in rows:
  symbol=row.get('listing_symbol');matching=[e for e in entries if e.get('inputIdentity',{}).get('listing_symbol')==symbol]
  if not matching:continue
  e=matching[0]
  if counts[symbol]!=1 or rowcounts[symbol]!=1 or not valid_isin(row.get('isin')) or row.get('security_type') not in ('stock','common_stock','common','equity') or row.get('share_class') not in (None,'','common','ordinary') or row.get('listing_reference_status') in ('expired','input_mismatch') or any(row.get(k)!=e.get('inputIdentity',{}).get(k) for k in FIELDS):
   out['rejected'][symbol]='identity_mismatch';continue
  if e.get('scope')!='insurance_group' or e.get('framework')!='Solvency II' or e.get('jurisdiction')!='DE' or e.get('regulator')!='BaFin' or not url(e.get('scopeSourceUrl')) or not e.get('scopeSourcePages'):
   out['rejected'][symbol]='scope_unverified';continue
  valid=[v for o in e.get('observations',[]) if (v:=observation(o,today,reviewed))]
  complete=sorted((o for o in valid if o['amountsVerified']),key=lambda o:o['period'],reverse=True)
  if not complete or sum(o['period']==complete[0]['period'] for o in complete)>1:
   out['rejected'][symbol]='complete_basis_unavailable_or_ambiguous';continue
  primary=complete[0]
  out['stocks'][symbol]={**e,'state':'available','observations':valid,'primary':primary,'reviewedOn':reviewed.isoformat(),'reviewExpires':expires.isoformat(),'pointInTimeUsable':False,'scoreContribution':0}
 out['state']='ready';out['summary']={'verifiedListings':len(out['stocks']),'rejected':dict(Counter(out['rejected'].values()))}
 return out
