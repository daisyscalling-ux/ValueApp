import json
import tempfile
import unittest
from pathlib import Path
from queue_policy import order_rows, due, failed

class QueueTests(unittest.TestCase):
    def test_new_listing_not_starved_by_priority(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'queue.json'
            p.write_text(json.dumps({'schema':1,'generatedAt':'2026-10-18T00:00:00Z','jobs':[
                {'symbol':'OLD','kind':'fundamentals','state':'queued'}]}))
            now=1792281600
            rows=order_rows([{'ticker':'OLD'},{'ticker':'NEW'}],{'attempts':{'OLD':'2026-10-17T00:00:00Z'}},p,now)
            self.assertEqual(rows[0]['ticker'],'NEW')

    def test_missing_queue_keeps_oldest_first(self):
        rows=order_rows([{'ticker':'B'},{'ticker':'A'}],{},'no-such-file',10)
        self.assertEqual([r['ticker'] for r in rows],['A','B'])

    def test_backoff_and_bad_timestamp(self):
        first=failed(None,'timeout','2026-10-18',100000)
        second=failed(first,'timeout','2026-10-18',100000)
        self.assertFalse(due(first,100001))
        self.assertTrue(due(first,107201))
        self.assertFalse(due(second,107201))
        self.assertTrue(due({'next_attempt_at':'2099-01-01'},100000))

if __name__=='__main__':unittest.main()
