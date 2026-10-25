import copy,datetime as dt,io,unittest,zipfile
from edinet_cashflow import parse_xml,parse_zip
from edinet_supply import run,eligible,select_doc,sec_code
from roic_risk_annual import identity
NOW=dt.datetime(2026,10,24,12,tzinfo=dt.timezone.utc)
ROW={'listing_symbol':'TSE:7974','ticker':'7974.T','isin':'JP3756600007','currency':'JPY'}
DOC={'docID':'S100TEST','edinetCode':'E00001','secCode':'79740','docTypeCode':'120','periodStart':'2025-04-01','periodEnd':'2026-03-31','submitDateTime':'2026-06-20 10:00','xbrlFlag':'1','withdrawalStatus':'0','disclosureStatus':'0','docInfoEditStatus':'0','indexDate':'2026-06-20'}
def xml():
 return '''<xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance" xmlns:iso4217="http://www.xbrl.org/2003/iso4217" xmlns:j="http://disclosure.edinet-fsa.go.jp/taxonomy/jpigp/2025-11-01/jpigp_cor" xmlns:d="http://disclosure.edinet-fsa.go.jp/taxonomy/jpdei/2013-08-31/jpdei_cor" xmlns:xbrldi="http://xbrl.org/2006/xbrldi">
 <d:EDINETCodeDEI>E00001</d:EDINETCodeDEI><d:WhetherConsolidatedFinancialStatementsArePreparedDEI>true</d:WhetherConsolidatedFinancialStatementsArePreparedDEI>
 <xbrli:context id="I"><xbrli:entity><xbrli:identifier scheme="http://disclosure.edinet-fsa.go.jp">E00001-000</xbrli:identifier></xbrli:entity><xbrli:period><xbrli:instant>2026-03-31</xbrli:instant></xbrli:period></xbrli:context>
 <xbrli:context id="D"><xbrli:entity><xbrli:identifier scheme="http://disclosure.edinet-fsa.go.jp">E00001-000</xbrli:identifier></xbrli:entity><xbrli:period><xbrli:startDate>2025-04-01</xbrli:startDate><xbrli:endDate>2026-03-31</xbrli:endDate></xbrli:period></xbrli:context>
 <xbrli:unit id="JPY"><xbrli:measure>iso4217:JPY</xbrli:measure></xbrli:unit>
 <j:AssetsIFRS contextRef="I" unitRef="JPY" decimals="-6">100000000</j:AssetsIFRS>
 <j:CashAndCashEquivalentsIFRS contextRef="I" unitRef="JPY">20000000</j:CashAndCashEquivalentsIFRS>
 <j:NetCashProvidedByUsedInOperatingActivitiesIFRS contextRef="D" unitRef="JPY">10000000</j:NetCashProvidedByUsedInOperatingActivitiesIFRS>
 <j:PurchaseOfPropertyPlantAndEquipmentInvCFIFRS contextRef="D" unitRef="JPY">-3000000</j:PurchaseOfPropertyPlantAndEquipmentInvCFIFRS>
 <j:PurchaseOfIntangibleAssetsInvCFIFRS contextRef="D" unitRef="JPY">-1000000</j:PurchaseOfIntangibleAssetsInvCFIFRS>
 </xbrli:xbrl>'''
def zipped(raw=None):
 b=io.BytesIO()
 with zipfile.ZipFile(b,'w') as z:z.writestr('XBRL/PublicDoc/report.xbrl',raw or xml())
 return b.getvalue()
def index():
 return {'schema':1,'days':{str(NOW.date()-dt.timedelta(days=i)):{'checkedAt':NOW.isoformat(),'documents':[DOC] if str(NOW.date()-dt.timedelta(days=i))==DOC['indexDate'] else []} for i in range(461)},'stocks':{},'attempts':{}}
def coverage():return {'generatedAt':NOW.isoformat(),'stocks':[{'symbol':ROW['listing_symbol'],'domains':{'balance':{'state':'partial'}}}]}
class Parser(unittest.TestCase):
 def test_scale_and_signed_outflow(self):
  a=parse_zip(zipped(),DOC,NOW);self.assertEqual(a['state'],'available');self.assertEqual(a['fields']['total_assets'],100000000);self.assertEqual(a['fields']['capex'],4000000);self.assertEqual(a['fcfAssets'],.06)
 def test_missing_intangible_is_not_zero(self):
  raw=xml().replace('-1000000','')
  a=parse_xml(raw.encode(),DOC,NOW);self.assertIsNone(a['fields']['capex']);self.assertEqual(a['state'],'partial')
 def test_explicit_zero(self):
  a=parse_xml(xml().replace('-1000000','0').encode(),DOC,NOW);self.assertEqual(a['fields']['capex'],3000000)
 def test_positive_outflows_rejected(self):
  a=parse_xml(xml().replace('-3000000','3000000').encode(),DOC,NOW);self.assertIsNone(a['fields']['capex'])
 def test_wrong_period_cannot_supply_cashflow(self):
  a=parse_xml(xml().replace('<xbrli:startDate>2025-04-01','<xbrli:startDate>2025-10-01').encode(),DOC,NOW);self.assertIsNone(a['fields']['capex'])
 def test_consolidation_and_issuer_required(self):
  for old,new,err in [('>true<','>false<','consolidation_unconfirmed'),('>E00001<','>E00002<','issuer_unconfirmed')]:
   with self.assertRaisesRegex(ValueError,err):parse_xml(xml().replace(old,new).encode(),DOC,NOW)
 def test_nonconsolidated_or_segment_context_excluded(self):
  raw=xml().replace('</xbrli:context>','<xbrli:scenario><xbrldi:explicitMember dimension="d:Axis">d:NonConsolidatedMember</xbrldi:explicitMember></xbrli:scenario></xbrli:context>')
  with self.assertRaisesRegex(ValueError,'unsupported_taxonomy'):parse_xml(raw.encode(),DOC,NOW)
 def test_duplicate_facts_conflict(self):
  raw=xml().replace('</xbrli:xbrl>','<j:AssetsIFRS contextRef="I" unitRef="JPY">999</j:AssetsIFRS></xbrli:xbrl>')
  a=parse_xml(raw.encode(),DOC,NOW);self.assertIn('total_assets',a['conflicts']);self.assertIsNone(a['fcfAssets'])
 def test_wrong_currency_namespace_and_extensions_rejected(self):
  for old,new in [('iso4217:JPY','iso4217:USD'),('http://www.xbrl.org/2003/iso4217','http://wrong.test'),('jpigp/2025-11-01/jpigp_cor','custom/2025-11-01/custom_cor')]:
   with self.assertRaises(ValueError):parse_xml(xml().replace(old,new).encode(),DOC,NOW)
 def test_xml_entity_and_ambiguous_zip_rejected(self):
  with self.assertRaisesRegex(ValueError,'unsafe_xml'):parse_xml(b'<!DOCTYPE x><x/>',DOC,NOW)
  b=io.BytesIO()
  with zipfile.ZipFile(b,'w') as z:
   for n in ('a','b'):z.writestr('XBRL/PublicDoc/'+n+'.xbrl',xml())
  with self.assertRaisesRegex(ValueError,'ambiguous_public_instance'):parse_zip(b.getvalue(),DOC,NOW)
class Supply(unittest.TestCase):
 def test_listing_and_doc_identity(self):
  self.assertEqual(sec_code(ROW),'79740');self.assertIsNone(sec_code({**ROW,'isin':'invalid'}))
  for field,value in [('secCode','99990'),('withdrawalStatus','1'),('disclosureStatus','1'),('docTypeCode','140'),('xbrlFlag','0'),('submitDateTime','2027-01-01 10:00')]:self.assertFalse(eligible({**DOC,field:value},'79740',NOW))
 def test_newest_revision_and_ambiguous_filer(self):
  correction={**DOC,'docTypeCode':'130','docID':'S100TWO1','submitDateTime':'2026-07-01 10:00'}
  self.assertEqual(select_doc([DOC,correction],'79740',NOW)['docID'],'S100TWO1')
  with self.assertRaisesRegex(ValueError,'ambiguous_filer'):select_doc([DOC,{**correction,'edinetCode':'E00002'}],'79740',NOW)
 def test_run_uses_cached_index_and_checkpoints(self):
  saves=[]
  s=run({'kandidaten':[ROW]},coverage(),index(),lambda d:self.fail('cached index'),lambda d:zipped(),NOW,checkpoint=lambda s:saves.append(copy.deepcopy(s)))
  self.assertEqual(s['report']['completeCashflows'],1);self.assertTrue(saves);self.assertEqual(s['stocks'][ROW['listing_symbol']]['annual']['fields']['capex'],4000000)
  run({'kandidaten':[ROW]},coverage(),s,lambda d:self.fail('cache'),lambda d:self.fail('cooldown'),NOW)
 def test_missing_coverage_stops_and_identity_change_removes(self):
  state=index();state['stocks'][ROW['listing_symbol']]={'inputIdentity':{**identity(ROW),'isin':'changed'}}
  s=run({'kandidaten':[ROW]}, {},state,lambda d:self.fail(),lambda d:self.fail(),NOW)
  self.assertFalse(s['stocks']);self.assertEqual(s['report']['stopped'],'coverage_missing_or_stale')
 def test_failed_download_preserves_original_age(self):
  state=index();state['stocks'][ROW['listing_symbol']]={'inputIdentity':identity(ROW),'retrievedAt':'2026-10-01T00:00:00Z'}
  def fail(d):raise TimeoutError('SECRET')
  s=run({'kandidaten':[ROW]},coverage(),state,lambda d:self.fail('cache'),fail,NOW)
  self.assertEqual(s['stocks'][ROW['listing_symbol']]['retrievedAt'],'2026-10-01T00:00:00Z');self.assertNotIn('SECRET',str(s))
 def test_cold_start_stops_on_auth_and_saves_report(self):
  import urllib.error
  def fail(d):raise urllib.error.HTTPError('url?secret',403,'secret',{},None)
  s=run({'kandidaten':[ROW]},coverage(),{},fail,lambda d:self.fail(),NOW)
  self.assertEqual(s['report']['stopped'],'index_access_or_budget');self.assertNotIn('secret',str(s))

class AdditionalSupplyTests(unittest.TestCase):
 def test_unavailable_correction_blocks_older_original(self):
  correction={**DOC,'docTypeCode':'130','docID':'S100TWO1','submitDateTime':'2026-07-01 10:00','xbrlFlag':'0'}
  with self.assertRaisesRegex(ValueError,'unavailable_correction'):select_doc([DOC,correction],'79740',NOW)
 def test_withdrawal_removes_archived_value(self):
  state=index();state['stocks'][ROW['listing_symbol']]={'inputIdentity':identity(ROW),'filing':DOC,'retrievedAt':'2026-10-20T00:00:00Z'}
  state['days'][DOC['indexDate']]['documents']=[{**DOC,'withdrawalStatus':'1'}]
  out=run({'kandidaten':[ROW]},coverage(),state,lambda d:self.fail('cache'),lambda d:self.fail('withdrawn'),NOW)
  self.assertFalse(out['stocks'])
 def test_json_auth_error_stops_index(self):
  out=run({'kandidaten':[ROW]},coverage(),{},lambda d:{'metadata':{'status':'401'}},lambda d:self.fail(),NOW)
  self.assertEqual(out['report']['errors'],{'http_401':1})
 def test_cold_index_checkpoints_and_resumes_without_repeat(self):
  calls=[]
  def get(d):calls.append(d);return {'metadata':{'status':'200'},'results':[DOC] if d==DOC['indexDate'] else []}
  out=run({'kandidaten':[ROW]},coverage(),{},get,lambda d:zipped(),NOW)
  self.assertEqual(len(calls),461);self.assertEqual(out['report']['completeCashflows'],1)
  run({'kandidaten':[ROW]},coverage(),out,lambda d:self.fail('already cached'),lambda d:self.fail('cooldown'),NOW)
 def test_duplicate_context_and_units_rejected(self):
  for bad in ['<xbrli:context id="I"/>','<xbrli:unit id="JPY"/>']:
   with self.assertRaises(ValueError):parse_xml(xml().replace('</xbrli:xbrl>',bad+'</xbrli:xbrl>').encode(),DOC,NOW)

if __name__=='__main__':unittest.main()
