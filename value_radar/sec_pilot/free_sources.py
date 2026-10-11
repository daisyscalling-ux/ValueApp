"""Free-source research export. Never claims verified permanent security identity."""
import concurrent.futures as futures
import csv
import datetime as dt
import hashlib
import io
import json
import math
from pathlib import Path
import re
import time
import urllib.request

CURRENT='https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
HISTORY='https://en.wikipedia.org/wiki/Historical_components_of_the_S%26P_500'
START='2014-01-01'

def clean(x):
    import pandas as pd
    return '' if pd.isna(x) else re.sub(r'\[\d+\]','',str(x)).strip()

def research_id(symbol):
    return 'UNVERIFIED_'+hashlib.sha256(symbol.encode()).hexdigest()[:16]

def reconstruct(current,events,start,asof):
    """Reverse recorded changes; all intervals remain provisional and left-censored."""
    ends={s:asof for s in current}; intervals=[];issues=[]
    for event in sorted(events,key=lambda r:r['date'],reverse=True):
        day=event['date']
        if not start<=day<asof:continue
        added,removed=event['added'],event['removed']
        if added:
            end=ends.pop(added,None)
            if end is None:issues.append({'date':day,'symbol':added,'issue':'addition not present in later reconstruction'})
            elif day<end:intervals.append({'symbol':added,'start':day,'end':end,'left_censored':False})
        if removed:
            if removed in ends:issues.append({'date':day,'symbol':removed,'issue':'removal already present in later reconstruction'})
            else:ends[removed]=day
    for symbol,end in ends.items():
        if start<end:intervals.append({'symbol':symbol,'start':start,'end':end,'left_censored':True})
    return intervals,issues

def write_csv(path,rows,fields):
    with path.open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(rows)

def fetch_html(url,path):
    req=urllib.request.Request(url,headers={'User-Agent':'ValueAppResearch/1.0 (historical financial data research)'})
    with urllib.request.urlopen(req,timeout=30) as response:raw=response.read(8_000_001)
    if len(raw)>8_000_000:raise ValueError('Wikipedia response too large')
    path.write_bytes(raw)
    return raw.decode('utf8'),hashlib.sha256(raw).hexdigest()

def load_wikipedia(out,asof):
    import pandas as pd
    html,h1=fetch_html(CURRENT,out/'wikipedia-current.html')
    history,h2=fetch_html(HISTORY,out/'wikipedia-history.html')
    tables=pd.read_html(io.StringIO(html),keep_default_na=False)
    table=next(t for t in tables if 'Symbol' in t.columns and 'Security' in t.columns)
    current={clean(r['Symbol']):{'company':clean(r['Security']),'cik':clean(r.get('CIK','')).zfill(10),'sector':clean(r.get('GICS Sector',''))} for _,r in table.iterrows()}
    histories=pd.read_html(io.StringIO(history),keep_default_na=False)
    changes=next(t for t in histories if any('Added' in str(c) for c in t.columns) and any('Removed' in str(c) for c in t.columns))
    events=[];unparsed=[]
    for _,r in changes.iterrows():
        values=[clean(x) for x in r.tolist()]
        try:day=pd.to_datetime(values[0],errors='raise').date().isoformat()
        except (ValueError,TypeError):unparsed.append(values);continue
        if day<START or day>=asof:continue
        added,removed=values[1],values[3]
        if any(s and not re.fullmatch(r'[A-Z0-9.\-]{1,15}',s) for s in [added,removed]):unparsed.append(values);continue
        events.append({'date':day,'added':added,'added_name':values[2],'removed':removed,'removed_name':values[4],'reason':values[5] if len(values)>5 else '', 'source':HISTORY})
    if not 450<=len(current)<=550 or len(events)<50:raise ValueError('Unexpected Wikipedia table coverage')
    return current,events,{'current_sha256':h1,'history_sha256':h2,'unparsed_changes':unparsed}

def quotes(symbol,out,end):
    import yfinance as yf
    yahoo=symbol.replace('.','-');sid=research_id(symbol)
    result={'Research_ID':sid,'Symbol':symbol,'Yahoo_Symbol':yahoo,'Status':'unavailable','rows':0,'return_rows':0,'Identitaet':'unverified_historical_security'}
    try:
        t=yf.Ticker(yahoo)
        frame=t.history(start=START,end=end,auto_adjust=False,repair=False,actions=True,timeout=12,raise_errors=True)
        if frame.empty or 'Adj Close' not in frame:raise ValueError('empty or no adjusted close')
        metadata=t.get_history_metadata()
        if metadata.get('symbol')!=yahoo or metadata.get('instrumentType')!='EQUITY' or metadata.get('currency')!='USD':raise ValueError('symbol, instrument or currency mismatch')
        result['Yahoo_Name']=metadata.get('longName') or metadata.get('shortName') or ''
        source='https://finance.yahoo.com/quote/'+yahoo+'/history/'
        rows=[];previous=None
        for index,row in frame.iterrows():
            day=index.date().isoformat();adj=float(row['Adj Close'])
            if not math.isfinite(adj) or adj<=0:previous=None;continue
            if rows and day<=rows[-1]['Datum']:raise ValueError('non-increasing dates')
            ret=None
            if previous and (index.date()-previous[0]).days<=7:ret=adj/previous[1]-1
            values={'Research_ID':sid,'Symbol':symbol,'Datum':day,'Adjusted_Close':adj,'Tagesrendite':ret,'Quelle':source,
                    'Identitaet':'unverified_historical_security','Abwicklung_bestaetigt':False}
            for col,name in [('Close','Schlusskurs'),('Dividends','Dividende'),('Stock Splits','Split')]:
                value=float(row.get(col,float('nan')));values[name]=value if math.isfinite(value) else None
            rows.append(values);previous=(index.date(),adj)
        if not rows:raise ValueError('no finite prices')
        write_csv(out/'prices'/f'{sid}.csv',rows,list(rows[0]))
        result.update(Status='prices_available_identity_unverified',rows=len(rows),return_rows=sum(r['Tagesrendite'] is not None for r in rows),first=rows[0]['Datum'],last=rows[-1]['Datum'])
    except Exception as exc:result['Fehlerklasse']=type(exc).__name__
    return result

def run():
    out=Path('free-source-output');out.mkdir(exist_ok=True);(out/'prices').mkdir(exist_ok=True)
    now=dt.datetime.now(dt.timezone.utc);end=now.date().isoformat()
    current,events,source_audit=load_wikipedia(out,end)
    intervals,issues=reconstruct(current,events,START,end)
    symbols=sorted(set(current)|{s for r in events for s in (r['added'],r['removed']) if s})
    members=[dict(Research_ID=research_id(r['symbol']),Symbol=r['symbol'],Eintrittsdatum=r['start'],Austrittsdatum=r['end'],Links_abgeschnitten=r['left_censored'],Status='provisional_wikipedia_reconstruction',Quelle=HISTORY) for r in intervals]
    write_csv(out/'sp500_historische_mitglieder_vorlaeufig.csv',members,['Research_ID','Symbol','Eintrittsdatum','Austrittsdatum','Links_abgeschnitten','Status','Quelle'])
    write_csv(out/'indexaenderungen.csv',events,['date','added','added_name','removed','removed_name','reason','source'])
    names={s:set() for s in symbols}
    for s,r in current.items():names[s].add(r['company'])
    for r in events:
        for side in ['added','removed']:
            if r[side]:names[r[side]].add(r[side+'_name'])
    master=[{'Research_ID':research_id(s),'Symbol':s,'Namenshinweise':' | '.join(sorted(names[s])),'CIK_aktuelle_Liste':current.get(s,{}).get('cik',''),'Heute_gelistet_im_Index':s in current,'Identitaet':'unverified_historical_security','Quelle':CURRENT+' ; '+HISTORY} for s in symbols]
    write_csv(out/'wertpapier_kandidaten.csv',master,list(master[0]))
    report={'generated_at':now.isoformat(),'requested_start':START,'requested_end_exclusive':end,'current_members':len(current),'recorded_changes':len(events),'candidate_symbols':len(symbols),'provisional_intervals':len(intervals),'reconstruction_issues':issues,'sources':source_audit,'complete_historical_universe_verified':False,'downloads':[]}
    def save():
        report['symbols_with_prices']=sum(x['rows']>0 for x in report['downloads'])
        report['total_price_rows']=sum(x['rows'] for x in report['downloads'])
        (out/'coverage.json').write_text(json.dumps(report,indent=2,allow_nan=False),encoding='utf8')
    save()
    # Two workers: bounded load, one history request per candidate, no identity substitution.
    with futures.ThreadPoolExecutor(max_workers=2) as pool:
        pending={pool.submit(quotes,s,out,end):s for s in symbols}
        for future in futures.as_completed(pending):
            report['downloads'].append(future.result());save()
            if len(report['downloads'])%50==0:print('Processed',len(report['downloads']),'of',len(symbols),flush=True)
    write_csv(out/'datenabdeckung.csv',sorted(report['downloads'],key=lambda r:r['Symbol']),['Research_ID','Symbol','Yahoo_Symbol','Status','Identitaet','Yahoo_Name','rows','return_rows','first','last','Fehlerklasse'])
    (out/'README.txt').write_text('''Forschungsdaten aus kostenlosen Quellen, kein verifizierter historischer S&P-500-Backtest.
Wikipedia-Seiten und Pruefsummen liegen bei; Wikipedia CC BY-SA, Herkunft und Aenderungen beachten.
Die Mitgliederintervalle sind aus aktueller Liste und aufgezeichneten Aenderungen rueckwaerts rekonstruiert.
Das Startdatum 2014-01-01 kann eine abgeschnittene Beobachtungsgrenze statt des echten Eintritts bedeuten.
Research_ID ist nur ein symbolbasierter Arbeitsschluessel, KEINE bestaetigte dauerhafte Wertpapierkennung.
Aktuelle CIKs duerfen nicht pauschal auf alte Emittenten desselben Kuerzels uebertragen werden.
Yahoo-Kurse koennen bei alten Kuerzeln zu anderen Firmen gehoeren. Historische Identitaet bleibt ungeprueft.
Tagesrenditen = AdjClose(t)/AdjClose(t-1)-1, als Dezimalzahlen. Dividenden nicht nochmals addieren.
Bei Abstand ueber sieben Kalendertagen keine Renditebruecke. Keine Nullauffuellung fehlender Werte.
Yahoo-Bereinigungen sind Anbieterwerte, keine verifizierten Abwicklungsrenditen.
Indexausschluss ist kein Delisting. Hier werden KEINE Delisting-Erloese erfunden.
Kein vollstaendiger Boersenkalender oder unabhaengiger Quellenabgleich. Kein automatischer Score-Import.
Nutzung und Weitergabe gemaess Bedingungen der Quellen; kostenlose Abrufbarkeit ist keine freie Datenlizenz.
''',encoding='utf8')
    print(json.dumps({k:report[k] for k in ['current_members','candidate_symbols','provisional_intervals','symbols_with_prices','total_price_rows']}),flush=True)

if __name__=='__main__':run()
