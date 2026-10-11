import unittest
from historical_delisted import collect,normalize

class DelistedTests(unittest.TestCase):
    def row(self,**changes):
        return dict(symbol='OLD',companyName='Old company',exchange='NYSE',ipoDate='2000-01-01',delistedDate='2020-01-01',**changes)
    def test_pages_deduplicate_records_but_keep_reused_symbols(self):
        a=self.row();b=dict(a,companyName='Different company',ipoDate='2021-01-01',delistedDate='2025-01-01')
        r=collect(lambda p:[[a],[a,b],[]][p]);self.assertEqual(len(r['records']),2);self.assertEqual(r['duplicates'],1)
        self.assertEqual(r['status'],'provider_end_reached');self.assertFalse(r['complete_historical_universe_verified'])
    def test_page_cap_and_repeated_page_are_partial(self):
        self.assertEqual(collect(lambda p:[self.row()],1)['status'],'page_limit')
        self.assertEqual(collect(lambda p:[self.row()])['status'],'repeated_page')
    def test_bad_dates_excluded_and_error_preserves_previous_rows(self):
        a=self.row();bad=dict(a,delistedDate='1999-01-01')
        r=collect(lambda p:[a,bad] if p==0 else None)
        self.assertEqual(r['invalid_rows'],1);self.assertEqual(len(r['records']),1);self.assertEqual(r['status'],'unrecognized_response')

if __name__=='__main__':unittest.main()
