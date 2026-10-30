"""Bridge reviewed consolidated holding evidence into the risk audit, never a score."""
import datetime as dt,math,os,re,sys
from pathlib import Path
from collections import Counter
from yahoo_sector import load,save
from news_identity import valid_isin
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'regulatory_export'))
from holding_stocks import enrich
from regulatory_credit import credit_context
from fed_capital_requirements import requirement_for
FIELDS=('listing_symbol','ticker','isin','currency','name','name_full','security_type','share_class')
CODES={'BHCAP793':'cet1_ratio','BHCA7206':'tier1_ratio','BHCA7205':'total_capital_ratio','BHCA7204':'tier1_leverage_ratio'}
def build(universe,holdings,registry,now=None,credit_archive=None,requirements_archive=None):
 now=now or dt.datetime.now(dt.timezone.utc);stocks={};rejected={}
 out={'schema':1,'generatedAt':now.isoformat(),'source':'reviewed_FR_Y9C_holding_capital','stocks':stocks,'rejected':rejected,'scoreContribution':0}
 try:
  imported=dt.datetime.fromisoformat(holdings['imported_at'].replace('Z','+00:00'))
  if imported.tzinfo is None or imported>now or imported.date()<dt.date.fromisoformat(holdings['reporting_period']):raise ValueError('source_date_invalid')
  report=enrich({'stocks':[],'summary':{}},universe,holdings,registry,now.date())
 except (KeyError,TypeError,ValueError):out['state']='source_unavailable';return out
 originals={r.get('listing_symbol'):r for r in universe.get('kandidaten',[])}
 hashes={f.get('sha256') for f in holdings.get('files',[]) if isinstance(f.get('sha256'),str)}
 for r in report['stocks']:
  s=r['symbol'];row=originals.get(s)
  if row is None:rejected[s]='listing_identity_unverified';continue
  if r.get('state')!='verified_holding_capital':rejected[s]=r.get('holding_mapping_reason','unverified_holding');continue
  if not valid_isin(row.get('isin')) or row.get('security_type') not in ('stock','common','common_stock','equity') or row.get('share_class') not in (None,'','common','ordinary') or row.get('listing_reference_status') in ('expired','input_mismatch'):
   rejected[s]='listing_identity_unverified';continue
  evidence=r['identity_evidence'];digest=evidence.get('holding_evidence',{}).get('source_file_sha256')
  if not isinstance(digest,str) or not re.fullmatch('[0-9a-f]{64}',digest) or digest not in hashes:rejected[s]='holding_source_digest_mismatch';continue
  metrics={}
  for code,key in CODES.items():
   m=r['group_metrics'].get(key,{});definition=holdings.get('definitions',{}).get(code,{})
   try:raw=float(m['raw_value']);value=m['value']
   except (KeyError,ValueError,TypeError):continue
   if (not definition.get('valid_from','9999')<=r['reporting_period']<=definition.get('valid_to','0000') or definition.get('metric')!=key or definition.get('unit')!='fraction' or definition.get('source_unit')!='percent' or m.get('source_field')!=code or m.get('state')!='reported'
       or not isinstance(value,(int,float)) or isinstance(value,bool) or not math.isfinite(value) or not math.isfinite(raw) or not 0<=value<=1 or abs(value-raw/100)>1e-10):continue
   metrics[key]={'state':'available','value':value,'unit':'fraction','sourceField':code}
  values=[metrics[k]['value'] for k in ('cet1_ratio','tier1_ratio','total_capital_ratio') if k in metrics]
  if any(a is not None and b is not None and a>b+1e-6 for a,b in zip(values,values[1:])):rejected[s]='capital_hierarchy_inconsistent';continue
  if 'cet1_ratio' not in metrics:rejected[s]='verified_cet1_missing';continue
  stocks[s]={'state':'available','scope':'listed_consolidated_holding','rssdId':r['holding_rssd_id'],'holdingName':evidence['holding_name'],'inputIdentity':{k:row.get(k) for k in FIELDS},
   'period':r['reporting_period'],'sourceImportedAt':holdings['imported_at'],'sourceUrl':holdings.get('source_url'),'sourceFileSha256':digest,'listingSourceUrl':evidence['listing_source_url'],
   'identityReviewExpires':registry['review_expires'],'publicationDate':None,'pointInTimeUsable':False,'metrics':metrics,'score':None,
   'limitations':['Reported capital ratios; institution-specific requirement and buffer not verified.','No holding liquidity or asset-quality inference from subsidiary FDIC ratios.']}
  stocks[s]['capitalRequirement']=requirement_for(stocks[s],requirements_archive or {},now)
  stocks[s]['creditQuality']=credit_context(credit_archive or {},stocks[s],now)
 out.update(state='ready',summary={'verifiedHoldings':len(stocks),'rejected':dict(Counter(rejected.values()))})
 return out

def main():
 folder=Path(os.getenv('RISK_DATA_DIR',str(Path(__file__).resolve().parents[1]/'daten')))
 result=build(load(folder/'cf_universum.json',{}),load(folder/'regulatory/bhcf-import.json',{}),load(Path(__file__).resolve().parents[1]/'regulatory_export/holding-stock-map.json',{}),credit_archive=load(folder/'regulatory/bhcf-credit-quality.json',{}),requirements_archive=load(folder/'cf_capital_requirements.json',{}))
 save(folder/'cf_regulatory_context.json',result);print(result.get('summary',{'state':result['state']}))
if __name__=='__main__':main()
