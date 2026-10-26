"""ECB daily reference rates for descriptive EUR investor comparisons only."""
import csv,datetime as dt,io,json,math,os,re,urllib.request,zipfile
from pathlib import Path
from yahoo_sector import save
URL='https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.zip'
SOURCE='ECB euro foreign exchange reference rates'
UTC=dt.timezone.utc

def normalize(payload,now=None):
 now=now or dt.datetime.now(UTC)
 if len(payload)>5_000_000:raise ValueError('fx_archive_too_large')
 with zipfile.ZipFile(io.BytesIO(payload)) as z:
  entries=z.infolist()
  if len(entries)!=1 or entries[0].filename!='eurofxref-hist.csv' or entries[0].file_size>10_000_000:raise ValueError('unexpected_fx_archive')
  reader=csv.DictReader(io.StringIO(z.read(entries[0]).decode('utf-8-sig')))
  if not reader.fieldnames or 'Date' not in reader.fieldnames or 'USD' not in reader.fieldnames:raise ValueError('fx_columns_missing')
  if len(set(reader.fieldnames))!=len(reader.fieldnames):raise ValueError('fx_columns_duplicate')
  currencies=[c for c in reader.fieldnames if c and c!='Date']
  if any(not re.fullmatch('[A-Z]{3}',c) for c in currencies):raise ValueError('fx_currency_invalid')
  rows={};seen=set()
  for row in reader:
   date=dt.date.fromisoformat(row['Date'])
   if row['Date']!=date.isoformat() or date in seen:raise ValueError('fx_date_invalid_or_duplicate')
   seen.add(date)
   # Only completed UTC days, and enough overlap for the 400-point equity cache.
   if not 0<(now.date()-date).days<=730:continue
   rates={}
   for c in currencies:
    v=(row.get(c) or '').strip()
    if v in ('','N/A'):continue
    rate=float(v)
    if not math.isfinite(rate) or rate<=0:raise ValueError('fx_rate_invalid')
    rates[c]=rate
   if rates:rows[date.isoformat()]=rates
 if len(rows)<250 or (now.date()-dt.date.fromisoformat(max(rows))).days>7:raise ValueError('fx_history_missing_or_stale')
 return {'schema':1,'source':SOURCE,'sourceUrl':URL,'base':'EUR','quoteConvention':'currency_units_per_EUR','retrievedAt':now.isoformat(),'lastObservation':max(rows),'rates':dict(sorted(rows.items())),
  'interpretation':'Informational reference rates, not executable prices. Same-date stock closes and ECB rates are not simultaneous. No forward fills or invented FX rates.'}

def main():
 folder=Path(os.getenv('RISK_DATA_DIR',str(Path(__file__).resolve().parents[1]/'daten')))
 try:
  with urllib.request.urlopen(urllib.request.Request(URL,headers={'User-Agent':'ValueApp risk data research'}),timeout=30) as response:payload=response.read(5_000_001)
  result=normalize(payload);save(folder/'cf_ecb_fx.json',result)
  print(json.dumps({'state':'available','days':len(result['rates']),'lastObservation':result['lastObservation']}))
 except Exception as exc:
  # Preserve the old timestamp on failure; consumer freshness guards decide reuse.
  print('::warning::ECB FX refresh failed; previous dated archive retained ('+type(exc).__name__+').')
  raise SystemExit(1)
if __name__=='__main__':main()
