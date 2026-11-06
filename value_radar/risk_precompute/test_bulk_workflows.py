from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]/'.github/workflows'

class BulkWorkflows(unittest.TestCase):
 def test_production_jobs_share_non_cancelling_queue_and_checkout_main(self):
  for filename,job in [('daily-risk.yml','risk'),('precompute-3tage.yml','precompute')]:
   with self.subTest(workflow=filename):
    s=(ROOT/filename).read_text(encoding='utf8');block=s.split('  '+job+':\n',1)[1]
    self.assertIn('    concurrency:\n      group: roic-bulk-production\n      cancel-in-progress: false\n      queue: max\n',block)
    self.assertIn("if: github.event_name != 'pull_request'",block)
    checkout=block.split('- uses: actions/checkout@v6',1)[1].split('- uses:',1)[0]
    self.assertIn('ref: main',checkout)
 def test_prs_cannot_displace_production_and_no_duplicate_lock_deadlock(self):
  for filename in ['daily-risk.yml','precompute-3tage.yml']:
   s=(ROOT/filename).read_text(encoding='utf8');top=s.split('jobs:',1)[0]
   self.assertNotIn('group: roic-bulk-production',top)
   self.assertIn("github.event_name == 'pull_request' && github.ref",top)
   self.assertIn('queue: max',top)

if __name__=='__main__':unittest.main()
