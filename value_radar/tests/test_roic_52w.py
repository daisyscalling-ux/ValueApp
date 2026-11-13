"""52-Wochen-Band aus den juengsten unbereinigten ROIC-Kursen (Befund K52, 13.11.2026)."""
import datetime as dt,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import roic,providers


class Schlusskurse(unittest.TestCase):
    def setUp(self):
        heute=dt.date.today()
        # ROIC liefert bei order=desc die juengsten zuerst
        self.desc=[{'date':(heute-dt.timedelta(days=i)).isoformat(),'close':100.0+i,'adj_close':90.0+i} for i in range(300)]
        self.calls=[]
        def fake(t,von=None,bis=None,limit=100,order='ASC'):
            self.calls.append((limit,order))
            rows=self.desc if order.upper()=='DESC' else list(reversed(self.desc))
            return rows[:limit]
        self.orig=roic.prices_history;roic.prices_history=fake
    def tearDown(self):roic.prices_history=self.orig

    def test_latest_days_oldest_first(self):
        r=roic.schlusskurse('X',tage=260)
        self.assertEqual(self.calls[-1],(260,'DESC'))
        self.assertEqual(r[-1][0],dt.date.today().isoformat(),'newest last')
        self.assertLess(r[0][0],r[-1][0]);self.assertEqual(len(r),260)
        self.assertEqual(r[-1][1],90.0,'adjusted by default')

    def test_unadjusted_for_band(self):
        r=roic.schlusskurse('X',tage=260,adjustiert=False)
        self.assertEqual(r[-1][1],100.0);self.assertEqual(max(k for _,k in r),359.0)

    def test_band_must_be_current(self):
        heute=dt.date.today()
        self.assertTrue(providers._band_aktuell([(heute.isoformat(),1)]))
        self.assertTrue(providers._band_aktuell([((heute-dt.timedelta(days=10)).isoformat(),1)]))
        self.assertFalse(providers._band_aktuell([((heute-dt.timedelta(days=11)).isoformat(),1)]))
        self.assertFalse(providers._band_aktuell([('2021-11-15',1)]),'old window as before the fix')
        self.assertFalse(providers._band_aktuell([]))


if __name__=='__main__':unittest.main()
