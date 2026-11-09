import datetime as dt
import gzip
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import feature_snapshot as fs

NOW = dt.datetime(2026, 11, 9, 18, 0, tzinfo=dt.timezone.utc)


def fixture(folder, manifest_age_hours=1, bad_hash=False):
    folder = Path(folder)
    shard = {'schema': 1, 'stocks': [
        {'symbol': 'NYSE:BK1', 'name': 'Bank One', 'country': 'US', 'domains': {
            'market': {'proxy': 'SPY'},
            'balance': {'profile': 'bank', 'bankCapital': {'state': 'available', 'period': '2026-06-30', 'rssdId': '1',
                        'metrics': {'cet1_ratio': {'value': .14}}, 'capitalRequirement': {'state': 'available', 'value': .115},
                        'liquidity': {'state': 'available', 'reportedRatio': 1.1, 'period': '2026-06-30'}}},
            'reviewedRisk': {'bankCredit': {'state': 'available', 'ratio': .0075, 'period': '2026-06-30'},
                             'events': [{'candidateId': 'a', 'state': 'confirmed_event', 'eventDate': '2026-11-05'},
                                        {'candidateId': 'b', 'state': 'not_subject_of_tagged_event'}]},
            'sector': {'state': 'available', 'group': 'g', 'drawdown': .1, 'medianDrawdown': .2}}},
        {'symbol': 'NASDAQ:ABC', 'name': 'Abc', 'country': 'US', 'domains': {'balance': {'profile': 'corporate', 'ratios': {'netDebtAssets': .1}}}},
    ]}
    raw = json.dumps(shard).encode()
    name = hashlib.sha256(raw).hexdigest()
    (folder / 'risk_app').mkdir(parents=True)
    (folder / 'risk_app' / f'{name}.json').write_bytes(raw if not bad_hash else raw + b' ')
    generated = (NOW - dt.timedelta(hours=manifest_age_hours)).isoformat()
    (folder / 'cf_risk_app_manifest.json').write_text(json.dumps({'generatedAt': generated, 'shards': {'0': name}}))
    (folder / 'cf_universum.json').write_text(json.dumps({'stand': '2026-11-09', 'kandidaten': [
        {'listing_symbol': 'NASDAQ:ABC', 'sector': 'Tech', 'industry': 'Software', 'price': 10, 'fair_value': float('nan'), 'gross_margin': 50.0}]}))
    (folder / 'cf_risk.json').write_text(json.dumps({'generatedAt': generated, 'stocks': {
        'NASDAQ:ABC': {'retrievedAt': generated, 'adjustment': 'total_return', 'statistics': {'observations': 600, 'last': '2026-11-06', 'error': '', 'es': .03, 'vol': .3, 'dd': .4, 'worst': .2, 'drawdown': .1}}},
        'benchmarks': {'SPY': {'statistics': {'drawdown': .05, 'last': '2026-11-06'}}}}))
    (folder / 'fundamentals').mkdir()
    (folder / 'fundamentals' / 'NASDAQ_ABC.json').write_text(json.dumps({'retrieved_at': generated, 'annual': {
        'end': '2025-12-31', 'published_at': '2026-02-20', 'currency': 'USD', 'fields': {'revenue': 100.0, 'gross_profit': 40.0, 'capex': None}},
        'market': {'fields': {'price': 10.0, 'shares_out': 5.0, 'beta': 1.1}}}))
    return folder


class FeatureSnapshotTests(unittest.TestCase):
    def test_records_raw_inputs_per_block_without_scores(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = fs.build(fixture(tmp), NOW, 'abc')
            self.assertEqual([r['symbol'] for r in s['records']], ['NASDAQ:ABC', 'NYSE:BK1'])
            recs = {r['symbol']: r for r in s['records']}
            b, c = recs['NYSE:BK1'], recs['NASDAQ:ABC']
            self.assertEqual(b['bank']['cet1Requirement'], .115)
            self.assertEqual(b['bank']['lcr'], 1.1)
            self.assertEqual(b['bank']['problemLoanRatio'], .0075)
            self.assertEqual([e['candidateId'] for e in b['confirmedEvents']], ['a'])
            self.assertEqual(b['market']['drawdown'], .05)
            self.assertEqual(c['price']['vol'], .3)
            self.assertEqual(c['sectorName'], 'Tech')
            self.assertIsNone(c['universe']['fair_value'], 'non-finite values become null')
            self.assertEqual(c['fundamentals']['publishedAt'], '2026-02-20')
            self.assertIsNone(c['fundamentals']['fields']['capex'])
            self.assertEqual(c['fundamentals']['market']['shares_out'], 5.0)
            self.assertNotIn('score', json.dumps(s['records']))
            self.assertEqual(s['sources']['fundamentals']['files'], 1)

    def test_first_snapshot_of_the_day_is_kept(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = fixture(tmp)
            target = folder / 'risk_observations' / 'features'
            first = fs.write_once(fs.build(folder, NOW), target, NOW)
            self.assertEqual(first['state'], 'recorded')
            later = NOW + dt.timedelta(hours=3)
            again = fs.write_once(fs.build(folder, later), target, later)
            self.assertEqual(again['state'], 'retained_first_daily_snapshot')
            saved = list(fs.load_snapshots(target))
            self.assertEqual(len(saved), 1)
            self.assertEqual(saved[0]['observedAt'], NOW.isoformat())
            self.assertNotIn('fair_value', saved[0]['records'][0].get('universe', {}), 'empty values are omitted')

    def test_stale_manifest_and_tampered_shard_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, 'stale'):
                fs.build(fixture(tmp, manifest_age_hours=40), NOW)
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, 'shard_hash'):
                fs.build(fixture(tmp, bad_hash=True), NOW)

    def test_compact_rounds_and_drops_empty(self):
        self.assertEqual(fs.compact({'a': 0.123456789, 'b': None, 'c': {}, 'd': [1.0000001], 'e': ''}), {'a': 0.123457, 'd': [1.0]})


if __name__ == '__main__':
    unittest.main()
