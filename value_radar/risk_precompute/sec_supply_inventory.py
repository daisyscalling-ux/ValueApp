"""Current-universe SEC inventory, separate from per-run activity counters."""
from collections import Counter
from market_priority import market_tier
from news_identity import valid_isin
from roic_risk_annual import identity
from yahoo_sector import recent


def scope(row,domain,cik,duplicate=False):
    if duplicate:return 'duplicate_listing'
    if domain.get('domains',{}).get('identity',{}).get('state')!='available':return 'identity_unconfirmed'
    if not valid_isin(row.get('isin')) or row.get('listing_reference_status') in ('expired','input_mismatch'):return 'identity_unconfirmed'
    if domain.get('domains',{}).get('balance',{}).get('profile')!='corporate':return 'different_balance_profile'
    if not str(cik or '').isdigit():return 'sec_mapping_missing'
    if row.get('cik') and str(row['cik']).lstrip('0')!=str(cik).lstrip('0'):return 'cik_conflict'
    return None


def build(universe,coverage,cache,listing_map,now):
    from sec_cashflow_history import balances
    rows={};duplicates=set()
    for r in universe.get('kandidaten',[]):
        symbol=r.get('listing_symbol')
        if not symbol:continue
        if symbol in rows:duplicates.add(symbol)
        rows[symbol]=r
    domains={r['symbol']:r for r in coverage.get('stocks',[]) if r.get('symbol')}
    checked={**cache,**{k:{s:c for s,c in cache.get(k,{}).items() if str(c.get('cik','')).lstrip('0')==str(listing_map.get(s,'')).lstrip('0')} for k in ('stocks','operatingStocks')}}
    valid=balances(checked,universe,now);out=[];counts=Counter();main=Counter()
    fresh_coverage=recent(coverage.get('generatedAt'),now,2)
    for symbol,row in rows.items():
        cik=listing_map.get(symbol)
        reason=scope(row,domains.get(symbol,{}),cik,symbol in duplicates)
        att=cache.get('attempts',{}).get(symbol,{})
        att=att if att.get('inputIdentity')==identity(row) else {}
        metrics={}
        for balance in valid.get(symbol,{}).get('balances',[]):
            for metric,value in balance.get('metrics',{}).items():
                end=value.get('basis',{}).get('period')
                if value.get('state')=='available' and end:metrics[metric]=max(metrics.get(metric,end),end)
        archives=[cache.get(k,{}).get(symbol,{}) for k in ('stocks','operatingStocks')]
        matching=[a for a in archives if a.get('inputIdentity')==identity(row) and str(a.get('cik','')).lstrip('0')==str(cik).lstrip('0')]
        if not fresh_coverage:state='coverage_stale';reason='coverage_missing_or_stale'
        elif reason:state='outside_scope' if reason in ('different_balance_profile','sec_mapping_missing') else 'blocked'
        elif metrics:state='available'
        elif any(a.get('periods') and not recent(a.get('retrievedAt'),now,14) for a in matching):state='stale'
        elif att.get('error'):state='failed';reason=att['error']
        elif matching:state='no_valid_periods'
        elif att:state='no_accepted_history'
        else:state='not_attempted'
        if state!='available':metrics={}
        counts[state]+=1
        tier=market_tier(symbol)
        if tier==0:main[state]+=1
        out.append({'symbol':symbol,'marketTier':tier,'state':state,'reason':reason,
            'latestMetricPeriods':metrics,'lastAttemptAt':att.get('at'),
            'lastAttemptError':att.get('error'),'originalError':att.get('originalError')})
    archived=set().union(*(set(cache.get(k,{})) for k in ('stocks','operatingStocks','attempts')))-set(rows)
    return {'schema':1,'generatedAt':now.isoformat(),'coverageFresh':fresh_coverage,
        'definition':'Validated SEC supplemental history; not full capex, current annual completeness or total risk coverage.',
        'summary':{'currentListings':len(rows),'states':dict(counts),'mainMarketStates':dict(main),
            'archivedListingsOutsideUniverse':len(archived),'unresolvedListingRows':sum(not r.get('listing_symbol') for r in universe.get('kandidaten',[]))},
        'stocks':sorted(out,key=lambda r:(r['marketTier'],r['symbol']))}
