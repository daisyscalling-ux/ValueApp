"""App-Rechenweg im Scanner (ts_bewertung.py). Integrationstest nur mit gebautem scanner-evaluate.mjs (SCANNER_EVAL_JS)."""
import math,os,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import ts_bewertung as T

JUMBO={'ticker':'ATHEX:BELA','name':'Jumbo S.A.','sector':'Retail trade','industry':'Specialty stores','currency':'EUR','price':27.6,
 'shares_out':134365561,'market_cap':3708489483.6,'revenue':1232904830,'net_income':320309417,'ebitda':441341578,'ebit':392515310,
 'free_cashflow':258528902,'net_debt':-470236502,'total_debt':66432256,'total_assets':1872429412,'eps_trailing':2.3839,
 'book_value_ps':11.731964606615232,'roe':0.20319405304130986,'gross_margin':0.5471542365520622,'operating_margin':0.3183662683842353,
 'net_debt_ebitda':-1.06547065910024,'ev_ebitda':7.3372941572253145,'pb':2.3525471585924627,'revenue_growth':0.07220931958289278,
 'beta':0.341,'target_mean':32.9875,'analyst_count':8,'52w_high':28.7,'52w_low':21.22}


def zeile(ticker,fund):
    return {'ticker':ticker,'composite':11,'fair_value':1.0,'upside':5.0,'quantum':22,'kauf_urteil':'meiden','_ts_input':T.eingabe(fund,{'buy':5,'hold':2,'sell':1})}


class Eingabe(unittest.TestCase):
    def test_json_safe_and_private_fields(self):
        d=T.eingabe({'price':float('nan'),'x':float('inf'),'reihe_ebitda':[{'jahr':2024,'wert':float('nan')}],'_quelle':'roic','_analyst_trend':{'richtung':'fallend'},
                     '_ist_zyklisch':True,'obj':object()},{'buy':3,'hold':1,'sell':0})
        self.assertIsNone(d['price']);self.assertIsNone(d['x']);self.assertIsNone(d['reihe_ebitda'][0]['wert']);self.assertIsNone(d['obj'])
        self.assertNotIn('_quelle',d);self.assertEqual(d['_analyst_trend'],{'richtung':'fallend'});self.assertTrue(d['_ist_zyklisch'])
        self.assertEqual((d['analyst_buy'],d['analyst_hold'],d['analyst_sell']),(3,1,0))

    def test_without_ts_build_python_values_stay_and_are_marked(self):
        rows=[zeile('A',JUMBO),{'ticker':'B','composite':40}]
        st=T.anwenden(rows,js='/nicht/vorhanden.mjs')
        self.assertTrue(st['ausfall']);self.assertEqual(rows[0]['scanner_method'],T.ALT);self.assertEqual(rows[0]['composite'],11)
        self.assertNotIn('_ts_input',rows[0]);self.assertNotIn('scanner_method',rows[1],'retained rows untouched')

    def test_failing_node_process_counts_as_outage(self):
        with tempfile.TemporaryDirectory() as d:
            js=os.path.join(d,'kaputt.mjs');open(js,'w').write('process.exit(3)')
            rows=[zeile('A',JUMBO)];st=T.anwenden(rows,js=js)
        self.assertTrue(st['ausfall']);self.assertEqual(rows[0]['scanner_method'],T.ALT)


@unittest.skipUnless(os.environ.get('SCANNER_EVAL_JS'),'scanner-evaluate.mjs nicht gebaut')
class AppRechenweg(unittest.TestCase):
    def test_values_replaced_by_app_path(self):
        rows=[zeile('ATHEX:BELA',JUMBO),zeile('BLOCK',{**JUMBO,'price':80.0})]
        st=T.anwenden(rows)
        self.assertEqual((st['ts'],st['ausfall']),(2,False))
        a,b=rows
        self.assertEqual(a['scanner_method'],T.METHODE);self.assertEqual(a['playbook'],'quality');self.assertNotEqual(a['composite'],11)
        self.assertTrue(a['fair_value']>27.6 and a['upside']>0 and math.isfinite(a['quantum']))
        self.assertIn(a['kauf_urteil'],('kauf','beobachten','meiden'));self.assertNotIn('_ts_input',a)
        # Kurs ueber dem Doppelten des 52W-Hochs: Datenpruefung der App sperrt die Bewertung
        self.assertEqual(b['kauf_urteil'],'Daten prüfen');self.assertIsNone(b['fair_value']);self.assertIsNone(b['quantum']);self.assertTrue(b['valuation_issues'])


if __name__=='__main__':unittest.main()
