"""Zusatztitel des Universums (universe_additions.py): Pflichtfelder, ISIN-Pruefziffer, Pruefdatum, Identitaet."""
import datetime as dt,json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import universe_additions as U
import index_membership as IM

MFC={'ticker':'MFC','listing_symbol':'NYSE:MFC','isin':'CA56501R1064','currency':'USD','security_type':'stock','name':'Manulife Financial Corporation',
     'reason':'Test','added_on':'2026-11-15','reviewed_on':'2026-11-15','review_expires':'2027-11-15'}
TODAY=dt.date(2026,11,16)

def write(titles,**doc):
    d=tempfile.mkdtemp();p=Path(d,'z.json');p.write_text(json.dumps({'schema':1,'method':U.METHOD,'titles':titles,**doc}));return p

class Load(unittest.TestCase):
    def test_valid_entry(self):
        out,problems=U.load(write([MFC]),TODAY);self.assertEqual(list(out),['MFC']);self.assertEqual(problems,[])
    def test_repository_file_valid(self):
        out,problems=U.load(today=max(TODAY,dt.date(2026,11,19)));self.assertIn('MFC',out);self.assertEqual(problems,[])
        ant=out['ANT'];self.assertEqual((ant['listing_symbol'],ant['isin'],ant['currency']),('NASDAQ:ANT','US03703U1079','USD'))
        self.assertTrue(U.isin_valid('US03703U1079'));self.assertFalse(U.isin_valid('US03703U1078'))
        self.assertTrue(ant['source_url'].startswith('https://www.sec.gov/'))
    def test_rejections_with_reason(self):
        cases=[({**MFC,'isin':'CA56501R1065'},'isin_pruefziffer'),({**MFC,'isin':'XX'},'isin_pruefziffer'),
               ({**MFC,'review_expires':'2026-11-16'},'pruefung_abgelaufen'),({**MFC,'reviewed_on':'2026-12-01'},'pruefung_in_zukunft'),
               ({k:v for k,v in MFC.items() if k!='reason'},'felder_fehlen'),({**MFC,'listing_symbol':'MFC'},'symbol_ungueltig'),
               ({**MFC,'reviewed_on':'15.11.2026'},'datum_ungueltig')]
        for entry,reason in cases:
            out,problems=U.load(write([entry]),TODAY);self.assertEqual(out,{});self.assertIn(reason,problems[0])
        out,problems=U.load(write([MFC,MFC]),TODAY);self.assertEqual(list(out),['MFC']);self.assertIn('doppelt',problems[0])
    def test_file_errors(self):
        self.assertEqual(U.load(Path(tempfile.mkdtemp(),'fehlt.json'),TODAY),({},[]))
        d=tempfile.mkdtemp();p=Path(d,'x.json');p.write_text(json.dumps({'schema':2,'method':U.METHOD,'titles':[MFC]}))
        self.assertEqual(U.load(p,TODAY),({},['schema_oder_methode_falsch']))
        p.write_text('{kaputt');self.assertIn('datei_unlesbar',U.load(p,TODAY)[1][0])

class Identity(unittest.TestCase):
    def test_row_must_match_listing_isin_currency(self):
        row={'ticker':'MFC','listing_symbol':'NYSE:MFC','isin':'CA56501R1064','currency':'USD'}
        self.assertIsNone(U.check_row(row,MFC))
        self.assertEqual(U.check_row({**row,'listing_symbol':'TSX:MFC'},MFC),'curated_addition_mismatch:listing_symbol')
        self.assertEqual(U.check_row({**row,'isin':'US0378331005'},MFC),'curated_addition_mismatch:isin')
        self.assertEqual(U.check_row({**row,'currency':'CAD'},MFC),'curated_addition_mismatch:currency')
        m=U.mark(dict(row),MFC);self.assertEqual(m['universe_addition']['review_expires'],'2027-11-15')
    def test_scope_with_additions_stays_complete(self):
        members={'SP500':['A']*480,'NDX':['B']*95,'STOXX600':['C']*590,'NIKKEI225':['D']*220,'DAX':['E']*40,U.INDEX:['MFC']}
        sc=IM.scope({k:[f'{v[0]}{i}' for i in range(len(v))] if k!=U.INDEX else v for k,v in members.items()},{})
        self.assertEqual(sc['members']['MFC'],[U.INDEX]);self.assertTrue(IM.scope_complete({'index_scope':sc}))

if __name__=='__main__':unittest.main()
