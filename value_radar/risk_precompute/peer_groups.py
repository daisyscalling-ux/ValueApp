"""Step 1: auditable issuer cohorts. No risk metrics or valuation changes."""
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from collections import Counter, defaultdict
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from listing_reference import apply_reference
from news_identity import valid_isin

HERE = Path(__file__).resolve().parent
UTC = dt.timezone.utc
ALLOWED = {'stock','equity','common','common_stock','ordinary','ordinary_share','dr','adr'}

def norm(value):
    return ' '.join(str(value or '').casefold().split())

def name_key(row):
    # Conservative punctuation/class cleanup; retain legal names and Holdings.
    name = norm(row.get('name_full') or row.get('name'))
    name = re.sub(r'\bclass\s+[a-z0-9]+\b', '', name)
    name = re.sub(r'\b(?:adr|depositary receipts|bearer|registered shares|pref)\s*$', '', name)
    return re.sub(r'[^\w]', '', name)

def symbol(row):
    return str(row.get('listing_symbol') or row.get('ticker') or '').upper()

def fresh(value, now):
    try:
        date = dt.datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return date.tzinfo is not None and dt.timedelta(0) <= now-date <= dt.timedelta(days=90)
    except (TypeError, ValueError):
        return False

def classify(row, rules, now):
    industry = norm(row.get('industry'))
    family = rules['aliases'].get(industry, industry)
    for rule in rules['reviewed']:
        if row.get('isin') not in rule['isins']:
            continue
        if name_key(row) not in rule['names']:
            return {'state':'review', 'reason':'reviewed_identity_mismatch'}
        if not rule['reviewedAt'] <= now.date().isoformat() <= rule['validUntil']:
            return {'state':'review', 'reason':'business_model_review_expired'}
        return {'state':'classified', 'group': 'model:'+rule['group'],
                'label':rule['label'], 'level':'reviewed_business_model',
                'source':rule['source'], 'reviewedAt':rule['reviewedAt'],
                'reason':'source_backed_business_activity'}
    sub = norm(row.get('sub_industry'))
    if sub and sub not in {'unknown','n/a','none',industry}:
        return {'state':'classified','group':'sub:'+family+':'+sub,'label':row['sub_industry'],
                'level':'provider_subindustry','source':row.get('metadata_source'),
                'reason':'provider_subindustry_not_independently_verified'}
    if not industry or industry in {'unknown','n/a','none'}:
        return {'state':'review','reason':'industry_missing'}
    return {'state':'classified','group':'industry:'+family,'label':family,
            'level':'industry_context','source':row.get('metadata_source'),
            'reason':'broad_industry_requires_business_model_review'}

def build(universe, now=None, rules=None):
    now = now or dt.datetime.now(UTC)
    rules = rules or json.loads((HERE/'peer-group-rules.json').read_text(encoding='utf8'))
    rows = [apply_reference(dict(r), now.date()) for r in universe.get('kandidaten', [])]
    original = {symbol(r):r for r in universe.get('kandidaten', [])}
    counts = Counter(symbol(r) for r in rows)
    eligible, excluded = [], []
    for r in rows:
        reason = None
        if not symbol(r) or counts[symbol(r)] != 1: reason = 'missing_or_duplicate_listing'
        elif not r.get('listing_symbol') or ':' not in symbol(r): reason = 'unconfirmed_listing'
        elif str(r.get('security_type') or '').lower() not in ALLOWED: reason = 'unsupported_security_type'
        elif not name_key(r): reason = 'issuer_name_missing'
        elif not valid_isin(r.get('isin')): reason = 'valid_isin_missing'
        elif r.get('listing_reference_status') in {'expired','input_mismatch'}: reason = 'listing_reference_review'
        elif not fresh(r.get('metadata_asof'), now): reason = 'metadata_missing_or_stale'
        if reason: excluded.append({'symbol':symbol(r), 'reason':reason}); continue
        eligible.append(r)

    # Union all supported links: using one preferred ID alone misses ADR/local pairs.
    parent = list(range(len(eligible)))
    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]; i = parent[i]
        return i
    def union(a,b):
        a,b=root(a),root(b)
        if a != b: parent[max(a,b)] = min(a,b)
    seen = {}
    for i,r in enumerate(eligible):
        cik = str(r.get('cik') or '').strip().lstrip('0')
        ids = [('isin',r['isin']), ('name',name_key(r))]
        if cik.isdigit(): ids.append(('cik',cik))
        if r.get('lei'): ids.append(('lei',str(r['lei']).upper()))
        for identifier in ids:
            if identifier in seen: union(i,seen[identifier])
            else: seen[identifier] = i
    clusters = defaultdict(list)
    for i,r in enumerate(eligible): clusters[root(i)].append(r)
    issuers, review = [], []
    for members in clusters.values():
        members.sort(key=lambda r: (r.get('is_primary') is not True,
                     symbol(r).startswith('OTC:'),
                     str(r.get('security_type')).lower() in {'dr','adr'},symbol(r)))
        ids = sorted(symbol(r) for r in members)
        classifications = [classify(r,rules,now) for r in members]
        ciks = {str(r['cik']).lstrip('0') for r in members if r.get('cik')}
        leis = {r['lei'] for r in members if r.get('lei')}
        reasons=[]
        if len(ciks)>1 or len(leis)>1: reasons.append('conflicting_issuer_identifiers')
        if any(c['state']!='classified' for c in classifications): reasons.append('classification_review')
        if len({c.get('group') for c in classifications}) != 1: reasons.append('conflicting_business_classifications')
        if reasons:
            review.append({'listings':ids,'reasons':reasons});continue
        rep=members[0]; c=classifications[0]
        issuer_id='issuer:'+hashlib.sha256('|'.join(sorted({r['isin'] for r in members})).encode()).hexdigest()[:20]
        issuers.append({'id':issuer_id,'representative':symbol(rep),'name':rep.get('name_full') or rep.get('name'),
                        'listings':ids,'classification':c,'currencies':sorted({str(r.get('currency')) for r in members if r.get('currency')}),
                        'countries':sorted({str(r.get('country')) for r in members if r.get('country')}),
                        'metadataDates':sorted({r['metadata_asof'] for r in members})})
    groups=defaultdict(list)
    for item in issuers: groups[item['classification']['group']].append(item)
    listing_groups={}
    for item in issuers:
        peers=sorted((p for p in groups[item['classification']['group']] if p['id']!=item['id']),key=lambda p:p['representative'])
        for listing in item['listings']:
            listing_groups[listing]={'issuerId':item['id'],'group':item['classification']['group'],
              'inputIdentity':{k:original[listing].get(k) for k in ['isin','currency','industry','sub_industry','name_full','security_type']},
              'level':item['classification']['level'],'peerIssuerCount':len(peers),
              'peerSymbols':[p['representative'] for p in peers],
              'state':'ready' if len(peers)>=5 else 'small_group',
              'reason':'same_business_activity' if item['classification']['level']=='reviewed_business_model' else item['classification']['reason'],
              'directCompetitorsVerified':False}
    summary={'inputListings':len(rows),'classifiedListings':len(listing_groups), 'uniqueIssuers':len(issuers),
             'collapsedAdditionalListings':sum(len(i['listings'])-1 for i in issuers),
             'excludedListings':len(excluded),'reviewListings':sum(len(r['listings']) for r in review),
             'groups':len(groups),'levels':dict(Counter(i['classification']['level'] for i in issuers)),
             'withFivePeers':sum(r['peerIssuerCount']>=5 for r in listing_groups.values())}
    return {'schema':1,'method':'issuer-business-groups-v1','generatedAt':now.isoformat(),
            'inputSha256':hashlib.sha256(json.dumps(universe,sort_keys=True).encode()).hexdigest(),
            'summary':summary,'listings':dict(sorted(listing_groups.items())),
            'issuers':sorted(issuers,key=lambda i:i['id']),'excluded':excluded,'review':review,
            'limitations':['Step 1 only: membership, not a risk score or return comparison.',
              'Broad provider industries are context cohorts, not verified direct competitors.',
              'Membership spans currencies; later return comparisons must handle currency and market exposure.',
              'Small groups remain small: no padding with unrelated companies.']}

def main():
    folder=Path(os.environ.get('RISK_DATA_DIR',str(HERE.parent/'daten')))
    result=build(json.loads((folder/'cf_universum.json').read_text(encoding='utf8')))
    output=folder/'cf_peer_groups.json';temp=output.with_suffix('.tmp')
    temp.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');temp.replace(output)
    print(json.dumps(result['summary']))
if __name__=='__main__':main()
