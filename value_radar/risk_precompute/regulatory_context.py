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
from holding_liquidity import liquidity_for
from regulatory_insurer import build_insurers
FIELDS=('listing_symbol','ticker','isin','currency','name','name_full','security_type','share_class')
CODES={'BHCAP793':'cet1_ratio','BHCA7206':'tier1_ratio','BHCA7205':'total_capital_ratio','BHCA7204':'tier1_leverage_ratio'}
def build(universe,holdings,registry,now=None,credit_archive=None,requirements_archive=None,liquidity_archive=None):
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
  stocks[s]['liquidity']=liquidity_for(stocks[s],liquidity_archive or {},now)
  stocks[s]['creditQuality']=credit_context(credit_archive or {},stocks[s],now)
 out.update(state='ready',summary={'verifiedHoldings':len(stocks),'rejected':dict(Counter(rejected.values()))})
 return out

EU_ITEMS={'cet1_ratio':'2520140','tier1_ratio':'2520141','total_capital_ratio':'2520142','leverage_ratio':'2520905'}
def build_eu(universe,capital,mapping,now):
 """EU/EWR-Banken: EBA-Kapital und -NPL je LEI, Teilanforderung aus EZB-P2R. Gleiche Identitaetsregeln wie bei US-Holdings."""
 stocks,rejected={},{}
 out={'schema':1,'source':'eba_transparency_ecb_p2r','method':capital.get('method'),'stocks':stocks,'rejected':rejected,'scoreContribution':0}
 if capital.get('method')!='eu-bank-capital-v1' or not isinstance(capital.get('banks'),dict):out['state']='source_unavailable';return out
 by_isin={i:b['lei'] for b in mapping.get('banks',[]) for i in b.get('isins',[])}
 eba=capital['sources']['eba'];ecb=capital['sources']['ecb']
 for row in universe.get('kandidaten',[]):
  s=row.get('listing_symbol');lei=by_isin.get(row.get('isin'))
  if not s or not lei:continue
  b=capital['banks'].get(lei)
  if not b:rejected[s]='no_eu_capital_for_lei';continue
  if not valid_isin(row.get('isin')) or row.get('security_type') not in ('stock','common','common_stock','equity') or row.get('share_class') not in (None,'','common','ordinary') or row.get('listing_reference_status') in ('expired','input_mismatch'):
   rejected[s]='listing_identity_unverified';continue
  metrics={k:{'state':'available','value':b['metrics'][k],'unit':'fraction','sourceField':'EBA:'+code} for k,code in EU_ITEMS.items() if isinstance(b['metrics'].get(k),(int,float)) and 0<=b['metrics'][k]<=1}
  if 'cet1_ratio' not in metrics:rejected[s]='eu_cet1_missing';continue
  req=None
  if isinstance(b.get('cet1RequirementPartial'),(int,float)):
   req={'state':'available','method':'ecb-p2r-partial-cet1-v1','unit':'fraction','value':b['cet1RequirementPartial'],'p2r':b['p2r']['value'],'p2rYear':b['p2r']['year'],
        'p2rFootnote':b['p2r'].get('footnote') or None,'ecbName':b['p2r']['ecbName'],'sourceUrl':ecb['url'],'sourceSha256':ecb['sha256'],'comparisonPeriod':b['period'],
        'headroomPercentagePoints':(b['metrics']['cet1_ratio']-b['cet1RequirementPartial'])*100,'reviewExpires':capital['mappingReviewExpires'],
        'definition':capital['requirementDefinition'],'excludes':['countercyclical_buffer','systemic_risk_buffer','O-SII_or_G-SII_buffer','CET1_share_above_legal_minimum'],'scoreContribution':0}
  credit=None
  if isinstance(b.get('nplRatio'),(int,float)) and 0<=b['nplRatio']<=1:
   credit={'state':'available','method':'eba-npl-v1','unit':'fraction','ratio':b['nplRatio'],'period':b['period'],'lei':lei,'item':b['loans']['item'],
           'sourceUrl':eba['tr_cre.csv']['url'],'sourceFileSha256':eba['tr_cre.csv']['sha256'],'definition':capital['nplDefinition'],'scoreContribution':0}
  stocks[s]={'state':'available','scope':'eu_prudential_group','lei':lei,'holdingName':b['ebaName'],'country':b['country'],'inputIdentity':{k:row.get(k) for k in FIELDS},
   'period':b['period'],'exercise':capital.get('exercise'),'sourceImportedAt':capital['importedAt'],'sourceUrl':eba['tr_oth.csv']['url'],'sourceFileSha256':eba['tr_oth.csv']['sha256'],
   'identityReviewExpires':capital['mappingReviewExpires'],'publicationDate':None,'pointInTimeUsable':False,'metrics':metrics,'score':None,
   'capitalRequirement':req,'liquidity':None,'creditQuality':credit,
   'limitations':['EBA transparency data are published annually; the period can be up to 24 months old.','Partial CET1 requirement excludes countercyclical, systemic and O-SII/G-SII buffers.','No LCR in this source.']}
 out.update(state='ready',summary={'euBanks':len(stocks),'rejected':dict(Counter(rejected.values()))})
 return out

def main():
 folder=Path(os.getenv('RISK_DATA_DIR',str(Path(__file__).resolve().parents[1]/'daten')))
 result=build(load(folder/'cf_universum.json',{}),load(folder/'regulatory/bhcf-import.json',{}),load(Path(__file__).resolve().parents[1]/'regulatory_export/holding-stock-map.json',{}),credit_archive=load(folder/'regulatory/bhcf-credit-quality.json',{}),requirements_archive=load(folder/'cf_capital_requirements.json',{}),liquidity_archive=load(Path(__file__).resolve().parents[1]/'regulatory_export/reviewed-liquidity.json',{}))
 result['insurers']=build_insurers(load(folder/'cf_universum.json',{}),load(Path(__file__).with_name('reviewed-insurer-solvency.json'),{}))
 result['euBanks']=build_eu(load(folder/'cf_universum.json',{}),load(folder/'regulatory/eu-bank-capital.json',{}),load(Path(__file__).resolve().parents[1]/'regulatory_export/eu-bank-map.json',{}),dt.datetime.now(dt.timezone.utc))
 save(folder/'cf_regulatory_context.json',result);print(result.get('summary',{'state':result['state']}))
if __name__=='__main__':main()
