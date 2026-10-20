import copy
import datetime as dt
import unittest
from holding_stocks import enrich

class HoldingStockTests(unittest.TestCase):
    def setUp(self):
        self.h={'scope':'FR_Y9C_consolidated_reporting_entity','reporting_period':'2026-06-30','files':[],
            'definitions':{'BHCAP793':{'metric':'cet1_ratio','unit':'fraction','source_unit':'percent'}},
            'entities':{'1':{'name':'Example Inc.','metrics':{'BHCAP793':{'value':.14,'state':'reported'}}}}}
        self.entry={'symbol':'NYSE:EX','rssd_id':'1','holding_name':'Example Inc.','security_type':'common_stock',
            'scope':'listed_consolidated_holding','listing_source_url':'https://example.com/ir','holding_evidence':{'rssd_field':'RSSD9001'}}
        self.reg={'schema':1,'reviewed_on':'2026-10-20','review_expires':'2027-04-18','entries':[self.entry]}
        self.u={'kandidaten':[{'listing_symbol':'NYSE:EX','name':'Example Inc.'}]}
    def run_case(self, today=dt.date(2026,10,20)):
        return enrich({'stocks':[],'summary':{}},self.u,self.h,self.reg,today)
    def test_verified_capital_is_not_score(self):
        r=self.run_case()['stocks'][0]
        self.assertEqual(r['group_metrics']['cet1_ratio']['value'],.14)
        self.assertEqual(r['state'],'verified_holding_capital')
        self.assertIsNone(r['score'])
        self.assertFalse(r['historical_point_in_time_usable'])
    def test_preferred_and_other_exchanges_not_inherited(self):
        self.u['kandidaten']=[{'listing_symbol':s,'name':'Example Inc.'} for s in ['EX-PA','NYSE:EX-PA','LSE:EX','EX']]
        self.assertEqual(self.run_case()['summary']['verified_group_metrics'],0)
    def test_changed_name_and_duplicate_fail_closed(self):
        self.u['kandidaten'][0]['name']='Example subsidiary'
        self.assertEqual(self.run_case()['stocks'][0]['holding_mapping_reason'],'listing_name_changed')
        self.u['kandidaten']*=2
        self.assertEqual(self.run_case()['stocks'][0]['holding_mapping_reason'],'duplicate_universe_symbol')
    def test_old_and_future_data_not_approved(self):
        for period in ['2025-06-30','2027-06-30']:
            self.h['reporting_period']=period
            self.assertIsNone(self.run_case()['stocks'][0]['group_metrics'])
    def test_expired_mapping_and_wrong_holding(self):
        self.assertEqual(self.run_case(dt.date(2027,5,1))['stocks'][0]['holding_mapping_reason'],'identity_review_expired')
        self.h['entities']['1']['name']='Different holding'
        self.assertEqual(self.run_case()['stocks'][0]['holding_mapping_reason'],'holding_identity_changed')
    def test_duplicate_registry_rejected(self):
        self.reg['entries'].append(copy.deepcopy(self.entry))
        with self.assertRaises(ValueError): self.run_case()
