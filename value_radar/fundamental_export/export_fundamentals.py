"""Dated supplemental observations. No calculated fair values, no credentials in output."""
import argparse, datetime as dt, json, math, os, pathlib, re, subprocess, sys, time, urllib.request
from listing_identity import listing_matches,SUFFIXES
from reference_data import fetch_ecb,fetch_sec_listings
from queue_policy import order_rows, due, failed as queue_failed
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
 else:
  data['annual_retrieved_at']=data['retrieved_at']
  # A partial response must not erase recently verified fields for the same
  # fiscal period. Matching anchors are still mandatory; ages are not reset.
  if old and old.get('annual') and data.get('annual'):
   observed=old.get('annual_retrieved_at',old.get('retrieved_at'))
   try:
    age=dt.datetime.fromisoformat(data['retrieved_at'].replace('Z','+00:00'))-dt.datetime.fromisoformat(observed.replace('Z','+00:00'))
    if dt.timedelta(0)<=age<=dt.timedelta(days=7):
     secondary=json.loads(json.dumps(old['annual']))
     for key in secondary.get('fields',{}):
      secondary.setdefault('field_sources',{}).setdefault(key,{})['retrieved_at']=old['annual'].get('field_sources',{}).get(key,{}).get('retrieved_at',observed)
     # Reject expired retained fields independently of the enclosing response.
     for key,source in secondary.get('field_sources',{}).items():
      try:
       field_age=dt.datetime.fromisoformat(data['retrieved_at'].replace('Z','+00:00'))-dt.datetime.fromisoformat(source['retrieved_at'].replace('Z','+00:00'))
       if (not dt.timedelta(0)<=field_age<=dt.timedelta(days=7)
           or source.get('end',secondary['end'])!=secondary['end']
           or source.get('currency',secondary['currency'])!=secondary['currency']):secondary['fields'].pop(key,None)
      except (ValueError,TypeError,KeyError):secondary['fields'].pop(key,None)
     data['annual']=enrich_matching_annual(data['annual'],secondary)
     diagnostics=data.get('annual_diagnostics')
     if diagnostics and diagnostics.get('selected_annual_end')==data['annual']['end']:
      diagnostics['missing_fields']=[k for k in ('eps_trailing','total_debt','cash','operating_cashflow','capex') if number(data['annual']['fields'].get(k)) is None]
      diagnostics['state']='partial' if diagnostics['missing_fields'] else 'available'
   except (ValueError,TypeError,AttributeError):pass
 return data
def yahoo_symbol(row):
 symbol=row.get('listing_symbol') or row.get('ticker','')
 if not re.fullmatch(r'[A-Za-z0-9:._^-]+',symbol): raise ValueError('invalid symbol')
 if ':' not in symbol: return symbol
 ex,t=symbol.split(':',1)
 suffix={'NASDAQ':'','NYSE':'','AMEX':'','XETR':'.DE','ETR':'.DE','FRA':'.F','TSE':'.T','TYO':'.T','JPX':'.T','HKEX':'.HK','HKG':'.HK','LSE':'.L','EPA':'.PA','AMS':'.AS','MIL':'.MI','SIX':'.SW','STO':'.ST','TSX':'.TO','ASX':'.AX','OTC':'','BME':'.MC','OSL':'.OL','HEL':'.HE','CPH':'.CO','GPW':'.WA','VIE':'.VI','ATHEX':'.AT','SET':'.BK','MYX':'.KL','ISE':'.IR','DUB':'.IR'}
 if ex=='EURONEXT':
  original=str(row.get('ticker',''))
  if original.rsplit('.',1)[0]==t and original.endswith(('.PA','.AS','.BR','.LS','.IR')): return original
  raise ValueError('ambiguous Euronext venue; original exchange suffix required')
 if ex not in suffix: raise ValueError('unsupported exchange mapping')
 # London commonly publishes RR., NG., etc.; Yahoo uses RR.L, not RR..L.
 if ex=='LSE':t=t.rstrip('.')
 return t.replace('.','-') if ex in ('NASDAQ','NYSE','AMEX','OTC') else t+suffix[ex]

def corrected_london_retry(row,failure):
 symbol=str(row.get('listing_symbol') or row.get('ticker') or '')
 try:mapped=yahoo_symbol(row)
 except ValueError:return False
 return bool(symbol.startswith('LSE:') and symbol.endswith('.') and failure
             and failure.get('reason') in ('mapping','provider_or_identity')
             and failure.get('mapped_symbol')!=mapped)
FIELDS={'revenue':'Total Revenue','net_income':'Net Income','eps_trailing':'Diluted EPS','gross_profit':'Gross Profit','ebit':'Operating Income','ebitda':'EBITDA','weighted_shares':'Diluted Average Shares','operating_cashflow':'Operating Cash Flow','capex':'Capital Expenditure','total_debt':'Total Debt','cash':'Cash And Cash Equivalents','total_assets':'Total Assets','equity':'Stockholders Equity','total_liabilities':'Total Liabilities Net Minority Interest','interest_expense':'Interest Expense','net_interest_income':'Net Interest Income'}
def yahoo_annual(frames,info,now=None):
 now=now or dt.datetime.now(UTC).date()
 inc=frames.get('income',{}); candidates=sorted(inc,reverse=True)
 for date in candidates:
  end=dt.date.fromisoformat(date[:10]); age=(now-end).days
  if not 0<=age<=460: continue
  latest=info.get('lastFiscalYearEnd')
  if latest and dt.datetime.fromtimestamp(latest,UTC).date()>end+dt.timedelta(days=35): continue
  # Read each metric from its own statement; a null on another table must
  # never overwrite a reported value. Only the exact fiscal date is used.
  balance=frames.get('balance',{}).get(date,{})
  cashflow=frames.get('cashflow',{}).get(date,{})
  fields={k:number((balance if k in ('total_debt','cash','total_assets','equity','total_liabilities') else cashflow if k in ('operating_cashflow','capex') else inc[date]).get(v)) for k,v in FIELDS.items()}
  source_url='https://finance.yahoo.com/quote/'+info['symbol']+'/financials/'
  field_sources={}
  def reported_alias(key,table,name):
   if fields[key] is not None:return
   value=number(table.get(name))
   if value is None:return
   # Both fields are provider-reported totals, not inferred from FCF or net
   # investing cash flow. Preserve the exact provider label as provenance.
   if key=='capex' and value>0:return
   fields[key]=value
   field_sources[key]={'source':'Yahoo annual statements','source_url':source_url,'end':str(end),'currency':info.get('financialCurrency'),'derivation':'reported_alternative_label','provider_field':name}
  reported_alias('operating_cashflow',cashflow,'Cash Flowsfromusedin Operating Activities Direct')
  reported_alias('capex',cashflow,'Capital Expenditure Reported')
  def component_sum(key,table,names,negative=False):
   if fields[key] is not None: return
   values=[number(table.get(name)) for name in names]
   if any(v is None or (v>0 if negative else v<0) for v in values): return
   fields[key]=sum(values)
   field_sources[key]={'source':'Yahoo annual statements','source_url':source_url,'end':str(end),'currency':info.get('financialCurrency'),'derivation':'sum_of_reported_components','components':dict(zip(names,values))}
  # Both maturities include leases: never mix lease-inclusive and exclusive
  # components or replace an unreported maturity with zero.
  component_sum('total_debt',balance,['Current Debt And Capital Lease Obligation','Long Term Debt And Capital Lease Obligation'])
  # Gross purchases only; net investment cash flow includes disposals and
  # acquisitions and is not a substitute for capital expenditure.
  component_sum('capex',cashflow,['Purchase Of PPE','Purchase Of Intangibles'],negative=True)
  if fields['revenue'] is None or fields['revenue']<=0: continue
  prior=next((inc[d] for d in candidates if 330<=(end-dt.date.fromisoformat(d[:10])).days<=400),None)
  prior_rev=number((prior or {}).get('Total Revenue'))
  if prior_rev and prior_rev>0: fields['revenue_growth']=fields['revenue']/prior_rev-1
  return {'end':str(end),'period_type':'annual','currency':info.get('financialCurrency'),'source':'Yahoo annual statements','source_url':source_url,'published_at':None,'field_sources':field_sources,'missing_fields':[k for k in ('eps_trailing','total_debt','operating_cashflow','capex') if fields.get(k) is None],'fields':fields}
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
def enrich_matching_annual(primary,secondary):
 # Exact period/currency and two independent matching observations required.
 # Missing EPS must not discard a verified balance sheet. It must also never
 # authorize transfer of per-share fields or share counts across share bases.
 if not primary or not secondary or any(primary.get(k)!=secondary.get(k) for k in ('end','period_type','currency')): return primary
 a,b=primary['fields'],secondary['fields']
 matches=[]
 for key in ('revenue','eps_trailing','net_income'):
  x,y=number(a.get(key)),number(b.get(key))
  if x is None or y is None: continue
  if abs(x-y)>max(abs(x),abs(y),1)*0.001: return primary
  matches.append(key)
 if 'revenue' not in matches or not any(k in matches for k in ('eps_trailing','net_income')): return primary
 for key,value in b.items():
  if key not in FIELDS and key!='revenue_growth': continue
  if key in ('eps_trailing','weighted_shares') and 'eps_trailing' not in matches: continue
  if key in ('total_debt','cash','total_assets') and number(value) is not None and number(value)<0: continue
  if a.get(key) is None and number(value) is not None:
   a[key]=value
   primary.setdefault('field_sources',{})[key]={**secondary.get('field_sources',{}).get(key,{}),'source':secondary.get('source'),'source_url':secondary.get('source_url'),'published_at':secondary.get('published_at'),'end':secondary['end'],'currency':secondary.get('currency'),'matched_fields':matches}
 primary['missing_fields']=[k for k in ('eps_trailing','total_debt','operating_cashflow','capex') if a.get(k) is None]
 return primary

def annual_diagnostics(annual,frames,info,now=None):
 now=now or dt.datetime.now(UTC).date()
 latest=max(frames.get('income',{}),default=None)
 required=('eps_trailing','total_debt','cash','operating_cashflow','capex')
 missing=[k for k in required if not annual or number(annual.get('fields',{}).get(k)) is None]
 reasons=[]
 if not annual:
  if not latest: reasons.append('income_table_empty')
  else:
   end=dt.date.fromisoformat(latest[:10]); age=(now-end).days
   if age>460: reasons.append('income_table_older_than_460_days')
   if age<0: reasons.append('income_table_future_dated')
   revenue=number(frames['income'][latest].get('Total Revenue'))
   if revenue is None: reasons.append('latest_income_revenue_missing')
   elif revenue<=0: reasons.append('latest_income_revenue_nonpositive')
   fiscal=info.get('lastFiscalYearEnd')
   if fiscal and dt.datetime.fromtimestamp(fiscal,UTC).date()>end+dt.timedelta(days=35):reasons.append('table_behind_provider_fiscal_end')
  if not reasons:reasons.append('no_eligible_annual_block')
 return {'state':('partial' if missing else 'available') if annual else 'provider_table_empty' if not latest else 'statement_outdated_or_incomplete','latest_income_table_end':latest[:10] if latest else None,'selected_annual_end':annual.get('end') if annual else None,'missing_fields':missing,'reason_codes':reasons}

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
   if sec and (not annual or sec['end']>=annual['end']): annual=enrich_matching_annual(sec,annual)
  except Exception: errors.append('SEC unavailable; no replacement fabricated')
 # Reviewed issuer releases bridge the interval before structured 10-K facts
 # appear. Data records, not issuer-specific valuation code; automatically
 # superseded by newer structured statements.
 reviewed=pathlib.Path(__file__).parent/'reviewed'/(re.sub('[^A-Za-z0-9._-]','_',row.get('listing_symbol') or row['ticker'])+'.json')
 if reviewed.exists():
  r=json.loads(reviewed.read_text(encoding='utf-8'))
  if r.get('symbol')==(row.get('listing_symbol') or row['ticker']) and r.get('annual',{}).get('reviewed_at') and r['annual'].get('published_at','9999')<=dt.datetime.now(UTC).date().isoformat():
   if not annual or r['annual']['end']>annual['end']: annual=r['annual']
   else: annual=enrich_matching_annual(annual,r['annual'])
 latest=info.get('lastFiscalYearEnd')
 if annual and latest and dt.datetime.fromtimestamp(latest,UTC).date()>dt.date.fromisoformat(annual['end'])+dt.timedelta(days=35):
  errors.append('Latest completed fiscal year missing from statement sources'); annual=None
 if not annual: errors.append('No current dated annual statements available')
 elif annual['fields'].get('eps_trailing') is None: errors.append('Current annual statements available; diluted EPS missing, earnings multiple excluded')
 diagnostics=annual_diagnostics(annual,frames,info)
 currency=info.get('currency'); observed=info.get('regularMarketTime')
 market={k:number(info.get(v)) for k,v in {'price':'regularMarketPrice','shares_out':'sharesOutstanding','52w_high':'fiftyTwoWeekHigh','52w_low':'fiftyTwoWeekLow','target_mean':'targetMeanPrice','analyst_count':'numberOfAnalystOpinions','beta':'beta'}.items()}
 references={}
 reference_path=os.getenv('FUNDAMENTAL_REFERENCES_PATH')
 if reference_path:
  try: references=json.loads(pathlib.Path(reference_path).read_text(encoding='utf-8'))
  except (OSError,ValueError):pass
 basis_path=pathlib.Path(__file__).parent/'share_basis.json'
 bases=json.loads(basis_path.read_text(encoding='utf-8')) if basis_path.exists() else {}
 return {'annual_diagnostics':diagnostics,'fx':references.get('fx'),'share_basis':bases.get(row.get('listing_symbol') or row['ticker']),'schema':1,'symbol':row.get('listing_symbol') or row['ticker'],'yahoo_symbol':ys,'retrieved_at':stamp(),'latest_fiscal_end':dt.datetime.fromtimestamp(latest,UTC).date().isoformat() if latest else None,'annual':annual,'market':{'currency':currency,'quote_at':dt.datetime.fromtimestamp(observed,UTC).isoformat() if observed else None,'source':'Yahoo Finance','source_url':f'https://finance.yahoo.com/quote/{ys}/','fields':market},'estimates':{'eps_forward':number(info.get('forwardEps')),'horizon':None,'usable':False,'reason':'info response does not provide an explicit EPS forecast period'},'issues':errors}
def select_registered_rows(universe,index,symbols):
 registry=index.setdefault('registered',{})
 # Remember explicit requests even if their first provider request fails.
 all_rows={k:dict(v) for k,v in registry.items()}
 for row in universe:
  key=row.get('listing_symbol') or row.get('ticker')
  if key:
   ticker=row.get('ticker')
   if ticker and row.get('listing_symbol') and not listing_matches(ticker,key):
    index.setdefault('identity_rejected',{})[str(ticker)]={'rejected_listing':key,'at':stamp()}
    # Never transfer contaminated name/ISIN/CIK or financials to a repaired key.
    if '.' in ticker:
     base,suffix=ticker.upper().rsplit('.',1); exchanges=SUFFIXES.get(suffix)
     if exchanges:
      correct=exchanges[0]+':'+base
      all_rows[correct]={'ticker':ticker,'listing_symbol':correct}
    continue
   all_rows[key]=row
 # Migrate old successful on-demand observations into recurring coverage.
 for key in index.get('listings',{}):
  if key not in {v['rejected_listing'] for v in index.get('identity_rejected',{}).values()} and key not in all_rows and re.fullmatch(r'[A-Z0-9._-]+:[A-Z0-9._-]+',key):
   all_rows[key]={'listing_symbol':key,'ticker':key}
 wanted={x.strip().upper() for x in symbols.split(',') if x.strip()}
 if wanted:
  selected={k:v for k,v in all_rows.items() if k.upper() in wanted or str(v.get('ticker','')).upper() in wanted}
  found={str(v.get(k,'')).upper() for v in selected.values() for k in ('listing_symbol','ticker')}
  for key in wanted-found:
   if not re.fullmatch(r'[A-Z0-9._-]+:[A-Z0-9._-]+',key): raise ValueError('Unknown ticker requires EXCHANGE:SYMBOL')
   selected[key]={'listing_symbol':key,'ticker':key}
  for key,row in selected.items():
   registry[key]={k:row[k] for k in ('listing_symbol','ticker','cik') if k in row}
  return list(selected.values())
 return list(all_rows.values())

def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--universe',default='daten/cf_universum.json');ap.add_argument('--out',default='daten/fundamentals');ap.add_argument('--symbols',default='');ap.add_argument('--budget-min',type=float,default=120);ap.add_argument('--child');ap.add_argument('--result');args=ap.parse_args()
 if args.child:
  save(pathlib.Path(args.result),collect(json.loads(args.child)));return
 out=pathlib.Path(args.out); rows=json.loads(pathlib.Path(args.universe).read_text(encoding='utf-8'))['kandidaten']
 index_path=out/'index.json'; index=json.loads(index_path.read_text(encoding='utf-8')) if index_path.exists() else {'schema':1,'listings':{},'attempts':{}}
 index.setdefault('failures',{})
 rows=select_registered_rows(rows,index,args.symbols)
 save(index_path,index) # Persist enrollment before network requests or budget expiry.
 rows=order_rows(rows,index,out.parent/'cf_risk_queue.json',time.time())
 references={'retrieved_at':stamp(),'issues':[]}
 try:references['fx']=fetch_ecb()
 except Exception:references['issues'].append('ECB reference rates unavailable; no rate substituted')
 ua=os.getenv('SEC_USER_AGENT','')
 if ua and any(not r.get('cik') for r in rows):
  try:
   ciks=fetch_sec_listings(ua)
   for row in rows:
    key=row.get('listing_symbol') or row['ticker']
    if not row.get('cik') and key in ciks: row['cik']=ciks[key]
  except Exception:references['issues'].append('SEC listing map unavailable; existing identifiers retained')
 reference_path=out/'references.json';save(reference_path,references)
 os.environ['FUNDAMENTAL_REFERENCES_PATH']=str(reference_path.resolve())
 deadline=time.monotonic()+args.budget_min*60; success=failed=skipped_cooldown=0
 for row in rows:
  if time.monotonic()+50>deadline: break
  symbol=row.get('listing_symbol') or row['ticker']; filename=re.sub('[^A-Za-z0-9._-]','_',symbol)+'.json'; dest=out/filename; temp=out/(filename+'.pending')
  if not args.symbols and not corrected_london_retry(row,index['failures'].get(symbol)) and not due(index['failures'].get(symbol),time.time()):
   skipped_cooldown+=1;continue
  out.mkdir(parents=True,exist_ok=True)
  try:
   yahoo_symbol(row) # Validate mappings before starting a network subprocess.
   result=subprocess.run([sys.executable,__file__,'--child',json.dumps(row),'--result',str(temp)],timeout=45,capture_output=True)
   if result.returncode or not temp.exists(): raise ValueError('collector failed')
   data=json.loads(temp.read_text(encoding='utf-8')); old=json.loads(dest.read_text(encoding='utf-8')) if dest.exists() else None
   # Never overwrite a newer retained annual block with an older/missing one.
   data=preserve_annual(data,old)
   save(dest,data);index['listings'][symbol]=filename;index['failures'].pop(symbol,None);success+=1
  except Exception as exc:
   failed+=1
   reason='timeout' if isinstance(exc,subprocess.TimeoutExpired) else 'mapping' if isinstance(exc,ValueError) and str(exc)!='collector failed' else 'provider_or_identity'
   index['failures'][symbol]=queue_failed(index['failures'].get(symbol),reason,stamp(),time.time())
   try:index['failures'][symbol]['mapped_symbol']=yahoo_symbol(row)
   except ValueError:pass
  finally:
   temp.unlink(missing_ok=True);index['attempts'][symbol]=stamp();index['generated_at']=stamp();index['last_run']={'success':success,'failed':failed};save(index_path,index)
 report={'generated_at':stamp(),'requested_unique':len(rows),'covered':0,'missing':[],'without_annual':[],'annual_currency_mismatch':[],'missing_analyst':[],'missing_debt':[],'missing_eps':[],'minor_unit_difference':[],'annual_gap_reasons':{}}
 for row in rows:
  symbol=row.get('listing_symbol') or row['ticker']; filename=index['listings'].get(symbol)
  if not filename or not (out/filename).exists(): report['missing'].append(symbol);continue
  data=json.loads((out/filename).read_text(encoding='utf-8')); report['covered']+=1
  annual=data.get('annual'); market=data.get('market',{})
  if not annual:
   report['without_annual'].append(symbol)
   report['annual_gap_reasons'][symbol]=data.get('annual_diagnostics',{'state':'not_classified'})
  elif annual.get('currency')!=market.get('currency'):
   report['annual_currency_mismatch'].append(symbol)
   if annual.get('currency')=='GBP' and market.get('currency') in ('GBp','GBX'): report['minor_unit_difference'].append(symbol)
  if annual and annual.get('fields',{}).get('eps_trailing') is None: report['missing_eps'].append(symbol)
  if not market.get('fields',{}).get('target_mean'): report['missing_analyst'].append(symbol)
  if annual and annual.get('fields',{}).get('total_debt') is None: report['missing_debt'].append(symbol)
 save(out/'coverage.json',report)
 print(json.dumps({'coverage':{k:len(v) if isinstance(v,list) else v for k,v in report.items()}}))
 print(json.dumps({'success':success,'failed':failed,'queued':len(rows)-success-failed-skipped_cooldown,'skipped_cooldown':skipped_cooldown}))
 if not success and not skipped_cooldown: raise SystemExit(1)
if __name__=='__main__': main()
