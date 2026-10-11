"""Conservative identity review of free-source exports; never a production admission gate."""
import argparse
from collections import Counter, defaultdict
import csv
import io
import json
from pathlib import Path
import zipfile

from free_sources import reconstruct, research_id, write_csv

EVIDENCE = Path(__file__).with_name('security_identity_evidence.json')


def load_evidence():
    return json.loads(EVIDENCE.read_text(encoding='utf8'))


def resolve(symbol, date, name, evidence):
    """Map historical events to research identities, not blindly to today's ticker."""
    for item in evidence['renames']:
        if symbol == item['old'] and date < item['effective']:
            return item['new'], item['source']
    ua = evidence['under_armour']
    if symbol == 'UA' and date < ua['ticker_change']:
        if 'class c' in name.lower():
            return 'UA', ua['source']
        if date < ua['class_c_issuance'] or 'class a' in name.lower():
            return 'UAA', ua['source']
        # Do not guess the share class from ticker/date alone in the ambiguous interval.
        return 'UA_CLASS_UNRESOLVED', ua['source']
    agn = evidence['allergan']
    if symbol == 'AGN':
        return (agn['old_identity'] if date < agn['reuse_date'] else agn['new_identity']), agn['source']
    if symbol == 'ACT' and date < agn['reuse_date']:
        return agn['new_identity'], agn['source']
    return symbol, ''


def normalize(current, events, evidence):
    corrected = []
    changes = []
    for event in events:
        rename = next((a for a in evidence['renames'] if event['date'] == a['effective']
                       and event['removed'] == a['old'] and event['added'] == a['new']), None)
        if rename:
            changes.append({'date':event['date'], 'side':'rename_only_no_membership_change',
                            'original_symbol':rename['old'], 'research_identity':rename['new'], 'source':rename['source']})
            continue
        row = dict(event)
        for side in ('added', 'removed'):
            symbol = event[side]
            identity, source = resolve(symbol, event['date'], event.get(side + '_name', ''), evidence)
            row[side] = identity
            if source:
                changes.append({'date': event['date'], 'side': side, 'original_symbol': symbol,
                                'research_identity': identity, 'source': source})
        corrected.append(row)
    return dict(current), corrected, changes


def price_status(identity, rows, intervals, download, evidence):
    if identity in {evidence['allergan']['old_identity'], evidence['allergan']['new_identity'], 'UA_CLASS_UNRESOLVED'}:
        return 'blocked_ambiguous_or_unavailable_identity', 0
    for item in evidence['blocked_quotes']:
        if identity == item['symbol']:
            return 'blocked_known_ticker_reuse', 0
    if not rows:
        return 'missing_prices', 0
    dates = [r['Datum'] for r in rows]
    overlap = sum(any(p['start'] <= d < p['end'] for p in intervals) for d in dates)
    if not overlap:
        return 'blocked_no_membership_overlap', 0
    if len(rows) < 2 or overlap < 2:
        return 'insufficient_price_rows', overlap
    return 'research_only_identity_and_returns_unverified', overlap


def audit(source, output):
    """Read archived or fresh raw output without overwriting it or extracting ZIP paths."""
    source, output = Path(source), Path(output)
    output.mkdir(parents=True, exist_ok=True)
    archive = zipfile.ZipFile(source) if source.is_file() else None
    def read(name):
        return archive.read(name).decode('utf-8-sig') if archive else (source / name).read_text(encoding='utf-8-sig')
    def read_csv(name):
        return list(csv.DictReader(io.StringIO(read(name))))
    try:
        report = json.loads(read('coverage.json'))
        master = read_csv('wertpapier_kandidaten.csv')
        events = read_csv('indexaenderungen.csv')
        evidence = load_evidence()
        current = {x['Symbol']: x for x in master if x['Heute_gelistet_im_Index'] == 'True'}
        current, corrected, changes = normalize(current, events, evidence)
        intervals, issues = reconstruct(current, corrected, report['requested_start'], report['requested_end_exclusive'])
        by_identity = defaultdict(list)
        for interval in intervals:
            by_identity[interval['symbol']].append(interval)
        names = {x['Symbol']: x['Namenshinweise'] for x in master}
        downloads = {d['Symbol']: d for d in report['downloads']}
        # Preserve all expected identities including missing and rejected instruments.
        identities = sorted(set(by_identity) | set(current) | {r[s] for r in corrected for s in ('added','removed') if r[s]})
        rows = []
        removed = defaultdict(list)
        for e in corrected:
            if e['removed']:
                removed[e['removed']].append(e)
        for identity in identities:
            d = downloads.get(identity, {})
            prices = read_csv('prices/' + research_id(identity) + '.csv') if d.get('rows') else []
            status, overlap = price_status(identity, prices, by_identity[identity], d, evidence)
            aliases = [a for a in evidence['renames'] if a['new'] == identity]
            last_exit = max(removed[identity], key=lambda e:e['date'], default={})
            reason = last_exit.get('reason', '')
            hint = ('acquisition_or_merger_hint_unverified' if any(t in reason.lower() for t in ('acquir','merg','bought','buyout'))
                    else 'other_or_unknown_exit') if last_exit else 'no_recorded_exit'
            rows.append({'identity':identity, 'name_hints':names.get(identity, ''), 'provider_name':d.get('Yahoo_Name',''),
                         'status':status, 'price_rows':len(prices), 'member_price_rows':overlap,
                         'first':d.get('first',''), 'last':d.get('last',''), 'former_symbols':';'.join(a['old'] for a in aliases),
                         'rename_sources':';'.join(a['source'] for a in aliases), 'last_index_exit':last_exit.get('date',''),
                         'exit_hint':hint, 'exit_reason':reason, 'exit_source':last_exit.get('source',''),
                         'price_file': 'prices/'+research_id(identity)+'.csv' if status.startswith('research_only') else '',
                         'production_eligible':False})
        write_csv(output/'identitaetspruefung.csv', rows, list(rows[0]))
        write_csv(output/'offene_faelle.csv', [r for r in rows if not r['status'].startswith('research_only')], list(rows[0]))
        write_csv(output/'belegte_zuordnungen.csv', changes, ['date','side','original_symbol','research_identity','source'])
        write_csv(output/'mitglieder_korrigiert_vorlaeufig.csv', intervals, ['symbol','start','end','left_censored'])
        write_csv(output/'abwicklung_nur_konditionen.csv', evidence['settlement_evidence'], list(evidence['settlement_evidence'][0]))
        (output/'security_identity_evidence.json').write_text(json.dumps(evidence,indent=2),encoding='utf8')
        summary = {'source_generated_at':report['generated_at'], 'raw_reconstruction_issues':report['reconstruction_issues'],
                   'remaining_reconstruction_issues':issues, 'applied_event_mappings':len(changes),
                   'expected_research_identities':len(rows), 'status_counts':dict(Counter(r['status'] for r in rows)),
                   'resolved_aliases_with_prices':[a['old']+' -> '+a['new'] for a in evidence['renames'] if downloads.get(a['new'],{}).get('rows')],
                   'complete_historical_universe_verified':False, 'production_eligible':False}
        (output/'identity_audit.json').write_text(json.dumps(summary,indent=2),encoding='utf8')
        (output/'README.txt').write_text('''Identitaetspruefung der kostenlosen Forschungsdaten.
Rohdaten bleiben unveraendert. Nur belegte Umbenennungen und kontextbezogene Identitaeten werden zugeordnet.
Alle 5 bisherigen Rekonstruktionswidersprueche werden erneut geprueft; null Widersprueche belegen keine vollstaendige Historie.
Keine Bereinigung durch Weglassen fehlender Aktien: offene_faelle.csv bleibt Teil des erwarteten Universums.
price_file ist nur bei einer nicht blockierten Forschungsreihe gesetzt und relativ zum Rohdatenordner.
Auch diese Reihen bleiben ungeprueft: keine dauerhafte Wertpapierkennung, keine vollstaendige Kalender- oder Kapitalmassnahmenpruefung.
member_price_rows zaehlt tatsaechliche Kurstage innerhalb vorlaeufiger Indexmitgliedschaften; es ist keine Vollstaendigkeitsquote.
Kein Kurs im Mitgliedschaftszeitraum blockiert eine Zuordnung. Dies beweist allein noch keine Tickerwiederverwendung.
Uebernahmehinweise stammen aus der Wikipedia-Begruendung und sind nicht als verifizierte Abwicklung zu verstehen.
Die zwei belegten Abwicklungskonditionen sind KEINE berechneten oder bereits enthaltenen Abwicklungsrenditen.
Keine Produktionsscores werden veraendert. Kein survivorfreier Backtest wird behauptet.
''',encoding='utf8')
        return summary
    finally:
        if archive:
            archive.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('source')
    parser.add_argument('output')
    args = parser.parse_args()
    print(json.dumps(audit(args.source,args.output),indent=2))
