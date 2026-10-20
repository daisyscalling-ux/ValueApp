import datetime as dt
import io
import unittest
import json
from pathlib import Path
from import_bhcf import FIELDS, ratio, parse_stream, link_fdic

class BHCFTests(unittest.TestCase):
    def test_imported_snapshot_integrity(self):
        root = Path(__file__).resolve().parent
        path = root.parent / 'daten/regulatory/bhcf-import.json'
        if not path.exists():
            path = root / 'live/bhcf-import.json'
        data = json.loads(path.read_text(encoding='utf8'))
        self.assertEqual(data['schema'], 1)
        self.assertEqual(data['entity_count'], len(data['entities']))
        self.assertEqual(data['source_row_count'], data['entity_count'] + data['rows_without_capital_ratios'])
        self.assertEqual(set(data['definitions']), set(FIELDS))
        for rssd, entity in data['entities'].items():
            self.assertEqual(rssd, entity['rssd_id'])
            for code, metric in entity['metrics'].items():
                self.assertIn(code, FIELDS)
                self.assertEqual(metric, ratio(metric['raw_value']))
        self.assertFalse(data['historical_point_in_time_usable'])

    def test_units_missing_zero_and_invalid(self):
        self.assertAlmostEqual(ratio('14.1913')['value'], .141913)
        self.assertEqual(ratio('0')['value'], 0)
        self.assertEqual(ratio(0)['value'], 0)
        self.assertEqual(ratio('-1')['value'], -.01)
        self.assertIsNone(ratio('')['value'])
        for raw in ['NaN','Infinity','not reported','1001']:
            self.assertEqual(ratio(raw)['state'], 'invalid')

    def stream(self, rows):
        return io.StringIO('RSSD9001^RSSD9999^RSSD9017^'+'^'.join(FIELDS)+'\n'+'\n'.join(rows))

    def test_consolidated_code_and_empty_rows(self):
        rows,total,missing = parse_stream(self.stream(['1^20260630^Holding^14^15^17^6','2^20260630^Small^^^^']), dt.date(2026,6,30), dt.date(2026,10,19))
        self.assertEqual((total,missing,len(rows)), (2,1,1))
        self.assertEqual(rows['1']['metrics']['BHCAP793']['value'], .14)
        self.assertEqual(rows['1']['metrics']['BHCA7206']['value'], .15)

    def test_duplicate_mixed_future_and_truncated_rejected(self):
        row = '1^20260630^Holding^14^15^17^6'
        for rows in [[row,row], [row.replace('20260630','20260331')], [row[:-2]], []]:
            with self.assertRaises(ValueError):
                parse_stream(self.stream(rows),dt.date(2026,6,30),dt.date(2026,10,19))
        with self.assertRaises(ValueError):
            parse_stream(self.stream([row]),dt.date(2026,6,30),dt.date(2026,1,1))

    def test_links_use_identifiers_not_names_and_never_stock_mapping(self):
        holdings={'reporting_period':'2026-06-30','scope':'FR_Y9C_consolidated_reporting_entity','entities':{'1':{'name':'Holding'}}}
        fdic={'institutions':{'10':{'holding_rssd_id':'1','period':'2026-06-30'},'20':{'holding_name':'Holding','holding_rssd_id':'2','period':'2026-06-30'}}}
        result=link_fdic(holdings,fdic,dt.date(2027,1,1))
        self.assertEqual(result['linked_institutions'],1)
        self.assertEqual(result['freshness'],'stale')
        self.assertFalse(result['stock_identity_verified'])
        self.assertIsNone(result['score'])

if __name__ == '__main__': unittest.main()
