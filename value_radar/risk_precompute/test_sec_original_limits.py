import copy
import unittest
from sec_original_filings import document_date, parse, selected_tree, MAX_DOCUMENT_BYTES
from sec_cashflow_history import run
from test_sec_original_pipeline import FIX, META, original
from test_sec_cashflow_history import ROW, NOW, fixture
from test_sec_currency_concordance import coverage


class OriginalLimits(unittest.TestCase):
    def test_actual_apd_novartis_selected_facts(self):
        from sec_cashflow_history import normalize
        for name,cik,acc,filed,form,end in (
            ('apd',2969,'0000002969-25-000055','2025-11-20','10-K','2025-09-30'),
            ('nvs',1114448,'0001114448-26-000004','2026-02-04','20-F','2025-12-31')):
            meta=dict(accessionNumber=acc,filingDate=filed,form=form,reportDate=end)
            result=parse((FIX/(name+'-2025-selected.xhtml')).read_bytes(),cik,meta,'unused')
            periods=normalize(result,cik,NOW)
            self.assertEqual(len(periods),2)
            self.assertEqual(max(p['end'] for p in periods),end)

    def test_explicit_date_formats(self):
        for text, fmt, expected in (
            ('30 September 2025', 'date-day-monthname-year-en', '2025-09-30'),
            ('December 31, 2025', 'datemonthdayyearen', '2025-12-31'),
            ('December 31, 2025', 'date-monthname-day-year-en', '2025-12-31'),
            ('31 February 2025', 'date-day-monthname-year-en', None),
            ('09/10/2025', 'date-day-monthname-year-en', None),
            ('December 31, 2025', 'unreviewed', None)):
            self.assertEqual(document_date(text, fmt), expected)

    def test_large_prose_does_not_change_facts(self):
        raw=(FIX/'pdd-2025-selected.xhtml').read_bytes()
        position=raw.rfind(b'</')
        large=raw[:position]+b'<div>'+b'prose '*3_000_000+b'</div>'+raw[position:]
        self.assertGreater(len(large), 15_000_000)
        m=META['pdd']
        result=parse(large,m['cik'],m,'unused')
        self.assertEqual(result['facts'], original('pdd')['facts'])
        root,_=selected_tree(large)
        self.assertLess(sum(len(e.text or '') for e in root.iter()), 100_000)

    def test_size_ceiling_stays_enforced(self):
        with self.assertRaisesRegex(ValueError,'filing_too_large'):
            parse(b' '*(MAX_DOCUMENT_BYTES+1),1,{},'unused')

    def test_changed_namespace_still_rejected(self):
        with self.assertRaisesRegex(ValueError,'ambiguous_namespace'):
            selected_tree(b'<a xmlns:x="one"><b xmlns:x="two"/></a>')

    def test_policy_retry_only_once_and_only_affected_cache(self):
        def collect(state):
            return run({'kandidaten':[ROW]},coverage(),state,{'NASDAQ:EX':'1'},lambda *a:fixture(),NOW)
        base=collect({})
        for error in ('filing_metadata_mismatch','response_too_large','filing_too_large'):
            state=copy.deepcopy(base)
            state['attempts'][ROW['listing_symbol']].update(policy='old',originalError=error)
            result=collect(state)
            self.assertEqual(result['report']['attempted'],1)
            self.assertEqual(collect(result)['report']['cached'],1)
        state=copy.deepcopy(base)
        state['attempts'][ROW['listing_symbol']].update(policy='old',originalError='filing_cik_mismatch')
        self.assertEqual(collect(state)['report']['cached'],1)
