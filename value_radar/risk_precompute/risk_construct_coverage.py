"""Taegliche Abdeckungsmessung des Risiko-Konstrukts (Version 0.8) fuer das ganze Universum.

Prueft je Notierung und Kennzahl, ob die Eingangsdaten offline vorliegen. Das ist eine
Datenverfuegbarkeit, kein nachgerechneter Score: Die App rechnet mit Live-Daten (ROIC-Abruf,
Peer-Kurse, Fair Value). Kennzahlen, die nur dort pruefbar sind, zaehlen als "app_only",
bewusst offene Kennzahlen (z. B. Bruttomarge bei Banken) als "by_design".

Ergebnis: daten/cf_risk_construct_coverage.json mit Befuellung je Profil und Block und einer
Rangliste der groessten Luecken (Gewicht x fehlende Notierungen).
"""
import datetime as dt
import functools
import json
import math
import os
import re
import unicodedata
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'fundamental_export'))
from share_basis_rule import ordinary_basis  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from listing_identity import listing_matches as _shared_listing_matches  # noqa: E402

DATA = Path(os.environ.get('RISK_DATA_DIR') or Path(__file__).resolve().parents[1] / 'daten')
BLOCKS = {'Kursrisiko': 30, 'Finanzielle Verwundbarkeit': 25, 'Umfeldstress': 15, 'Bewertungsrisiko': 15, 'Wettbewerbsanfälligkeit': 15}
CONSTRUCT_VERSION = '0.8'
METHOD = 'offline-input-availability-v2'
MIN_OBSERVATIONS = 505
SHORT_OBSERVATIONS = 253
PEER_HISTORIES = 5   # die App laedt die Kurshistorien der ersten fuenf ausgewaehlten Peers
PEER_MINIMUM = 3     # und braucht mindestens drei mit aktuellem Abstand zum Jahreshoch

# Spiegel von selectPeers/peerFamily (valueapp-cf, src/lib/peer-selection.ts); nur fuer die Messung.
FAMILIES = [
    ('Universalbanken', r'citigroup|jpmorgan|bank of america|wells fargo|hsbc|bnp paribas|banco santander|barclays|deutsche bank|unicredit|mitsubishi ufj|sumitomo mitsui|mizuho'),
    ('Regionalbanken', r'pnc financial|us bancorp|u\.?s\.? bancorp|truist|fifth third|regions financial|huntington bancshares|keycorp'),
    ('Investmentbanken', r'goldman sachs|morgan stanley|jefferies'),
    ('Vermögensverwalter', r'blackrock|schroders|man group|t\.? rowe price|franklin resources|amundi'),
    ('Versicherer', r'allianz|axa|unipol|zurich insurance|chubb|travelers|progressive|munich re|swiss re'),
    ('Beteiligungsgesellschaften', r'investor ab|industriv|berkshire hathaway|exor'),
    ('Zahlungsnetzwerke', r'^(visa|mastercard)\b'),
    ('Unternehmenssoftware', r'microsoft|oracle|salesforce|sap se|servicenow|adobe|workday'),
    ('Chipdesigner', r'nvidia|advanced micro devices|broadcom|qualcomm|marvell'),
    ('Chipfertiger', r'taiwan semiconductor|united microelectronics|globalfoundries'),
    ('Speicherchips', r'micron|sk hynix'),
    ('Halbleiterausrüstung', r'asml|applied materials|lam research|kla corporation'),
    ('Internetwerbung', r'alphabet|meta platforms'),
    ('Telekommunikation', r'deutsche telekom|verizon|at&t|vodafone|telefonica|orange sa|t-mobile'),
    ('Automobilhersteller', r'toyota|volkswagen|mercedes|bmw|ford motor|general motors|honda motor|suzuki motor|tesla|stellantis'),
    ('Getränkehersteller', r'coca.cola|pepsico|keurig dr pepper'),
]


def finite(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def load(path, default):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return default


def available(d):
    return isinstance(d, dict) and d.get('state') == 'available'


def listing_matches(ticker, listing):
    """Spiegel von listingMatches (valueapp-cf, src/lib/listing-identity.ts); seit 10.11.2026 identisch mit value_radar/listing_identity.py."""
    return _shared_listing_matches(ticker, listing)


def _text(x):
    return str(x if x is not None else '').strip()


def peer_symbol(x):
    return _text(x).upper().split(':')[-1]


def _company(x):
    s = _text(x).lower().replace('&', 'and')
    s = re.sub(r'\b(incorporated|inc|corporation|corp|plc|limited|ltd|company|co|publ|class [a-z])\b', '', s)
    return re.sub(r'[\W_]', '', s)


# Gepruefte Branchengruppen, identische Kopie von valueapp-cf/src/lib/peer-industry-groups.json.
_GROUPS = json.loads((Path(__file__).resolve().parent / 'src' / 'lib' / 'peer-industry-groups.json').read_text(encoding='utf-8'))
_GROUP_OF = {i: g for g, items in _GROUPS['groups'].items() for i in items}
PEER_MINIMUM_SELECTION, GROUP_FILL = 3, 5


def _industry(r):
    raw = re.sub(r'[^a-z0-9]+', ' ', _text(r.get('industry')).lower()).strip()
    return _GROUPS['crosswalk'].get(raw, raw)


def industry_group(r):
    return _GROUP_OF.get(_industry(r), '') if peer_family(r).startswith('Branche: ') else ''


def peer_family(r):
    sub_ = _text(r.get('sub_industry')).lower()
    if sub_ and not re.fullmatch(r'unknown|other|n/a', sub_):
        return 'Unterbranche: ' + re.sub(r'[\W_]+', ' ', sub_)
    name = _text(r.get('name_full') or r.get('name')).lower()
    for family, rx in FAMILIES:
        if re.search(rx, name):
            return family
    ind = _industry(r)
    if re.fullmatch(r'major banks|banks diversified|diversified banks|money center banks', ind):
        return 'Universalbanken'
    if re.fullmatch(r'regional banks|banks regional', ind):
        return 'Regionalbanken'
    return 'Branche: ' + ind if ind and not re.fullmatch(r'finance|financial services|technology|industrials|other|unknown', ind) else ''


def same_company(a, b):
    cik = lambda x: _text(x).lstrip('0') if re.fullmatch(r'0*[1-9][0-9]*', _text(x)) else ''
    ca, cb = _company(a.get('name_full') or a.get('name')), _company(b.get('name_full') or b.get('name'))
    return (_text(a.get('ticker')).upper() == _text(b.get('ticker')).upper() or (bool(a.get('listing_symbol')) and a.get('listing_symbol') == b.get('listing_symbol'))
            or bool(a.get('isin') and a.get('isin') == b.get('isin')) or bool(cik(a.get('cik')) and cik(a.get('cik')) == cik(b.get('cik')))
            or bool(a.get('lei') and a.get('lei') == b.get('lei')) or bool(ca and ca == cb))


def _bare_symbol(r):
    # Boersenendung (SAN.PA fuer EURONEXT:SAN) ist keine Vorzugsaktien-Kennung, wenn die Notierungspruefung sie bestaetigt (wie die App).
    t = peer_symbol(r.get('ticker'))
    return t[:t.rfind('.')] if '.' in t and listing_matches(r.get('ticker'), r.get('listing_symbol')) else t


def _preferred(r):
    return bool(re.search(r'preferred|preference|warrant|fund|etf|bond', _text(r.get('security_type')), re.I)
                or re.search(r'[-.]P(?:R)?[A-Z]+$|\^|/P[A-Z]', _bare_symbol(r))
                or re.search(r'preferred|depositary shares|preference shares|warrant', _text(r.get('name')), re.I))


def select_peers(target, rows, families, limit=8, groups=None):
    """Peer-Auswahl wie /api/peers: gleiche Familie, Primaernotierung zuerst, dann Groesse in gleicher Waehrung, dann kurzes Symbol."""
    group = families.get(id(target))
    if not group:
        return []
    viable = [r for r in rows if _text(r.get('ticker')) and families.get(id(r)) == group and not _preferred(r) and not same_company(target, r)]
    cap = lambda r: r['market_cap'] if finite(r.get('market_cap')) and r['market_cap'] > 0 else None
    base = cap(target)

    def compare(a, b):
        # Paarweiser Vergleich wie in der App (nicht als Sortierschluessel darstellbar).
        primary = int(b.get('is_primary') is True) - int(a.get('is_primary') is True)
        if primary:
            return primary
        ac, bc = cap(a), cap(b)
        if base and ac and bc and target.get('currency') and a.get('currency') == target.get('currency') and b.get('currency') == target.get('currency'):
            d = abs(math.log(ac / base)) - abs(math.log(bc / base))
            return (d > 0) - (d < 0)
        d = len(peer_symbol(a.get('ticker'))) - len(peer_symbol(b.get('ticker')))
        if d:
            return d
        # localeCompare: zuerst ohne Gross-/Kleinschreibung und Akzente, dann exakt.
        fold = lambda s: (unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode().casefold(), s.swapcase())
        na, nb = fold(_text(a.get('name'))), fold(_text(b.get('name')))
        return (na > nb) - (na < nb)
    selected = []
    for r in sorted(viable, key=functools.cmp_to_key(compare)):
        if not any(same_company(p, r) for p in selected):
            selected.append(r)
        if len(selected) == limit:
            break
    # Weniger als drei Peers der exakten Branche: verwandte Branchen der geprueften Gruppe fuellen bis GROUP_FILL auf (wie die App).
    related = groups.get(id(target)) if groups is not None else industry_group(target)
    if len(selected) < PEER_MINIMUM_SELECTION and related:
        extra = [r for r in rows if _text(r.get('ticker')) and families.get(id(r)) != group and not _preferred(r) and not same_company(target, r)
                 and (groups.get(id(r)) if groups is not None else industry_group(r)) == related]
        for r in sorted(extra, key=functools.cmp_to_key(compare)):
            if len(selected) >= min(limit, GROUP_FILL):
                break
            if not any(same_company(p, r) for p in selected):
                selected.append(r)
    return selected


def fx_resolved(b, fx, report, quote, today=None):
    today = today or dt.datetime.now(dt.timezone.utc).date()
    if not isinstance(b, dict) or not isinstance(fx, dict):
        return False
    try:
        age = (today - dt.date.fromisoformat(str(b.get('reviewed_at')))).days
    except ValueError:
        return False
    rates = fx.get('rates') or {}
    target = 'GBP' if quote in ('GBp', 'GBX') else quote
    r, e = b.get('ordinary_shares_per_unit'), b.get('evidence') or {}
    # Verhältnis ungleich 1:1 nur aus der doppelten Prüfung (wie sharesPerUnit in der App).
    derived = (b.get('kind') == 'ADR' and b.get('method') == 'share_count_and_price_ratio_v1' and finite(r) and r > 0 and finite(e.get('byShareCount')) and finite(e.get('byPrice'))
               and abs(e['byShareCount'] / r - 1) <= .02 and abs(e['byPrice'] / r - 1) <= .10)
    return (b.get('kind') in ('ADR', 'ordinary') and (r == 1 or derived) and b.get('annual_eps_basis') == 'ordinary'
            and b.get('report_currency') == report and b.get('quote_currency') == quote and 0 <= age <= 180 and str(b.get('source_url', '')).startswith('https://')
            and fx.get('base') == 'EUR' and finite(rates.get(report)) and finite(rates.get(target)))


class Listing:
    """Offline verfuegbare Eingangsdaten einer Notierung."""

    def __init__(self, symbol, domains, universe_row, stats, annual, market_currency, peers, peer_selected=0, peer_usable=0, share_basis=None, fx=None, today=None):
        self.symbol, self.domains, self.u, self.stats = symbol, domains or {}, universe_row or {}, stats or {}
        self.balance = self.domains.get('balance') or {}
        self.f = (annual or {}).get('fields') or {}
        ac, mc = (annual or {}).get('currency'), market_currency
        self.annual_currency, self.market_currency = ac, mc
        # Waehrungskonflikt wie in der App-Datenpruefung: Bericht und Handel verschieden (GBP/Pence gilt als gleich).
        # Geprüfte Aktienbasis plus EZB-Kurse lösen den Konflikt wie verifiedFxScale in der App (Verhältnis 1:1, höchstens 180 Tage alt).
        self.fx_resolved = fx_resolved(share_basis, fx, ac, mc, today)
        self.currency_conflict = bool(annual) and ac != mc and not (ac == 'GBP' and mc == 'GBp') and not self.fx_resolved
        # Grund unterscheiden: Stammaktie (Regel greift, Datei noch nicht aktualisiert) oder ADR/unklar (Umtauschverhältnis fehlt).
        self.conflict_reason = ('Währungskonflikt: Stammaktie, Aktienbasis noch nicht in der Abschlussdatei' if ordinary_basis(self.u, annual, mc, 'https://placeholder')
                                else 'Währungskonflikt: ADR oder unklare Aktienbasis')
        self.peers, self.peer_selected, self.peer_usable = peers, peer_selected, peer_usable
        self.peer_ev_ebitda = 0
        bc = self.balance.get('bankCapital') or {}
        profile = self.balance.get('profile') or 'unclassified'
        self.bank_like = profile == 'specialist_financial' and available(bc)
        self.profile = 'bank' if self.bank_like else profile

    def stat(self, key):
        s = self.stats
        return not s.get('error') and finite(s.get('observations')) and s['observations'] >= MIN_OBSERVATIONS and finite(s.get(key))


def m(block, name, weight, status, reason=''):
    return {'block': block, 'name': name, 'weight': weight, 'status': status, 'reason': reason}


def yes(ok, reason):
    return 'filled' if ok else 'missing', ('' if ok else reason)


def first(*checks):
    """Erste zutreffende Ursache als Grund; ohne Ursache gilt die Kennzahl als befuellt."""
    for failed, reason in checks:
        if failed:
            return 'missing', reason
    return 'filled', ''


def bank_pb(x):
    """KBV wie die App (financialValuationMetrics): Kurs / (Eigenkapital zum EZB-Kurs / Aktienzahl der Notierung), wenn
    Abschluss und Kurs vorliegen und der Waehrungsunterschied geprueft aufgeloest ist; sonst das KBV des Universums."""
    q, eq = getattr(x, 'quote', {}) or {}, x.f.get('equity')
    price, shares = q.get('price'), q.get('shares_out')
    rates = (getattr(x, 'fx', {}) or {}).get('rates') or {}
    ac, mc = x.annual_currency, x.market_currency
    if finite(price) and finite(shares) and shares > 0 and finite(eq) and eq > 0 and ac and mc:
        if ac == mc or (ac == 'GBP' and mc in ('GBp', 'GBX')):
            scale = 100 if mc in ('GBp', 'GBX') and ac == 'GBP' else 1
        elif x.fx_resolved and finite(rates.get(ac)) and finite(rates.get('GBP' if mc in ('GBp', 'GBX') else mc)):
            scale = rates['GBP' if mc in ('GBp', 'GBX') else mc] / rates[ac] * (100 if mc in ('GBp', 'GBX') else 1)
        else:
            scale = None
        if scale:
            return price / (eq * scale / shares)
    return x.u.get('pb')


# Spiegel von insurerSolvencyScope (valueapp-cf, src/lib/risk-construct.ts): vergleichbare Gruppen-Solvenzquote nur
# unter Solvency II (EWR) und Solvency UK; andere Systeme bewusst ausserhalb (Entscheidung 11.11.2026).
SOLVENCY_COUNTRIES = {'AT', 'BE', 'BG', 'HR', 'CY', 'CZ', 'DK', 'EE', 'FI', 'FR', 'DE', 'GR', 'HU', 'IS', 'IE', 'IT', 'LV', 'LI', 'LT', 'LU',
                      'MT', 'NL', 'NO', 'PL', 'PT', 'RO', 'SK', 'SI', 'ES', 'SE', 'GB'}
SOLVENCY_EXCEPTIONS = {'GB0007099541': 'Hongkong GWS (Insurance Authority als Gruppenaufsicht)'}   # Prudential plc, HY26-Bericht
SOLVENCY_SCOPE_REASON = 'Kein vergleichbares Gruppen-Solvenzsystem (außerhalb Solvency II/UK)'


def insurer_solvency_comparable(row):
    isin = _text((row or {}).get('isin')).upper()
    if not re.fullmatch(r'[A-Z]{2}[A-Z0-9]{9}[0-9]', isin):
        return True
    return isin not in SOLVENCY_EXCEPTIONS and isin[:2] in SOLVENCY_COUNTRIES


def metrics(x):
    """Kennzahlen des Konstrukts mit Status filled / missing / app_only / by_design."""
    out = []
    K, F, U, V, W = BLOCKS.keys()
    s = x.stats
    # Verkuerzte Historie (253-504 Kurspunkte, shortHistory): ES und Volatilitaet gefuellt, groesster Rueckgang offen (wie die App).
    short = s.get('shortHistory') is True and finite(s.get('observations')) and SHORT_OBSERVATIONS <= s['observations'] < MIN_OBSERVATIONS
    for name, key, w in (('Expected Shortfall', 'es', 15), ('Volatilität', 'vol', 10), ('Größter Rückgang', 'dd', 5)):
        out.append(m(K, name, w, *first((not s, 'Keine Kurshistorie'), (bool(s.get('error')), 'Kurshistorie fehlerhaft'),
                                        (key == 'dd' and short, 'Verkürzte Historie: größter Rückgang erst ab zwei Handelsjahren'),
                                        (not (finite(s.get('observations')) and (s['observations'] >= MIN_OBSERVATIONS or short)), 'Kurshistorie kürzer als 505 Handelstage'),
                                        (not finite(s.get(key)), 'Kennzahl in der Vorberechnung noch nicht vorhanden'))))
    f, u, b = x.f, x.u, x.balance
    p = x.profile
    if p == 'bank':
        c = b.get('bankCapital') or {}
        credit = available(c.get('creditQuality')) or available((x.domains.get('reviewedRisk') or {}).get('bankCredit'))
        out += [m(F, 'Kernkapital-Puffer (CET1)', 10, *yes(available(c) and available(c.get('capitalRequirement')), 'Geprüfte Kapitalquote mit Anforderung fehlt')),
                m(F, 'Liquiditätsdeckung (LCR)', 7.5, *yes(available(c) and available(c.get('liquidity')), 'Geprüfte LCR fehlt')),
                m(F, 'Kreditqualität', 7.5, *yes(available(c) and credit, 'Geprüfte Kreditqualität fehlt'))]
    elif p == 'insurer':
        solvency = available(b.get('insurerSolvency'))
        out += [m(F, 'Solvenzquote', 15, 'filled') if solvency else
                m(F, 'Solvenzquote', 15, 'by_design', SOLVENCY_SCOPE_REASON) if not insurer_solvency_comparable(x.u) else
                m(F, 'Solvenzquote', 15, 'missing', 'Geprüfte Solvenzquote fehlt'),
                m(F, 'Reserve- und Kapitalanlagerisiko', 10, 'by_design', 'Für Versicherer noch nicht umgesetzt')]
    elif p == 'specialist_financial':
        eq, ta = f.get('equity'), f.get('total_assets')
        ratio = eq / ta if finite(eq) and finite(ta) and ta > 0 else None
        nd_ok = not x.currency_conflict and finite(eq) and eq > 0 and finite(f.get('total_debt')) and finite(f.get('cash')) and ratio is not None
        if nd_ok and ratio < .10:
            out.append(m(F, 'Nettofinanzschulden / Eigenkapital', 15, 'by_design', 'Bilanz mit Kunden-, Clearing- oder Bankvermögen'))
        else:
            out.append(m(F, 'Nettofinanzschulden / Eigenkapital', 15, *yes(nd_ok, 'Eigenkapital, Schulden, Kasse oder Bilanzsumme fehlen oder Währungskonflikt')))
        out.append(m(F, 'Eigenkapitalrendite', 10, *yes(finite(f.get('net_income')) and finite(eq) and eq > 0, 'Jahresergebnis oder Eigenkapital fehlt')))
    else:
        ebitda = f.get('ebitda')
        out += [m(F, 'Nettoschulden / EBITDA', 15, *yes((finite(ebitda) and ebitda > 0 and finite(f.get('total_debt')) and finite(f.get('cash'))) or finite(u.get('net_debt_ebitda')), 'EBITDA, Schulden oder Kasse fehlen')),
                # Die App nimmt FCFF und Umsatz aus der ROIC-Zeile; seit dem Universumsexport mit fcff_margin genau messbar, sonst Näherung über den Ersatzabschluss.
                (m(F, 'FCFF-Marge', 10, *yes(finite(u.get('fcff_margin')), 'ROIC liefert keinen FCFF oder Umsatz (TTM)')) if 'fcff_margin' in u else
                 m(F, 'FCFF-Marge', 10, *yes(finite(f.get('operating_cashflow')) and finite(f.get('capex')) and finite(f.get('revenue')) and f['revenue'] > 0, 'Cashflow, Investitionen oder Umsatz fehlen (Näherung über den Ersatzabschluss)')))]
    out += [m(U, 'Markt-ETF', 10, *yes(available(x.domains.get('market')), 'Kein Markt-ETF zugeordnet')),
            m(U, 'Peer-Stress', 5, *first((x.peer_selected == 0, 'Keine Peers ausgewählt (keine Geschäftsfamilie oder Unterbranche)'),
                                          (x.peer_selected < PEER_MINIMUM, 'Weniger als drei Peers ausgewählt'),
                                          (x.peer_usable < PEER_MINIMUM, 'Weniger als drei der ersten fünf Peers mit aktueller Kurshistorie')))]
    growth = f.get('revenue_growth') if finite(f.get('revenue_growth')) else (u['revenue_growth'] / 100 if finite(u.get('revenue_growth')) else None)
    if p in ('bank', 'insurer'):
        out.append(m(V, 'Erwartungslücke Eigenkapitalrendite', 10, *first((x.currency_conflict, x.conflict_reason),
                                                                        (not (finite(bank_pb(x)) and .05 < bank_pb(x) < 15), 'KBV fehlt oder unplausibel'),
                                                                        (not finite(u.get('roe')), 'Eigenkapitalrendite fehlt'))))
    elif p == 'specialist_financial':
        ni = f.get('net_income')
        out.append(m(V, 'Erwartungslücke Gewinnwachstum', 10, *first((x.currency_conflict, x.conflict_reason),
                                                                   (not (finite(ni) and ni > 0), 'Verlust oder Jahresergebnis fehlt'),
                                                                   (growth is None, 'Umsatzwachstum fehlt'),
                                                                   (growth is not None and abs(growth) > .5, 'Umsatzsprung über ±50 %'))))
    else:
        fcf = f['operating_cashflow'] - abs(f['capex']) if finite(f.get('operating_cashflow')) and finite(f.get('capex')) else None
        if fcf is None or fcf <= 0:
            # Ersatz in der App (Version 0.9): EV/EBITDA gegenüber dem Median von mindestens drei Peers.
            own = u.get('ev_ebitda')
            out.append(m(V, 'Erwartungslücke Reverse DCF', 10, *first((not (finite(own) and own > 0), 'Kein positiver Cashflow und kein positives EV/EBITDA'),
                                                                    (x.peer_ev_ebitda < 3, 'Kein positiver Cashflow und weniger als drei Peers mit EV/EBITDA'))))
        else:
            out.append(m(V, 'Erwartungslücke Reverse DCF', 10, *first((x.currency_conflict, x.conflict_reason),
                                                                    (growth is None, 'Umsatzwachstum fehlt'))))
    out.append(m(V, 'Abstand zum Bear-Szenario', 5, 'app_only', 'Benötigt die Szenariorechnung der App'))
    if p in ('bank', 'insurer', 'specialist_financial'):
        out += [m(W, 'Bruttomargen-Trend', 5, 'by_design', 'Für Finanzunternehmen nicht definiert'),
                m(W, 'EBITDA-Marge gegenüber Peers', 5, 'by_design', 'Für Finanzunternehmen nicht aussagekräftig')]
    else:
        out += [m(W, 'Bruttomargen-Trend', 5, 'app_only', 'Benötigt drei Geschäftsjahre aus dem ROIC-Abruf der App'),
                m(W, 'EBITDA-Marge gegenüber Peers', 5, *yes(finite(u.get('ebitda_margin')) and x.peers >= 3, 'Eigene EBITDA-Marge oder mindestens drei Peers mit Marge fehlen'))]
    out.append(m(W, 'Umsatzentwicklung', 5, 'app_only', 'Benötigt drei Geschäftsjahre aus dem ROIC-Abruf der App'))
    return out


PREFERRED_REASON = 'Vorzugsaktie: Risikomodell gilt für Stammaktien'


def preferred_instrument(r):
    """Spiegel von preferredInstrument (valueapp-cf, src/lib/risk-construct.ts)."""
    t = _text(r.get('ticker') or r.get('symbol')).upper().split(':')[-1]
    return bool(re.fullmatch(r'[A-Z]+-P[A-Z]+', t) or re.fullmatch(r'[A-Z]+\.PR[A-Z]', t) or re.search(r'preferred|preference', _text(r.get('security_type')), re.I))


def build(universe, shards, risk, annuals, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    rows = {r.get('listing_symbol'): r for r in universe.get('kandidaten', []) if r.get('listing_symbol')}
    per_profile = defaultdict(lambda: {'listings': 0, 'blocks': defaultdict(lambda: defaultdict(float))})
    per_metric = defaultdict(lambda: {'filled': 0, 'missing': 0, 'app_only': 0, 'by_design': 0, 'weight': 0, 'reasons': defaultdict(int)})
    pool = [r for r in universe.get('kandidaten', []) if not (r.get('listing_symbol') and r.get('ticker')) or listing_matches(r['ticker'], r['listing_symbol'])]
    families = {id(r): peer_family(r) for r in pool}
    groups = {id(r): industry_group(r) for r in pool}
    by_symbol = {r.get('listing_symbol'): r for r in pool}
    def drawdown_ok(r):
        s = (risk.get(r.get('listing_symbol')) or {}).get('statistics') or {}
        return finite(s.get('drawdown')) and not s.get('error')
    for symbol, domains in shards.items():
        u = rows.get(symbol, {})
        target = by_symbol.get(symbol)
        chosen = select_peers(target, pool, families, groups=groups) if target is not None else []
        usable = sum(1 for r in chosen[:PEER_HISTORIES] if drawdown_ok(r))
        ev_peers = sum(1 for r in chosen if finite(r.get('ev_ebitda')) and r['ev_ebitda'] > 0)
        # Wie competitionMetrics der App: alle ausgewaehlten Peers (bis zu 8, inkl. Branchengruppe) mit EBITDA-Marge, ohne die eigene Notierung.
        margin_peers = sum(1 for r in chosen if finite(r.get('ebitda_margin')) and r.get('listing_symbol') != symbol)
        annual, currency, basis, fx, quote = (tuple(annuals.get(symbol) or ()) + (None, None, None, None, None))[:5]
        x = Listing(symbol, domains, u, (risk.get(symbol) or {}).get('statistics'), annual, currency, margin_peers, len(chosen), usable, basis, fx, now.date())
        x.peer_ev_ebitda = ev_peers
        x.quote, x.fx = quote or {}, fx or {}
        prof = per_profile[x.profile]
        prof['listings'] += 1
        out_of_scope = preferred_instrument({**u, 'ticker': u.get('ticker') or symbol})
        for k in metrics(x):
            if out_of_scope:
                k = {**k, 'status': 'by_design', 'reason': PREFERRED_REASON}
            blk = prof['blocks'][k['block']]
            blk[k['status']] += k['weight']
            pm = per_metric[(x.profile, k['block'], k['name'])]
            pm[k['status']] += 1
            pm['weight'] = k['weight']
            if k['status'] == 'missing':
                pm['reasons'][k['reason']] += 1
    profiles = {}
    for name, prof in sorted(per_profile.items()):
        n = prof['listings']
        blocks = {}
        for b, w in BLOCKS.items():
            s = prof['blocks'][b]
            blocks[b] = {'weight': w, **{k: round(s[k] / n, 2) for k in ('filled', 'missing', 'app_only', 'by_design')},
                         'filledShareOfMeasurable': round(s['filled'] / (s['filled'] + s['missing']), 3) if s['filled'] + s['missing'] else None}
        tot = {k: round(sum(prof['blocks'][b][k] for b in BLOCKS) / n, 1) for k in ('filled', 'missing', 'app_only', 'by_design')}
        profiles[name] = {'listings': n, 'averageWeight': tot, 'blocks': blocks}
    gaps = [{'profile': p, 'block': b, 'metric': n, 'weight': v['weight'], 'missingListings': v['missing'], 'filledListings': v['filled'],
             'weightedGap': round(v['weight'] * v['missing'], 1), 'reasons': dict(sorted(v['reasons'].items(), key=lambda kv: -kv[1]))}
            for (p, b, n), v in per_metric.items() if v['missing']]
    gaps.sort(key=lambda g: -g['weightedGap'])
    app_only = sorted({(b, n) for (p, b, n), v in per_metric.items() if v['app_only']})
    listings = sum(p['listings'] for p in profiles.values())
    overall = {k: round(sum(p['averageWeight'][k] * p['listings'] for p in profiles.values()) / listings, 1) for k in ('filled', 'missing', 'app_only', 'by_design')} if listings else {}
    return {'schema': 1, 'method': METHOD, 'constructVersion': CONSTRUCT_VERSION, 'generatedAt': now.isoformat(),
            'listings': listings, 'overallAverageWeight': overall, 'profiles': profiles, 'largestGaps': gaps[:25],
            'appOnlyMetrics': [{'block': b, 'metric': n} for b, n in app_only],
            'limitations': ['Measures whether offline inputs exist, not the score the app computes with live data.',
                            'Peer stress mirrors the app peer selection (selectPeers) and counts the first five peers with a precomputed current drawdown.',
                            'Corporate FCF uses operating cash flow minus capex from the dated annual record, not the FCFF of the app.']}


def annual_records(folder):
    out = {}
    for f in (folder / 'fundamentals').glob('*.json'):
        d = load(f, {})
        a = d.get('annual') if isinstance(d.get('annual'), dict) else None
        out[f.stem] = (a, (d.get('market') or {}).get('currency'), d.get('share_basis'), d.get('fx'), (d.get('market') or {}).get('fields') or {})
    return out


def main(folder=DATA):
    folder = Path(folder)
    manifest = load(folder / 'cf_risk_app_manifest.json', {})
    shards = {}
    for h in (manifest.get('shards') or {}).values():
        for s in load(folder / 'risk_app' / f'{h}.json', {}).get('stocks', []):
            shards[s['symbol']] = s.get('domains', {})
    files = annual_records(folder)
    annuals = {sym: files.get(sym.replace(':', '_'), (None, None, None, None, None)) for sym in shards}
    result = build(load(folder / 'cf_universum.json', {}), shards, (load(folder / 'cf_risk.json', {}).get('stocks') or {}), annuals)
    (folder / 'cf_risk_construct_coverage.json').write_text(json.dumps(result, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print(json.dumps({'listings': result['listings'], 'overallAverageWeight': result['overallAverageWeight'],
                      'topGaps': [(g['profile'], g['metric'], g['missingListings']) for g in result['largestGaps'][:5]]}, ensure_ascii=False))


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else DATA)
