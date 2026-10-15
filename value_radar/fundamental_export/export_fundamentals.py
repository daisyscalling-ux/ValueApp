"""Dated supplemental observations. No calculated fair values, no credentials in output."""
import argparse, datetime as dt, json, math, os, pathlib, re, subprocess, sys, time, urllib.request
UTC=dt.timezone.utc
def stamp(): return dt.datetime.now(UTC).isoformat()
def number(x):
 try:
  n=float(x)
  return n if math.isfinite(n) and not isinstance(x,bool) else None
 except (TypeError,ValueError): return None
def save(path,data):
 path.parent.mkdir(parents=True,exist_ok=True)
 tmp=path.with_suffix('.tmp'); tmp.write_text(json.dumps(data,ensure_ascii=False,allow_nan=False),encoding='utf-8'); tmp.replace(path)
def preserve_annual(data,old):
 if old and old.get('annual') and (not data.get('annual') or old['annual']['end']>data['annual']['end']):
  data['annual']=old['annual'];data['annual_retrieved_at']=old.get('annual_retrieved_at',old['retrieved_at']);data['issues'].append('Retained prior annual block; refresh did not provide newer statements')
 else: data['annual_retrieved_at']=data['retrieved_at']
 return data
def yahoo_symbol(row):
 symbol=row.get('listing_symbol') or row.get('ticker','')
 if not re.fullmatch(r'[A-Za-z0-9:._^-]+',symbol): raise ValueError('invalid symbol')
 if ':' not in symbol: return symbol
 ex,t=symbol.split(':',1)
 suffix={'NASDAQ':'','NYSE':'','AMEX':'','XETR':'.DE','ETR':'.DE','FRA':'.F','TSE':'.T','TYO':'.T','JPX':'.T','HKEX':'.HK','HKG':'.HK','LSE':'.L','EPA':'.PA','AMS':'.AS','MIL':'.MI','SIX':'.SW','STO':'.ST','TSX':'.TO','ASX':'.AX'}
 if ex not in suffix: raise ValueError('unsupported exchange mapping')
 return t.replace('.','-') if ex in ('NASDAQ','NYSE','AMEX') else t+suffix[ex]
FIELDS={'revenue':'Total Revenue','net_income':'Net Income','eps_trailing':'Diluted EPS','gross_profit':'Gross Profit','ebit':'Operating Income','ebitda':'EBITDA','weighted_shares':'Diluted Average Shares','operating_cashflow':'Operating Cash Flow','capex':'Capital Expenditure','total_debt':'Total Debt','cash':'Cash And Cash Equivalents','total_assets':'Total Assets','equity':'Stockholders Equity'}
def yahoo_annual(frames,info,now=None):
 now=now or dt.datetime.now(UTC).date()
 inc=frames.get('income',{}); candidates=sorted(inc,reverse=True)
 for date in candidates:
  end=dt.date.fromisoformat(date[:10]); age=(now-end).days
  if not 0<=age<=460: continue
  latest=info.get('lastFiscalYearEnd')
  if latest and dt.datetime.fromtimestamp(latest,UTC).date()>end+dt.timedelta(days=35): continue
  merged={}
  for rows in frames.values(): merged.update(rows.get(date,{}))
  fields={k:number(merged.get(v)) for k,v in FIELDS.items()}
  if fields['revenue'] is None or fields['eps_trailing'] is None: continue
  prior=next((inc[d] for d in candidates if 330<=(end-dt.date.fromisoformat(d[:10])).days<=400),None)
  prior_rev=number((prior or {}).get('Total Revenue'))
  if prior_rev and prior_rev>0: fields['revenue_growth']=fields['revenue']/prior_rev-1
  return {'end':str(end),'period_type':'annual','currency':info.get('financialCurrency'),'source':'Yahoo annual statements','source_url':'https://finance.yahoo.com/quote/'+info['symbol']+'/financials/','published_at':None,'fields':fields}
 return None
TAGS={'revenue':['RevenueFromContractWithCustomerExcludingAssessedTax','Revenues','SalesRevenueNet'],'net_income':['NetIncomeLoss'],'eps_trailing':['EarningsPerShareDiluted'],'gross_profit':['GrossProfit'],'ebit':['OperatingIncomeLoss'],'weighted_shares':['WeightedAverageNumberOfDilutedSharesOutstanding'],'operating_cashflow':['NetCashProvidedByUsedInOperatingActivities'],'capex':['PaymentsToAcquirePropertyPlantAndEquipment'],'cash':['CashAndCashEquivalentsAtCarryingValue'],'total_assets':['Assets'],'equity':['StockholdersEquity']}
def sec_annual(data,cik,now=None):
 today=now or dt.datetime.now(UTC).date(); facts=data.get('facts',{}).get('us-gaap',{}); groups={}
 if str(data.get('cik','')).lstrip('0')!=str(cik).lstrip('0'): return None
 for key,tags in TAGS.items():
  unit='USD/shares' if key=='eps_trailing' else 'shares' if key=='weighted_shares' else 'USD'
  for tag in tags:
   for f in facts.get(tag,{}).get('units',{}).get(unit,[]):
    try:
     end=dt.date.fromisoformat(f['end']); filed=dt.date.fromisoformat(f['filed'])
     if f.get('form') not in ('10-K','10-K/A') or not 0<=(today-end).days<=460 or filed>today: continue
     if key not in ('cash','total_assets','equity') and not 330<=(end-dt.date.fromisoformat(f['start'])).days<=400: continue
     g=groups.setdefault((str(end),f['accn'],str(filed)),{})
     if key not in g and number(f.get('val')) is not None: g[key]=number(f['val'])
    except (KeyError,ValueError): continue
 eligible=[(k,v) for k,v in groups.items() if all(x in v for x in ('revenue','eps_trailing','net_income'))]
 if not eligible: return None
 (end,accn,filed),fields=max(eligible,key=lambda x:(x[0][0],x[0][2]))
 return {'end':end,'published_at':filed,'accession':accn,'period_type':'annual','currency':'USD','source':'SEC companyfacts / US-GAAP','source_url':f'https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accn.replace("-","")}/','fields':fields}
def collect(row):
 import yfinance as yf
 ys=yahoo_symbol(row); t=yf.Ticker(ys); info=t.get_info()
 if info.get('symbol','').upper()!=ys.upper(): raise ValueError('Yahoo identity mismatch')
 frames={}
 for key,attr in [('income','income_stmt'),('balance','balance_sheet'),('cashflow','cashflow')]:
  frame=getattr(t,attr); frames[key]=json.loads(frame.to_json(date_format='iso'))
 annual=yahoo_annual(frames,info); errors=[]
 cik=str(row.get('cik') or '').strip(); ua=os.getenv('SEC_USER_AGENT','')
 if cik.isdigit() and ua and ys.find('.')<0:
  try:
   req=urllib.request.Request(f'https://data.sec.gov/api/xbrl/companyfacts/CIK{int(cik):010d}.json',headers={'User-Agent':ua,'Accept':'application/json'})
   with urllib.request.urlopen(req,timeout=12) as response: sec=sec_annual(json.load(response),cik)
   if sec and (not annual or sec['end']>=annual['end']): annual=sec
  except Exception: errors.append('SEC unavailable; no replacement fabricated')
 # Reviewed issuer releases bridge the interval before structured 10-K facts
 # appear. Data records, not issuer-specific valuation code; automatically
 # superseded by newer structured statements.
 reviewed=pathlib.Path(__file__).parent/'reviewed'/(re.sub('[^A-Za-z0-9._-]','_',row.get('listing_symbol') or row['ticker'])+'.json')
 if reviewed.exists():
  r=json.loads(reviewed.read_text(encoding='utf-8'))
  if r.get('symbol')==(row.get('listing_symbol') or row['ticker']) and r.get('annual',{}).get('reviewed_at') and r['annual'].get('published_at','9999')<=dt.datetime.now(UTC).date().isoformat():
   if not annual or r['annual']['end']>annual['end']: annual=r['annual']
 latest=info.get('lastFiscalYearEnd')
 if annual and latest and dt.datetime.fromtimestamp(latest,UTC).date()>dt.date.fromisoformat(annual['end'])+dt.timedelta(days=35):
  errors.append('Latest completed fiscal year missing from statement sources'); annual=None
 if not annual: errors.append('No current dated annual statements available')
 currency=info.get('currency'); observed=info.get('regularMarketTime')
 market={k:number(info.get(v)) for k,v in {'price':'regularMarketPrice','shares_out':'sharesOutstanding','52w_high':'fiftyTwoWeekHigh','52w_low':'fiftyTwoWeekLow','target_mean':'targetMeanPrice','analyst_count':'numberOfAnalystOpinions','beta':'beta'}.items()}
 return {'schema':1,'symbol':row.get('listing_symbol') or row['ticker'],'yahoo_symbol':ys,'retrieved_at':stamp(),'latest_fiscal_end':dt.datetime.fromtimestamp(latest,UTC).date().isoformat() if latest else None,'annual':annual,'market':{'currency':currency,'quote_at':dt.datetime.fromtimestamp(observed,UTC).isoformat() if observed else None,'source':'Yahoo Finance','source_url':f'https://finance.yahoo.com/quote/{ys}/','fields':market},'estimates':{'eps_forward':number(info.get('forwardEps')),'horizon':None,'usable':False,'reason':'info response does not provide an explicit EPS forecast period'},'issues':errors}
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--universe',default='daten/cf_universum.json');ap.add_argument('--out',default='daten/fundamentals');ap.add_argument('--symbols',default='');ap.add_argument('--budget-min',type=float,default=120);ap.add_argument('--child');ap.add_argument('--result');args=ap.parse_args()
 if args.child:
  save(pathlib.Path(args.result),collect(json.loads(args.child)));return
 out=pathlib.Path(args.out); rows=json.loads(pathlib.Path(args.universe).read_text(encoding='utf-8'))['kandidaten']
 wanted=set(args.symbols.split(',')) if args.symbols else set()
 if wanted:
  selected=[r for r in rows if r.get('ticker') in wanted or r.get('listing_symbol') in wanted]
  found={str(r.get(k)) for r in selected for k in ('ticker','listing_symbol')}
  for symbol in wanted-found:
   if re.fullmatch(r'[A-Z0-9._-]+:[A-Z0-9._-]+',symbol):selected.append({'ticker':symbol,'listing_symbol':symbol})
  rows=selected
 index_path=out/'index.json'; index=json.loads(index_path.read_text()) if index_path.exists() else {'schema':1,'listings':{},'attempts':{}}
 rows.sort(key=lambda r:index['attempts'].get(r.get('listing_symbol') or r['ticker'],''))
 deadline=time.monotonic()+args.budget_min*60; success=failed=0
 for row in rows:
  if time.monotonic()+50>deadline: break
  symbol=row.get('listing_symbol') or row['ticker']; filename=re.sub('[^A-Za-z0-9._-]','_',symbol)+'.json'; dest=out/filename; temp=out/(filename+'.pending')
  out.mkdir(parents=True,exist_ok=True)
  try:
   result=subprocess.run([sys.executable,__file__,'--child',json.dumps(row),'--result',str(temp)],timeout=45,capture_output=True)
   if result.returncode or not temp.exists(): raise ValueError('collector failed')
   data=json.loads(temp.read_text()); old=json.loads(dest.read_text()) if dest.exists() else None
   # Never overwrite a newer retained annual block with an older/missing one.
   data=preserve_annual(data,old)
   save(dest,data);index['listings'][symbol]=filename;success+=1
  except Exception: failed+=1
  finally:
   temp.unlink(missing_ok=True);index['attempts'][symbol]=stamp();index['generated_at']=stamp();index['last_run']={'success':success,'failed':failed};save(index_path,index)
 print(json.dumps({'success':success,'failed':failed,'queued':len(rows)-success-failed}))
 if not success: raise SystemExit(1)
if __name__=='__main__': main()

