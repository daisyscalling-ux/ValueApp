import copy
import datetime as dt
import unittest
from test_sec_cashflow_history import ROW,NOW,fixture
from sec_cashflow_history import run,balances
from sec_supply_inventory import build


class SupplyInventory(unittest.TestCase):
    def setUp(self):
        self.u={'kandidaten':[copy.deepcopy(ROW)]}
        self.c={'generatedAt':NOW.isoformat(),'stocks':[{'symbol':ROW['listing_symbol'],'domains':{'identity':{'state':'available'},'balance':{'profile':'corporate'}}}]}
        self.mapping={ROW['listing_symbol']:'1'}
        self.cache=run(self.u,self.c,{},self.mapping,lambda *a:fixture(),NOW)

    def result(self,now=NOW):return build(self.u,self.c,self.cache,self.mapping,now)
    def row(self):return self.result()['stocks'][0]

    def test_cached_run_still_reports_entire_current_inventory(self):
        result=run(self.u,self.c,self.cache,self.mapping,lambda *a:self.fail('cache should be used'),NOW)
        self.assertEqual(result['report']['cached'],1)
        inv=result['report']['inventory']
        self.assertEqual(inv['summary']['states'],{'available':1})
        self.assertEqual(inv['stocks'][0]['latestMetricPeriods']['cashAfterPpeAssets'],'2025-12-31')

    def test_new_listing_not_silently_absent(self):
        self.cache={}
        self.assertEqual(self.row()['state'],'not_attempted')
        limited=run(self.u,self.c,{},self.mapping,lambda *a:fixture(),NOW,budget=0)
        self.assertEqual(limited['report']['inventory']['summary']['states'],{'not_attempted':1})

    def test_removed_listing_is_archived_not_current_failure(self):
        self.u={'kandidaten':[]}
        self.assertEqual(self.result()['summary']['archivedListingsOutsideUniverse'],1)
        self.assertEqual(self.result()['stocks'],[])

    def test_expired_archive_and_stale_coverage_distinguished(self):
        later=NOW+dt.timedelta(days=15)
        self.assertEqual(self.result(later)['stocks'][0]['state'],'coverage_stale')
        self.c['generatedAt']=later.isoformat()
        self.assertEqual(self.result(later)['stocks'][0]['state'],'stale')

    def test_duplicate_listing_cannot_supply_any_cashflow_metric(self):
        self.u['kandidaten']*=2
        self.assertEqual(self.row()['reason'],'duplicate_listing')
        self.assertEqual(balances(self.cache,self.u,NOW),{})

    def test_conflicting_cik_cannot_supply_any_cashflow_metric(self):
        self.u['kandidaten'][0]['cik']='2'
        self.assertEqual(self.row()['reason'],'cik_conflict')
        self.assertEqual(balances(self.cache,self.u,NOW),{})

    def test_changed_identity_does_not_inherit_old_failure(self):
        self.cache['attempts'][ROW['listing_symbol']]['error']='issuer_name_mismatch'
        self.u['kandidaten'][0]['isin']='US5949181045'
        self.assertEqual(self.row()['state'],'not_attempted')
        self.assertIsNone(self.row()['lastAttemptError'])

    def test_non_sec_and_specialist_profiles_are_not_missing_corporate_data(self):
        self.mapping={}
        self.assertEqual(self.row()['state'],'outside_scope')
        self.assertEqual(self.row()['reason'],'sec_mapping_missing')
        self.mapping={ROW['listing_symbol']:'1'}
        self.c['stocks'][0]['domains']['balance']['profile']='bank'
        self.assertEqual(self.row()['reason'],'different_balance_profile')

    def test_fresh_but_invalid_values_not_counted_as_available(self):
        for key in ('stocks','operatingStocks'):
            for p in self.cache[key][ROW['listing_symbol']]['periods']:p['value']=999
        self.assertEqual(self.row()['state'],'no_valid_periods')
        self.assertEqual(self.row()['latestMetricPeriods'],{})

    def test_reference_mapping_change_does_not_validate_old_cik(self):
        self.mapping={ROW['listing_symbol']:'2'}
        self.assertNotEqual(self.row()['state'],'available')


if __name__=='__main__':unittest.main()
