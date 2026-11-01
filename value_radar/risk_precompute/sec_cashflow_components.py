"""Total OCF from two signed, co-reported components; never continuing-only."""
import copy
import datetime as dt
import math
import re

TOTAL='NetCashProvidedByUsedInOperatingActivities'
CONT='NetCashProvidedByUsedInOperatingActivitiesContinuingOperations'
DISC='CashProvidedByUsedInOperatingActivitiesDiscontinuedOperations'
METHOD='signed-continuing-plus-discontinued-v1'


def compose(data, now):
    result=copy.deepcopy(data)
    facts=result.get('facts',{}).get('us-gaap',{})
    grouped={}
    for tag in (TOTAL,CONT,DISC):
        for currency, rows in facts.get(tag,{}).get('units',{}).items():
            if not re.fullmatch('[A-Z]{3}',currency):continue
            for f in rows:
                try:
                    start=dt.date.fromisoformat(f['start']);end=dt.date.fromisoformat(f['end']);filed=dt.date.fromisoformat(f['filed'])
                    if f.get('form') not in ('10-K','10-K/A','20-F','20-F/A','40-F','40-F/A'):continue
                    if not 330<=(end-start).days<=400 or not end<=filed<=now.date():continue
                    if not re.fullmatch(r'\d{10}-\d{2}-\d{6}',f['accn']):continue
                    if isinstance(f['val'],bool) or not isinstance(f['val'],(int,float)) or not math.isfinite(f['val']):continue
                    key=(currency,f['start'],f['end'],f['filed'],f['accn'],f['form'])
                    grouped.setdefault(key,{}).setdefault(tag,[]).append(f)
                except (ValueError,TypeError,KeyError):continue
    stats={'derived':0,'conflicts':0}
    for key, tags in grouped.items():
        if CONT not in tags or DISC not in tags:continue
        if any(len({f['val'] for f in rows})!=1 for rows in tags.values()):
            stats['conflicts']+=1
            continue
        continuing=tags[CONT][0]['val'];discontinued=tags[DISC][0]['val']
        total=continuing+discontinued
        if not math.isfinite(total):continue
        if TOTAL in tags:
            if not math.isclose(tags[TOTAL][0]['val'],total,rel_tol=1e-10,abs_tol=.01):stats['conflicts']+=1
            # Keep the reported total authoritative. Never replace or average it.
            continue
        row={**tags[CONT][0],'val':total,'ocfDerivation':{'method':METHOD,'continuing':continuing,'discontinued':discontinued,'concepts':[CONT,DISC]}}
        facts.setdefault(TOTAL,{}).setdefault('units',{}).setdefault(key[0],[]).append(row)
        stats['derived']+=1
    return result,stats


def verified(evidence, total):
    if not isinstance(evidence,dict) or evidence.get('method')!=METHOD or evidence.get('concepts')!=[CONT,DISC]:return False
    values=[evidence.get('continuing'),evidence.get('discontinued'),total]
    return all(isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) for v in values) and math.isclose(values[0]+values[1],total,rel_tol=1e-12,abs_tol=1e-8)
