"""Reviewed filing-specific cash capex mappings. Never extrapolate to other filings."""
import math

EVIDENCE = {
    (1013462, '0001013462-24-000007'): {
        'source': 'https://www.sec.gov/Archives/edgar/data/1013462/000101346224000007/anss-20231231.htm',
        'tags': ['PaymentsToAcquireProductiveAssets'],
        'values': {'2021': [23018000], '2022': [24370000], '2023': [25318000]},
        'basis': 'Consolidated cash flow statement: capital expenditures; acquisitions separately reported.'},
    (1013462, '0001013462-23-000013'): {
        'source': 'https://www.sec.gov/Archives/edgar/data/1013462/000101346223000013/anss-20221231.htm',
        'tags': ['PaymentsToAcquireProductiveAssets'],
        'values': {'2020': [35370000], '2021': [23018000], '2022': [24370000]},
        'basis': 'Consolidated cash flow statement: capital expenditures; acquisitions separately reported.'},
    (1013462, '0001013462-25-000009'): {
        'source': 'https://www.sec.gov/Archives/edgar/data/1013462/000101346225000009/anss-20241231.htm',
        'tags': ['PaymentsToAcquireProductiveAssets'],
        'values': {'2022': [24370000], '2023': [25318000], '2024': [44045000]},
        'basis': 'Consolidated cash flow statement: capital expenditures; acquisitions separately reported.'},
    (1038357, '0001038357-24-000020'): {
        'source': 'https://www.sec.gov/Archives/edgar/data/1038357/000103835724000020/pxd-20231231.htm',
        'tags': ['PaymentsToAcquireOilAndGasProperty', 'PaymentsToAcquireOtherProductiveAssets'],
        'values': {'2021': [3156000000, 118000000], '2022': [3920000000, 113000000],
                   '2023': [4571000000, 177000000]},
        'basis': 'Cash additions to oil/gas properties plus other assets and property/equipment; not management adjusted FCF.'},
    (4447, '0001628280-25-008716'): {
        'source': 'https://www.sec.gov/Archives/edgar/data/4447/000162828025008716/hes-20241231.htm',
        'tags': ['PaymentsToAcquireOilAndGasPropertyAndEquipment', 'PaymentsToAcquireMachineryAndEquipment'],
        'values': {'2022': [2487000000, 238000000], '2023': [3884000000, 224000000],
                   '2024': [4640000000, 306000000]},
        'basis': 'Cash additions to property/plant/equipment: E&P plus Midstream.'},
}


def reviewed_capex(facts, selected, read_field):
    try:
        evidence = EVIDENCE.get((int(facts['cik']), selected['accession']))
    except (KeyError, ValueError, TypeError):
        return None
    if evidence is None:
        return None
    year = selected['end'][:4]
    expected = evidence['values'].get(year)
    if expected is None or selected['start'] != year + '-01-01' or selected['end'] != year + '-12-31':
        return None
    components = [read_field(facts, tag, selected) for tag in evidence['tags']]
    values = [c['value'] for c in components]
    valid = all(c['status'] == 'available' and isinstance(v, (int, float))
                and not isinstance(v, bool) and math.isfinite(v) and v >= 0 and v == target
                for c, v, target in zip(components, values, expected))
    return {'status': 'verified' if valid else 'evidence_mismatch',
            'value': sum(values) if valid else None, 'components': components,
            'source': evidence['source'], 'basis': evidence['basis'],
            'reviewed_on': '2026-10-18', 'accession': selected['accession']}
