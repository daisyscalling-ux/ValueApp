"""Conservative issuer-name equivalence for news only, never a security-master repair."""
import hashlib
import json
import re
import unicodedata
from collections import defaultdict

POLICY_VERSION='issuer-names-v1'
LEGAL_SUFFIXES=[tuple(x.split()) for x in [
 'societe anonyme','spolka akcyjna','aktiengesellschaft','corporation','incorporated',
 'limited','company','corp','inc','ltd','plc','oyj','abp','ag','sa','se','nv','bv','spa','as','ab','co']]

def tokens(value,german=False):
    s=str(value or '').casefold().replace('ø','o').replace('ł','l').replace('ß','ss').replace('&',' and ')
    if german:
        for a,b in [('ä','ae'),('ö','oe'),('ü','ue')]:s=s.replace(a,b)
    s=unicodedata.normalize('NFKD',s)
    s=''.join(c for c in s if not unicodedata.combining(c))
    s=re.sub(r'\b([a-z])\.(?=[a-z]\.)',r'\1',s)
    s=s.replace('a/s','as')
    return re.findall(r'[^\W_]+',s)

def canonical_names(value):
    result=set()
    for german in [False,True]:
        t=tokens(value,german)
        if t[:1]==['the']:t=t[1:]
        changed=True
        while changed:
            changed=False
            for suffix in LEGAL_SUFFIXES:
                if len(t)>len(suffix) and tuple(t[-len(suffix):])==suffix:
                    t=t[:-len(suffix)];changed=True;break
        # Do not collapse short brands/tickers or erase class/subsidiary descriptors.
        if len(''.join(t))>=5:result.add(' '.join(t))
    return result

def valid_isin(value):
    s=str(value or '').upper()
    if not re.fullmatch(r'[A-Z]{2}[A-Z0-9]{9}\d',s):return False
    digits=''.join(str(ord(c)-55) if c.isalpha() else c for c in s)
    total=0
    for i,c in enumerate(reversed(digits)):
        n=int(c)*(2 if i%2 else 1);total+=n//10+n%10
    return total%10==0

def class_conflict(row,info):
    name=str(row.get('name_full') or row.get('name') or '')
    expected=re.search(r'\bclass\s+([A-Z0-9]+)\b',name,re.I)
    if not expected:return False
    for field in ['longName','shortName']:
        actual=str(info.get(field) or '')
        explicit=re.search(r'\bclass\s+([A-Z0-9]+)\b',actual,re.I)
        trailing=re.search(r'\s([ABCR])$',actual)
        code=(explicit or trailing)
        if code and code.group(1).upper()!=expected.group(1).upper():return True
    return False

def auto_name_match(row,info):
    if row.get('_newsIdentityBlocked') or not valid_isin(row.get('isin')):return False
    if not row.get('exchange') or not row.get('listing_symbol'):return False
    expected=canonical_names(row.get('name_full') or row.get('name'))
    actual=canonical_names(info.get('longName'))
    return bool(expected & actual) and not row.get('_newsNameCollision',True)

def identity_fingerprint(row):
    fields=['ticker','listing_symbol','exchange','isin','currency','name_full','name','_newsNameCollision','_newsIdentityBlocked']
    return hashlib.sha256(json.dumps({k:row.get(k) for k in fields},sort_keys=True).encode()).hexdigest()

def prepare_universe(rows):
    names=defaultdict(set);tickers=defaultdict(list);listings=defaultdict(list)
    for row in rows:
        for name in canonical_names(row.get('name_full') or row.get('name')):names[name].add(row.get('isin') or 'unknown:'+str(row.get('ticker')))
        tickers[str(row.get('ticker','')).upper()].append(row)
        listings[str(row.get('listing_symbol') or row.get('ticker') or '').upper()].append(row)
    for row in rows:
        ticker=str(row.get('ticker','')).upper();listing=str(row.get('listing_symbol') or row.get('ticker') or '').upper()
        row['_newsIdentityBlocked']=not ticker or len(tickers[ticker])>1 or len(listings[listing])>1
        row['_newsNameCollision']=any(len(names[n])>1 for n in canonical_names(row.get('name_full') or row.get('name')))
    return {'rows':len(rows),'ambiguousListingRows':sum(bool(r['_newsIdentityBlocked']) for r in rows),
            'canonicalCollisionRows':sum(bool(r['_newsNameCollision']) for r in rows),
            'invalidOrMissingIsinRows':sum(not valid_isin(r.get('isin')) for r in rows),
            'policyVersion':POLICY_VERSION}

def audit_rows(rows,archive):
    result=[]
    for row in rows:
        symbol=str(row.get('listing_symbol') or row.get('ticker') or '').upper()
        old=archive.get('stocks',{}).get(symbol,{})
        evidence=old.get('identityEvidence') or {}
        current=(evidence.get('policyVersion')==POLICY_VERSION and evidence.get('inputFingerprint')==identity_fingerprint(row))
        state='rejected' if old.get('fallbackError') else 'accepted_current_policy' if current else 'legacy_check' if evidence else 'not_checked'
        result.append({'symbol':symbol,'name':row.get('name_full') or row.get('name'),
          'state':state,'reason':old.get('fallbackError'),'method':evidence.get('nameMatch'),
          'lastAttemptAt':old.get('fallbackAttemptAt'),'ambiguousListing':bool(row.get('_newsIdentityBlocked')),
          'nameCollision':bool(row.get('_newsNameCollision')),'validIsinChecksum':valid_isin(row.get('isin'))})
    return result

