import copy
import unittest
from sec_source_evidence import build
from sec_cashflow_history import VARIANTS, normalize, run
from test_sec_cashflow_history import fixture, NOW, ROW, TAGS
from test_sec_currency_concordance import coverage


class Evidence(unittest.TestCase):
    def test_exact_missing_field_is_visible_without_changing_values(self):
        data=fixture()
        data['facts']['us-gaap'][TAGS['ppe']]['units']['USD'].pop()
        before=copy.deepcopy(data)
        result=build(data,1,NOW,VARIANTS,normalize(data,1,NOW))
        variant=result['variants'][0]
        self.assertEqual(variant['latestAcceptedEnd'],'2024-12-31')
        self.assertEqual(variant['fields']['assets']['latestAnnualEnd'],'2025-12-31')
        self.assertEqual(variant['incompleteGroups'][0]['missingFields'],['ppe'])
        self.assertEqual(data,before)
        self.assertTrue(result['diagnosticOnly'])

    def test_different_accession_never_appears_as_complete_group(self):
        data=fixture()
        data['facts']['us-gaap'][TAGS['ppe']]['units']['USD'][-1]['accn']='0000000001-26-000099'
        result=build(data,1,NOW,VARIANTS,[])
        groups=result['variants'][0]['incompleteGroups']
        self.assertEqual(len(groups),2)
        self.assertEqual({tuple(g['missingFields']) for g in groups},{('ppe',),('assets','ocf')})

    def test_inventory_keeps_sign_duration_and_namespace(self):
        data=fixture()
        data['facts']['ifrs-full']={'PurchaseOfPropertyPlantAndEquipmentAndIntangibleAssets':{'units':{'EUR':[{
            'end':'2025-12-31','start':'2025-10-01','filed':'2026-02-20','form':'20-F',
            'accn':'0000000001-26-000001','val':-50}]}}}
        result=build(data,1,NOW,VARIANTS,[])
        alt=next(x for x in result['alternativeConcepts'] if x['namespace']=='ifrs-full')
        self.assertEqual(alt['latestObservations'][0]['value'],-50)
        self.assertEqual(alt['latestObservations'][0]['durationDays'],91)
        self.assertEqual(len(normalize(data,1,NOW)),6)

    def test_invalid_and_future_observations_are_not_exported(self):
        data=fixture()
        rows=data['facts']['us-gaap']['Assets']['units']['USD']
        for patch in ({'val':True},{'val':float('nan')},{'filed':'2030-01-01'},{'form':'10-Q'},{'accn':'bad'}):
            rows.append({**rows[0],**patch})
        result=build(data,1,NOW,VARIANTS,[])
        self.assertEqual(result['variants'][0]['fields']['assets']['observationCount'],6)
        with self.assertRaises(ValueError):build(data,2,NOW,VARIANTS,[])

    def test_bounded_payload_and_truncation_flags(self):
        data=fixture()
        for i in range(80):
            data['facts']['us-gaap'][f'PaymentsToAcquireOtherProperty{i}']=copy.deepcopy(data['facts']['us-gaap'][TAGS['ppe']])
        result=build(data,1,NOW,VARIANTS,[])
        self.assertEqual(len(result['alternativeConcepts']),48)
        self.assertTrue(result['alternativesTruncated'])

    def test_partial_success_evidence_is_saved_and_retried_only_once(self):
        data=fixture();data['facts']['us-gaap'][TAGS['ppe']]['units']['USD'].pop()
        u={'kandidaten':[ROW]};calls=[]
        def fetch(*args):calls.append(1);return data
        state=run(u,coverage(),{}, {'NASDAQ:EX':'1'},fetch,NOW)
        self.assertIn('sourceEvidence',state['attempts']['NASDAQ:EX'])
        state['attempts']['NASDAQ:EX']['policy']='old'
        state=run(u,coverage(),state,{'NASDAQ:EX':'1'},fetch,NOW)
        state=run(u,coverage(),state,{'NASDAQ:EX':'1'},fetch,NOW)
        self.assertEqual(len(calls),2)
        self.assertEqual(len(state['stocks']['NASDAQ:EX']['periods']),5)


if __name__=='__main__':unittest.main()
