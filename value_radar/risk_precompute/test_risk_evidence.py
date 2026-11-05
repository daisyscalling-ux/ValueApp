import copy
import datetime as dt
import gzip
import hashlib
import json
from pathlib import Path
import tempfile
import subprocess
import shutil
import unittest
from news_identity import prepare_universe,identity_fingerprint
from risk_evidence import news_review,sector_packets,checkpoint,encoded,article_url,resolve_inputs

NOW=dt.datetime(2026,11,5,15,tzinfo=dt.timezone.utc)
ROW={'listing_symbol':'NASDAQ:EX','ticker':'EX','name':'Example Corporation','isin':'US0378331005','currency':'USD'}


class Evidence(unittest.TestCase):
    def setUp(self):
        self.u={'kandidaten':[copy.deepcopy(ROW)]};prepare_universe(self.u['kandidaten'])
        self.c={'generatedAt':NOW.isoformat(),'stocks':[{'symbol':'NASDAQ:EX','domains':{'identity':{'state':'available'},'balance':{'profile':'corporate'}}}]}
        item={'title':'Example cuts outlook','url':'https://example.com/story?utm_source=x','publisher':'Example','publishedAt':NOW.isoformat()}
        self.a={'schema':1,'stocks':{'NASDAQ:EX':{'successAt':NOW.isoformat(),'inputFingerprint':identity_fingerprint(self.u['kandidaten'][0]),'items':[item]}}}
    def review(self):return news_review(self.u,self.c,self.a,NOW)

    def test_candidates_are_not_verified_or_scored(self):
        r=self.review();g=r['candidates'][0]
        self.assertEqual(g['categories'],['earnings_warning']);self.assertFalse(g['verified']);self.assertEqual(g['scoreContribution'],0)
        self.assertEqual(g['sources'][0]['url'],'https://example.com/story')

    def test_syndication_collapsed_without_independent_evidence_claim(self):
        item=copy.deepcopy(self.a['stocks']['NASDAQ:EX']['items'][0]);item['url']='https://second.example/story'
        self.a['stocks']['NASDAQ:EX']['items'].append(item)
        g=self.review()['candidates'][0]
        self.assertEqual(len(g['sources']),2)
        self.assertIn('syndication_or_duplicate_coverage_possible',g['reviewFlags'])
        self.assertFalse(g['verified'])

    def test_stale_future_and_identity_changed_articles_excluded(self):
        original=copy.deepcopy(self.a)
        for key,value in [('successAt',(NOW-dt.timedelta(days=2)).isoformat()),('inputFingerprint','wrong')]:
            self.a=copy.deepcopy(original);self.a['stocks']['NASDAQ:EX'][key]=value
            self.assertEqual(self.review()['candidates'],[])
        self.a=original;self.a['stocks']['NASDAQ:EX']['items'][0]['publishedAt']=(NOW+dt.timedelta(seconds=1)).isoformat()
        self.assertEqual(self.review()['candidates'],[])

    def test_negation_and_empty_sample_are_not_low_risk(self):
        self.a['stocks']['NASDAQ:EX']['items'][0]['title']='Example denies bankruptcy report'
        self.assertIn('negation_or_hypothetical_language',self.review()['candidates'][0]['reviewFlags'])
        self.a['stocks']['NASDAQ:EX']['items'][0]['title']='Example k\u00f6nnte bankruptcy vermeiden'
        self.assertIn('negation_or_hypothetical_language',self.review()['candidates'][0]['reviewFlags'])
        self.a['stocks']['NASDAQ:EX']['items']=[]
        self.assertEqual(self.review()['stocks']['NASDAQ:EX'],'no_tagged_candidate_in_sample')

    def test_duplicate_listing_and_credential_urls_rejected(self):
        self.u['kandidaten']*=2
        self.assertEqual(self.review()['stocks']['NASDAQ:EX'],'identity_unconfirmed')
        for url in ['https://example.com/?apikey=secret','https://user:password@example.com/x','file:///tmp/a']:
            self.assertIsNone(article_url(url))

    def test_sector_context_does_not_close_requirement(self):
        r=self.c['stocks'][0];r['country']='US'
        r['domains']['balance']={'profile':'bank','sectorRequirements':['liquidity_LCR_or_local_equivalent'],'bankCapital':{'state':'available','creditQuality':{'state':'available'}}}
        p=sector_packets(self.c,NOW)['packets'][0]['companies'][0]
        self.assertEqual(p['openRequirements'],['liquidity_LCR_or_local_equivalent'])
        self.assertTrue(p['availableContext']['loanQuality'])

    def files(self,folder):
        data={'cf_universum.json':self.u,'cf_risk_coverage.json':self.c,'cf_risk.json':{'schema':1},'cf_company_news.json':self.a,'cf_risk_event_review.json':self.review(),'cf_sector_review_packets.json':sector_packets(self.c,NOW)}
        data['cf_risk_run_integrity.json']={'state':'verified','processedSha256':hashlib.sha256(encoded(self.u)).hexdigest(),'generatedAt':self.c['generatedAt']}
        for name,value in data.items():(folder/name).write_bytes(encoded(value))

    def test_first_daily_observation_immutable_and_not_backdated(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);self.files(folder);report=checkpoint(folder,NOW,'commit1');path=folder/'risk_observations'/report['file'];first=path.read_bytes()
            report2=checkpoint(folder,NOW+dt.timedelta(hours=1),'commit2')
            self.assertEqual(first,path.read_bytes());self.assertEqual(report2['state'],'retained_first_daily_observation')
            result=json.loads(gzip.decompress(first));self.assertEqual(result['observedAt'],NOW.isoformat());self.assertEqual(result['codeVersion'],'commit1')
            self.assertEqual(result['horizonsTradingDays'],[21,63,126])
            self.assertIn('no_full_model_validation',result['modelValidationStatus'])
            inputs=resolve_inputs(result,lambda name:(folder/name).read_bytes())
            self.assertEqual(inputs['cf_universum.json'],self.u)
            with self.assertRaisesRegex(ValueError,'observation_source_hash_mismatch'):
                resolve_inputs(result,lambda name:b'{}')

    def test_unsealed_or_changed_universe_is_not_archived(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);self.files(folder)
            (folder/'cf_universum.json').write_bytes(b'{}')
            with self.assertRaisesRegex(ValueError,'unverified_observation_inputs'):checkpoint(folder,NOW,'c')
            self.assertFalse((folder/'risk_observations').exists())

    @unittest.skipUnless(shutil.which('git'),'Git required for historical-revision test')
    def test_resolver_uses_original_commit_not_current_files(self):
        from resolve_risk_observation import resolve
        with tempfile.TemporaryDirectory() as tmp:
            repo=Path(tmp);folder=repo/'value_radar/daten';folder.mkdir(parents=True)
            def git(*args):subprocess.run(['git','-C',str(repo),'-c','user.name=Test','-c','user.email=test@example.invalid',*args],check=True,capture_output=True)
            git('init');self.files(folder);checkpoint(folder,NOW,'code1');git('add','.');git('commit','-m','First observed inputs')
            (folder/'cf_risk.json').write_text('{"later":true}',encoding='utf-8');git('add','.');git('commit','-m','Later revision')
            result=resolve(repo,'2026-11-05')
            self.assertEqual(result['inputs']['cf_risk.json'],{'schema':1})
            self.assertEqual(result['observation']['codeVersion'],'code1')


if __name__=='__main__':unittest.main()
