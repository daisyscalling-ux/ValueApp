import datetime as dt
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from run_integrity import capture,seal,verify_remote,describe
from risk_app_export import publish


class IntegrityTests(unittest.TestCase):
    def test_actual_daily_pipeline_replaces_old_manifest_and_seals_enriched_rows(self):
        from risk_app_export import main as export_main
        from risk_evidence import main as evidence_main
        old=json.loads((self.folder/'cf_risk_app_manifest.json').read_text())
        self.coverage['generatedAt']=dt.datetime.now(dt.timezone.utc).isoformat()
        for row in self.coverage['stocks']:
            row['domains']={'identity':{'state':'available'},'balance':{'profile':'corporate'}}
        (self.folder/'cf_risk_coverage.json').write_text(json.dumps(self.coverage))
        (self.folder/'cf_risk.json').write_text('{}')
        (self.folder/'cf_company_news.json').write_text('{"schema":1,"stocks":{}}')
        with self.assertRaisesRegex(ValueError,'manifest_coverage_mismatch'):seal(self.folder,self.record)
        with patch.dict('os.environ',{'RISK_DATA_DIR':str(self.folder),'GITHUB_STEP_SUMMARY':''}):
            export_main();seal(self.folder,self.record)
            evidence_main();export_main();report=seal(self.folder,self.record)
        manifest=json.loads((self.folder/'cf_risk_app_manifest.json').read_text())
        self.assertNotEqual(manifest['generatedAt'],old['generatedAt'])
        self.assertEqual(manifest['inputUniverse'],report)
        rows=[]
        for digest in manifest['shards'].values():rows.extend(json.loads((self.folder/'risk_app'/(digest+'.json')).read_text())['stocks'])
        self.assertTrue(all('reviewedRisk' in row['domains'] for row in rows))
        self.assertEqual(json.loads((self.folder/'cf_risk_coverage.json').read_text()),self.coverage)
        # Tampering even an added review field must remain detectable after rehashing.
        from risk_app_export import publish
        rows[0]['domains']['reviewedRisk']['legalSolicitationCount']=999
        publish(self.folder,{**self.coverage,'stocks':rows},dt.datetime.now(dt.timezone.utc))
        with self.assertRaisesRegex(ValueError,'shard_coverage_values_mismatch'):seal(self.folder,self.record)
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.folder=Path(self.tmp.name);self.record=self.folder/'input.json'
        self.raw=json.dumps({'stand':'2026-11-03 00:00 UTC','anzahl':2,'kandidaten':[{'listing_symbol':'NYSE:A'},{'listing_symbol':'NYSE:B'}]}).encode()
        (self.folder/'cf_universum.json').write_bytes(self.raw)
        capture(self.folder,self.record)
        self.now=dt.datetime.now(dt.timezone.utc)+dt.timedelta(seconds=1)
        self.coverage={'schema':1,'generatedAt':self.now.isoformat(),'stocks':[{'symbol':'NYSE:A','score':1},{'symbol':'NYSE:B','score':2}]}
        self.write_results()

    def write_results(self):
        (self.folder/'cf_risk_coverage.json').write_text(json.dumps(self.coverage))
        publish(self.folder,self.coverage,self.now)

    def test_complete_chain_seals_without_changing_scores(self):
        report=seal(self.folder,self.record)
        self.assertEqual(report['publishedListings'],2)
        self.assertEqual(report['inputSha256'],report['processedSha256'])
        self.assertEqual(json.loads((self.folder/'cf_risk_coverage.json').read_text()),self.coverage)
        self.assertEqual(json.loads((self.folder/'cf_risk_app_manifest.json').read_text())['inputUniverse'],report)

    def test_coverage_loss_rejected(self):
        self.coverage['stocks'].pop();self.write_results()
        with self.assertRaisesRegex(ValueError,'listing_mismatch'):seal(self.folder,self.record)

    def test_previous_run_results_rejected_even_with_same_universe(self):
        self.coverage['generatedAt']=(self.now-dt.timedelta(days=1)).isoformat();self.write_results()
        with self.assertRaisesRegex(ValueError,'predate'):seal(self.folder,self.record)

    def test_tampered_shard_rejected(self):
        shard=next((self.folder/'risk_app').glob('*.json'));shard.write_bytes(b'{}')
        with self.assertRaisesRegex(ValueError,'shard_hash'):seal(self.folder,self.record)

    def test_current_coverage_cannot_be_paired_with_old_values(self):
        self.coverage['stocks'][0]['score']=90
        (self.folder/'cf_risk_coverage.json').write_text(json.dumps(self.coverage))
        with self.assertRaisesRegex(ValueError,'shard_coverage_values'):seal(self.folder,self.record)

    def test_concurrent_new_export_rejected(self):
        verify_remote(self.record,self.raw)
        with self.assertRaisesRegex(ValueError,'universe_changed'):verify_remote(self.record,self.raw+b' ')

    def test_local_identity_enrichment_is_recorded_separately(self):
        doc=json.loads(self.raw);doc['kandidaten'][0]['isin']='US1234567890'
        (self.folder/'cf_universum.json').write_text(json.dumps(doc))
        report=seal(self.folder,self.record)
        self.assertNotEqual(report['inputSha256'],report['processedSha256'])
        verify_remote(self.record,self.raw)

    def test_invalid_count_and_duplicate_listing_rejected(self):
        for doc in ({'anzahl':0,'kandidaten':[]},{'anzahl':2,'kandidaten':[{'ticker':'A'},{'ticker':'A'}]}):
            with self.assertRaises(ValueError):describe(json.dumps(doc).encode())

    def test_workflow_orders_capture_seal_and_publication_guard(self):
        path=Path(__file__).resolve().parents[2]/'.github/workflows/daily-risk.yml'
        s=path.read_text(encoding='utf-8')
        self.assertIn('workflows: [precompute-3tage]',s)
        self.assertIn("github.event.workflow_run.head_repository.full_name == github.repository",s)
        self.assertIn("github.event.workflow_run.event != 'pull_request'",s)
        self.assertIn("steps.riskpack.outcome == 'success'",s)
        self.assertLess(s.index('run_integrity.py capture'),s.index('recover_listing_metadata.py\n'))
        self.assertLess(s.index('run_integrity.py seal'),s.index('Ergebnisse und Teilfortschritt'))
        self.assertLess(s.index('run_integrity.py remote'),s.index('git rebase origin/main'))
        block=s[s.index('      - name: Abdeckung nach dem Lauf neu pruefen'):s.index('      - uses: actions/upload-artifact')]
        sequence=[line.strip().split('risk_precompute/')[-1] for line in block.splitlines() if any(x in line for x in ('risk_app_export.py','run_integrity.py seal','risk_evidence.py'))]
        self.assertEqual(sequence,['risk_app_export.py','run_integrity.py seal value_radar/daten /tmp/risk-input.json','risk_evidence.py','risk_app_export.py','run_integrity.py seal value_radar/daten /tmp/risk-input.json'])
