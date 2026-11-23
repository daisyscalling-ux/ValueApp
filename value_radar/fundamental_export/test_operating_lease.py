import unittest
from operating_lease import operating_lease, einordnung, wert, METHOD
import datetime as dt


def f(val, end='2025-12-31', form='10-K', filed='2026-02-20', accn='0001-26-1', **x):
 return {'val': val, 'end': end, 'form': form, 'filed': filed, 'accn': accn, **x}


def cf(cik='789570', **tags):
 return {'cik': cik, 'facts': {'us-gaap': {t: {'units': {'USD': v}} for t, v in tags.items()}}}


ANNUAL = {'end': '2025-12-31', 'currency': 'USD', 'fields': {'total_debt': 31.4e9}}


class Lease(unittest.TestCase):
 def test_enthalten_mit_herkunft(self):
  b = operating_lease(cf(OperatingLeaseLiability=[f(25e9)], LongTermDebt=[f(6.4e9)]), ANNUAL, '789570', 'a' * 64, '2026-11-23T00:00:00+00:00')
  self.assertEqual((b['method'], b['einordnung'], b['grund']), (METHOD, 'enthalten', None))
  self.assertEqual(b['operating_lease_liability']['wert'], 25e9)
  self.assertTrue(b['source_url'].endswith('CIK0000789570.json'))
  self.assertEqual((b['sha256'], b['end'], b['total_debt']), ('a' * 64, '2025-12-31', 31.4e9))

 def test_nicht_enthalten_und_offen_mit_grund(self):
  b = operating_lease(cf(OperatingLeaseLiability=[f(1e9)], LongTermDebt=[f(30e9)]), {**ANNUAL, 'fields': {'total_debt': 30e9}}, '789570', 'x', 't')
  self.assertEqual(b['einordnung'], 'nicht_enthalten')
  b = operating_lease(cf(LongTermDebt=[f(30e9)]), ANNUAL, '789570', 'x', 't')
  self.assertEqual(b['einordnung'], 'offen'); self.assertIn('Keine Operating', b['grund'])
  b = operating_lease(cf(OperatingLeaseLiability=[f(1e9)]), ANNUAL, '789570', 'x', 't')
  self.assertIn('Finanzschulden', b['grund'])
  b = operating_lease(cf(OperatingLeaseLiability=[f(1e9)], LongTermDebt=[f(3e9)]), {**ANNUAL, 'fields': {}}, '789570', 'x', 't')
  self.assertIn('Total Debt', b['grund'])

 def test_falsche_identitaet_waehrung_stichtag(self):
  self.assertIsNone(operating_lease(cf(cik='1', OperatingLeaseLiability=[f(1e9)]), ANNUAL, '789570', 'x', 't'), 'andere CIK')
  self.assertIsNone(operating_lease(cf(OperatingLeaseLiability=[f(1e9)]), {**ANNUAL, 'currency': 'EUR'}, '789570', 'x', 't'))
  self.assertIsNone(operating_lease(cf(OperatingLeaseLiability=[f(1e9)]), None, '789570', 'x', 't'))
  e = dt.date(2025, 12, 31)
  self.assertIsNone(wert(cf(OperatingLeaseLiability=[f(1e9, end='2024-12-31')])['facts']['us-gaap'], 'OperatingLeaseLiability', e), 'Vorjahr')
  self.assertIsNone(wert(cf(OperatingLeaseLiability=[f(1e9, form='10-Q')])['facts']['us-gaap'], 'OperatingLeaseLiability', e), 'nur 10-K')
  self.assertEqual(wert(cf(OperatingLeaseLiability=[f(1e9, filed='2026-01-01'), f(2e9, filed='2026-03-01', form='10-K/A')])['facts']['us-gaap'], 'OperatingLeaseLiability', e)['wert'], 2e9)

 def test_teile_und_kurzfristige_schulden(self):
  b = operating_lease(cf(OperatingLeaseLiabilityCurrent=[f(1e9)], OperatingLeaseLiabilityNoncurrent=[f(4e9)], LongTermDebtNoncurrent=[f(5e9)], CommercialPaper=[f(1e9)]),
                      {**ANNUAL, 'fields': {'total_debt': 11e9}}, '789570', 'x', 't')
  self.assertEqual((b['operating_lease_liability']['wert'], b['finanzschulden_sec']['wert'], b['einordnung']), (5e9, 6e9, 'enthalten'))
  self.assertEqual(einordnung(None, {'wert': 1}, {'wert': 1}), 'offen')


if __name__ == '__main__':
 unittest.main()
