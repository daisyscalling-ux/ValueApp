import datetime as dt,io,json,unittest,urllib.error,zipfile
import import_eu_pillar3 as p
LEI='2W8N8UU78PMDQKZENC08';NOW=dt.datetime(2026,11,10,tzinfo=dt.timezone.utc)
def url(date='2026-06-30',ts='20260901',scope='CON'):return f'https://errp.eba.europa.eu/public-documents/CODIS/input/{LEI}.{scope}_IT_PILLAR3020100_CODIS_{date}_{ts}.zip'
KM={'dp85151':.13,'dp85152':.15,'dp85153':.18,'dp85156':.098,'dp424336':.0101,'dp475582':.0441,'dp410433':.1421,'dp143076':1.376,'dp458571':1.198}
def pkg(date='2026-06-30',scope='CON',km=None,ext=p.TAXONOMY,entity=None):
 b=io.BytesIO();z=zipfile.ZipFile(b,'w');base='X/reports/'
 z.writestr(base+'report.json',json.dumps({'documentInfo':{'extends':[ext]}}))
 z.writestr(base+'parameters.csv','name,value\nentityID,rs:%s.%s\nrefPeriod,%s\nbaseCurrency,iso4217:EUR\ndecimalsPercentage,4\n'%(entity or LEI,scope,date))
 if km is not False:z.writestr(base+'k_61.00.csv','datapoint,factValue\n'+''.join(f'{k},{v}\n' for k,v in (km or KM).items()))
 z.close();return b.getvalue()
MAP={'banks':[{'lei':LEI,'ebaName':'Intesa Sanpaolo S.p.A.'}],'review_expires':'2027-05-08'}
def run(files,urls):
 def fetch(u):
  if u not in files:raise urllib.error.HTTPError(u,404,'missing',None,None)
  return files[u]
 return p.build({'urls':urls},MAP,fetch,NOW)
class EuPillar3(unittest.TestCase):
 def test_reads_km1_and_full_requirement(self):
  r=run({url():pkg()},[url()]);b=r['banks'][LEI]
  self.assertEqual((b['period'],b['lcr'],b['nsfr'],b['metrics']['cet1_ratio']),('2026-06-30',1.376,1.198,.13))
  self.assertAlmostEqual(b['cet1Requirement']['value'],.045+.0101+.0441);self.assertEqual(len(b['sourceFileSha256']),64)
 def test_latest_period_first_and_fallback_on_404(self):
  r=run({url('2026-03-31'):pkg('2026-03-31')},[url('2026-03-31'),url('2026-06-30')])
  self.assertEqual(r['banks'][LEI]['period'],'2026-03-31')
 def test_identity_period_taxonomy_and_chain_checks(self):
  for f,why in [(pkg(entity='549300TRUWO2CD2G5692'),'identity_or_period_mismatch'),(pkg(date='2026-03-31'),'identity_or_period_mismatch'),
                (pkg(ext='http://www.eba.europa.eu/eu/fr/xbrl/crr/fws/pillar3/4.1/mod/codis.json'),'taxonomy_not_4_2'),(pkg(km=False),'km1_missing'),
                (pkg(km={**KM,'dp85151':.2}),'capital_ratios_missing_or_inconsistent')]:
   r=run({url():f},[url()]);self.assertNotIn(LEI,r['banks']);self.assertTrue(r['rejected'][LEI][0].endswith(why),r['rejected'])
 def test_requirement_rules(self):
  b=run({url():pkg(km={**KM,'dp410433':.13,'dp85156':.10,'dp475582':.04})},[url()])['banks'][LEI]
  self.assertIsNone(b['cet1Requirement']);self.assertEqual(b['cet1RequirementOpen'],'overall_requirement_inconsistent_or_rounded');self.assertEqual(b['lcr'],1.376)
  km={k:v for k,v in KM.items() if k!='dp424336'};km.update({'dp85156':.08,'dp410433':.08+.0441})
  b=run({url():pkg(km=km)},[url()])['banks'][LEI]
  self.assertAlmostEqual(b['cet1Requirement']['value'],.045+.0441);self.assertEqual(b['cet1Requirement']['derivation'],'p2r_cet1_zero_because_total_srep_equals_pillar1_8pct')
  km={k:v for k,v in KM.items() if k!='dp424336'}
  self.assertEqual(run({url():pkg(km=km)},[url()])['banks'][LEI]['cet1RequirementOpen'],'p2r_cet1_or_buffer_missing')
 def test_old_and_foreign_urls_ignored(self):
  r=run({url('2025-12-31'):pkg('2025-12-31')},[url('2025-12-31').replace('errp.eba','evil.example'),url('2025-12-31')])
  self.assertEqual(r['rejected'][LEI],['2025-12-31:too_old'])

class Cr1Npl(unittest.TestCase):
 def findis(self,perf=980.0,np_=20.0,ext=p.FINDIS_TAXONOMY,date='2026-06-30'):
  b=io.BytesIO();z=zipfile.ZipFile(b,'w');base='X/reports/'
  z.writestr(base+'report.json',json.dumps({'documentInfo':{'extends':[ext]}}))
  z.writestr(base+'parameters.csv','name,value\nentityID,rs:%s.CON\nrefPeriod,%s\nbaseCurrency,iso4217:EUR\n'%(LEI,date))
  if perf is not None:z.writestr(base+'k_21.01.a.csv','datapoint,factValue\n%s,%s\n%s,%s\n'%(p.CR1_PERFORMING,perf,p.CR1_NON_PERFORMING,np_))
  z.close();return b.getvalue()
 def test_npl_ratio_and_checks(self):
  f=url().replace('/CODIS/','/FINDIS/').replace('_CODIS_','_FINDIS_')
  b=run({url():pkg(),f:self.findis()},[url(),f])['banks'][LEI];self.assertAlmostEqual(b['npl']['ratio'],.02);self.assertEqual(b['npl']['sourceUrl'],f)
  for bad,why in [(self.findis(ext=p.TAXONOMY),'taxonomy_not_4_2'),(self.findis(perf=None),'cr1_missing'),(self.findis(perf=-1),'cr1_loans_missing'),(self.findis(date='2026-03-31'),'identity_or_period_mismatch')]:
   b=run({url():pkg(),f:bad},[url(),f])['banks'][LEI];self.assertIsNone(b['npl']);self.assertTrue(b['nplOpen'][0].endswith(why),b['nplOpen'])
  self.assertEqual(run({url():pkg()},[url()])['banks'][LEI]['nplOpen'],['no_findis_submission_listed'])
if __name__=='__main__':unittest.main()


class UnitCorrectionTests(unittest.TestCase):
    """Geprüfte Einheitenkorrektur (Crédit Agricole S.A., EU 7e als Prozentwert gemeldet)."""
    def bank(self):
        return {'metrics': {'srep_additional_cet1': 0.9281, 'combined_buffer': 0.0332, 'srep_total': 0.0965, 'overall_requirement': 0.1297},
                'cet1Requirement': None, 'cet1RequirementOpen': 'requirement_out_of_range'}
    def corr(self, **k):
        c = {'lei': 'L', 'field': 'srep_additional_cet1', 'reportedValue': 0.9281, 'correctedValue': 0.009281, 'statedRequirement': 0.088, 'tolerance': 0.001,
             'evidence': 'Pflichtmitteilung', 'evidenceUrl': 'https://example.org/p.html', 'evidenceSha256': 'a' * 64, 'reviewedOn': '2026-11-12', 'reviewExpires': '2026-12-31'}
        c.update(k); return c
    def run_c(self, c, bank=None):
        import import_eu_pillar3 as ip
        banks = {'L': bank or self.bank()}
        ip.apply_unit_corrections(banks, [c], dt.datetime(2026, 11, 12, tzinfo=dt.timezone.utc))
        return banks['L']
    def test_correction_applies_with_marker(self):
        b = self.run_c(self.corr())
        self.assertAlmostEqual(b['cet1Requirement']['value'], 0.087481)
        self.assertEqual(b['cet1Requirement']['derivation'], 'reviewed_unit_correction_p2r_cet1_percent')
        self.assertEqual(b['cet1Requirement']['unitCorrection']['statedRequirement'], 0.088)
    def test_rejections(self):
        for k in ({'reportedValue': 0.93}, {'correctedValue': 0.0093}, {'statedRequirement': 0.095}, {'reviewExpires': '2026-11-01'},
                  {'evidenceSha256': 'x'}, {'evidenceUrl': 'http://x'}, {'field': 'combined_buffer'}):
            b = self.run_c(self.corr(**k))
            self.assertIsNone(b['cet1Requirement'], k)
            self.assertIn(b['cet1RequirementOpen'], ('unit_correction_not_applicable', 'unit_correction_check_failed'), k)
    def test_existing_requirement_is_never_replaced(self):
        bank = {**self.bank(), 'cet1Requirement': {'value': 0.1}, 'cet1RequirementOpen': None}
        self.assertEqual(self.run_c(self.corr(), bank)['cet1Requirement'], {'value': 0.1})
    def test_repository_correction_reproduces_stored_requirement(self):
        import json
        from pathlib import Path
        root = Path(__file__).resolve().parent
        m = json.loads((root / 'eu-bank-map.json').read_text(encoding='utf-8'))
        k = json.loads((root.parent / 'daten/regulatory/eu-pillar3-km1.json').read_text(encoding='utf-8'))
        b = k['banks']['969500TJ5KRTCJQWXH05']
        self.assertEqual(b['cet1Requirement']['derivation'], 'reviewed_unit_correction_p2r_cet1_percent')
        self.assertEqual(m['km1UnitCorrections'][0]['lei'], '969500TJ5KRTCJQWXH05')
