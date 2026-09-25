"""ROIC -> Quantum peer store. Standard library only; no ValueApp side effects."""
import json, math, os, time, urllib.request, urllib.parse, urllib.error
from datetime import date, datetime, timezone

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise RuntimeError('Redirect refused')

class StopRun(Exception):
    pass

class ProviderDenied(StopRun):
    pass

class Client:
    def __init__(self, key, endpoint, token, budget=30):
        url=urllib.parse.urlsplit(endpoint)
        if url.scheme!='https' or not url.netloc or url.username or url.password or url.query or url.fragment:
            raise ValueError('QUANTUM_URL must be an HTTPS origin')
        self.endpoint=endpoint.rstrip('/')+'/api/peer-sync'
        self.key,self.token=key,token
        self.end=time.monotonic()+budget*60
        self.last=0
        self.opener=urllib.request.build_opener(NoRedirect())
    def request(self,url,token,data=None):
        if time.monotonic()>self.end-30: raise StopRun('Save reserve reached')
        req=urllib.request.Request(url,data=json.dumps(data,allow_nan=False).encode() if data is not None else None,headers={'Authorization':'Bearer '+token,'Accept':'application/json','Content-Type':'application/json'})
        with self.opener.open(req,timeout=min(20,max(1,self.end-time.monotonic()-25))) as response:
            return json.loads(response.read(4_000_001).decode())
    def roic(self,path):
        url=urllib.parse.urljoin('https://api.roic.ai',path)
        parsed=urllib.parse.urlsplit(url)
        if parsed.netloc!='api.roic.ai' or not parsed.path.startswith('/v3.0.0/') or parsed.username or parsed.password:
            raise ValueError('Invalid ROIC cursor')
        # <= 240 requests/minute; reserve remains for interactive use and cron.
        time.sleep(max(0,.26-(time.monotonic()-self.last)))
        self.last=time.monotonic()
        try:return self.request(url,self.key)
        except urllib.error.HTTPError as e:
            if e.code in (401,403,429):raise ProviderDenied('Provider denied access or rate limit') from None
            raise
    def optional(self,path):
        try:return self.roic(path)
        except StopRun:raise
        except Exception:return None
    def read(self):return self.request(self.endpoint,self.token).get('checkpoint')
    def save(self,state,fact=None):return self.request(self.endpoint,self.token,{'checkpoint':state,'facts':[fact] if fact else []})

def num(n):return float(n) if isinstance(n,(int,float)) and not isinstance(n,bool) and math.isfinite(n) else None
def ratio(a,b,k=1):return a/b*k if a is not None and b is not None and b>0 else None
def rows(data):return data.get('data',[]) if isinstance(data,dict) and isinstance(data.get('data'),list) else []
def first(*args):return next((x for x in args if x is not None),None)
def matched(data,inc):
    return next((r for r in rows(data) if r.get('period_type')=='ttm' and r.get('period_end_date')==inc.get('period_end_date') and r.get('currency')==inc.get('currency') and r.get('symbol',inc.get('symbol'))==inc.get('symbol')), {})

def metrics(inc,b,c,r,quote=None,splits=None):
    def n(row,key):return num(row.get(key))
    revenue=n(inc,'is_sales_revenue_turnover');ebitda=n(inc,'ebitda')
    capex=first(n(c,'cf_cap_expenditures'),n(c,'cf_acquis_fxd_and_intang_detailed'))
    fixed,intangible=n(c,'cf_purchase_of_fixed_prod_assets'),n(c,'cf_acquisition_of_intang_assets')
    if capex is None and fixed is not None and intangible is not None and fixed<=0 and intangible<=0:capex=fixed+intangible
    op=n(c,'cf_cash_from_oper');fcf=op+capex if op is not None and capex is not None and capex<=0 else None
    reported=n(c,'cf_free_cash_flow')
    if fcf is not None and reported is not None and abs(fcf-reported)>max(1,abs(op)*.01):fcf=None
    short,long,cash=n(b,'bs_st_borrow'),n(b,'bs_lt_borrow'),n(b,'bs_cash_near_cash_item')
    debt=short+long-cash if all(v is not None for v in [short,long,cash]) else None
    quote=quote or {};price=n(quote,'close') if quote.get('currency')==inc.get('currency') and splits is not None and not rows(splits) else None
    return {'grossMargin':first(n(inc,'gross_margin'),n(r,'gross_margin')),'operatingMargin':first(n(inc,'oper_margin'),n(r,'oper_margin')),'netMargin':first(n(inc,'profit_margin'),n(r,'profit_margin'),ratio(n(inc,'is_net_income'),revenue,100)),'ebitdaMargin':ratio(ebitda,revenue,100),'fcfMargin':ratio(fcf,revenue,100),'roic':n(r,'return_on_inv_capital'),'currentRatio':first(n(b,'cur_ratio'),ratio(n(b,'bs_cur_asset_report'),n(b,'bs_cur_liab'))),'leverage':ratio(debt,ebitda),'pe':ratio(price,n(inc,'diluted_eps'))}

def collect(client,ticker):
    if ticker.get('is_primary') is not True or ticker.get('type')!='stock' or ticker.get('type_specifications') and 'common' not in ticker['type_specifications']:return None
    identifier=urllib.parse.quote(ticker['id'],safe='');period='?period_type=ttm&order=desc&limit=1'
    profile=client.roic('/v3.0.0/company/profile/'+identifier)
    income=rows(client.roic('/v3.0.0/fundamental/income-statement/'+identifier+period))
    inc=next((r for r in income if r.get('period_type')=='ttm'),None)
    if not inc or not profile.get('sector'):return None
    report=date.fromisoformat(inc['period_end_date'])
    if not 0<=(datetime.now(timezone.utc).date()-report).days<=550:return None
    balance=matched(client.optional('/v3.0.0/fundamental/balance-sheet/'+identifier+period),inc)
    cash=matched(client.optional('/v3.0.0/fundamental/cash-flow/'+identifier+period),inc)
    ratios=matched(client.optional('/v3.0.0/fundamental/ratios/profitability/'+identifier+period),inc)
    quote=client.optional('/v3.0.0/stock-prices/latest/'+identifier)
    splits=client.optional('/v3.0.0/stock-splits?identifier='+identifier+'&date.gt='+inc['period_end_date']+'&limit=100')
    values=metrics(inc,balance,cash,ratios,quote,splits)
    if all(n is None for n in values.values()):return None
    return {'id':ticker['id'],'industry':profile.get('industry') or '', 'sector':profile['sector'],'period':'ttm','date':inc['period_end_date'],'updatedAt':int(time.time()*1000),'metrics':values}

def run():
    client=Client(os.environ['ROIC_API_KEY'],os.environ['QUANTUM_URL'],os.environ['QUANTUM_SYNC_TOKEN'],min(35,max(2,float(os.getenv('QUANTUM_BUDGET_MIN','30')))))
    state=client.read() or {'cursor':None,'remaining':[],'complete':False}
    if state.get('complete') and not state.get('remaining'):state={'cursor':None,'remaining':[],'complete':False}
    processed=saved=failed=0
    limit=min(1000,max(1,int(os.getenv('QUANTUM_MAX_COMPANIES','250'))))
    try:
        while processed<limit and time.monotonic()<client.end-60:
            if not state.get('remaining'):
                if state.get('complete'):break
                page=client.roic(state.get('cursor') or '/v3.0.0/tickers?type=stock&is_primary=true&status=listed&limit=50')
                next_page=page.get('next_page_url')
                if next_page and next_page==state.get('cursor'):raise StopRun('Repeated catalogue cursor')
                state={'cursor':next_page,'remaining':[{k:t[k] for k in ('id','is_primary','type','type_specifications') if k in t} for t in rows(page) if isinstance(t.get('id'),str)],'complete':not bool(next_page)}
                client.save(state)
                if not state['remaining']:break
            ticker=state['remaining'][0]
            try:fact=collect(client,ticker)
            except StopRun:raise
            except Exception:fact=None;failed+=1
            next_state={**state,'remaining':state['remaining'][1:]}
            # Only advance the checkpoint after the server atomically saved this result.
            client.save(next_state,fact)
            state=next_state;processed+=1;saved+=int(fact is not None)
            if processed%25==0:print(f'Quantum: {processed} processed, {saved} saved, {failed} failed',flush=True)
    except ProviderDenied as e:raise SystemExit(str(e)) from None
    except StopRun as e:print('Quantum paused:',str(e),flush=True)
    print(f'Quantum result: {processed} processed, {saved} saved, {failed} failed; checkpoint persisted',flush=True)
    if failed and not saved:raise SystemExit('No usable data received; last valid database values retained')

if __name__=='__main__':run()
