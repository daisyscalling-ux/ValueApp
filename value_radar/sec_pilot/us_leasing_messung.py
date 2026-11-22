"""Messung US-Leasing in den Nettoschulden (seit 22.11.2026, Entscheidung des Nutzers: erst messen, dann entscheiden).

Unter US-GAAP mindert die Miete aus Operating-Leasing den operativen Cashflow. Der Jahresblock (Yahoo „Total Debt“)
enthaelt die Leasingverbindlichkeiten aber vermutlich zusaetzlich (MGM: 31,4 Mrd $ bei rund 6 Mrd $ Anleihen). Dann
zaehlt die Miete im DCF doppelt: einmal im freien Cashflow, einmal in den Nettoschulden.

Die Messung liest je US-Titel des Universums (CIK, Waehrung USD) die SEC-companyfacts (us-gaap) und nimmt aus dem 10-K
mit Bilanzstichtag = Stichtag des Jahresblocks (+-5 Tage):
- OperatingLeaseLiability (sonst Summe aus ...Current und ...Noncurrent),
- Finanzschulden ohne Leasing (LongTermDebt bzw. ...Noncurrent + ...Current, dazu ShortTermBorrowings, CommercialPaper).
Einordnung je Titel: Liegt „Total Debt“ naeher an Finanzschulden + Leasing als an den Finanzschulden allein, gilt das
Leasing als enthalten. Ohne SEC-Finanzschulden bleibt die Einordnung offen.
Wirkung: DCF je Aktie aus den Teilen der Universumszeile (score_diagnostics.dcf_inputs) mit Nettoschulden minus
Leasing. Naeherung: Der Fremdkapitalanteil im Zins bleibt unveraendert (ohne Leasing waere er kleiner, der Zins etwas hoeher).
Nur Messung: schreibt nach us-leasing-output/, aendert keine Bewertung. Abruf mit SEC_USER_AGENT, hoechstens 2 je Sekunde.
"""
import datetime as dt
import hashlib
import json
import math
import os
import re
import statistics
import sys
import time
import urllib.request
from pathlib import Path

METHOD = 'us_operating_lease_in_net_debt_measure_v1'
ROOT = Path(__file__).resolve().parents[1]
STICHTAG_TOLERANZ = 5
LEASE_TOTAL = 'OperatingLeaseLiability'
LEASE_TEILE = ('OperatingLeaseLiabilityCurrent', 'OperatingLeaseLiabilityNoncurrent')
DEBT_TOTAL = ('LongTermDebt', 'DebtLongtermAndShorttermCombinedAmount')
DEBT_TEILE = ('LongTermDebtNoncurrent', 'LongTermDebtCurrent')
DEBT_KURZ = ('ShortTermBorrowings', 'CommercialPaper')


def _zahl(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _datei(sym):
    return re.sub(r'[^A-Za-z0-9._-]', '_', sym) + '.json'


def wert(facts, tag, ende):
    """Bilanzwert eines us-gaap-Tags aus einem 10-K mit Stichtag ende (+-STICHTAG_TOLERANZ Tage); juengste Einreichung."""
    treffer = []
    for f in (((facts or {}).get('us-gaap') or {}).get(tag) or {}).get('units', {}).get('USD', []):
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
    return {'wert': float(f['val']), 'tag': tag, 'ende': f['end'], 'accession': f.get('accn'), 'form': f.get('form')}


def summe(facts, tags, ende):
    teile = [wert(facts, t, ende) for t in tags]
    gefunden = [t for t in teile if t]
    if not gefunden:
        return None
    return {'wert': sum(t['wert'] for t in gefunden), 'tag': '+'.join(t['tag'] for t in gefunden), 'ende': gefunden[0]['ende'],
            'accession': gefunden[0]['accession'], 'form': gefunden[0]['form']}


def leasing(facts, ende):
    return wert(facts, LEASE_TOTAL, ende) or summe(facts, LEASE_TEILE, ende)


def finanzschulden(facts, ende):
    lang = next((w for w in (wert(facts, t, ende) for t in DEBT_TOTAL) if w), None) or summe(facts, DEBT_TEILE, ende)
    if not lang:
        return None
    kurz = summe(facts, DEBT_KURZ, ende)
    return {**lang, 'wert': lang['wert'] + (kurz['wert'] if kurz else 0.0), 'tag': lang['tag'] + ('+' + kurz['tag'] if kurz else '')}


def einordnung(total_debt, schulden, lease):
    """'enthalten' | 'nicht_enthalten' | 'offen' (fehlende Werte oder Leasing 0)."""
    if not _zahl(total_debt) or not schulden or not lease or lease['wert'] <= 0:
        return 'offen'
    ohne = abs(total_debt - schulden['wert'])
    mit = abs(total_debt - schulden['wert'] - lease['wert'])
    return 'enthalten' if mit < ohne else 'nicht_enthalten'


def dcf_wirkung(row, lease_wert):
    """DCF je Aktie vorher/nachher aus den offengelegten Teilen; None ohne Teile."""
    d = ((row.get('score_diagnostics') or {}).get('dcf_inputs')) or {}
    pv, tv, nd, n, kurs = d.get('pv_explizit'), d.get('pv_endwert'), d.get('nettoschulden'), d.get('aktien'), row.get('price')
    if not all(_zahl(x) for x in (pv, tv, nd, n, kurs)) or n <= 0 or kurs <= 0:
        return None
    vorher = (pv + tv - nd) / n
    nachher = (pv + tv - (nd - lease_wert)) / n
    return {'dcf_kurs_vorher': round(vorher / kurs, 4) if vorher > 0 else None, 'dcf_kurs_nachher': round(nachher / kurs, 4) if nachher > 0 else None,
            'vorher_offen': vorher <= 0, 'nachher_offen': nachher <= 0, 'playbook': row.get('playbook')}


def jahresblock(ordner, sym):
    try:
        s = json.loads((Path(ordner) / _datei(sym)).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    a = (s or {}).get('annual') or {}
    if s.get('symbol') != sym or a.get('currency') != 'USD' or not a.get('end'):
        return None
    td = (a.get('fields') or {}).get('total_debt')
    return {'ende': a['end'], 'total_debt': td if _zahl(td) else None, 'quelle': a.get('source'),
            'quelle_total_debt': ((a.get('field_sources') or {}).get('total_debt') or {}).get('source') or a.get('source')}


def auswahl(universum):
    out = []
    for r in universum.get('kandidaten', []):
        if r.get('currency') == 'USD' and r.get('cik') and r.get('listing_symbol') and r.get('playbook') != 'financial':
            out.append(r)
    return out


def messen(universum, ordner, holen, jetzt):
    zeilen, fehler = [], {}
    for r in auswahl(universum):
        sym = r['listing_symbol']
        jb = jahresblock(ordner, sym)
        if not jb:
            fehler['jahresblock_fehlt'] = fehler.get('jahresblock_fehlt', 0) + 1
            continue
        try:
            roh = holen(r['cik'])
        except Exception as e:  # Netz- oder HTTP-Fehler: zaehlen, nicht wiederholen
            fehler['abruf_' + type(e).__name__] = fehler.get('abruf_' + type(e).__name__, 0) + 1
            continue
        facts = json.loads(roh).get('facts') or {}
        ende = dt.date.fromisoformat(jb['ende'][:10])
        lease, schulden = leasing(facts, ende), finanzschulden(facts, ende)
        url = f'https://data.sec.gov/api/xbrl/companyfacts/CIK{int(r["cik"]):010d}.json'
        z = {'symbol': sym, 'name': r.get('name'), 'isin': r.get('isin'), 'cik': str(r['cik']), 'jahresende': jb['ende'],
             'total_debt': jb['total_debt'], 'total_debt_quelle': jb['quelle_total_debt'],
             'leasing': lease, 'finanzschulden_sec': schulden, 'einordnung': einordnung(jb['total_debt'], schulden, lease),
             'sourceUrl': url, 'sha256': hashlib.sha256(roh).hexdigest(), 'retrievedAt': jetzt.isoformat()}
        if lease and z['einordnung'] == 'enthalten':
            z['dcf'] = dcf_wirkung(r, lease['wert'])
        zeilen.append(z)
    return zeilen, fehler


def zusammenfassen(zeilen, fehler):
    ein = [z for z in zeilen if z['einordnung'] == 'enthalten']
    mit_dcf = [z for z in ein if z.get('dcf')]
    vorher = [z['dcf']['dcf_kurs_vorher'] for z in mit_dcf if z['dcf']['dcf_kurs_vorher'] is not None]
    nachher = [z['dcf']['dcf_kurs_nachher'] for z in mit_dcf if z['dcf']['dcf_kurs_nachher'] is not None]
    anteil = [z['leasing']['wert'] / z['total_debt'] for z in ein if z['total_debt']]
    beide = [(z['dcf']['dcf_kurs_vorher'], z['dcf']['dcf_kurs_nachher']) for z in mit_dcf
             if z['dcf']['dcf_kurs_vorher'] is not None and z['dcf']['dcf_kurs_nachher'] is not None]
    return {'titel': len(zeilen), 'einordnung': {k: sum(z['einordnung'] == k for z in zeilen) for k in ('enthalten', 'nicht_enthalten', 'offen')},
            'mit_leasing': sum(1 for z in zeilen if z['leasing'] and z['leasing']['wert'] > 0),
            'leasing_anteil_an_total_debt_median': round(statistics.median(anteil), 4) if anteil else None,
            'dcf_teile': len(mit_dcf), 'dcf_kurs_median_vorher': round(statistics.median(vorher), 4) if vorher else None,
            'dcf_kurs_median_nachher': round(statistics.median(nachher), 4) if nachher else None,
            'dcf_aenderung_median': round(statistics.median(n / v - 1 for v, n in beide), 4) if beide else None,
            'vorher_offen_nachher_wert': sum(1 for z in mit_dcf if z['dcf']['vorher_offen'] and not z['dcf']['nachher_offen']),
            'fehler': fehler}


def bericht(summary, zeilen):
    s = summary
    zeilen_md = sorted((z for z in zeilen if z.get('dcf')), key=lambda z: -(z['leasing']['wert'] / (z['total_debt'] or 1)))[:25]
    t = ['# Messung US-Leasing in den Nettoschulden', '', f"Methode `{METHOD}`. Nur Messung, keine Bewertungsänderung.", '',
         f"- US-Titel (ohne Finanzmodell) gemessen: {s['titel']}, mit Operating-Leasing: {s['mit_leasing']}",
         f"- Leasing in Total Debt enthalten: {s['einordnung']['enthalten']}, nicht enthalten: {s['einordnung']['nicht_enthalten']}, offen: {s['einordnung']['offen']}",
         f"- Leasinganteil an Total Debt (Median, enthalten): {s['leasing_anteil_an_total_debt_median']}",
         f"- DCF/Kurs Median vorher {s['dcf_kurs_median_vorher']} → ohne Leasing {s['dcf_kurs_median_nachher']} ({s['dcf_teile']} Titel mit DCF-Teilen); Änderung je Titel Median {s['dcf_aenderung_median']}",
         f"- DCF vorher offen (Eigenkapital ≤ 0), ohne Leasing mit Wert: {s['vorher_offen_nachher_wert']}",
         f"- Fehler: {s['fehler']}", '', '| Titel | Leasing Mrd $ | Total Debt Mrd $ | DCF/Kurs vorher | ohne Leasing |', '|---|---|---|---|---|']
    for z in zeilen_md:
        d = z['dcf']
        t.append(f"| {z['symbol']} | {z['leasing']['wert'] / 1e9:.2f} | {(z['total_debt'] or 0) / 1e9:.2f} | {d['dcf_kurs_vorher'] if d['dcf_kurs_vorher'] is not None else 'offen'} | {d['dcf_kurs_nachher'] if d['dcf_kurs_nachher'] is not None else 'offen'} |")
    return '\n'.join(t) + '\n'


def holer(ua):
    letzte = [0.0]

    def holen(cik):
        time.sleep(max(0.0, 0.6 - (time.monotonic() - letzte[0])))
        letzte[0] = time.monotonic()
        req = urllib.request.Request(f'https://data.sec.gov/api/xbrl/companyfacts/CIK{int(cik):010d}.json',
                                     headers={'User-Agent': ua, 'Accept': 'application/json'})
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read()
    return holen


def main():
    ua = os.getenv('SEC_USER_AGENT', '').strip()
    if not ua:
        print('SEC_USER_AGENT fehlt; keine Abfrage ohne den vorgesehenen User-Agent.')
        return 2
    universum = json.loads((ROOT / 'daten' / 'cf_universum.json').read_text(encoding='utf-8'))
    jetzt = dt.datetime.now(dt.timezone.utc)
    zeilen, fehler = messen(universum, ROOT / 'daten' / 'fundamentals', holer(ua), jetzt)
    s = zusammenfassen(zeilen, fehler)
    out = Path('us-leasing-output')
    out.mkdir(exist_ok=True)
    (out / 'us_leasing_messung.json').write_text(json.dumps({'schema': 1, 'method': METHOD, 'generatedAt': jetzt.isoformat(),
                                                              'summary': s, 'stocks': zeilen}, ensure_ascii=False, indent=1), encoding='utf-8')
    (out / 'report.md').write_text(bericht(s, zeilen), encoding='utf-8')
    print(json.dumps(s, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
