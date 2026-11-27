"""Dated supplemental observations. No calculated fair values, no credentials in output."""
import argparse, datetime as dt, json, math, os, pathlib, re, subprocess, sys, time, urllib.request
from share_basis_rule import ordinary_basis
from listing_identity import listing_matches,SUFFIXES
from reference_data import fetch_ecb,fetch_sec_listings
from queue_policy import order_rows, due, failed as queue_failed, annual_supply_status
from operating_lease import operating_lease
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
 # Nordische Aktiengattungen: STO:ATCO_A / CPH:NOVO_B heissen bei Yahoo ATCO-A.ST / NOVO-B.CO.
 if ex in ('STO','CPH','HEL'):t=re.sub(r'[_ ]([A-Z])$',r'-\1',t)
 return t.replace('.','-') if ex in ('NASDAQ','NYSE','AMEX','OTC') else t+suffix[ex]

def corrected_london_retry(row,failure):
 symbol=str(row.get('listing_symbol') or row.get('ticker') or '')
 try:mapped=yahoo_symbol(row)
 except ValueError:return False
 # Sofort neu versuchen, wenn sich die Yahoo-Zuordnung seit dem Fehlschlag geaendert hat (z. B. LSE RR..L -> RR.L,
 # nordische Gattungen ATCO_A.ST -> ATCO-A.ST). Aeltere LSE-Fehlschlaege ohne gespeicherte Zuordnung gelten als geaendert.
 if not failure or failure.get('reason') not in ('mapping','provider_or_identity'):return False
 if failure.get('mapped_symbol') is not None:return failure['mapped_symbol']!=mapped
 return symbol.startswith('LSE:') and symbol.endswith('.')
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
CASH_HISTORY_METHOD='yahoo_annual_cash_history_v1'
def yahoo_cash_history(frames,info,years=5):
 """Mehrjaehrige Cashflow-Historie fuer die Cash-Conversion (Ersatz, wenn ROIC keine drei vollstaendigen Jahre hat;
 Entscheidung des Nutzers 16.11.2026). Je Geschaeftsjahr nur mit operativem Cashflow, Investitionen (gemeldete Summe oder
 Sachanlagen + Immaterielle; nie Netto-Investitions-Cashflow) und Jahresueberschuss desselben Datums. Investitionen als
 positive Ausgabe. Keine Rechnung hier: die App rechnet und prueft (cash-conversion.ts)."""
 inc,cf=frames.get('income',{}),frames.get('cashflow',{});out=[]
 for date in sorted(set(inc)&set(cf),reverse=True)[:years]:
  c,i=cf.get(date,{}),inc.get(date,{})
  ocf=number(c.get('Operating Cash Flow'));ni=number(i.get('Net Income'))
  capex=number(c.get('Capital Expenditure'));how='reported_total'
  if capex is None:
   capex=number(c.get('Capital Expenditure Reported'));how='reported_alternative_label'
  if capex is None:
   parts=[number(c.get(k)) for k in ('Purchase Of PPE','Purchase Of Intangibles')]
   if all(v is not None and v<=0 for v in parts):capex=sum(parts);how='sum_of_reported_components'
  if ocf is None or ni is None or capex is None or capex>0:continue
  out.append({'end':date[:10],'currency':info.get('financialCurrency'),'fields':{'operating_cashflow':ocf,'capex':-capex,'net_income':ni},'capex_derivation':how})
 return {'method':CASH_HISTORY_METHOD,'source':'Yahoo annual statements','source_url':'https://finance.yahoo.com/quote/'+str(info.get('symbol'))+'/cash-flow/','annuals':sorted(out,key=lambda a:a['end'])}
# Kennzahlen je Aktie und Geschäftsjahr (seit 26.11.2026, Wunsch des Nutzers): Gewinn je Aktie, Gewinn, Eigenkapital,
# Aktienzahl und gezahlte Dividenden aus den Yahoo-Jahresabschlüssen, dazu der unbereinigte Schlusskurs am letzten
# Handelstag bis zum Stichtag und die Dividenden je Aktie im Geschäftsjahr (Kurswährung). Keine Rechnung hier: KGV, KBV,
# Graham-Zahl, Rendite und Wachstum rechnet und prüft die App (kennzahlen-je-aktie.ts). Fehlende Felder bleiben None.
PER_SHARE_METHOD='yahoo_annual_per_share_v1'
def kennzahlen_jahre(frames,info,kurse,years=4):
 """kurse: Liste (datum 'YYYY-MM-DD', schluss, dividende) aufsteigend, unbereinigt, Kurswährung."""
 inc,bal,cf=frames.get('income',{}),frames.get('balance',{}),frames.get('cashflow',{});out=[]
 for date in sorted(inc,reverse=True)[:years]:
  end=date[:10];i,b,c=inc.get(date,{}),bal.get(date,{}),cf.get(date,{})
  try:e=dt.date.fromisoformat(end)
  except ValueError:continue
  bis=[k for k in kurse if k[0]<=end]
  preis=bis[-1] if bis and (e-dt.date.fromisoformat(bis[-1][0])).days<=7 else None
  start=(e-dt.timedelta(days=365)).isoformat()
  div=[k[2] for k in kurse if start<k[0]<=end and number(k[2]) is not None and k[2]>0]
  paid=number(c.get('Cash Dividends Paid'))
  out.append({'end':end,'currency':info.get('financialCurrency'),
   'fields':{'eps_diluted':number(i.get('Diluted EPS')),'net_income':number(i.get('Net Income')),'equity':number(b.get('Stockholders Equity')),
    'shares':number(b.get('Ordinary Shares Number')) or number(b.get('Share Issued')),'dividends_paid':abs(paid) if paid is not None else None},
   'kurs':{'datum':preis[0] if preis else None,'schluss':number(preis[1]) if preis else None,'dividende_je_aktie':round(sum(div),6) if kurse else None,'waehrung':info.get('currency')}})
 return {'method':PER_SHARE_METHOD,'source':'Yahoo annual statements und Kurshistorie','source_url':'https://finance.yahoo.com/quote/'+str(info.get('symbol'))+'/financials/','jahre':sorted(out,key=lambda x:x['end'])}
# Archiv der Kennzahlen je Aktie (seit 26.11.2026, Entscheidung des Nutzers): Yahoo liefert nur die letzten vier
# Geschäftsjahre; mit jedem neuen Jahr fiele das älteste weg. Jahre aus der bisherigen Datei, die Yahoo nicht mehr liefert,
# bleiben erhalten und tragen herkunft 'archiv' mit dem Datum der letzten Lieferung. Es wird nie gelöscht. Liefert Yahoo
# einen Stichtag erneut, gilt der neue Wert. Übernommen wird nur bei gleicher Notierung (symbol, yahoo_symbol) und
# gleicher Methode; ein archiviertes Jahr wird nie mit einem gelieferten vermischt.
PER_SHARE_ARCHIVE_METHOD='per_share_archive_v1'
# Ältere Geschäftsjahre aus SEC companyfacts (seit 27.11.2026, Entscheidung des Nutzers): nur US-GAAP-10-K, Abschluss und
# Notierung in USD. Je Stichtag gilt die zuletzt eingereichte Zahl (Anpassungen späterer 10-K). Gewinn je Aktie und Aktienzahl
# werden mit allen Yahoo-Splits nach dem Einreichungsdatum auf die heutige Aktienbasis gebracht, damit sie zum
# split-bereinigten Yahoo-Kurs passen (KGV und KBV hängen davon nicht ab, die Reihe des Gewinns je Aktie schon).
# Abgleich Pflicht: In mindestens SEC_PS_MIN_ABGLEICH Jahren, die auch Yahoo liefert, darf der Gewinn je Aktie höchstens
# SEC_PS_TOLERANZ abweichen; sonst wird der ganze SEC-Block verworfen. SEC ergänzt nur Jahre vor dem ältesten Yahoo-Jahr.
SEC_PER_SHARE_METHOD='sec_annual_per_share_v1'
SEC_PS_TOLERANZ=0.02
SEC_PS_MIN_ABGLEICH=1
SEC_PS_MAX_JAHRE=20
SEC_PS_TAGS={'eps_diluted':('EarningsPerShareDiluted','USD/shares',True),'net_income':('NetIncomeLoss','USD',True),
 'equity':('StockholdersEquity','USD',False),'shares':('CommonStockSharesOutstanding','shares',False)}
def _sec_fakten(facts,tag,unit,dauer):
 """{stichtag: fakt} je Stichtag die zuletzt eingereichte 10-K-Zahl; Flussgrößen nur mit Jahresdauer."""
 out={}
 for f in facts.get(tag,{}).get('units',{}).get(unit,[]):
  try:
   if f.get('form') not in ('10-K','10-K/A'):continue
   end=dt.date.fromisoformat(f['end']);filed=dt.date.fromisoformat(f['filed']);v=number(f.get('val'))
   if v is None or not re.fullmatch(r'\d{10}-\d{2}-\d{6}',str(f.get('accn',''))):continue
   if dauer and not 330<=(end-dt.date.fromisoformat(f['start'])).days<=400:continue
  except (KeyError,ValueError,TypeError):continue
  alt=out.get(end)
  if alt is None or filed>alt['filed']:out[end]={'val':v,'filed':filed,'accn':f['accn'],'form':f['form']}
 return out
def sec_jahre_je_aktie(data,cik,kurse,splits,yahoo_jahre,info,sha,stand,heute=None):
 """(jahre, block, grund): SEC-Jahre vor dem ältesten Yahoo-Jahr oder Grund, warum keine."""
 heute=heute or dt.datetime.now(UTC).date()
 if str(data.get('cik','')).lstrip('0')!=str(cik).lstrip('0'):return [],None,'SEC-Identität (CIK) abweichend'
 if info.get('financialCurrency')!='USD' or info.get('currency')!='USD':return [],None,'Abschluss oder Notierung nicht in USD'
 facts=data.get('facts',{}).get('us-gaap',{})
 f={k:_sec_fakten(facts,tag,unit,dauer) for k,(tag,unit,dauer) in SEC_PS_TAGS.items()}
 sp=[(dt.date.fromisoformat(s['date']),s['ratio']) for s in splits if number(s.get('ratio')) and s['ratio']>0]
 def faktor(filed):
  x=1.0
  for d,r in sp:
   if d>filed:x*=r
  return x
 def eps_adj(end):
  e=f['eps_diluted'].get(end);return (e['val']/faktor(e['filed']),e) if e else (None,None)
 # Abgleich mit Yahoo
 yj={dt.date.fromisoformat(j['end']):j for j in yahoo_jahre if isinstance(j.get('end'),str)}
 vergleich=[]
 for end,j in yj.items():
  # Stichtage dürfen bis 7 Tage abweichen (52/53-Wochen-Jahre: Yahoo 31.01., SEC 29.01.).
  nah=[e for e in f['eps_diluted'] if abs((e-end).days)<=7]
  y=number((j.get('fields') or {}).get('eps_diluted'));s,_=eps_adj(min(nah,key=lambda e:abs((e-end).days))) if nah else (None,None)
  if y is None or s is None:continue
  ab=abs(s-y)/max(abs(s),abs(y),0.01);vergleich.append((end,ab,s,y))
 schlecht=[v for v in vergleich if v[1]>SEC_PS_TOLERANZ]
 if schlecht:
  e,_,s,y=schlecht[0];return [],None,f'Gewinn je Aktie GJ {e.year} weicht ab (SEC {s:.4g}, Yahoo {y:.4g})'
 if len(vergleich)<SEC_PS_MIN_ABGLEICH:return [],None,'Kein Geschäftsjahr zum Abgleich mit Yahoo'
 erstes=min(yj) if yj else heute
 out=[]
 for end in sorted(f['eps_diluted'],reverse=True):
  if end>=erstes-dt.timedelta(days=35) or (heute-end).days>365*SEC_PS_MAX_JAHRE:continue
  eps,quelle=eps_adj(end)
  ni=f['net_income'].get(end);eq=f['equity'].get(end);sh=f['shares'].get(end)
  ende=end.isoformat();bis=[k for k in kurse if k[0]<=ende]
  preis=bis[-1] if bis and (end-dt.date.fromisoformat(bis[-1][0])).days<=7 else None
  start=(end-dt.timedelta(days=365)).isoformat()
  div=[k[2] for k in kurse if start<k[0]<=ende and number(k[2]) is not None and k[2]>0]
  out.append({'end':ende,'currency':'USD','herkunft':'sec',
   'fields':{'eps_diluted':round(eps,6),'net_income':ni['val'] if ni else None,'equity':eq['val'] if eq else None,
    'shares':sh['val']*faktor(sh['filed']) if sh else None,'dividends_paid':None},
   'kurs':{'datum':preis[0] if preis else None,'schluss':number(preis[1]) if preis else None,'dividende_je_aktie':round(sum(div),6) if kurse and kurse[0][0]<=start else None,'waehrung':'USD'},
   'sec':{'accession':quelle['accn'],'filed':quelle['filed'].isoformat(),'form':quelle['form'],'split_faktor':round(faktor(quelle['filed']),6),
    'source_url':f'https://www.sec.gov/Archives/edgar/data/{int(cik)}/{quelle["accn"].replace("-","")}/'}})
 out.sort(key=lambda x:x['end'])
 block={'method':SEC_PER_SHARE_METHOD,'cik':str(cik),'sha256':sha,'abgerufen':stand,'jahre':len(out),
  'abgleich':{'jahre':len(vergleich),'max_abweichung':round(max(v[1] for v in vergleich),6)},'source':'SEC companyfacts / US-GAAP (10-K)'}
 return out,block,None
def per_share_archivieren(data,old):
 neu=data.get('per_share');stand=data.get('retrieved_at')
 if isinstance(neu,dict):
  for j in neu.get('jahre',[]):
   if j.get('herkunft')!='sec':j['herkunft']='yahoo';j['zuletzt_geliefert']=stand
 alt=(old or {}).get('per_share')
 if not isinstance(alt,dict) or alt.get('method')!=PER_SHARE_METHOD:return data
 if (old.get('symbol'),old.get('yahoo_symbol'))!=(data.get('symbol'),data.get('yahoo_symbol')):
  data.setdefault('issues',[]).append('Archiv der Kennzahlen je Aktie verworfen: Notierung abweichend');return data
 if not isinstance(neu,dict):
  data['per_share']=neu=alt;data.setdefault('issues',[]).append('Kennzahlen je Aktie: Abruf fehlgeschlagen, bisheriger Block behalten')
  return data
 da={j['end'] for j in neu.get('jahre',[]) if isinstance(j,dict) and isinstance(j.get('end'),str)};n=0
 for j in alt.get('jahre',[]):
  if not isinstance(j,dict) or not isinstance(j.get('end'),str):continue
  # SEC-Jahre (seit 27.11.2026) kommen bei jedem Lauf neu; fehlt der SEC-Abruf, bleiben sie unverändert als SEC.
  if j.get('herkunft')=='sec':
   if j['end'] not in da:neu['jahre'].append(j);da.add(j['end'])
   continue
  # Eigene, früher von Yahoo gelieferte Jahre haben Vorrang vor SEC für denselben Stichtag.
  if j['end'] in da:
   if not any(x.get('end')==j['end'] and x.get('herkunft')=='sec' for x in neu['jahre']):continue
   neu['jahre']=[x for x in neu['jahre'] if x.get('end')!=j['end']]
  if j.get('herkunft')!='archiv':j={**j,'herkunft':'archiv','zuletzt_geliefert':j.get('zuletzt_geliefert') or old.get('retrieved_at')}
  neu['jahre'].append(j);n+=1;da.add(j['end'])
 neu['jahre'].sort(key=lambda x:x['end'])
 # Behaltene SEC-Jahre brauchen ihren Block (Prüfsumme, Abgleich); ohne neuen SEC-Abruf gilt der bisherige.
 if 'sec' not in neu and isinstance(alt.get('sec'),dict) and any(x.get('herkunft')=='sec' for x in neu['jahre']):neu['sec']=alt['sec']
 if n:neu['archiv']={'method':PER_SHARE_ARCHIVE_METHOD,'jahre':n}
 return data
# Gesamtumsatz zuerst (11.11.2026): RevenueFromContractWithCustomer... (ASC 606) enthaelt keine Miet-, Leasing-, Zins- oder
# Praemienertraege; bei United Rentals, ADM, GM, REITs und Banken war der Umsatz dadurch bis zu 99 % zu niedrig.
TAGS={'revenue':['Revenues','RevenueFromContractWithCustomerExcludingAssessedTax','SalesRevenueNet'],'net_income':['NetIncomeLoss'],'eps_trailing':['EarningsPerShareDiluted'],'gross_profit':['GrossProfit'],'ebit':['OperatingIncomeLoss'],'weighted_shares':['WeightedAverageNumberOfDilutedSharesOutstanding'],'operating_cashflow':['NetCashProvidedByUsedInOperatingActivities'],'capex':['PaymentsToAcquirePropertyPlantAndEquipment'],'cash':['CashAndCashEquivalentsAtCarryingValue'],'total_assets':['Assets'],'equity':['StockholdersEquity']}
def sec_revenue_growth(facts,accn,end):
 """{'value','tag','prior_end'} oder None: aktueller und Vorjahresumsatz mit demselben Tag aus derselben Einreichung."""
 for tag in TAGS['revenue']:
  cur=prior=None;prior_end=None
  for f in facts.get(tag,{}).get('units',{}).get('USD',[]):
   try:
    if f.get('accn')!=accn or f.get('form') not in ('10-K','10-K/A'):continue
    e=dt.date.fromisoformat(f['end']);st=dt.date.fromisoformat(f['start'])
    if not 330<=(e-st).days<=400:continue
    v=number(f.get('val'))
    if v is None:continue
    if e==end:cur=v
    elif 330<=(end-e).days<=400:prior,prior_end=v,str(e)
   except (KeyError,ValueError):continue
  if cur is not None and prior and prior>0 and cur>0:return {'value':cur/prior-1,'tag':tag,'prior_end':prior_end}
 return None
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
 # Umsatzwachstum aus dem Vorjahreswert DERSELBEN Einreichung und desselben XBRL-Tags (Vergleichszahlen des 10-K,
 # seit 16.11.2026). Vorher fehlte es bei SEC-Abschluessen ohne passenden Yahoo-Abschluss (68 Titel, u. a. MU, HIG).
 sources={}
 growth=sec_revenue_growth(facts,accn,dt.date.fromisoformat(end))
 if growth:
  fields={**fields,'revenue_growth':growth['value']}
  sources['revenue_growth']={'source':'SEC companyfacts / US-GAAP','derivation':'same_filing_prior_year','tag':growth['tag'],'prior_end':growth['prior_end'],'accession':accn}
 return {'field_sources':sources,'end':end,'published_at':filed,'accession':accn,'period_type':'annual','currency':'USD','source':'SEC companyfacts / US-GAAP','source_url':f'https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accn.replace("-","")}/','fields':fields}
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

def native_risk_annual(annual,symbol):
 if not annual:return None
 block=json.loads(json.dumps(annual))
 block.update(symbol=symbol,purpose='standalone_balance_risk_context')
 return block

ESTIMATE_METHOD='consensus_0y_1y_v1'
def consensus_estimates(table,info,ys,now=None):
 """Analystenkonsens je Geschaeftsjahr (Yahoo earnings estimate, 0y = laufendes, +1y = naechstes GJ) mit Analystenzahl,
 Waehrung und Geschaeftsjahresende. Keine Mischung und kein Gate hier: die App rechnet den 12-Monats-Mix und prueft
 (forward-estimate.ts). usable=False mit Grund, wenn der Block unvollstaendig ist."""
 now=now or dt.datetime.now(UTC)
 out={'method':ESTIMATE_METHOD,'source':'Yahoo Finance earnings estimate','source_url':f'https://finance.yahoo.com/quote/{ys}/analysis/',
      'as_of':now.isoformat(),'currency':info.get('financialCurrency'),'periods':{},'usable':False,'reason':None}
 nfy=info.get('nextFiscalYearEnd');lfy=info.get('lastFiscalYearEnd')
 try:
  end0=dt.datetime.fromtimestamp(nfy,UTC).date() if nfy else None
  last=dt.datetime.fromtimestamp(lfy,UTC).date() if lfy else None
 except (TypeError,ValueError,OSError):end0=last=None
 rows=table if isinstance(table,dict) else {}
 end1=end0+dt.timedelta(days=365) if end0 else None
 for key,end in (('0y',end0),('+1y',end1)):
  r=rows.get(key) or {}
  out['periods'][key]={'avg':number(r.get('avg')),'low':number(r.get('low')),'high':number(r.get('high')),'analysts':number(r.get('numberOfAnalysts')),
                       'year_ago_eps':number(r.get('yearAgoEps')),'fiscal_end':end.isoformat() if end else None}
 p0,p1=out['periods']['0y'],out['periods']['+1y']
 if not out['currency']:out['reason']='Waehrung der Schaetzung fehlt'
 elif not end0 or not last or end0<=last:out['reason']='Geschaeftsjahresende fehlt oder widerspruechlich'
 elif p0['avg'] is None or p1['avg'] is None:out['reason']='Konsens fuer laufendes oder naechstes Geschaeftsjahr fehlt'
 else:out['usable']=True
 return out

def recent_splits(t,years=5):
 """Aktiensplits der letzten Jahre (Datum, neue Aktien je alte), fuer die Bereinigung der Jahresaktienzahl. yfinance
 fuehrt auch Abspaltungsfaktoren als Split (DuPont 2,39); die App nutzt nur Standardverhaeltnisse. Ausfall: []."""
 try:
  cut=dt.datetime.now(UTC)-dt.timedelta(days=365*years)
  return [{'date':k.date().isoformat(),'ratio':round(float(v),6)} for k,v in t.splits.items() if k.to_pydatetime().astimezone(UTC)>=cut and number(float(v)) and float(v)>0]
 except Exception:return []

def estimate_table(t):
 """earnings_estimate als {Periode: Felder}; Ausfall ergibt {} (Block bleibt offen, nie geschaetzt)."""
 try:
  frame=t.earnings_estimate
  return {} if frame is None else json.loads(frame.to_json(orient='index'))
 except Exception:return {}

ANALYST_METHOD='yahoo_recommendations_0m_v1'
def analyst_recommendations(frame,ys,now=None):
 """Analystenempfehlungen des laufenden Monats (Yahoo recommendation trend, Zeile period=0m) als Kauf/Halten/Verkauf
 mit Stand und Quelle. Einzige Quelle fuer App und Screener (seit 17.11.2026); die App prueft Alter und Notierung
 erneut. usable=False mit Grund, wenn die Zeile fehlt oder Zahlen ungueltig sind; nie geschaetzt."""
 now=now or dt.datetime.now(UTC)
 out={'method':ANALYST_METHOD,'source':'Yahoo Finance recommendation trend','source_url':f'https://finance.yahoo.com/quote/{ys}/analysis/',
      'as_of':now.isoformat(),'period':'0m','strong_buy':None,'buy':None,'hold':None,'sell':None,'strong_sell':None,'usable':False,'reason':None}
 rows=frame if isinstance(frame,list) else []
 row=next((r for r in rows if isinstance(r,dict) and r.get('period')=='0m'),None)
 if row is None:out['reason']='Keine Empfehlungen fuer den laufenden Monat';return out
 keys={'strong_buy':'strongBuy','buy':'buy','hold':'hold','sell':'sell','strong_sell':'strongSell'}
 for k,v in keys.items():
  x=number(row.get(v))
  out[k]=int(x) if x is not None and x>=0 and float(x).is_integer() else None
 if any(out[k] is None for k in keys):out['reason']='Empfehlungszahlen fehlen oder ungueltig'
 elif sum(out[k] for k in keys)==0:out['reason']='Keine Analystenempfehlungen'
 else:out['usable']=True
 return out

SURPRISE_METHOD='yahoo_earnings_history_v1'
def earnings_surprises(table,ys,now=None):
 """Gewinnueberraschungen der letzten Quartale (Yahoo earnings_history): Quartalsende, Ist-EPS, Schaetzung und daraus
 selbst gerechnet surprise_pct = (Ist - Schaetzung) / |Schaetzung| * 100 (Prozent wie bisher bei Finnhub; Yahoos
 surprisePercent ist ein Anteil und wird nicht uebernommen). Neueste zuerst. Quartale ohne Ist, ohne Schaetzung oder
 mit Schaetzung 0 entfallen. usable=False mit Grund unter 2 Quartalen; die App prueft Alter und Notierung erneut."""
 now=now or dt.datetime.now(UTC)
 out={'method':SURPRISE_METHOD,'source':'Yahoo Finance earnings history','source_url':f'https://finance.yahoo.com/quote/{ys}/analysis/',
      'as_of':now.isoformat(),'quarters':[],'usable':False,'reason':None}
 rows=table if isinstance(table,dict) else {}
 for key,r in rows.items():
  try:end=dt.datetime.fromisoformat(str(key).replace('Z','+00:00')).date()
  except ValueError:continue
  a,e=number((r or {}).get('epsActual')),number((r or {}).get('epsEstimate'))
  if a is None or e is None or e==0:continue
  out['quarters'].append({'quarter_end':end.isoformat(),'eps_actual':a,'eps_estimate':e,'surprise_pct':round((a-e)/abs(e)*100,4)})
 out['quarters'].sort(key=lambda q:q['quarter_end'],reverse=True)
 if len(out['quarters'])<2:out['reason']='Weniger als 2 Quartale mit Ist und Schaetzung'
 else:out['usable']=True
 return out

def earnings_history_table(t):
 """earnings_history als {Quartalsende: Felder}; Ausfall ergibt {} (Block bleibt offen)."""
 try:
  frame=t.earnings_history
  return {} if frame is None else json.loads(frame.to_json(orient='index',date_format='iso'))
 except Exception:return {}

def recommendation_rows(t):
 """recommendations als Liste von Zeilen; Ausfall ergibt [] (Block bleibt offen)."""
 try:
  frame=t.recommendations
  return [] if frame is None else json.loads(frame.to_json(orient='records'))
 except Exception:return []

def collect(row):
 import yfinance as yf
 ys=yahoo_symbol(row); t=yf.Ticker(ys); info=t.get_info()
 if info.get('symbol','').upper()!=ys.upper(): raise ValueError('Yahoo identity mismatch')
 frames={}
 for key,attr in [('income','income_stmt'),('balance','balance_sheet'),('cashflow','cashflow')]:
  frame=getattr(t,attr); frames[key]=json.loads(frame.to_json(date_format='iso'))
 annual=yahoo_annual(frames,info); errors=[]
 # Keep the provider-native annual block for balance-risk ratios. SEC may
 # subsequently replace the valuation block; never merge these risk sources.
 risk_annual=native_risk_annual(annual,row.get('listing_symbol') or row['ticker'])
 cik=str(row.get('cik') or '').strip(); ua=os.getenv('SEC_USER_AGENT','')
 sec_daten=sec_roh=None
 if cik.isdigit() and ua and ys.find('.')<0:
  try:
   req=urllib.request.Request(f'https://data.sec.gov/api/xbrl/companyfacts/CIK{int(cik):010d}.json',headers={'User-Agent':ua,'Accept':'application/json'})
   with urllib.request.urlopen(req,timeout=12) as response: sec_roh=response.read()
   sec_daten=json.loads(sec_roh); sec=sec_annual(sec_daten,cik)
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
 # Kurshistorie unbereinigt (Schlusskurs und Dividende je Tag) für die Kennzahlen je Aktie (seit 26.11.2026).
 per_share=None
 try:
  # 20 Jahre (seit 27.11.2026, vorher 6) für die SEC-Jahre. Yahoo-Kurse sind split-bereinigt, nicht dividendenbereinigt.
  h=t.history(period='20y',interval='1d',auto_adjust=False,actions=True)
  kurse=[(ix.strftime('%Y-%m-%d'),number(float(r['Close'])),number(float(r.get('Dividends',0) or 0))) for ix,r in h.iterrows()]
  per_share=kennzahlen_jahre(frames,info,kurse)
  if sec_daten is not None:
   import hashlib
   alle_splits=recent_splits(t,years=SEC_PS_MAX_JAHRE+2)
   try:
    sj,sb,grund=sec_jahre_je_aktie(sec_daten,cik,kurse,alle_splits,per_share['jahre'],info,hashlib.sha256(sec_roh).hexdigest(),stamp())
    if sb:per_share['jahre']=sorted(per_share['jahre']+sj,key=lambda x:x['end']);per_share['sec']=sb
    else:per_share['sec_status']=grund
   except Exception:per_share['sec_status']='SEC-Jahre je Aktie: Auswertung fehlgeschlagen'
 except Exception: errors.append('Kurshistorie für Kennzahlen je Aktie nicht verfügbar')
 # Operating-Leasing zum Stichtag des endgültigen Jahresabschlusses aus derselben SEC-Antwort (seit 23.11.2026, operating_lease.py).
 lease=None
 if sec_daten is not None:
  import hashlib
  try: lease=operating_lease(sec_daten,annual,cik,hashlib.sha256(sec_roh).hexdigest(),stamp())
  except (ValueError,TypeError,KeyError): lease=None
 currency=info.get('currency'); observed=info.get('regularMarketTime')
 market={k:number(info.get(v)) for k,v in {'price':'regularMarketPrice','shares_out':'sharesOutstanding','52w_high':'fiftyTwoWeekHigh','52w_low':'fiftyTwoWeekLow','target_mean':'targetMeanPrice','analyst_count':'numberOfAnalystOpinions','beta':'beta','implied_shares_out':'impliedSharesOutstanding'}.items()}
 references={}
 reference_path=os.getenv('FUNDAMENTAL_REFERENCES_PATH')
 if reference_path:
  try: references=json.loads(pathlib.Path(reference_path).read_text(encoding='utf-8'))
  except (OSError,ValueError):pass
 basis_path=pathlib.Path(__file__).parent/'share_basis.json'
 bases=json.loads(basis_path.read_text(encoding='utf-8')) if basis_path.exists() else {}
 return {'risk_annual':risk_annual,'annual_diagnostics':diagnostics,'fx':references.get('fx'),'share_basis':bases.get(row.get('listing_symbol') or row['ticker']) or ordinary_basis(row,annual,currency,f'https://finance.yahoo.com/quote/{ys}/'),'schema':1,'symbol':row.get('listing_symbol') or row['ticker'],'yahoo_symbol':ys,'retrieved_at':stamp(),'latest_fiscal_end':dt.datetime.fromtimestamp(latest,UTC).date().isoformat() if latest else None,'annual':annual,'market':{'currency':currency,'quote_at':dt.datetime.fromtimestamp(observed,UTC).isoformat() if observed else None,'source':'Yahoo Finance','source_url':f'https://finance.yahoo.com/quote/{ys}/','fields':market},'cash_history':yahoo_cash_history(frames,info),'estimates':consensus_estimates(estimate_table(t),info,ys),'analysts':analyst_recommendations(recommendation_rows(t),ys),'surprises':earnings_surprises(earnings_history_table(t),ys),'splits':recent_splits(t),'operating_lease':lease,'per_share':per_share,'issues':errors}
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
 index.setdefault('annualSupply',{})
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
   data=per_share_archivieren(data,old)
   index['annualSupply'][symbol]={**annual_supply_status(data,time.time()),'checkedAt':stamp()}
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
