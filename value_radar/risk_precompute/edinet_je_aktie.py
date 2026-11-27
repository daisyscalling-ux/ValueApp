"""Kennzahlen je Aktie aus der Fünfjahresübersicht japanischer Jahresberichte (EDINET, seit 27.11.2026, Entscheidung des Nutzers).

Jeder Jahresbericht (有価証券報告書) enthält unter 主要な経営指標等の推移 fünf Geschäftsjahre: Gewinn je Aktie, Gewinn,
Buchwert je Aktie, KGV und Dividende je Aktie, so wie das Unternehmen sie berichtet hat. Gelesen werden je Titel zwei Berichte:
der neueste (aus dem Index von edinet_supply) und der von vor ALT_JAHRE Jahren. Zusammen ergibt das bis zu neun Jahre.

Dieses Modul speichert nur berichtete Werte mit Herkunft (docID, Prüfsumme der Datei, Taxonomie, Standard). Umrechnung auf die
heutige Aktienbasis und Abgleich mit Yahoo macht export_fundamentals.py (edinet_jahre_je_aktie), weil dort die Kurse liegen.

Regeln:
- Elementnamen geprüft gegen die FSA-Taxonomie 2025-11-01 (1c_Taxonomy.zip, sha256 8d57f848...5de2). Achtung: der Buchwert
  je Aktie nach IFRS heißt dort EquityToAssetRatioIFRSSummaryOfBusinessResults (Typ je Aktie, Bezeichnung
  １株当たり親会社所有者帰属持分), nicht ...Ratio im Wortsinn.
- Konzernwerte aus Kontexten ohne Dimension; Dividende je Aktie und Aktienzahl aus dem Einzelabschluss
  (ConsolidatedOrNonConsolidatedAxis = NonConsolidatedMember), sonst aus dem Konzern. Andere Dimensionen werden übergangen.
- Jahre über die Periodendaten (330–400 Tage), nicht über Kontextnamen. Widersprüchliche Werte: Feld offen und gemeldet.
- Älterer Bericht: nur Original (120) mit derselben EDINET-Nummer und einem Stichtag ALT_JAHRE Jahre vor dem neuesten (±40 Tage).
  Gibt es dazu eine Korrektur (130), bleibt der Bericht offen (keine Auswahl unter Korrekturen). Nur innerhalb der gesetzlichen
  Einsichtsfrist von 5 Jahren abrufbar.
"""
import datetime as dt
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

from edinet_supply import sec_code, select_doc, published, safe_error
from roic_risk_annual import identity
from yahoo_sector import load, save

UTC = dt.timezone.utc
X = 'http://www.xbrl.org/2003/instance'
D = 'http://xbrl.org/2006/xbrldi'
METHOD = 'edinet_summary_per_share_v1'
PARSER = 'edinet-summary-v1'
TAXONOMIE = 'FSA EDINET-Taxonomie 2025-11-01 (1c_Taxonomy.zip, sha256 8d57f84802b20a8dc6a517ad6d4768270c294aa6991621d66cb5adb562df5de2)'
ALT_JAHRE = 4
FENSTER_TAGE = 10
EINSICHT_TAGE = 5 * 365 - 30
JE_AKTIE_ELEMENTE = {
    'jgaap': {'eps_diluted': 'DilutedEarningsPerShareSummaryOfBusinessResults', 'eps_basic': 'BasicEarningsLossPerShareSummaryOfBusinessResults',
              'net_income': 'ProfitLossAttributableToOwnersOfParentSummaryOfBusinessResults', 'bvps': 'NetAssetsPerShareSummaryOfBusinessResults',
              'per': 'PriceEarningsRatioSummaryOfBusinessResults'},
    'ifrs': {'eps_diluted': 'DilutedEarningsLossPerShareIFRSSummaryOfBusinessResults', 'eps_basic': 'BasicEarningsLossPerShareIFRSSummaryOfBusinessResults',
             'net_income': 'ProfitLossAttributableToOwnersOfParentIFRSSummaryOfBusinessResults', 'bvps': 'EquityToAssetRatioIFRSSummaryOfBusinessResults',
             'per': 'PriceEarningsRatioIFRSSummaryOfBusinessResults'},
    'usgaap': {'eps_diluted': 'DilutedEarningsLossPerShareUSGAAPSummaryOfBusinessResults', 'eps_basic': 'BasicEarningsLossPerShareUSGAAPSummaryOfBusinessResults',
               'net_income': 'NetIncomeLossAttributableToOwnersOfParentUSGAAPSummaryOfBusinessResults', 'bvps': 'EquityAttributableToOwnersOfParentPerShareUSGAAPSummaryOfBusinessResults',
               'per': 'PriceEarningsRatioUSGAAPSummaryOfBusinessResults'},
}
EINZEL_ELEMENTE = {'dps': 'DividendPaidPerShareSummaryOfBusinessResults', 'shares_issued': 'TotalNumberOfIssuedSharesSummaryOfBusinessResults'}
EINHEIT = {'eps_diluted': 'je_aktie', 'eps_basic': 'je_aktie', 'bvps': 'je_aktie', 'dps': 'je_aktie', 'net_income': 'JPY', 'per': 'pure', 'shares_issued': 'shares'}


def _lokal(tag):
    return tag.split('}')[-1].split(':')[-1]


def parse_summary(raw, doc):
    """XBRL-Instanz -> {'standard', 'jahre': [...], 'konflikte': [...]}; ValueError mit festem Code bei Unsicherheit."""
    if len(raw) > 30_000_000 or b'\x00' in raw or b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():
        raise ValueError('unsafe_xml')
    try:
        raw.decode('utf-8-sig')
    except UnicodeError:
        raise ValueError('unsafe_xml')
    ns = {}
    for _, (prefix, uri) in ET.iterparse(io.BytesIO(raw), events=['start-ns']):
        if prefix in ns and ns[prefix] != uri:
            raise ValueError('conflicting_namespace')
        ns[prefix] = uri
    root = ET.fromstring(raw)
    if root.tag != '{' + X + '}xbrl':
        raise ValueError('not_xbrl_instance')
    dei = {}
    for e in root:
        if not re.fullmatch(r'\{http://disclosure\.edinet-fsa\.go\.jp/taxonomy/jpdei/\d{4}-\d{2}-\d{2}/jpdei_cor\}.+', e.tag):
            continue
        k = e.tag.split('}')[-1]
        if k in dei and dei[k] != e.text:
            raise ValueError('issuer_unconfirmed')
        dei[k] = e.text
    if dei.get('EDINETCodeDEI') != doc['edinetCode']:
        raise ValueError('issuer_unconfirmed')
    if dei.get('WhetherConsolidatedFinancialStatementsArePreparedDEI') not in ('true', '1'):
        raise ValueError('consolidation_unconfirmed')
    ende_doc = dt.date.fromisoformat(doc['periodEnd'])
    kontexte, ids = {}, set()
    for c in root.findall('{' + X + '}context'):
        cid = c.get('id')
        if not cid or cid in ids:
            raise ValueError('duplicate_context')
        ids.add(cid)
        ident = c.find('{' + X + '}entity/{' + X + '}identifier')
        if ident is None or ident.get('scheme') != 'http://disclosure.edinet-fsa.go.jp' or (ident.text or '').split('-')[0] != doc['edinetCode']:
            continue
        if c.find('.//{' + D + '}typedMember') is not None:
            continue
        dims = c.findall('.//{' + D + '}explicitMember')
        if not dims:
            umfang = 'konzern'
        elif len(dims) == 1 and _lokal(dims[0].get('dimension', '')) == 'ConsolidatedOrNonConsolidatedAxis' and _lokal(dims[0].text or '') == 'NonConsolidatedMember':
            umfang = 'einzel'
        else:
            continue
        p = c.find('{' + X + '}period')
        if p is None:
            continue
        try:
            if p.findtext('{' + X + '}instant'):
                ende, dauer = dt.date.fromisoformat(p.findtext('{' + X + '}instant')), None
            else:
                start, ende = dt.date.fromisoformat(p.findtext('{' + X + '}startDate')), dt.date.fromisoformat(p.findtext('{' + X + '}endDate'))
                dauer = (ende - start).days
                if not 330 <= dauer <= 400:
                    continue
        except (TypeError, ValueError):
            continue
        if ende > ende_doc or (ende_doc - ende).days > 5 * 366 + 10:
            continue
        kontexte[cid] = (umfang, ende, dauer is not None)
    einheiten = {}
    for u in root.findall('{' + X + '}unit'):
        uid = u.get('id')
        if not uid or uid in einheiten:
            raise ValueError('duplicate_unit')
        m = [_m.text or '' for _m in u.findall('{' + X + '}measure')]
        zaehler = [x.text or '' for x in u.findall('{' + X + '}divide/{' + X + '}unitNumerator/{' + X + '}measure')]
        nenner = [x.text or '' for x in u.findall('{' + X + '}divide/{' + X + '}unitDenominator/{' + X + '}measure')]

        def ist(text, uri, lokal):
            p = text.split(':')
            return len(p) == 2 and p[1] == lokal and ns.get(p[0]) == uri
        if len(m) == 1 and ist(m[0], 'http://www.xbrl.org/2003/iso4217', 'JPY'):
            einheiten[uid] = 'JPY'
        elif len(m) == 1 and ist(m[0], X, 'shares'):
            einheiten[uid] = 'shares'
        elif len(m) == 1 and ist(m[0], X, 'pure'):
            einheiten[uid] = 'pure'
        elif len(zaehler) == 1 and len(nenner) == 1 and ist(zaehler[0], 'http://www.xbrl.org/2003/iso4217', 'JPY') and ist(nenner[0], X, 'shares'):
            einheiten[uid] = 'je_aktie'
    werte = {}
    for e in root:
        mt = re.fullmatch(r'\{http://disclosure\.edinet-fsa\.go\.jp/taxonomy/jpcrp/\d{4}-\d{2}-\d{2}/jpcrp_cor\}(.+SummaryOfBusinessResults)', e.tag)
        if not mt or e.get('contextRef') not in kontexte or e.get('{http://www.w3.org/2001/XMLSchema-instance}nil') in ('true', '1'):
            continue
        try:
            v = float(e.text)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(v):
            continue
        umfang, ende, dauer = kontexte[e.get('contextRef')]
        werte.setdefault((mt[1], umfang, ende, dauer, einheiten.get(e.get('unitRef'))), set()).add(v)
    # Standard je Geschäftsjahr, nur aus Konzernwerten (seit 27.11.2026, Korrektur nach dem ersten Lauf: 45 von 89 Titeln
    # verworfen). IFRS- und US-GAAP-Konzerne berichten den Einzelabschluss der Muttergesellschaft nach J-GAAP; nach einer
    # Umstellung stehen ältere Jahre der Übersicht noch nach J-GAAP. Zwei Standards im Konzern für dasselbe Jahr: Jahr offen.
    def standards_im_jahr(ende):
        return [s for s, el in JE_AKTIE_ELEMENTE.items()
                if any(k[0] in (el['net_income'], el['eps_basic']) and k[1] == 'konzern' and k[2] == ende and k[3] for k in werte)]
    enden = sorted({k[2] for k in werte if k[1] == 'konzern' and k[3]
                    and any(k[0] in (el['net_income'], el['eps_basic']) for el in JE_AKTIE_ELEMENTE.values())})
    if ende_doc not in enden:
        raise ValueError('invalid_annual_period')
    if len(standards_im_jahr(ende_doc)) != 1:
        raise ValueError('ambiguous_or_unsupported_taxonomy')
    standard = standards_im_jahr(ende_doc)[0]
    dauer_felder = {'eps_diluted', 'eps_basic', 'net_income', 'per', 'dps'}
    jahre, konflikte = [], []
    for ende in enden:
        st = standards_im_jahr(ende)
        if len(st) != 1:
            konflikte.append(f'standard:{ende}')
            continue
        elemente = {**JE_AKTIE_ELEMENTE[st[0]], **EINZEL_ELEMENTE}
        felder = {}
        for feld, el in elemente.items():
            umfaenge = ('einzel', 'konzern') if feld in EINZEL_ELEMENTE else ('konzern',)
            wert = None
            for umfang in umfaenge:
                s = werte.get((el, umfang, ende, feld in dauer_felder, EINHEIT[feld]))
                if s and len(s) > 1:
                    konflikte.append(f'{feld}:{ende}')
                    break
                if s:
                    wert = next(iter(s))
                    break
            felder[feld] = wert
        jahre.append({'end': ende.isoformat(), 'standard': st[0], 'fields': felder})
    return {'standard': standard, 'jahre': jahre, 'konflikte': konflikte}


def parse_zip(raw, doc):
    if len(raw) > 30_000_000:
        raise ValueError('archive_too_large')
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        namen = [x for x in archive.infolist() if '/PublicDoc/' in '/' + x.filename and x.filename.endswith('.xbrl')]
        if len(namen) != 1:
            raise ValueError('ambiguous_public_instance')
        e = namen[0]
        if e.file_size > 30_000_000 or e.file_size > max(e.compress_size, 1) * 300:
            raise ValueError('archive_too_large')
        inhalt = archive.read(e)
    out = parse_summary(inhalt, doc)
    out['fileSha256'] = hashlib.sha256(raw).hexdigest()
    return out


def alt_ziel(neu):
    """Gesuchter älterer Bericht: Stichtag und Einreichungstag ALT_JAHRE Jahre vor dem neuesten."""
    ende = dt.date.fromisoformat(neu['periodEnd'])
    tag = published(neu).date()
    versatz = dt.timedelta(days=round(ALT_JAHRE * 365.25))
    return ende - versatz, tag - versatz


def select_alt(docs, neu, code, now):
    """Original-Jahresbericht ALT_JAHRE Jahre vor dem neuesten; None oder ValueError mit Grund."""
    ziel_ende, _ = alt_ziel(neu)
    kandidaten = []
    for d in docs:
        try:
            ende = dt.date.fromisoformat(d['periodEnd'])
        except (KeyError, TypeError, ValueError):
            continue
        if (d.get('docTypeCode') == '120' and d.get('secCode') == code and d.get('edinetCode') == neu['edinetCode']
                and abs((ende - ziel_ende).days) <= 40 and d.get('xbrlFlag') == '1' and not d.get('fundCode')
                and d.get('withdrawalStatus') == '0' and d.get('disclosureStatus') == '0' and d.get('docInfoEditStatus') == '0'
                and re.fullmatch(r'S[0-9A-Z]{7}', str(d.get('docID', ''))) and published(d) is not None and published(d) <= now):
            kandidaten.append(d)
    ids = {d['docID'] for d in kandidaten}
    if len(ids) > 1:
        raise ValueError('ambiguous_filer')
    if not kandidaten:
        return None
    alt = kandidaten[0]
    if any(d.get('docTypeCode') == '130' and d.get('parentDocID') == alt['docID'] for d in docs):
        raise ValueError('korrektur_vorhanden')
    if (now - published(alt)).days > EINSICHT_TAGE:
        raise ValueError('ausserhalb_einsichtsfrist')
    return alt


def run(universe, index_state, state, get_day, get_zip, now=None, budget=900, checkpoint=None):
    now = now or dt.datetime.now(UTC)
    gestartet = time.monotonic()
    if state.get('schema') != 1 or state.get('method') != METHOD:
        state = {'schema': 1, 'method': METHOD, 'days': {}, 'stocks': {}, 'attempts': {}}
    state['taxonomie'] = TAXONOMIE
    report = {'titel': 0, 'neu_gelesen': 0, 'unveraendert': 0, 'tage_geladen': 0, 'fehler': {}}
    index_docs = [d for v in index_state.get('days', {}).values() for d in v.get('documents', [])]
    rows = {}
    for r in universe.get('kandidaten', []):
        if sec_code(r):
            rows[r['listing_symbol']] = r
    for s in list(state['stocks']):
        if s not in rows or state['stocks'][s].get('inputIdentity') != identity(rows[s]):
            del state['stocks'][s]

    def persist():
        state.update(generatedAt=now.isoformat(), report=report)
        if checkpoint:
            checkpoint(state)

    def fehler(code):
        report['fehler'][code] = report['fehler'].get(code, 0) + 1
        return code in ('http_401', 'http_403', 'http_429', 'budget_exhausted')

    def tag_laden(datum):
        data = get_day(datum)
        status = str(data.get('metadata', {}).get('status')) if isinstance(data, dict) else ''
        if status in ('401', '403', '429'):
            raise ValueError('http_' + status)
        if status != '200' or not isinstance(data.get('results'), list):
            raise ValueError('invalid_index')
        state['days'][datum] = {'checkedAt': now.isoformat(), 'documents': [{**d, 'indexDate': datum} for d in data['results']
                                                                            if d.get('docTypeCode') in ('120', '130') and (d.get('secCode') or d.get('parentDocID'))]}
        report['tage_geladen'] += 1
    reihenfolge = sorted(rows, key=lambda s: state['attempts'].get(s, {}).get('at', ''))
    for s in reihenfolge:
        if time.monotonic() - gestartet >= budget:
            report['budget_erreicht'] = True
            break
        row, code = rows[s], sec_code(rows[s])
        report['titel'] += 1
        versuch = {'at': now.isoformat(), 'parser': PARSER, 'inputIdentity': identity(row)}
        try:
            neu = select_doc(index_docs, code, now)
            if not neu:
                raise ValueError('annual_filing_not_found')
            alt_eintrag = state['stocks'].get(s, {})
            if alt_eintrag.get('neu', {}).get('docID') == neu['docID'] and alt_eintrag.get('parser') == PARSER and alt_eintrag.get('alt_status'):
                report['unveraendert'] += 1
                continue
            _, ziel_tag = alt_ziel(neu)
            for i in range(-FENSTER_TAGE, FENSTER_TAGE + 1):
                datum = str(ziel_tag + dt.timedelta(days=i))
                if datum not in state['days']:
                    tag_laden(datum)
            alt_docs = [d for v in state['days'].values() for d in v['documents']]
            berichte, alt_status = [], 'ok'
            neu_werte = parse_zip(get_zip(neu['docID']), neu)
            berichte.append({'docID': neu['docID'], 'edinetCode': neu['edinetCode'], 'periodEnd': neu['periodEnd'], 'submitDateTime': neu['submitDateTime'], **neu_werte})
            try:
                alt = select_alt(alt_docs, neu, code, now)
                if alt:
                    alt_werte = parse_zip(get_zip(alt['docID']), alt)
                    berichte.append({'docID': alt['docID'], 'edinetCode': alt['edinetCode'], 'periodEnd': alt['periodEnd'], 'submitDateTime': alt['submitDateTime'], **alt_werte})
                else:
                    alt_status = 'alter_bericht_nicht_gefunden'
            except ValueError as e:
                alt_status = str(e) if str(e) in ('korrektur_vorhanden', 'ausserhalb_einsichtsfrist', 'ambiguous_filer') else safe_error(e)
                if alt_status in ('http_401', 'http_403', 'http_429', 'budget_exhausted'):
                    raise
            state['stocks'][s] = {'inputIdentity': identity(row), 'retrievedAt': now.isoformat(), 'parser': PARSER, 'neu': {'docID': neu['docID']},
                                  'alt_status': alt_status, 'berichte': berichte, 'source_url': 'https://disclosure2.edinet-fsa.go.jp/'}
            report['neu_gelesen'] += 1
        except ValueError as e:
            versuch['error'] = str(e) if str(e) in ('annual_filing_not_found', 'korrektur_vorhanden') else safe_error(e)
            if versuch['error'] in ('unsafe_xml', 'issuer_unconfirmed', 'consolidation_unconfirmed', 'ambiguous_or_unsupported_taxonomy', 'invalid_annual_period', 'ambiguous_filer', 'ambiguous_revision'):
                state['stocks'].pop(s, None)
            if fehler(versuch['error']):
                state['attempts'][s] = versuch
                report['gestoppt'] = versuch['error']
                persist()
                return state
        except Exception as e:
            versuch['error'] = safe_error(e)
            fehler(versuch['error'])
        state['attempts'][s] = versuch
        persist()
    report['mit_werten'] = len(state['stocks'])
    persist()
    return state


def main():
    ordner = Path(os.getenv('RISK_DATA_DIR', str(Path(__file__).resolve().parents[1] / 'daten')))
    ziel = ordner / 'cf_edinet_je_aktie.json'
    state = load(ziel, {})
    key = os.getenv('EDINET_API_KEY')
    if not key:
        state.update(schema=1, method=METHOD, report={'gestoppt': 'edinet_key_missing'})
        save(ziel, state)
        print(json.dumps(state['report']))
        return
    budget = float(os.getenv('EDINET_JE_AKTIE_BUDGET_S', '900'))
    start, letzte = time.monotonic(), [0.0]

    def anfrage(pfad, params, grenze):
        if time.monotonic() - start > budget + 60:
            raise ValueError('budget_exhausted')
        time.sleep(max(0, 2 - (time.monotonic() - letzte[0])))
        letzte[0] = time.monotonic()
        url = 'https://api.edinet-fsa.go.jp/api/v2/' + pfad + '?' + urllib.parse.urlencode({**params, 'Subscription-Key': key})
        with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'ValueApp financial research'}), timeout=20) as r:
            roh = r.read(grenze + 1)
        if len(roh) > grenze:
            raise ValueError('response_too_large')
        if roh.lstrip().startswith(b'{'):
            try:
                status = str(json.loads(roh).get('metadata', {}).get('status'))
            except (ValueError, AttributeError):
                status = ''
            if status in ('401', '403', '429'):
                raise ValueError('http_' + status)
        return roh
    state = run(load(ordner / 'cf_universum.json', {}), load(ordner / 'cf_edinet_cashflow.json', {}), state,
                lambda d: json.loads(anfrage('documents.json', {'date': d, 'type': 2}, 5_000_000)),
                lambda doc: anfrage('documents/' + doc, {'type': 1}, 30_000_000), budget=budget, checkpoint=lambda s: save(ziel, s))
    save(ziel, state)
    print(json.dumps(state['report'], ensure_ascii=False))


if __name__ == '__main__':
    main()
