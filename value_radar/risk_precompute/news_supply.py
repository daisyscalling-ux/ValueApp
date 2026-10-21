"""Provider-specific retry and coverage classification; missing news is not safety."""
import datetime as dt
from collections import Counter

def stamp(value):
    try:
        d=dt.datetime.fromisoformat(str(value).replace('Z','+00:00'))
        return d if d.tzinfo else None
    except (ValueError,TypeError):return None

def yahoo_wait_hours(old):
    if old.get('fallbackError') in ['yahoo_share_class_conflict','yahoo_issuer_name_mismatch','yahoo_ambiguous_listing']:return 168
    result=old.get('yahooResult') or {}
    if not old.get('fallbackError') and (result.get('acceptedArticles')==0 or old.get('source')=='Yahoo Finance' and not old.get('items')):return 72
    return 20

def yahoo_due(old,now,corrected=False):
    if corrected:return True
    last=stamp(old.get('fallbackAttemptAt'))
    return not last or now-last>=dt.timedelta(hours=yahoo_wait_hours(old))

def coverage_plan(rows,archive,now):
    entries=[]
    for row in rows:
        symbol=str(row.get('listing_symbol') or row.get('ticker') or '').upper()
        old=archive.get('stocks',{}).get(symbol,{})
        fresh=stamp(old.get('successAt'));articles=any(stamp(i.get('publishedAt')) and dt.timedelta(0)<=now-stamp(i['publishedAt'])<=dt.timedelta(days=7) for i in old.get('items',[]))
        if row.get('_newsIdentityBlocked'):state='identity_review'
        elif articles and fresh and dt.timedelta(0)<=now-fresh<=dt.timedelta(hours=36):state='recent_articles'
        elif not old.get('googleAttemptAt'):state='google_not_attempted'
        elif old.get('googleError'):state='google_fetch_failed'
        elif old.get('googleResult',{}).get('acceptedArticles')==0:state='google_checked_no_eligible_article'
        else:state='refresh_due'
        last=stamp(old.get('fallbackAttemptAt'))
        entries.append({'symbol':symbol,'state':state,'yahooReason':old.get('fallbackError'),
                        'yahooNextRetryAt':(last+dt.timedelta(hours=yahoo_wait_hours(old))).isoformat() if last else None})
    return {'schema':1,'generatedAt':now.isoformat(),'summary':dict(Counter(r['state'] for r in entries)),'rows':entries,
            'limitations':['Coverage plan only, not a risk rating. Empty provider responses do not establish absence of events.']}

