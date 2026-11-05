import copy
import datetime as dt
import json
import unittest
from pathlib import Path
from sec_linked_annual import annual_link,parse_linked
from sec_cashflow_history import normalize
from sec_original_supply import loader,verified_original

FIX=Path(__file__).parent/'fixtures'
PRIMARY=(FIX/'ibm-2025-primary-selected.xhtml').read_bytes()
FINANCIAL=(FIX/'ibm-2025-financial-selected.xhtml').read_bytes()
META=dict(accessionNumber='0000051143-26-000010',filingDate='2026-02-24',reportDate='2025-12-31',form='10-K',primaryDocument='ibm-20251231.htm')
URL='https://www.sec.gov/Archives/edgar/data/51143/000005114326000010/ibm-20251231.htm'
NAME='ibm-20251231_d2.htm'
NOW=dt.datetime(2026,11,5,tzinfo=dt.timezone.utc)


class LinkedAnnual(unittest.TestCase):
    def parsed(self,primary=PRIMARY,financial=FINANCIAL):
        return parse_linked(primary,financial,NAME,51143,META,URL)

    def test_selected_original_shared_contexts_and_units(self):
        rows=normalize(self.parsed(),51143,NOW)
        self.assertEqual([(r['end'],r['operatingCashflow'],r['cashPpe']) for r in rows],
            [('2024-12-31',13445000000,1048000000),('2025-12-31',13193000000,1091000000)])
        self.assertTrue(all(verified_original(r,51143) for r in rows))

    def test_link_requires_unique_explicit_relative_annual_document(self):
        for href in ['https://example.com/annual.htm','../annual.htm','annual.htm?x=1','annual.pdf']:
            self.assertIsNone(annual_link(('<a href="'+href+'">Annual Report to Security Holders</a>').encode()))
        self.assertIsNone(annual_link(b'<a href="one.htm">Annual Report</a>'))
        self.assertIsNone(annual_link(PRIMARY.replace(b'</body>',b'<a href="other.htm">Annual Report to Security Holders</a></body>')))

    def test_wrong_primary_identity_or_period_rejected(self):
        for raw in [PRIMARY.replace(b'0000051143',b'0000051144'),PRIMARY.replace(b', 2025',b', 2024')]:
            self.assertNotEqual(raw,PRIMARY)
            with self.assertRaises(ValueError):self.parsed(primary=raw)

    def test_unknown_link_and_unsafe_companion_rejected(self):
        with self.assertRaisesRegex(ValueError,'annual_link_mismatch'):
            self.parsed(primary=PRIMARY.replace(NAME.encode(),b'other.htm'))
        with self.assertRaisesRegex(ValueError,'unsafe_linked_xml'):
            self.parsed(financial=b'<!DOCTYPE x>'+FINANCIAL)

    def test_conflicting_namespace_rejected(self):
        with self.assertRaisesRegex(ValueError,'linked_namespace_conflict'):
            self.parsed(financial=FINANCIAL.replace(b'http://fasb.org/us-gaap/2025',b'http://fasb.org/us-gaap/2024'))

    def test_provenance_cannot_point_to_other_accession_or_host(self):
        row=normalize(self.parsed(),51143,NOW)[0]
        for key,value in [('sourceUrl','https://example.com/file.htm'),('distributionUrl','https://example.com/file.htm'),('sha256','bad'),('filename','../file.htm')]:
            changed=copy.deepcopy(row);changed['originalFiling']['linkedAnnualDocument'][key]=value
            self.assertFalse(verified_original(changed,51143))

    def test_loader_fetches_only_one_explicit_companion(self):
        calls=[]
        def transport(url,timeout,limit):
            calls.append(url)
            if 'submissions' in url:return json.dumps({'cik':51143,'filings':{'recent':{k:[v] for k,v in META.items()}}}).encode()
            return FINANCIAL if url.endswith(NAME) else PRIMARY
        result=loader('operator',[],NOW,transport)(51143,30)
        self.assertEqual(len(calls),3)
        self.assertEqual(calls[-1],URL.rsplit('/',1)[0]+'/'+NAME)
        self.assertEqual(len(normalize(result,51143,NOW)),2)


if __name__=='__main__':unittest.main()
