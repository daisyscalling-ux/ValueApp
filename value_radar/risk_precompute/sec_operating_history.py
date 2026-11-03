"""Independent annual operating cashflow / ending assets; no capex assumptions."""
import datetime as dt
import math
from sec_source_evidence import observation
from sec_cashflow_components import compose,verified as verified_ocf
from sec_original_supply import verified_original

TAGS={'us-gaap':'NetCashProvidedByUsedInOperatingActivities','ifrs-full':'CashFlowsFromUsedInOperatingActivities'}


def select(rows):
    grouped={};result=[]
    for r in rows:grouped.setdefault((r['namespace'],r['end']),[]).append(r)
    for key,versions in grouped.items():
        newest=max(r['filed'] for r in versions)
        latest=[r for r in versions if r['filed']==newest]
        chosen=[]
        for currency in sorted({r['currency'] for r in latest}):
            same=[r for r in latest if r['currency']==currency]
            if len({(r['assets'],r['operatingCashflow'],r['start']) for r in same})!=1:
                chosen=[];break
            chosen.append(max(same,key=lambda r:(r['accession'],bool(r.get('originalFiling')))))
        if len(chosen)>1:
            if len({(r['start'],r['filed'],r['accession']) for r in chosen})!=1:continue
            values=[r['value'] for r in chosen]
            if not math.isclose(min(values),max(values),rel_tol=1e-4,abs_tol=1e-6):continue
        result.extend(chosen)
    return sorted(result,key=lambda r:(r['end'],r['namespace'],r['currency']))


def normalize(data,cik,now):
    if str(data.get('cik','')).lstrip('0')!=str(cik).lstrip('0'):raise ValueError('cik_mismatch')
    data,_=compose(data,now);rows=[]
    for ns,ocf_tag in TAGS.items():
        facts=data.get('facts',{}).get(ns,{})
        groups={}
        for field,tag in [('assets','Assets'),('operatingCashflow',ocf_tag)]:
            for currency,items in facts.get(tag,{}).get('units',{}).items():
                for fact in items:
                    r=observation(fact,currency,now)
                    if r is None:continue
                    if field=='assets' and (r['start'] or r['value']<=0):continue
                    if field=='operatingCashflow' and (r['durationDays'] is None or not 330<=r['durationDays']<=400):continue
                    key=(r['end'],r['filed'],r['accession'],currency,r['form'])
                    groups.setdefault(key,{}).setdefault(field,[]).append((r,fact.get('ocfDerivation')))
        for (end,filed,acc,currency,form),g in groups.items():
            if set(g)!={'assets','operatingCashflow'}:continue
            if any(len({(r['value'],r['start']) for r,_ in entries})!=1 for entries in g.values()):continue
            asset=g['assets'][0][0];ocf,derivation=g['operatingCashflow'][0]
            value=ocf['value']/asset['value']
            if not math.isfinite(value):continue
            r=dict(end=end,filed=filed,accession=acc,currency=currency,form=form,start=ocf['start'],assets=asset['value'],operatingCashflow=ocf['value'],value=value,namespace=ns,concept=ocf_tag,metric='operatingCashflowAssets')
            r['sourceUrl']=f'https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc.replace("-", "")}/'
            if derivation:r['ocfDerivation']=derivation
            if data.get('originalFiling'):r['originalFiling']=data['originalFiling']
            rows.append(r)
    return select(rows)


def balances(cache,universe,now):
    from roic_risk_annual import identity
    from yahoo_sector import recent
    from sec_cashflow_history import METHOD
    if cache.get('schema')!=1 or cache.get('method')!=METHOD:return {}
    rows={};duplicates=set();out={}
    for row in universe.get('kandidaten',[]):
        s=row.get('listing_symbol')
        if s in rows:duplicates.add(s)
        rows[s]=row
    for s,c in cache.get('operatingStocks',{}).items():
        if s in duplicates or c.get('inputIdentity')!=identity(rows.get(s,{})) or not recent(c.get('retrievedAt'),now,14):continue
        entries=[]
        for p in c.get('periods',[]):
            try:
                ns=p['namespace'];tag=TAGS.get(ns)
                if not tag or p['concept']!=tag or p['metric']!='operatingCashflowAssets':continue
                data={'cik':c['cik'],'facts':{ns:{}}}
                for field,concept in [('assets','Assets'),('operatingCashflow',tag)]:
                    fact={'end':p['end'],'filed':p['filed'],'accn':p['accession'],'form':p['form'],'val':p[field]}
                    if field!='assets':fact['start']=p['start']
                    data['facts'][ns][concept]={'units':{p['currency']:[fact]}}
                checked=normalize(data,c['cik'],now)
                if not checked or isinstance(p['value'],bool) or not math.isfinite(p['value']) or abs(checked[0]['value']-p['value'])>1e-12 or checked[0]['sourceUrl']!=p['sourceUrl']:continue
                if p.get('ocfDerivation') and not verified_ocf(p['ocfDerivation'],p['operatingCashflow']):continue
                if p.get('originalFiling') and not verified_original(p,c['cik']):continue
                label=('SEC original annual filing' if p.get('originalFiling') else 'SEC companyfacts')+' / '+ns+' / operating cashflow before investments'
                if p.get('ocfDerivation'):label+=' / OCF continuing + discontinued'
                basis={'period':p['end'],'currency':p['currency'],'retrievedAt':c['retrievedAt'],'fields':{k:{'source':label,'end':p['end'],'currency':p['currency'],'retrievedAt':c['retrievedAt']} for k in ('assets','operatingCashflow')}}
                entries.append({'profile':'corporate','sourceUrl':p.get('originalFiling',{}).get('sourceUrl',p['sourceUrl']),'metrics':{'operatingCashflowAssets':{'state':'available','value':p['value'],'basis':basis}}})
            except (KeyError,TypeError,ValueError,OverflowError):continue
        if entries:out[s]={'inputIdentity':c['inputIdentity'],'balances':entries}
    return out
