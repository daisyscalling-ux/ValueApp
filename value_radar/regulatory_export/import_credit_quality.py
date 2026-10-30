"""Reviewed holding loan-quality evidence from a local official BHCF archive."""
import csv,datetime as dt,hashlib,io,json,re,zipfile
from pathlib import Path
FIELDS={
 'BHCK1403':('nonaccrual','NONACCRUAL: TOTAL LOANS AND LEASES'),
 'BHCK1406':('past_due_30_89','PAST DUE 30 THROUGH 89 DAYS AND STILL ACCRUING: TOTAL LOANS AND LEASES'),
 'BHCK1407':('past_due_90','PAST DUE 90 DAYS OR MORE AND STILL ACCRUING: TOTAL LOANS AND LEASES'),
 'BHCKB528':('held_for_investment','LOANS AND LEASES, HELD FOR INVESTMENT'),
 'BHCK5369':('held_for_sale','LOANS AND LEASES HELD FOR SALE')}
SOURCE='https://www.ffiec.gov/npw/FinancialReport/FinancialDataDownload'
FORM='https://s203.q4cdn.com/711684571/files/doc_downloads/9C/2026/05/FR-Y-9C-1Q26.pdf'

def amount(raw):
 raw='' if raw is None else str(raw).strip()
 if not raw:return {'state':'missing','value':None,'raw_value':None}
 if not re.fullmatch(r'[0-9]+',raw):return {'state':'invalid','value':None,'raw_value':raw}
 value=int(raw)
 if value>9_007_199_254_740:return {'state':'invalid','value':None,'raw_value':raw}
 return {'state':'reported','value':value,'raw_value':raw}

def parse(stream,period,wanted):
 reader=csv.DictReader(stream,delimiter='^');columns=reader.fieldnames or []
 if not (set(FIELDS)|{'RSSD9001','RSSD9017','RSSD9999'}).issubset(columns) or len(columns)!=len(set(columns)):raise ValueError('invalid_columns')
 seen=set();out={}
 for row in reader:
  if None in row or any(v is None for v in row.values()):raise ValueError('malformed_row')
  rssd=row['RSSD9001'].strip()
  if not re.fullmatch('[1-9][0-9]*',rssd) or rssd in seen:raise ValueError('duplicate_or_invalid_rssd')
  seen.add(rssd)
  if row['RSSD9999']!=period.strftime('%Y%m%d'):raise ValueError('mixed_period')
  if rssd not in wanted:continue
  if not row['RSSD9017'].strip():raise ValueError('missing_name')
  out[rssd]={'rssd_id':rssd,'name':row['RSSD9017'].strip(),'fields':{code:amount(row[code]) for code in FIELDS}}
 if not out:raise ValueError('no_reviewed_holdings_in_archive')
 return out

def import_archive(archive,dictionary,registry,now=None):
 import openpyxl
 now=now or dt.datetime.now(dt.timezone.utc)
 archive=Path(archive);dictionary=Path(dictionary)
 with zipfile.ZipFile(archive) as z:
  entries=z.infolist()
  if len(entries)!=1 or not re.fullmatch('BHCF[0-9]{8}\\.txt',entries[0].filename,re.I) or entries[0].file_size>100_000_000:raise ValueError('invalid_archive')
  period=dt.datetime.strptime(entries[0].filename[4:12],'%Y%m%d').date()
  if not 0<=(now.date()-period).days<=180 or (period.month,period.day) not in [(3,31),(6,30),(9,30),(12,31)]:raise ValueError('stale_or_invalid_period')
  defs={};book=openpyxl.load_workbook(dictionary,read_only=True,data_only=True)
  try:
   for number,(code,start,end,description) in enumerate(book['Financial'].iter_rows(values_only=True),1):
    if code not in FIELDS or not start.date()<=period<=end.date():continue
    if code in defs or not description.upper().startswith(FIELDS[code][1]):raise ValueError('changed_dictionary')
    defs[code]={'metric':FIELDS[code][0],'description':description,'row':number,'valid_from':start.date().isoformat(),'valid_to':end.date().isoformat(),'unit':'USD_thousands'}
  finally:book.close()
  if set(defs)!=set(FIELDS):raise ValueError('missing_definitions')
  wanted={r['rssd_id'] for r in registry['entries']}
  with z.open(entries[0]) as stream:entities=parse(io.TextIOWrapper(stream,encoding='cp1252'),period,wanted)
 return {'schema':1,'source':'FFIEC_BHCF_loan_quality','scope':'FR_Y9C_consolidated_reporting_entity','source_url':SOURCE,'unit_evidence_url':FORM,'reporting_period':period.isoformat(),'imported_at':now.isoformat(),'published_at':None,'historical_point_in_time_usable':False,'source_file_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'dictionary_sha256':hashlib.sha256(dictionary.read_bytes()).hexdigest(),'definitions':defs,'entities':entities}

if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--archive',required=True);p.add_argument('--dictionary',required=True);p.add_argument('--registry',required=True);p.add_argument('--output',required=True);a=p.parse_args()
 result=import_archive(a.archive,a.dictionary,json.loads(Path(a.registry).read_text(encoding='utf-8-sig')))
 dest=Path(a.output)
 if dest.exists():
  previous=json.loads(dest.read_text(encoding='utf-8'))
  if previous['reporting_period']>result['reporting_period'] or not set(previous['entities']).issubset(result['entities']):raise ValueError('refusing_regression_or_incomplete_replacement')
 dest.parent.mkdir(parents=True,exist_ok=True);tmp=dest.with_suffix('.tmp');tmp.write_text(json.dumps(result,ensure_ascii=False,allow_nan=False),encoding='utf-8');tmp.replace(dest)
 print({'period':result['reporting_period'],'holdings':len(result['entities'])})
