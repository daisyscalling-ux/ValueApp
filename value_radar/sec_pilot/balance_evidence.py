"""Filing-specific reviewed book debt and unrestricted cash, not market values."""
EVIDENCE = {
    (1013462, '0001013462-24-000007'): {
        'source': 'https://www.sec.gov/Archives/edgar/data/1013462/000101346224000007/anss-20231231.htm',
        'debt': {'tags': ['LongTermDebtNoncurrent'],
                 'values': {'2022': [753574000], '2023': [753891000]},
                 'basis': 'Note 10: total term loan carrying amount is noncurrent; no outstanding revolver, all debt matures in 2027.'}},
    (1013462, '0001013462-23-000013'): {
        'source': 'https://www.sec.gov/Archives/edgar/data/1013462/000101346223000013/anss-20221231.htm',
        'debt': {'tags': ['LongTermDebtNoncurrent'],
                 'values': {'2021': [753576000], '2022': [753574000]},
                 'basis': 'Note 10: total term loan carrying amount is noncurrent; no outstanding revolver, all debt matures in 2027.'}},
    (1013462, '0001013462-25-000009'): {
        'source': 'https://www.sec.gov/Archives/edgar/data/1013462/000101346225000009/anss-20241231.htm',
        'debt': {'tags': ['LongTermDebtNoncurrent'],
                 'values': {'2023': [753891000], '2024': [754208000]},
                 'basis': 'Note 11: all term loan debt is noncurrent; no revolver borrowings. Book carrying amount, not principal.'},
        'cash': {'tags': ['CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents'],
                 'values': {'2023': [860201000], '2024': [1446743000]},
                 'basis': 'Matches cash and cash equivalents on consolidated balance sheet; short-term investments excluded.'}},
    (1038357, '0001038357-24-000020'): {
        'source': 'https://www.sec.gov/Archives/edgar/data/1038357/000103835724000020/pxd-20231231.htm',
        'debt': {'tags': ['LongTermDebt'], 'values': {'2023': [4835000000]},
                 'basis': 'Debt note: total carrying debt including current portion; no outstanding credit facility borrowings.'}},
    (101778, '0000101778-24-000023'): {
        'source': 'https://www.sec.gov/Archives/edgar/data/101778/000010177824000023/mro-20231231.htm',
        'debt': {'tags': ['LongTermDebt', 'CommercialPaper'],
                 'values': {'2022': [5923000000, 0], '2023': [4978000000, 450000000]},
                 'basis': 'Note 14 debt carrying amount plus separately reported short-term commercial paper; no double counting of current maturities.'}},
}


def reviewed_balance(facts, selected, metric, read_field):
    try:
        evidence = EVIDENCE.get((int(facts['cik']), selected['accession']), {})
    except (KeyError, ValueError, TypeError):
        return None
    rule = evidence.get(metric)
    if not rule:
        return None
    year = selected['end'][:4]
    expected = rule['values'].get(year)
    if expected is None or selected['end'] != year + '-12-31':
        return None
    components = [read_field(facts, tag, selected, False) for tag in rule['tags']]
    valid = all(c['status'] == 'available' and c['value'] == value
                for c, value in zip(components, expected))
    return {'status': 'verified' if valid else 'evidence_mismatch',
            'value': sum(c['value'] for c in components) if valid else None,
            'components': components, 'source': evidence['source'], 'basis': rule['basis'],
            'reviewed_on': '2026-10-18', 'accession': selected['accession']}
