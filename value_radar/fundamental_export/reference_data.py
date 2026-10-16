"""Bounded public reference data; no inferred share ratios or FX prices."""
import datetime as dt,json,math,urllib.request,xml.etree.ElementTree as ET
ECB='https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml'
def parse_ecb(xml,today=None):
 today=today or dt.datetime.now(dt.timezone.utc).date()
 root=ET.fromstring(xml); dated=[e for e in root.iter() if 'time' in e.attrib]
 if len(dated)!=1: raise ValueError('ambiguous FX date')
 day=dt.date.fromisoformat(dated[0].attrib['time'])
 if not 0<=(today-day).days<=7: raise ValueError('stale or future FX')
 rates={'EUR':1.0}
 for e in dated[0]:
  currency=e.attrib.get('currency'); rate=float(e.attrib.get('rate','nan'))
  if not currency or len(currency)!=3 or not math.isfinite(rate) or rate<=0: raise ValueError('invalid FX rate')
  if currency in rates: raise ValueError('duplicate FX currency')
  rates[currency]=rate
 if len(rates)<2: raise ValueError('empty FX data')
 return {'base':'EUR','observed_at':day.isoformat(),'source':'ECB reference rates','source_url':ECB,'rates':rates}
def fetch_ecb():
 with urllib.request.urlopen(ECB,timeout=12) as response:return parse_ecb(response.read())
def sec_listing_map(data):
 fields=data.get('fields',[]); records={}; ambiguous=set()
 for values in data.get('data',[]):
  row=dict(zip(fields,values));symbol=str(row.get('ticker','')).upper();exchange=str(row.get('exchange','')).upper()
  exchange={'NASDAQ':'NASDAQ','NYSE':'NYSE','NYSE AMERICAN':'AMEX','AMEX':'AMEX'}.get(exchange)
  cik=str(row.get('cik',''))
  if not exchange or not symbol or not cik.isdigit():continue
  key=exchange+':'+symbol
  if key in records and records[key]!=cik:ambiguous.add(key)
  records[key]=cik
 return {k:v for k,v in records.items() if k not in ambiguous}
def fetch_sec_listings(user_agent):
 request=urllib.request.Request('https://www.sec.gov/files/company_tickers_exchange.json',headers={'User-Agent':user_agent,'Accept':'application/json'})
 with urllib.request.urlopen(request,timeout=12) as response:return sec_listing_map(json.load(response))

