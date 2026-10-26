"""Refresh policy and actionable coverage plan; never fills financial values."""
import datetime as dt
import hashlib
import json
from pathlib import Path
import os
from collections import Counter
from market_priority import market_tier
from news_identity import valid_isin
from yahoo_sector import load,save,recent
UTC=dt.timezone.utc
IDENTITY=('listing_symbol','ticker','isin','currency','security_type','share_class')

def fingerprint(row,balance):
 # New fiscal periods, changed identity and changed missing requirements retry
 # immediately. A mere audit timestamp must not bypass provider cooldowns.
 value={'identity':{k:row.get(k) for k in IDENTITY},'period':balance.get('period'),'currency':balance.get('currency'),'profile':balance.get('profile'),'reason':balance.get('reason')}
 return hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()

def parse_date(value):
 try:
  v=dt.datetime.fromisoformat(str(value).replace('Z','+00:00'))
  return v if v.tzinfo else None
 except (ValueError,TypeError):return None

def decision(row,balance,record,attempt,now):
 sig=fingerprint(row,balance);old_sig=attempt.get('coverageSignature')
 identity={k:row.get(k) for k in IDENTITY}
 if attempt.get('inputIdentity')!=identity:attempt={};old_sig=None
 if record.get('inputIdentity')!=identity:record={}
 if market_tier(row.get('listing_symbol',''))>1:return {'due':False,'reason':'deferred_other_market','coverageSignature':sig,'nextAttemptAt':None}
 if not valid_isin(row.get('isin')) or row.get('listing_reference_status') in ('expired','input_mismatch'):return {'due':False,'reason':'identity_blocked','coverageSignature':sig,'nextAttemptAt':None}
 at=parse_date(attempt.get('at'));changed=old_sig is not None and old_sig!=sig
 used=balance.get('source')=='ROIC v3 annual statements'
 preventive=balance.get('refreshDue') is True and balance.get('state') in ('available','context_only') and not used
 need=balance.get('state') in ('partial','missing') or not balance
 if not need and not used and not preventive:return {'due':False,'reason':'covered_by_other_source','coverageSignature':sig,'nextAttemptAt':None}
 if need and record.get('annual') and not any(v is not None for v in record['annual'].get('fields',{}).values()) and attempt.get('normalizationVersion')!='nonempty-annual-v1':
  return {'due':True,'reason':'repair_empty_legacy_archive','coverageSignature':sig,'nextAttemptAt':now.isoformat()}
 if preventive:
  next_at=at+dt.timedelta(days=1) if at and at<=now else now
  return {'due':now>=next_at,'reason':'preventive_fallback_refresh','coverageSignature':sig,'nextAttemptAt':next_at.isoformat()}
 if changed:return {'due':True,'reason':'requirements_changed','coverageSignature':sig,'nextAttemptAt':now.isoformat()}
 error=attempt.get('error');count=attempt.get('consecutiveFailures',1)
 count=min(7,max(1,count)) if isinstance(count,int) else 1
 # Long-lived gaps are checked weekly. Timeouts get bounded exponential retry.
 days= min(7,2**(count-1)) if error and error not in ('eligible_balance_missing','http_404','http_402','empty_statement_values') else 7
 if not error and used:days=4
 if old_sig is None:days=1  # compatible transition from the existing collector
 ref=at or parse_date(record.get('retrievedAt'))
 next_at=ref+dt.timedelta(days=days) if ref and ref<=now else now
 # Never let backoff push a USED record past the seven-day validity limit.
 if used:
  retrieved=parse_date(record.get('retrievedAt'))
  if not retrieved or not recent(record.get('retrievedAt'),now,6):next_at=now
  else:next_at=min(next_at,retrieved+dt.timedelta(days=6))
 return {'due':now>=next_at,'reason':'refresh_used_source' if used else 'retry_provider_error' if error else 'retry_missing_fields' if attempt else 'new_listing_or_gap','coverageSignature':sig,'nextAttemptAt':next_at.isoformat()}

def make_plan(universe,coverage,roic,edinet,now=None):
 now=now or dt.datetime.now(UTC);balances={x['symbol']:x.get('domains',{}).get('balance',{}) for x in coverage.get('stocks',[])}
 counts=Counter();items=[];seen={};conflicts=set();unresolved_rows=0
 for row in universe.get('kandidaten',[]):
  s=row.get('listing_symbol')
  if not s:unresolved_rows+=1;continue
  if s in seen and any(seen[s].get(k)!=row.get(k) for k in IDENTITY):conflicts.add(s)
  seen[s]=row
 for s,row in sorted(seen.items()):
  b=balances.get(s,{});record=roic.get('stocks',{}).get(s,{});attempt=roic.get('attempts',{}).get(s,{})
  d=decision(row,b,record,attempt,now)
  if not recent(coverage.get('generatedAt'),now,2):d.update(due=False,reason='coverage_missing_or_stale',nextAttemptAt=None)
  if s in conflicts:d.update(due=False,reason='conflicting_listing_identity',nextAttemptAt=None)
  annual=record.get('annual',{});fields=annual.get('fields',{})
  requirements=['total_assets','equity','net_income'] if b.get('profile') in ('bank','insurer','specialist_financial') else ['total_assets','total_debt','cash','operating_cashflow','capex']
  missing=[k for k in requirements if fields.get(k) is None]
  period_mismatch=bool(b.get('period') and annual.get('end') and b['period']!=annual['end'])
  e=edinet.get('stocks',{}).get(s,{});ea=edinet.get('attempts',{}).get(s,{})
  unresolved=b.get('state') in ('partial','missing') or not b
  if unresolved or d['due']:
   items.append({'symbol':s,'marketTier':market_tier(s),'balanceState':b.get('state','missing'),'expectedPeriod':b.get('period'),
    'coverageReason':b.get('reason'),'selectedSource':b.get('source'),'sourceSelection':b.get('sourceSelection'),'availableMetrics':[k for k,v in b.get('metrics',{}).items() if v.get('state')=='available'],'sourceExpiresAt':b.get('expiresAt'),'preventiveRefresh':b.get('refreshDue',False),'roic':{**d,'observedPeriod':annual.get('end'),'retrievedAt':record.get('retrievedAt'),'missingFields':missing,'periodMismatch':period_mismatch,'lastError':attempt.get('error')},
    'edinet':{'applicable':s.startswith(('TSE:','TYO:','JPX:')),'period':e.get('annual',{}).get('end'),'state':e.get('annual',{}).get('state'),'lastError':ea.get('error'),'missingFields':e.get('annual',{}).get('missing_fields',[]),'parserVersion':e.get('annual',{}).get('parserVersion'),'revisionChain':e.get('filing',{}).get('revisionChain',[]),'reconciliation':b.get('edinetReconciliation'),'debtScope':e.get('annual',{}).get('debtScope')},
    'automaticNextSource':'ROIC' if d['due'] else None,
    'nextSource':'reconcile_sources' if b.get('edinetReconciliation',{}).get('state')=='not_aligned' else 'original_debt_scope_review' if b.get('sourceSelection')=='edinet_standalone_original_filing' and 'missing_total_debt' in str(b.get('reason')) else 'EDINET' if s.startswith(('TSE:','TYO:','JPX:')) and unresolved else 'ROIC' if d['due'] else 'original_filing_review' if unresolved and market_tier(s)<=1 else 'scheduled_refresh'})
   counts[d['reason']]+=1
 items.sort(key=lambda x:(not x['roic']['due'],x['marketTier'],x['roic'].get('nextAttemptAt') or '',x['symbol']))
 return {'schema':1,'generatedAt':now.isoformat(),'coverageAsOf':coverage.get('generatedAt'),'coverageFresh':recent(coverage.get('generatedAt'),now,2),'summary':{'trackedListings':len(seen),'unresolvedListingRows':unresolved_rows,'dueRoic':sum(x['roic']['due'] for x in items),'openMainMarketBalances':sum(x['marketTier']<=1 and x['balanceState'] in ('partial','missing') for x in items),'reasons':dict(counts)},'stocks':items}

def main():
 folder=Path(os.getenv('RISK_DATA_DIR',str(Path(__file__).resolve().parents[1]/'daten')))
 result=make_plan(load(folder/'cf_universum.json',{}),load(folder/'cf_risk_coverage.json',{}),load(folder/'cf_roic_risk_annual.json',{}),load(folder/'cf_edinet_cashflow.json',{}))
 save(folder/'cf_financial_supply_plan.json',result);print(json.dumps(result['summary']))
 if os.getenv('GITHUB_STEP_SUMMARY'):
  with open(os.environ['GITHUB_STEP_SUMMARY'],'a',encoding='utf8') as f:
   f.write('\n## Finanzdaten-Nachversorgung\n\n'+str(result['summary']['openMainMarketBalances'])+' offene Bilanzbeobachtungen in den Hauptmaerkten. '+str(result['summary']['dueRoic'])+' ROIC-Abrufe faellig.\n\n')
   f.write('| Ursache / naechste Pruefung | Anzahl |\n|---|---:|\n')
   for k,v in result['summary']['reasons'].items():f.write('| '+k+' | '+str(v)+' |\n')
if __name__=='__main__':main()
