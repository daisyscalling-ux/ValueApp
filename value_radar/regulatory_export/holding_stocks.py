"""Reviewed common-stock mapping. No fuzzy names, suffix stripping or score."""
import datetime as dt
import re
from collections import Counter

def key(name):
    return re.sub('[^A-Z0-9]', '', str(name or '').upper())

def enrich(report, universe, holdings, registry, today=None):
    today = today or dt.datetime.now(dt.timezone.utc).date()
    if registry.get('schema') != 1 or holdings.get('scope') != 'FR_Y9C_consolidated_reporting_entity':
        raise ValueError('Unsupported holding mapping')
    entries = registry['entries']
    symbols = [r['symbol'] for r in entries]
    if len(set(symbols)) != len(symbols):
        raise ValueError('Duplicate registry symbol')
    start = dt.date.fromisoformat(registry['reviewed_on'])
    end = dt.date.fromisoformat(registry['review_expires'])
    if end < start:
        raise ValueError('Invalid review dates')
    age = (today - dt.date.fromisoformat(holdings['reporting_period'])).days
    universe_rows = universe.get('kandidaten', [])
    symbol_of = lambda r: r.get('listing_symbol') or r.get('ticker')
    counts = Counter(symbol_of(r) for r in universe_rows)
    inputs = {symbol_of(r): r for r in universe_rows}
    existing = {r['symbol']: r for r in report['stocks']}
    verified = 0
    for entry in entries:
        symbol = entry['symbol']
        if symbol not in inputs:
            continue
        stock = inputs[symbol]
        row = existing.get(symbol)
        if row is None:
            row = {'symbol': symbol, 'name': stock.get('name'), 'industry': stock.get('industry'),
                   'country': stock.get('country'), 'fdic_name_candidates': []}
            report['stocks'].append(row)
        row.update(group_metrics=None, score=None, state='identity_review')
        entity = holdings['entities'].get(entry['rssd_id'])
        reason = None
        if counts[symbol] != 1:
            reason = 'duplicate_universe_symbol'
        elif entry.get('security_type') != 'common_stock' or entry.get('scope') != 'listed_consolidated_holding':
            reason = 'security_scope_not_verified'
        elif not start <= today <= end:
            reason = 'identity_review_expired'
        elif not entity or key(entity['name']) != key(entry['holding_name']):
            reason = 'holding_identity_changed'
        elif key(stock.get('name')) not in {key(n) for n in [entry['holding_name'], *entry.get('name_aliases', [])]}:
            reason = 'listing_name_changed'
        elif not 0 <= age <= 180:
            reason = 'holding_data_stale_or_future'
        elif not entry.get('listing_source_url') or not entry.get('holding_evidence'):
            reason = 'identity_evidence_missing'
        if reason:
            row['holding_mapping_reason'] = reason
            continue
        metrics = {}
        for code, definition in holdings['definitions'].items():
            observation = entity['metrics'].get(code)
            if observation:
                metrics[definition['metric']] = {**observation, 'source_field': code,
                    'unit': definition['unit'], 'source_unit': definition['source_unit']}
        row.update(state='verified_holding_capital', holding_rssd_id=entry['rssd_id'],
            group_metrics=metrics, reporting_period=holdings['reporting_period'],
            age_days=age, scope='listed_consolidated_holding', identity_evidence=entry,
            source_files=holdings['files'], historical_point_in_time_usable=False,
            missing_requirements=['liquidity_coverage_ratio','holding_asset_quality','institution_specific_capital_requirement'])
        verified += 1
    report['summary']['financial_listings'] = len(report['stocks'])
    report['summary']['verified_group_metrics'] = verified
    report['summary']['holding_mapping_review_required'] = sum('holding_mapping_reason' in r for r in report['stocks'])
    return report
