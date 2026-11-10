import datetime as dt
import unittest
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock,patch
from export_continuity import baseline,scan_order,combine,guard

NOW=dt.datetime(2026,11,2,12,tzinfo=dt.timezone.utc)
def row(t,**kw):return dict(ticker=t,listing_symbol='NYSE:'+t,isin='US0000000001',currency='USD',price=10,**kw)
def doc(rows,stand='2026-11-01 12:00 UTC'):return dict(stand=stand,kandidaten=rows)

class ContinuityTests(unittest.TestCase):
    def test_budget_stop_exports_dated_cache_instead_of_empty_result(self):
        import export_cf
        roic=Mock();roic.export_universum.return_value=['A','B'];roic.enabled.return_value=True
        precompute=Mock()
        precompute.filter_boersen.side_effect=lambda x:x
        precompute.collapse_listings.side_effect=lambda x:x
        precompute.ersetze_pence_durch_adr.side_effect=lambda x:x
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/'out.json'
            observed=dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
            with patch.dict('sys.modules',{'roic':roic,'precompute':precompute}),patch.object(export_cf,'AUSGABE',target),patch.object(export_cf,'BUDGET_MIN',0),patch.object(export_cf,'snapshots',return_value=[doc([row('A'),row('B')],observed)]):
                self.assertEqual(export_cf.main(),0)
            data=json.loads(target.read_text())
            self.assertEqual(data['anzahl'],2)
            self.assertEqual(data['scan']['pending'],2)
            self.assertEqual(data['scan']['refreshed'],0)
            self.assertTrue(all(r['export_observed_at']==observed and r['export_status']=='retained' for r in data['kandidaten']))
            precompute.score_ticker.assert_not_called()

    def test_previous_full_snapshot_restores_missing_half(self):
        tickers=['X'+str(i) for i in range(1330)]
        full=doc([row(t) for t in tickers])
        partial=doc(full['kandidaten'][:673],'2026-11-02 11:00 UTC')
        saved=baseline(tickers,[partial,full],NOW)
        self.assertEqual(len(saved),1330)
        self.assertEqual(saved['X900']['export_observed_at'],full['stand'])
        self.assertEqual(saved['X0']['export_observed_at'],partial['stand'])
        order=scan_order(tickers,saved)
        self.assertTrue(all(int(t[1:])>=673 for t in order[:657]))

    def test_partial_scan_preserves_dates_and_rotates(self):
        saved=baseline(['A','B'],[doc([row('A'),row('B')])],NOW)
        rows=combine(['A','B'],saved,[row('A')],set(),'2026-11-02 12:00 UTC')
        self.assertEqual(rows[1]['export_observed_at'],'2026-11-01 12:00 UTC')
        saved=baseline(['A','B'],[doc(rows,'2026-11-02 12:00 UTC')],NOW)
        self.assertEqual(scan_order(['A','B','C'],saved),['C','B','A'])

    def test_reviewed_isin_correction_is_not_an_identity_change(self):
        a={'ticker':'IDCBF','listing_symbol':'OTC:IDCBF','isin':'CNE000001P37','currency':'USD','name':'Industrial and Commercial Bank of China ',
           'name_full':'Industrial and Commercial Bank of China Limited Class A','export_observed_at':'2026-11-09 12:00 UTC'}
        old=doc([a],'2026-11-09 12:00 UTC')
        new=doc([{**a,'isin':'CNE1000003G1','listing_reference_status':'applied','export_observed_at':'2026-11-10 06:00 UTC'}],'2026-11-10 06:00 UTC')
        later=dt.datetime(2026,11,11,12,tzinfo=dt.timezone.utc)
        saved=baseline(['IDCBF'],[new,old],later)
        self.assertEqual(saved['IDCBF']['isin'],'CNE1000003G1')
        self.assertEqual(baseline(['IDCBF'],[old],later)['IDCBF']['isin'],'CNE1000003G1','old snapshot gets the reviewed correction')

    def test_old_future_wrong_listing_and_conflicting_identity_excluded(self):
        for date in ('2026-10-01 12:00 UTC','2026-11-03 12:00 UTC','invalid'):
            self.assertFalse(baseline(['A'],[doc([row('A')],date)],NOW))
        wrong=row('A');wrong['listing_symbol']='LSE:A'
        self.assertFalse(baseline(['A'],[doc([wrong])],NOW))
        changed=row('A');changed['isin']='US0000000002'
        self.assertFalse(baseline(['A'],[doc([changed]),doc([row('A')])],NOW))

    def test_rejected_and_removed_members_do_not_resurrect(self):
        saved=baseline(['A','B'],[doc([row('A'),row('B'),row('C')])],NOW)
        self.assertEqual([r['ticker'] for r in combine(['A','B'],saved,[],{'A'},'unused')],['B'])

    def test_publication_blocks_mass_loss_even_with_same_count(self):
        old=doc([row('X'+str(i)) for i in range(1330)])
        with self.assertRaisesRegex(ValueError,'coverage regression'):guard(old,doc(old['kandidaten'][:673]))
        with self.assertRaises(ValueError):guard(old,doc([row('Y'+str(i)) for i in range(1330)]))
        guard(old,doc(old['kandidaten'][1:]))
