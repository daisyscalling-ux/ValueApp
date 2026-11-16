import datetime as dt,json,tempfile,unittest
from pathlib import Path
import review_deadlines as R

class Deadlines(unittest.TestCase):
 def test_explicit_and_derived_deadlines_sorted_and_windowed(self):
  with tempfile.TemporaryDirectory() as d:
   d=Path(d);(d/'regulatory_export').mkdir();(d/'daten/regulatory').mkdir(parents=True);(d/'risk_precompute').mkdir()
   (d/'regulatory_export/fed.json').write_text(json.dumps({'reviewExpires':'2026-12-31','entries':[]}))
   (d/'regulatory_export/eu.json').write_text(json.dumps({'km1UnitCorrections':[{'issuer':'Crédit Agricole S.A.','reviewExpires':'2026-12-31'}]}))
   (d/'risk_precompute/reviewed-x.json').write_text(json.dumps({'entries':[{'symbol':'A:B','review_expires':'2027-09-01'}]}))
   (d/'daten/regulatory/intl-bank-metrics.json').write_text(json.dumps({'mappingReviewExpires':'2027-05-08','issuers':{'JP1':{'issuer':'MUFG','period':'2026-06-30','creditPeriod':'2026-03-31'}}}))
   (d/'regulatory_export/broken.json').write_text('{kaputt')
   items=R.collect(d)
   self.assertEqual([x['expires'].isoformat() for x in items],['2026-12-26','2026-12-31','2026-12-31','2027-03-27','2027-05-08','2027-09-01'])
   cr1=items[0];self.assertIn('MUFG: Kreditqualität (CR1), Stichtag 2026-03-31',cr1['what']);self.assertEqual(cr1['kind'],'Stichtag + 270 Tage')
   self.assertTrue(any('fed.json' in x['what'] for x in items),'top-level entry named by its file')
   due=R.due(items,dt.date(2026,11,16),60);self.assertEqual(len(due),3)
   md=R.markdown(due,dt.date(2026,11,16));self.assertIn('| 2026-12-26 | 40 |',md)

if __name__=='__main__':unittest.main()
