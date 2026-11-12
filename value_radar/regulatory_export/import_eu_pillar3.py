"""EU-Banken: Schluesselkennzahlen (EU KM1) aus dem EBA Pillar 3 Data Hub.

Seit 2026 veroeffentlicht die EBA die Saeule-3-Offenlegung grosser EU-Institute zentral und unveraendert
(Originaldateien als XBRL-CSV unter errp.eba.europa.eu/public-documents). Dieses Programm laedt je Bank aus
eu-bank-map.json (LEI) die juengste Einreichung des Moduls CODIS, prueft Identitaet, Stichtag und Taxonomie und
liest aus Tabelle K_61.00 (EU KM1, Spalte T) die Kapitalquoten, die Kapitalanforderungen, LCR und NSFR.

CET1-Anforderung = 4,5 % Mindestquote + CET1-Anteil der SREP-Zusatzanforderung (EU 7e) + kombinierte
Kapitalpufferanforderung (Zeile 11). Sie wird nur uebernommen, wenn die Gesamtanforderung (EU 11a) auf 0,05
Prozentpunkte der SREP-Gesamtanforderung (EU 7g) plus kombinierter Pufferanforderung entspricht; gerundet
gemeldete Werte (z. B. auf ganze Prozent) fallen dadurch heraus.

Aufruf: python import_eu_pillar3.py p3dh-submissions.json ../daten/regulatory/eu-pillar3-km1.json
"""
import csv
import datetime as dt
import hashlib
import io
import json
import re
import sys
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
METHOD = 'eba-p3dh-km1-v1'
TAXONOMY = 'http://www.eba.europa.eu/eu/fr/xbrl/crr/fws/pillar3/4.2/mod/codis.json'
TABLE = 'k_61.00.csv'   # EU KM1, Annotated Table Layout PILLAR3 4.2 CODIS
# Spalte T (aktueller Stichtag) laut annotierter Vorlage PILLAR3 4.2, Tabelle K_61.00.
DATAPOINTS = {'cet1_ratio': 'dp85151', 'tier1_ratio': 'dp85152', 'total_capital_ratio': 'dp85153', 'srep_total': 'dp85156',
              'srep_additional': 'dp410438', 'srep_additional_cet1': 'dp424336', 'combined_buffer': 'dp475582',
              'overall_requirement': 'dp410433', 'leverage_ratio': 'dp475724', 'lcr': 'dp143076', 'nsfr': 'dp458571'}
ROWS = {'cet1_ratio': '0050 (5)', 'tier1_ratio': '0060 (6)', 'total_capital_ratio': '0070 (7)', 'srep_additional': '0080 (EU 7d)',
        'srep_additional_cet1': '0090 (EU 7e)', 'srep_total': '0110 (EU 7g)', 'combined_buffer': '0180 (11)',
        'overall_requirement': '0190 (EU 11a)', 'leverage_ratio': '0220 (14)', 'lcr': '0320 (17)', 'nsfr': '0350 (20)'}
URL = re.compile(r'^https://errp\.eba\.europa\.eu/public-documents/(CODIS|FINDIS)/input/([A-Z0-9]{20})\.(CON|IND)_([A-Z]{2})_PILLAR3(\d+)_(CODIS|FINDIS)_(\d{4}-\d{2}-\d{2})_(\d+)\.zip$')
# EU CR1 (Modul FINDIS, Tabelle K_21.01.a), Zeile 010 "Loans and advances": Bruttobuchwert nicht notleidend (Spalte a) und notleidend (Spalte d).
FINDIS_TAXONOMY = 'http://www.eba.europa.eu/eu/fr/xbrl/crr/fws/pillar3/4.2/mod/findis.json'
CR1_TABLE, CR1_PERFORMING, CR1_NON_PERFORMING = 'k_21.01.a.csv', 'dp3528599', 'dp3528855'
MAX_AGE_DAYS = 270
CONSISTENCY = 5e-4


def candidates(urls, leis, module='CODIS'):
    """Je LEI die Einreichungen eines Moduls, juengster Stichtag zuerst; konsolidiert vor Einzelinstitut, spaetere Einreichung zuerst."""
    out = {}
    for u in urls:
        m = URL.match(u)
        if m and m.group(1) == module and m.group(6) == module and m.group(2) in leis:
            _, lei, scope, cc, ver, _, date, ts = m.groups()
            out.setdefault(lei, []).append({'url': u, 'scope': scope, 'country': cc, 'date': date, 'ts': ts})
    for lei in out:
        out[lei].sort(key=lambda c: (c['date'], c['scope'] == 'CON', c['ts']), reverse=True)
    return out


def number(v):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if x == x and abs(x) != float('inf') else None


def open_package(raw, cand, lei, taxonomy):
    """Leser fuer reports/<datei> und Parameter, nach Pruefung von Taxonomie, Institut und Stichtag; sonst (None, Grund)."""
    try:
        z = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile:
        return None, 'not_a_zip'
    names = z.namelist()
    base = names[0].split('/')[0] if names else ''
    read = lambda n: z.read(base + '/reports/' + n).decode('utf-8-sig')
    try:
        report, params = json.loads(read('report.json')), dict(list(csv.reader(io.StringIO(read('parameters.csv'))))[1:])
    except (KeyError, ValueError):
        return None, 'package_incomplete'
    if (report.get('documentInfo') or {}).get('extends') != [taxonomy]:
        return None, 'taxonomy_not_4_2'
    if params.get('entityID') != 'rs:' + lei + '.' + cand['scope'] or params.get('refPeriod') != cand['date']:
        return None, 'identity_or_period_mismatch'
    return (read, params), ''


def parse(raw, cand, lei):
    """KM1-Werte aus einer Einreichung oder (None, Grund)."""
    pkg, why = open_package(raw, cand, lei, TAXONOMY)
    if not pkg:
        return None, why
    read, params = pkg
    try:
        rows = dict(list(csv.reader(io.StringIO(read(TABLE))))[1:])
    except KeyError:
        return None, 'km1_missing'
    vals = {k: number(rows.get(dp)) for k, dp in DATAPOINTS.items()}
    chain = [vals[k] for k in ('cet1_ratio', 'tier1_ratio', 'total_capital_ratio')]
    if any(v is None or not 0 < v < 1 for v in chain) or not chain[0] <= chain[1] + 1e-6 <= chain[2] + 2e-6:
        return None, 'capital_ratios_missing_or_inconsistent'
    return {'values': vals, 'currency': params.get('baseCurrency'), 'decimalsPercentage': params.get('decimalsPercentage')}, ''


def parse_npl(raw, cand, lei):
    """NPL-Quote der Kredite und Darlehen aus EU CR1 oder (None, Grund)."""
    pkg, why = open_package(raw, cand, lei, FINDIS_TAXONOMY)
    if not pkg:
        return None, why
    read, params = pkg
    try:
        rows = dict(list(csv.reader(io.StringIO(read(CR1_TABLE))))[1:])
    except KeyError:
        return None, 'cr1_missing'
    perf, np_ = number(rows.get(CR1_PERFORMING)), number(rows.get(CR1_NON_PERFORMING))
    if perf is None or np_ is None or perf < 0 or np_ < 0 or perf + np_ <= 0:
        return None, 'cr1_loans_missing'
    return {'ratio': np_ / (perf + np_), 'performing': perf, 'nonPerforming': np_, 'currency': params.get('baseCurrency')}, ''


def requirement(v):
    """Vollstaendige CET1-Anforderung oder (None, Grund)."""
    p2r, cbr, srep, ocr = v['srep_additional_cet1'], v['combined_buffer'], v['srep_total'], v['overall_requirement']
    derived = None
    # Ohne Zeile EU 7e, aber SREP-Gesamtanforderung genau 8 % (= Saeule-1-Mindestanforderung): keine Zusatzanforderung, CET1-Anteil 0.
    if p2r is None and srep is not None and abs(srep - .08) < 1e-6:
        p2r, derived = 0.0, 'p2r_cet1_zero_because_total_srep_equals_pillar1_8pct'
    if p2r is None or cbr is None:
        return None, 'p2r_cet1_or_buffer_missing'
    # Kombinierte Puffer koennen hoch sein (Norwegen: Systemrisiko-, antizyklischer und Erhaltungspuffer ueber 10 %).
    if not (0 <= p2r < .1 and 0 <= cbr < .15):
        return None, 'requirement_out_of_range'
    if srep is None or ocr is None or abs(ocr - (srep + cbr)) > CONSISTENCY:
        return None, 'overall_requirement_inconsistent_or_rounded'
    value = .045 + p2r + cbr
    return {'value': round(value, 6), 'components': {'pillar1_cet1': .045, 'p2r_cet1': p2r, 'combined_buffer': cbr},
            'check': {'overall_requirement': ocr, 'srep_total': srep}, 'derivation': derived}, ''


def apply_unit_corrections(banks, corrections, now):
    """Gepruefte Einheitenkorrekturen (eu-bank-map.json, km1UnitCorrections): nur wenn der gemeldete Wert exakt uebereinstimmt,
    die Pruefung gilt und die korrigierte Anforderung hoechstens `tolerance` von der veroeffentlichten Anforderung der Bank abweicht.
    Sonst bleibt die Anforderung offen. Gekennzeichnet ueber derivation und unitCorrection."""
    today = now.date().isoformat()
    for c in corrections or []:
        b = banks.get(c.get('lei'))
        if not b or b.get('cet1Requirement') is not None:
            continue
        ok = (str(c.get('reviewedOn', '9999')) <= today <= str(c.get('reviewExpires', '0000')) and str(c.get('evidenceUrl', '')).startswith('https://')
              and re.fullmatch(r'[0-9a-f]{64}', str(c.get('evidenceSha256', ''))) and c.get('field') == 'srep_additional_cet1'
              and b['metrics'].get(c['field']) == c.get('reportedValue') and isinstance(c.get('correctedValue'), float)
              and abs(c['correctedValue'] * 100 - c['reportedValue']) < 1e-9 and isinstance(c.get('statedRequirement'), float))
        if not ok:
            b['cet1RequirementOpen'] = 'unit_correction_not_applicable'
            continue
        req, why = requirement({**b['metrics'], c['field']: c['correctedValue']})
        if not req or abs(req['value'] - c['statedRequirement']) > c.get('tolerance', .001):
            b['cet1RequirementOpen'] = 'unit_correction_check_failed'
            continue
        req['derivation'] = 'reviewed_unit_correction_p2r_cet1_percent'
        req['unitCorrection'] = {k: c[k] for k in ('field', 'reportedValue', 'correctedValue', 'statedRequirement', 'evidenceUrl', 'evidenceSha256', 'evidence', 'reviewedOn', 'reviewExpires')}
        b['cet1Requirement'], b['cet1RequirementOpen'] = req, None
    return banks


def build(submissions, mapping, fetch, now):
    leis = {b['lei']: b for b in mapping.get('banks', [])}
    # Banken ohne EBA-Transparenzdaten (nur Saeule 3): gleiche Pruefung, Name aus GLEIF.
    leis.update({b['lei']: {**b, 'ebaName': b.get('gleifName')} for b in mapping.get('pillar3Only', [])})
    banks, rejected = {}, {}
    for lei, cands in candidates(submissions.get('urls', []), leis).items():
        reasons = []
        for c in cands:
            age = (now.date() - dt.date.fromisoformat(c['date'])).days
            if not 0 <= age <= MAX_AGE_DAYS:
                reasons.append(c['date'] + ':too_old')
                break
            try:
                raw = fetch(c['url'])
            except (urllib.error.URLError, OSError) as e:
                reasons.append(c['date'] + ':' + str(getattr(e, 'code', 'download_failed')))
                continue
            parsed, why = parse(raw, c, lei)
            if not parsed:
                reasons.append(c['date'] + ':' + why)
                continue
            v = parsed['values']
            req, req_why = requirement(v)
            lcr = v['lcr'] if v['lcr'] is not None and 0 < v['lcr'] < 10 else None
            banks[lei] = {'name': leis[lei].get('ebaName'), 'period': c['date'], 'scope': 'consolidated' if c['scope'] == 'CON' else 'individual',
                          'sourceUrl': c['url'], 'sourceFileSha256': hashlib.sha256(raw).hexdigest(), 'baseCurrency': parsed['currency'],
                          'decimalsPercentage': parsed['decimalsPercentage'], 'metrics': v, 'lcr': lcr, 'nsfr': v['nsfr'] if v['nsfr'] is not None and 0 < v['nsfr'] < 10 else None,
                          'cet1Requirement': req, 'cet1RequirementOpen': req_why or None}
            break
        if lei not in banks:
            rejected[lei] = reasons or ['no_submission']
    findis = candidates(submissions.get('urls', []), leis, 'FINDIS')
    for lei, bank in banks.items():
        reasons = []
        for c in findis.get(lei, []):
            age = (now.date() - dt.date.fromisoformat(c['date'])).days
            if not 0 <= age <= MAX_AGE_DAYS:
                reasons.append(c['date'] + ':too_old')
                break
            try:
                raw = fetch(c['url'])
            except (urllib.error.URLError, OSError) as e:
                reasons.append(c['date'] + ':' + str(getattr(e, 'code', 'download_failed')))
                continue
            npl, why = parse_npl(raw, c, lei)
            if not npl:
                reasons.append(c['date'] + ':' + why)
                continue
            bank['npl'] = {**npl, 'period': c['date'], 'scope': 'consolidated' if c['scope'] == 'CON' else 'individual', 'sourceUrl': c['url'],
                           'sourceFileSha256': hashlib.sha256(raw).hexdigest()}
            break
        if 'npl' not in bank:
            bank['npl'], bank['nplOpen'] = None, reasons or ['no_findis_submission_listed']
    for lei in leis:
        if lei not in banks and lei not in rejected:
            rejected[lei] = ['no_codis_submission_listed']
    apply_unit_corrections(banks, mapping.get('km1UnitCorrections'), now)
    return {'schema': 1, 'method': METHOD, 'importedAt': now.isoformat(), 'mappingReviewExpires': mapping.get('review_expires'),
            'source': {'name': 'EBA Pillar 3 data hub (P3DH), Originaldateien', 'listUrl': 'https://edap-public.eba.europa.eu/Report/index/MTE1',
                       'listRetrievedAt': submissions.get('retrievedAt'), 'taxonomy': TAXONOMY, 'table': 'K_61.00 EU KM1, Spalte T', 'rows': ROWS,
                       'creditTable': 'K_21.01.a EU CR1, Zeile 010 Loans and advances, Spalten a (nicht notleidend) und d (notleidend)', 'findisTaxonomy': FINDIS_TAXONOMY},
            'banks': banks, 'rejected': rejected, 'scoreContribution': 0}


def fetch_url(url):
    time.sleep(.4)
    req = urllib.request.Request(url, headers={'User-Agent': 'value-radar'})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def main():
    submissions = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    mapping = json.loads((ROOT / 'eu-bank-map.json').read_text(encoding='utf-8'))
    result = build(submissions, mapping, fetch_url, dt.datetime.now(dt.timezone.utc))
    out = Path(sys.argv[2])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print(json.dumps({'banks': len(result['banks']), 'withRequirement': sum(1 for b in result['banks'].values() if b['cet1Requirement']),
                      'withLcr': sum(1 for b in result['banks'].values() if b['lcr'] is not None),
                      'withNpl': sum(1 for b in result['banks'].values() if b.get('npl')), 'rejected': result['rejected']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
