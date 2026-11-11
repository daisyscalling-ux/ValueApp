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
from holding_liquidity import liquidity_for,exemption_for
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
  stocks[s]['liquidityExemption']=exemption_for(stocks[s],liquidity_archive or {},now) if not stocks[s]['liquidity'] else None
  stocks[s]['creditQuality']=credit_context(credit_archive or {},stocks[s],now)
 out.update(state='ready',summary={'verifiedHoldings':len(stocks),'rejected':dict(Counter(rejected.values()))})
 return out

ORDINARY=('stock','common','common_stock','equity')
DEPOSITARY=('dr','adr','gdr','depositary_receipt')
def depositary_candidate(row):
 """Depositary Receipt mit der ISIN der Stammaktie: Kandidat fuer die Konzernkennzahlen der geprueften Stammaktie."""
 return (row.get('security_type') in DEPOSITARY and valid_isin(row.get('isin')) and row.get('share_class') in (None,'','common','ordinary')
         and row.get('listing_reference_status') not in ('expired','input_mismatch'))
def adopt_depositaries(stocks,rejected,deferred,group):
 """Kapital-, Liquiditaets- und Kreditquoten gelten fuer den Konzern, nicht fuer die Aktie. Ein DR uebernimmt den Eintrag nur,
 wenn im selben Lauf eine Stammaktie desselben Konzerns geprueft wurde (group: LEI bzw. gepruefte Emittenten-ISIN inkl.
 weiterer Aktiengattungen wie A/H); sonst bleibt er offen."""
 for row,key in deferred:
  s=row['listing_symbol']
  base=sorted((k for k,v in stocks.items() if v.get(group)==key and (v.get('inputIdentity') or {}).get('security_type') in ORDINARY and not v.get('depositaryOf')),key=lambda k:(k.startswith('OTC:'),k))
  if not base:rejected[s]='depositary_without_verified_ordinary';continue
  stocks[s]={**stocks[base[0]],'inputIdentity':{k:row.get(k) for k in FIELDS},'depositaryOf':base[0],
   'limitations':[*stocks[base[0]].get('limitations',[]),'Depositary receipt: group ratios of the verified ordinary share '+base[0]+' of the same group.']}
EU_ITEMS={'cet1_ratio':'2520140','tier1_ratio':'2520141','total_capital_ratio':'2520142','leverage_ratio':'2520905'}
KM1_MAX_AGE_DAYS=270
def _km1_bank(km1,lei,now):
 """Gepruefte EU-KM1-Werte (EBA Pillar 3 Data Hub, import_eu_pillar3.py) fuer eine LEI, hoechstens 270 Tage alt."""
 if not isinstance(km1,dict) or km1.get('schema')!=1 or km1.get('method')!='eba-p3dh-km1-v1':return None
 b=(km1.get('banks') or {}).get(lei)
 try:age=(now.date()-dt.date.fromisoformat(str((b or {}).get('period')))).days
 except ValueError:return None
 if not b or not 0<=age<=KM1_MAX_AGE_DAYS or not re.fullmatch('[0-9a-f]{64}',str(b.get('sourceFileSha256',''))) or not str(b.get('sourceUrl','')).startswith('https://errp.eba.europa.eu/public-documents/'):return None
 return b
def km1_liquidity(km1,lei,now):
 b=_km1_bank(km1,lei,now)
 if not b or not isinstance(b.get('lcr'),(int,float)) or not 0<b['lcr']<10:return None
 return {'state':'available','method':'eba-p3dh-km1-lcr-v1','reportedRatio':b['lcr'],'nsfr':b.get('nsfr'),'period':b['period'],'unit':'fraction',
         'sourceUrl':b['sourceUrl'],'sourceFileSha256':b['sourceFileSha256'],'definition':'EU KM1 Zeile 17: LCR (Durchschnitt), Saeule-3-Offenlegung im EBA Pillar 3 Data Hub','scoreContribution':0}
def km1_requirement(km1,lei,now):
 """Vollstaendige CET1-Anforderung (4,5 % + P2R-CET1 + kombinierte Puffer) mit der CET1-Quote desselben Stichtags."""
 b=_km1_bank(km1,lei,now);q=(b or {}).get('cet1Requirement') or {}
 cet1=((b or {}).get('metrics') or {}).get('cet1_ratio')
 if not b or not isinstance(q.get('value'),(int,float)) or not 0<q['value']<.3 or not isinstance(cet1,(int,float)) or not 0<cet1<1:return None
 return {'state':'available','method':'eba-p3dh-km1-cet1-requirement-v1','unit':'fraction','value':q['value'],'cet1Ratio':cet1,'comparisonPeriod':b['period'],
         'headroomPercentagePoints':(cet1-q['value'])*100,'components':q.get('components'),'derivation':q.get('derivation'),'sourceUrl':b['sourceUrl'],
         'sourceFileSha256':b['sourceFileSha256'],'reviewExpires':km1.get('mappingReviewExpires'),
         'definition':'4,5 % CET1-Mindestquote + CET1-Anteil der SREP-Zusatzanforderung (EU KM1 EU 7e) + kombinierte Kapitalpufferanforderung (Zeile 11)','scoreContribution':0}
def km1_credit(km1,lei,now):
 """NPL-Quote aus EU CR1 (EBA Pillar 3 Data Hub, Modul FINDIS): notleidende / gesamte Kredite und Darlehen, brutto, hoechstens 270 Tage alt."""
 b=_km1_bank(km1,lei,now);n=(b or {}).get('npl') or {}
 try:age=(now.date()-dt.date.fromisoformat(str(n.get('period')))).days
 except ValueError:return None
 if not b or not isinstance(n.get('ratio'),(int,float)) or not 0<=n['ratio']<=1 or not 0<=age<=KM1_MAX_AGE_DAYS \
    or not re.fullmatch('[0-9a-f]{64}',str(n.get('sourceFileSha256',''))) or not str(n.get('sourceUrl','')).startswith('https://errp.eba.europa.eu/public-documents/FINDIS/'):return None
 return {'state':'available','method':'eba-p3dh-cr1-npl-v1','unit':'fraction','ratio':n['ratio'],'period':n['period'],'lei':lei,'nonPerforming':n.get('nonPerforming'),'performing':n.get('performing'),
         'sourceUrl':n['sourceUrl'],'sourceFileSha256':n['sourceFileSha256'],'definition':'EU CR1 Zeile 010: notleidende / (nicht notleidende + notleidende) Kredite und Darlehen, Bruttobuchwert','scoreContribution':0}
P3_CODES={'cet1_ratio':'P3DH:K_61.00/0050','tier1_ratio':'P3DH:K_61.00/0060','total_capital_ratio':'P3DH:K_61.00/0070','leverage_ratio':'P3DH:K_61.00/0220'}
def pillar3_only_record(row,lei,km1,mapping,now):
 """EU-Bank ohne EBA-Transparenzdaten: Kapitalquoten, Anforderung und LCR ausschliesslich aus EU KM1 (EBA Pillar 3 Data Hub)."""
 b=_km1_bank(km1,lei,now)
 if not b:return None
 v=b.get('metrics') or {}
 metrics={k:{'state':'available','value':v[k],'unit':'fraction','sourceField':code} for k,code in P3_CODES.items() if isinstance(v.get(k),(int,float)) and 0<=v[k]<=1}
 if 'cet1_ratio' not in metrics:return None
 return {'state':'available','scope':'eu_prudential_group','capitalSource':'eba_p3dh_km1','lei':lei,'holdingName':b.get('name'),'inputIdentity':{k:row.get(k) for k in FIELDS},
  'period':b['period'],'exercise':'EBA Pillar 3 Data Hub (EU KM1)','sourceImportedAt':km1.get('importedAt'),'sourceUrl':b['sourceUrl'],'sourceFileSha256':b['sourceFileSha256'],
  'identityReviewExpires':mapping.get('review_expires'),'publicationDate':None,'pointInTimeUsable':False,'metrics':metrics,'score':None,
  'capitalRequirement':km1_requirement(km1,lei,now),'liquidity':km1_liquidity(km1,lei,now),'creditQuality':km1_credit(km1,lei,now),
  'limitations':['Only Pillar 3 (no EBA transparency data): capital, requirement and LCR from EU KM1, non-performing loans from EU CR1.']}
def build_eu(universe,capital,mapping,now,km1=None):
 """EU/EWR-Banken: EBA-Kapital und -NPL je LEI, Teilanforderung aus EZB-P2R. Gleiche Identitaetsregeln wie bei US-Holdings."""
 stocks,rejected,deferred={},{},[]
 out={'schema':1,'source':'eba_transparency_ecb_p2r','method':capital.get('method'),'stocks':stocks,'rejected':rejected,'scoreContribution':0}
 if capital.get('method')!='eu-bank-capital-v1' or not isinstance(capital.get('banks'),dict):out['state']='source_unavailable';return out
 by_isin={i:b['lei'] for b in mapping.get('banks',[]) for i in b.get('isins',[])}
 p3only={b['lei'] for b in mapping.get('pillar3Only',[])}
 by_isin.update({i:b['lei'] for b in mapping.get('pillar3Only',[]) for i in b.get('isins',[])})
 eba=capital['sources']['eba'];ecb=capital['sources']['ecb']
 for row in universe.get('kandidaten',[]):
  s=row.get('listing_symbol');lei=by_isin.get(row.get('isin'))
  if not s or not lei:continue
  b=capital['banks'].get(lei)
  if not b and lei in p3only:
   rec=pillar3_only_record(row,lei,km1,mapping,now)
   if rec is None:rejected[s]='no_current_pillar3_km1_for_lei'
   elif depositary_candidate(row):deferred.append((row,lei))
   elif not valid_isin(row.get('isin')) or row.get('security_type') not in ('stock','common','common_stock','equity') or row.get('share_class') not in (None,'','common','ordinary') or row.get('listing_reference_status') in ('expired','input_mismatch'):rejected[s]='listing_identity_unverified'
   else:stocks[s]=rec
   continue
  if not b:rejected[s]='no_eu_capital_for_lei';continue
  if depositary_candidate(row):deferred.append((row,lei));continue
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
   'capitalRequirement':km1_requirement(km1,lei,now) or req,'liquidity':km1_liquidity(km1,lei,now),'creditQuality':km1_credit(km1,lei,now) or credit,
   'limitations':['EBA transparency data are published annually; the period can be up to 24 months old.','Without Pillar 3 KM1: partial CET1 requirement excludes countercyclical, systemic and O-SII/G-SII buffers, and no LCR.']}
 adopt_depositaries(stocks,rejected,deferred,'lei')
 out.update(state='ready',summary={'euBanks':len(stocks),'rejected':dict(Counter(rejected.values()))})
 return out

INTL_CREDIT_MAX_AGE_DAYS=270
def intl_credit_source(i,now):
 """CR1 mit eigenem Stichtag (Japan: nur Jahres-/Halbjahresbericht). None = gleicher Stichtag wie KM1, False = ungueltig, sonst Zusatzfelder."""
 p,src=i.get('creditPeriod'),i.get('creditSource')
 if p is None and src is None:return None
 if not isinstance(src,dict) or not isinstance(p,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',p) or p>str(i.get('period')):return False
 if not 0<=(now.date()-dt.date.fromisoformat(p)).days<=INTL_CREDIT_MAX_AGE_DAYS:return False
 if src.get('type')!='basel_pillar3_cr1' or not re.fullmatch(r'[0-9a-f]{64}',str(src.get('sha256',''))) or not str(src.get('url','')).startswith('https://') or not str(src.get('location','')).strip():return False
 return {'period':p,'periodBasis':'separate_cr1','sourceType':src['type'],'sourceUrl':src['url'],'sourceFileSha256':src['sha256'],'sourceDetail':src['location']}

def build_intl(universe,data,now):
 """Banken ausserhalb EU/EWR/USA (APRA, spaeter Basel-KM1): Kapitalquoten, LCR, NSFR je Konzern. Gleiche Identitaetsregeln."""
 stocks,rejected,deferred={},{},[]
 out={'schema':1,'source':'intl_basel_key_metrics','method':data.get('method'),'stocks':stocks,'rejected':rejected,'scoreContribution':0}
 if data.get('method')!='intl-bank-metrics-v1' or not isinstance(data.get('issuers'),dict):out['state']='source_unavailable';return out
 for row in universe.get('kandidaten',[]):
  s=row.get('listing_symbol');i=data['issuers'].get(row.get('isin'))
  if not s or not i:continue
  if depositary_candidate(row):deferred.append((row,i.get('shareClassOf') or row['isin']));continue
  if not valid_isin(row.get('isin')) or row.get('security_type') not in ('stock','common','common_stock','equity') or row.get('share_class') not in (None,'','common','ordinary') or row.get('listing_reference_status') in ('expired','input_mismatch'):
   rejected[s]='listing_identity_unverified';continue
  src=i['source'];metrics={k:{'state':'available','value':v,'unit':'fraction','sourceField':src['type']+':'+k} for k,v in i['metrics'].items() if isinstance(v,(int,float)) and 0<=v<=1}
  if 'cet1_ratio' not in metrics:rejected[s]='intl_cet1_missing';continue
  liq={'state':'available','method':'intl-lcr-v1','reportedRatio':i['lcr'],'nsfr':i.get('nsfr'),'period':i['period'],'unit':'fraction','sourceType':src['type']} if isinstance(i.get('lcr'),(int,float)) and 0<i['lcr']<10 else None
  req=None
  if isinstance(i.get('cet1Requirement'),(int,float)) and 0<i['cet1Requirement']<.3:
   req={'state':'available','method':'basel-km1-cet1-requirement-v1','unit':'fraction','value':i['cet1Requirement'],'comparisonPeriod':i['period'],'reviewExpires':data['mappingReviewExpires'],'definition':i.get('cet1RequirementDefinition'),
        'components':i.get('requirementComponents'),'componentSourceUrl':i.get('requirementSourceUrl'),'scoreContribution':0}
  credit=None
  if isinstance(i.get('defaultedLoanRatio'),(int,float)) and 0<=i['defaultedLoanRatio']<=1:
   credit={'state':'available','method':'basel-cr1-default-v1','unit':'fraction','ratio':i['defaultedLoanRatio'],'period':i['period'],
           'definition':'Defaulted / (defaulted + non-defaulted) gross carrying value of loans, Basel Pillar 3 table CR1.','scoreContribution':0}
   sep=intl_credit_source(i,now)
   if sep is False:credit=None
   elif sep:credit.update(sep)
  stocks[s]={'state':'available','scope':'basel_key_metrics','holdingName':i['issuer'],'issuerIsin':i.get('shareClassOf') or row['isin'],'jurisdiction':i['jurisdiction'],'regulator':i['regulator'],'consolidation':i['scope'],
   'inputIdentity':{k:row.get(k) for k in FIELDS},'period':i['period'],'sourceImportedAt':data['importedAt'],'sourceUrl':src['url'],'sourceFileSha256':src['sha256'],'sourceType':src['type'],
   'sourceDetail':src.get('tables') or src.get('location'),'identityReviewExpires':data['mappingReviewExpires'],'publicationDate':None,'pointInTimeUsable':False,'metrics':metrics,'score':None,
   'capitalRequirement':req,'liquidity':liq,'creditQuality':credit,
   'limitations':['Published key metrics of the supervised consolidated group; no institution-specific requirement unless disclosed.','No harmonised non-performing loan ratio in this source.']}
 adopt_depositaries(stocks,rejected,deferred,'issuerIsin')
 out.update(state='ready',summary={'intlBanks':len(stocks),'rejected':dict(Counter(rejected.values()))})
 return out

def main():
 folder=Path(os.getenv('RISK_DATA_DIR',str(Path(__file__).resolve().parents[1]/'daten')))
 result=build(load(folder/'cf_universum.json',{}),load(folder/'regulatory/bhcf-import.json',{}),load(Path(__file__).resolve().parents[1]/'regulatory_export/holding-stock-map.json',{}),credit_archive=load(folder/'regulatory/bhcf-credit-quality.json',{}),requirements_archive=load(folder/'cf_capital_requirements.json',{}),liquidity_archive=load(Path(__file__).resolve().parents[1]/'regulatory_export/reviewed-liquidity.json',{}))
 result['insurers']=build_insurers(load(folder/'cf_universum.json',{}),load(Path(__file__).with_name('reviewed-insurer-solvency.json'),{}))
 result['euBanks']=build_eu(load(folder/'cf_universum.json',{}),load(folder/'regulatory/eu-bank-capital.json',{}),load(Path(__file__).resolve().parents[1]/'regulatory_export/eu-bank-map.json',{}),dt.datetime.now(dt.timezone.utc),km1=load(folder/'regulatory/eu-pillar3-km1.json',{}))
 result['intlBanks']=build_intl(load(folder/'cf_universum.json',{}),load(folder/'regulatory/intl-bank-metrics.json',{}),dt.datetime.now(dt.timezone.utc))
 save(folder/'cf_regulatory_context.json',result);print(result.get('summary',{'state':result['state']}))
if __name__=='__main__':main()
