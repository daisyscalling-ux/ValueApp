import datetime as dt
import unittest
import numpy as np
import test_pilot
from study_evaluate import financial_features, compare, ridge_predict

class StudyTests(unittest.TestCase):
 def fixture(self):
  facts,filings=test_pilot.AuditTests().fixture()
  for tag,value in [('Assets',1000),('Liabilities',400),('StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest',600)]:
   facts['facts']['us-gaap'][tag]={'units':{'USD':[dict(end='2022-12-31',accn='first',filed='2023-02-01',form='10-K',val=value)]}}
  return facts,filings
 def test_no_future_financials_and_no_stale_annual(self):
  f,s=self.fixture();self.assertIsNone(financial_features(f,s,'2023-02-01')[0]);v,e=financial_features(f,s,'2023-03-01')
  self.assertIsNone(e);self.assertEqual(v['negative_fcf_assets'],-.08);self.assertEqual(v['liabilities_assets'],.4)
  self.assertIsNone(financial_features(f,s,'2026-01-01')[0])
 def test_assets_equity_fallback_and_conflict(self):
  f,s=self.fixture();del f['facts']['us-gaap']['Liabilities'];v,e=financial_features(f,s,'2023-03-01');self.assertEqual(v['liabilities_assets'],.4)
  f,s=self.fixture();f['facts']['us-gaap']['Liabilities']['units']['USD'][0]['val']=999
  self.assertEqual(financial_features(f,s,'2023-03-01')[1],'balance sheet does not reconcile')
 def test_later_labels_never_change_fitted_predictions(self):
  train=[{'score':i,'negative_fcf_assets':i/100,'loss':i/100} for i in range(40)]
  a=[{'score':1,'negative_fcf_assets':.01,'loss':.1}]
  b=[dict(a[0],loss=.9)]
  np.testing.assert_allclose(ridge_predict(train,a,['score','negative_fcf_assets']),ridge_predict(train,b,['score','negative_fcf_assets']))
 def test_matched_sample_excludes_missing_and_split_crossing(self):
  rows=[]
  for i in range(80):
   rows.append({'symbol':str(i%10),'sector':'test','date':'2024-03-31' if i<40 else '2025-03-31','end':'2024-06-30' if i<40 else '2025-06-30','score':i%25,'loss':(i%10)/100,'negative_fcf_assets':i/100})
  rows += [dict(rows[0],end='2025-01-02'),dict(rows[-1],negative_fcf_assets=None)]
  r=compare(rows,['negative_fcf_assets'],'score');self.assertEqual(r['earlier_windows'],40);self.assertEqual(r['later_windows'],40);self.assertEqual(r['status'],'exploratory')

if __name__=='__main__':unittest.main()
