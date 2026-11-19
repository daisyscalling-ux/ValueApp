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
# Herkunft wie im Lauf: FCF und EV/EBITDA von ROIC (NUR_ROIC, seit 17.11.2026)
JUMBO['_roic']=True;JUMBO['_roic_felder']=sorted(k for k in JUMBO if not k.startswith('_'))


def zeile(ticker,fund):
    return {'ticker':ticker,'composite':11,'fair_value':1.0,'upside':5.0,'quantum':22,'kauf_urteil':'meiden','_ts_input':T.eingabe(fund,{'buy':5,'hold':2,'sell':1})}


class Eingabe(unittest.TestCase):
    def test_band_conflict_without_split(self):
        # 19.11.2026: Compass ROIC 27-2.527 (Pence/Pfund gemischt), Rose Yahoo 0,03-3,95; Netflix-Split vor 367 Tagen.
        import datetime as _dt
        heute=_dt.date(2026,11,19);self.assertEqual(T.SPLIT_FENSTER_TAGE,400)
        m=lambda lo,hi,px:{'_fundamental_supplement':{'splits':[],'market':{'quote_at':'2026-11-19','fields':{'price':px,'52w_low':lo,'52w_high':hi}}}}
        cpg={'price':33.0,'52w_low':27.185,'52w_high':2527.0};b=T.band_nach_split(cpg,m(26.0,34.92,33.0),heute)
        self.assertEqual((cpg['52w_low'],cpg['52w_high']),(26.0,34.92));self.assertTrue(b['conflict']);self.assertIn('Yahoo',b['source'])
        rose={'price':3.22,'52w_low':2.95,'52w_high':3.88};b=T.band_nach_split(rose,m(0.03,3.95,3.22),heute)
        self.assertEqual((rose['52w_low'],rose['52w_high']),(2.95,3.88));self.assertIn('ROIC',b['source'])
        weg={'price':10.0,'52w_low':20.0,'52w_high':30.0};b=T.band_nach_split(weg,m(40.0,90.0,10.0),heute)
        self.assertIsNone(weg['52w_high']);self.assertIn('keines enthaelt',b['reason'])
        gleich={'price':33.0,'52w_low':27.0,'52w_high':36.0};self.assertIsNone(T.band_nach_split(gleich,m(26.0,34.9,33.0),heute),'ohne Widerspruch keine Aenderung')
        alt={'price':33.0,'52w_low':27.185,'52w_high':2527.0};self.assertIsNone(T.band_nach_split(alt,{'_fundamental_supplement':{'splits':[],'market':{'quote_at':'2026-11-01','fields':{'price':33.0,'52w_low':26.0,'52w_high':34.9}}}},heute),'veraltete Ergaenzungsdatei')
        nflx={'price':59.82,'52w_low':59.68,'52w_high':1157.5}
        b=T.band_nach_split(nflx,{'_fundamental_supplement':{'splits':[{'date':'2025-11-17','ratio':10.0}],'market':{'quote_at':'2026-11-19','fields':{'price':59.82,'52w_low':59.41,'52w_high':113.34}}}},heute)
        self.assertEqual(nflx['52w_high'],113.34);self.assertEqual(b['splits'][0]['date'],'2025-11-17')

    def test_band_after_split_from_supplement(self):
        # Mitsui Kinzoku 17.11.2026: Split 10:1 am 29.09.2026, ROIC-Band 1.344,5-54.900, Yahoo bereinigt 1.326-5.770.
        import datetime as _dt
        heute=_dt.date(2026,11,17)
        sup=lambda **o:{'_fundamental_supplement':{'splits':[{'date':'2026-09-29','ratio':10.0}],'market':{'quote_at':'2026-11-17T06:00:00+00:00',
            'fields':{'price':1344.5,'52w_low':1326.0,'52w_high':5770.0}},**o}}
        row={'price':1344.5,'52w_low':1344.5,'52w_high':54900.0};ein=dict(sup())
        b=T.band_nach_split(row,ein,heute)
        self.assertEqual((row['52w_low'],row['52w_high']),(1326.0,5770.0));self.assertEqual((ein['52w_low'],ein['52w_high']),(1326.0,5770.0))
        self.assertEqual(b['method'],T.BAND_METHODE);self.assertIsNone(b['reason']);self.assertEqual(b['splits'][0]['ratio'],10.0)
        alt={'price':1344.5,'52w_low':1.0,'52w_high':2.0};self.assertIsNone(T.band_nach_split(alt,{'_fundamental_supplement':{'splits':[{'date':'2025-09-29','ratio':10}]}},heute),'Split ausserhalb 365 Tagen')
        self.assertEqual(alt['52w_high'],2.0);self.assertIsNone(T.band_nach_split(dict(alt),{},heute))
        for markt,grund in [({'quote_at':'2026-11-01','fields':{'price':1344.5,'52w_low':1326.0,'52w_high':5770.0}},'aelter'),
                            ({'quote_at':'2026-11-17','fields':{'price':1500.0,'52w_low':1326.0,'52w_high':5770.0}},'passt nicht'),
                            ({'quote_at':'2026-11-17','fields':{'price':1344.5,'52w_low':None,'52w_high':5770.0}},'Kein bereinigtes')]:
            r={'price':1344.5,'52w_low':1344.5,'52w_high':54900.0};b=T.band_nach_split(r,{'_fundamental_supplement':{'splits':[{'date':'2026-09-29','ratio':10.0}],'market':markt}},heute)
            self.assertIn(grund,b['reason']);self.assertEqual((r['52w_low'],r['52w_high']),(None,None),'offen statt unbereinigt')
        p={'price':2350.0,'52w_low':1788.0,'52w_high':2522.0}
        b=T.band_nach_split(p,{'_fundamental_supplement':{'splits':[{'date':'2026-08-17','ratio':0.75}],'market':{'quote_at':'2026-11-17','fields':{'price':23.5,'52w_low':21.92,'52w_high':32.45}}}},heute)
        self.assertEqual(b['unit_factor'],100.0);self.assertAlmostEqual(p['52w_high'],3245.0)

    def test_roic_raw_blocks_same_paths_as_the_app(self):
        # 17.11.2026: KGV-Band, Reihen und Gewinnhistorie aus denselben ROIC-Bloecken wie worker/bundle-fetch.ts.
        import roic
        from unittest import mock
        aufrufe=[]
        def get(pfad,params=None):
            aufrufe.append((pfad,params));return [{'pfad':pfad}]
        with mock.patch.object(roic,'_key',lambda:'x'),mock.patch.object(roic,'_sym',lambda t:'NASDAQ:AAPL'),mock.patch.object(roic,'_get',get):
            b=roic.rohbloecke('AAPL')
        self.assertEqual((b['method'],b['symbol']),('roic_raw_blocks_v1','NASDAQ:AAPL'))
        self.assertIn(('fundamental/multiples/NASDAQ:AAPL',{'period_type':'annual','limit':5}),aufrufe)
        self.assertIn(('fundamental/enterprise-value/NASDAQ:AAPL',None),aufrufe)
        self.assertIn(('fundamental/income-statement/NASDAQ:AAPL',{'period_type':'annual','limit':3}),aufrufe)
        self.assertIn(('fundamental/cash-flow/NASDAQ:AAPL',{'period_type':'annual','limit':3}),aufrufe)
        app=open(Path(__file__).resolve().parents[1]/'risk_precompute'/'worker'/'bundle-fetch.ts',encoding='utf-8').read()
        for teil in ('fundamental/multiples/${sym}?period_type=annual&limit=5','fundamental/enterprise-value/${sym}`',
                     'fundamental/income-statement/${sym}?period_type=annual&limit=3','fundamental/cash-flow/${sym}?period_type=annual&limit=3'):
            self.assertIn(teil,app,'App-Pfade geaendert: ROH_PFADE anpassen')
        with mock.patch.object(roic,'_key',lambda:None):
            self.assertIsNone(roic.rohbloecke('AAPL'))
        self.assertIn('roic_history_status',T.FELDER)
        self.assertIn('eps_basis',T.FELDER,'Sondereffekt-Kennzeichnung in der Zeile (17.11.2026)')
        self.assertIn('risk_free',T.FELDER)

    def test_rates_file_reaches_every_input(self):
        # cf_rates.json (scripts/export_rates.py) unveraendert an jeden Eingang; App prueft (valuation.ts riskFree).
        import tempfile,json as _j,os as _o
        doc={'schema':1,'method':'gov_10y_v1','rates':{'USD':{'value':0.0512,'as_of':'2026-11-16'}},'issues':{}}
        with tempfile.TemporaryDirectory() as d:
            p=_o.path.join(d,'r.json');open(p,'w').write(_j.dumps(doc))
            self.assertEqual(T.zinsen(p),doc);self.assertIsNone(T.zinsen(_o.path.join(d,'fehlt.json')))
        from unittest import mock
        gesehen=[]
        def fake(offen,js,node,universum=None,**kw):
            gesehen.extend(offen.values());return {t:{'scanner_method':T.METHODE} for t in offen}
        with mock.patch.object(T,'rechnen',fake):
            T.anwenden([zeile('A',JUMBO)],js='x',risiko={},ordner=tempfile.gettempdir()+'/leer-nicht-vorhanden',zins=doc)
        self.assertTrue(gesehen and all(g['_rates']==doc for g in gesehen))

    def test_bank_margins_from_yahoo_are_dropped(self):
        # KeyCorp 17.11.2026: ROIC ohne Margen, Yahoo grossMargins 0.0 und operatingMargins 0.355 still eingesetzt.
        f={'gross_margin':0.0,'operating_margin':0.355,'roe':0.11,'roa':0.011,'pb':1.1,'current_ratio':None,'net_debt_ebitda':2.0,
           '_roic':True,'_roic_felder':['roe','roa','pb']}
        d=T.eingabe(f)
        self.assertIsNone(d['gross_margin'],'0.0 von Yahoo ist kein Wert der App');self.assertIsNone(d['operating_margin'])
        self.assertEqual((d['roe'],d['roa'],d['pb']),(0.11,0.011,1.1));self.assertEqual(d['net_debt_ebitda'],2.0,'App rechnet selbst')
        self.assertEqual(d['_pruef_eingang']['nur_roic_verworfen'],['gross_margin','operating_margin'])
        self.assertIsNone(T.eingabe({'roe':0.2,'_roic_felder':[]})['roe'])

    def test_yahoo_fill_ins_without_roic_are_dropped(self):
        # IBM/Pfizer 16.11.2026: ROIC ohne FCF, Yahoo freeCashflow still eingesetzt; App laesst offen.
        d=T.eingabe({'free_cashflow':5e9,'ev_ebitda':12.0,'revenue':6e10,'_roic':True,'_roic_felder':['revenue']})
        self.assertIsNone(d['free_cashflow']);self.assertIsNone(d['ev_ebitda']);self.assertEqual(d['revenue'],6e10)
        self.assertEqual(d['_pruef_eingang']['nur_roic_verworfen'],['free_cashflow','ev_ebitda'])
        k=T.eingabe({'free_cashflow':5e9,'ev_ebitda':12.0,'_roic_felder':['free_cashflow','ev_ebitda']})
        self.assertEqual((k['free_cashflow'],k['ev_ebitda']),(5e9,12.0));self.assertNotIn('nur_roic_verworfen',k['_pruef_eingang'])
        self.assertIsNone(T.eingabe({'free_cashflow':5e9})['free_cashflow'],'ohne ROIC-Herkunft kein Wert')

    def test_value_inputs_reach_the_universe_row(self):
        # Peers lesen Forward-KGV, PEG und FCF-Rendite aus der Zeile (value-inputs.ts, seit 17.11.2026).
        self.assertIn('value_inputs',T.FELDER);self.assertIn('eps_forward_no_profit',T.FELDER)

    def test_json_safe_and_private_fields(self):
        d=T.eingabe({'price':float('nan'),'x':float('inf'),'reihe_ebitda':[{'jahr':2024,'wert':float('nan')}],'_quelle':'roic','_analyst_trend':{'richtung':'fallend'},
                     '_ist_zyklisch':True,'obj':object(),'_roic_kursverhaeltnis':0.0065,'market_cap':5e9},{'buy':3,'hold':1,'sell':0})
        self.assertEqual(d['_pruef_eingang'],{'market_cap':5e9,'_quelle':'roic','_roic_kursverhaeltnis':0.0065,'price':None})
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
                   'fields':{'weighted_shares':1.12e9,'revenue':3.7e10}},'market':{'currency':'USD','fields':{'price':1}},'share_basis':None,
                   'risk_annual':{'end':'2025-08-28'}}
            Path(d,'NASDAQ_MU.json').write_text(json.dumps(datei));Path(d,'NASDAQ_AMD.json').write_text(json.dumps({**datei,'symbol':'NASDAQ:MUX'}))
            e=T.ersatzdaten({'listing_symbol':'NASDAQ:MU','ticker':'MU'},d)
            self.assertEqual(e['_supplement_symbol'],'NASDAQ:MU')
            self.assertEqual(e['_fundamental_supplement']['annual']['fields']['weighted_shares'],1.12e9,'full supplement as in the single analysis')
            self.assertNotIn('risk_annual',e['_fundamental_supplement'])
            leer={'_fundamental_supplement':None,'_supplement_symbol':None}
            self.assertEqual(T.ersatzdaten({'listing_symbol':'NASDAQ:AMD'},d),leer,'file of another listing')
            self.assertEqual(T.ersatzdaten({'listing_symbol':'NYSE:XX'},d),leer,'no file')
            Path(d,'NYSE_NA.json').write_text(json.dumps({**datei,'symbol':'NYSE:NA','annual':None}))
            self.assertIsNone(T.ersatzdaten({'listing_symbol':'NYSE:NA'},d)['_fundamental_supplement']['annual'],'no annual block, estimates still passed')
            self.assertEqual(T.ersatzdaten({'listing_symbol':'../x'},d),leer,'path characters are replaced')
            ein=T.eingabe({**JUMBO,**e});self.assertIn('_fundamental_supplement',ein);self.assertIn('_supplement_symbol',ein)

    def test_without_ts_build_python_values_stay_and_are_marked(self):
        rows=[zeile('A',JUMBO),{'ticker':'B','composite':40}]
        st=T.anwenden(rows,js='/nicht/vorhanden.mjs')
        self.assertTrue(st['ausfall']);self.assertEqual(rows[0]['scanner_method'],T.ALT);self.assertEqual(rows[0]['composite'],11)
        self.assertNotIn('_ts_input',rows[0]);self.assertNotIn('scanner_method',rows[1],'retained rows untouched')

    def test_second_pass_sees_peer_rows_as_the_app_does(self):
        # Lauf 17.11.2026: alle 1.341 Zeilen frisch, Peers ohne value_inputs -> Forward-KGV/PEG/FCF nur auf fester Skala.
        from unittest import mock
        aufrufe=[]
        def fake(offen,js,node,universum=None,**kw):
            aufrufe.append([dict(r) for r in universum])
            n=len(aufrufe)
            return {t:{'scanner_method':T.METHODE,'composite':10*n,'value_inputs':{'method':'value_inputs_v1','pe_forward':20.0},
                       'report_converted':{'pe':12.5} if t=='A' else None} for t in offen}
        rows=[zeile('A',JUMBO),zeile('B',JUMBO),{'ticker':'C','composite':40,'value_inputs':{'method':'alt'}}]
        with mock.patch.object(T,'rechnen',fake):
            st=T.anwenden(rows,js='x',risiko={},ordner=tempfile.gettempdir()+'/leer-nicht-vorhanden')
        self.assertEqual(st['durchgaenge'],2);self.assertEqual(len(aufrufe),2)
        self.assertNotIn('value_inputs',aufrufe[0][0],'erster Durchgang: frische Zeile ohne App-Felder')
        self.assertEqual(aufrufe[1][0]['value_inputs']['pe_forward'],20.0,'zweiter Durchgang: Peer-Zeile mit App-Feldern')
        self.assertEqual(aufrufe[1][0]['pe'],12.5,'umgerechnete Kennzahlen wie in der fertigen Zeile')
        self.assertEqual(aufrufe[1][2]['value_inputs'],{'method':'alt'},'uebernommene Zeilen unveraendert')
        self.assertEqual(rows[0]['composite'],20,'Ergebnis aus dem zweiten Durchgang');self.assertEqual(rows[2]['composite'],40)

    def test_second_pass_outage_keeps_first_pass(self):
        from unittest import mock
        n=[0]
        def fake(offen,js,node,universum=None,**kw):
            n[0]+=1
            return None if n[0]==2 else {t:{'scanner_method':T.METHODE,'composite':77} for t in offen}
        rows=[zeile('A',JUMBO)]
        with mock.patch.object(T,'rechnen',fake):
            st=T.anwenden(rows,js='x',risiko={},ordner=tempfile.gettempdir()+'/leer-nicht-vorhanden')
        self.assertEqual(st['durchgaenge'],1);self.assertFalse(st['ausfall']);self.assertEqual(rows[0]['composite'],77)

    def test_failing_node_process_counts_as_outage(self):
        with tempfile.TemporaryDirectory() as d:
            js=os.path.join(d,'kaputt.mjs');open(js,'w').write('process.exit(3)')
            rows=[zeile('A',JUMBO)];st=T.anwenden(rows,js=js)
        self.assertTrue(st['ausfall']);self.assertEqual(rows[0]['scanner_method'],T.ALT)


@unittest.skipUnless(os.environ.get('SCANNER_EVAL_JS'),'scanner-evaluate.mjs nicht gebaut')
class AppRechenweg(unittest.TestCase):
    def test_values_replaced_by_app_path(self):
        rows=[zeile('ATHEX:BELA',JUMBO),zeile('BLOCK',{**JUMBO,'price':80.0})]
        st=T.anwenden(rows,ordner=tempfile.mkdtemp())  # ohne Ergaenzungsdatei: reine Zeilenwerte
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
        # Erwartungsluecke nur als Kontext (scoreContribution 0), gesperrte Zeile mit Grund
        self.assertEqual(a['expectation_gap']['scoreContribution'],0);self.assertIsInstance(a['expectation_gap']['gap_pp'],float)
        self.assertEqual(b['expectation_gap']['status'],'Bewertungsdaten gesperrt')


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

    def test_report_currency_converted_with_ecb_rate(self):
        import json,datetime as dt
        # Equinor: ROIC-Betraege in USD (risk_financial.currency), Notierung NOK
        eq={**JUMBO,'ticker':'OSL:EQNR','currency':'NOK','price':407.6,'shares_out':2.6e9,'market_cap':407.6*2.6e9,'eps_trailing':2.8,
            'book_value_ps':15.0,'revenue':1e11,'ebitda':3.5e10,'ebit':2.5e10,'net_income':7e9,'net_debt':1e10,'free_cashflow':8e9,'total_debt':3e10,
            '52w_high':450,'52w_low':300,'risk_financial':{'asof':'2026-06-30','currency':'USD','source':'ROIC Enterprise Value · dieselbe Berichtszeile'}}
        gestern=(dt.date.today()-dt.timedelta(days=1)).isoformat()
        datei={'schema':1,'symbol':'OSL:EQNR','annual':None,'market':{'currency':'NOK'},'share_basis':None,
               'fx':{'base':'EUR','observed_at':gestern,'source_url':'https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml','rates':{'EUR':1,'USD':1.16,'NOK':11.09}}}
        with tempfile.TemporaryDirectory() as d:
            Path(d,'OSL_EQNR.json').write_text(json.dumps(datei))
            mit=[{**zeile('OSL:EQNR',eq),'listing_symbol':'OSL:EQNR'}];T.anwenden(mit,risiko={},ordner=d)
            ohne=[{**zeile('OSL:EQNR',eq),'listing_symbol':'OSL:EQNR'}];T.anwenden(ohne,risiko={},ordner=d+'/fehlt')
        self.assertNotEqual(mit[0]['kauf_urteil'],'Daten prüfen');self.assertGreater(mit[0]['fair_value'],100)
        self.assertEqual(ohne[0]['kauf_urteil'],'Daten prüfen');self.assertIn('EZB',' '.join(ohne[0]['valuation_issues']))
        # Zeilenwerte fuer Anzeige und Peers umgerechnet und gekennzeichnet; ohne Kurs bleiben sie, mit Status
        self.assertAlmostEqual(mit[0]['eps_trailing'],2.8*11.09/1.16,places=2);self.assertEqual(mit[0]['report_fx']['from'],'USD')
        self.assertAlmostEqual(mit[0]['pe'],407.6/(2.8*11.09/1.16),places=0)
        self.assertNotIn('report_converted',mit[0]);self.assertIn('EZB',ohne[0]['report_fx_status'])

    def test_newer_fiscal_year_from_supplement_reaches_the_row(self):
        import json,datetime as dt
        jetzt=dt.datetime.now(dt.timezone.utc)
        mu={**JUMBO,'ticker':'NASDAQ:MU','currency':'USD','price':778.31,'shares_out':1.122e9,'market_cap':8.7e11,'eps_trailing':7.65,'52w_high':1183,'52w_low':196,
            'income_period':'2025-08-28','income_currency':'USD'}
        datei={'schema':1,'symbol':'NASDAQ:MU','retrieved_at':jetzt.isoformat(),'annual_retrieved_at':jetzt.isoformat(),'latest_fiscal_end':'2026-09-03',
               'market':{'currency':'USD','quote_at':(jetzt-dt.timedelta(days=1)).isoformat(),'fields':{'price':778.31,'shares_out':1.122e9}},
               'annual':{'end':'2026-09-03','period_type':'annual','currency':'USD','source':'SEC companyfacts / US-GAAP',
                         'fields':{'eps_trailing':74.33,'revenue':1.33188e11,'net_income':8.4969e10,'equity':1.1e11,'cash':4.8e10,'total_debt':1.5e10,'ebitda':1e11,'ebit':9e10}},
               'share_basis':None,'risk_annual':{'end':'2026-08-31'}}
        with tempfile.TemporaryDirectory() as d:
            Path(d,'NASDAQ_MU.json').write_text(json.dumps(datei))
            rows=[{**zeile('NASDAQ:MU',mu),'listing_symbol':'NASDAQ:MU','eps_trailing':7.65,'pe':101.7}];T.anwenden(rows,risiko={},ordner=d)
        r=rows[0]
        self.assertTrue(r['annual_supplement_applied']);self.assertEqual(r['supplement_annual_end'],'2026-09-03')
        self.assertAlmostEqual(r['eps_trailing'],74.33);self.assertAlmostEqual(r['pe'],778.31/74.33,places=1)
        self.assertIsNone(r['supplement_retained_fields'],'newer fiscal year: nothing kept from the old ROIC year')
        # Jahresblock ohne EPS: die Zeile zeigt kein altes EPS mehr
        datei['annual']['fields'].pop('eps_trailing')
        with tempfile.TemporaryDirectory() as d:
            Path(d,'NASDAQ_MU.json').write_text(json.dumps(datei))
            rows=[{**zeile('NASDAQ:MU',mu),'listing_symbol':'NASDAQ:MU','eps_trailing':7.65,'pe':101.7}];T.anwenden(rows,risiko={},ordner=d)
        self.assertIsNone(rows[0]['eps_trailing']);self.assertIsNone(rows[0]['pe'])

    def test_peers_from_the_whole_universe(self):
        peers=[{'ticker':f'ATHEX:P{i}','listing_symbol':f'ATHEX:P{i}','isin':f'GRS00000000{i}','name':f'Peer {i}','name_full':f'Peer {i}','currency':'EUR',
                'sector':'Retail trade','industry':'Specialty stores','market_cap':3e9,'price':50,'eps_forward':2.5,'ev_ebitda':8+i,'pb':2+i/10,
                'roe':12+i,'gross_margin':40+i,'revenue_growth':3+i,'net_debt_ebitda':0.5} for i in range(1,7)]
        subject={**zeile('ATHEX:BELA',JUMBO),'listing_symbol':'ATHEX:BELA','isin':'GRS282183003','name':'Jumbo S.A.','currency':'EUR',
                 'sector':'Retail trade','industry':'Specialty stores','market_cap':3.7e9}
        rows=[subject,*peers]
        st=T.anwenden(rows,ordner=tempfile.mkdtemp())  # ohne Ergaenzungsdatei: reine Zeilenwerte
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
