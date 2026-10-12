import copy
import unittest
from settlement_review import stock_scenario
from window_coverage import inspect_windows


class SettlementTests(unittest.TestCase):
    def setUp(self):
        self.days=['2020-01-02','2020-01-03','2020-01-06','2020-01-07','2020-01-08']
        self.pre=[dict(Datum=d,Adjusted_Close='50',Tagesrendite='' if i==0 else '0')
                  for i,d in enumerate(self.days[:2])]
        self.post=[{'Date':d,'Close':'45','Adj Close':'40','Volume':'10',
                    'Dividends':'0','Stock Splits':'0'} for d in self.days[2:]]
        self.event=dict(identity='OLD',successor='NEW',effective=self.days[2],
                        first_nontrading_session=self.days[2],stock_ratio=2,cash_per_share=0,
                        currency='USD',source='https://example.org/closing',
                        successor_identity_source='https://example.org/identity',
                        successor_symbol_effective=self.days[3],successor_former_symbol='FORMER')
        self.anchor=dict(symbol='OLD',date=self.days[1],close=100,currency='USD',
                         adjustment='Unadjusted',source='https://example.org/raw')
        self.meta=dict(symbol='NEW',currency='USD',instrumentType='EQUITY')
    def scenario(self):
        return stock_scenario(self.pre,self.post,self.days,self.event,self.anchor,self.meta)
    def test_raw_transition_not_adjusted_prices_or_split_twice(self):
        old=copy.deepcopy(self.pre)
        r=self.scenario()
        self.assertAlmostEqual(float(r[2]['Tagesrendite']),-.10)
        self.assertEqual(float(r[2]['Adjusted_Close']),45)
        self.assertEqual(float(r[3]['Tagesrendite']),0)
        self.assertEqual(old,self.pre)
    def test_later_dividend_not_added_twice(self):
        self.post[1].update({'Adj Close':'42','Dividends':'2'})
        self.assertAlmostEqual(float(self.scenario()[3]['Tagesrendite']),.05)
    def test_missing_session_not_filled(self):
        self.post.pop(1)
        with self.assertRaises(ValueError):self.scenario()
    def test_duplicate_rejected(self):
        self.post.append(dict(self.post[0]))
        with self.assertRaises(ValueError):self.scenario()
    def test_wrong_currency_rejected(self):
        self.meta['currency']='EUR'
        with self.assertRaises(ValueError):self.scenario()
    def test_adjusted_anchor_rejected(self):
        self.anchor['adjustment']='Adjusted: Splits and Dividends'
        with self.assertRaises(ValueError):self.scenario()
    def test_mixed_cash_case_not_silently_ignored(self):
        self.event['cash_per_share']=5
        with self.assertRaises(ValueError):self.scenario()
    def test_boundary_dividend_requires_review(self):
        self.post[0]['Dividends']='1'
        with self.assertRaises(ValueError):self.scenario()
    def test_wrong_anchor_day_rejected(self):
        self.anchor['date']=self.days[0]
        with self.assertRaises(ValueError):self.scenario()
    def test_nontradable_entries_stay_in_denominator(self):
        r,_=inspect_windows(self.days,[(self.days[0],self.days[-1])],self.scenario(),
                            self.days[0],horizons=(1,),entry_before=self.days[2])
        self.assertEqual(r[1]['expected_windows'],4)
        self.assertEqual(r[1]['covered_windows'],1)
        self.assertEqual(r[1]['nontradable_entry_windows'],2)
        self.assertEqual(r[1]['incomplete_windows'],2)
        self.assertEqual(r[1]['pending_windows'],1)


if __name__=='__main__':unittest.main()
