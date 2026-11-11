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


class RegistryFileTests(unittest.TestCase):
    """Die geprüften Registerdateien gegen die Originaldaten: RSSD und Name aus FR Y-9C, Fed-Anforderung je Holding."""

    def test_map_matches_bhcf_and_fed_table(self):
        import json
        from pathlib import Path
        here = Path(__file__).resolve().parent
        reg = json.loads((here / 'holding-stock-map.json').read_text(encoding='utf-8'))
        fed = json.loads((here / 'fed-capital-requirements.json').read_text(encoding='utf-8'))
        bhcf = json.loads((here.parent / 'daten/regulatory/bhcf-import.json').read_text(encoding='utf-8'))
        fed_by = {e['rssdId']: e for e in fed['entries']}
        self.assertEqual(len(reg['entries']), 22)
        for e in reg['entries']:
            ent = bhcf['entities'].get(e['rssd_id'])
            self.assertIsNotNone(ent, e['symbol'])
            self.assertEqual(ent['name'], e['holding_name'], e['symbol'])
            self.assertEqual((e['security_type'], e['scope']), ('common_stock', 'listed_consolidated_holding'))
            self.assertTrue(e['listing_source_url'].startswith('https://'), e['symbol'])
            archive = [f['sha256'] for f in bhcf['files'] if f['name'].upper().startswith('BHCF')]
            self.assertEqual([e['holding_evidence']['source_file_sha256']], archive, e['symbol'])
            f = fed_by.get(e['rssd_id'])
            self.assertIsNotNone(f, e['symbol'])
            self.assertEqual(f['holdingName'], e['holding_name'])
            self.assertEqual(f['minimumBps'] + f['stressBufferBps'] + f['gsibBps'], f['totalBps'])
        # Werte aus Tabelle 1 der Fed vom 24.06.2026 (Gesamtanforderung in Basispunkten)
        expected = {'1068025': 770, '1068191': 700, '3242838': 700, '1037003': 720, '1070345': 770, '1132449': 900, '1074156': 700,
                    '1199611': 700, '1111435': 800, '3587146': 850, '2162966': 1180, '1275216': 700, '4504654': 700}
        for rssd, total in expected.items():
            self.assertEqual(fed_by[rssd]['totalBps'], total, rssd)
