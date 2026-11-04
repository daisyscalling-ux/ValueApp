import copy
import unittest
from sec_reported_ppe import recover

def facts():
 return {'us-gaap':{'NetCashProvidedByUsedInOperatingActivities':{'units':{'USD':[{'start':str(y)+'-01-01','end':str(y)+'-12-31','val':v*1000000,'accn':'0001559720-26-000004','filed':'2026-02-12','form':'10-K'} for y,v in [(2024,4518),(2025,4646)]]}}}}

def table():
 return '<p>Reconciliation of cash provided by operating activities to FCF (in millions, except percentages)</p><table><tr><td></td><td>2024</td><td>2025</td></tr><tr><td>Net cash provided by operating activities</td><td>$</td><td>4,518</td><td>$</td><td>4,646</td></tr><tr><td>Purchases of property and equipment</td><td>(34)</td><td>(33)</td></tr><tr><td>FCF</td><td>4,484</td><td>4,613</td></tr></table>'

class ReportedPpe(unittest.TestCase):
 def test_selected_real_airbnb_filing_and_cache_revalidation(self):
  import datetime as dt
  from pathlib import Path
  from sec_original_filings import parse
  from sec_cashflow_history import normalize
  from sec_original_supply import verified_original
  meta={'accessionNumber':'0001559720-26-000004','reportDate':'2025-12-31','form':'10-K','filingDate':'2026-02-12'}
  url='https://www.sec.gov/Archives/edgar/data/1559720/000155972026000004/abnb-20251231.htm'
  d=parse((Path(__file__).with_name('fixtures')/'abnb-2025-reconciliation-selected.xhtml').read_bytes(),'1559720',meta,url)
  r=normalize(d,'1559720',dt.datetime(2026,11,4,tzinfo=dt.timezone.utc))
  self.assertEqual([(p['end'],p['cashPpe']) for p in r],[('2024-12-31',34000000),('2025-12-31',33000000)])
  self.assertTrue(verified_original(r[-1],1559720))
  self.assertEqual(r[-1]['metric'],'cashAfterPpeAssets')
  tampered=copy.deepcopy(r[-1]);tampered['cashPpe']=0
  self.assertFalse(verified_original(tampered,1559720))
 def test_reported_amounts_scale_and_provenance(self):
  f=facts();old=copy.deepcopy(f);r=recover(table().encode(),f)
  self.assertEqual([x['val'] for x in r],[34000000,33000000]);self.assertEqual(f,old)
  self.assertEqual(r[-1]['reportedTableEvidence']['method'],'explicit-annual-ppe-reconciliation-v1')
 def test_caption_scale_and_labels_are_required(self):
  for a,b in [('in millions','in thousands'),('Reconciliation','Schedule'),('Purchases of property and equipment','Purchases of investments')]:
   self.assertFalse(recover(table().replace(a,b).encode(),facts()))
 def test_matching_tagged_cashflow_required_for_each_year(self):
  f=facts();f['us-gaap']['NetCashProvidedByUsedInOperatingActivities']['units']['USD'][-1]['val']=999
  self.assertEqual([r['end'] for r in recover(table().encode(),f)],['2024-12-31'])
  f=facts();f['us-gaap']['NetCashProvidedByUsedInOperatingActivities']['units']['EUR']=f['us-gaap']['NetCashProvidedByUsedInOperatingActivities']['units'].pop('USD')
  self.assertFalse(recover(table().encode(),f))
 def test_quarterly_and_noncalendar_periods_not_guessed(self):
  f=facts()
  for x in f['us-gaap']['NetCashProvidedByUsedInOperatingActivities']['units']['USD']:x['start']='2025-10-01'
  self.assertFalse(recover(table().encode(),f))
 def test_inconsistent_bridge_or_positive_purchases_rejected(self):
  for a,b in [('4,613','4,600'),('(33)','33')]:
   self.assertEqual(len(recover(table().replace(a,b).encode(),facts())),1)
 def test_duplicate_labels_and_conflicting_tables_rejected(self):
  t=table();extra='<tr><td>FCF</td><td>4,484</td><td>4,613</td></tr>'
  self.assertFalse(recover(t.replace('</table>',extra+'</table>').encode(),facts()))
  other=t.replace('(33)','(44)').replace('4,613','4,602')
  self.assertEqual([x['end'] for x in recover((t+other).encode(),facts())],['2024-12-31'])
 def test_missing_value_is_not_zero_and_malformed_parentheses_rejected(self):
  for v in ['—','(33','unknown']:
   self.assertFalse(recover(table().replace('(33)',v).encode(),facts()))
if __name__=='__main__':unittest.main()
