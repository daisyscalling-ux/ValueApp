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



class SplitBereinigung(unittest.TestCase):
    """Aktiensplits im 52-Wochen-Fenster (QA 17.11.2026: Netflix Hoch 1.157,50 bei Kurs 59,85)."""
    def test_ten_for_one_split_inside_window(self):
        # vor dem Split close 1100..1150, adj = close/10 * 0.99 (Dividendenbereinigung), danach close 60..65, adj 0.99*close..close
        vor=[(f'2026-0{m}-15',1100.0+m*10,(1100.0+m*10)/10*0.99) for m in range(1,6)]
        nach=[(f'2026-0{m}-15',60.0+m,(60.0+m)*(0.995 if m<9 else 1.0)) for m in range(6,10)]
        reihe,splits=roic.split_bereinigen(vor+nach)
        self.assertEqual(len(splits),1);self.assertEqual(splits[0]['date'],'2026-06-15');self.assertAlmostEqual(splits[0]['factor'],10*0.995/0.99,places=3)
        hoch=max(k for _,k in reihe);self.assertLess(hoch,120,'Hoch auf heutiger Aktienbasis')
        self.assertEqual(reihe[-1][1],69.0,'juengster Kurs unveraendert unbereinigt')
    def test_dividends_are_not_splits(self):
        rows=[(f'2026-01-{d:02d}',100.0,100.0*(0.97 if d<10 else 0.985 if d<20 else 1.0)) for d in range(1,29)]
        reihe,splits=roic.split_bereinigen(rows)
        self.assertEqual(splits,[]);self.assertEqual([k for _,k in reihe],[100.0]*28,'Dividenden bleiben unbereinigt (K52)')
    def test_reverse_split(self):
        rows=[('2026-01-01',2.0,20.0),('2026-01-02',2.1,21.0),('2026-01-05',21.5,21.5),('2026-01-06',22.0,22.0)]
        reihe,splits=roic.split_bereinigen(rows)
        self.assertAlmostEqual(splits[0]['factor'],0.1);self.assertEqual([round(k,2) for _,k in reihe],[20.0,21.0,21.5,22.0])
    def test_missing_adj_close_rows_stay_unadjusted(self):
        rows=[('2026-01-01',100.0,None),('2026-01-02',101.0,101.0),('2026-01-05',None,None)]
        reihe,splits=roic.split_bereinigen(rows)
        self.assertEqual(splits,[]);self.assertEqual(reihe,[('2026-01-01',100.0),('2026-01-02',101.0)])
    def test_kursband_reads_newest_days(self):
        heute=dt.date.today()
        desc=[{'date':(heute-dt.timedelta(days=i)).isoformat(),'close':60.0 if i<5 else 600.0,'adj_close':60.0} for i in range(10)]
        orig=roic.prices_history;roic.prices_history=lambda t,von=None,bis=None,limit=100,order='ASC':desc[:limit] if order.upper()=='DESC' else list(reversed(desc))[:limit]
        try:reihe,splits=roic.kursband('X',tage=10)
        finally:roic.prices_history=orig
        self.assertEqual(len(splits),1);self.assertAlmostEqual(splits[0]['factor'],10.0);self.assertEqual(max(k for _,k in reihe),60.0)
        self.assertEqual(roic.SPLIT_METHODE,'adj_close_ratio_step_v1')

if __name__=='__main__':unittest.main()
