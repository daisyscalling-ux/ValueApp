import datetime as dt
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import Mock, patch

import index_membership as im
from export_continuity import guard

NOW = dt.datetime(2026, 11, 10, 12, tzinfo=dt.timezone.utc)
SYMS = ['A' + chr(65 + i // 26) + chr(65 + i % 26) for i in range(503)]


def html(symbols, table_id='constituents'):
    rows = ''.join(f'<tr><td>{s}</td><td>Name {s}</td></tr>' for s in symbols)
    return f'<html><body><table id="{table_id}"><tr><th>Symbol</th><th>Security</th></tr>{rows}</table></body></html>'


def fixed(tmp, symbols, stand='2026-11-10'):
    p = Path(tmp) / 'sp500_liste.txt'
    p.write_text(f'# Quelle\n# Stand: {stand}\n' + '\n'.join(symbols) + '\n', encoding='utf-8')
    return p


class Sp500Tests(unittest.TestCase):
    def test_wikipedia_table_with_descriptive_user_agent(self):
        seen = {}
        def fetcher(url):
            seen['url'] = url
            return html(SYMS[:500] + ['BRK.B', 'BF.B', 'MMM']).encode()
        with tempfile.TemporaryDirectory() as tmp:
            out, src = im.sp500_members(fetcher, fixed(tmp, SYMS), NOW)
        self.assertEqual(src['kind'], 'wikipedia'); self.assertEqual(len(out), 503)
        self.assertIn('BRK-B', out); self.assertEqual(len(src['sha256']), 64)
        self.assertNotIn('Mozilla', im.USER_AGENT); self.assertNotIn('@', im.USER_AGENT)

    def test_http_403_falls_back_to_dated_fixed_list_never_screener(self):
        def fetcher(url):
            raise urllib.error.HTTPError(url, 403, 'Forbidden', None, None)
        with tempfile.TemporaryDirectory() as tmp:
            out, src = im.sp500_members(fetcher, fixed(tmp, SYMS), NOW)
        self.assertEqual(src['kind'], 'fixed_list'); self.assertEqual(src['wikipediaFailure'], 'wikipedia_403'); self.assertEqual(len(out), 503)

    def test_truncated_or_wrong_table_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = fixed(tmp, SYMS)
            out, src = im.sp500_members(lambda u: html(SYMS[:300]).encode(), p, NOW)
            self.assertEqual((src['kind'], src['wikipediaFailure']), ('fixed_list', 'wikipedia_table_invalid'))
            out, src = im.sp500_members(lambda u: html(SYMS, 'other').encode(), p, NOW)
            self.assertEqual(src['kind'], 'fixed_list')
            out, src = im.sp500_members(lambda u: html(SYMS[:500] + ['not a symbol!', 'X1', 'X2']).encode(), p, NOW)
            self.assertEqual(src['kind'], 'fixed_list', 'implausible symbol')

    def test_stale_undated_or_short_fixed_list_gives_empty_result(self):
        fail = lambda u: (_ for _ in ()).throw(OSError('offline'))
        with tempfile.TemporaryDirectory() as tmp:
            out, src = im.sp500_members(fail, fixed(tmp, SYMS, '2026-06-01'), NOW)
            self.assertEqual((out, src['kind'], src['fixedListProblem']), ([], 'unavailable', 'fixed_list_stale'))
            p = Path(tmp) / 'x.txt'; p.write_text('\n'.join(SYMS), encoding='utf-8')
            self.assertEqual(im.sp500_members(fail, p, NOW)[1]['fixedListProblem'], 'fixed_list_undated')
            self.assertEqual(im.sp500_members(fail, fixed(tmp, SYMS[:200]), NOW)[1]['fixedListProblem'], 'fixed_list_invalid')
            self.assertEqual(im.sp500_members(fail, Path(tmp) / 'missing.txt', NOW)[1]['fixedListProblem'], 'fixed_list_missing')

    def test_repository_fixed_list_is_valid(self):
        out, stand = im.read_fixed_list(im.HERE / 'sp500_liste.txt', dt.date(2026, 11, 10))
        self.assertTrue(500 <= len(out) <= 506, len(out)); self.assertEqual(stand, '2026-11-10')


def row(t, sym=None):
    return dict(ticker=t, listing_symbol=sym or 'NYSE:' + t, isin='US0000000001', currency='USD', price=10)


def doc(rows, scope=None):
    d = dict(stand='2026-11-10 12:00 UTC', kandidaten=rows)
    if scope is not None:
        d['index_scope'] = scope
    return d


def full_scope(members):
    counts = dict(im.MIN_MEMBERS)
    return {'method': im.METHOD, 'complete': True, 'counts': counts, 'members': members}


class GuardTests(unittest.TestCase):
    def setUp(self):
        self.members = ['M' + str(i) for i in range(1000)]
        self.otc = ['O' + str(i) for i in range(300)]
        self.old = doc([row(t) for t in self.members] + [row(t, 'OTC:' + t) for t in self.otc])

    def test_non_members_may_leave_with_complete_scope(self):
        new = doc([row(t) for t in self.members], full_scope({t: ['SP500'] for t in self.members}))
        guard(self.old, new)

    def test_without_scope_the_ten_percent_rule_still_blocks(self):
        with self.assertRaisesRegex(ValueError, 'coverage regression'):
            guard(self.old, doc([row(t) for t in self.members]))

    def test_incomplete_or_wrong_scope_blocks(self):
        rows = [row(t) for t in self.members]
        members = {t: ['SP500'] for t in self.members}
        for bad in [{**full_scope(members), 'complete': False}, {**full_scope(members), 'method': 'other'},
                    {**full_scope(members), 'counts': {**im.MIN_MEMBERS, 'SP500': 300}}]:
            with self.assertRaises(ValueError):
                guard(self.old, doc(rows, bad))

    def test_removing_index_members_still_counts(self):
        keep = self.members[:800]
        new = doc([row(t) for t in keep], full_scope({t: ['SP500'] for t in self.members}))
        with self.assertRaisesRegex(ValueError, 'coverage regression'):
            guard(self.old, new)


class ExportTaggingTests(unittest.TestCase):
    def test_rows_carry_index_membership_and_scope(self):
        import export_cf
        roic = Mock(); roic.export_universum.return_value = ['AAA', 'BP.L', 'ZZZ']; roic.enabled.return_value = True
        roic.export_scope.return_value = {'method': im.METHOD, 'complete': True, 'counts': {}, 'members': {'AAA': ['SP500', 'NDX'], 'BP.L': ['STOXX600']}}
        precompute = Mock(); precompute.PENCE_ZU_ADR = {'BP.L': 'BP'}
        precompute.ersetze_pence_durch_adr.side_effect = lambda x: [precompute.PENCE_ZU_ADR.get(t, t) for t in x]
        precompute.filter_boersen.side_effect = lambda x: x
        precompute.collapse_listings.side_effect = lambda x: x
        precompute.score_ticker.side_effect = lambda t, deep=True: {'ticker': t, 'price': 1, 'listing_symbol': None}
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'out.json'
            with patch.dict('sys.modules', {'roic': roic, 'precompute': precompute}), patch.object(export_cf, 'AUSGABE', target), \
                    patch.object(export_cf, 'snapshots', return_value=[]), patch.object(export_cf, 'apply_reference', side_effect=lambda r: r):
                self.assertEqual(export_cf.main(), 0)
            data = json.loads(target.read_text())
        rows = {r['ticker']: r['index_membership'] for r in data['kandidaten']}
        self.assertEqual(rows, {'AAA': ['SP500', 'NDX'], 'BP': ['STOXX600'], 'ZZZ': []})
        self.assertEqual(data['index_scope']['method'], im.METHOD)
        self.assertEqual(data['index_scope']['members'], {'AAA': ['SP500', 'NDX'], 'BP': ['STOXX600']})


class ScopeTests(unittest.TestCase):
    def test_scope_counts_and_completeness(self):
        s = im.scope({'SP500': SYMS, 'NDX': SYMS[:100], 'STOXX600': ['S' + str(i) for i in range(600)],
                      'NIKKEI225': ['N' + str(i) for i in range(225)], 'DAX': ['D' + str(i) for i in range(40)]}, {}, NOW)
        self.assertTrue(s['complete']); self.assertEqual(s['members'][SYMS[0]], ['SP500', 'NDX'])
        self.assertTrue(im.scope_complete({'index_scope': s}))
        s2 = im.scope({'SP500': SYMS, 'NDX': [], 'STOXX600': [], 'NIKKEI225': [], 'DAX': []}, {}, NOW)
        self.assertFalse(s2['complete']); self.assertFalse(im.scope_complete({'index_scope': s2}))


class CollapseTests(unittest.TestCase):
    PRIO = {'DE': 1, 'F': 2, 'L': 10, 'XC': 60}

    def test_only_same_country_listings_merge(self):
        out = im.collapse_same_market(['AMZ.F', 'AMZ.DE', 'BHPL.XC', 'BHP.L'], self.PRIO)
        self.assertEqual(out, ['AMZ.DE', 'BHP.L'])

    def test_us_ticker_never_displaces_foreign_index_member(self):
        for us, foreign in [('DTE', 'DTE.DE'), ('MRK', 'MRK.DE'), ('AIR', 'AIR.PA'), ('SAN', 'SAN.MC'), ('PRU', 'PRU.L'), ('ASML', 'ASML.AS')]:
            self.assertEqual(im.collapse_same_market([foreign, us], self.PRIO), [foreign, us])
            self.assertEqual(im.collapse_same_market([us, foreign], self.PRIO), [us, foreign])


if __name__ == '__main__':
    unittest.main()
