"""Rendite 10-jaehriger Staatsanleihen je Waehrung aus amtlichen Quellen (seit 17.11.2026, Entscheidung des Nutzers).

Grundlage fuer den risikolosen Zins der Kapitalkosten (valuation.ts riskFree). Je Waehrung eine amtliche Tagesquelle;
gespeichert werden Wert (Anteil, 0.0512 = 5,12 %), Stichtag, Quelle, Quell-URL, sha256 der Antwort und Abrufzeit.
Fehlt eine Quelle oder ist sie veraltet, steht die Waehrung mit Grund unter `issues`; nichts wird geschaetzt.
CHF, DKK und PLN haben keine aktuelle amtliche Tagesreihe (SNB-Reihe endet 31.07.2025; DK/PL nur monatlich bei der EZB).
"""
import csv, datetime as dt, hashlib, io, json, os, urllib.request
from pathlib import Path

METHOD = 'gov_10y_v1'
MAX_AGE_DAYS = 7
UA = 'ValueRadar-Rates/1.0 (public statistics reader)'
OUT = Path(os.environ.get('RATES_OUTPUT', 'value_radar/daten/cf_rates.json'))


def fetch(url, timeout=25):
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': '*/*'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(2_000_001)


def num(x):
    try:
        v = float(str(x).strip())
    except (TypeError, ValueError):
        return None
    return v if -5 < v < 30 else None


def parse_usd(raw):
    """U.S. Treasury daily par yield curve (CSV, neueste Zeile zuerst), Spalte '10 Yr', Datum MM/DD/YYYY."""
    rows = list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))))
    for r in rows:
        v = num(r.get('10 Yr'))
        if v is not None:
            return dt.datetime.strptime(r['Date'], '%m/%d/%Y').date(), v
    return None


def parse_ecb(raw):
    """EZB Data API csvdata: TIME_PERIOD (YYYY-MM-DD), OBS_VALUE; juengste Beobachtung."""
    rows = [r for r in csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))) if num(r.get('OBS_VALUE')) is not None]
    if not rows:
        return None
    r = max(rows, key=lambda x: x['TIME_PERIOD'])
    return dt.date.fromisoformat(r['TIME_PERIOD']), num(r['OBS_VALUE'])


def parse_jpy(raw):
    """Japanisches Finanzministerium jgbcme.csv (laufender Monat): Kopfzeile mit Date,...,10Y; Datum YYYY/M/D."""
    lines = raw.decode('utf-8', 'replace').splitlines()
    head = next((i for i, l in enumerate(lines) if l.startswith('Date,')), None)
    if head is None:
        return None
    rows = list(csv.DictReader(lines[head:]))
    best = None
    for r in rows:
        v = num(r.get('10Y'))
        try:
            d = dt.datetime.strptime((r.get('Date') or '').strip(), '%Y/%m/%d').date()
        except ValueError:
            continue
        if v is not None and (best is None or d > best[0]):
            best = (d, v)
    return best


def parse_gbp(raw):
    """Bank of England IADB CSV, Serie IUDMNZC (10 Jahre nominal, Nullkupon): DATE (DD Mon YYYY), Wert."""
    rows = list(csv.reader(io.StringIO(raw.decode('utf-8-sig'))))
    best = None
    for r in rows[1:]:
        if len(r) < 2:
            continue
        try:
            d = dt.datetime.strptime(r[0].strip(), '%d %b %Y').date()
        except ValueError:
            continue
        v = num(r[1])
        if v is not None and (best is None or d > best[0]):
            best = (d, v)
    return best


def parse_sek(raw):
    """Riksbank SWEA API Latest: {"date": "YYYY-MM-DD", "value": 3.11}."""
    d = json.loads(raw.decode('utf-8'))
    v = num(d.get('value'))
    return (dt.date.fromisoformat(d['date']), v) if v is not None and d.get('date') else None


def parse_nok(raw):
    """Norges Bank SDMX CSV (Semikolon): TIME_PERIOD, OBS_VALUE."""
    rows = [r for r in csv.DictReader(io.StringIO(raw.decode('utf-8-sig')), delimiter=';') if num(r.get('OBS_VALUE')) is not None]
    if not rows:
        return None
    r = max(rows, key=lambda x: x['TIME_PERIOD'])
    return dt.date.fromisoformat(r['TIME_PERIOD']), num(r['OBS_VALUE'])


def sources(today):
    y = today.year
    gb_from = (today - dt.timedelta(days=20)).strftime('%d/%b/%Y')
    return {
        'USD': ('U.S. Treasury, Daily Treasury Par Yield Curve, 10 Yr',
                f'https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/{y}/all?type=daily_treasury_yield_curve&field_tdr_date_value={y}', parse_usd),
        'EUR': ('EZB, Zinsstrukturkurve Euroraum AAA, 10 Jahre (YC)',
                'https://data-api.ecb.europa.eu/service/data/YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y?lastNObservations=3&format=csvdata', parse_ecb),
        'JPY': ('Japanisches Finanzministerium, JGB Interest Rate, 10Y',
                'https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/jgbcme.csv', parse_jpy),
        'GBP': ('Bank of England, IUDMNZC (10 Jahre nominal, Nullkupon)',
                f'https://www.bankofengland.co.uk/boeapps/database/_iadb-fromshowcolumns.asp?csv.x=yes&Datefrom={gb_from}&Dateto=now&SeriesCodes=IUDMNZC&CSVF=TN&UsingCodes=Y', parse_gbp),
        'SEK': ('Sveriges Riksbank, SEGVB10YC (Staatsanleihe 10 Jahre)',
                'https://api.riksbank.se/swea/v1/Observations/Latest/SEGVB10YC', parse_sek),
        'NOK': ('Norges Bank, GOVT_GENERIC_RATES 10Y (Staatsanleihe)',
                'https://data.norges-bank.no/api/data/GOVT_GENERIC_RATES/B.10Y.GBON?format=csv&lastNObservations=3&locale=en', parse_nok),
    }


NO_SOURCE = {
    'CHF': 'Keine aktuelle amtliche Tagesreihe (SNB rendoblid endet am 31.07.2025)',
    'DKK': 'Keine amtliche Tagesreihe (EZB nur Monatswerte)',
    'PLN': 'Keine amtliche Tagesreihe (EZB nur Monatswerte)',
}


def collect(now=None, fetcher=fetch):
    now = now or dt.datetime.now(dt.timezone.utc)
    rates, issues = {}, dict(NO_SOURCE)
    for cur, (name, url, parser) in sources(now.date()).items():
        try:
            raw = fetcher(url)
            got = parser(raw)
        except Exception as exc:  # nur Typ/Status, nie Antworttext
            issues[cur] = 'Abruf fehlgeschlagen: ' + (('HTTP ' + str(exc.code)) if hasattr(exc, 'code') else type(exc).__name__)
            continue
        if not got:
            issues[cur] = 'Antwort ohne gueltigen 10-Jahres-Wert'
            continue
        d, v = got
        age = (now.date() - d).days
        if age < 0 or age > MAX_AGE_DAYS:
            issues[cur] = f'Juengster Wert vom {d.isoformat()} ausserhalb von {MAX_AGE_DAYS} Tagen'
            continue
        rates[cur] = {'value': round(v / 100, 6), 'as_of': d.isoformat(), 'source': name, 'source_url': url,
                      'sha256': hashlib.sha256(raw).hexdigest(), 'retrieved_at': now.isoformat()}
    return {'schema': 1, 'method': METHOD, 'generated_at': now.isoformat(), 'max_age_days': MAX_AGE_DAYS,
            'rates': rates, 'issues': issues}


def main():
    doc = collect()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
    for cur, r in sorted(doc['rates'].items()):
        print(f"{cur} {r['value']*100:.3f} % Stand {r['as_of']}")
    for cur, why in sorted(doc['issues'].items()):
        print(f'{cur} offen: {why}')
    if not doc['rates']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
