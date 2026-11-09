"""Conservative news triage, explicit reviewed decisions and bank credit context."""
import copy
import datetime as dt
import math
import re
import statistics
from collections import Counter,defaultdict
from urllib.parse import urlsplit
from company_news import stamp
from news_identity import prepare_universe,identity_fingerprint

SOLICITATION=re.compile(r'\b(lead plaintiff|opportunity to lead|contact.{0,45}(law|firm|levi|kessler)|investors should contact|shareholder.{0,20}(alert|notice)|investor.{0,20}deadline|reminds.{0,100}(investors|shareholders)|(class action|lawsuit).{0,80}deadline)\b',re.I)
CODES={'nonaccrual':'BHCK1403','past_due_30_89':'BHCK1406','past_due_90':'BHCK1407','held_for_investment':'BHCKB528','held_for_sale':'BHCK5369'}


def review_news(report,universe,registry,now):
    """Only explicit, dated, identity-bound review records can confirm an event."""
    result=copy.deepcopy(report);rows=copy.deepcopy(universe.get('kandidaten',[]));prepare_universe(rows)
    symbols=Counter(r.get('listing_symbol') or r.get('ticker') for r in rows)
    identities={r.get('listing_symbol') or r.get('ticker'):identity_fingerprint(r) for r in rows if symbols[r.get('listing_symbol') or r.get('ticker')]==1 and not r.get('_newsIdentityBlocked')}
    decisions=registry.get('decisions',[]) if registry.get('schema')==1 else []
    counts=Counter((d.get('candidateId'),d.get('symbol')) for d in decisions)
    by_key={(d.get('candidateId'),d.get('symbol')):d for d in decisions}
    for c in result.get('candidates',[]):
        solicitation=bool(SOLICITATION.search(c['headline'])) and 'legal_regulatory' in c['categories']
        c['triage']={'kind':'legal_solicitation' if solicitation else 'event_candidate',
            'explanation':'Anwaltsaufruf; kein neuer Schaden oder Schuldspruch daraus ableitbar.' if solicitation else 'Ereignis und betroffene Firma anhand der Originalquelle pruefen.',
            'scoreContribution':0}
        c['decisions']=[]
        for symbol in c['associatedSymbols']:
            key=(c['id'],symbol);d=by_key.get(key)
            if not d:continue
            reason=validate_decision(d,c,identities,now) if counts[key]==1 else 'conflicting_review_records'
            if reason:c['decisions'].append({'symbol':symbol,'state':'review_invalid','reason':reason});continue
            c['decisions'].append(copy.deepcopy(d))
        confirmed=[d['symbol'] for d in c['decisions'] if d['state']=='confirmed_event']
        c['verified']=bool(confirmed);c['verifiedSymbols']=confirmed
        if set(confirmed)==set(c['associatedSymbols']):
            c['reviewFlags']=[f for f in c.get('reviewFlags',[]) if f not in ('company_subject_unverified','event_not_verified')]
        c['state']='partially_reviewed' if c['decisions'] else 'review_required'
        c['scoreContribution']=0
    result['summary']['legalSolicitationClusters']=sum(c['triage']['kind']=='legal_solicitation' for c in result['candidates'])
    result['summary']['confirmedEventClusters']=sum(bool(c['verifiedSymbols']) for c in result['candidates'])
    result['summary']['invalidReviewDecisions']=sum(d['state']=='review_invalid' for c in result['candidates'] for d in c['decisions'])
    queue=defaultdict(list)
    for c in result['candidates']:
        if c['triage']['kind']=='legal_solicitation':
            for symbol in c['associatedSymbols']:queue[symbol].append(c['id'])
    result['legalSolicitationQueue']=[{'symbol':s,'candidateIds':ids,'scoreContribution':0,'note':'Gemeinsamer Pruefkorb, kein Nachweis identischer Verfahren oder mehrerer unabhaengiger Risiken.'} for s,ids in sorted(queue.items())]
    result['limitations'].append('Confirmation means a documented event, not a measured loss probability. Manual review records expire and apply only to their exact candidate and issuer identity.')
    return result


def validate_decision(d,c,identities,now):
    if d.get('state') not in ('confirmed_event','not_subject_of_tagged_event'):return 'unsupported_decision'
    if d.get('inputFingerprint')!=identities.get(d.get('symbol')) or not d.get('inputFingerprint'):return 'issuer_identity_changed'
    reviewed=stamp(d.get('reviewedAt'));expires=stamp(d.get('expiresAt'))
    if not reviewed or not expires or not reviewed<=now<expires or expires-reviewed>dt.timedelta(days=30):return 'review_date_invalid_or_expired'
    if not d.get('reviewer') or not d.get('rationale') or not d.get('sourceUrl'):return 'review_evidence_missing'
    p=urlsplit(d['sourceUrl'])
    if p.scheme!='https' or not p.hostname or p.username or p.password:return 'review_source_invalid'
    if d['state']=='confirmed_event':
        if d.get('sourceType')!='issuer_primary' or not d.get('sourceLocator') or not d.get('eventDate') or not d.get('counterContext'):return 'primary_evidence_incomplete'
        try:event=dt.date.fromisoformat(d['eventDate'])
        except ValueError:return 'event_date_invalid'
        if event>reviewed.date() or (reviewed.date()-event).days>30:return 'event_date_invalid'
        if d.get('sourceAccess') not in ('direct','indexed_official_release'):return 'source_access_unrecorded'
    elif d.get('sourceUrl') not in {s['url'] for s in c['sources']}:return 'rejection_source_mismatch'
    return None


def valid_credit(row,now):
    b=row.get('domains',{}).get('balance',{});p=b.get('bankCapital') or {};c=p.get('creditQuality') or {}
    # Spezialfinanzierer mit geprueftem US-Holding-Kapital (z. B. Goldman Sachs, Schwab) sind Bankkonzerne.
    if b.get('profile') not in ('bank','specialist_financial') or row.get('domains',{}).get('identity',{}).get('state')!='available':return None
    if p.get('state')!='available' or p.get('scope')!='listed_consolidated_holding' or c.get('state')!='available' or c.get('method')!='bhcf-loan-quality-v1':return None
    if any(c.get(k)!=p.get(k) or not p.get(k) for k in ('period','rssdId','sourceFileSha256')):return None
    date=stamp(p['period']+'T00:00:00+00:00');imported=stamp(c.get('sourceImportedAt'))
    if not date or not dt.timedelta(0)<=now-date<=dt.timedelta(days=180) or not imported or not date<=imported<=now:return None
    if not re.fullmatch(r'[0-9a-f]{64}',c['sourceFileSha256']) or c.get('unit')!='fraction' or c.get('amountUnit')!='USD_thousands':return None
    f=c.get('components',{})
    if any(c.get('sourceFields',{}).get(k)!=v or type(f.get(k)) is not int or not 0<=f[k]<=9_007_199_254_740 for k,v in CODES.items()):return None
    total=f['held_for_investment']+f['held_for_sale']
    if total<=0 or total!=c.get('totalLoans') or sum(f[k] for k in ('nonaccrual','past_due_30_89','past_due_90'))>total:return None
    ratio=(f['nonaccrual']+f['past_due_90'])/total
    supplied=c.get('ratios',{}).get('nonaccrual_or_90_past_due')
    if type(supplied) not in (int,float) or not math.isfinite(supplied) or abs(supplied-ratio)>1e-12:return None
    return {'symbol':row['symbol'],'rssdId':p['rssdId'],'period':p['period'],'ratio':ratio,'sourceUrl':c.get('sourceUrl'),'sourceFileSha256':c['sourceFileSha256']}


def bank_credit_comparison(coverage,now):
    groups=defaultdict(list)
    for row in coverage.get('stocks',[]):
        c=valid_credit(row,now)
        if c:groups[(c['period'],c['rssdId'])].append(c)
    unique=defaultdict(list);conflicts=[]
    for (period,rssd),rows in groups.items():
        if len({(r['ratio'],r['sourceFileSha256']) for r in rows})!=1:conflicts.append(rssd);continue
        unique[period].append({**rows[0],'symbols':sorted({r['symbol'] for r in rows})})
    stocks={}
    for period,rows in unique.items():
        for r in rows:
            peers=[x['ratio'] for x in rows if x['rssdId']!=r['rssdId']]
            median=statistics.median(peers) if len(peers)>=5 else None
            comparison='peer_base_too_small' if median is None else 'above_peer_median' if r['ratio']>median+1e-12 else 'below_peer_median' if r['ratio']<median-1e-12 else 'at_peer_median'
            for symbol in r['symbols']:
                stocks[symbol]={**r,'symbol':symbol,'state':'available','peerCount':len(peers),'peerMedian':median,'comparison':comparison,'scoreContribution':0,
                    'label':'Kredite ohne Zinsvereinnahmung oder mindestens 90 Tage ueberfaellig / Gesamtkredite',
                    'interpretation':'Ein hoeherer Anteil bedeutet mehr bereits auffaellige Kredite. Geschaeftsmodell, Besicherung, Garantien und Trend koennen den Vergleich wesentlich beeinflussen.',
                    'limitations':['Gleiche US-Meldedefinition und Periode, aber unterschiedliche Kreditportfolios.','Kein erwarteter Kreditausfall, keine IFRS-NPL-Gleichsetzung und keine automatische Risikopunktzahl.']}
    return {'method':'same-period-us-holding-credit-comparison-v1','stocks':stocks,'excludedConflictingHoldings':sorted(conflicts),'scoreContribution':0}
