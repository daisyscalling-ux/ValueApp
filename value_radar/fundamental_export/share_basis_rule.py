"""Regelbasierte Aktienbasis fuer Stammaktien mit abweichender Berichtswaehrung.

Eine Notierung ist die Stammaktie selbst (1 handelbare Einheit = 1 Stammaktie), wenn
- der Wertpapiertyp "stock" ist und keine Sonderaktienklasse vorliegt und
- die ISIN keine US-ISIN ist: Depositary Receipts tragen eigene US-ISINs, die auslaendische
  Stammaktie ihre Heimat-ISIN (z. B. OTC:KYCCF mit JP3236200006, LSE:DGE mit GB0002374006).
Echte ADRs/DRs bleiben ausgeschlossen; sie brauchen ein geprueftes Umtauschverhaeltnis in share_basis.json.
Die App prueft danach selbst EZB-Kurs, Waehrungen und Alter (verifiedFxScale in valueapp-cf).
"""
import datetime as dt
import re

METHOD = 'rule_ordinary_share_isin_v1'
ISIN = re.compile(r'[A-Z]{2}[A-Z0-9]{9}[0-9]')


def ordinary_basis(row, annual, quote_currency, quote_source_url, today=None):
    today = today or dt.datetime.now(dt.timezone.utc).date()
    symbol = row.get('listing_symbol') or row.get('ticker')
    isin = str(row.get('isin') or '').upper()
    report = (annual or {}).get('currency')
    if not symbol or row.get('security_type') not in ('stock', 'common_stock', 'common', 'equity'):
        return None
    if row.get('share_class') not in (None, '', 'common', 'ordinary') or not ISIN.fullmatch(isin) or isin.startswith('US'):
        return None
    if not report or not quote_currency or report == quote_currency or {report, quote_currency} == {'GBP', 'GBp'}:
        return None
    if not str(quote_source_url or '').startswith('https://'):
        return None
    return {'symbol': symbol, 'kind': 'ordinary', 'ordinary_shares_per_unit': 1, 'report_currency': report, 'quote_currency': quote_currency,
            'annual_eps_basis': 'ordinary', 'reviewed_at': today.isoformat(), 'source_url': quote_source_url, 'method': METHOD,
            'evidence': f'Security type stock with the non-US ordinary ISIN {isin}; depositary receipts carry separate ISINs.'}
