"""Bounded original-report retrieval and independent-period merging."""
import datetime as dt
import json
import re
import time
import urllib.request
import urllib.error
from sec_original_filings import parse,latest_annual


def verified_original(period,cik):
    o=period.get('originalFiling')
    if not isinstance(o,dict) or o.get('method')!='annual-inline-xbrl-v1':return False
    prefix=f'https://www.sec.gov/Archives/edgar/data/{int(cik)}/{period["accession"].replace("-","")}/'
    if not isinstance(o.get('sourceUrl'),str) or not o['sourceUrl'].startswith(prefix):return False
    if not re.fullmatch(r'[A-Za-z0-9_.-]+\.html?',o['sourceUrl'][len(prefix):]):return False
    filename=o['sourceUrl'][len(prefix):]
    mirror=f'https://cdn.yahoofinance.com/prod/sec-filings/{int(cik):010d}/{period["accession"].replace("-","")}/{filename}'
    if o.get('distributionUrl',o['sourceUrl']) not in (o['sourceUrl'],mirror):return False
    if not re.fullmatch('[a-f0-9]{64}',o.get('sha256','')):return False
    try:
        end=dt.date.fromisoformat(period['end']);report=dt.date.fromisoformat(o['reportDate']);filed=dt.date.fromisoformat(period['filed'])
    except (KeyError,ValueError,TypeError):return False
    return o.get('accession')==period['accession'] and o.get('filed')==period['filed'] and o.get('form') in ('10-K','10-K/A','20-F','20-F/A','40-F','40-F/A') and end<=report<=filed


def merge_periods(existing,additional):
    from sec_cashflow_history import currency_concordant
    grouped={};out=[];stats={'conflictingPeriods':0,'supersededObservations':0}
    for p in [*existing,*additional]:
        grouped.setdefault(tuple(p[k] for k in ('namespace','concept','metric','end')),[]).append(p)
    for rows in grouped.values():
        newest=max(p['filed'] for p in rows)
        latest=[p for p in rows if p['filed']==newest]
        stats['supersededObservations']+=len(rows)-len(latest)
        selected=[];conflict=False
        for c in sorted({p['currency'] for p in latest}):
            same=[p for p in latest if p['currency']==c]
            if len({tuple(p[k] for k in ('start','assets','operatingCashflow','cashPpe')) for p in same})!=1:
                conflict=True;break
            selected.append(max(same,key=lambda p:(p['accession'],bool(p.get('originalFiling')))))
        if conflict or (len(selected)>1 and not currency_concordant(selected)):
            stats['conflictingPeriods']+=1;continue
        out.extend(selected)
    return sorted(out,key=lambda p:(p['end'],p['namespace'],p['concept'],p['currency'])),stats


def loader(user_agent,last_request,now=None,transport=None):
    now=now or dt.datetime.now(dt.timezone.utc)
    def read(url,timeout,limit):
        time.sleep(max(0,.6-(time.monotonic()-last_request[0])))
        last_request[0]=time.monotonic()
        # Operator contact is for SEC only, not forwarded to the public distribution provider.
        agent=user_agent if url.startswith(('https://www.sec.gov/','https://data.sec.gov/')) else 'ValueApp public filing reader'
        request=urllib.request.Request(url,headers={'User-Agent':agent,'Accept':'application/json,application/xhtml+xml,text/html'})
        with urllib.request.urlopen(request,timeout=timeout) as response:raw=response.read(limit+1)
        if len(raw)>limit:raise ValueError('response_too_large')
        return raw
    get=transport or read
    def fetch(cik,budget):
        started=time.monotonic()
        raw=get(f'https://data.sec.gov/submissions/CIK{int(cik):010d}.json',min(12,budget),6_000_000)
        filing=latest_annual(json.loads(raw),cik,now)
        if filing is None:return None
        remaining=budget-(time.monotonic()-started)
        if remaining<1:raise TimeoutError('original_budget_exhausted')
        url=f'https://www.sec.gov/Archives/edgar/data/{int(cik)}/{filing["accessionNumber"].replace("-","")}/{filing["primaryDocument"]}'
        distribution=url
        try:raw=get(url,min(18,remaining),15_000_000)
        except urllib.error.HTTPError as error:
            # No retry of a denied/rate-limited SEC request. An independent public copy
            # is considered only for Archives 403/server errors, never SEC 429.
            if error.code!=403 and not 500<=error.code<=599:raise
            remaining=budget-(time.monotonic()-started)
            if remaining<1:raise
            distribution=f'https://cdn.yahoofinance.com/prod/sec-filings/{int(cik):010d}/{filing["accessionNumber"].replace("-","")}/{filing["primaryDocument"]}'
            raw=get(distribution,min(18,remaining),15_000_000)
        result=parse(raw,cik,filing,url)
        result['originalFiling']['distributionUrl']=distribution
        return result
    return fetch
