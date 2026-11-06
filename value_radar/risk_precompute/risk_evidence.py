"""Universe-wide review packets and immutable prospective input observations.

No automatic event verification, score change, or retrospective data dating.
"""
import copy
import datetime as dt
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
from urllib.parse import urlsplit,urlunsplit,parse_qsl,urlencode
from company_news import PATTERNS,stamp
from news_identity import prepare_universe,identity_fingerprint
from market_priority import market_tier
from yahoo_sector import load,save,recent
from risk_review import review_news,bank_credit_comparison


def encoded(value):return json.dumps(value,sort_keys=True,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode('utf-8')
def digest(value):return hashlib.sha256(value).hexdigest()


def article_url(value):
    try:
        p=urlsplit(value)
        if p.scheme not in ('http','https') or not p.hostname or p.username or p.password:return None
        query=parse_qsl(p.query)
        if any(k.lower() in ('apikey','api_key','token','access_token') for k,v in query):return None
        return urlunsplit((p.scheme,p.netloc.lower(),p.path,urlencode([(k,v) for k,v in query if not k.lower().startswith('utm_') and k.lower() not in ('mod','ref')]),''))
    except (ValueError,TypeError):return None


def news_review(universe,coverage,archive,now):
    rows=copy.deepcopy(universe.get('kandidaten',[]));prepare_universe(rows)
    counts={};groups={};states={};domains={r['symbol']:r.get('domains',{}) for r in coverage.get('stocks',[])}
    for r in rows:
        symbol=r.get('listing_symbol') or r.get('ticker');counts[symbol]=counts.get(symbol,0)+1
    for row in rows:
        symbol=row.get('listing_symbol') or row.get('ticker')
        if not symbol:continue
        source=archive.get('stocks',{}).get(symbol,{})
        if counts[symbol]!=1 or row.get('_newsIdentityBlocked') or domains.get(symbol,{}).get('identity',{}).get('state')!='available' or source.get('inputFingerprint')!=identity_fingerprint(row):
            states[symbol]='identity_unconfirmed';continue
        if archive.get('schema')!=1 or not recent(source.get('successAt'),now,1.5):states[symbol]='missing_or_stale';continue
        states[symbol]='no_tagged_candidate_in_sample'
        for item in source.get('items',[]):
            title=item.get('title');date=stamp(item.get('publishedAt'));url=article_url(item.get('url'))
            if not isinstance(title,str) or not title.strip() or not url or not date or not dt.timedelta(0)<=now-date<=dt.timedelta(days=7):continue
            title=' '.join(title.split())[:500]
            tags=sorted(k for k,p in PATTERNS.items() if re.search(p,title,re.I))
            if not tags:continue
            states[symbol]='review_required'
            # Equal headlines may be syndicated copies, not independent confirmations.
            key=digest(title.casefold().encode())
            g=groups.setdefault(key,{'id':key,'headline':title,'categories':tags,'associatedSymbols':set(),'sources':{},'firstPublishedAt':date.isoformat(),'lastPublishedAt':date.isoformat()})
            g['associatedSymbols'].add(symbol)
            g['firstPublishedAt']=min(g['firstPublishedAt'],date.isoformat());g['lastPublishedAt']=max(g['lastPublishedAt'],date.isoformat())
            g['sources'][url]={'url':url,'publishedAt':date.isoformat(),'publisher':str(item.get('publisher') or urlsplit(url).hostname)[:150]}
    out=[]
    for g in groups.values():
        symbols=sorted(g.pop('associatedSymbols'));sources=sorted(g.pop('sources').values(),key=lambda x:x['url'])
        flags=['company_subject_unverified','event_not_verified']
        if len(symbols)>1:flags.append('cross_company_association_requires_review')
        if len(sources)>1:flags.append('syndication_or_duplicate_coverage_possible')
        if re.search(r'\b(no|not|denies?|denied|could|may|might|if|kein|keine|dementiert|k\u00f6nnte)\b',g['headline'],re.I):flags.append('negation_or_hypothetical_language')
        out.append({**g,'associatedSymbols':symbols,'marketTier':min(market_tier(s) for s in symbols),'sources':sources,
            'expiresAt':(stamp(g['lastPublishedAt'])+dt.timedelta(days=7)).isoformat(),'reviewFlags':flags,
            'state':'review_required','verified':False,'scoreContribution':0,
            'requiredChecks':['read_original_source','confirm_subject_and_affected_business','confirm_event_date_and_actual_occurrence','check_independent_evidence_and_counterevidence']})
    return {'schema':1,'method':'headline-review-packets-v1','generatedAt':now.isoformat(),'stocks':states,
        'summary':{'listings':len(states),'candidateClusters':len(out),'listingsWithCandidates':sum(v=='review_required' for v in states.values())},
        'candidates':sorted(out,key=lambda x:(x['marketTier'],x['id'])),
        'limitations':['Bounded English/German headline rules, not a complete event feed.','Publisher count is not independent verification.','No tagged candidate does not mean low risk; no automatic cross-company risk transfer.']}


def sector_packets(coverage,now):
    groups={}
    for row in coverage.get('stocks',[]):
        b=row.get('domains',{}).get('balance',{});profile=b.get('profile')
        if profile not in ('bank','insurer','specialist_financial'):continue
        requirements=b.get('sectorAssessment',{}).get('openRequirements',b.get('sectorRequirements',[]))
        if not requirements:continue
        country=row.get('country') or 'unconfirmed'
        key=(market_tier(row['symbol']),profile,country)
        g=groups.setdefault(key,{'marketTier':key[0],'profile':profile,'listingCountry':country,'companies':[]})
        capital=b.get('bankCapital',{}) or {}
        g['companies'].append({'symbol':row['symbol'],'name':row.get('name'),'openRequirements':sorted(set(requirements)),
            'fulfilledRequirements':b.get('sectorAssessment',{}).get('fulfilledRequirements',[]),
            'availableContext':{'capital':capital.get('state')=='available','loanQuality':capital.get('creditQuality',{}).get('state')=='available' if capital.get('creditQuality') else False},
            'requiredScope':'listed consolidated issuer; verify jurisdiction separately from listing country'})
    return {'schema':1,'generatedAt':now.isoformat(),'scoreContribution':0,'packets':[{**g,'companies':sorted(g['companies'],key=lambda x:x['symbol'])} for _,g in sorted(groups.items())],
        'limitations':['Listing country is routing metadata, not verified regulatory jurisdiction.','Book ratios and loan-quality context do not automatically satisfy regulatory requirements.']}


def checkpoint(folder,now,code_version):
    folder=Path(folder)
    names=('cf_universum.json','cf_risk_coverage.json','cf_risk.json','cf_company_news.json','cf_risk_run_integrity.json','cf_risk_event_review.json','cf_sector_review_packets.json')
    raw={n:(folder/n).read_bytes() for n in names};data={n:json.loads(v) for n,v in raw.items()}
    integrity=data['cf_risk_run_integrity.json'];coverage=data['cf_risk_coverage.json'];universe=data['cf_universum.json']
    if integrity.get('state')!='verified' or integrity.get('processedSha256')!=digest(raw['cf_universum.json']):raise ValueError('unverified_observation_inputs')
    if not recent(coverage.get('generatedAt'),now,1.5) or integrity.get('generatedAt')!=coverage.get('generatedAt'):raise ValueError('stale_observation_coverage')
    symbols=[r['symbol'] for r in coverage['stocks']]
    expected=[r.get('listing_symbol') or r.get('ticker') for r in universe['kandidaten']]
    if len(symbols)!=len(set(symbols)) or sorted(symbols)!=sorted(expected):raise ValueError('observation_universe_mismatch')
    target=folder/'risk_observations';target.mkdir(parents=True,exist_ok=True)
    path=target/(now.date().isoformat()+'.json.gz')
    if path.exists():
        saved=json.loads(gzip.decompress(path.read_bytes()))
        if saved.get('method')!='prospective-risk-input-manifest-v1' or not stamp(saved.get('observedAt')) or stamp(saved.get('observedAt')).date()!=now.date():raise ValueError('existing_observation_invalid')
        return {'state':'retained_first_daily_observation','file':path.name,'observedAt':saved['observedAt'],'sha256':digest(path.read_bytes())}
    snapshot={'schema':1,'method':'prospective-risk-input-manifest-v1','observedAt':now.isoformat(),'codeVersion':code_version,
        'horizonsTradingDays':[21,63,126],'modelValidationStatus':'inputs_archived_no_full_model_validation',
        'sourceHashes':{n:digest(v) for n,v in raw.items()},
        'inputResolution':'Read source files from the Git commit that first added this observation; verify every SHA256 before use.',
        'summary':{'listings':len(symbols),'news':data['cf_risk_event_review.json'].get('summary',{})},
        'limitations':['Observed now, never backdated to financial period or article date.','No completed full-model score or outcome labels inferred.','Historical vendor revisions remain possible; future outcomes require separately dated total-return observations.']}
    payload=gzip.compress(encoded(snapshot),mtime=0)
    with path.open('xb') as f:f.write(payload)
    return {'state':'recorded','file':path.name,'observedAt':snapshot['observedAt'],'sha256':digest(payload),'bytes':len(payload),'listings':len(symbols)}


def resolve_inputs(snapshot,read_source):
    """read_source must read the Git revision that first introduced this manifest."""
    if snapshot.get('method')!='prospective-risk-input-manifest-v1':raise ValueError('unknown_observation_method')
    expected={'cf_universum.json','cf_risk_coverage.json','cf_risk.json','cf_company_news.json','cf_risk_run_integrity.json','cf_risk_event_review.json','cf_sector_review_packets.json'}
    hashes=snapshot.get('sourceHashes',{})
    if set(hashes)!=expected:raise ValueError('observation_source_set_mismatch')
    resolved={}
    for name,sha in hashes.items():
        raw=read_source(name)
        if digest(raw)!=sha:raise ValueError('observation_source_hash_mismatch')
        resolved[name]=json.loads(raw)
    return resolved


def main():
    folder=Path(os.getenv('RISK_DATA_DIR',str(Path(__file__).resolve().parents[1]/'daten')));now=dt.datetime.now(dt.timezone.utc)
    universe=load(folder/'cf_universum.json',{});coverage=load(folder/'cf_risk_coverage.json',{})
    if not recent(coverage.get('generatedAt'),now,1.5):raise ValueError('coverage_stale')
    news=news_review(universe,coverage,load(folder/'cf_company_news.json',{}),now)
    news=review_news(news,universe,load(Path(__file__).with_name('reviewed-risk-events.json'),{}),now)
    sector=sector_packets(coverage,now)
    sector['bankCreditComparison']=bank_credit_comparison(coverage,now)
    news['coverageGeneratedAt']=coverage['generatedAt']
    sector['coverageGeneratedAt']=coverage['generatedAt']
    save(folder/'cf_risk_event_review.json',news);save(folder/'cf_sector_review_packets.json',sector)
    report=checkpoint(folder,now,os.getenv('GITHUB_SHA','local-unversioned'))
    save(folder/'cf_risk_observation_status.json',report)
    result={'news':news['summary'],'sectorPackets':len(sector['packets']),'observation':report}
    print(json.dumps(result))
    if os.getenv('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'],'a',encoding='utf-8') as f:f.write('\n## Ereignispruefung und prospektive Daten\n'+json.dumps(result)+'\nKeine automatische Ereignisbestaetigung oder neue Risikopunkte.\n')


if __name__=='__main__':main()
