"""Sektor 'Industrial services' nur bei Energie-Branchen als Energy (17.11.2026), identisch mit valuation.ts."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import sektor as S


class IndustrialServices(unittest.TestCase):
    def test_energy_only_for_energy_industries(self):
        for i in ('Oilfield services/Equipment','Contract drilling','Oil & gas pipelines'):
            self.assertEqual(S.normalisieren('Industrial services',i),'Energy',i)
        for i in ('Environmental services','Engineering & construction',None,'','Toiletries'):
            self.assertEqual(S.normalisieren('Industrial services',i),'Industrials',str(i))
        self.assertEqual(S.normalisieren('Energy minerals'),'Energy');self.assertIsNone(S.normalisieren(None))

    def test_same_pattern_as_app(self):
        app=(Path(__file__).resolve().parents[1]/'risk_precompute'/'src'/'lib'/'valuation.ts').read_text(encoding='utf-8')
        self.assertIn(r'ENERGY_SERVICE_INDUSTRY = /\b(oil\w*|gas|drilling|pipelines?)\b/i',app)
        self.assertEqual(S._ENERGIE_DIENSTE.pattern,r'\b(oil\w*|gas|drilling|pipelines?)\b')


if __name__=='__main__':unittest.main()
