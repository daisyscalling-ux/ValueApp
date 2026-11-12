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


class CarriedDefinitionTests(unittest.TestCase):
    """Ohne neues Woerterbuch: Definitionen aus einem frueheren, gegen das Woerterbuch geprueften Import (12.11.2026)."""
    def previous(self):
        import import_bhcf as ib
        defs = {code: {'metric': m, 'description': d + ' (BHC CONSOLIDATED)', 'sheet': 'Financial', 'row': 1, 'valid_from': '2015-03-31',
                       'valid_to': '9999-12-31', 'source_unit': 'percent', 'unit': 'fraction'} for code, (m, d) in ib.FIELDS.items()}
        return {'reporting_period': '2026-06-30', 'imported_at': '2026-10-30T13:56:52+00:00', 'definitions': defs,
                'files': [{'name': 'BHCF20260630.ZIP', 'sha256': 'a' * 64}, {'name': 'Financial_Download_Dictionary.xlsx', 'sha256': 'b' * 64}]}

    def test_carried_definitions_keep_reviewed_dictionary_hash(self):
        import datetime as dt, import_bhcf as ib
        defs, origin = ib.carried_definitions(self.previous(), dt.date(2026, 9, 30), ib.FIELDS, ('unit', 'source_unit'))
        self.assertEqual(set(defs), set(ib.FIELDS))
        self.assertEqual(origin['kind'], 'previous_reviewed_import'); self.assertEqual(origin['dictionary_sha256'], 'b' * 64)

    def test_carried_definitions_chain_over_two_quarters(self):
        import datetime as dt, import_bhcf as ib
        p = self.previous(); defs, origin = ib.carried_definitions(p, dt.date(2026, 6, 30), ib.FIELDS, ('unit', 'source_unit'))
        second = {'reporting_period': '2026-06-30', 'definitions': defs, 'definitions_source': origin, 'files': [{'name': 'BHCF20260630.ZIP', 'sha256': 'c' * 64}]}
        self.assertEqual(ib.carried_definitions(second, dt.date(2026, 9, 30), ib.FIELDS, ('unit', 'source_unit'))[1]['dictionary_sha256'], 'b' * 64)

    def test_carried_definitions_rejections(self):
        import datetime as dt, import_bhcf as ib
        code = next(iter(ib.FIELDS))
        cases = {'incomplete': lambda p: p['definitions'].pop(code),
                 'metric': lambda p: p['definitions'][code].update(metric='other'),
                 'description': lambda p: p['definitions'][code].update(description='SOMETHING ELSE'),
                 'period': lambda p: p['definitions'][code].update(valid_to='2026-03-31'),
                 'unit': lambda p: p['definitions'][code].pop('source_unit'),
                 'no dictionary hash': lambda p: p.update(files=p['files'][:1])}
        for label, change in cases.items():
            p = self.previous(); change(p)
            with self.assertRaises(ValueError, msg=label):
                ib.carried_definitions(p, dt.date(2026, 6, 30), ib.FIELDS, ('unit', 'source_unit'))
