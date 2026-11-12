"""Playbook-Zuordnung mit vereinheitlichtem Sektor, Spiegel von classifyPlaybook (valueapp-cf, valuation.ts)."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import valuation


class PlaybookSector(unittest.TestCase):
    def case(self,**f):return valuation.classify_playbook({'revenue_growth':0.05,**f})

    def test_provider_sector_names_are_normalized(self):
        # ROIC/FactSet-Namen wie im Universum (cf_universum.json): 274 Titel "Finance".
        self.assertEqual(self.case(sector='Finance',industry='Major Banks'),'financial')
        self.assertEqual(self.case(sector='Financial Services',industry='Banks - Diversified'),'financial')
        self.assertEqual(self.case(sector='Process industries',industry='Chemicals: Specialty'),'cyclical')
        self.assertEqual(self.case(sector='Non-energy minerals',industry='Other metals/Minerals'),'cyclical')
        self.assertEqual(self.case(sector='Energy minerals',industry='Integrated Oil'),'cyclical')

    def test_unchanged_cases(self):
        self.assertEqual(self.case(sector='Electronic technology',industry='Semiconductors'),'quality')
        self.assertEqual(self.case(sector='Technology services',industry='Packaged Software',revenue_growth=0.30),'inflection')
        # Defensive Sektoren werden nie zyklisch, auch mit Stichwort ("gas")
        self.assertEqual(self.case(sector='Utilities',industry='Gas Distributors'),'quality')
        self.assertEqual(self.case(sector='Consumer non-durables',industry='Food: Specialty/Candy'),'quality')
        self.assertEqual(self.case(sector='Finance',industry='Major Banks',_ist_zyklisch=True),'cyclical')

    def test_payment_networks_are_not_balance_sheet_financials(self):
        self.assertEqual(self.case(ticker='V',sector='Finance',industry='Finance/Rental/Leasing',revenue_growth=0.10),'quality')
        self.assertEqual(self.case(ticker='NYSE:MA',sector='Finance',industry='Miscellaneous Commercial Services',revenue_growth=0.12),'quality')
        # Gleiche Branche, anderer Titel: bleibt Finanzwert
        self.assertEqual(self.case(ticker='AXP',sector='Finance',industry='Finance/Rental/Leasing'),'financial')


if __name__=='__main__':unittest.main()
