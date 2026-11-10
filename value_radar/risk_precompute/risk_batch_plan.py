"""Separate acquisition gaps from structural limits, with independently usable metrics."""
from collections import Counter
import math
from market_priority import market_tier

METRICS=('netDebtAssets','fcfAssets','operatingCashflowAssets','cashAssets','bookEquityAssets','netIncomeEndingAssets')
def metric_available(balance,key):
 metric=(balance.get('metrics') or {}).get(key) or (balance.get('supplementalMetrics') or {}).get(key) or {}
 value=metric.get('value')
 return metric.get('state')=='available' and isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)

def metric_coverage(rows):
 out={}
 for key in METRICS:
  applicable=[r for r in rows if r.get('domains',{}).get('balance',{}).get('profile') in (('corporate',) if key in ('netDebtAssets','fcfAssets','operatingCashflowAssets','cashAssets') else ('corporate','bank','insurer','specialist_financial'))]
  available=[r for r in applicable if r.get('domains',{}).get('identity',{}).get('state')=='available' and metric_available(r['domains']['balance'],key)]
  out[key]={'available':len(available),'applicableListings':len(applicable),'percent':round(100*len(available)/len(applicable),1) if applicable else None}
 return out

def plan(rows,batches):
 indexed={r['symbol']:r for r in rows};groups={}
 for batch in batches:
  for symbol in batch['symbols']:
   row=indexed[symbol];domains=row.get('domains',{});reason=batch['reason'];kind=batch['kind']
   category='source_or_mapping_review';automatic=False
   if kind=='sector':
    context=any(domains.get('sector',{}).get(k,{}).get('state')=='available' for k in ('industryContext','broaderContext','currencyAdjustedContext'))
    category='strict_peer_extension_context_already_present' if context else 'sector_context_gap'
   elif kind=='historical' and ('Weniger als zwei Handelsjahre' in reason or 'Weniger als ein Handelsjahr' in reason):category='insufficient_listing_history'
   elif kind=='sector_framework':category='sector_original_disclosure_batch'
   elif kind=='source_reconciliation':category='definition_or_period_reconciliation'
   elif kind=='financial_fields':category='financial_statement_field_batch'
   elif kind in ('price','historical','quote'):category='provider_refresh_or_listing_review';automatic=True
   key=(batch['marketTier'],category,kind,reason)
   g=groups.setdefault(key,{'marketTier':batch['marketTier'],'category':category,'kind':kind,'reason':reason,'automaticRefreshCandidate':automatic,'symbols':set()})
   g['symbols'].add(symbol)
 priorities={'financial_statement_field_batch':0,'provider_refresh_or_listing_review':1,'sector_context_gap':2,'sector_original_disclosure_batch':3,'definition_or_period_reconciliation':4,'source_or_mapping_review':5,'strict_peer_extension_context_already_present':6,'insufficient_listing_history':7}
 output=[{**g,'symbols':sorted(g['symbols']),'listings':len(g['symbols'])} for g in groups.values()]
 output.sort(key=lambda g:(g['marketTier'],priorities[g['category']],-g['listings'],g['reason']))
 categories={}
 for category in sorted({g['category'] for g in output}):
  symbols={s for g in output if g['category']==category for s in g['symbols']}
  categories[category]={'mainMarketListings':sum(market_tier(s)<=1 for s in symbols),'deferredListings':sum(market_tier(s)>1 for s in symbols),'uniqueListings':len(symbols)}
 return {'schema':1,'categories':categories,'batches':output,
  'metricCoverage':{'all':metric_coverage(rows),'mainMarkets':metric_coverage([r for r in rows if market_tier(r['symbol'])<=1])},
  'interpretation':'Distinct listings per category, categories overlap. Structural peer/history limitations remain open but are not missing provider fields. No automatic safety verdict or score reweighting. Refresh candidates still obey the existing identity, freshness and backoff checks.'}
