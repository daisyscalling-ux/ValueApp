"""Trading-session coverage of provisional memberships, never a backtest approval."""
import argparse
from bisect import bisect_left
from collections import Counter
import csv
import datetime as dt
import io
import json
import math
from pathlib import Path
import zipfile

from free_sources import write_csv


def expected_sessions(sessions, spans):
    return sorted({d for a,b in spans for d in sessions[bisect_left(sessions,a):bisect_left(sessions,b)]})


def inspect_rows(sessions, expected, rows):
    """A return across a missing session is not a valid daily return."""
    previous_session = dict(zip(sessions[1:], sessions))
    prices, returns, duplicate = {}, {}, set()
    previous_row = None
    errors = 0
    for row in rows:
        day = row['Datum']
        if day in prices:
            duplicate.add(day)
        try:
            p = float(row['Adjusted_Close'])
            if not math.isfinite(p) or p <= 0:
                raise ValueError('invalid price')
            prices[day] = p
            value = float(row['Tagesrendite']) if row.get('Tagesrendite') else None
            if value is not None and (not math.isfinite(value) or value < -1):
                errors += 1
            elif value is not None and previous_row == previous_session.get(day) and previous_row in prices:
                if math.isclose(value, p / prices[previous_row] - 1, rel_tol=1e-7, abs_tol=1e-10):
                    returns[day] = value
                else:
                    errors += 1
        except (ValueError, TypeError):
            errors += 1
        previous_row = day
    # Ambiguous duplicate observations cannot support a price or next-day return.
    for d in duplicate:
        prices.pop(d, None)
        returns.pop(d, None)
    returns = {d:v for d,v in returns.items() if previous_session.get(d) in prices and d in prices}
    missing = [d for d in expected if d not in prices]
    required_returns = [d for d in expected if d in previous_session]
    missing_returns = [d for d in required_returns if d not in returns]
    return {'expected_price_sessions':len(expected), 'observed_price_sessions':len(expected)-len(missing),
            'missing_price_sessions':len(missing), 'expected_return_sessions':len(required_returns),
            'valid_return_sessions':len(required_returns)-len(missing_returns),
            'missing_or_invalid_return_sessions':len(missing_returns), 'duplicate_dates':len(duplicate),
            'numeric_errors':errors}, missing, missing_returns


def gap_ranges(expected, missing):
    missing = set(missing)
    ranges = []
    active = None
    for day in expected:
        if day in missing:
            if active is None:
                active = {'first':day, 'last':day, 'sessions':0}
            active['last'] = day
            active['sessions'] += 1
        elif active:
            ranges.append(active)
            active = None
    if active:
        ranges.append(active)
    return ranges


def run(source, output):
    import exchange_calendars as xcals
    source, output = Path(source), Path(output)
    output.mkdir(parents=True, exist_ok=True)
    archive = zipfile.ZipFile(source) if source.is_file() else None
    def read(name):
        return archive.read(name).decode('utf-8-sig') if archive else (source/name).read_text(encoding='utf-8-sig')
    def table(name):
        return list(csv.DictReader(io.StringIO(read(name))))
    try:
        raw = json.loads(read('coverage.json'))
        start, end = raw['requested_start'], raw['requested_end_exclusive']
        last_day = (dt.date.fromisoformat(end)-dt.timedelta(days=1)).isoformat()
        calendar = xcals.get_calendar('XNYS', start=start, end=last_day)
        sessions = [d.date().isoformat() for d in calendar.sessions if start <= d.date().isoformat() < end]
        if not sessions:
            raise ValueError('Empty reference calendar')
        identities = table('identity-review/identitaetspruefung.csv')
        members = table('identity-review/mitglieder_korrigiert_vorlaeufig.csv')
        summaries, gaps = [], []
        for identity in identities:
            sid = identity['identity']
            spans = [(r['start'],r['end']) for r in members if r['symbol']==sid]
            expected = expected_sessions(sessions, spans)
            # Rejected raw Yahoo series never improve the coverage numerator.
            prices = table(identity['price_file']) if identity['price_file'] else []
            result, missing, missing_returns = inspect_rows(sessions,expected,prices)
            complete = bool(expected) and not missing and not missing_returns and not result['duplicate_dates'] and not result['numeric_errors']
            status = 'calendar_complete_research_only' if complete else ('no_expected_sessions' if not expected else 'incomplete')
            summaries.append(dict(identity=sid, identity_status=identity['status'], calendar_status=status,
                                  listing_boundary=identity.get('listing_boundary',''),
                                  listing_boundary_source=identity.get('listing_boundary_source',''),
                                  **result, production_eligible=False))
            for kind, days in [('price',missing),('daily_return',missing_returns)]:
                for span in spans:
                    window=expected_sessions(sessions,[span])
                    for g in gap_ranges(window,days):
                        boundary = identity.get('listing_boundary','')
                        note = ('listing_boundary_return_unverified' if kind=='daily_return' and
                                g['first']==boundary else 'missing_observation')
                        gaps.append(dict(identity=sid,kind=kind,**g,review_reason=note))
        write_csv(output/'handelskalender.csv', [{'date':d} for d in sessions], ['date'])
        write_csv(output/'abdeckung_je_wertpapier.csv',summaries,list(summaries[0]))
        write_csv(output/'luecken_zeitraeume.csv',gaps,['identity','kind','first','last','sessions','review_reason'])
        totals={k:sum(r[k] for r in summaries) for k in ('expected_price_sessions','observed_price_sessions','missing_price_sessions','expected_return_sessions','valid_return_sessions','missing_or_invalid_return_sessions')}
        report={'calendar':'XNYS','calendar_library':'exchange_calendars','calendar_version':xcals.__version__,
                'start_inclusive':start,'end_exclusive':end,'calendar_sessions':len(sessions),
                'source_generated_at':raw['generated_at'],'identity_count':len(summaries),
                'status_counts':dict(Counter(r['calendar_status'] for r in summaries)),**totals,
                'complete_historical_universe_verified':False,'production_eligible':False,
                'scope':'Reference-calendar coverage during provisional membership only; no terminal-return validation or post-exit holding windows.'}
        (output/'session_coverage.json').write_text(json.dumps(report,indent=2),encoding='utf8')
        (output/'README.txt').write_text('''Handelstagepruefung fuer historische Forschungsdaten.
Referenzkalender: XNYS aus exchange_calendars (Version im Bericht), US-Aktienmarkt.
Keine unabhaengige Bestaetigung aller boersenspezifischen Sonderfaelle oder Handelsaussetzungen.
Erwartete Tage: rekonstruierte Mitgliedschaft, Eintritt inklusive / Austritt exklusive.
Fehlende und gesperrte Unternehmen bleiben im Nenner. Gesperrte Yahoo-Reihen zaehlen nicht als Abdeckung.
Eine Tagesrendite braucht den unmittelbar vorherigen Kalender-Handelstag und passende bereinigte Kurse.
Eine Renditebruecke ueber einen fehlenden Handelstag wird verworfen, auch bei weniger als sieben Kalendertagen.
Feiertage und Wochenenden erzeugen keine Luecken. Luecken werden NICHT mit Nullen aufgefuellt.
calendar_complete_research_only bestaetigt nur diese Kalender- und Zahlenpruefung.
Wertpapieridentitaet, Kapitalmassnahmen und Abwicklungsrenditen bleiben gesondert zu pruefen.
Perioden nach Indexausschluss fuer 1/3/6-Monats-Haltefenster werden hier noch nicht bewertet.
Kein kalibrierter Riskscore und keine Produktionsfreigabe.
''',encoding='utf8')
        return report
    finally:
        if archive:
            archive.close()


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('source');parser.add_argument('output')
    args=parser.parse_args()
    print(json.dumps(run(args.source,args.output),indent=2))

