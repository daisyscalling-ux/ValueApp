import datetime as dt,unittest
from regulatory_context import build_eu
NOW=dt.datetime(2026,11,10,tzinfo=dt.timezone.utc)
LEI='PQOH26KWDF7CG10L6792';SRC='https://errp.eba.europa.eu/public-documents/CODIS/input/x.zip'
CAP={'method':'eu-bank-capital-v1','banks':{},'sources':{'eba':{},'ecb':{}}}
MAP={'review_expires':'2027-05-08','banks':[],'pillar3Only':[{'lei':LEI,'isins':['AT0000652011'],'gleifName':'ERSTE GROUP BANK AG'}]}
KM1={'schema':1,'method':'eba-p3dh-km1-v1','importedAt':'2026-11-10T00:00:00Z','mappingReviewExpires':'2027-05-08','banks':{LEI:{'name':'ERSTE GROUP BANK AG','period':'2026-06-30','sourceUrl':SRC,'sourceFileSha256':'a'*64,
 'metrics':{'cet1_ratio':.152,'tier1_ratio':.17,'total_capital_ratio':.2,'leverage_ratio':.07},'lcr':1.48,'nsfr':1.3,'cet1Requirement':{'value':.117},
 'npl':{'ratio':.0212,'period':'2026-06-30','sourceUrl':'https://errp.eba.europa.eu/public-documents/FINDIS/input/x.zip','sourceFileSha256':'b'*64}}}}
ROW={'listing_symbol':'VIE:EBS','ticker':'EBS.VI','isin':'AT0000652011','currency':'EUR','security_type':'stock'}
class Pillar3Only(unittest.TestCase):
 def test_record_from_km1(self):
  r=build_eu({'kandidaten':[ROW]},CAP,MAP,NOW,km1=KM1)['stocks']['VIE:EBS']
  self.assertEqual((r['capitalSource'],r['metrics']['cet1_ratio']['sourceField'],r['liquidity']['reportedRatio'],r['capitalRequirement']['value']),('eba_p3dh_km1','P3DH:K_61.00/0050',1.48,.117))
  self.assertEqual((r['creditQuality']['method'],r['creditQuality']['ratio']),('eba-p3dh-cr1-npl-v1',.0212))
  bad={**KM1,'banks':{LEI:{**KM1['banks'][LEI],'npl':{**KM1['banks'][LEI]['npl'],'sourceUrl':'https://errp.eba.europa.eu/public-documents/CODIS/input/x.zip'}}}}
  self.assertIsNone(build_eu({'kandidaten':[ROW]},CAP,MAP,NOW,km1=bad)['stocks']['VIE:EBS']['creditQuality'])
 def test_missing_or_stale_km1_and_identity(self):
  self.assertEqual(build_eu({'kandidaten':[ROW]},CAP,MAP,NOW,km1={})['rejected'],{'VIE:EBS':'no_current_pillar3_km1_for_lei'})
  old={**KM1,'banks':{LEI:{**KM1['banks'][LEI],'period':'2025-12-31'}}}
  self.assertEqual(build_eu({'kandidaten':[ROW]},CAP,MAP,NOW,km1=old)['rejected'],{'VIE:EBS':'no_current_pillar3_km1_for_lei'})
  self.assertEqual(build_eu({'kandidaten':[{**ROW,'share_class':'preferred'}]},CAP,MAP,NOW,km1=KM1)['rejected'],{'VIE:EBS':'listing_identity_unverified'})
if __name__=='__main__':unittest.main()
