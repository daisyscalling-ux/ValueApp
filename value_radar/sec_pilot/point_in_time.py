"""Conservative annual filing selection; intentionally not a TTM risk model."""
import datetime as dt
import math

def known(row, filing, cutoff):
    try:
        filed = dt.date.fromisoformat(row['filed'])
        accepted = (filing or {}).get('acceptanceDateTime')
        return (filing is not None and filing.get('filingDate') == row['filed']
                and filing.get('form') == row.get('form') and filed < cutoff
                and (not accepted or dt.date.fromisoformat(accepted[:10]) < cutoff))
    except (KeyError, TypeError, ValueError):
        return False

def finite(value):
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)

def field(facts, tag, selected, duration=True):
    rows = facts.get('facts', {}).get('us-gaap', {}).get(tag, {}).get('units', {}).get('USD', [])
    values = {r['val'] for r in rows if r.get('accn') == selected['accession']
              and r.get('filed') == selected['filed'] and r.get('form') == selected['form']
              and r.get('end') == selected['end'] and finite(r.get('val'))
              and (r.get('start') == selected['start'] if duration else not r.get('start'))}
    return {'tag': tag, 'value': next(iter(values)) if len(values) == 1 else None,
            'status': 'available' if len(values) == 1 else 'conflict' if values else 'missing'}

def select_annual(facts, filings, cutoff):
    # Candidates come from CFO even if capex is missing/conflicting: never silently
    # fall back to an older "complete" filing of the same period.
    rows = facts.get('facts', {}).get('us-gaap', {}).get('NetCashProvidedByUsedInOperatingActivities', {}).get('units', {}).get('USD', [])
    periods = {}
    for r in rows:
        try:
            start, end = dt.date.fromisoformat(r['start']), dt.date.fromisoformat(r['end'])
        except (KeyError, ValueError, TypeError):
            continue
        if not 330 <= (end-start).days <= 380 or end >= cutoff or r.get('form') not in ('10-K', '10-K/A'):
            continue
        filing = filings.get(r.get('accn'))
        if not known(r, filing, cutoff):
            continue
        key = (r['start'], r['end'])
        periods.setdefault(key, {})[r['accn']] = dict(start=r['start'], end=r['end'], accession=r['accn'],
            filed=r['filed'], form=r['form'], accepted=filing.get('acceptanceDateTime'))
    selected_rows = []
    for key, candidates in sorted(periods.items()):
        latest_day = max(r['filed'] for r in candidates.values())
        latest = [r for r in candidates.values() if r['filed'] == latest_day]
        if len(latest) > 1:
            # Intraday order is used only if every filing has an explicit timestamp.
            if not all(r['accepted'] for r in latest) or len({r['accepted'] for r in latest}) != len(latest):
                selected_rows.append(dict(start=key[0], end=key[1], status='ambiguous_filing', fields={}, cfo_minus_capex=None))
                continue
            latest.sort(key=lambda r: r['accepted'])
        chosen = dict(latest[-1])
        fields = {name: field(facts, tag, chosen, duration) for name, tag, duration in [
            ('cfo', 'NetCashProvidedByUsedInOperatingActivities', True),
            ('capex', 'PaymentsToAcquirePropertyPlantAndEquipment', True),
            ('cash', 'CashAndCashEquivalentsAtCarryingValue', False),
            ('debt_total', 'DebtLongtermAndShorttermCombinedAmount', False),
            ('debt_current', 'LongTermDebtCurrent', False),
            ('debt_noncurrent', 'LongTermDebtNoncurrent', False),
            ('short_borrowing', 'ShortTermBorrowings', False),
            ('depreciation', 'Depreciation', True),
            ('amortization', 'AmortizationOfIntangibleAssets', True),
            ('operating_income', 'OperatingIncomeLoss', True)]}
        v = {k: f['value'] for k, f in fields.items()}
        debt, debt_method = v['debt_total'], 'reported_combined'
        components = [v[k] for k in ('debt_current', 'debt_noncurrent', 'short_borrowing')]
        if fields['debt_total']['status'] == 'missing' and all(x is not None and x >= 0 for x in components):
            debt, debt_method = sum(components), 'current_plus_noncurrent_plus_explicit_short_borrowing'
        if debt is None or debt < 0:
            debt, debt_method = None, 'unresolved'
        if v['debt_total'] is not None and all(x is not None and x >= 0 for x in components) and abs(sum(components)-v['debt_total']) > max(1, abs(v['debt_total'])*.001):
            debt, debt_method = None, 'conflicting_debt_definitions'
        cfo, capex = v['cfo'], v['capex']
        fcf = cfo-capex if cfo is not None and capex is not None and capex >= 0 else None
        da = [v['depreciation'], v['amortization']]
        proxy = v['operating_income']+sum(da) if v['operating_income'] is not None and all(x is not None and x >= 0 for x in da) else None
        chosen.update(status='selected', currency='USD', fields=fields, cfo_minus_capex=fcf,
                      debt=debt, debt_method=debt_method,
                      net_debt=debt-v['cash'] if debt is not None and v['cash'] is not None and v['cash'] >= 0 else None,
                      operating_income_plus_da_proxy=proxy,
                      missing_or_conflicting=[k for k, f in fields.items() if f['status'] != 'available'])
        selected_rows.append(chosen)
    return {'cutoff_exclusive': cutoff.isoformat(), 'periods': selected_rows,
            'latest_annual': max(selected_rows, key=lambda r: (r['end'], r['start'])) if selected_rows else None,
            'scope': 'Latest known filing carrying standard annual CFO for each exact period; no reconstruction of amendments without CFO. Annual only, not TTM. Operating income plus D&A is a proxy, not reconciled ROIC EBITDA.'}
