"""Fixed ex-ante technical sample. No selection by subsequent stock performance."""
import contextlib
import datetime as dt
import json
import os
from pathlib import Path
import re
import sys
import time
from pilot import Client, filing_index

# Banks excluded: debt/cash ratios have a different economic meaning there.
SAMPLE = {
 'MSFT':('0000789019','technology'), 'ORCL':('0001341439','technology'),
 'ADBE':('0000796343','technology'), 'CRM':('0001108524','technology'),
 'XOM':('0000034088','energy'), 'CVX':('0000093410','energy'),
 'COP':('0001163165','energy'), 'EOG':('0000821189','energy'),
 'JNJ':('0000200406','health'), 'MRK':('0000310158','health'),
 'PFE':('0000078003','health'), 'UNH':('0000731766','health'),
 'CAT':('0000018230','industrial'), 'DE':('0000315189','industrial'),
 'HON':('0000773840','industrial'), 'GE':('0000040545','industrial'),
 'WMT':('0000104169','consumer'), 'COST':('0000909832','consumer'),
 'KO':('0000021344','consumer'), 'PEP':('0000077476','consumer')}

def run():
 import yfinance as yf
 out=Path('sec-study-output');out.mkdir(exist_ok=True)
 ua=os.environ.get('SEC_USER_AGENT','')
 if not re.search(r'[^\s@]+@[^\s@]+\.[^\s@]+',ua):
  raise RuntimeError('SEC_USER_AGENT missing; never print its value')
 now=dt.datetime.now(dt.timezone.utc);client=Client(ua,out)
 companies={};histories={};errors={}
 for symbol,(cik,sector) in SAMPLE.items():
  try:
   sub=client.get('/submissions/CIK'+cik+'.json')
   facts=client.get('/api/xbrl/companyfacts/CIK'+cik+'.json')
   if int(sub['cik'])!=int(cik) or int(facts['cik'])!=int(cik) or symbol not in sub.get('tickers',[]):
    raise ValueError('SEC issuer identity mismatch')
   blocks=[sub['filings']['recent']];archives=sub['filings'].get('files',[])
   if len(archives)>30:raise ValueError('Too many archives')
   for a in archives:
    if not re.fullmatch('CIK'+cik+r'-submissions-\d+\.json',a['name']):raise ValueError('Invalid archive')
    blocks.append(client.get('/submissions/'+a['name']))
   companies[symbol]={'cik':cik,'sector':sector,'filings':filing_index(blocks),'facts_file':'api_xbrl_companyfacts_CIK'+cik+'.json'}
   t=yf.Ticker(symbol)
   with contextlib.redirect_stdout(sys.stderr):
    f=t.history(start=(now-dt.timedelta(days=5*365)).date().isoformat(),end=now.date().isoformat(),auto_adjust=False,repair=False,timeout=15,raise_errors=True)
    m=t.get_history_metadata()
   if m.get('symbol')!=symbol or m.get('instrumentType')!='EQUITY' or m.get('currency')!='USD' or 'Adj Close' not in f:raise ValueError('Yahoo identity or adjustment missing')
   histories[symbol]={'symbol':symbol,'adjustment':'total_return','retrievedAt':now.isoformat(),'bars':[{'date':i.date().isoformat(),'close':float(v)} for i,v in f['Adj Close'].items()]}
  except Exception as exc:
   errors[symbol]=str(exc) if isinstance(exc,(ValueError,RuntimeError)) else type(exc).__name__
  (out/'collection.json').write_text(json.dumps({'generated_at':now.isoformat(),'sample':SAMPLE,'companies':companies,'errors':errors,'downloads':client.manifest}),encoding='utf8')
  (out/'histories.json').write_text(json.dumps({'histories':histories},allow_nan=False),encoding='utf8')
  print(symbol,'SEC' if symbol in companies else 'no SEC','prices' if symbol in histories else 'no prices',flush=True)
  time.sleep(.6)
 if not histories:raise RuntimeError('No histories; inspect collection.json')

if __name__=='__main__':run()
