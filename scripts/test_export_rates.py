"""Zinsexport: Parser je amtlicher Quelle, Frische, Fehler ohne Antworttext, Waehrungen ohne Tagesquelle offen."""
import datetime as dt,json,unittest,urllib.error
import export_rates as R

NOW=dt.datetime(2026,11,17,6,0,tzinfo=dt.timezone.utc)
FIX={
 'USD':b'Date,"1 Mo","10 Yr","30 Yr"\n11/16/2026,4.10,5.12,5.46\n11/13/2026,4.10,5.15,5.47\n',
 'EUR':b'KEY,FREQ,TIME_PERIOD,OBS_VALUE\nYC.B,B,2026-11-13,3.4115908883\nYC.B,B,2026-11-16,3.4224059614\n',
 'JPY':b'Interest Rate (November 2026),,(Unit : %)\nDate,1Y,10Y,40Y\n2026/11/2,1.671,2.817,3.96\n2026/11/16,1.70,2.927,4.0\n',
 'GBP':b'DATE,IUDMNZC\n12 Nov 2026,5.2617\n13 Nov 2026,5.3224\n',
 'SEK':b'{"date":"2026-11-16","value":3.11}',
 'NOK':b'FREQ;TENOR;TIME_PERIOD;OBS_VALUE\nB;10Y;2026-11-13;4.358\nB;10Y;2026-11-16;4.385\n',
}
def fetcher_for(fix):
    urls={c:u for c,(n,u,p) in R.sources(NOW.date()).items()}
    def f(url):
        cur=next(c for c,u in urls.items() if u==url);v=fix[cur]
        if isinstance(v,Exception):raise v
        return v
    return f

class Parser(unittest.TestCase):
    def test_each_official_source(self):
        doc=R.collect(NOW,fetcher_for(FIX))
        self.assertEqual({c:(r['value'],r['as_of']) for c,r in doc['rates'].items()},{
            'USD':(0.0512,'2026-11-16'),'EUR':(0.034224,'2026-11-16'),'JPY':(0.02927,'2026-11-16'),
            'GBP':(0.053224,'2026-11-13'),'SEK':(0.0311,'2026-11-16'),'NOK':(0.04385,'2026-11-16')})
        self.assertEqual(doc['method'],'gov_10y_v1');self.assertEqual(len(doc['rates']['USD']['sha256']),64)
        self.assertEqual(set(doc['issues']),{'CHF','DKK','PLN'},'ohne Tagesquelle offen, nie geschaetzt')
    def test_stale_future_broken_and_http_errors_stay_open(self):
        fix=dict(FIX,USD=b'Date,"10 Yr"\n11/01/2026,5.0\n',EUR=b'KEY,TIME_PERIOD,OBS_VALUE\nx,2026-11-20,3.4\n',
                 JPY=b'kein csv',GBP=urllib.error.HTTPError('u',403,'x',{},None),SEK=b'{"date":"2026-11-16","value":null}',NOK=TimeoutError())
        doc=R.collect(NOW,fetcher_for(fix))
        self.assertEqual(doc['rates'],{})
        self.assertIn('ausserhalb von 7 Tagen',doc['issues']['USD']);self.assertIn('ausserhalb',doc['issues']['EUR'],'Zukunftsdatum')
        self.assertIn('ohne gueltigen',doc['issues']['JPY']);self.assertEqual(doc['issues']['GBP'],'Abruf fehlgeschlagen: HTTP 403')
        self.assertIn('ohne gueltigen',doc['issues']['SEK']);self.assertEqual(doc['issues']['NOK'],'Abruf fehlgeschlagen: TimeoutError')
    def test_implausible_values_rejected(self):
        self.assertIsNone(R.parse_sek(b'{"date":"2026-11-16","value":312}'));self.assertIsNone(R.num('abc'))

if __name__=='__main__':unittest.main()
