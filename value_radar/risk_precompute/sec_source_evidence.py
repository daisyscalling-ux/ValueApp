"""Bounded SEC field evidence. Observations here are NOT valuation inputs."""
import datetime as dt
import math
import re

VERSION = 'sec-field-evidence-v1'
ANNUAL = {'10-K', '10-K/A', '20-F', '20-F/A', '40-F', '40-F/A'}


def observation(fact, currency, now):
    try:
        end = dt.date.fromisoformat(fact['end'])
        filed = dt.date.fromisoformat(fact['filed'])
        if fact.get('form') not in ANNUAL or not re.fullmatch('[A-Z]{3}', currency):
            return None
        if not 0 <= (now.date() - end).days <= 8 * 366 or not end <= filed <= now.date():
            return None
        if not re.fullmatch(r'\d{10}-\d{2}-\d{6}', fact['accn']):return None
        value = fact['val']
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):return None
        start = fact.get('start')
        duration = (end - dt.date.fromisoformat(start)).days if start else None
        return {'end': str(end), 'start': start, 'filed': str(filed),
                'accession': fact['accn'], 'form': fact['form'], 'currency': currency,
                'value': value, 'durationDays': duration}
    except (KeyError, TypeError, ValueError):
        return None


def build(data, cik, now, variants, accepted):
    if str(data.get('cik', '')).lstrip('0') != str(cik).lstrip('0'):
        raise ValueError('cik_mismatch')
    facts = data.get('facts', {})
    output = []
    for namespace, tags, metric in variants:
        fields = {}
        groups = {}
        for field, tag in tags.items():
            rows = []
            for currency, observations in facts.get(namespace, {}).get(tag, {}).get('units', {}).items():
                for fact in observations:
                    row = observation(fact, currency, now)
                    if row is None:continue
                    rows.append(row)
                    # Inventory presence is not acceptance: duration and signs are explicit.
                    key = (row['end'], row['filed'], row['accession'], currency)
                    groups.setdefault(key, {}).setdefault(field, set()).add((row['start'], row['value']))
            unique = {tuple(r.items()): r for r in rows}
            rows = sorted(unique.values(), key=lambda r:(r['end'],r['filed'],r['accession'],r['currency'],str(r['start']),r['value']), reverse=True)
            fields[field] = {'concept': tag, 'latestAnnualEnd': rows[0]['end'] if rows else None,
                             'observations': rows[:8], 'observationCount': len(rows), 'truncated':len(rows)>8}
        incomplete = []
        for (end, filed, acc, currency), present in sorted(groups.items(), reverse=True):
            missing = sorted(set(tags) - set(present))
            if not missing:continue
            incomplete.append({'end':end,'filed':filed,'accession':acc,'currency':currency,
                               'presentFields':sorted(present),'missingFields':missing,
                               'sourceUrl':f'https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc.replace("-", "")}/'})
        retained = [p['end'] for p in accepted if p.get('namespace')==namespace and p.get('concept')==tags['ppe'] and p.get('metric')==metric]
        output.append({'namespace':namespace,'metric':metric,'fields':fields,
                       'latestAcceptedEnd':max(retained,default=None),
                       'incompleteGroups':incomplete[:12], 'incompleteGroupCount':len(incomplete),
                       'incompleteGroupsTruncated':len(incomplete)>12})
    alternatives = []
    for namespace in ('us-gaap','ifrs-full'):
        for tag, info in sorted(facts.get(namespace,{}).items()):
            if not re.search(r'(Cash.*Operating|Operating.*Cash|PaymentsToAcquire|Purchase.*(Property|Plant|Equipment|Intangible)|Acquisition.*(Property|Equipment))',tag):continue
            rows = [r for c, entries in info.get('units',{}).items() for f in entries if (r:=observation(f,c,now)) is not None]
            if not rows:continue
            newest = max(r['end'] for r in rows)
            alternatives.append({'namespace':namespace,'concept':tag,'latestAnnualEnd':newest,
                                 'currencies':sorted({r['currency'] for r in rows}),
                                 'latestObservations':sorted(rows,key=lambda r:(r['end'],r['filed'],r['accession'],r['currency']),reverse=True)[:2]})
    alternatives.sort(key=lambda r:(r['latestAnnualEnd'],r['namespace'],r['concept']),reverse=True)
    return {'version':VERSION,'cik':str(cik),'generatedAt':now.isoformat(),
            'diagnosticOnly':True,'variants':output,'alternativeConcepts':alternatives[:48],
            'alternativeConceptCount':len(alternatives),'alternativesTruncated':len(alternatives)>48}
