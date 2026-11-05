"""Selected original filings plus malformed continuation regression cases."""
import datetime as dt
import json
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET
from sec_original_filings import parse,document_date,metadata_text,IX
from sec_cashflow_history import normalize

FIX=Path(__file__).parent/'fixtures'
META=json.loads((FIX/'sec-date-selected-metadata.json').read_text())
NOW=dt.datetime(2026,11,5,tzinfo=dt.timezone.utc)


class MetadataDates(unittest.TestCase):
    def test_actual_filings_recover_seven_periods(self):
        expected={'cprt':[('2024-07-31',1472564000,510990000),('2025-07-31',1799750000,568990000),('2026-07-31',1604492000,337363000)],
            'cmi':[('2024-12-31',1487000000,1208000000),('2025-12-31',3621000000,1235000000)],
            'hlt':[('2024-12-31',2013000000,96000000),('2025-12-31',2129000000,101000000)]}
        for name,meta in META.items():
            raw=(FIX/(name+'-date-selected.xhtml')).read_bytes()
            result=parse(raw,meta['cik'],meta,'unused')
            rows=normalize(result,meta['cik'],NOW)
            self.assertEqual([(r['end'],r['operatingCashflow'],r['cashPpe']) for r in rows],expected[name])
            with self.assertRaisesRegex(ValueError,'filing_metadata_mismatch'):
                parse(raw,meta['cik'],{**meta,'reportDate':'2020-01-01'},'unused')

    def test_numeric_order_requires_explicit_transform(self):
        self.assertEqual(document_date('03/04/2025','date-month-day-year'),'2025-03-04')
        self.assertEqual(document_date('03/04/2025','date-day-month-year'),'2025-04-03')
        for sep in ('/','.','-',' '):
            self.assertEqual(document_date(sep.join(['12','31','2025']),'date-month-day-year'),'2025-12-31')
        for text,fmt in [('12/31/2025',''),('12/31/2025','unknown'),('02/30/2025','date-month-day-year'),('13/01/2025','date-month-day-year'),('12/31/25','date-month-day-year')]:
            self.assertIsNone(document_date(text,fmt))

    def node(self,text,**attrs):
        e=ET.Element('{'+IX+'}continuation',attrs);e.text=text;return e

    def test_chained_metadata_excludes_nonfact_text(self):
        first=self.node('July',continuedAt='one')
        skip=ET.SubElement(first,'{'+IX+'}exclude');skip.text='wrong';skip.tail=' 31'
        self.assertEqual(metadata_text(first,{'one':self.node(', ',continuedAt='two'),'two':self.node('2026')}),'July 31, 2026')

    def test_missing_duplicate_and_cyclic_continuations_rejected(self):
        first=self.node('July 31',continuedAt='one')
        for refs in ({},{'one':None},{'one':self.node(', 2026',continuedAt='one')}):
            with self.assertRaisesRegex(ValueError,'invalid_metadata_continuation'):metadata_text(first,refs)

    def test_chain_and_text_limits(self):
        refs={str(i):self.node(' ',continuedAt=str(i+1)) for i in range(20)}
        for first,chain in [(self.node('',continuedAt='0'),refs),(self.node('x'*513),{})]:
            with self.assertRaisesRegex(ValueError,'invalid_metadata_continuation'):metadata_text(first,chain)

    def test_linked_annual_keeps_primary_metadata_continuations(self):
        from test_sec_linked_annual import PRIMARY,FINANCIAL,NAME,META as IBM,URL
        from sec_linked_annual import parse_linked
        raw=PRIMARY.replace(b'id="f-4"',b'id="f-4" continuedAt="annual-date"')
        raw=raw.replace(b', 2025</ix:nonNumeric>',b'</ix:nonNumeric>')
        raw=raw.replace(b'</body>',b'<ix:continuation id="annual-date">, 2025</ix:continuation></body>')
        result=parse_linked(raw,FINANCIAL,NAME,51143,IBM,URL)
        self.assertEqual(len(normalize(result,51143,NOW)),2)

    def test_duplicate_copart_continuation_is_rejected_by_parser(self):
        meta=META['cprt'];raw=(FIX/'cprt-date-selected.xhtml').read_bytes()
        import re
        identifier=re.search(br'continuedAt="([^"]+)"',raw).group(1)
        duplicate=b'<ix:continuation id="'+identifier+b'">, 2026</ix:continuation>'
        with self.assertRaisesRegex(ValueError,'invalid_metadata_continuation'):
            parse(raw.replace(b'</body>',duplicate+b'</body>'),meta['cik'],meta,'unused')


if __name__=='__main__':unittest.main()
