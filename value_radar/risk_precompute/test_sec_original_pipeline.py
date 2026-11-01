import copy
import datetime as dt
import json
import unittest
import urllib.error
from pathlib import Path
from sec_cashflow_components import compose,CONT,DISC,TOTAL
from sec_original_filings import parse,latest_annual
from sec_original_supply import loader,merge_periods
from sec_cashflow_history import normalize,balances,METHOD,run
from financial_history import build
from risk_app_export import build as app_shards
from roic_risk_annual import identity
from test_sec_cashflow_history import fixture,NOW,ROW
from test_sec_currency_concordance import coverage

FIX=Path(__file__).with_name('fixtures')
META={
 'pdd':{'cik':1737806,'accessionNumber':'0001104659-26-050727','filingDate':'2026-04-29','form':'20-F','reportDate':'2025-12-31','primaryDocument':'pdd-20251231x20f.htm'},
 'tsm':{'cik':1046179,'accessionNumber':'0001628280-26-025362','filingDate':'2026-04-16','form':'20-F','reportDate':'2025-12-31','primaryDocument':'tsm-20251231.htm'},
}


def original(symbol):
 m=META[symbol]
 url=f'https://www.sec.gov/Archives/edgar/data/{m["cik"]}/{m["accessionNumber"].replace("-","")}/{m["primaryDocument"]}'
 return parse((FIX/(symbol+'-2025-selected.xhtml')).read_bytes(),m['cik'],m,url)


class Components(unittest.TestCase):
 def split(self):
  data=fixture();g=data['facts']['us-gaap'];g[CONT]=g.pop(TOTAL);g[DISC]=copy.deepcopy(g[CONT])
  for row in g[DISC]['units']['USD']:row['val']=-3
  return data
 def test_signed_components_require_both_and_preserve_input(self):
  data=self.split();saved=copy.deepcopy(data)
  out,stats=compose(data,NOW)
  self.assertEqual(stats['derived'],6);self.assertEqual(data,saved)
  self.assertEqual(out['facts']['us-gaap'][TOTAL]['units']['USD'][-1]['val'],17)
  del data['facts']['us-gaap'][DISC]
  self.assertFalse(normalize(data,1,NOW))
 def test_mismatched_period_currency_or_filing_never_combined(self):
  for patch in ({'start':'2025-01-02'},{'filed':'2026-03-01'},{'accn':'0000000001-26-000099'},{'val':True}):
   data=self.split();data['facts']['us-gaap'][DISC]['units']['USD'][-1].update(patch)
   self.assertEqual(len(normalize(data,1,NOW)),5)
  data=self.split();units=data['facts']['us-gaap'][DISC]['units'];units['EUR']=units.pop('USD')
  self.assertFalse(normalize(data,1,NOW))
 def test_reported_zero_valid_and_conflicting_total_not_replaced(self):
  data=self.split();g=data['facts']['us-gaap']
  for row in g[DISC]['units']['USD']:row['val']=0
  self.assertEqual(normalize(data,1,NOW)[-1]['operatingCashflow'],20)
  g[TOTAL]=copy.deepcopy(g[CONT])
  for row in g[TOTAL]['units']['USD']:row['val']=42
  result,stats=compose(data,NOW)
  self.assertEqual(stats['conflicts'],6)
  self.assertEqual(normalize(result,1,NOW)[-1]['operatingCashflow'],42)
 def test_real_apd_and_ge_healthcare_observations(self):
  corpus=json.loads((FIX/'ocf-component-observations.json').read_text())
  for symbol,data in corpus.items():
   rows=normalize(data,data['cik'],NOW)
   self.assertTrue(rows,symbol)
   self.assertTrue(all('ocfDerivation' in p for p in rows))
   if symbol=='NASDAQ:GEHC':
    self.assertEqual(next(p for p in rows if p['end']=='2024-12-31')['operatingCashflow'],1951000000)
 def test_tampered_derivation_is_rejected_on_cache_read(self):
  rows=normalize(self.split(),1,NOW);rows[-1]['ocfDerivation']['discontinued']=999
  state={'schema':1,'method':METHOD,'stocks':{'NASDAQ:EX':{'inputIdentity':identity(ROW),'cik':'1','retrievedAt':NOW.isoformat(),'periods':rows}}}
  self.assertEqual(len(balances(state,{'kandidaten':[ROW]},NOW)['NASDAQ:EX']['balances']),5)


class Originals(unittest.TestCase):
 def test_actual_original_reports_restore_2025(self):
  for symbol in META:
   rows=normalize(original(symbol),META[symbol]['cik'],NOW)
   self.assertEqual({p['end'] for p in rows},{'2024-12-31','2025-12-31'})
   self.assertTrue(all(p.get('originalFiling') for p in rows))
   row=next(p for p in rows if p['end']=='2025-12-31' and p['currency'] in ('TWD','CNY'))
   if symbol=='pdd':
    self.assertEqual(row['cashPpe'],1145077000)
    self.assertEqual(row['metric'],'cashAfterPpeIntangiblesAssets')
    self.assertAlmostEqual(row['value'],.16791455531985133)
   else:self.assertAlmostEqual(row['value'],.12638157129679556)
 def test_foreign_issuer_and_report_metadata_rejected(self):
  m=META['pdd'];raw=(FIX/'pdd-2025-selected.xhtml').read_bytes()
  for cik,filing in ((1,m),(m['cik'],{**m,'reportDate':'2024-12-31'}),(m['cik'],{**m,'form':'10-K'})):
   with self.assertRaises(ValueError):parse(raw,cik,filing,'unused')
 def test_unsafe_xml_and_unknown_transforms_rejected(self):
  m=META['pdd'];raw=(FIX/'pdd-2025-selected.xhtml').read_bytes()
  with self.assertRaises(ValueError):parse(b'<!DOCTYPE a>'+raw,m['cik'],m,'unused')
  with self.assertRaises(ValueError):parse(('<!DOCTYPE a>'+raw.decode()).encode('utf-16'),m['cik'],m,'unused')
  changed=raw.replace(b'ixt:num-dot-decimal',b'ixt:unreviewed-transform')
  self.assertFalse(normalize(parse(changed,m['cik'],m,'unused'),m['cik'],NOW))
 def test_custom_concept_cannot_be_reused_for_other_issuer(self):
  data=original('pdd');data['cik']=1
  self.assertFalse(normalize(data,1,NOW))
 def test_pipeline_reaches_two_year_history_without_score_mutation(self):
  for symbol in META:
   data=original(symbol);row={**ROW,'listing_symbol':'NASDAQ:EX'};u={'kandidaten':[row]};cov=coverage()
   cache={'schema':1,'method':METHOD,'stocks':{'NASDAQ:EX':{'inputIdentity':identity(row),'cik':str(data['cik']),'retrievedAt':NOW.isoformat(),'periods':normalize(data,data['cik'],NOW)}}}
   b=balances(cache,u,NOW)
   self.assertTrue(b)
   archive,result=build(cov,u,{},NOW,{'schema':1,'method':'roic-history-balances-v1','generatedAt':NOW.isoformat(),'stocks':b})
   metrics=result['stocks'][0]['domains']['balance']['history']['metrics']
   self.assertEqual(len(metrics),1);self.assertEqual(metrics[0]['periodCount'],2)
   self.assertEqual(metrics[0]['state'],'comparable');self.assertEqual(metrics[0]['period'],'2025-12-31')
   self.assertIn('SEC original annual filing',metrics[0]['sourceLabel'])
   manifest,payloads=app_shards(result,NOW)
   shard=json.loads(payloads[manifest['shards'][manifest['listings']['NASDAQ:EX']]])
   self.assertEqual(shard['stocks'][0]['domains']['balance']['history']['metrics'],metrics)
   self.assertEqual(cov['stocks'][0]['domains']['balance']['metrics'],{})
   self.assertFalse(archive['pointInTimeUsable'])
   broken=copy.deepcopy(cache);broken['stocks']['NASDAQ:EX']['periods'][0]['originalFiling']['sha256']='bad'
   self.assertFalse(balances(broken,u,NOW))
 def test_new_filing_supersedes_old_but_same_day_conflict_quarantined(self):
  rows=normalize(original('tsm'),META['tsm']['cik'],NOW)
  existing=copy.deepcopy(rows)
  for p in existing:p['filed']='2026-03-01';p['value']=.5
  combined,stats=merge_periods(existing,rows)
  self.assertEqual(len(combined),len(rows));self.assertEqual(stats['supersededObservations'],len(rows))
  bad=copy.deepcopy(rows);bad[0]['cashPpe']+=1000000
  combined,stats=merge_periods(rows,bad)
  self.assertEqual(stats['conflictingPeriods'],1)
 def test_loader_uses_only_cik_bound_safe_latest_document(self):
  m=META['pdd'];keys=['accessionNumber','filingDate','reportDate','form','primaryDocument']
  submissions={'cik':m['cik'],'filings':{'recent':{k:[m[k]] for k in keys}}}
  calls=[]
  def fetch(url,timeout,limit):
   calls.append(url)
   return json.dumps(submissions).encode() if 'submissions' in url else (FIX/'pdd-2025-selected.xhtml').read_bytes()
  data=loader('not-logged',[0],NOW,fetch)(m['cik'],30)
  self.assertEqual(data['cik'],m['cik']);self.assertEqual(len(calls),2)
  self.assertIn('/1737806/000110465926050727/pdd-20251231x20f.htm',calls[1])
  submissions['filings']['recent']['primaryDocument']=['../../other.htm']
  self.assertIsNone(latest_annual(submissions,m['cik'],NOW))
 def test_original_failure_does_not_erase_existing_companyfacts(self):
  def fail(*args):raise TimeoutError()
  data=fixture();data['facts']['us-gaap']['PaymentsToAcquirePropertyPlantAndEquipment']['units']['USD'].pop()
  s=run({'kandidaten':[ROW]},coverage(),{}, {'NASDAQ:EX':'1'},lambda *a:data,NOW,fetch_original=fail)
  self.assertEqual(len(s['stocks']['NASDAQ:EX']['periods']),5)
  self.assertIn('originalError',s['attempts']['NASDAQ:EX'])
 def test_independent_public_distribution_fallback_and_rate_limit_stop(self):
  m=META['pdd'];keys=['accessionNumber','filingDate','reportDate','form','primaryDocument']
  submissions={'cik':m['cik'],'filings':{'recent':{k:[m[k]] for k in keys}}}
  for status in (403,429):
   calls=[]
   def fetch(url,timeout,limit):
    calls.append(url)
    if 'submissions' in url:return json.dumps(submissions).encode()
    if url.startswith('https://www.sec.gov/'):raise urllib.error.HTTPError(url,status,'',{},None)
    return (FIX/'pdd-2025-selected.xhtml').read_bytes()
   if status==403:
    result=loader('not-logged',[0],NOW,fetch)(m['cik'],30)
    self.assertTrue(result['originalFiling']['distributionUrl'].startswith('https://cdn.yahoofinance.com/'))
    self.assertEqual(len(calls),3)
   else:
    with self.assertRaises(urllib.error.HTTPError):loader('not-logged',[0],NOW,fetch)(m['cik'],30)
    self.assertEqual(len(calls),2)


if __name__=='__main__':unittest.main()
