"""Operating-Leasing je US-Abschluss für die Bewertung (us_operating_lease_v1, seit 23.11.2026, Entscheidung des Nutzers).

Unter US-GAAP mindert die Miete aus Operating-Leasing bereits den operativen Cashflow und das EBITDA. „Total Debt“ (Yahoo)
enthält die Leasingverbindlichkeit aber bei vielen Firmen zusätzlich (Messung 23.11.2026: 195 von 416 US-Titeln, 77 nicht,
144 nicht prüfbar). Dann zählt die Miete in DCF, EPV und EV/EBITDA doppelt. Dieses Modul liest aus denselben SEC-companyfacts,
die der Export ohnehin abruft, für den Bilanzstichtag des Jahresabschlusses (±5 Tage, nur 10-K):
- OperatingLeaseLiability (sonst Summe aus ...Current und ...Noncurrent),
- Finanzschulden ohne Leasing (LongTermDebt bzw. DebtLongtermAndShorttermCombinedAmount bzw. Teile, dazu
  ShortTermBorrowings und CommercialPaper),
und ordnet ein: enthalten, wenn „Total Debt“ näher an Finanzschulden + Leasing liegt als an den Finanzschulden allein.
Die App (fundamental-supplement.ts) prüft beim Lesen erneut und nimmt das Leasing nur bei „enthalten“ aus den Nettoschulden
der Bewertung; der Risikoscore behält es. Herkunft: Quell-URL, Prüfsumme der SEC-Antwort, Accession, Stichtag.
"""
import datetime as dt
import math

METHOD = 'us_operating_lease_v1'
STICHTAG_TOLERANZ = 5
LEASE_TOTAL = 'OperatingLeaseLiability'
LEASE_TEILE = ('OperatingLeaseLiabilityCurrent', 'OperatingLeaseLiabilityNoncurrent')
DEBT_TOTAL = ('LongTermDebt', 'DebtLongtermAndShorttermCombinedAmount')
DEBT_TEILE = ('LongTermDebtNoncurrent', 'LongTermDebtCurrent')
DEBT_KURZ = ('ShortTermBorrowings', 'CommercialPaper')


def _zahl(v):
 return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def wert(facts, tag, ende):
 treffer = []
 for f in ((facts or {}).get(tag) or {}).get('units', {}).get('USD', []):
  try:
   if f.get('form') not in ('10-K', '10-K/A') or not _zahl(f.get('val')) or 'start' in f:
    continue
   if abs((dt.date.fromisoformat(f['end']) - ende).days) > STICHTAG_TOLERANZ:
    continue
   treffer.append((f.get('filed', ''), f))
  except (KeyError, TypeError, ValueError):
   continue
 if not treffer:
  return None
 f = max(treffer, key=lambda x: x[0])[1]
 return {'wert': float(f['val']), 'tag': tag, 'ende': f['end'], 'accession': f.get('accn')}


def summe(facts, tags, ende):
 teile = [t for t in (wert(facts, x, ende) for x in tags) if t]
 if not teile:
  return None
 return {'wert': sum(t['wert'] for t in teile), 'tag': '+'.join(t['tag'] for t in teile), 'ende': teile[0]['ende'], 'accession': teile[0]['accession']}


def finanzschulden(facts, ende):
 lang = next((w for w in (wert(facts, t, ende) for t in DEBT_TOTAL) if w), None) or summe(facts, DEBT_TEILE, ende)
 if not lang:
  return None
 kurz = summe(facts, DEBT_KURZ, ende)
 return {**lang, 'wert': lang['wert'] + (kurz['wert'] if kurz else 0.0), 'tag': lang['tag'] + ('+' + kurz['tag'] if kurz else '')}


def einordnung(total_debt, schulden, lease):
 if not _zahl(total_debt) or not schulden or not lease or lease['wert'] <= 0:
  return 'offen'
 return 'enthalten' if abs(total_debt - schulden['wert'] - lease['wert']) < abs(total_debt - schulden['wert']) else 'nicht_enthalten'


def operating_lease(companyfacts, annual, cik, sha256, retrieved_at):
 """Block für die Ergänzungsdatei oder None (kein US-Abschluss, keine Fakten). Immer mit Grund, wenn offen."""
 if not annual or annual.get('currency') != 'USD' or not annual.get('end'):
  return None
 facts = ((companyfacts or {}).get('facts') or {}).get('us-gaap') or {}
 if not facts or str((companyfacts or {}).get('cik', '')).lstrip('0') != str(cik).lstrip('0'):
  return None
 ende = dt.date.fromisoformat(str(annual['end'])[:10])
 lease = wert(facts, LEASE_TOTAL, ende) or summe(facts, LEASE_TEILE, ende)
 schulden = finanzschulden(facts, ende)
 td = (annual.get('fields') or {}).get('total_debt')
 e = einordnung(td, schulden, lease)
 grund = None
 if e == 'offen':
  grund = ('Keine Operating-Leasingverbindlichkeit im 10-K zum Stichtag' if not lease or lease['wert'] <= 0
           else 'Finanzschulden ohne Leasing im 10-K nicht gefunden' if not schulden else 'Total Debt fehlt im Jahresabschluss')
 return {'method': METHOD, 'end': annual['end'], 'currency': 'USD', 'total_debt': td if _zahl(td) else None,
         'operating_lease_liability': lease, 'finanzschulden_sec': schulden, 'einordnung': e, 'grund': grund,
         'source': 'SEC companyfacts / US-GAAP', 'source_url': f'https://data.sec.gov/api/xbrl/companyfacts/CIK{int(cik):010d}.json',
         'sha256': sha256, 'retrieved_at': retrieved_at}
