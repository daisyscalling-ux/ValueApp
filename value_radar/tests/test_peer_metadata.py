import unittest
from peer_metadata import metadata, export_metadata, coverage
class PeerMetadataTest(unittest.TestCase):
 def test_primary_only_when_confirmed(self):
  self.assertIsNone(metadata({})['primary_listing'])
  self.assertEqual(metadata({}, {'symbol':'NYSE:C','is_primary':True})['primary_listing'],'NYSE:C')
  self.assertIsNone(metadata({}, {'symbol':'OTC:ABC','is_primary':False})['primary_listing'])
 def test_preserves_business_and_identity(self):
  row=metadata({'industry':'Insurance','subIndustry':'Life Insurance','cik':'00042','isin':'US1234567890'})
  exported=export_metadata({**row,'name':'Complete corporate name','market_cap':100})
  self.assertEqual(exported['sub_industry'],'Life Insurance')
  self.assertEqual(exported['cik'],'00042')
  self.assertEqual(exported['name_full'],'Complete corporate name')
  self.assertEqual(coverage([exported,{}])['industry'],1)
if __name__=='__main__': unittest.main()

