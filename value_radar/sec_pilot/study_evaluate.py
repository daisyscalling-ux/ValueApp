"""Exploratory matched-sample holdout test, annual financials only, no tuning."""
import datetime as dt
import hashlib
import json
from pathlib import Path
import numpy as np
from point_in_time import select_annual

SPLIT='2025-01-01'

def financial_features(facts,filings,cutoff):
 selection=select_annual(facts,filings,dt.date.fromisoformat(cutoff))
 r=selection['latest_annual']
 if not r or r['status']!='selected':return None,'no unambiguous annual filing'
 if (dt.date.fromisoformat(cutoff)-dt.date.fromisoformat(r['end'])).days>550:return None,'annual period older than 550 days'
 # Do not claim a clean snapshot after an unprocessed amendment of this period.
 for f in filings.values():
  if f.get('form')=='10-K/A' and r['filed']<=f.get('filingDate','')<cutoff and f.get('reportDate')==r['end'] and f.get('accessionNumber')!=r['accession']:
   return None,'unreconciled annual amendment'
 fields=r['fields'];assets=fields['assets']['value'];liabilities=fields['liabilities']['value'];liability_source='Liabilities'
 if assets is None or assets<=0:return None,'assets missing or nonpositive'
 equity=fields['equity_including_minority']['value']
 if liabilities is None and fields['liabilities']['status']=='missing' and equity is not None:
  liabilities=assets-equity;liability_source='Assets minus equity including minority'
 if liabilities is not None and equity is not None and abs(assets-liabilities-equity)>max(1,abs(assets)*.001):return None,'balance sheet does not reconcile'
 net_debt=r['net_debt'];fcf=r['cfo_minus_capex']
 return {'filing':r['accession'],'filed':r['filed'],'period_end':r['end'],
         'liabilities_assets':liabilities/assets if liabilities is not None and liabilities>=0 else None,
         'net_debt_assets':net_debt/assets if net_debt is not None else None,
         'negative_fcf_assets':-fcf/assets if fcf is not None else None,
         'liability_source':liability_source,'annual':True},None

def ridge_predict(train,test,features):
 x=np.array([[r[k] for k in features] for r in train],dtype=float)
 z=np.array([[r[k] for k in features] for r in test],dtype=float)
 y=np.array([r['loss'] for r in train])
 mean=x.mean(axis=0);sd=x.std(axis=0);sd[sd<1e-12]=1
 x=(x-mean)/sd;z=(z-mean)/sd
 # Fixed ridge strength; centering and scaling use only earlier observations.
 w=np.linalg.solve(x.T@x+np.eye(len(features)),x.T@(y-y.mean()))
 return z@w+y.mean()

def compare(rows,finance,baseline):
 keys=[baseline]+finance
 complete=[r for r in rows if all(isinstance(r.get(k),(int,float)) and np.isfinite(r[k]) for k in keys)]
 train=[r for r in complete if r['end']<SPLIT]
 test=[r for r in complete if r['date']>=SPLIT]
 result={'earlier_windows':len(train),'later_windows':len(test),'earlier_companies':len({r['symbol'] for r in train}),'later_companies':len({r['symbol'] for r in test})}
 if len(train)<32 or len(test)<16 or min(result['earlier_companies'],result['later_companies'])<8:
  return dict(result,status='insufficient_data')
 base=ridge_predict(train,test,[baseline]);aug=ridge_predict(train,test,keys);y=np.array([r['loss'] for r in test])
 squared_base=(base-y)**2;squared_aug=(aug-y)**2
 groups={}
 for sector in sorted({r['sector'] for r in test}):
  idx=[i for i,r in enumerate(test) if r['sector']==sector]
  groups[sector]={'n':len(idx),'mse_baseline':float(squared_base[idx].mean()),'mse_with_financials':float(squared_aug[idx].mean())}
 return dict(result,status='exploratory',mse_baseline=float(squared_base.mean()),mse_with_financials=float(squared_aug.mean()),
             mse_improvement=float(squared_base.mean()-squared_aug.mean()),sectors=groups,
             interpretation='Positive improvement means lower squared error in this sample, not proven general benefit.')

def run(folder='sec-study-output'):
 out=Path(folder);collection=json.loads((out/'collection.json').read_text());prices=json.loads((out/'price-observations.json').read_text())
 for d in collection['downloads']:
  if hashlib.sha256((out/d['file']).read_bytes()).hexdigest()!=d['sha256']:raise ValueError('SEC checksum mismatch')
 rows=[];coverage={}
 for symbol,company in collection['companies'].items():
  facts=json.loads((out/company['facts_file']).read_text());memo={};issues={}
  for o in prices.get(symbol,[]):
   if o['date'] not in memo:memo[o['date']]=financial_features(facts,company['filings'],o['date'])
   f,error=memo[o['date']]
   if error:issues[error]=issues.get(error,0)+1
   rows.append(dict(o,symbol=symbol,sector=company['sector'],**(f or {})))
  coverage[symbol]={'price_windows':len(prices.get(symbol,[])),'finance_dates':sum(f is not None for f,e in memo.values()),'excluded_windows':issues}
 tests=[]
 for horizon in [1,3,6]:
  sample=[r for r in rows if r['horizon']==horizon]
  for finance in [['negative_fcf_assets'],['liabilities_assets'],['net_debt_assets'],['liabilities_assets','negative_fcf_assets']]:
   for baseline in ['volatility','score']:
    tests.append(dict(horizon=horizon,financial_features=finance,baseline=baseline,**compare(sample,finance,baseline)))
 report={'schema':1,'generated_at':dt.datetime.now(dt.timezone.utc).isoformat(),'sample':collection['sample'],'coverage':coverage,'collection_errors':collection['errors'],'tests':tests,
 'limitations':['20 deliberately selected current US nonfinancial companies; selection and survivorship bias.',
 'Annual filings only, up to 550 days old. Quarterly releases and earlier earnings announcements not reconstructed.',
 'Only matched standard taxonomy fields. Financial model is separate from ROIC FCFF/EBITDA score.',
 'Five-year adjusted price history; earlier/later split 2025-01-01, same price windows as existing study. No 2020/2022 forward crisis sample.',
 'Ridge alpha=1 fixed; scaling trained on earlier data only. Same complete-case sample for each paired comparison.',
 'Repeated firms, overlapping windows and shared market shocks; no independent-observation significance claim.',
 'Multiple exploratory comparisons; do not select winning features/weights from these results. No production score changes.']}
 (out/'study-report.json').write_text(json.dumps(report,indent=2,allow_nan=False),encoding='utf8')
 (out/'matched-observations.json').write_text(json.dumps(rows,indent=2,allow_nan=False),encoding='utf8')
 lines=['# Historische Finanzprüfung · explorativ','','Keine automatische Änderung der Risikogewichte. Positiver MSE-Unterschied bedeutet weniger Prognosefehler in dieser Stichprobe, keinen bewiesenen allgemeinen Mehrwert.','',
 '| Monate | Finanzmerkmale | Vergleich | Frühere / spätere Fenster | MSE-Vorteil |','|---|---|---|---:|---:|']
 for t in tests:
  delta=f"{t['mse_improvement']:.6f}" if t['status']=='exploratory' else 'Daten unzureichend'
  lines.append(f"| {t['horizon']} | {', '.join(t['financial_features'])} | {t['baseline']} | {t['earlier_windows']} / {t['later_windows']} | {delta} |")
 lines+=['','## Grenzen']+['- '+s for s in report['limitations']]
 (out/'study-report.md').write_text('\n'.join(lines),encoding='utf8')
 print('Companies:',len(coverage),'windows:',len(rows),'eligible comparisons:',sum(t['status']=='exploratory' for t in tests))
 if not any(t['status']=='exploratory' for t in tests):raise SystemExit('No sufficiently covered comparisons; report saved')

if __name__=='__main__':run()
