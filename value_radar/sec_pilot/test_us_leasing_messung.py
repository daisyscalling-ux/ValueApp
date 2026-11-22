import datetime as dt
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import us_leasing_messung as m

ENDE = dt.date(2025, 12, 31)


def f(val, end='2025-12-31', form='10-K', filed='2026-02-20', accn='0001-26-1', **extra):
    return {'val': val, 'end': end, 'form': form, 'filed': filed, 'accn': accn, **extra}


def facts(**tags):
    return {'us-gaap': {t: {'units': {'USD': v}} for t, v in tags.items()}}


class Werte(unittest.TestCase):
    def test_nur_10k_mit_stichtag(self):
        x = facts(OperatingLeaseLiability=[f(5e9, form='10-Q'), f(4e9, end='2024-12-31'), f(3e9, end='2026-01-03')])
        self.assertEqual(m.leasing(x, ENDE)['wert'], 3e9)  # 3 Tage Abstand zulaessig
        self.assertIsNone(m.leasing(facts(OperatingLeaseLiability=[f(3e9, end='2026-01-10')]), ENDE))

    def test_juengste_einreichung_und_keine_perioden(self):
        x = facts(OperatingLeaseLiability=[f(2e9, filed='2026-02-01'), f(2.5e9, filed='2026-05-01', form='10-K/A'),
                                           f(9e9, start='2025-01-01')])
        self.assertEqual(m.leasing(x, ENDE)['wert'], 2.5e9)

    def test_teile_wenn_summe_fehlt(self):
        x = facts(OperatingLeaseLiabilityCurrent=[f(1e9)], OperatingLeaseLiabilityNoncurrent=[f(4e9)])
        r = m.leasing(x, ENDE)
        self.assertEqual(r['wert'], 5e9)
        self.assertIn('Current', r['tag'])

    def test_ungueltige_werte(self):
        x = facts(OperatingLeaseLiability=[f(None), f(True), f('3')])
        self.assertIsNone(m.leasing(x, ENDE))
        self.assertIsNone(m.leasing({}, ENDE))

    def test_finanzschulden_mit_kurzfristigen(self):
        x = facts(LongTermDebtNoncurrent=[f(5e9)], LongTermDebtCurrent=[f(1e9)], CommercialPaper=[f(0.5e9)])
        self.assertEqual(m.finanzschulden(x, ENDE)['wert'], 6.5e9)
        self.assertIsNone(m.finanzschulden(facts(CommercialPaper=[f(1e9)]), ENDE))


class Einordnung(unittest.TestCase):
    def test_enthalten_und_nicht(self):
        s, l = {'wert': 6e9}, {'wert': 24e9}
        self.assertEqual(m.einordnung(30.5e9, s, l), 'enthalten')
        self.assertEqual(m.einordnung(6.2e9, s, l), 'nicht_enthalten')

    def test_offen(self):
        self.assertEqual(m.einordnung(None, {'wert': 1}, {'wert': 1}), 'offen')
        self.assertEqual(m.einordnung(5e9, None, {'wert': 1e9}), 'offen')
        self.assertEqual(m.einordnung(5e9, {'wert': 4e9}, {'wert': 0}), 'offen')


class Wirkung(unittest.TestCase):
    row = {'price': 10.0, 'playbook': 'quality', 'score_diagnostics': {'dcf_inputs': {'pv_explizit': 4e9, 'pv_endwert': 6e9, 'nettoschulden': 12e9, 'aktien': 1e8}}}

    def test_vorher_offen_nachher_wert(self):
        d = m.dcf_wirkung(self.row, 5e9)
        self.assertTrue(d['vorher_offen'])
        self.assertFalse(d['nachher_offen'])
        self.assertEqual(d['dcf_kurs_nachher'], 3.0)

    def test_ohne_teile(self):
        self.assertIsNone(m.dcf_wirkung({'price': 10, 'score_diagnostics': {'dcf_inputs': {'pv_explizit': None}}}, 1e9))
        self.assertIsNone(m.dcf_wirkung({**self.row, 'price': 0}, 1e9))


class Lauf(unittest.TestCase):
    def test_messen_filtert_und_fuehrt_herkunft(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / 'NYSE_MGM.json').write_text(json.dumps({'symbol': 'NYSE:MGM', 'annual': {'end': '2025-12-31', 'currency': 'USD', 'source': 'Yahoo annual statements', 'fields': {'total_debt': 31.4e9}}}))
            (Path(tmp) / 'NYSE_XX.json').write_text(json.dumps({'symbol': 'NYSE:ANDERS', 'annual': {'end': '2025-12-31', 'currency': 'USD', 'fields': {'total_debt': 1e9}}}))
            uni = {'kandidaten': [
                {**Wirkung.row, 'listing_symbol': 'NYSE:MGM', 'cik': '789570', 'currency': 'USD', 'isin': 'US5529531015'},
                {'listing_symbol': 'NYSE:XX', 'cik': '1', 'currency': 'USD', 'playbook': 'quality'},
                {'listing_symbol': 'NYSE:BANK', 'cik': '2', 'currency': 'USD', 'playbook': 'financial'},
                {'listing_symbol': 'XETR:SAP', 'cik': '3', 'currency': 'EUR', 'playbook': 'quality'},
                {'listing_symbol': 'NYSE:OHNECIK', 'currency': 'USD', 'playbook': 'quality'}]}
            roh = json.dumps({'facts': facts(OperatingLeaseLiability=[f(24e9)], LongTermDebt=[f(6.4e9)])}).encode()
            abrufe = []
            zeilen, fehler = m.messen(uni, tmp, lambda cik: abrufe.append(cik) or roh, dt.datetime(2026, 11, 22, tzinfo=dt.timezone.utc))
        self.assertEqual(abrufe, ['789570'])  # Symbol der Datei passt nicht -> kein Abruf; Finanzwerte, EUR, ohne CIK nicht gewaehlt
        self.assertEqual(fehler, {'jahresblock_fehlt': 1})
        z = zeilen[0]
        self.assertEqual(z['einordnung'], 'enthalten')
        self.assertTrue(z['sourceUrl'].endswith('CIK0000789570.json'))
        self.assertEqual(len(z['sha256']), 64)
        self.assertIn('dcf', z)
        s = m.zusammenfassen(zeilen, fehler)
        self.assertEqual(s['einordnung']['enthalten'], 1)
        self.assertEqual(s['vorher_offen_nachher_wert'], 1)
        self.assertIn('NYSE:MGM', m.bericht(s, zeilen))

    def test_abruffehler_gezaehlt(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / 'NYSE_A.json').write_text(json.dumps({'symbol': 'NYSE:A', 'annual': {'end': '2025-12-31', 'currency': 'USD', 'fields': {'total_debt': 1e9}}}))
            def kaputt(cik):
                raise TimeoutError()
            zeilen, fehler = m.messen({'kandidaten': [{'listing_symbol': 'NYSE:A', 'cik': '5', 'currency': 'USD', 'playbook': 'quality'}]}, tmp, kaputt, dt.datetime.now(dt.timezone.utc))
        self.assertEqual(zeilen, [])
        self.assertEqual(fehler, {'abruf_TimeoutError': 1})

    def test_ohne_user_agent_kein_abruf(self):
        import os
        alt = os.environ.pop('SEC_USER_AGENT', None)
        try:
            self.assertEqual(m.main(), 2)
        finally:
            if alt is not None:
                os.environ['SEC_USER_AGENT'] = alt


if __name__ == '__main__':
    unittest.main()
