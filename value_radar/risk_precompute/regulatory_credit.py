"""Credit observations, not a harmonized NPL rating or liquidity proxy."""
import datetime as dt,math
CODES={'nonaccrual':'BHCK1403','past_due_30_89':'BHCK1406','past_due_90':'BHCK1407','held_for_investment':'BHCKB528','held_for_sale':'BHCK5369'}

def credit_context(archive,capital,now):
 missing={'state':'missing','reason':'verified_same_period_credit_fields_unavailable'}
 try:
  if archive.get('schema')!=1 or archive.get('source')!='FFIEC_BHCF_loan_quality' or archive.get('scope')!='FR_Y9C_consolidated_reporting_entity':return missing
  imported=dt.datetime.fromisoformat(archive['imported_at'].replace('Z','+00:00'))
  if imported.tzinfo is None or imported>now or imported.date()<dt.date.fromisoformat(capital['period']):return missing
  if archive['reporting_period']!=capital['period'] or archive['source_file_sha256']!=capital['sourceFileSha256']:return missing
  entity=archive['entities'][capital['rssdId']]
  from holding_stocks import key
  if key(entity['name'])!=key(capital['holdingName']):return missing
  fields={}
  for name,code in CODES.items():
   d=archive['definitions'][code];m=entity['fields'][code];value=m.get('value')
   if d['metric']!=name or d['unit']!='USD_thousands' or not d['valid_from']<=capital['period']<=d['valid_to']:return missing
   if m['state']!='reported' or not isinstance(value,int) or isinstance(value,bool) or not 0<=value<=9_007_199_254_740 or str(value)!=m['raw_value']:return missing
   fields[name]=value
  total=fields['held_for_investment']+fields['held_for_sale']
  if total<=0 or sum(fields[k] for k in ('nonaccrual','past_due_30_89','past_due_90'))>total:return {**missing,'reason':'credit_totals_inconsistent'}
  ratios={k:fields[k]/total for k in ('nonaccrual','past_due_30_89','past_due_90')}
  ratios['nonaccrual_or_90_past_due']=(fields['nonaccrual']+fields['past_due_90'])/total
  return {'state':'available','method':'bhcf-loan-quality-v1','period':capital['period'],'rssdId':capital['rssdId'],'sourceFileSha256':archive['source_file_sha256'],'sourceImportedAt':archive['imported_at'],'unit':'fraction','amountUnit':'USD_thousands','components':fields,'totalLoans':total,'ratios':ratios,'sourceFields':CODES,'sourceUrl':archive['source_url'],'score':None,'pointInTimeUsable':False,'limitations':['Single-quarter loan-quality context, not expected losses or an IFRS NPL comparison.','Government guarantees, credit mix and trend need separate assessment.','No LCR or institution-specific capital requirement inferred.']}
 except (KeyError,TypeError,ValueError,OverflowError):return missing
