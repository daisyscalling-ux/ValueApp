"""Adapter only: calculations remain in the unchanged user-supplied valuation.py."""
import json, math
from datetime import date
import valuation as v

SECTORS = {'Technology services':'Technology','Electronic technology':'Technology','Communications':'Communication Services','Finance':'Financial Services','Energy minerals':'Energy','Non-energy minerals':'Basic Materials','Health technology':'Healthcare','Health services':'Healthcare','Consumer non-durables':'Consumer Defensive','Consumer durables':'Consumer Cyclical','Consumer services':'Consumer Cyclical','Producer manufacturing':'Industrials','Industrial services':'Industrials','Transportation':'Industrials','Process industries':'Basic Materials','Utilities':'Utilities'}
def ratio(a,b):
    return a/b if a is not None and b is not None and b != 0 else None

def mapped(stock):
    rows=stock.get('financials') or []
    f=rows[0] if rows else {}
    previous=None
    for p in (stock.get('ttmFinancials') or [])+rows[1:]:
        if p.get('currency') != f.get('currency'): continue
        try: gap=(date.fromisoformat(f['date'])-date.fromisoformat(p['date'])).days
        except (KeyError,ValueError): continue
        if abs(gap-365)<20 and (p.get('periodType')==f.get('periodType') or p.get('periodType')=='annual' and f.get('periodLabel')=='Q4'):
            previous=p;break
    previous=previous or {}
    def growth(field):
        a,b=f.get(field),previous.get(field)
        return a/b-1 if a is not None and b is not None and b>0 else None
    shares=f.get('shares'); price=stock.get('price')
    cap=price*shares if price is not None and shares is not None else None
    debt,cash=f.get('debt'),f.get('cash')
    nd=debt-cash if debt is not None and cash is not None else None
    ev=cap+nd if cap is not None and nd is not None else None
    fund={'ticker':stock.get('symbol'),'sector':SECTORS.get(stock.get('sector'),stock.get('sector')),'industry':stock.get('industry'),
      'price':price,'shares_out':shares,'market_cap':cap,'total_debt':debt,'net_debt':nd,'cash':cash,
      'ebitda':f.get('ebitda'),'revenue':f.get('revenue'),'net_income':f.get('netIncome'),
      'eps_trailing':f.get('eps'),'eps_forward':None,'book_value_ps':ratio(f.get('equity'),shares),
      'roe':ratio(f.get('netIncome'),f.get('equity')),'operating_margin':ratio(f.get('operatingMargin'),100),'gross_margin':ratio(f.get('grossMargin'),100),
      'current_ratio':f.get('currentRatio'),'net_debt_ebitda':ratio(nd,f.get('ebitda')),'ev_ebitda':ratio(ev,f.get('ebitda')),
      'free_cashflow':f.get('fcf'),'operating_cashflow':f.get('operatingCashFlow'),'beta':None,
      'revenue_growth':growth('revenue'),'earnings_growth':growth('netIncome'),'eps_growth':growth('eps'),
      'target_mean':(stock.get('analystTarget') or {}).get('mean'),'total_assets':f.get('totalAssets')}
    annual=[p for p in rows if p.get('periodType') in (None,'annual') and p.get('currency')==f.get('currency')]
    margins=[ratio(p.get('netIncome'),p.get('revenue')) for p in annual]
    zd=v.zyklisch_aus_margen(margins,ratio(f.get('netIncome'),f.get('revenue')))
    fund['_ist_zyklisch']=zd['zyklisch'];fund['_zyklus_diagnose']=zd
    conversion=v.conversion_aus_historie([p.get('fcf') for p in annual],[p.get('netIncome') for p in annual])
    if conversion:fund['cash_conversion']=conversion['median']
    return fund,annual

def forward_view(stock, fund, preset, blocked):
    if blocked:
        return {'target': None, 'bands': [], 'reason': 'Aktiengattung, Splitprüfung oder Währung nicht bestätigt.'}
    target = v.kursziel_12m(dict(fund), preset)
    price = fund.get('price')
    if not price or price <= 0:
        return {'target': target, 'bands': [], 'reason': 'Kein gültiger Kurs.'}
    history = {}
    for row in stock.get('history') or []:
        close = row.get('close')
        if isinstance(close, (float, int)) and math.isfinite(close) and close > 0:
            try: history[date.fromisoformat(row['date'])] = close
            except (ValueError, KeyError): pass
    ordered = sorted(history.items())[-253:]
    returns = [math.log(b[1]/a[1]) for a,b in zip(ordered,ordered[1:]) if 0 < (b[0]-a[0]).days <= 5]
    try: fresh = bool(ordered) and 0 <= (date.fromisoformat(stock['priceDate'])-ordered[-1][0]).days <= 10
    except (ValueError, KeyError): fresh = False
    if len(returns) < 60 or not fresh:
        return {'target': target, 'bands': [], 'reason': 'Mindestens 60 aktuelle Tagesrenditen aus splitbereinigten Kursen benötigt.'}
    mean = sum(returns)/len(returns)
    sigma = math.sqrt(sum((x-mean)**2 for x in returns)/(len(returns)-1)*252)
    anchor = target['ziel'] if target else price
    points = [{'month': 0, 'center': price, 'low': price, 'high': price}]
    for month in (1,3,6):
        t = month/12
        center = price * (anchor/price)**t
        spread = sigma*math.sqrt(t)
        points.append({'month': month, 'center': center, 'low': center*math.exp(-spread), 'high': center*math.exp(spread)})
    return {'target': target, 'bands': points, 'volatility': sigma*100, 'observations': len(returns), 'reason': 'Logarithmische Fortschreibung zum EPS/KGV-Ziel; ohne Ziel seitwärts. Band: historische Jahresvolatilität × Wurzel der Zeit. Keine kalibrierte Trefferwahrscheinlichkeit.'}

def calculate(stock):
    fund,annual=mapped(stock)
    preset=v.classify_playbook(fund)
    result=v.fair_value(dict(fund),preset=preset)
    result['playbook']=preset
    result['engine_version']=v.__version__
    result['input']=fund
    result['all_methods']={k:fn(fund,preset) for k,fn in {'justified_pe':v.justified_pe,'dcf':v.dcf_two_stage,'pb':v.multiple_pb,'epv':v.epv,'fwd_pe':v.fwd_pe,'fwd_composite':v.fwd_composite,'hist_pe':v.hist_pe}.items()}
    result['all_methods']['ev_ebitda']=v.multiple_ev_ebitda(fund,None,preset)
    result['all_methods']['analyst']=v.analyst_target(fund)
    result['weights']=v._WEIGHTS[preset]
    result['reverse']=v.reverse_dcf_analyse(fund,v.anker_aus_fund(fund,historie=[{'jahr':p['year'],'revenue':p.get('revenue')} for p in annual]),preset)
    result['adapter_notes']=['Keine Forward-EPS, kein Beta und keine historischen KGV im bisherigen Datenmodell: Originalskript verwendet seine Rückfälle.','Keine Peer-Daten übergeben: Sektortabelle aus config.py wird verwendet.','Geprüfter FCF als Eingabe; unbestätigter ROIC-FCF wird nicht als geprüfter Cashflow umgedeutet.','Das Originalskript zieht Minderheiten und Vorzugskapital nicht zusätzlich ab. Kursbezogene Filter und Deckel sind unverändert aktiv.']
    result['blocked']=not(stock.get('isPrimary') and not stock.get('valuationBlocked') and stock.get('currency')==(stock.get('financials') or [{}])[0].get('currency'))
    result['forward_view']=forward_view(stock,fund,preset,result['blocked'])
    return result

def run_payload(payload):
    return json.dumps(calculate(json.loads(payload)),ensure_ascii=False,allow_nan=False)

if __name__=='__main__':
    import sys
    print(run_payload(sys.stdin.read()))

