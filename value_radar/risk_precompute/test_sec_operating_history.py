import copy
import json
import unittest
from pathlib import Path
from sec_operating_history import normalize,balances
from sec_cashflow_history import run,balances as all_balances,METHOD,TAGS
from sec_original_filings import parse
from test_sec_cashflow_history import NOW,ROW,fixture
from test_sec_currency_concordance import coverage,translated
from roic_risk_annual import identity
from financial_history import build
from risk_app_export import build as shards

class OperatingTests(unittest.TestCase):
    def test_missing_capex_never_becomes_zero_capex(self):
        data=fixture();del data['facts']['us-gaap'][TAGS['ppe']]
        result=normalize(data,1,NOW)
        self.assertEqual(len(result),6)
        self.assertTrue(all(p['value']==.2 and 'cashPpe' not in p for p in result))
        state=run({'kandidaten':[ROW]},coverage(),{}, {'NASDAQ:EX':'1'},lambda *a:data,NOW)
        self.assertFalse(state['stocks'])
        self.assertEqual(state['attempts']['NASDAQ:EX']['error'],'cash_ppe_concept_missing')
        self.assertEqual(len(state['operatingStocks']['NASDAQ:EX']['periods']),6)

    def test_duration_filing_assets_and_duplicate_conflicts(self):
        for key,patch in [('assets',{'val':0}),('assets',{'start':'2025-01-01'}),('ocf',{'start':'2025-10-01'}),('ocf',{'accn':'0000000001-26-000099'}),('ocf',{'val':True})]:
            data=fixture();data['facts']['us-gaap'][TAGS[key]]['units']['USD'][-1].update(patch)
            self.assertEqual(len(normalize(data,1,NOW)),5)
        data=fixture();rows=data['facts']['us-gaap'][TAGS['ocf']]['units']['USD'];rows.append({**rows[-1],'val':999})
        self.assertEqual(len(normalize(data,1,NOW)),5)

    def test_negative_operating_cashflow_is_retained(self):
        data=fixture();data['facts']['us-gaap'][TAGS['ocf']]['units']['USD'][-1]['val']=-20
        self.assertEqual(normalize(data,1,NOW)[-1]['value'],-.2)

    def test_cross_currency_concordance_and_no_implicit_conversion(self):
        data=translated();self.assertEqual(len(normalize(data,1,NOW)),12)
        data['facts']['us-gaap'][TAGS['ocf']]['units']['TWD'][-1]['val']=999
        self.assertEqual(len(normalize(data,1,NOW)),10)

    def test_stale_identity_and_tampered_cache_rejected(self):
        cache={'schema':1,'method':METHOD,'operatingStocks':{'NASDAQ:EX':{'inputIdentity':identity(ROW),'cik':'1','retrievedAt':NOW.isoformat(),'periods':normalize(fixture(),1,NOW)}}}
        saved=copy.deepcopy(cache)
        cache['operatingStocks']['NASDAQ:EX']['periods'][-1]['value']=88
        self.assertEqual(len(balances(cache,{'kandidaten':[ROW]},NOW)['NASDAQ:EX']['balances']),5)
        cache=saved;cache['operatingStocks']['NASDAQ:EX']['inputIdentity']['isin']='other'
        self.assertFalse(balances(cache,{'kandidaten':[ROW]},NOW))

    def test_real_reports_reach_app_without_free_cashflow_or_score_changes(self):
        cases=[('bp',313807,'0000313807-26-000006','2026-03-06','BP PLC',.08793793039069961),('rio',863064,'0001628280-26-009531','2026-02-19','Rio Tinto plc',.13139529437479508)]
        for name,cik,acc,filed,company,value in cases:
            meta=dict(accessionNumber=acc,filingDate=filed,reportDate='2025-12-31',form='20-F')
            url=f'https://www.sec.gov/Archives/edgar/data/{cik}/{acc.replace("-","")}/{name}-20251231.htm'
            original=parse((Path(__file__).with_name('fixtures')/(name+'-2025-selected.xhtml')).read_bytes(),cik,meta,url)
            rows=normalize(original,cik,NOW)
            self.assertEqual(len(rows),2);self.assertAlmostEqual(rows[-1]['value'],value)
            row={**ROW,'name':company};u={'kandidaten':[row]};cov=coverage();cov['stocks'][0]['score']=57
            state=run(u,cov,{}, {'NASDAQ:EX':str(cik)},lambda *a:{'cik':cik,'entityName':company,'facts':{}},NOW,fetch_original=lambda *a:original)
            bf={'schema':1,'method':'roic-history-balances-v1','generatedAt':NOW.isoformat(),'stocks':all_balances(state,u,NOW)}
            archive,report=build(cov,u,{},NOW,bf)
            metrics=report['stocks'][0]['domains']['balance']['history']['metrics']
            self.assertEqual([m['metric'] for m in metrics],['operatingCashflowAssets'])
            self.assertEqual(metrics[0]['periodCount'],2)
            _,payloads=shards(report,NOW)
            published=json.loads(next(iter(payloads.values())))['stocks'][0]
            self.assertEqual(published['score'],57)
            self.assertEqual(published['domains']['balance']['metrics'],{})
            self.assertFalse(archive['pointInTimeUsable'])
