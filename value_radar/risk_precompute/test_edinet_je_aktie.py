"""Fünfjahresübersicht aus EDINET-Jahresberichten (edinet_summary_per_share_v1)."""
import datetime as dt
import io
import unittest
import zipfile

from edinet_je_aktie import parse_summary, parse_zip, select_alt, alt_ziel, run, METHOD

DOC = {'edinetCode': 'E01234', 'periodStart': '2025-04-01', 'periodEnd': '2026-03-31', 'docID': 'S100AAAA'}
NOW = dt.datetime(2026, 11, 27, 12, tzinfo=dt.timezone.utc)


def ctx(cid, ende, start=None, einzel=False, segment=False, code='E01234'):
    dim = ''
    if einzel:
        dim = '<xbrli:segment><xbrldi:explicitMember dimension="jppfs_cor:ConsolidatedOrNonConsolidatedAxis">jppfs_cor:NonConsolidatedMember</xbrldi:explicitMember></xbrli:segment>'
    if segment:
        dim = '<xbrli:segment><xbrldi:explicitMember dimension="jpcrp_cor:OperatingSegmentsAxis">x:FooMember</xbrldi:explicitMember></xbrli:segment>'
    per = f'<xbrli:startDate>{start}</xbrli:startDate><xbrli:endDate>{ende}</xbrli:endDate>' if start else f'<xbrli:instant>{ende}</xbrli:instant>'
    return f'<xbrli:context id="{cid}"><xbrli:entity><xbrli:identifier scheme="http://disclosure.edinet-fsa.go.jp">{code}-000</xbrli:identifier>{dim}</xbrli:entity><xbrli:period>{per}</xbrli:period></xbrli:context>'


def instanz(fakten, standard='', konsolidiert='true', code='E01234', extra_ctx=''):
    jahre = [(2026, 'CurrentYear'), (2025, 'Prior1Year'), (2024, 'Prior2Year'), (2023, 'Prior3Year'), (2022, 'Prior4Year')]
    c = ''.join(ctx(f'{n}Duration', f'{y}-03-31', f'{y - 1}-04-01') + ctx(f'{n}Instant', f'{y}-03-31')
                + ctx(f'{n}Duration_NonConsolidatedMember', f'{y}-03-31', f'{y - 1}-04-01', einzel=True)
                + ctx(f'{n}Instant_NonConsolidatedMember', f'{y}-03-31', einzel=True) for y, n in jahre)
    c += ctx('Seg', '2026-03-31', '2025-04-01', segment=True) + extra_ctx
    return ('<?xml version="1.0" encoding="UTF-8"?><xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance" xmlns:iso4217="http://www.xbrl.org/2003/iso4217" '
            'xmlns:xbrldi="http://xbrl.org/2006/xbrldi" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
            'xmlns:jpcrp_cor="http://disclosure.edinet-fsa.go.jp/taxonomy/jpcrp/2025-11-01/jpcrp_cor" '
            'xmlns:jppfs_cor="http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2025-11-01/jppfs_cor" '
            'xmlns:jpdei_cor="http://disclosure.edinet-fsa.go.jp/taxonomy/jpdei/2013-08-31/jpdei_cor">'
            f'<jpdei_cor:EDINETCodeDEI contextRef="FilingDateInstant">{code}</jpdei_cor:EDINETCodeDEI>'
            f'<jpdei_cor:WhetherConsolidatedFinancialStatementsArePreparedDEI contextRef="FilingDateInstant">{konsolidiert}</jpdei_cor:WhetherConsolidatedFinancialStatementsArePreparedDEI>'
            + c + '<xbrli:unit id="JPY"><xbrli:measure>iso4217:JPY</xbrli:measure></xbrli:unit>'
            '<xbrli:unit id="JPYPerShares"><xbrli:divide><xbrli:unitNumerator><xbrli:measure>iso4217:JPY</xbrli:measure></xbrli:unitNumerator>'
            '<xbrli:unitDenominator><xbrli:measure>xbrli:shares</xbrli:measure></xbrli:unitDenominator></xbrli:divide></xbrli:unit>'
            '<xbrli:unit id="pure"><xbrli:measure>xbrli:pure</xbrli:measure></xbrli:unit><xbrli:unit id="shares"><xbrli:measure>xbrli:shares</xbrli:measure></xbrli:unit>'
            + ''.join(f'<jpcrp_cor:{el}{standard}SummaryOfBusinessResults contextRef="{c}" unitRef="{u}" decimals="0"{" xsi:nil=\"true\">" if v is None else ">" + str(v)}</jpcrp_cor:{el}{standard}SummaryOfBusinessResults>'
                      for el, c, u, v in fakten) + '</xbrli:xbrl>').encode('utf-8')


def jgaap():
    f = []
    for (n, eps, ni, bps, per, dps, sh) in [('CurrentYear', 300.0, 30e9, 2500.0, 12.5, 90.0, 100e6), ('Prior1Year', 250.0, 25e9, 2300.0, 13.0, 80.0, 100e6),
                                            ('Prior4Year', 400.0, 20e9, 3600.0, 11.0, 120.0, 50e6)]:
        f += [('BasicEarningsLossPerShare', f'{n}Duration', 'JPYPerShares', eps), ('DilutedEarningsPerShare', f'{n}Duration', 'JPYPerShares', None),
              ('ProfitLossAttributableToOwnersOfParent', f'{n}Duration', 'JPY', ni), ('NetAssetsPerShare', f'{n}Instant', 'JPYPerShares', bps),
              ('PriceEarningsRatio', f'{n}Duration', 'pure', per), ('DividendPaidPerShare', f'{n}Duration_NonConsolidatedMember', 'JPYPerShares', dps),
              ('TotalNumberOfIssuedShares', f'{n}Instant_NonConsolidatedMember', 'shares', sh)]
    f.append(('BasicEarningsLossPerShare', 'Seg', 'JPYPerShares', 999.0))
    return f


class Parser(unittest.TestCase):
    def test_jgaap_fuenf_jahre_konzern_und_einzel(self):
        r = parse_summary(instanz(jgaap()), DOC)
        self.assertEqual(r['standard'], 'jgaap')
        j = {x['end']: x['fields'] for x in r['jahre']}
        self.assertEqual(sorted(j), ['2022-03-31', '2025-03-31', '2026-03-31'], 'nur Jahre mit Gewinn oder Gewinn je Aktie')
        a = j['2026-03-31']
        self.assertEqual((a['eps_basic'], a['eps_diluted'], a['net_income'], a['bvps'], a['per'], a['dps'], a['shares_issued']),
                         (300.0, None, 30e9, 2500.0, 12.5, 90.0, 100e6), 'nil bleibt offen, Segment übergangen')
        self.assertEqual(j['2022-03-31']['eps_basic'], 400.0)
        self.assertEqual(r['konflikte'], [])

    def test_ifrs_buchwert_je_aktie_unter_irrefuehrendem_namen(self):
        f = [('BasicEarningsLossPerShare', 'CurrentYearDuration', 'JPYPerShares', 150.0), ('ProfitLossAttributableToOwnersOfParent', 'CurrentYearDuration', 'JPY', 9e9),
             ('EquityToAssetRatio', 'CurrentYearInstant', 'JPYPerShares', 1800.0), ('PriceEarningsRatio', 'CurrentYearDuration', 'pure', 20.0)]
        r = parse_summary(instanz(f, standard='IFRS'), DOC)
        self.assertEqual((r['standard'], r['jahre'][0]['fields']['bvps']), ('ifrs', 1800.0))

    def test_ifrs_konzern_mit_jgaap_einzelabschluss(self):
        # Wie im ersten Lauf (45 Titel verworfen): Muttergesellschaft im Einzelabschluss nach J-GAAP.
        f = [('BasicEarningsLossPerShareIFRS', 'CurrentYearDuration', 'JPYPerShares', 150.0), ('ProfitLossAttributableToOwnersOfParentIFRS', 'CurrentYearDuration', 'JPY', 9e9),
             ('BasicEarningsLossPerShare', 'CurrentYearDuration_NonConsolidatedMember', 'JPYPerShares', 40.0),
             ('NetIncomeLoss', 'CurrentYearDuration_NonConsolidatedMember', 'JPY', 2e9),
             ('DividendPaidPerShare', 'CurrentYearDuration_NonConsolidatedMember', 'JPYPerShares', 50.0)]
        r = parse_summary(instanz(f), DOC)
        j = r['jahre'][-1]
        self.assertEqual((r['standard'], j['standard'], j['fields']['eps_basic'], j['fields']['net_income'], j['fields']['dps']), ('ifrs', 'ifrs', 150.0, 9e9, 50.0))

    def test_umstellung_jgaap_auf_ifrs_je_jahr(self):
        f = [('BasicEarningsLossPerShareIFRS', 'CurrentYearDuration', 'JPYPerShares', 150.0), ('BasicEarningsLossPerShareIFRS', 'Prior1YearDuration', 'JPYPerShares', 140.0),
             ('BasicEarningsLossPerShare', 'Prior3YearDuration', 'JPYPerShares', 120.0), ('ProfitLossAttributableToOwnersOfParent', 'Prior3YearDuration', 'JPY', 7e9),
             ('BasicEarningsLossPerShare', 'Prior1YearDuration', 'JPYPerShares', 139.0)]
        r = parse_summary(instanz(f), DOC)
        j = {x['end']: x for x in r['jahre']}
        self.assertEqual((r['standard'], j['2026-03-31']['standard'], j['2023-03-31']['standard'], j['2023-03-31']['fields']['net_income']), ('ifrs', 'ifrs', 'jgaap', 7e9))
        self.assertNotIn('2025-03-31', j, 'Übergangsjahr mit beiden Standards im Konzern bleibt offen')
        self.assertIn('standard:2025-03-31', r['konflikte'])

    def test_widerspruch_falsche_einheit_und_identitaet(self):
        f = jgaap() + [('BasicEarningsLossPerShare', 'CurrentYearDuration', 'JPYPerShares', 301.0)]
        r = parse_summary(instanz(f), DOC)
        self.assertIsNone([x for x in r['jahre'] if x['end'] == '2026-03-31'][0]['fields']['eps_basic'])
        self.assertIn('eps_basic:2026-03-31', r['konflikte'])
        falsch = [(e, c, 'JPY' if u == 'JPYPerShares' else u, v) for e, c, u, v in jgaap()]
        self.assertIsNone(parse_summary(instanz(falsch), DOC)['jahre'][-1]['fields']['bvps'], 'Je-Aktie-Wert mit Einheit JPY zählt nicht')
        with self.assertRaisesRegex(ValueError, 'issuer_unconfirmed'):
            parse_summary(instanz(jgaap(), code='E09999'), DOC)
        with self.assertRaisesRegex(ValueError, 'consolidation_unconfirmed'):
            parse_summary(instanz(jgaap(), konsolidiert='false'), DOC)

    def test_unsicher_oder_mehrdeutig(self):
        with self.assertRaisesRegex(ValueError, 'unsafe_xml'):
            parse_summary(b'<!DOCTYPE x [<!ENTITY a "b">]><x/>', DOC)
        beides = jgaap() + [('ProfitLossAttributableToOwnersOfParentIFRS', 'CurrentYearDuration', 'JPY', 1.0)]
        with self.assertRaisesRegex(ValueError, 'ambiguous_or_unsupported_taxonomy'):
            parse_summary(instanz(beides), DOC)
        ohne_aktuell = [x for x in jgaap() if not x[1].startswith('CurrentYear')]
        with self.assertRaisesRegex(ValueError, 'invalid_annual_period'):
            parse_summary(instanz(ohne_aktuell), DOC)

    def test_zip_genau_eine_instanz(self):
        def z(*namen):
            b = io.BytesIO()
            with zipfile.ZipFile(b, 'w') as a:
                for n in namen:
                    a.writestr(n, instanz(jgaap()))
            return b.getvalue()
        self.assertEqual(parse_zip(z('XBRL/PublicDoc/x.xbrl'), DOC)['standard'], 'jgaap')
        self.assertEqual(len(parse_zip(z('XBRL/PublicDoc/x.xbrl'), DOC)['fileSha256']), 64)
        with self.assertRaisesRegex(ValueError, 'ambiguous_public_instance'):
            parse_zip(z('XBRL/PublicDoc/a.xbrl', 'XBRL/PublicDoc/b.xbrl'), DOC)


def idx(doc_id, ende, eingereicht, typ='120', parent=None, code='12340', edinet='E01234', **o):
    return {'docID': doc_id, 'docTypeCode': typ, 'secCode': code, 'edinetCode': edinet, 'periodStart': None, 'periodEnd': ende, 'submitDateTime': eingereicht,
            'xbrlFlag': '1', 'withdrawalStatus': '0', 'disclosureStatus': '0', 'docInfoEditStatus': '0', 'fundCode': None, 'parentDocID': parent, 'indexDate': eingereicht[:10], **o}


NEU = {**idx('S100NEU1', '2026-03-31', '2026-06-23 10:00'), 'periodStart': '2025-04-01'}


class AlterBericht(unittest.TestCase):
    def test_ziel_und_auswahl(self):
        ende, tag = alt_ziel(NEU)
        self.assertEqual((ende.isoformat(), tag.isoformat()), ('2022-03-31', '2022-06-23'))
        docs = [idx('S100ALT1', '2022-03-31', '2022-06-24 09:30'), idx('S100XXX1', '2022-03-31', '2022-06-24 09:30', code='99990', edinet='E09999'),
                idx('S100ALT9', '2021-03-31', '2021-06-24 09:30')]
        self.assertEqual(select_alt(docs, NEU, '12340', NOW)['docID'], 'S100ALT1')

    def test_korrektur_zurueckgezogen_einsichtsfrist_mehrdeutig(self):
        with self.assertRaisesRegex(ValueError, 'korrektur_vorhanden'):
            select_alt([idx('S100ALT1', '2022-03-31', '2022-06-24 09:30'), idx('S100KOR1', '2022-03-31', '2022-08-01 09:30', typ='130', parent='S100ALT1')], NEU, '12340', NOW)
        self.assertIsNone(select_alt([idx('S100ALT1', '2022-03-31', '2022-06-24 09:30', withdrawalStatus='1')], NEU, '12340', NOW))
        with self.assertRaisesRegex(ValueError, 'ausserhalb_einsichtsfrist'):
            select_alt([idx('S100ALT1', '2022-03-31', '2022-06-24 09:30')], NEU, '12340', NOW + dt.timedelta(days=1200))
        with self.assertRaisesRegex(ValueError, 'ambiguous_filer'):
            select_alt([idx('S100ALT1', '2022-03-31', '2022-06-24 09:30'), idx('S100ALT2', '2022-03-31', '2022-06-25 09:30')], NEU, '12340', NOW)


class Lauf(unittest.TestCase):
    def test_run_liest_zwei_berichte_und_ueberspringt_danach(self):
        row = {'listing_symbol': 'TSE:7203', 'isin': 'JP3633400001', 'currency': 'JPY', 'ticker': '7203.T'}  # gültige ISIN (Toyota)
        neu = {**NEU, 'secCode': '72030'}

        def zipdaten():
            b = io.BytesIO()
            with zipfile.ZipFile(b, 'w') as a:
                a.writestr('XBRL/PublicDoc/x.xbrl', instanz(jgaap()))
            return b.getvalue()
        alt_inst = instanz(jgaap()).replace(b'2026-03-31', b'2022-03-31').replace(b'2025-03-31', b'2021-03-31').replace(b'2025-04-01', b'2021-04-01')
        geladen = []

        def get_zip(doc_id):
            geladen.append(doc_id)
            if doc_id == 'S100NEU1':
                return zipdaten()
            b = io.BytesIO()
            with zipfile.ZipFile(b, 'w') as a:
                a.writestr('XBRL/PublicDoc/x.xbrl', alt_inst)
            return b.getvalue()
        tage = {'2022-06-24': [idx('S100ALT1', '2022-03-31', '2022-06-24 09:30', code='72030')]}

        def get_day(d):
            return {'metadata': {'status': '200'}, 'results': tage.get(d, [])}
        index = {'days': {'2026-06-23': {'documents': [neu]}}}
        st = run({'kandidaten': [row]}, index, {}, get_day, get_zip, now=NOW)
        e = st['stocks']['TSE:7203']
        self.assertEqual((st['method'], e['alt_status'], [b['docID'] for b in e['berichte']]), (METHOD, 'ok', ['S100NEU1', 'S100ALT1']))
        self.assertEqual(st['report']['tage_geladen'], 21, '±10 Tage um den Zieltag')
        st2 = run({'kandidaten': [row]}, index, st, get_day, get_zip, now=NOW)
        self.assertEqual((st2['report']['unveraendert'], len(geladen)), (1, 2), 'unveränderter neuester Bericht: kein neuer Abruf')
        anders = run({'kandidaten': [{**row, 'isin': 'JP3435000009'}]}, index, st2, get_day, get_zip, now=NOW)
        self.assertEqual(anders['report']['neu_gelesen'], 1, 'andere ISIN: alter Eintrag verworfen, neu gelesen')


if __name__ == '__main__':
    unittest.main()
