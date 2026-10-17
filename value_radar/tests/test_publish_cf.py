import datetime as dt
import json
import pathlib
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import publish_cf as p


class PublishTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        self.remote = self.root/'remote.git'
        self.repo = self.root/'publisher'
        self.other = self.root/'other'
        subprocess.run(['git', 'init', '--bare', '--initial-branch=main', str(self.remote)], check=True, capture_output=True)
        subprocess.run(['git', 'clone', str(self.remote), str(self.repo)], check=True, capture_output=True)
        self.configure(self.repo)
        (self.repo/'README.md').write_text('initial')
        p.git(self.repo, 'add', '.')
        p.git(self.repo, 'commit', '-m', 'initial')
        p.git(self.repo, 'push', 'origin', 'main')
        subprocess.run(['git', 'clone', str(self.remote), str(self.other)], check=True, capture_output=True)
        self.configure(self.other)
        self.now = dt.datetime(2026, 10, 17, 12, tzinfo=dt.timezone.utc)
        self.source = self.root/'export.json'
        self.source.write_text(json.dumps({'stand':'2026-10-17 11:00 UTC', 'anzahl':1, 'kandidaten':[{'ticker':'MSFT'}]}))

    def configure(self, repo):
        p.git(repo, 'config', 'user.name', 'test')
        p.git(repo, 'config', 'user.email', 'test@example.invalid')

    def advance(self, conflict=False):
        f = self.other/p.TARGET if conflict else self.other/'other.txt'
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text('competing data')
        p.git(self.other, 'add', '.')
        p.git(self.other, 'commit', '-m', 'concurrent update')
        p.git(self.other, 'push', 'origin', 'main')

    def test_publish_and_no_change(self):
        self.assertEqual(p.publish(self.repo, self.source, self.now), 'published')
        self.assertEqual(p.publish(self.repo, self.source, self.now), 'unchanged')

    def test_stale_and_empty_rejected(self):
        with self.assertRaises(ValueError):
            p.publish(self.repo, self.source, self.now+dt.timedelta(days=2))
        self.source.write_text(json.dumps({'stand':'2026-10-17 11:00 UTC','anzahl':0,'kandidaten':[]}))
        with self.assertRaises(ValueError):
            p.publish(self.repo, self.source, self.now)

    def test_newer_published_export_is_preserved(self):
        newer = json.loads(self.source.read_text())
        newer['stand'] = '2026-10-17 11:30 UTC'
        f = self.other/p.TARGET
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(newer))
        p.git(self.other, 'add', '.')
        p.git(self.other, 'commit', '-m', 'newer export')
        p.git(self.other, 'push', 'origin', 'main')
        with self.assertRaisesRegex(RuntimeError, 'newer export'):
            p.publish(self.repo, self.source, self.now)
        self.assertEqual(json.loads((self.repo/p.TARGET).read_text())['stand'], newer['stand'])

    def test_concurrent_unrelated_commit_preserved(self):
        original = p.git
        advanced = False
        def racing(repo, *args, **kwargs):
            nonlocal advanced
            if args[0]=='push' and not advanced:
                advanced=True
                self.advance()
            return original(repo, *args, **kwargs)
        with patch.object(p, 'git', racing):
            self.assertEqual(p.publish(self.repo, self.source, self.now), 'published')
        self.assertTrue((self.repo/'other.txt').exists())

    def test_conflicting_export_fails(self):
        original=p.git
        advanced=False
        def racing(repo,*args,**kwargs):
            nonlocal advanced
            if args[0]=='push' and not advanced:
                advanced=True
                self.advance(True)
            return original(repo,*args,**kwargs)
        with patch.object(p,'git',racing), self.assertRaisesRegex(RuntimeError,'conflict'):
            p.publish(self.repo,self.source,self.now)

    def test_push_failure_is_not_success(self):
        original=p.git
        def failing(repo,*args,**kwargs):
            if args[0]=='push': return subprocess.CompletedProcess([],1,'','rejected')
            return original(repo,*args,**kwargs)
        with patch.object(p,'git',failing),self.assertRaisesRegex(RuntimeError,'three attempts'):
            p.publish(self.repo,self.source,self.now)


if __name__=='__main__': unittest.main()

