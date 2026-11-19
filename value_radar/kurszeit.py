"""Kurszeitpunkt je Titel: Schlusskurs oder Kurs aus dem laufenden Handel (seit 19.11.2026).

Der Export holte den Kurs bisher ohne Zeitangabe. Ein Lauf waehrend der US-Handelszeit lieferte so Handelskurse, ein
Lauf davor den Schluss des Vortags, und die App konnte beides nicht unterscheiden. Jede Kursquelle gibt jetzt ihren
Zeitstempel mit (yfinance regularMarketTime, Finnhub t, Tiingo/ROIC Datum des Tagesbalkens), dazu der Abrufzeitpunkt.

Regel (METHODE): Ein Kurs gilt als Schlusskurs seines Handelstags, wenn er nach Boersenschluss plus NACHLAUF abgerufen
wurde oder von einem frueheren Kalendertag (Ortszeit der Boerse) stammt als der Abruf. Sonst ist er ein Handelskurs.
Ohne Zeitangabe oder bei unbekannter Boerse bleibt die Art offen ("unbekannt"). Feiertage sind nicht hinterlegt: An einem
Feiertag gilt ein Kurs vom Vortag als Schluss des Vortags, das ist richtig.
"""
import datetime as dt
from zoneinfo import ZoneInfo

METHODE = 'exchange_close_v1'
NACHLAUF_MIN = 15      # Schlussauktion und Datenverzug
# Boerse -> (Zeitzone, Schluss Stunde, Minute) der regulaeren Sitzung inkl. Schlussauktion
BOERSEN = {
    'NYSE': ('America/New_York', 16, 0), 'NASDAQ': ('America/New_York', 16, 0),
    'TSE': ('Asia/Tokyo', 15, 30), 'LSE': ('Europe/London', 16, 35),
    'XETR': ('Europe/Berlin', 17, 35), 'EURONEXT': ('Europe/Paris', 17, 35), 'SIX': ('Europe/Zurich', 17, 30),
    'STO': ('Europe/Stockholm', 17, 30), 'MIL': ('Europe/Rome', 17, 35), 'BME': ('Europe/Madrid', 17, 35),
    'CPH': ('Europe/Copenhagen', 17, 0), 'OSL': ('Europe/Oslo', 16, 25), 'GPW': ('Europe/Warsaw', 17, 5),
    'HEL': ('Europe/Helsinki', 18, 30), 'ATHEX': ('Europe/Athens', 17, 20), 'VIE': ('Europe/Vienna', 17, 35),
}


def _zeit(v):
    """ISO-Text oder Epoch-Sekunden -> aware datetime (UTC) oder None."""
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, (int, float)):
        return dt.datetime.fromtimestamp(v, dt.timezone.utc) if 1e9 < v < 4e9 else None
    try:
        t = dt.datetime.fromisoformat(str(v).replace('Z', '+00:00'))
    except ValueError:
        return None
    return t if t.tzinfo else None


def iso(v):
    t = _zeit(v)
    return t.astimezone(dt.timezone.utc).isoformat(timespec='seconds') if t else None


def einordnen(boerse, kurszeit=None, kursdatum=None, abruf=None):
    """-> {'kind': schluss|handel|unbekannt, 'date': Handelstag (Ortszeit) oder None, 'reason': Text}."""
    b = BOERSEN.get(str(boerse or '').upper())
    ab = _zeit(abruf)
    if not b:
        return {'kind': 'unbekannt', 'date': None, 'reason': 'Börse ohne hinterlegte Schlusszeit'}
    if ab is None:
        return {'kind': 'unbekannt', 'date': None, 'reason': 'Abrufzeitpunkt fehlt'}
    tz = ZoneInfo(b[0])
    ab_lokal = ab.astimezone(tz)
    kz = _zeit(kurszeit)
    if kz is not None:
        if kz > ab + dt.timedelta(minutes=5):
            return {'kind': 'unbekannt', 'date': None, 'reason': 'Kurszeit nach dem Abruf'}
        tag = kz.astimezone(tz).date()
    else:
        try:
            tag = dt.date.fromisoformat(str(kursdatum)[:10])
        except ValueError:
            return {'kind': 'unbekannt', 'date': None, 'reason': 'Kurs ohne Zeitangabe'}
        if tag > ab_lokal.date():
            return {'kind': 'unbekannt', 'date': None, 'reason': 'Kursdatum nach dem Abruf'}
    schluss = dt.datetime(tag.year, tag.month, tag.day, b[1], b[2], tzinfo=tz) + dt.timedelta(minutes=NACHLAUF_MIN)
    if tag < ab_lokal.date() or ab_lokal >= schluss:
        return {'kind': 'schluss', 'date': tag.isoformat(), 'reason': ''}
    if kz is None:
        return {'kind': 'unbekannt', 'date': tag.isoformat(), 'reason': 'Tageskurs vor Börsenschluss abgerufen'}
    return {'kind': 'handel', 'date': tag.isoformat(), 'reason': 'Abruf während der Handelszeit'}
