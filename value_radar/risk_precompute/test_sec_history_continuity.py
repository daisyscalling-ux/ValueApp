import copy
import unittest
from financial_history import build
from sec_operating_history import normalize,balances
from sec_cashflow_history import METHOD
from test_sec_cashflow_history import NOW,ROW,fixture
from test_sec_currency_concordance import coverage
from roic_risk_annual import identity
import test_financial_history as cases


class ContinuityTests(unittest.TestCase):
    def test_original_and_companyfacts_same_definition_form_one_series(self):
        periods=normalize(fixture(),1,NOW)
        for p in periods[-2:]:
            p['originalFiling']={'method':'annual-inline-xbrl-v1','sourceUrl':p['sourceUrl']+'report.htm','sha256':'a'*64,'accession':p['accession'],'reportDate':p['end'],'form':'10-K','filed':p['filed']}
        state={'schema':1,'method':METHOD,'operatingStocks':{'NASDAQ:EX':{'inputIdentity':identity(ROW),'cik':'1','retrievedAt':NOW.isoformat(),'periods':periods}}}
        u={'kandidaten':[ROW]};backfill={'schema':1,'method':'roic-history-balances-v1','generatedAt':NOW.isoformat(),'stocks':balances(state,u,NOW)}
        archive,report=build(coverage(),u,{},NOW,backfill)
        self.assertEqual(len(archive['series']),1)
        metric=report['stocks'][0]['domains']['balance']['history']['metrics'][0]
        self.assertEqual(metric['periodCount'],6)
        self.assertEqual(len(metric['points']),6)
        self.assertFalse(metric['points'][0]['sourceUrl'].endswith('report.htm'))
        self.assertTrue(metric['points'][-1]['sourceUrl'].endswith('report.htm'))
        self.assertEqual(metric['points'][-1]['sourceRetrievedAt'],NOW.isoformat())
        self.assertFalse(archive['pointInTimeUsable'])

    def test_new_single_period_beats_old_comparable_pair(self):
        helper=cases.HistoryTests();helper.setUp()
        bf=helper.backfill()
        bf['stocks']['NYSE:EX']['balances']=bf['stocks']['NYSE:EX']['balances'][:4]
        _,report=build(helper.coverage(source='Yahoo'),helper.u,{},helper.now,bf)
        metric=report['stocks'][0]['domains']['balance']['history']['metrics'][0]
        self.assertEqual(metric['period'],'2025-12-31')
        self.assertEqual(metric['state'],'one_period')
        self.assertIsNone(metric['previousValue'])
        self.assertEqual(metric['sourceLabel'],'Yahoo')

    def test_current_gap_not_hidden_by_older_complete_series(self):
        helper=cases.HistoryTests();helper.setUp();bf=helper.backfill()
        old=bf['stocks']['NYSE:EX']['balances'][:4]
        current=copy.deepcopy([old[0],bf['stocks']['NYSE:EX']['balances'][-1]])
        for b in current:
            for f in b['metrics']['netDebtAssets']['basis']['fields'].values():f['source']='Separate verified source'
        bf['stocks']['NYSE:EX']['balances']=old+current
        _,report=build(helper.coverage(source='Yahoo'),helper.u,{},helper.now,bf)
        metric=report['stocks'][0]['domains']['balance']['history']['metrics'][0]
        self.assertEqual(metric['period'],'2025-12-31')
        self.assertNotEqual(metric['state'],'comparable')
        self.assertIsNone(metric['changePercentagePoints'])
