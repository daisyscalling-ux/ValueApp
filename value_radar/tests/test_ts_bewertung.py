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
                     '_ist_zyklisch':True,'obj':object(),'_roic_fx':0.0065,'market_cap':5e9},{'buy':3,'hold':1,'sell':0})
        self.assertEqual(d['_pruef_eingang'],{'market_cap':5e9,'_quelle':'roic','_roic_fx':0.0065,'price':None})
        self.assertIsNone(d['price']);self.assertIsNone(d['x']);self.assertIsNone(d['reihe_ebitda'][0]['wert']);self.assertIsNone(d['obj'])
        self.assertNotIn('_quelle',d);self.assertEqual(d['_analyst_trend'],{'richtung':'fallend'});self.assertNotIn('_ist_zyklisch',d,'unchecked flag replaced by _cyclicality (13.11.2026)')
        self.assertEqual((d['analyst_buy'],d['analyst_hold'],d['analyst_sell']),(3,1,0))

    def test_cyclicality_with_margin_series_old_flag_dropped(self):
        import valuation
        diag=valuation.zyklisch_aus_margen([0.28,-0.15,0.05,0.30,0.10])
        z=T.zyklik(diag)
        self.assertEqual((z['method'],z['cyclical'],z['years'],len(z['margins'])),('margin_cv_v1',True,5,5))
        self.assertIsNone(T.zyklik({'zyklisch':True}),'without margin series nothing is passed')
        d=T.eingabe({'_ist_zyklisch':True,'_zyklus_diagnose':diag})
        self.assertNotIn('_ist_zyklisch',d);self.assertEqual(d['_cyclicality'],z)

    def test_annual_share_count_only_for_the_same_listing(self):
        import json
        with tempfile.TemporaryDirectory() as d:
            datei={'schema':1,'symbol':'NASDAQ:MU','annual':{'end':'2025-08-28','currency':'USD','source':'Yahoo annual statements',
                   'fields':{'weighted_shares':1.12e9,'revenue':3.7e10}},'market':{'currency':'USD','fields':{'price':1}},'share_basis':None}
            Path(d,'NASDAQ_MU.json').write_text(json.dumps(datei));Path(d,'NASDAQ_AMD.json').write_text(json.dumps({**datei,'symbol':'NASDAQ:MUX'}))
            e=T.ersatzdaten({'listing_symbol':'NASDAQ:MU','ticker':'MU'},d)
            self.assertEqual(e['_supplement_symbol'],'NASDAQ:MU')
            self.assertEqual(e['_fundamental_supplement']['annual']['fields'],{'weighted_shares':1.12e9},'only the share count is passed')
            self.assertEqual(T.ersatzdaten({'listing_symbol':'NASDAQ:AMD'},d),{},'file of another listing')
            self.assertEqual(T.ersatzdaten({'listing_symbol':'NYSE:XX'},d),{},'no file')
            Path(d,'NYSE_NA.json').write_text(json.dumps({**datei,'symbol':'NYSE:NA','annual':None}))
            self.assertEqual(T.ersatzdaten({'listing_symbol':'NYSE:NA'},d),{},'no annual block')
            self.assertEqual(T.ersatzdaten({'listing_symbol':'../x'},d),{},'path characters are replaced')
            ein=T.eingabe({**JUMBO,**e});self.assertIn('_fundamental_supplement',ein);self.assertIn('_supplement_symbol',ein)

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
        # Diagnose nur bei gesperrten Zeilen: Rohwerte fuer die Ursachensuche
        self.assertEqual(b['valuation_check_inputs']['price'],80.0);self.assertEqual(b['valuation_check_inputs']['52w_high'],28.7)
        self.assertNotIn('valuation_check_inputs',a)


    def test_market_cap_price_times_shares_with_annual_check(self):
        import json
        # Micron 13.11.2026: ROIC-Boersenwert zum Stichtag 2025-08-28 (130 Mrd.), Kurs x Aktien 873 Mrd. USD
        mu={**JUMBO,'ticker':'NASDAQ:MU','currency':'USD','price':778.31,'shares_out':1.122e9,'market_cap':130.16e9,'52w_high':1183,'52w_low':196,
            'risk_financial':{'asof':'2025-08-28','currency':'USD','source':'ROIC Enterprise Value · dieselbe Berichtszeile'}}
        datei={'schema':1,'symbol':'NASDAQ:MU','annual':{'end':'2025-08-28','currency':'USD','source':'Yahoo annual statements','fields':{'weighted_shares':1.12e9}},
               'market':{'currency':'USD'},'share_basis':None}
        with tempfile.TemporaryDirectory() as d:
            Path(d,'NASDAQ_MU.json').write_text(json.dumps(datei))
            mit=[{**zeile('NASDAQ:MU',mu),'listing_symbol':'NASDAQ:MU'}];ohne=[{**zeile('NASDAQ:MU',mu),'listing_symbol':'NASDAQ:MU'}]
            T.anwenden(mit,risiko={},ordner=d);T.anwenden(ohne,risiko={},ordner=tempfile.gettempdir()+'/leer-nicht-vorhanden')
            Path(d,'NASDAQ_MU.json').write_text(json.dumps({**datei,'annual':{**datei['annual'],'fields':{'weighted_shares':4e9}}}))
            falsch=[{**zeile('NASDAQ:MU',mu),'listing_symbol':'NASDAQ:MU'}];T.anwenden(falsch,risiko={},ordner=d)
        self.assertNotEqual(mit[0]['kauf_urteil'],'Daten prüfen');self.assertEqual(mit[0]['market_cap_source'],'kurs_x_aktien')
        self.assertAlmostEqual(mit[0]['market_cap'],778.31*1.122e9,delta=1)
        self.assertEqual(ohne[0]['kauf_urteil'],'Daten prüfen','without annual report the stale provider value stays the yardstick')
        self.assertEqual(falsch[0]['kauf_urteil'],'Daten prüfen');self.assertIn('Jahresabschluss',' '.join(falsch[0]['valuation_issues']))

    def test_peers_from_the_whole_universe(self):
        peers=[{'ticker':f'ATHEX:P{i}','listing_symbol':f'ATHEX:P{i}','isin':f'GRS00000000{i}','name':f'Peer {i}','name_full':f'Peer {i}','currency':'EUR',
                'sector':'Retail trade','industry':'Specialty stores','market_cap':3e9,'price':50,'eps_forward':2.5,'ev_ebitda':8+i,'pb':2+i/10,
                'roe':12+i,'gross_margin':40+i,'revenue_growth':3+i,'net_debt_ebitda':0.5} for i in range(1,7)]
        subject={**zeile('ATHEX:BELA',JUMBO),'listing_symbol':'ATHEX:BELA','isin':'GRS282183003','name':'Jumbo S.A.','currency':'EUR',
                 'sector':'Retail trade','industry':'Specialty stores','market_cap':3.7e9}
        rows=[subject,*peers]
        st=T.anwenden(rows)
        self.assertEqual(st['ts'],1)
        self.assertGreaterEqual(subject['peer_count'],5);self.assertEqual(subject['ev_ebitda_anchor'],'peers')
        self.assertIn('roe',subject['composite_peer_metrics'])
        self.assertNotIn('scanner_method',peers[0],'retained rows are only peers, not re-evaluated')

    def test_verified_cash_conversion_from_risk_data_changes_dcf(self):
        cc={'state':'available','method':'sum_fcf_over_sum_net_income_v1','value':0.7,'raw':0.7,'clamped':False,'years':3,'currency':'EUR','sumFcf':7,'sumNetIncome':10,
            'periods':[{'end':'2023-12-31','fcf':2,'netIncome':3},{'end':'2024-12-31','fcf':2,'netIncome':3},{'end':'2025-12-31','fcf':3,'netIncome':4}]}
        mit=[{**zeile('ATHEX:BELA',JUMBO),'listing_symbol':'ATHEX:BELA'}];ohne=[{**zeile('ATHEX:BELA',JUMBO),'listing_symbol':'ATHEX:BELA'}]
        T.anwenden(mit,risiko={'ATHEX:BELA':{'_cash_conversion_history':cc}});T.anwenden(ohne,risiko={})
        self.assertNotEqual(mit[0]['fair_value'],ohne[0]['fair_value'])
        falsch=[{**zeile('ATHEX:BELA',JUMBO),'listing_symbol':'ATHEX:BELA'}]
        T.anwenden(falsch,risiko={'ATHEX:BELA':{'_cash_conversion_history':{**cc,'value':1.2}}})
        self.assertEqual(falsch[0]['fair_value'],ohne[0]['fair_value'],'manipulated conversion ignored by the app check')

    def test_health_from_verified_financial_data(self):
        rf={'asof':'2026-06-30','currency':'EUR','source':'ROIC Enterprise Value · dieselbe Berichtszeile','debt':600,'cash':0,'ebitda':100,'fcff':-10,'revenue':100}
        a=[{**zeile('ATHEX:BELA',{**JUMBO,'risk_financial':rf}),'listing_symbol':'ATHEX:BELA'}];b=[{**zeile('ATHEX:BELA',JUMBO),'listing_symbol':'ATHEX:BELA'}]
        T.anwenden(a,risiko={'ATHEX:BELA':{'_risk_coverage':{'balance':{'state':'available','profile':'corporate'}}}});T.anwenden(b,risiko={})
        self.assertEqual(a[0]['health_raw'],0);self.assertEqual(a[0]['health_profile'],'corporate')
        self.assertEqual(a[0]['health_parts'],['Nettoschulden / EBITDA','Cashflow-Puffer · berichteter FCFF / Umsatz'])
        # Nur ein Titel im Profil: kein Rang (mindestens 20), bisherige Bilanz bleibt, gekennzeichnet
        self.assertEqual(a[0]['health_source'],'kennzahlen_ohne_rang');self.assertEqual(a[0]['health'],b[0]['health'])
        self.assertEqual(b[0]['health_source'],'kennzahlen')
        # Mit 25 uebernommenen Zeilen im Profil: Rang statt absoluter Skala
        alt=[{'ticker':f'X:{i}','listing_symbol':f'X:{i}','scanner_method':'ts-evaluate-v1','health_raw':float(i*4),'health_profile':'corporate'} for i in range(25)]
        c=[{**zeile('ATHEX:BELA',{**JUMBO,'risk_financial':rf}),'listing_symbol':'ATHEX:BELA'},*alt]
        T.anwenden(c,risiko={'ATHEX:BELA':{'_risk_coverage':{'balance':{'state':'available','profile':'corporate'}}}})
        self.assertEqual(c[0]['health_source'],'risiko_rang')
        # 26 Werte (25 uebernommene + eigener), zwei Gleichstaende bei 0: (0 + 0,5 x 2) / 26 = 3,8 %
        self.assertAlmostEqual(c[0]['health'],3.8)

    def test_data_cyclicality_in_scanner_with_sector_exclusions(self):
        import valuation
        diag=valuation.zyklisch_aus_margen([0.28,-0.15,0.05,0.30,0.10])
        a=[{**zeile('ATHEX:BELA',{**JUMBO,'_zyklus_diagnose':diag}),'listing_symbol':'ATHEX:BELA'}]
        b=[{**zeile('ATHEX:BELA',{**JUMBO,'_zyklus_diagnose':diag,'sector':'Utilities'}),'listing_symbol':'ATHEX:BELA'}]
        T.anwenden(a,risiko={});T.anwenden(b,risiko={})
        self.assertEqual(a[0]['playbook'],'cyclical');self.assertEqual(b[0]['playbook'],'quality','defensive sector excluded')

if __name__=='__main__':unittest.main()
