"""Marktnachrichten-Export: mehrere Feeds einer Quelle (Financial Times), Originallinks, Teilausfall."""
import io,time,unittest,urllib.error
from unittest import mock
import export_market_news as M

def feed(*items):
    return ('<?xml version="1.0"?><rss version="2.0"><channel><title>FT</title>'+''.join(items)+'</channel></rss>').encode()
def item(uid,title,stamp):
    return f'<item><title>{title}</title><link>https://www.ft.com/content/{uid}?syn-25a6b1a6=1</link><pubDate>{time.strftime("%a, %d %b %Y %H:%M:%S GMT",time.gmtime(stamp))}</pubDate></item>'

class FT(unittest.TestCase):
    def test_sections_merged_original_links_and_partial_failure(self):
        now=time.time();name,urls,via=M.SOURCES['ft']
        self.assertEqual(name,'Financial Times');self.assertEqual(len(urls),3)
        def opener(req,timeout=0):
            u=req.full_url
            if '/markets?' in u: return io.BytesIO(feed(item('a1','Markets story',now-3600),item('b2','Shared story',now-7200)))
            if '/companies?' in u: return io.BytesIO(feed(item('b2','Shared story',now-7200)))
            raise urllib.error.HTTPError(u,503,'x',{},None)
        with mock.patch.object(M.urllib.request,'urlopen',opener):
            key,status=M.retrieve('ft',{},now)
        self.assertIsNone(status['error']);self.assertEqual([a['url'] for a in status['items']],['https://www.ft.com/content/a1?syn-25a6b1a6=1','https://www.ft.com/content/b2?syn-25a6b1a6=1'])
        self.assertEqual(status['items'][0]['publisher'],'Financial Times');self.assertNotIn('rmpwl',str(status))
    def test_all_sections_fail_keeps_recent_old_items_with_reason(self):
        now=time.time();old={'successAt':1,'items':[{'title':'x','url':'https://www.ft.com/content/o','publishedAt':time.strftime('%Y-%m-%dT%H:%M:%S+00:00',time.gmtime(now-3600))}]}
        def opener(req,timeout=0):raise urllib.error.HTTPError(req.full_url,503,'x',{},None)
        with mock.patch.object(M.urllib.request,'urlopen',opener):
            key,status=M.retrieve('ft',old,now)
        self.assertEqual(status['error'],'HTTP 503');self.assertEqual(len(status['items']),1)

class BloombergWSJ(unittest.TestCase):
    def test_four_sections_each_and_same_urls_as_worker(self):
        for key,name,host in (('bloomberg','Bloomberg','https://www.bloomberg.com/feeds/'),('wsj','The Wall Street Journal','https://feeds.content.dowjones.io/public/rss/')):
            n,urls,via=M.SOURCES[key]
            self.assertEqual(n,name);self.assertEqual(len(urls),4);self.assertTrue(all(u.startswith(host) for u in urls))
    def test_original_links_old_items_dropped_failure_without_invented_items(self):
        now=time.time();fmt=lambda t:time.strftime("%a, %d %b %Y %H:%M:%S GMT",time.gmtime(t))
        def opener(req,timeout=0):
            if '/feeds/markets/' in req.full_url:
                return io.BytesIO(feed(f'<item><title>Stocks rise</title><link>https://www.bloomberg.com/news/articles/x</link><pubDate>{fmt(now-600)}</pubDate></item>',
                                       f'<item><title>Old</title><link>https://www.bloomberg.com/news/articles/old</link><pubDate>{fmt(now-8*86400)}</pubDate></item>'))
            raise urllib.error.HTTPError(req.full_url,403,'x',{},None)
        with mock.patch.object(M.urllib.request,'urlopen',opener):
            _,b=M.retrieve('bloomberg',{},now);_,w=M.retrieve('wsj',{},now)
        self.assertIsNone(b['error']);self.assertEqual([a['url'] for a in b['items']],['https://www.bloomberg.com/news/articles/x'])
        self.assertEqual(b['items'][0]['publisher'],'Bloomberg')
        self.assertEqual(w['error'],'HTTP 403');self.assertEqual(w['items'],[])

if __name__=='__main__':unittest.main()
