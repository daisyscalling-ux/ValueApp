import json,tempfile,unittest
from pathlib import Path
import app_copies


class AppCopies(unittest.TestCase):
    def test_all_copies_identical_to_listed_app_originals(self):
        self.assertEqual(app_copies.pruefen(),[])

    def test_list_covers_every_file_under_src(self):
        liste={e['pipeline'] for e in json.loads(app_copies.LISTE.read_text(encoding='utf-8'))['files']}
        src=app_copies.ROOT/'value_radar/risk_precompute/src'
        fehlend=[str(p.relative_to(app_copies.ROOT)) for p in src.rglob('*') if p.is_file() and p.suffix in ('.ts','.json') and str(p.relative_to(app_copies.ROOT)) not in liste]
        self.assertEqual(fehlend,[],'neue Kopie ohne Eintrag in app-copies.json')

    def test_detects_changed_copy_and_allows_only_listed_path_change(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'x.ts';p.write_text("import a from '../m.json';\n",encoding='utf-8')
            sha=app_copies._sha("import a from './m.json';\n".encode())
            liste=Path(d)/'l.json'
            rel=str(p.relative_to(app_copies.ROOT)) if str(p).startswith(str(app_copies.ROOT)) else None
            orig=app_copies.ROOT
            try:
                app_copies.ROOT=Path(d)
                liste.write_text(json.dumps({'files':[{'app':'x.ts','pipeline':'x.ts','sha256':sha,'normalize':[["'../m.json'","'./m.json'"]]}]}),encoding='utf-8')
                self.assertEqual(app_copies.pruefen(liste),[])
                liste.write_text(json.dumps({'files':[{'app':'x.ts','pipeline':'x.ts','sha256':sha}]}),encoding='utf-8')
                self.assertEqual(len(app_copies.pruefen(liste)),1,'without the listed path change it is a deviation')
                p.write_text("import a from '../m.json';// geaendert\n",encoding='utf-8')
                liste.write_text(json.dumps({'files':[{'app':'x.ts','pipeline':'x.ts','sha256':sha,'normalize':[["'../m.json'","'./m.json'"]]}]}),encoding='utf-8')
                self.assertEqual(len(app_copies.pruefen(liste)),1)
            finally:
                app_copies.ROOT=orig


if __name__=='__main__':unittest.main()
